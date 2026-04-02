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
REFRESH_TOKEN_EXPIRY_VALUE = 500 

ACCESS_TOKEN_EXPIRY_UNIT = "days"
ACCESS_TOKEN_EXPIRY_VALUE = 30

DATA_UPLOAD_MAX_NUMBER_FIELDS = None

INSTALLED_APPS = [
    "test_bulk_upload.apps.TestBulkUploadConfig",
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
    "email_sender.apps.EmailSenderConfig",
    "corsheaders",
    "utilities.apps.UtilitiesConfig",
    'clearcache',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'storages',
    'mail_box.apps.MailBoxConfig',
    'legacybot.apps.LegacybotConfig',
    'django_celery_beat',
    'celeryapp',
    'jobaid.apps.JobaidConfig',
    'company_iq.apps.CompanyIqConfig',
    'drf_spectacular',
    "drf_spectacular_sidecar",
    'analytics.apps.AnalyticsConfig',
    'client_apis.apps.ClientApisConfig',
]

MIDDLEWARE = [
    "commons.LogRequestMiddleware.LogRequestMiddleware",
    "web_auth.middlewares.UserAuthenticationMiddleware",
    "clients.middlewares.ClientIdentifierMiddleware",
    "tenants.middlewares.TenantIdentifierMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "commons.ResponseMiddleware.SlackNoRetryMiddleware",
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'client_apis.apis.middleware.APIKeyUsageLogMiddleware',
    

]

CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOWED_ORIGINS = [
    "https://platform.coachbots.com",
    "https://playground.coachbots.com",
    "https://talk.coachbots.com",
    "https://check.aadil611.live",
    "https://myplayground.coachbots.com",
    
]

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
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
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
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages'
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

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_TZ = True

# STATIC_URL = '/static/'
# STATIC_ROOT = os.path.join(BASE_DIR, 'static/')


USE_S3 = os.getenv('USE_S3') == 'TRUE'

if USE_S3:
    # aws settings
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
    AWS_DEFAULT_ACL = 'public-read'
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
    AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}
    # s3 static settings
    AWS_LOCATION = 'static'
    STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/{AWS_LOCATION}/'
    STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
else:
    STATIC_URL = '/staticfiles/'
    STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = (os.path.join(BASE_DIR, 'static'),)

MEDIA_URL = '/mediafiles/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'mediafiles')



DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    "SECURITY": [{"BearerAuth": []}],
    "COMPONENTS": {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        },
    },
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
WHATSAPP_API_BASE_URL = os.getenv("WHATSAPP_API_BASE_URL")
WHATSAPP_API_KEY = os.getenv("WHATSAPP_API_KEY")
BACKEND = os.getenv("BACKEND") if ENV != 'local' else "http://localhost:8001"


CSRF_TRUSTED_ORIGINS = ['https://coach-api-ovh.coachbots.com','https://coach-api-prod-ovh.coachbots.com','https://coach-api-gke-dev.coachbots.com','https://coach-api-gke-prod.coachbots.com']




if ENV != 'local':
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            # 'LOCATION': 'redis://localhost:6379/1',  # Update with your Redis server details
            'LOCATION': 'redis://redis:6379/1',
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            }
        }
    }


CELERY_BROKER_URL = 'redis://localhost:6379/0' if ENV == 'local' else 'redis://redis:6379/1'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0' if ENV == 'local' else 'redis://redis:6379/1'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Kolkata'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
