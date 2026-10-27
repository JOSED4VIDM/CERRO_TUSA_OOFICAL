from datetime import datetime, timezone

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.contrib.auth.hashers import make_password
from pymongo.errors import DuplicateKeyError

from store.mongo import get_database


class Command(BaseCommand):
    help = "Crea la cuenta administradora inicial de TechGear usando variables de entorno."

    def handle(self, *args, **options):
        email = settings.TECHGEAR_ADMIN_EMAIL
        password = settings.TECHGEAR_ADMIN_PASSWORD
        if not email or not password:
            raise CommandError("Configura TECHGEAR_ADMIN_EMAIL y TECHGEAR_ADMIN_PASSWORD.")
        try:
            validate_email(email)
        except ValidationError as exc:
            raise CommandError("TECHGEAR_ADMIN_EMAIL debe contener un correo válido.") from exc
        if not 12 <= len(password) <= 128:
            raise CommandError("TECHGEAR_ADMIN_PASSWORD debe tener entre 12 y 128 caracteres.")
        users = get_database()["users"]
        existing = users.find_one({"email": email})
        if existing:
            if existing.get("role") != "admin":
                raise CommandError("Ese correo ya pertenece a un cliente; usa otro correo para el administrador.")
            self.stdout.write(self.style.SUCCESS("El administrador ya existía; no se modificó."))
            return
        document = {
            "name": "TechGear Admin",
            "email": email,
            "password_hash": make_password(password),
            "role": "admin",
            "active": True,
            "created_at": datetime.now(timezone.utc),
        }
        try:
            users.insert_one(document)
        except DuplicateKeyError as exc:
            raise CommandError("Ese correo ya fue registrado; no se creó el administrador.") from exc
        self.stdout.write(self.style.SUCCESS("Administrador creado."))
