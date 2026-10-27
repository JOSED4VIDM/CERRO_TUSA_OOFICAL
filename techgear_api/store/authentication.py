from datetime import datetime, timedelta, timezone

import jwt
from bson import ObjectId
from django.conf import settings
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from store.mongo import get_database


class MongoUser:
    is_authenticated = True

    def __init__(self, document: dict):
        self.id = str(document["_id"])
        self.pk = self.id
        self.email = document["email"]
        self.name = document.get("name", "")
        self.role = document.get("role", "customer")
        self.is_staff = self.role == "admin"
        self.is_superuser = self.is_staff


class MongoJWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        parts = get_authorization_header(request).decode("utf-8").split()
        if not parts:
            return None
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise AuthenticationFailed("Usa el esquema Authorization: Bearer <token>.")
        if len(settings.TECHGEAR_JWT_SECRET) < 32 and not settings.DEBUG:
            raise AuthenticationFailed("La autenticación de TechGear no está configurada.")
        secret = settings.TECHGEAR_JWT_SECRET or "django-debug-only-techgear-jwt-secret"
        try:
            payload = jwt.decode(parts[1], secret, algorithms=["HS256"])
            user_id = payload.get("sub")
            if not isinstance(user_id, str) or not ObjectId.is_valid(user_id):
                raise jwt.InvalidTokenError
        except jwt.InvalidTokenError as exc:
            raise AuthenticationFailed("La sesión no es válida o expiró.") from exc
        user = get_database()["users"].find_one({"_id": ObjectId(user_id), "active": True})
        if user is None:
            raise AuthenticationFailed("La sesión no es válida o expiró.")
        return MongoUser(user), parts[1]

    def authenticate_header(self, request):
        return "Bearer"


def issue_token(user_id: ObjectId) -> str:
    if len(settings.TECHGEAR_JWT_SECRET) < 32 and not settings.DEBUG:
        raise RuntimeError("Configura TECHGEAR_JWT_SECRET con al menos 32 caracteres.")
    secret = settings.TECHGEAR_JWT_SECRET or "django-debug-only-techgear-jwt-secret"
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(hours=8)},
        secret,
        algorithm="HS256",
    )
