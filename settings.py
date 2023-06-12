import os
from pathlib import Path

from dotenv import load_dotenv
from pythonjsonlogger.jsonlogger import JsonFormatter

from commons.log_filters import TraceIdFilter

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")

DEBUG = "t" in os.getenv("DJANGO_DEBUG")

ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS").split(",")

ENV = os.getenv("ENV")

REFRESH_TOKEN_EXPIRY_UNIT = "days"
REFRESH_TOKEN_EXPIRY_VALUE = 30

ACCESS_TOKEN_EXPIRY_UNIT = "days"
ACCESS_TOKEN_EXPIRY_VALUE = 1

INSTALLED_APPS = [
    "tenants.apps.TenantsConfig",
    "clients.apps.ClientsConfig",
    "users.apps.UsersConfig",
    "identities.apps.IdentitiesConfig",
    "tests.apps.TestsConfig",
    "documents.apps.DocumentsConfig",
    "coaching_conversations.apps.CoachingConversationsConfig",
    "skills.apps.SkillsConfig",
    "web_auth.apps.WebAuthConfig",
    "url_shortener.apps.UrlShortenerConfig",
    "corsheaders",
]

MIDDLEWARE = [
    "commons.LogRequestMiddleware.LogRequestMiddleware",
    "web_auth.middlewares.UserAuthenticationMiddleware",
    "clients.middlewares.ClientIdentifierMiddleware",
    "tenants.middlewares.TenantIdentifierMiddleware",
    "corsheaders.middleware.CorsMiddleware",
]

CORS_ORIGIN_ALLOW_ALL = True

ROOT_URLCONF = 'urls'

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("MYSQL_DBNAME"),
        "USER": os.getenv("MYSQL_USER"),
        "PASSWORD": os.getenv("MYSQL_PASSWORD"),
        # Or an IP Address that your DB is hosted on
        "HOST": os.getenv("MYSQL_HOST"),
        "PORT": os.getenv("MYSQL_PORT"),
    }
}

TEMPLATES_DIR = BASE_DIR.joinpath("templates")

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [TEMPLATES_DIR],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
            ],
        },
    },
]

WSGI_APPLICATION = 'wsgi.application'

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_AUTHENTICATION_CLASSES': [],
}

# AUTH_USER_MODEL = "users.User"

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'trace_id': {
            '()': TraceIdFilter,
        }
    },
    "formatters": {
        "json": {
            "format": '%(asctime) [%(levelname)] %(processName) %(threadName) %(trace_id) %(lineno) %(name): %(message)',
            "()": JsonFormatter
        }
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'filters': ["trace_id"],
            "formatter": "json",
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO'
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'propagate': False,
            'level': 'INFO'
        },
    },
}

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
COACH_WHISPER_BASE_URL = os.getenv("COACH_WHISPER_BASE_URL")
SLACK_MESSAGE_WEBHOOK_URL = os.getenv('SLACK_MESSAGE_WEBHOOK_URL')
ANTHROPIC_KEY = os.getenv('ANTHROPIC_KEY')
COACH_METRIC_BASE_URL = os.getenv("COACH_METRIC_BASE_URL")
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL")
URL_SHORTENING_API_KEY = os.getenv("URL_SHORTENING_API_KEY")
