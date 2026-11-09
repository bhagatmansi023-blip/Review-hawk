"""
reviews/views.py
================
GitHub webhook receiver for Review-hawk (POST /api/webhook/ or /api/webhook/webhook/).

Handled pull_request actions:
  opened, synchronize, reopened -> save the PR, queue a review if this head commit has none
  closed                        -> update the PR state (closed or merged)
  anything else                 -> PR fields are refreshed, no review

Every delivery is stored as a WebhookEvent with an ``outcome`` (what we did) or an ``error``
(what went wrong), so a silent failure is visible in the admin and in `manage.py check_pipeline`.
A delivery is skipped as a duplicate unless its previous attempt crashed, so GitHub's
"Redeliver" button works after a failure.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime

from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from decouple import config

from repos.models import PullRequest, Repository
from reviews.models import Review, WebhookEvent
from reviews.queueing import reset_review
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


def _parse_time(value) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@csrf_exempt
def github_webhook(request):
    """
    POST /api/webhook/
    Receives GitHub webhook events, verifies their signature, and handles pull_request events.
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

    # ── Match the connected repository ─────────────────────────────────────
    github_repo_id = (payload.get("repository") or {}).get("id")
    db_repo = Repository.objects.filter(github_repo_id=github_repo_id).first() if github_repo_id else None

    # ── Audit record + idempotency ─────────────────────────────────────────
    webhook_event = None
    if delivery_id:
        webhook_event, created = WebhookEvent.objects.get_or_create(
            delivery_id=delivery_id,
            defaults={
                "event_type": event_type, "action": action, "repository": db_repo,
                "payload": payload, "error": "", "outcome": "",
            },
        )
        # A delivery we already accepted is skipped. Only one whose previous attempt CRASHED
        # (error recorded) is processed again, so GitHub's "Redeliver" works after a failure.
        if not created and not webhook_event.error:
            logger.info("Delivery %s already processed — skipping.", delivery_id)
            return JsonResponse({"status": "skipped", "reason": "already processed"})

    # ── Route the event ────────────────────────────────────────────────────
    try:
        if event_type == "pull_request":
            outcome = _handle_pull_request(payload, action, db_repo, webhook_event)
        elif event_type == "ping":
            logger.info("Received ping event from GitHub.")
            outcome = "ping acknowledged"
        else:
            outcome = f"ignored event type '{event_type}'"
    except Exception as exc:  # noqa: BLE001 - record it, tell GitHub, allow a redelivery
        logger.exception("Webhook %s (%s.%s) failed", delivery_id, event_type, action)
        if webhook_event:
            webhook_event.error = f"{exc.__class__.__name__}: {exc}"[:2000]
            webhook_event.save(update_fields=["error"])
        return JsonResponse({"status": "error", "message": "Webhook processing failed; see server log."}, status=500)

    if webhook_event:
        webhook_event.processed = True
        webhook_event.outcome = outcome[:200]
        webhook_event.error = ""
        webhook_event.save(update_fields=["processed", "outcome", "error"])
    logger.info("Webhook %s outcome: %s", delivery_id, outcome)
    return JsonResponse({"status": "success", "message": f"Processed {event_type}.{action} event"})


def _pr_state(pr_data: dict) -> str:
    if pr_data.get("state") == "closed":
        return PullRequest.State.MERGED if pr_data.get("merged") or pr_data.get("merged_at") else PullRequest.State.CLOSED
    return PullRequest.State.OPEN


def _handle_pull_request(
    payload: dict,
    action: str,
    db_repo: Repository | None,
    webhook_event: WebhookEvent | None,
) -> str:
    """
    Save the pull request and, for opened / synchronize / reopened, queue a review
    unless this exact head commit has already been reviewed. Returns a short outcome string.
    """
    repo_info = payload.get("repository") or {}
    if db_repo is None:
        logger.warning(
            "pull_request.%s received for repo '%s' (id %s) which is NOT registered in the "
            "dashboard — ignoring. Connect it on the Repositories page.",
            action, repo_info.get("full_name", "?"), repo_info.get("id", "?"),
        )
        return f"ignored: {repo_info.get('full_name', 'repository')} is not connected in the dashboard"

    pr_data = payload.get("pull_request") or {}
    pr_number = pr_data.get("number")
    head = pr_data.get("head") or {}
    head_sha = head.get("sha", "")
    if not (pr_number and head_sha):
        logger.warning("pull_request payload missing number or head.sha — skipping.")
        return "ignored: payload has no PR number or head commit"

    # GitHub App deliveries carry installation.id; absent for plain repo webhooks
    installation_id: int | None = (payload.get("installation") or {}).get("id") or None
    state = _pr_state(pr_data)

    # ── Create or update the PullRequest row (all fields we show) ──────────
    db_pr, _created = PullRequest.objects.update_or_create(
        repository=db_repo,
        number=pr_number,
        defaults={
            "title": (pr_data.get("title") or "")[:500],
            "body": pr_data.get("body") or "",
            "author": ((pr_data.get("user") or {}).get("login") or "")[:100],
            "state": state,
            "html_url": pr_data.get("html_url") or "",
            "latest_head_sha": head_sha,
            "source_branch": (head.get("ref") or "")[:200],
            "target_branch": ((pr_data.get("base") or {}).get("ref") or "")[:200],
            "is_draft": bool(pr_data.get("draft")),
            "github_pr_id": pr_data.get("id") if isinstance(pr_data.get("id"), int) else None,
            "installation_id": installation_id,
            "github_created_at": _parse_time(pr_data.get("created_at")),
            "github_updated_at": _parse_time(pr_data.get("updated_at")),
            "closed_at": _parse_time(pr_data.get("closed_at")),
            "merged_at": _parse_time(pr_data.get("merged_at")),
        },
    )
    if installation_id and db_repo.installation_id != installation_id:
        Repository.objects.filter(pk=db_repo.pk).update(installation_id=installation_id)

    if action == "closed":
        return f"PR #{pr_number} marked {state}"
    if action not in REVIEW_TRIGGER_ACTIONS:
        logger.info("pull_request.%s — no review needed.", action)
        return f"PR #{pr_number} updated; no review needed for '{action}'"
    if not db_repo.is_enabled:
        return f"PR #{pr_number} saved; repository is disabled, so no review was queued"

    # ── Idempotency: one review per head commit ────────────────────────────
    existing = Review.objects.filter(pull_request=db_pr, head_sha=head_sha).first()
    if existing is not None:
        if existing.status == Review.Status.FAILED and action == "reopened":
            reset_review(existing)  # a reopen is a good moment to retry a failed review
            review = existing
        else:
            logger.info("Review for PR #%d @ %s already exists — skipping duplicate.", pr_number, head_sha[:7])
            return f"review for {head_sha[:7]} already exists ({existing.status})"
    else:
        try:
            review = Review.objects.create(
                pull_request=db_pr,
                head_sha=head_sha,
                status=Review.Status.PENDING,
                installation_id=installation_id,
            )
        except IntegrityError:
            # Two webhook deliveries raced; the other one won — this is fine.
            logger.info("IntegrityError creating Review for PR #%d @ %s — concurrent duplicate, skipping.", pr_number, head_sha[:7])
            return f"review for {head_sha[:7]} created by a concurrent delivery"

    logger.info("Review(id=%d) for PR #%d @ %s — dispatching Celery task.", review.pk, pr_number, head_sha[:7])

    # ── Dispatch Celery task ───────────────────────────────────────────────
    # If the broker (Redis) is down, record why on the review instead of crashing the
    # webhook with a 500, so the dashboard shows the reason.
    try:
        run_llm_review.delay(review.pk)
    except Exception as exc:  # noqa: BLE001 - broker errors vary (redis, kombu, OSError)
        logger.error("Could not queue review %d — is Redis running? %s: %s", review.pk, exc.__class__.__name__, exc)
        review.status = Review.Status.FAILED
        review.error_message = f"Could not queue the review. Is Redis running? ({exc.__class__.__name__}: {exc})"[:1000]
        review.save(update_fields=["status", "error_message"])
        return f"review {review.pk} could not be queued: Redis unreachable"
    return f"review {review.pk} queued for {head_sha[:7]}"
