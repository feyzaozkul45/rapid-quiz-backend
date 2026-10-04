from config.secret_key import validate_secret_key

from .base import *  # noqa: F403

DEBUG = False
REST_FRAMEWORK = {**REST_FRAMEWORK, "NUM_PROXIES": env.int("NUM_PROXIES", default=1)}  # noqa: F405
# Prod'da zorunlu ve güçlü olmalı (varsayılan yok); zayıf/örnek değerde uygulama başlamaz.
SECRET_KEY = validate_secret_key(env("DJANGO_SECRET_KEY"))  # noqa: F405
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])  # noqa: F405

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

DATABASES["default"]["CONN_MAX_AGE"] = 60  # noqa: F405
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True  # noqa: F405

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
