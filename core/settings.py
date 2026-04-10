# config/settings.py

import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

# ─── Load your .env file ───────────────────────────────────────────────────────
# This reads your .env file so os.getenv() can find your secrets
load_dotenv()

# ─── Base directory ────────────────────────────────────────────────────────────
# This is just the path to your project folder — Django uses it internally
BASE_DIR = Path(__file__).resolve().parent.parent


# ─── Security ──────────────────────────────────────────────────────────────────
# Reads SECRET_KEY from .env — never hardcode this
SECRET_KEY = os.getenv('SECRET_KEY')

# True in development, MUST be False in production
DEBUG = os.getenv('DEBUG', 'False') == 'True'

# Which hostnames are allowed to access this server
# '*' means anyone — fine for development only
ALLOWED_HOSTS = ['*']


# ─── Installed Apps ────────────────────────────────────────────────────────────
# Django won't know about your app or DRF unless you list them here
INSTALLED_APPS = [
    'django.contrib.admin',        # The /admin/ panel
    'django.contrib.auth',         # User login system
    'django.contrib.contenttypes', # Django internal
    'django.contrib.sessions',     # Session handling
    'django.contrib.messages',     # Flash messages
    'django.contrib.staticfiles',  # CSS/JS files
    'rest_framework',  
    'django_celery_results',       # Django REST Framework — for building APIs
    'orders',                      # YOUR app
]


# ─── Middleware ─────────────────────────────────────────────────────────────────
# These run on every request/response — don't change this for now
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ─── URL Configuration ─────────────────────────────────────────────────────────
# Tells Django where to find your URL routes
ROOT_URLCONF = 'core.urls'


# ─── Templates ─────────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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


# ─── Database ──────────────────────────────────────────────────────────────────
# dj_database_url reads the DATABASE_URL from .env and converts it
# into the dictionary format Django expects
DATABASES = {
    'default': dj_database_url.parse(
        os.getenv('DATABASE_URL'),
        conn_max_age=600,        # Keep DB connections alive for 10 minutes
        ssl_require=True,        # Supabase requires SSL
    )
}


# ─── Password Validators ────────────────────────────────────────────────────────
# Rules for user passwords (used by Django admin)
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ─── Internationalisation ───────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# ─── Static Files ───────────────────────────────────────────────────────────────
STATIC_URL = 'static/'


# ─── Default Primary Key ────────────────────────────────────────────────────────
# We're using UUID in our model so this won't matter much,
# but Django requires this setting
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ─── Django REST Framework ─────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    # DRF handles its own authentication — disable Django's CSRF for API views
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
}

# ─── Celery Configuration ──────────────────────────────────────────────────────

# Where Celery sends tasks (your Redis server)
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL')

# Store task results in PostgreSQL (same Supabase DB)
CELERY_RESULT_BACKEND = 'django-db'

# Task will be acknowledged AFTER it completes (not when received)
# WHY: If worker crashes mid-task, the task goes back to queue
# This is how we handle "worker crashes mid-processing" (Phase 7)
CELERY_ACKS_LATE = True

# Only take 1 task at a time per worker
# WHY: Prevents a worker from grabbing tasks it can't finish if it crashes
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Always pass arguments as JSON (not Python pickle — safer)
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']

# Timezone
CELERY_TIMEZONE = 'UTC'

# Also add 'django_celery_results' to INSTALLED_APPS

# Disable CSRF for DRF API endpoints
CSRF_TRUSTED_ORIGINS = ['http://127.0.0.1:8000', 'http://localhost:8000']

# Razorpay
RAZORPAY_KEY_ID     = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')


# ─── Structured Logging ────────────────────────────────────────────────────────

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,

    'formatters': {
        # JSON formatter — every log line is valid JSON
        # This is what production systems use
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
        },
        # Human-readable formatter for development
        # Easier to read in your terminal
        'verbose': {
            'format': '[%(asctime)s] %(levelname)s [%(name)s] %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },

    'handlers': {
        # Prints to terminal — uses human-readable format
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },

        # Writes JSON logs to a file
        # This file can be shipped to Datadog, CloudWatch, etc.
        'json_file': {
            'class': 'logging.FileHandler',
            'filename': 'logs/orders.log',
            'formatter': 'json',
        },
    },

    'loggers': {
        # Your orders app — log everything DEBUG and above
        'orders': {
            'handlers': ['console', 'json_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        # Django itself — only WARNING and above
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}