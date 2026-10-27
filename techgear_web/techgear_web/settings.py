import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR.parent / ".env")

SECRET_KEY = os.getenv("DJANGO_WEB_SECRET_KEY", os.getenv("DJANGO_SECRET_KEY", ""))
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() in {"1", "true", "yes"}
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_WEB_ALLOWED_HOSTS", os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")).split(",") if host.strip()]
if DEBUG and "*" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("*")

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "django.contrib.messages",
    "storefront.apps.StorefrontConfig",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "techgear_web.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "techgear_web" / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "techgear_web.wsgi.application"
LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "techgear_web" / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
TECHGEAR_API_URL = os.getenv("TECHGEAR_API_URL", "http://127.0.0.1:8001").rstrip("/")
TECHGEAR_MONGODB_URI = os.getenv("TECHGEAR_MONGODB_URI", "") or os.getenv("MONGODB_URI", "")
TECHGEAR_MONGODB_DATABASE = os.getenv("TECHGEAR_MONGODB_DATABASE", "techgear")
TECHGEAR_DNS_NAMESERVERS = os.getenv("TECHGEAR_DNS_NAMESERVERS", "")
SESSION_ENGINE = "storefront.sessions"
SESSION_COOKIE_NAME = "techgear_session"
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
