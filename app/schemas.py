import re
from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, StringConstraints, field_validator

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class BookingStatus(StrEnum):
    pendiente = "pendiente"
    confirmada = "confirmada"
    rechazada = "rechazada"
    cancelada = "cancelada"


class ContactStatus(StrEnum):
    nuevo = "nuevo"
    contactado = "contactado"
    archivado = "archivado"


class ExperienceInput(BaseModel):
    nombre: ShortText
    slug: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
    descripcion: LongText
    imagen: HttpUrl | None = None
    precio: Annotated[int, Field(ge=0, le=100_000_000)] | None = None
    duracion: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] = ""
    dificultad: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] = ""
    requisitos: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ""
    activa: bool = False


class ExperienceOutput(ExperienceInput):
    id: str
    fecha_creacion: datetime
    fecha_actualizacion: datetime


class BookingCreate(BaseModel):
    nombre_completo: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
    email: EmailStr
    telefono: Annotated[str, StringConstraints(strip_whitespace=True, min_length=7, max_length=30)]
    experiencia_id: Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{24}$")]
    fecha_solicitada: date
    numero_participantes: Annotated[int, Field(ge=1, le=20)]
    comentarios: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] = ""
    aceptacion_privacidad: bool

    @field_validator("telefono")
    @classmethod
    def phone_has_contactable_characters(cls, value: str) -> str:
        if not re.fullmatch(r"[+()\d .-]{7,30}", value):
            raise ValueError("Ingresa un número de teléfono válido.")
        return value

    @field_validator("fecha_solicitada")
    @classmethod
    def date_is_not_in_the_past(cls, value: date) -> date:
        if value < datetime.now(timezone.utc).date():
            raise ValueError("La fecha solicitada no puede estar en el pasado.")
        return value

    @field_validator("aceptacion_privacidad")
    @classmethod
    def privacy_must_be_accepted(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Debes aceptar la política de privacidad.")
        return value


class BookingStatusUpdate(BaseModel):
    estado: BookingStatus
    notas_administrativas: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


class BookingNoteUpdate(BaseModel):
    notas_administrativas: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class BookingOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    codigo_reserva: str
    nombre_completo: str
    email: EmailStr
    telefono: str
    experiencia_id: str
    experiencia_nombre: str
    fecha_solicitada: date
    numero_participantes: int
    comentarios: str
    estado: BookingStatus
    aceptacion_privacidad: bool = False
    fecha_creacion: datetime
    fecha_actualizacion: datetime
    notas_administrativas: str = ""


class ContactCreate(BaseModel):
    nombre: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
    email: EmailStr
    telefono: Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)] = ""
    asunto: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
    mensaje: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=2000)]


class ContactStatusUpdate(BaseModel):
    estado: ContactStatus


class ContactOutput(BaseModel):
    id: str
    nombre: str
    email: EmailStr
    telefono: str = ""
    asunto: str
    mensaje: str
    fecha_creacion: datetime
    estado: ContactStatus


class AdminLogin(BaseModel):
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class AdminOutput(BaseModel):
    email: EmailStr
    nombre: str
    rol: str


class CustomerRegister(BaseModel):
    nombre: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=12, max_length=128)]


class CustomerOutput(BaseModel):
    email: EmailStr
    nombre: str
    rol: str


class CustomerBookingOutput(BaseModel):
    id: str
    codigo_reserva: str
    experiencia_nombre: str
    fecha_solicitada: date
    numero_participantes: int
    estado: BookingStatus
    fecha_creacion: datetime


class PaginatedBookings(BaseModel):
    items: list[BookingOutput]
    total: int
    limit: int
    offset: int


class PaginatedContacts(BaseModel):
    items: list[ContactOutput]
    total: int
    limit: int
    offset: int


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
