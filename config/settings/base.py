"""
Base settings for Air Quality API project.
"""
import os
from pathlib import Path
import environ

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Initialize environment variables
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CACHE_TTL_SECONDS=(int, 600),
    LOCATION_CACHE_TTL_SECONDS=(int, 86400),
    RATE_LIMIT_PER_MINUTE=(int, 100),
)

# Read .env file if it exists
env_file = BASE_DIR / '.env'
if env_file.exists():
    environ.Env.read_env(str(env_file))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY', default='django-insecure-change-this-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG')

ALLOWED_HOSTS = env('ALLOWED_HOSTS')


# Application definition

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'corsheaders',
    'django_ratelimit',
]

LOCAL_APPS = [
    'apps.core',
    'apps.location',
    'apps.adapters',
    'apps.fusion',
    'apps.forecast',
    'apps.api',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': env.db('DATABASE_URL', default='sqlite:///db.sqlite3')
}


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Django REST Framework
# https://www.django-rest-framework.org/api-guide/settings/

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': f'{env("RATE_LIMIT_PER_MINUTE")}/minute',
    },
    'EXCEPTION_HANDLER': 'apps.api.exceptions.custom_exception_handler',
}


# CORS Settings
# https://github.com/adamchainz/django-cors-headers

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

CORS_ALLOW_METHODS = [
    'GET',
    'POST',
    'OPTIONS',
]


# Cache Configuration
# https://docs.djangoproject.com/en/5.0/topics/cache/

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://127.0.0.1:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'airquality',
        'TIMEOUT': env('CACHE_TTL_SECONDS'),
    }
}


# API Keys Configuration

API_KEYS = {
    'AIRNOW': env('AIRNOW_API_KEY', default=''),
    'PURPLEAIR': env('PURPLEAIR_API_KEY', default=''),
    'OPENWEATHERMAP': env('OPENWEATHERMAP_API_KEY', default=''),
    'WAQI': env('WAQI_API_KEY', default=''),
    'AIRVISUAL': env('AIRVISUAL_API_KEY', default=''),
    'BREEZOMETER': env('BREEZOMETER_API_KEY', default=''),
    'GOOGLE_GEOCODING': env('GOOGLE_GEOCODING_API_KEY', default=''),
}


# Air Quality API Settings

AIR_QUALITY_SETTINGS = {
    # Cache TTLs
    'RESPONSE_CACHE_TTL': env('CACHE_TTL_SECONDS'),  # 10 minutes
    'LOCATION_CACHE_TTL': env('LOCATION_CACHE_TTL_SECONDS'),  # 24 hours
    
    # Search Parameters
    'DEFAULT_SEARCH_RADIUS_KM': 25,
    'MAX_SEARCH_RADIUS_KM': 100,
    
    # Data Freshness
    'MAX_DATA_AGE_HOURS': 3,
    'PREFERRED_DATA_AGE_MINUTES': 30,
    
    # Fusion Weights
    'SOURCE_WEIGHTS': {
        'EPA_AIRNOW': 1.0,
        'ECCC_AQHI': 1.0,
        'PURPLEAIR': 0.85,
        'OPENWEATHERMAP': 0.7,
        'BREEZOMETER': 0.8,
        'AIRVISUAL': 0.75,
        'WAQI': 0.65,
    },
    
    # Source Priority by Region
    'SOURCE_PRIORITY': {
        'US': ['EPA_AIRNOW', 'PURPLEAIR', 'OPENWEATHERMAP', 'AIRVISUAL', 'WAQI'],
        'CA': ['ECCC_AQHI', 'PURPLEAIR', 'OPENWEATHERMAP', 'AIRVISUAL', 'WAQI'],
        'DEFAULT': ['OPENWEATHERMAP', 'AIRVISUAL', 'WAQI', 'PURPLEAIR'],
    },
    
    # PurpleAir Settings
    'PURPLEAIR_EPA_CORRECTION': True,
    'PURPLEAIR_MIN_CONFIDENCE': 80,
    
    # Retry Settings
    'MAX_RETRIES': 3,
    'RETRY_BACKOFF_FACTOR': 2,
    'REQUEST_TIMEOUT': 10,
}


# Logging Configuration

# Create logs directory if it doesn't exist (for local development)
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
