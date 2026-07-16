import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "meridian.settings.dev")

app = Celery("meridian")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()