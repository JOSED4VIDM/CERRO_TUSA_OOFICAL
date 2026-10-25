import asyncio
import getpass
import re
from datetime import datetime, timezone

from pymongo import AsyncMongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.config import get_settings
from app.database import create_indexes
from app.security import hash_password


async def main() -> None:
    settings = get_settings()
    if not settings.mongodb_uri:
        raise SystemExit("Configura MONGODB_URI antes de crear el administrador.")
    email = (settings.admin_email or input("Correo del administrador: ")).strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise SystemExit("El correo no tiene un formato válido.")
    name = input("Nombre del administrador: ").strip()
    password = getpass.getpass("Contraseña (mínimo 12 caracteres): ")
    confirmation = getpass.getpass("Confirma la contraseña: ")
    if len(password) < 12 or password != confirmation:
        raise SystemExit("La contraseña debe tener al menos 12 caracteres y ambas entradas deben coincidir.")
    client = AsyncMongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
    try:
        await client.admin.command("ping")
        database = client[settings.mongodb_database]
        await create_indexes(database)
        await database["administradores"].insert_one(
            {
                "email": email,
                "nombre": name[:120],
                "password_hash": hash_password(password),
                "rol": "admin",
                "activo": True,
                "fecha_creacion": datetime.now(timezone.utc),
            }
        )
        print(f"Administrador creado: {email}")
    except DuplicateKeyError:
        raise SystemExit("Ya existe una cuenta con ese correo.") from None
    except PyMongoError as exc:
        raise SystemExit(f"No se pudo completar la operación de base de datos ({type(exc).__name__}).") from None
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
