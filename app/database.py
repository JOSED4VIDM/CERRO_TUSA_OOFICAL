from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError
from pymongo import AsyncMongoClient

from app.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.mongo_client = None
    app.state.database = None
    if settings.mongodb_uri:
        client = AsyncMongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
        app.state.mongo_client = client
        app.state.database = client[settings.mongodb_database]
        try:
            await client.admin.command("ping")
            await create_indexes(app.state.database)
        except PyMongoError as exc:
            logger.error("MongoDB startup check failed: %s", type(exc).__name__)
            await client.close()
            app.state.mongo_client = None
            app.state.database = None
    try:
        yield
    finally:
        if app.state.mongo_client is not None:
            await app.state.mongo_client.close()


async def create_indexes(database: AsyncDatabase[dict[str, Any]]) -> None:
    await database["reservas"].create_index("codigo_reserva", unique=True)
    await database["administradores"].create_index("email", unique=True)
    await database["clientes"].create_index("email", unique=True)
    await database["experiencias"].create_index("slug", unique=True)
    await database["reservas"].create_index([("fecha_solicitada", ASCENDING), ("estado", ASCENDING)])
    await database["reservas"].create_index([("fecha_creacion", DESCENDING)])
    await database["reservas"].create_index([("cliente_id", ASCENDING), ("fecha_creacion", DESCENDING)])
    await database["contactos"].create_index([("fecha_creacion", DESCENDING)])


async def get_database(request: Request) -> AsyncDatabase[dict[str, Any]]:
    database = getattr(request.app.state, "database", None)
    if database is None:
        raise HTTPException(status_code=503, detail="El servicio de datos no está disponible.")
    return database
