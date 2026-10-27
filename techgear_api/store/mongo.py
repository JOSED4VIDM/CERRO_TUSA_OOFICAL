from functools import lru_cache

import dns.resolver
from django.conf import settings
from pymongo import MongoClient
from pymongo.database import Database


class MongoConfigurationError(RuntimeError):
    pass


def configure_dns_resolver() -> None:
    nameservers = [item.strip() for item in settings.TECHGEAR_DNS_NAMESERVERS.split(",") if item.strip()]
    if not nameservers:
        return
    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = nameservers
    resolver.timeout = 3
    resolver.lifetime = 5
    dns.resolver.default_resolver = resolver


@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    if not settings.TECHGEAR_MONGODB_URI:
        raise MongoConfigurationError("Configura TECHGEAR_MONGODB_URI para conectar TechGear con MongoDB Atlas.")
    configure_dns_resolver()
    return MongoClient(settings.TECHGEAR_MONGODB_URI, serverSelectionTimeoutMS=5000, appname="TechGear")


@lru_cache(maxsize=1)
def get_database() -> Database:
    database = get_client()[settings.TECHGEAR_MONGODB_DATABASE]
    database["users"].create_index("email", unique=True)
    database["categories"].create_index("slug", unique=True)
    database["products"].create_index("slug", unique=True)
    database["orders"].create_index([("user_id", 1), ("created_at", -1)])
    database["carts"].create_index("user_id", unique=True)
    return database
