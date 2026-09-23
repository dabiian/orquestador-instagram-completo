"""configuraciones django"""
from datetime import timedelta
from pathlib import Path
import os
import environ

# Initialize environment variables
env = environ.Env()
BASE_DIR = Path(__file__).resolve().parent.parent
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = env.str(
    "SECRET_KEY",
    default="django-insecure-vp79+2sd0g6+(x!vyu51^b_sju(&+5g=myb+yekk)-i)x0(=ir",
)
DEBUG = env.bool("DEBUG", default=False)
if not DEBUG and SECRET_KEY.startswith("django-insecure-"):
    raise RuntimeError("SECRET_KEY must be configured for production.")

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "rest_framework", "openai", "rest_framework_simplejwt", "drf_yasg", "corsheaders",
    "channels", "dashboard", "login_app", "openia", "reny", "schedule_tasks",
]

ASGI_APPLICATION = "back_redes_sociales.asgi.application"
REDIS_URL = env.str("REDIS_URL", default="")
if REDIS_URL:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [REDIS_URL]}}}
else:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware", "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "back_redes_sociales.urls"
CORS_ALLOW_CREDENTIALS = True
CORS_EXPOSE_HEADERS = ["Link", "X-Result-Count"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug", "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages",
    ]},
}]
DATABASES = {"default": env.db()}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = "/app/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"standard": {"format": "{levelname} {asctime} {name} {message}", "style": "{"}},
    "handlers": {"dashboard_console": {"class": "logging.StreamHandler", "formatter": "standard"}},
    "loggers": {
        "dashboard.views_v2": {"handlers": ["dashboard_console"], "level": "INFO", "propagate": False},
        "dashboard.consumers": {"handlers": ["dashboard_console"], "level": "INFO", "propagate": False},
        "dashboard.orchestrator": {"handlers": ["dashboard_console"], "level": "INFO", "propagate": False},
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=50),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "VERIFYING_KEY": None,
    "AUDIENCE": None,
    "ISSUER": None,
    "JWK_URL": None,
    "LEEWAY": 0,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.tokens.TokenUser",
    "JTI_CLAIM": "jti",
    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=5),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
}

CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=DEBUG)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"] if DEBUG else [])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# RPA Orchestrator - Instagram adapter
ORCHESTRATOR_ADAPTER_ENABLED = env.bool("ORCHESTRATOR_ADAPTER_ENABLED", default=False)
ORCHESTRATOR_URL = env.str("ORCHESTRATOR_URL", default="http://10.0.0.92:8005")
ORCHESTRATOR_WS_URL = env.str("ORCHESTRATOR_WS_URL", default="ws://10.0.0.92:8005/api/v1/bots/ws")
ORCHESTRATOR_BOT_KEY = env.str("ORCHESTRATOR_BOT_KEY", default="instagram-backend-01")
ORCHESTRATOR_BOT_TOKEN = env.str("ORCHESTRATOR_BOT_TOKEN", default="")
ORCHESTRATOR_BOT_NAME = env.str("ORCHESTRATOR_BOT_NAME", default="Instagram Backend")
ORCHESTRATOR_BOT_VERSION = env.str("ORCHESTRATOR_BOT_VERSION", default="instagram-backend-adapter-v1")
ORCHESTRATOR_MAX_CONCURRENCY = env.int("ORCHESTRATOR_MAX_CONCURRENCY", default=1)
ORCHESTRATOR_HEARTBEAT_SECONDS = env.int("ORCHESTRATOR_HEARTBEAT_SECONDS", default=15)
ORCHESTRATOR_TASK_POLL_SECONDS = env.int("ORCHESTRATOR_TASK_POLL_SECONDS", default=5)
ORCHESTRATOR_HTTP_TIMEOUT_SECONDS = env.float("ORCHESTRATOR_HTTP_TIMEOUT_SECONDS", default=20.0)

# Orchestrator -> Django catalog authentication.
# New canonical name. The old ORCHESTRATOR_API_TOKEN remains as a temporary
# fallback so existing deployments do not break during migration.
INSTAGRAM_ORCHESTRATOR_TOKEN = env.str(
    "INSTAGRAM_ORCHESTRATOR_TOKEN",
    default=env.str("ORCHESTRATOR_API_TOKEN", default=""),
)

ORCHESTRATOR_DEFAULT_BOT_EXECUTOR = env.str("ORCHESTRATOR_DEFAULT_BOT_EXECUTOR", default="")
# Separate credential for Instagram workers claiming TaskBot jobs.
INSTAGRAM_TASK_CLAIM_TOKEN = env.str("INSTAGRAM_TASK_CLAIM_TOKEN", default="")
