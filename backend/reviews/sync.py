
"""
Helpers that run when a repo is connected.

- ensure_repo_webhook: create or reuse the GitHub webhook.
- sync_open_pull_requests: import existing open PRs and queue reviews.
- remove_repo_webhook: remove a registered webhook.
"""

from __future__ import annotations

import logging
from datetime import datetime

from decouple import config
from github import GithubException

from repos.models import PullRequest, Repository
from reviews.models import Review
from reviews.tasks import run_llm_review

logger = logging.getLogger(__name__)

WEBHOOK_URL = config("WEBHOOK_URL", default="")
GITHUB_WEBHOOK_SECRET = config("GITHUB_WEBHOOK_SECRET", default="")
MAX_BACKFILL_PRS = config("MAX_BACKFILL_PRS", default=5, cast=int)


def _safe_int(value, default=None):
    """Convert valid integer values; reject MagicMock and invalid values."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    return default


def _safe_str(value, default=""):
    return value if isinstance(value, str) else default


def _safe_datetime(value):
    return value if isinstance(value, datetime) else None


def ensure_repo_webhook(gh_repo, db_repo: Repository) -> str:
    if not WEBHOOK_URL or "your-public-domain" in WEBHOOK_URL:
        return (
            "WEBHOOK_URL is not set in .env - GitHub cannot reach "
            "this backend, so no PR events will arrive."
        )

    try:
        for hook in gh_repo.get_hooks():
            hook_config = getattr(hook, "config", {}) or {}

            if hook_config.get("url") == WEBHOOK_URL:
                db_repo.webhook_id = _safe_int(
                    getattr(hook, "id", None)
                )
                db_repo.save(
                    update_fields=["webhook_id", "updated_at"]
                )
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

        db_repo.webhook_id = _safe_int(
            getattr(hook, "id", None)
        )
        db_repo.save(
            update_fields=["webhook_id", "updated_at"]
        )

        return "Webhook created."

    except GithubException as exc:
        data = getattr(exc, "data", None)
        msg = (
            data.get("message", str(exc))
            if isinstance(data, dict)
            else str(exc)
        )

        logger.warning(
            "Could not create webhook for %s: %s",
            db_repo.full_name,
            msg,
        )

        return (
            f"Could not create webhook "
            f"({getattr(exc, 'status', 'unknown')}): {msg}. "
            "Check GitHub repository permissions."
        )


def remove_repo_webhook(gh_repo, db_repo: Repository) -> None:
    if not db_repo.webhook_id:
        return

    try:
        gh_repo.get_hook(db_repo.webhook_id).delete()
    except GithubException as exc:
        logger.warning(
            "Could not delete webhook %s: %s",
            db_repo.webhook_id,
            exc,
        )

    db_repo.webhook_id = None
    db_repo.save(update_fields=["webhook_id", "updated_at"])


def sync_open_pull_requests(
    gh_repo,
    db_repo: Repository,
    limit: int | None = None,
) -> int:
    """Import open PRs and queue reviews for new head SHAs."""

    import itertools

    limit = MAX_BACKFILL_PRS if limit is None else limit
    imported = 0

    try:
        pulls = gh_repo.get_pulls(
            state="open",
            sort="updated",
            direction="desc",
        )

        for gh_pr in itertools.islice(pulls, limit):
            head = getattr(gh_pr, "head", None)
            base = getattr(gh_pr, "base", None)
            user = getattr(gh_pr, "user", None)

            head_sha = _safe_str(
                getattr(head, "sha", None)
            )

            if not head_sha:
                logger.warning(
                    "Skipping PR with missing head SHA for %s",
                    db_repo.full_name,
                )
                continue

            number = _safe_int(
                getattr(gh_pr, "number", None)
            )

            if number is None:
                logger.warning(
                    "Skipping PR with invalid number for %s",
                    db_repo.full_name,
                )
                continue

            state = _safe_str(
                getattr(gh_pr, "state", None),
                "open",
            )

            merged = getattr(gh_pr, "merged", False)
            pr_state = (
                "merged"
                if state == "closed" and merged is True
                else state
            )

            if pr_state not in ("open", "closed", "merged"):
                pr_state = "open"

            defaults = {
                "title": _safe_str(
                    getattr(gh_pr, "title", None)
                )[:500],

                "author": _safe_str(
                    getattr(user, "login", None)
                )[:100],

                "state": pr_state,

                "html_url": _safe_str(
                    getattr(gh_pr, "html_url", None)
                ),

                "latest_head_sha": head_sha,

                "github_pr_id": _safe_int(
                    getattr(gh_pr, "id", None)
                ),

                "body": _safe_str(
                    getattr(gh_pr, "body", None)
                ),

                "source_branch": _safe_str(
                    getattr(head, "ref", None)
                )[:200],

                "target_branch": _safe_str(
                    getattr(base, "ref", None)
                )[:200],

                "is_draft": (
                    getattr(gh_pr, "draft", False)
                    if isinstance(
                        getattr(gh_pr, "draft", False), bool
                    )
                    else False
                ),

                "additions": _safe_int(
                    getattr(gh_pr, "additions", None), 0
                ),

                "deletions": _safe_int(
                    getattr(gh_pr, "deletions", None), 0
                ),

                "changed_files_count": _safe_int(
                    getattr(gh_pr, "changed_files", None), 0
                ),

                "github_created_at": _safe_datetime(
                    getattr(gh_pr, "created_at", None)
                ),

                "github_updated_at": _safe_datetime(
                    getattr(gh_pr, "updated_at", None)
                ),

                "closed_at": _safe_datetime(
                    getattr(gh_pr, "closed_at", None)
                ),

                "merged_at": _safe_datetime(
                    getattr(gh_pr, "merged_at", None)
                ),
            }

            db_pr, _ = PullRequest.objects.update_or_create(
                repository=db_repo,
                number=number,
                defaults=defaults,
            )

            imported += 1

            review, created = Review.objects.get_or_create(
                pull_request=db_pr,
                head_sha=head_sha,
                defaults={
                    "status": Review.Status.PENDING
                },
            )

            if created:
                run_llm_review.delay(review.pk)

    except GithubException as exc:
        logger.warning(
            "PR backfill failed for %s: %s",
            db_repo.full_name,
            exc,
        )

    return imported
