"""
config/celery.py
================
Celery application factory for Review-hawk.

Workers are started with:
    celery -A config worker -l info

For Windows development, add --pool=solo:
    celery -A config worker -l info --pool=solo
"""

from __future__ import annotations

import os

from celery import Celery

# Point Celery at the Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("review_hawk")

# Read broker/backend/etc. from Django settings (all keys prefixed CELERY_)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in every INSTALLED_APP's tasks.py
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Smoke-test task — run `celery -A config call config.celery.debug_task`."""
    print(f"Request: {self.request!r}")
