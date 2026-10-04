from pathlib import Path

import environ
from corsheaders.defaults import default_headers

from config.admin_url import normalize_admin_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

# Django Admin adresi. Varsayılan `admin/`; production'da tahmin edilmesi zor bir değer verin.
ADMIN_URL = normalize_admin_url(env("ADMIN_URL", default="admin/"))

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = False
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "apps.quiz",
    "apps.quiz_sessions",
    "apps.leaderboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Yerelde DATABASE_URL verilmezse SQLite kullanılır (Docker/PostgreSQL yoksa testler için).
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Throttle sayaçları tüm gunicorn worker'ları arasında paylaşılsın diye veritabanı cache'i.
# Tablo `migrate` ile oluşmaz: `python manage.py createcachetable` gerekir.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "rapidquiz_cache",
        # Varsayılan MAX_ENTRIES=300'dür: aşılınca kayıtların üçte biri rastgele silinir ve throttle
        # sayaçları sıfırlanır. Çok farklı IP/oturum anahtarı olsa bile sayaçlar korunsun.
        "OPTIONS": {"MAX_ENTRIES": 100_000},
    },
}

LANGUAGE_CODE = "tr"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_HEADERS = (*default_headers, "x-client-type", "x-client-version")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "config.api_errors.exception_handler",
    # IP başına sınırlar; okul/operatör NAT'ı arkasındakiler için gevşek tutuldu.
    "DEFAULT_THROTTLE_RATES": {
        "quiz_start": "10/min",
        "player_name": "10/min",
        "answer": "120/min",
        # Soru isteği: IP başına geniş sınır (rastgele oturum ID'siyle sayaç şişirmeyi sınırlar).
        "question": "240/min",
        # Oturum başına sınırlar (config/throttles.py): bir oturumda en fazla 20 soru/cevap vardır.
        "answer_session": "40/min",
        "question_session": "60/min",
        # Salt okunur uç noktalar (kategoriler, sonuç, skor tablosu): IP başına geniş sınır.
        "read": "300/min",
    },
    # Yük dengeleyici arkasında gerçek istemci IP'si için X-Forwarded-For'daki güvenilir hop sayısı.
    "NUM_PROXIES": env.int("NUM_PROXIES", default=0),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Rapid Quiz API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
