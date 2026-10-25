import asyncio
import re
import secrets
import time
from datetime import date
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pymongo import DESCENDING
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.config import get_settings
from app.database import get_database
from app.schemas import (
    AdminLogin,
    AdminOutput,
    BookingCreate,
    BookingNoteUpdate,
    BookingOutput,
    BookingStatus,
    BookingStatusUpdate,
    ContactCreate,
    ContactOutput,
    ContactStatus,
    ContactStatusUpdate,
    CustomerBookingOutput,
    CustomerOutput,
    CustomerRegister,
    ExperienceInput,
    ExperienceOutput,
    PaginatedContacts,
    PaginatedBookings,
    utc_now,
)
from app.security import (
    COOKIE_NAME,
    CUSTOMER_COOKIE_NAME,
    TOKEN_LIFETIME,
    create_access_token,
    customer_from_cookie,
    require_admin,
    require_customer,
    verify_password,
    hash_password,
)

api = APIRouter(prefix="/api")
ALLOWED_TRANSITIONS = {
    BookingStatus.pendiente: {BookingStatus.confirmada, BookingStatus.rechazada, BookingStatus.cancelada},
    BookingStatus.confirmada: {BookingStatus.cancelada},
    BookingStatus.rechazada: set(),
    BookingStatus.cancelada: set(),
}


async def enforce_rate_limit(request: Request, scope: str, limit: int, window: int = 900) -> None:
    client_ip = request.client.host if request.client else "unknown"
    key = (scope, client_ip)
    now = time.monotonic()
    buckets: dict[tuple[str, str], list[float]] = request.app.state.rate_limits
    lock: asyncio.Lock = request.app.state.rate_limit_lock
    async with lock:
        for existing_key, timestamps in list(buckets.items()):
            recent = [timestamp for timestamp in timestamps if now - timestamp < window]
            if recent:
                buckets[existing_key] = recent
            else:
                buckets.pop(existing_key, None)
        recent = buckets.get(key, [])
        if len(recent) >= limit:
            raise HTTPException(status_code=429, detail="Demasiadas solicitudes. Intenta nuevamente más tarde.")
        buckets[key] = [*recent, now]


def object_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=404, detail="No se encontró el recurso solicitado.")
    return ObjectId(value)


def mongo_id(document: dict[str, Any]) -> dict[str, Any]:
    document["id"] = str(document.pop("_id"))
    if isinstance(document.get("experiencia_id"), ObjectId):
        document["experiencia_id"] = str(document["experiencia_id"])
    return document


def safe_admin(admin: dict[str, Any]) -> AdminOutput:
    return AdminOutput(email=admin["email"], nombre=admin.get("nombre", ""), rol=admin["rol"])


@api.get("/configuracion")
async def public_configuration() -> dict[str, str]:
    settings = get_settings()
    return {
        "nombre_comercial": settings.business_name,
        "whatsapp": settings.whatsapp_number,
        "email_contacto": settings.contact_email,
    }


@api.get("/experiencias", response_model=list[ExperienceOutput])
async def list_experiences(
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
) -> list[dict[str, Any]]:
    cursor = database["experiencias"].find({"activa": True}).sort("fecha_creacion", DESCENDING).limit(100)
    return [mongo_id(item) async for item in cursor]


@api.get("/experiencias/{experience_id}", response_model=ExperienceOutput)
async def get_experience(
    experience_id: str,
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
) -> dict[str, Any]:
    item = await database["experiencias"].find_one({"_id": object_id(experience_id), "activa": True})
    if item is None:
        raise HTTPException(status_code=404, detail="No se encontró la experiencia solicitada.")
    return mongo_id(item)


@api.get("/admin/experiencias", response_model=list[ExperienceOutput])
async def list_all_experiences(
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
    _: dict[str, Any] = Depends(require_admin),
) -> list[dict[str, Any]]:
    cursor = database["experiencias"].find({}).sort("fecha_creacion", DESCENDING).limit(200)
    return [mongo_id(item) async for item in cursor]


@api.post("/experiencias", response_model=ExperienceOutput, status_code=status.HTTP_201_CREATED)
async def create_experience(
    payload: ExperienceInput,
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    now = utc_now()
    document = payload.model_dump(mode="json")
    document.update({"fecha_creacion": now, "fecha_actualizacion": now})
    try:
        result = await database["experiencias"].insert_one(document)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Ya existe una experiencia con ese identificador.") from None
    document["_id"] = result.inserted_id
    return mongo_id(document)


@api.put("/experiencias/{experience_id}", response_model=ExperienceOutput)
async def update_experience(
    experience_id: str,
    payload: ExperienceInput,
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    document = payload.model_dump(mode="json")
    document["fecha_actualizacion"] = utc_now()
    try:
        result = await database["experiencias"].find_one_and_update(
            {"_id": object_id(experience_id)},
            {"$set": document},
            return_document=True,
        )
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Ya existe una experiencia con ese identificador.") from None
    if result is None:
        raise HTTPException(status_code=404, detail="No se encontró la experiencia solicitada.")
    return mongo_id(result)


@api.delete("/experiencias/{experience_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_experience(
    experience_id: str,
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
    _: dict[str, Any] = Depends(require_admin),
) -> Response:
    result = await database["experiencias"].update_one(
        {"_id": object_id(experience_id)},
        {"$set": {"activa": False, "fecha_actualizacion": utc_now()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="No se encontró la experiencia solicitada.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api.post("/reservas", status_code=status.HTTP_201_CREATED)
async def create_booking(
    payload: BookingCreate,
    request: Request,
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
) -> dict[str, str]:
    await enforce_rate_limit(request, "reservas", limit=10)
    customer = await customer_from_cookie(request, database)
    email = str(payload.email).lower()
    if customer is not None and email != customer["email"]:
        raise HTTPException(status_code=403, detail="Usa el correo asociado a tu cuenta para registrar esta solicitud.")
    experience_id = ObjectId(payload.experiencia_id)
    experience = await database["experiencias"].find_one({"_id": experience_id, "activa": True})
    if experience is None:
        raise HTTPException(status_code=404, detail="La experiencia no existe o no está disponible para solicitudes.")
    duplicate_filter = {
        "experiencia_id": experience_id,
        "email": email,
        "fecha_solicitada": payload.fecha_solicitada.isoformat(),
        "estado": {"$in": [BookingStatus.pendiente.value, BookingStatus.confirmada.value]},
    }
    if await database["reservas"].find_one(duplicate_filter):
        raise HTTPException(status_code=409, detail="Ya existe una solicitud pendiente o confirmada para esos datos.")
    code = f"CT-{secrets.token_hex(4).upper()}"
    now = utc_now()
    document = payload.model_dump(mode="json")
    document.update(
        {
            "codigo_reserva": code,
            "email": email,
            "experiencia_id": experience_id,
            "experiencia_nombre": experience["nombre"],
            "fecha_solicitada": payload.fecha_solicitada.isoformat(),
            "estado": BookingStatus.pendiente.value,
            "fecha_creacion": now,
            "fecha_actualizacion": now,
            "notas_administrativas": "",
        }
    )
    if customer is not None:
        document["cliente_id"] = customer["_id"]
    await database["reservas"].insert_one(document)
    return {
        "codigo_reserva": code,
        "estado": BookingStatus.pendiente.value,
        "mensaje": "Solicitud registrada. El operador debe confirmar disponibilidad; esto no confirma una reserva.",
    }


@api.get("/clientes/auth/me", response_model=CustomerOutput)
async def current_customer(customer: dict[str, Any] = Depends(require_customer)) -> CustomerOutput:
    return CustomerOutput(email=customer["email"], nombre=customer.get("nombre", ""), rol="cliente")


@api.post("/clientes/auth/registro", response_model=CustomerOutput, status_code=status.HTTP_201_CREATED)
async def register_customer(
    payload: CustomerRegister,
    request: Request,
    response: Response,
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
) -> CustomerOutput:
    await enforce_rate_limit(request, "registro_cliente", limit=5)
    email = str(payload.email).lower()
    customer = {
        "nombre": payload.nombre,
        "email": email,
        "password_hash": hash_password(payload.password),
        "rol": "cliente",
        "activo": True,
        "fecha_creacion": utc_now(),
    }
    try:
        result = await database["clientes"].insert_one(customer)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese correo.") from None
    token = create_access_token(str(result.inserted_id))
    response.set_cookie(
        CUSTOMER_COOKIE_NAME,
        token,
        max_age=int(TOKEN_LIFETIME.total_seconds()),
        httponly=True,
        secure=get_settings().environment.lower() == "production",
        samesite="strict",
        path="/",
    )
    return CustomerOutput(email=email, nombre=payload.nombre, rol="cliente")


@api.post("/clientes/auth/login", response_model=CustomerOutput)
async def customer_login(
    payload: AdminLogin,
    request: Request,
    response: Response,
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
) -> CustomerOutput:
    await enforce_rate_limit(request, "login_cliente", limit=5)
    customer = await database["clientes"].find_one({"email": str(payload.email).lower(), "activo": True})
    if customer is None or customer.get("rol") != "cliente" or not verify_password(
        payload.password, customer.get("password_hash", "")
    ):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos.")
    token = create_access_token(str(customer["_id"]))
    response.set_cookie(
        CUSTOMER_COOKIE_NAME,
        token,
        max_age=int(TOKEN_LIFETIME.total_seconds()),
        httponly=True,
        secure=get_settings().environment.lower() == "production",
        samesite="strict",
        path="/",
    )
    return CustomerOutput(email=customer["email"], nombre=customer.get("nombre", ""), rol="cliente")


@api.post("/clientes/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def customer_logout(
    response: Response,
    _: dict[str, Any] = Depends(require_customer),
) -> Response:
    response.delete_cookie(CUSTOMER_COOKIE_NAME, path="/", httponly=True, samesite="strict")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@api.get("/clientes/me/reservas", response_model=list[CustomerBookingOutput])
async def customer_bookings(
    customer: dict[str, Any] = Depends(require_customer),
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
) -> list[dict[str, Any]]:
    cursor = database["reservas"].find({"cliente_id": customer["_id"]}).sort("fecha_creacion", DESCENDING).limit(100)
    return [CustomerBookingOutput(**mongo_id(item)) async for item in cursor]


@api.get("/reservas", response_model=PaginatedBookings)
async def list_bookings(
    estado: BookingStatus | None = None,
    fecha: date | None = None,
    busqueda: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100_000),
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if estado:
        query["estado"] = estado.value
    if fecha:
        query["fecha_solicitada"] = fecha.isoformat()
    if busqueda and busqueda.strip():
        escaped = re.escape(busqueda.strip())
        query["$or"] = [
            {"nombre_completo": {"$regex": escaped, "$options": "i"}},
            {"email": {"$regex": escaped, "$options": "i"}},
            {"codigo_reserva": {"$regex": escaped, "$options": "i"}},
        ]
    collection = database["reservas"]
    total = await collection.count_documents(query)
    cursor = collection.find(query).sort("fecha_creacion", DESCENDING).skip(offset).limit(limit)
    items = [BookingOutput(**mongo_id(item)) async for item in cursor]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@api.get("/reservas/{booking_id}", response_model=BookingOutput)
async def get_booking(
    booking_id: str,
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    item = await database["reservas"].find_one({"_id": object_id(booking_id)})
    if item is None:
        raise HTTPException(status_code=404, detail="No se encontró la solicitud.")
    return mongo_id(item)


@api.patch("/reservas/{booking_id}/estado", response_model=BookingOutput)
async def update_booking_status(
    booking_id: str,
    payload: BookingStatusUpdate,
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    collection = database["reservas"]
    current = await collection.find_one({"_id": object_id(booking_id)})
    if current is None:
        raise HTTPException(status_code=404, detail="No se encontró la solicitud.")
    current_status = BookingStatus(current["estado"])
    if payload.estado not in ALLOWED_TRANSITIONS[current_status]:
        raise HTTPException(status_code=409, detail=f"No se permite cambiar de {current_status.value} a {payload.estado.value}.")
    changes: dict[str, Any] = {
        "estado": payload.estado.value,
        "fecha_actualizacion": utc_now(),
    }
    if payload.notas_administrativas is not None:
        changes["notas_administrativas"] = payload.notas_administrativas
    result = await collection.find_one_and_update(
        {"_id": current["_id"], "estado": current_status.value},
        {"$set": changes},
        return_document=True,
    )
    if result is None:
        raise HTTPException(status_code=409, detail="La solicitud cambió en otra operación; vuelve a cargarla.")
    return mongo_id(result)


@api.patch("/reservas/{booking_id}/notas", response_model=BookingOutput)
async def update_booking_notes(
    booking_id: str,
    payload: BookingNoteUpdate,
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    result = await database["reservas"].find_one_and_update(
        {"_id": object_id(booking_id)},
        {"$set": {"notas_administrativas": payload.notas_administrativas, "fecha_actualizacion": utc_now()}},
        return_document=True,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="No se encontró la solicitud.")
    return mongo_id(result)


@api.post("/contacto", status_code=status.HTTP_201_CREATED)
async def create_contact(
    payload: ContactCreate,
    request: Request,
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
) -> dict[str, str]:
    await enforce_rate_limit(request, "contacto", limit=5)
    document = payload.model_dump(mode="json")
    document.update({"email": str(payload.email).lower(), "fecha_creacion": utc_now(), "estado": "nuevo"})
    await database["contactos"].insert_one(document)
    return {"mensaje": "Tu mensaje fue recibido. Nos pondremos en contacto contigo."}


@api.get("/contactos", response_model=PaginatedContacts)
async def list_contacts(
    estado: ContactStatus | None = None,
    busqueda: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100_000),
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if estado:
        query["estado"] = estado.value
    if busqueda and busqueda.strip():
        escaped = re.escape(busqueda.strip())
        query["$or"] = [
            {"nombre": {"$regex": escaped, "$options": "i"}},
            {"email": {"$regex": escaped, "$options": "i"}},
            {"asunto": {"$regex": escaped, "$options": "i"}},
        ]
    collection = database["contactos"]
    total = await collection.count_documents(query)
    cursor = collection.find(query).sort("fecha_creacion", DESCENDING).skip(offset).limit(limit)
    items = [ContactOutput(**mongo_id(item)) async for item in cursor]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@api.patch("/contactos/{contact_id}/estado", response_model=ContactOutput)
async def update_contact_status(
    contact_id: str,
    payload: ContactStatusUpdate,
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    result = await database["contactos"].find_one_and_update(
        {"_id": object_id(contact_id)},
        {"$set": {"estado": payload.estado.value}},
        return_document=True,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="No se encontró el mensaje de contacto.")
    return mongo_id(result)


@api.post("/auth/login", response_model=AdminOutput)
async def login(
    payload: AdminLogin,
    request: Request,
    response: Response,
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
) -> AdminOutput:
    await enforce_rate_limit(request, "login", limit=5)
    admin = await database["administradores"].find_one({"email": str(payload.email).lower(), "activo": True})
    if admin is None or not verify_password(payload.password, admin.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos.")
    token = create_access_token(admin["email"])
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(TOKEN_LIFETIME.total_seconds()),
        httponly=True,
        secure=get_settings().environment.lower() == "production",
        samesite="strict",
        path="/",
    )
    return safe_admin(admin)


@api.get("/auth/me", response_model=AdminOutput)
async def current_admin(admin: dict[str, Any] = Depends(require_admin)) -> AdminOutput:
    return safe_admin(admin)


@api.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    _: dict[str, Any] = Depends(require_admin),
) -> Response:
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="strict")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@api.get("/admin/dashboard")
async def dashboard(
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, int]:
    reservations = database["reservas"]
    experiences = database["experiencias"]
    return {
        "solicitudes": await reservations.count_documents({}),
        "pendientes": await reservations.count_documents({"estado": BookingStatus.pendiente.value}),
        "confirmadas": await reservations.count_documents({"estado": BookingStatus.confirmada.value}),
        "canceladas": await reservations.count_documents({"estado": BookingStatus.cancelada.value}),
        "experiencias": await experiences.count_documents({}),
        "contactos_nuevos": await database["contactos"].count_documents({"estado": ContactStatus.nuevo.value}),
    }
