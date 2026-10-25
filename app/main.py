import asyncio
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pymongo.errors import PyMongoError

from app.config import get_settings
from app.database import lifespan
from app.routers import api

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Cerro Tusa Experience API",
    description="API de experiencias turísticas y solicitudes de reserva para Cerro Tusa.",
    version="1.0.0",
    lifespan=lifespan,
)
settings = get_settings()
if settings.allowed_origins:
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Requested-With"],
    )

app.state.rate_limits = {}
app.state.rate_limit_lock = asyncio.Lock()
app.include_router(api)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.exception_handler(PyMongoError)
async def database_error_handler(_: Request, exc: PyMongoError) -> JSONResponse:
    logger.error("Database operation failed: %s", type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "No se pudo completar la operación de datos."})


@app.get("/", include_in_schema=False)
async def home() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/admin", include_in_schema=False)
async def admin_page() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "admin.html")


@app.get("/cuenta", include_in_schema=False)
async def customer_page() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "customer.html")


@app.get("/health")
async def health(request: Request) -> dict[str, str]:
    client: Any = getattr(request.app.state, "mongo_client", None)
    if client is None:
        raise HTTPException(status_code=503, detail="La base de datos no está configurada o no está disponible.")
    try:
        await client.admin.command("ping")
    except PyMongoError:
        raise HTTPException(status_code=503, detail="La base de datos no está disponible.") from None
    return {"status": "ok", "database": "connected"}
