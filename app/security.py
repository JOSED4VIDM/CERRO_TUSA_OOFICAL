from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from bson import ObjectId
from fastapi import Depends, HTTPException, Request, status
from pwdlib import PasswordHash
from pymongo.asynchronous.database import AsyncDatabase

from app.config import get_settings
from app.database import get_database

password_hash = PasswordHash.recommended()
COOKIE_NAME = "cerro_tusa_admin"
CUSTOMER_COOKIE_NAME = "cerro_tusa_customer"
TOKEN_LIFETIME = timedelta(hours=8)


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return password_hash.verify(password, encoded)
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str) -> str:
    secret = get_settings().jwt_secret
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="La autenticación no está configurada de forma segura.")
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": subject, "iat": now, "exp": now + TOKEN_LIFETIME},
        secret,
        algorithm="HS256",
    )


async def require_admin(
    request: Request,
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
) -> dict[str, Any]:
    token = request.cookies.get(COOKIE_NAME)
    secret = get_settings().jwt_secret
    if not token or len(secret) < 32:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida.")
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        email = payload.get("sub")
        if not isinstance(email, str):
            raise jwt.InvalidTokenError
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="La sesión no es válida o expiró.") from None
    admin = await database["administradores"].find_one({"email": email, "activo": True})
    if admin is None or admin.get("rol") != "admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="La sesión no es válida o expiró.")
    return admin


async def customer_from_cookie(
    request: Request,
    database: AsyncDatabase[dict[str, Any]],
) -> dict[str, Any] | None:
    token = request.cookies.get(CUSTOMER_COOKIE_NAME)
    if not token:
        return None
    secret = get_settings().jwt_secret
    if len(secret) < 32:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="La autenticación no está configurada de forma segura.")
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        subject = payload.get("sub")
        if not isinstance(subject, str) or not ObjectId.is_valid(subject):
            raise jwt.InvalidTokenError
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="La sesión no es válida o expiró.") from None
    customer = await database["clientes"].find_one({"_id": ObjectId(subject), "activo": True})
    if customer is None or customer.get("rol") != "cliente":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="La sesión no es válida o expiró.")
    return customer


async def require_customer(
    request: Request,
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
) -> dict[str, Any]:
    customer = await customer_from_cookie(request, database)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida.")
    return customer
