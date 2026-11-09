"""
reviews/queueing.py
===================
Helpers for putting reviews on the Celery queue safely.
"""
from __future__ import annotations

import logging

from django.conf import settings

from .models import Review
from .tasks import run_llm_review

logger = logging.getLogger(__name__)


def queue_review(review: Review) -> str | None:
    """
    Hand a review to Celery. Returns an error message if the broker is unreachable
    (usually Redis/Memurai not running); the review is then marked failed so the UI
    shows why, instead of staying 'pending' forever.
    """
    try:
        run_llm_review.delay(review.pk)
        return None
    except Exception as exc:  # noqa: BLE001 - broker errors vary (redis, kombu, OSError)
        message = f"Could not queue the review. Is Redis running? ({exc.__class__.__name__}: {exc})"
        logger.error("Queueing review %d failed: %s", review.pk, message)
        review.status = Review.Status.FAILED
        review.error_message = message[:1000]
        review.save(update_fields=["status", "error_message"])
        return message


def reset_review(review: Review) -> None:
    """Return a finished/failed review to a clean 'pending' state so it can run again."""
    review.comments.all().delete()
    review.status = Review.Status.PENDING
    review.summary = ""
    review.error_message = ""
    review.github_post_error = ""
    review.analysis_warnings = []
    review.llm_model = ""
    review.input_tokens = review.output_tokens = review.files_reviewed = 0
    review.github_review_id = None
    review.posted_at = review.started_at = review.finished_at = None
    review.health_score = None
    review.health_grade = ""
    review.health_report = {}
    review.save()


def celery_status() -> dict:
    """
    Is anything going to execute queued reviews? Cheap (about 1s worst case); call once per sync.
    Returns {"eager", "broker_ok", "workers", "warning"}.
    """
    if settings.CELERY_TASK_ALWAYS_EAGER:
        return {
            "eager": True, "broker_ok": None, "workers": None,
            "warning": "Celery is in eager mode, so reviews run inside the web request. "
                       "Set CELERY_TASK_ALWAYS_EAGER=False in .env and start a worker.",
        }
    try:
        from config.celery import app
        replies = app.control.inspect(timeout=1.0).ping() or {}
    except Exception as exc:  # noqa: BLE001
        return {
            "eager": False, "broker_ok": False, "workers": 0,
            "warning": f"Cannot reach the Celery broker ({exc.__class__.__name__}). Start Redis/Memurai.",
        }
    workers = len(replies)
    return {
        "eager": False, "broker_ok": True, "workers": workers,
        "warning": "" if workers else
        "No Celery worker is running, so queued reviews will stay pending. "
        "Start one: celery -A config worker -l info -P solo",
    }
