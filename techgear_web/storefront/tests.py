from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.test import Client, SimpleTestCase, override_settings
from storefront.sessions import SessionStore


def set_mongo_session(client, session_data):
    session_key = "test-session-key"
    session = SessionStore(session_key)
    document = {
        "_id": session_key,
        "session_data": session.encode(session_data),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    client.cookies["techgear_session"] = session_key
    return document


class StorefrontTests(SimpleTestCase):
    @patch("storefront.views.api_request")
    @override_settings(SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies")
    def test_catalog_renders_products_from_api(self, api_request):
        api_request.side_effect = [
            [{
                "id": "507f1f77bcf86cd799439011",
                "name": "Mouse",
                "slug": "mouse",
                "description": "Mouse inalámbrico",
                "price": 50000,
                "stock": 4,
                "category_id": "507f1f77bcf86cd799439012",
                "image_url": "",
            }],
            [],
        ]
        response = Client().get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mouse")
        self.assertContains(response, "$50000")

    @patch("storefront.views.api_request")
    @override_settings(SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies")
    def test_login_saves_api_token_in_server_session(self, api_request):
        api_request.return_value = {
            "token": "test-token",
            "user": {"id": "user-1", "name": "Tech User", "email": "user@example.com", "role": "customer"},
        }
        client = Client()
        response = client.post(
            "/cuenta/",
            {"action": "login", "email": "user@example.com", "password": "long-password"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.session["techgear_token"], "test-token")


class MongoSessionStoreTests(SimpleTestCase):
    @patch("storefront.sessions._session_collection")
    def test_create_persists_session_data_in_mongodb(self, collection):
        collection.return_value.find_one.return_value = None
        session = SessionStore()
        session["techgear_token"] = "server-side-token"

        session.create()

        saved = collection.return_value.insert_one.call_args.args[0]
        self.assertEqual(saved["_id"], session.session_key)
        self.assertNotEqual(saved["session_data"], "server-side-token")
        self.assertIn("expires_at", saved)


class StoreAdminViewTests(SimpleTestCase):
    @patch("storefront.views.api_request")
    def test_admin_can_load_management_dashboard(self, api_request):
        api_request.side_effect = [
            [{"id": "category-1", "name": "Audio", "slug": "audio", "active": True}],
            [],
            [],
        ]
        client = Client()
        document = set_mongo_session(client, {
            "techgear_token": "admin-token",
            "techgear_user": {"role": "admin"},
        })
        with patch("storefront.sessions._session_collection") as collection:
            collection.return_value.find_one.return_value = document

            response = client.get("/gestion/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Administrar TechGear")

    def test_customer_is_redirected_away_from_admin_dashboard(self):
        client = Client()
        document = set_mongo_session(client, {"techgear_user": {"role": "customer"}})

        with patch("storefront.sessions._session_collection") as collection:
            collection.return_value.find_one.return_value = document
            response = client.get("/gestion/")

        self.assertRedirects(response, "/cuenta/", fetch_redirect_response=False)
