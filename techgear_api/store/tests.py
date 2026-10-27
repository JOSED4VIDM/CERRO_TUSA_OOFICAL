from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient

from store.serializers import ProductSerializer, RegisterSerializer


class RegisterSerializerTests(SimpleTestCase):
    def test_registration_requires_a_long_password(self):
        serializer = RegisterSerializer(data={
            "name": "Tech User",
            "email": "user@example.com",
            "password": "short",
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors)

    def test_registration_cannot_assign_admin_role(self):
        serializer = RegisterSerializer(data={
            "name": "Tech User",
            "email": "user@example.com",
            "password": "a-long-password",
            "role": "admin",
        })
        self.assertTrue(serializer.is_valid())
        self.assertNotIn("role", serializer.validated_data)


class ProductSerializerTests(SimpleTestCase):
    def test_product_image_requires_https(self):
        serializer = ProductSerializer(data={
            "name": "Mouse Tech",
            "slug": "mouse-tech",
            "price": 1000,
            "stock": 2,
            "category_id": "507f1f77bcf86cd799439011",
            "image_url": "http://example.com/image.jpg",
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn("image_url", serializer.errors)


class HealthEndpointTests(SimpleTestCase):
    @override_settings(TECHGEAR_MONGODB_URI="")
    def test_health_reports_missing_atlas_configuration(self):
        response = APIClient().get("/api/health/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "error")


class RegisterEndpointTests(SimpleTestCase):
    def test_invalid_registration_is_rejected_without_database_access(self):
        response = APIClient().post(
            "/api/auth/register/",
            {"name": "A", "email": "not-an-email", "password": "short"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
