# core/celery.py

import os
from celery import Celery
from dotenv import load_dotenv

# Load .env BEFORE anything else
load_dotenv()

# Tell Celery where your Django settings are
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Create the Celery app — 'core' is just the name
app = Celery('core')
app.conf.worker_pool = 'solo'

# Read Celery config from Django settings
# namespace='CELERY' means all celery settings in settings.py
# must start with CELERY_ prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks.py files in all installed apps
# This means Celery will find orders/tasks.py automatically
app.autodiscover_tasks()