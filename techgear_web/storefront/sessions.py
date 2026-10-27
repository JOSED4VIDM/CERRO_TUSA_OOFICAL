from datetime import datetime, timezone
from functools import lru_cache

import dns.resolver
from django.conf import settings
from django.contrib.sessions.backends.base import CreateError, SessionBase
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError


@lru_cache(maxsize=1)
def _session_collection():
    if not settings.TECHGEAR_MONGODB_URI:
        raise RuntimeError("Configura TECHGEAR_MONGODB_URI para guardar las sesiones de la tienda.")
    nameservers = [item.strip() for item in settings.TECHGEAR_DNS_NAMESERVERS.split(",") if item.strip()]
    if nameservers:
        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = nameservers
        resolver.timeout = 3
        resolver.lifetime = 5
        dns.resolver.default_resolver = resolver
    client = MongoClient(settings.TECHGEAR_MONGODB_URI, serverSelectionTimeoutMS=5000, appname="TechGearWeb")
    collection = client[settings.TECHGEAR_MONGODB_DATABASE]["web_sessions"]
    collection.create_index("expires_at", expireAfterSeconds=0)
    return collection


class SessionStore(SessionBase):
    def load(self):
        if not self.session_key:
            return {}
        document = _session_collection().find_one({
            "_id": self.session_key,
            "expires_at": {"$gt": datetime.now(timezone.utc)},
        })
        return self.decode(document["session_data"]) if document else {}

    def exists(self, session_key):
        return _session_collection().find_one({"_id": session_key}, {"_id": 1}) is not None

    def create(self):
        while True:
            self._session_key = self._get_new_session_key()
            try:
                self.save(must_create=True)
            except CreateError:
                continue
            self.modified = True
            return

    def save(self, must_create=False):
        if self.session_key is None:
            self._session_key = self._get_new_session_key()
        document = {
            "session_data": self.encode(self._get_session(no_load=must_create)),
            "expires_at": self.get_expiry_date(),
        }
        collection = _session_collection()
        try:
            if must_create:
                collection.insert_one({"_id": self.session_key, **document})
                return
            result = _session_collection().replace_one(
                {"_id": self.session_key},
                {"_id": self.session_key, **document},
                upsert=True,
            )
        except DuplicateKeyError as exc:
            raise CreateError from exc

    def delete(self, session_key=None):
        key = session_key or self.session_key
        if key:
            _session_collection().delete_one({"_id": key})

    @classmethod
    def clear_expired(cls):
        _session_collection().delete_many({"expires_at": {"$lte": datetime.now(timezone.utc)}})
