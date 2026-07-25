from pathlib import Path

from decouple import config, Csv


BASE_DIR = Path(__file__).resolve().parent.parent


# =========================================================
# Güvenlik
# =========================================================

SECRET_KEY = config("DJANGO_SECRET_KEY")

DEBUG = config("DJANGO_DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = [
    "glauria.dev",
    "www.glauria.dev",
    "2.28.4.211",
    "localhost",
    "127.0.0.1",
]
CSRF_TRUSTED_ORIGINS = [
    "https://glauria.dev",
    "https://www.glauria.dev",
]


# =========================================================
# Uygulamalar
# =========================================================

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
THIRD_PARTY_APPS = [
]

LOCAL_APPS = [
    "apps.core.apps.CoreConfig",
     "apps.organizations.apps.OrganizationsConfig",
     "apps.accounts.apps.AccountsConfig",
     "apps.dashboard",
     "apps.portal",
     "apps.crm",
     "apps.sales",
     "apps.purchasing",
     "apps.inventory",
     "apps.manufacturing",
     "apps.finance",
     "apps.hr",
     
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

AUTH_USER_MODEL = "accounts.User"


# =========================================================
# Middleware
# =========================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# =========================================================
# URL ve uygulama girişleri
# =========================================================

ROOT_URLCONF = "config.urls"

WSGI_APPLICATION = "config.wsgi.application"

ASGI_APPLICATION = "config.asgi.application"


# =========================================================
# Template ayarları
# =========================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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


# =========================================================
# PostgreSQL
# =========================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("POSTGRES_DB"),
        "USER": config("POSTGRES_USER"),
        "PASSWORD": config("POSTGRES_PASSWORD"),
        "HOST": config("POSTGRES_HOST", default="db"),
        "PORT": config("POSTGRES_PORT", default="5432"),
        "CONN_MAX_AGE": 60,
    }
}


# =========================================================
# Parola doğrulama
# =========================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# =========================================================
# Dil ve zaman
# =========================================================

LANGUAGE_CODE = "tr"

TIME_ZONE = "Europe/Istanbul"

USE_I18N = True

USE_TZ = True


# =========================================================
# Static ve media
# =========================================================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# =========================================================
# Redis cache
# =========================================================

REDIS_URL = config("REDIS_URL", default="redis://redis:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}


# =========================================================
# Celery
# =========================================================

CELERY_BROKER_URL = config(
    "CELERY_BROKER_URL",
    default="redis://redis:6379/0",
)

CELERY_RESULT_BACKEND = config(
    "CELERY_RESULT_BACKEND",
    default="redis://redis:6379/1",
)

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE


# =========================================================
# Django varsayılanları
# =========================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
