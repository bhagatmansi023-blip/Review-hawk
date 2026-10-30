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

from django.conf import settings as _settings

_settings.CELERY_TASK_ALWAYS_EAGER = True
_settings.CELERY_TASK_EAGER_PROPAGATES = True

import pytest


@pytest.fixture(autouse=True, scope="session")
def _override_settings_for_tests():
    """Ensure eager Celery throughout the test session."""
    _settings.CELERY_TASK_ALWAYS_EAGER = True
    _settings.CELERY_TASK_EAGER_PROPAGATES = True
