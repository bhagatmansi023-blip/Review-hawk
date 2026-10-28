"""
conftest.py — root pytest configuration
========================================
Sets required environment variables before Django initialises, then switches
the database to in-memory SQLite so tests run without Postgres or Redis.
"""

from __future__ import annotations

import os

# ── 1. Stub every env-var that settings.py reads via environ.Env() ──────────
#    These must be set BEFORE `config.settings` is first imported.
_STUBS = {
    "DB_NAME":              "test_reviewhawk",
    "DB_USER":              "postgres",
    "DB_PASSWORD":          "postgres",
    "DB_HOST":              "localhost",
    "DB_PORT":              "5432",
    "GITHUB_CLIENT_ID":     "fake_client_id",
    "GITHUB_CLIENT_SECRET": "fake_client_secret",
    "GITHUB_WEBHOOK_SECRET":"test-secret-abc123",
    "GEMINI_API_KEY":       "fake_gemini_key",
    "GEMINI_MODEL":         "gemini-2.5-flash",
    "CELERY_BROKER_URL":    "memory://",
    "CELERY_RESULT_BACKEND":"cache+memory://",
    "FRONTEND_URL":         "http://localhost:5173",
}
for k, v in _STUBS.items():
    os.environ.setdefault(k, v)

# ── 2. After env-vars are set, configure Django (pytest-django reads
#    DJANGO_SETTINGS_MODULE from pytest.ini, but we still need settings
#    accessible for the DB override below).
import django
from django.conf import settings as _settings


def pytest_configure(config):
    """Switch DB to SQLite and make Celery eager — called before collection."""
    # Django isn't set up yet at this point; we hook into django_settings
    # via an app-ready signal in the fixture below instead.
    pass


# ── 3. Override DB + Celery once Django settings are loaded ─────────────────
#    Use the django_settings fixture pattern: a session-scoped autouse fixture.

import pytest


@pytest.fixture(autouse=True, scope="session")
def _override_settings_for_tests(django_db_setup=None):
    """
    Switch to SQLite and enable eager Celery for the entire test session.
    Must run before any DB access; scope=session means it runs once.
    """
    from django.test.utils import override_settings
    # We can't use override_settings as a context manager at session scope,
    # so we patch directly — this is safe because tests run in isolation.
    _settings.DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
    _settings.CELERY_TASK_ALWAYS_EAGER = True
    _settings.CELERY_TASK_EAGER_PROPAGATES = True
