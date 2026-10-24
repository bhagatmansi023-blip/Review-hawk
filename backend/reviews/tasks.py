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
    default_retry_delay=60,   # seconds between retries
    acks_late=True,           # only ack after the task finishes (safer)
    reject_on_worker_lost=True,
)
def run_llm_review(self, review_id: int) -> None:
    """
    Celery task: run a full Gemini AI review for the given Review row.

    Parameters
    ----------
    review_id:
        Primary key of a ``reviews.Review`` DB row that has been created
        (status=PENDING) and is ready for processing.

    Retry behaviour
    ---------------
    On any unexpected exception the task is retried up to 3 times with a
    60-second delay.  Permanent failures (e.g. invalid JSON from Gemini)
    are caught inside ``run_review`` and written to ``Review.error_message``;
    those do NOT trigger a Celery retry.
    """
    from reviews.llm_reviewer import run_review

    logger.info("Celery task started: run_llm_review(review_id=%d)", review_id)
    try:
        run_review(review_id)
    except Exception as exc:
        logger.exception(
            "Unhandled exception in run_llm_review(review_id=%d): %s", review_id, exc
        )
        raise self.retry(exc=exc)
