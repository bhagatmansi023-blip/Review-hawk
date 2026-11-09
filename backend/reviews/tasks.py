"""
reviews/tasks.py
================
Celery tasks for Review-hawk's AI review pipeline.
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="reviews.run_llm_review",
    max_retries=3,
    default_retry_delay=60,   # base seconds; Celery applies exponential backoff via countdown
    acks_late=True,           # only ack after the task finishes (safer)
    reject_on_worker_lost=True,
)
def run_llm_review(self, review_id: int) -> None:
    """
    Celery task: run a full Gemini AI review for the given Review row.

    Retry behaviour
    ---------------
    ``run_review`` re-raises transient errors (timeouts, rate-limits, 5xx) so
    this task can retry them with exponential backoff (max 3 attempts).
    Permanent failures (bad JSON, 404, auth errors) are caught inside
    ``run_review``, written to ``Review.error_message``, and NOT re-raised —
    so Celery does NOT retry them.

    Double-post guard
    -----------------
    ``run_review`` checks ``review.status == COMPLETED`` at the top and returns
    immediately, so even if Celery re-delivers the task the review is only
    posted once.
    """
    from django.utils import timezone

    from reviews.llm_reviewer import run_review, _is_transient
    from reviews.models import Review

    def _set(status, message):
        Review.objects.filter(pk=review_id).exclude(status=Review.Status.COMPLETED).update(
            status=status, error_message=message[:2000],
            finished_at=timezone.now() if status == Review.Status.FAILED else None,
        )

    logger.info("Celery task started: run_llm_review(review_id=%d)", review_id)
    try:
        run_review(review_id)
    except Exception as exc:
        if _is_transient(exc):
            if self.request.retries >= self.max_retries:
                # Out of retries: record the real error instead of leaving the review "running" forever.
                _set(Review.Status.FAILED, f"Gave up after {self.max_retries + 1} attempts. {exc.__class__.__name__}: {exc}")
                logger.error("Review %d failed after %d attempts: %s", review_id, self.max_retries + 1, exc)
                return
            delay = self.default_retry_delay * (2 ** self.request.retries)
            _set(Review.Status.PENDING, f"Temporary error ({exc.__class__.__name__}: {exc}). Retrying in {delay}s.")
            logger.warning(
                "Transient error in review %d (attempt %d/%d), retrying in %ds: %s",
                review_id,
                self.request.retries + 1,
                self.max_retries,
                delay,
                exc,
            )
            raise self.retry(exc=exc, countdown=delay)
        # Permanent — run_review already saved error_message; log and stop.
        logger.error(
            "Permanent failure in run_llm_review(review_id=%d): %s", review_id, exc
        )
