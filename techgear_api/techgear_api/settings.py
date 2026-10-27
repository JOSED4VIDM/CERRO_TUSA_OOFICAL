import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR.parent / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() in {"1", "true", "yes"}
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if host.strip()]
if DEBUG and "*" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.extend(["*"])

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "store.apps.StoreConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "techgear_api.urls"
TEMPLATES = []
WSGI_APPLICATION = "techgear_api.wsgi.application"
ASGI_APPLICATION = "techgear_api.asgi.application"

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "techgear-api-unused.sqlite3"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"

TECHGEAR_MONGODB_URI = os.getenv("TECHGEAR_MONGODB_URI", "") or os.getenv("MONGODB_URI", "")
TECHGEAR_MONGODB_DATABASE = os.getenv("TECHGEAR_MONGODB_DATABASE", "techgear")
TECHGEAR_DNS_NAMESERVERS = os.getenv("TECHGEAR_DNS_NAMESERVERS", "")
TECHGEAR_JWT_SECRET = os.getenv("TECHGEAR_JWT_SECRET", "")
TECHGEAR_ADMIN_EMAIL = os.getenv("TECHGEAR_ADMIN_EMAIL", "").strip().lower()
TECHGEAR_ADMIN_PASSWORD = os.getenv("TECHGEAR_ADMIN_PASSWORD", "")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["store.authentication.MongoJWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle", "rest_framework.throttling.UserRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"anon": "300/day", "user": "1200/day", "login": "10/hour", "register": "10/hour"},
    "EXCEPTION_HANDLER": "store.exceptions.api_exception_handler",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer", "rest_framework.renderers.BrowsableAPIRenderer"],
}

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
