import copy
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.database import get_database
from app.main import app


def matches(document, query):
    for key, value in query.items():
        if key == "$or":
            if not any(matches(document, clause) for clause in value):
                return False
            continue
        actual = document.get(key)
        if isinstance(value, dict) and "$in" in value:
            if actual not in value["$in"]:
                return False
        elif isinstance(value, dict) and "$regex" in value:
            import re

            if not re.search(value["$regex"], str(actual or ""), re.IGNORECASE):
                return False
        elif actual != value:
            return False
    return True


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, *_):
        return self

    def skip(self, count):
        self.documents = self.documents[count:]
        return self

    def limit(self, count):
        self.documents = self.documents[:count]
        return self

    def __aiter__(self):
        async def iterate():
            for document in self.documents:
                yield copy.deepcopy(document)

        return iterate()


class FakeCollection:
    def __init__(self):
        self.documents = []

    async def find_one(self, query):
        return copy.deepcopy(next((doc for doc in self.documents if matches(doc, query)), None))

    def find(self, query):
        return FakeCursor([doc for doc in self.documents if matches(doc, query)])

    async def count_documents(self, query):
        return sum(matches(document, query) for document in self.documents)

    async def insert_one(self, document):
        saved = copy.deepcopy(document)
        saved.setdefault("_id", ObjectId())
        self.documents.append(saved)
        return SimpleNamespace(inserted_id=saved["_id"])

    async def find_one_and_update(self, query, update, **_):
        for document in self.documents:
            if matches(document, query):
                document.update(copy.deepcopy(update["$set"]))
                return copy.deepcopy(document)
        return None

    async def update_one(self, query, update):
        for document in self.documents:
            if matches(document, query):
                document.update(copy.deepcopy(update["$set"]))
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)


class FakeDatabase:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        return self.collections[name]


@pytest.fixture
def database():
    fake = FakeDatabase()
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: fake
    yield fake
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def test_home_is_served():
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "Cerro Tusa" in response.text


def test_admin_page_is_served():
    with TestClient(app) as client:
        response = client.get("/admin")
    assert response.status_code == 200
    assert "ESPACIO PRIVADO" in response.text
    assert 'id="section-reservations"' in response.text
    assert 'id="section-contacts"' in response.text


def test_customer_account_page_is_served():
    with TestClient(app) as client:
        response = client.get("/cuenta")
    assert response.status_code == 200
    assert 'id="customer-login-form"' in response.text
    assert 'id="customer-register-form"' in response.text


def test_health_reports_missing_database():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert "database" not in response.text.lower() or "no está configurada" in response.text


def test_booking_requires_privacy_acceptance():
    from app.schemas import BookingCreate
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        BookingCreate(
            nombre_completo="Ana Visitante",
            email="ana@example.com",
            telefono="+573001234567",
            experiencia_id="0123456789abcdef01234567",
            fecha_solicitada=date.today() + timedelta(days=1),
            numero_participantes=2,
            aceptacion_privacidad=False,
        )


def test_admin_api_rejects_anonymous_user():
    with TestClient(app) as client:
        response = client.get("/api/admin/dashboard")
    assert response.status_code in (401, 503)


def test_api_documentation_is_available():
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/reservas" in response.json()["paths"]
    assert "/api/contactos" in response.json()["paths"]
    assert "/api/contactos/{contact_id}/estado" in response.json()["paths"]


def test_reservation_is_saved_and_duplicate_is_rejected(database):
    experience_id = ObjectId()
    database["experiencias"].documents.append(
        {"_id": experience_id, "nombre": "Caminata de naturaleza", "activa": True}
    )
    payload = {
        "nombre_completo": "Ana Visitante",
        "email": "ANA@example.com",
        "telefono": "+573001234567",
        "experiencia_id": str(experience_id),
        "fecha_solicitada": (date.today() + timedelta(days=2)).isoformat(),
        "numero_participantes": 2,
        "comentarios": "",
        "aceptacion_privacidad": True,
    }
    with TestClient(app) as client:
        response = client.post("/api/reservas", json=payload)
        duplicate = client.post("/api/reservas", json=payload)

    assert response.status_code == 201
    assert response.json()["estado"] == "pendiente"
    assert response.json()["codigo_reserva"].startswith("CT-")
    assert "no confirma una reserva" in response.json()["mensaje"]
    assert duplicate.status_code == 409
    assert len(database["reservas"].documents) == 1


def test_reservation_rejects_invalid_data_and_unknown_experience(database):
    invalid = {
        "nombre_completo": "A",
        "email": "no-es-correo",
        "telefono": "123",
        "experiencia_id": "0123456789abcdef01234567",
        "fecha_solicitada": (date.today() - timedelta(days=1)).isoformat(),
        "numero_participantes": 0,
        "aceptacion_privacidad": False,
    }
    unknown = {
        **invalid,
        "nombre_completo": "Ana Visitante",
        "email": "ana@example.com",
        "telefono": "+573001234567",
        "fecha_solicitada": (date.today() + timedelta(days=1)).isoformat(),
        "numero_participantes": 1,
        "aceptacion_privacidad": True,
    }
    with TestClient(app) as client:
        invalid_response = client.post("/api/reservas", json=invalid)
        unknown_response = client.post("/api/reservas", json=unknown)
    assert invalid_response.status_code == 422
    assert unknown_response.status_code == 404
    assert database["reservas"].documents == []


def test_admin_login_and_dashboard_do_not_expose_password_hash(database, monkeypatch):
    from app import routers, security

    settings = SimpleNamespace(jwt_secret="a" * 48, environment="test")
    monkeypatch.setattr(routers, "get_settings", lambda: settings)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    database["administradores"].documents.append(
        {
            "_id": ObjectId(),
            "email": "admin@example.com",
            "nombre": "Admin",
            "rol": "admin",
            "activo": True,
            "password_hash": security.hash_password("correct-horse-battery"),
        }
    )
    booking_id = ObjectId()
    database["reservas"].documents.append(
        {
            "_id": booking_id,
            "codigo_reserva": "CT-TEST1234",
            "nombre_completo": "Ana Visitante",
            "email": "ana@example.com",
            "telefono": "+573001234567",
            "experiencia_id": ObjectId(),
            "experiencia_nombre": "Caminata de naturaleza",
            "fecha_solicitada": (date.today() + timedelta(days=2)).isoformat(),
            "numero_participantes": 2,
            "comentarios": "",
            "estado": "pendiente",
            "aceptacion_privacidad": True,
            "fecha_creacion": "2026-10-24T00:00:00+00:00",
            "fecha_actualizacion": "2026-10-24T00:00:00+00:00",
            "notas_administrativas": "Nota privada original",
        }
    )
    contact_id = ObjectId()
    database["contactos"].documents.append(
        {
            "_id": contact_id,
            "nombre": "Ana Visitante",
            "email": "ana@example.com",
            "telefono": "+573001234567",
            "asunto": "Consulta de recorrido",
            "mensaje": "Quisiera información del recorrido.",
            "estado": "nuevo",
            "fecha_creacion": "2026-10-24T00:00:00+00:00",
        }
    )
    with TestClient(app) as client:
        denied = client.get("/api/admin/dashboard")
        denied_contacts = client.get("/api/contactos")
        login = client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "correct-horse-battery"},
        )
        dashboard = client.get("/api/admin/dashboard")
        transition = client.patch(
            f"/api/reservas/{booking_id}/estado",
            json={"estado": "confirmada"},
        )
        updated_note = client.patch(
            f"/api/reservas/{booking_id}/notas",
            json={"notas_administrativas": "Nota actualizada"},
        )
        invalid_transition = client.patch(
            f"/api/reservas/{booking_id}/estado",
            json={"estado": "rechazada"},
        )
        contact_list = client.get("/api/contactos?estado=nuevo")
        contact_status = client.patch(
            f"/api/contactos/{contact_id}/estado",
            json={"estado": "contactado"},
        )

    assert denied.status_code == 401
    assert denied_contacts.status_code == 401
    assert login.status_code == 200
    assert "password_hash" not in login.text
    assert dashboard.status_code == 200
    assert dashboard.json()["solicitudes"] == 1
    assert dashboard.json()["contactos_nuevos"] == 1
    assert transition.status_code == 200
    assert transition.json()["notas_administrativas"] == "Nota privada original"
    assert transition.json()["aceptacion_privacidad"] is True
    assert updated_note.status_code == 200
    assert updated_note.json()["notas_administrativas"] == "Nota actualizada"
    assert invalid_transition.status_code == 409
    assert contact_list.status_code == 200
    assert contact_list.json()["total"] == 1
    assert contact_list.json()["items"][0]["asunto"] == "Consulta de recorrido"
    assert contact_status.status_code == 200
    assert contact_status.json()["estado"] == "contactado"


def test_customer_can_register_login_and_only_see_linked_bookings(database, monkeypatch):
    from app import routers, security

    settings = SimpleNamespace(jwt_secret="b" * 48, environment="test")
    monkeypatch.setattr(routers, "get_settings", lambda: settings)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    experience_id = ObjectId()
    database["experiencias"].documents.append(
        {"_id": experience_id, "nombre": "Caminata de naturaleza", "activa": True}
    )
    payload = {
        "nombre_completo": "Ana Visitante",
        "email": "ana@example.com",
        "telefono": "+573001234567",
        "experiencia_id": str(experience_id),
        "fecha_solicitada": (date.today() + timedelta(days=2)).isoformat(),
        "numero_participantes": 2,
        "comentarios": "",
        "aceptacion_privacidad": True,
    }
    with TestClient(app) as client:
        registration = client.post(
            "/api/clientes/auth/registro",
            json={"nombre": "Ana Visitante", "email": "ANA@example.com", "password": "correct-horse-battery"},
        )
        assert registration.status_code == 201
        assert "password_hash" not in registration.text
        assert client.get("/api/clientes/me/reservas").json() == []
        created_booking = client.post("/api/reservas", json=payload)
        customer_bookings = client.get("/api/clientes/me/reservas")
        admin_denied = client.get("/api/admin/dashboard")
        logout = client.post("/api/clientes/auth/logout")
        logged_out = client.get("/api/clientes/me/reservas")
        login = client.post(
            "/api/clientes/auth/login",
            json={"email": "ana@example.com", "password": "correct-horse-battery"},
        )
        relogged_bookings = client.get("/api/clientes/me/reservas")

    assert created_booking.status_code == 201
    assert customer_bookings.status_code == 200
    assert len(customer_bookings.json()) == 1
    assert customer_bookings.json()[0]["codigo_reserva"] == created_booking.json()["codigo_reserva"]
    assert "notas_administrativas" not in customer_bookings.text
    customer = database["clientes"].documents[0]
    assert database["reservas"].documents[0]["cliente_id"] == customer["_id"]
    assert admin_denied.status_code == 401
    assert logout.status_code == 204
    assert logged_out.status_code == 401
    assert login.status_code == 200
    assert relogged_bookings.status_code == 200
    assert len(relogged_bookings.json()) == 1


def test_customer_cannot_link_booking_using_another_email(database, monkeypatch):
    from app import routers, security

    settings = SimpleNamespace(jwt_secret="c" * 48, environment="test")
    monkeypatch.setattr(routers, "get_settings", lambda: settings)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    experience_id = ObjectId()
    database["experiencias"].documents.append(
        {"_id": experience_id, "nombre": "Caminata de naturaleza", "activa": True}
    )
    payload = {
        "nombre_completo": "Ana Visitante",
        "email": "otra@example.com",
        "telefono": "+573001234567",
        "experiencia_id": str(experience_id),
        "fecha_solicitada": (date.today() + timedelta(days=2)).isoformat(),
        "numero_participantes": 2,
        "comentarios": "",
        "aceptacion_privacidad": True,
    }
    with TestClient(app) as client:
        client.post(
            "/api/clientes/auth/registro",
            json={"nombre": "Ana Visitante", "email": "ana@example.com", "password": "correct-horse-battery"},
        )
        response = client.post("/api/reservas", json=payload)

    assert response.status_code == 403
    assert database["reservas"].documents == []
