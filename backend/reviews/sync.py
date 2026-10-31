"""
reviews/sync.py
===============
Helpers that run when a repo is connected:

* ``ensure_repo_webhook``       – create the GitHub webhook that delivers
                                  pull_request events to this backend.
* ``sync_open_pull_requests``   – import PRs that are ALREADY open (webhooks only
                                  fire for future events) and queue reviews.
* ``remove_repo_webhook``       – clean up on unregister.

Every function swallows GitHub errors and returns a human-readable message so a
GitHub hiccup never breaks the "connect repository" request.
"""
from __future__ import annotations

import logging

from decouple import config
from github import GithubException

from repos.models import PullRequest, Repository
from reviews.models import Review
from reviews.tasks import run_llm_review

logger = logging.getLogger(__name__)

WEBHOOK_URL = config("WEBHOOK_URL", default="")
GITHUB_WEBHOOK_SECRET = config("GITHUB_WEBHOOK_SECRET", default="")
MAX_BACKFILL_PRS = config("MAX_BACKFILL_PRS", default=5, cast=int)


def ensure_repo_webhook(gh_repo, db_repo: Repository) -> str:
    """Create (or reuse) a repo webhook pointing at WEBHOOK_URL. Returns a status message."""
    if not WEBHOOK_URL or "your-public-domain" in WEBHOOK_URL:
        return "WEBHOOK_URL is not set in .env - GitHub cannot reach this backend, so no PR events will arrive."

    try:
        # Reuse an existing hook for the same URL (re-connecting a repo).
        for hook in gh_repo.get_hooks():
            if hook.config.get("url") == WEBHOOK_URL:
                db_repo.webhook_id = hook.id
                db_repo.save(update_fields=["webhook_id", "updated_at"])
                return "Webhook already present."

        hook = gh_repo.create_hook(
            name="web",
            config={
                "url": WEBHOOK_URL,
                "content_type": "json",
                "secret": GITHUB_WEBHOOK_SECRET,
                "insecure_ssl": "0",
            },
            events=["pull_request"],
            active=True,
        )
        db_repo.webhook_id = hook.id
        db_repo.save(update_fields=["webhook_id", "updated_at"])
        return "Webhook created."
    except GithubException as exc:
        msg = (exc.data or {}).get("message", str(exc)) if isinstance(exc.data, dict) else str(exc)
        logger.warning("Could not create webhook for %s: %s", db_repo.full_name, msg)
        return f"Could not create webhook ({exc.status}): {msg}. Need admin rights on the repo."


def remove_repo_webhook(gh_repo, db_repo: Repository) -> None:
    if not db_repo.webhook_id:
        return
    try:
        gh_repo.get_hook(db_repo.webhook_id).delete()
    except GithubException as exc:
        logger.warning("Could not delete webhook %s: %s", db_repo.webhook_id, exc)
    db_repo.webhook_id = None
    db_repo.save(update_fields=["webhook_id", "updated_at"])


def sync_open_pull_requests(gh_repo, db_repo: Repository, limit: int | None = None) -> int:
    """Import currently-open PRs and queue a review for each new head SHA. Returns PRs imported."""
    limit = MAX_BACKFILL_PRS if limit is None else limit
    imported = 0
    try:
        pulls = gh_repo.get_pulls(state="open", sort="updated", direction="desc")
        for gh_pr in pulls[:limit]:
            db_pr, _ = PullRequest.objects.update_or_create(
                repository=db_repo,
                number=gh_pr.number,
                defaults={
                    "title": gh_pr.title[:500],
                    "author": (gh_pr.user.login if gh_pr.user else "")[:100],
                    "state": "open",
                    "html_url": gh_pr.html_url,
                    "latest_head_sha": gh_pr.head.sha,
                },
            )
            imported += 1
            review, created = Review.objects.get_or_create(
                pull_request=db_pr,
                head_sha=gh_pr.head.sha,
                defaults={"status": Review.Status.PENDING},
            )
            if created:
                run_llm_review.delay(review.pk)
    except GithubException as exc:
        logger.warning("PR backfill failed for %s: %s", db_repo.full_name, exc)
    return imported
