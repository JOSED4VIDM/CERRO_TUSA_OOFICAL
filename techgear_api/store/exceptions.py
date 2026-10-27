import logging

from pymongo.errors import PyMongoError
from rest_framework.response import Response
from rest_framework.views import exception_handler

from store.mongo import MongoConfigurationError

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    if isinstance(exc, (MongoConfigurationError, PyMongoError)):
        logger.error("TechGear database operation failed: %s", type(exc).__name__)
        return Response(
            {"detail": "La base de datos de TechGear no está disponible. Verifica la configuración de MongoDB Atlas."},
            status=503,
        )
    return exception_handler(exc, context)
