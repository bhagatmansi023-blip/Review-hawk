"""
reviews/views.py
================
GitHub webhook receiver for Review-hawk.

On pull_request opened/synchronize events:
1. Verify the HMAC-SHA256 signature from GitHub.
2. Persist a WebhookEvent audit record.
3. Get-or-create the PullRequest row.
4. Create a Review row (status=PENDING).
5. Dispatch the Celery task that calls Gemini and posts the review.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from decouple import config

from repos.models import PullRequest, Repository
from reviews.models import Review, WebhookEvent
from reviews.tasks import run_llm_review

logger = logging.getLogger(__name__)

# Retrieve the webhook secret from your .env file
GITHUB_WEBHOOK_SECRET = config("GITHUB_WEBHOOK_SECRET", default="")

# PR actions that should trigger an AI review
REVIEW_TRIGGER_ACTIONS = {"opened", "synchronize", "reopened"}


def verify_signature(payload_body: bytes, secret_token: str, signature_header: str | None) -> bool:
    """Verify that the payload was sent from GitHub by validating SHA256."""
    if not signature_header:
        return False

    hash_object = hmac.new(
        secret_token.encode("utf-8"), msg=payload_body, digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)


@csrf_exempt
def github_webhook(request):
    """
    POST /api/webhook/webhook/

    Receives GitHub webhook events, verifies their signature, and dispatches
    Celery tasks for pull_request events.
    """
    if request.method != "POST":
        return HttpResponse(status=405, content="Method Not Allowed")

    # ── Signature verification ─────────────────────────────────────────────
    signature_header = request.headers.get("X-Hub-Signature-256")
    if not verify_signature(request.body, GITHUB_WEBHOOK_SECRET, signature_header):
        if not GITHUB_WEBHOOK_SECRET:
            logger.error("GITHUB_WEBHOOK_SECRET is empty in .env, so every webhook will be rejected.")
        logger.warning(
            "Webhook rejected (HTTP 403): signature missing or does not match GITHUB_WEBHOOK_SECRET. "
            "The secret in .env must equal the secret in the GitHub App settings."
        )
        return HttpResponseForbidden("Invalid signature!")

    # ── Parse payload ──────────────────────────────────────────────────────
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse(status=400, content="Invalid JSON payload")

    event_type = request.headers.get("X-GitHub-Event", "")
    delivery_id = request.headers.get("X-GitHub-Delivery", "")
    action = payload.get("action", "")

    logger.info("Webhook received: event=%s action=%s delivery=%s", event_type, action, delivery_id)

    # ── Idempotency check — skip if we've already processed this delivery ──
    if delivery_id and WebhookEvent.objects.filter(delivery_id=delivery_id).exists():
        logger.info("Delivery %s already processed — skipping.", delivery_id)
        return JsonResponse({"status": "skipped", "reason": "already processed"})

    # ── Persist audit record ───────────────────────────────────────────────
    repo_data = payload.get("repository", {})
    github_repo_id = repo_data.get("id")
    db_repo = None
    if github_repo_id:
        db_repo = Repository.objects.filter(github_repo_id=github_repo_id).first()

    webhook_event = None
    if delivery_id:
        webhook_event = WebhookEvent.objects.create(
            delivery_id=delivery_id,
            event_type=event_type,
            action=action,
            repository=db_repo,
            payload=payload,
        )

    # ── Route event ────────────────────────────────────────────────────────
    if event_type == "pull_request":
        _handle_pull_request(payload, action, db_repo, webhook_event)

    elif event_type == "ping":
        logger.info("Received ping event from GitHub App installation.")

    return JsonResponse(
        {"status": "success", "message": f"Processed {event_type}.{action} event"}
    )


def _handle_pull_request(
    payload: dict,
    action: str,
    db_repo: Repository | None,
    webhook_event: WebhookEvent | None,
) -> None:
    """
    Handle pull_request webhook events.

    Creates (or updates) the PullRequest row and fires off the Celery review
    task for actionable events (opened / synchronize / reopened).
    """
    if db_repo is None:
        logger.warning(
            "pull_request.%s received for repo '%s' (id %s) which is NOT registered in the "
            "dashboard — ignoring. Connect it on the Repositories page.",
            action,
            payload.get("repository", {}).get("full_name", "?"),
            payload.get("repository", {}).get("id", "?"),
        )
        return

    pr_data = payload.get("pull_request", {})
    pr_number = pr_data.get("number")
    head_sha = pr_data.get("head", {}).get("sha", "")
    title = pr_data.get("title", "")
    author = pr_data.get("user", {}).get("login", "")
    html_url = pr_data.get("html_url", "")
    state = pr_data.get("state", "open")
    # GitHub App sends installation.id; may be absent for OAuth-only setups
    installation_id: int | None = (
        payload.get("installation", {}).get("id") or None
    )

    if not (pr_number and head_sha):
        logger.warning("pull_request payload missing number or head.sha — skipping.")
        return

    # ── Get-or-create PullRequest row ──────────────────────────────────────
    db_pr, pr_created = PullRequest.objects.get_or_create(
        repository=db_repo,
        number=pr_number,
        defaults={
            "title": title,
            "author": author,
            "state": state,
            "html_url": html_url,
            "latest_head_sha": head_sha,
        },
    )
    if not pr_created:
        # Update mutable fields on re-sync / push
        db_pr.title = title
        db_pr.state = state
        db_pr.latest_head_sha = head_sha
        db_pr.save(update_fields=["title", "state", "latest_head_sha", "updated_at"])

    # ── Only review on triggering actions ──────────────────────────────────
    if action not in REVIEW_TRIGGER_ACTIONS:
        logger.info("pull_request.%s — no review needed.", action)
        return

    # ── Idempotency: skip if a review for this exact SHA already exists ────
    if Review.objects.filter(pull_request=db_pr, head_sha=head_sha).exists():
        logger.info(
            "Review for PR #%d @ %s already exists — skipping duplicate.", pr_number, head_sha[:7]
        )
        return

    # ── Create pending Review row (guard against concurrent redeliveries) ──
    try:
        review = Review.objects.create(
            pull_request=db_pr,
            head_sha=head_sha,
            status=Review.Status.PENDING,
            installation_id=installation_id,
        )
    except IntegrityError:
        # Two webhook deliveries raced; the other one won — this is fine.
        logger.info(
            "IntegrityError creating Review for PR #%d @ %s — concurrent duplicate, skipping.",
            pr_number, head_sha[:7],
        )
        return

    logger.info(
        "Created Review(id=%d) for PR #%d @ %s — dispatching Celery task.",
        review.pk,
        pr_number,
        head_sha[:7],
    )

    # Mark webhook as processed
    if webhook_event:
        webhook_event.processed = True
        webhook_event.save(update_fields=["processed"])

    # ── Dispatch Celery task ───────────────────────────────────────────────
    # If the broker (Redis) is down, record why on the review instead of crashing the
    # webhook with a 500, so GitHub does not keep redelivering and the dashboard shows the reason.
    try:
        run_llm_review.delay(review.pk)
    except Exception as exc:  # noqa: BLE001 - broker errors vary (redis, kombu, OSError)
        logger.error("Could not queue review %d — is Redis running? %s: %s", review.pk, exc.__class__.__name__, exc)
        review.status = Review.Status.FAILED
        review.error_message = f"Could not queue the review. Is Redis running? ({exc.__class__.__name__}: {exc})"[:1000]
        review.save(update_fields=["status", "error_message"])
