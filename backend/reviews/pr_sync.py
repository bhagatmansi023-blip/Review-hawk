"""
reviews/pr_sync.py
==================
Pull request synchronisation from the GitHub API.

Webhooks only tell us about *new* events. This module reads the real state from GitHub so
that already-open pull requests show up too, and so the dashboard still works when webhook
delivery is broken (tunnel down, wrong URL, ...).

For each connected repository it:
  1. authenticates as the GitHub App installation (OAuth user token only as a flagged fallback),
  2. fetches ALL open pull requests (paginated, 100 per request),
  3. creates or updates PullRequest rows (never duplicates),
  4. refreshes PRs we believed were open but GitHub no longer lists (closed / merged),
  5. queues a review for every open PR whose current head commit has no review yet
     (failed reviews are retried; pending/running/completed ones are left alone),
  6. records status, count and any error on the Repository row.

One repository failing never stops the others, and nothing is skipped silently.
"""
from __future__ import annotations

import itertools
import logging
from datetime import datetime, timedelta

from decouple import config
from django.db.models import Count, F, Q
from django.utils import timezone
from github import GithubException

from repos.models import PullRequest, Repository

from .github_app import GitHubAccessError, client_for_repository
from .models import Review
from .queueing import celery_status, queue_review, reset_review

logger = logging.getLogger(__name__)

MAX_PRS_PER_REPO = config("SYNC_MAX_PRS_PER_REPO", default=500, cast=int)
MAX_STALE_REFRESH = 50                     # open-in-DB PRs re-checked individually per sync
LOCK_TIMEOUT = timedelta(minutes=5)        # a "syncing" lock older than this is considered dead


# ─────────────────────────────────────────────────────────────────────────────
# Single pull request
# ─────────────────────────────────────────────────────────────────────────────
def _dt(value):
    return value if isinstance(value, datetime) else None


def pr_state(gh_pr) -> str:
    """open / merged / closed. The list endpoint has merged_at (not the lazy 'merged' flag)."""
    if getattr(gh_pr, "state", "open") == "open":
        return PullRequest.State.OPEN
    return PullRequest.State.MERGED if getattr(gh_pr, "merged_at", None) else PullRequest.State.CLOSED


def upsert_pull_request(db_repo: Repository, gh_pr, installation_id: int | None):
    """
    Create or update the PullRequest row for a PyGithub PR object.
    Returns (PullRequest, created) or (None, False) if GitHub gave no head commit.
    """
    head = getattr(gh_pr, "head", None)
    base = getattr(gh_pr, "base", None)
    user = getattr(gh_pr, "user", None)
    head_sha = getattr(head, "sha", "") or ""
    if not head_sha:
        logger.warning("Skipping PR #%s of %s: GitHub returned no head commit.", getattr(gh_pr, "number", "?"), db_repo.full_name)
        return None, False

    defaults = {
        "title": (getattr(gh_pr, "title", "") or "")[:500],
        "body": getattr(gh_pr, "body", "") or "",
        "author": (getattr(user, "login", "") or "")[:100],
        "state": pr_state(gh_pr),
        "html_url": getattr(gh_pr, "html_url", "") or "",
        "latest_head_sha": head_sha,
        "source_branch": (getattr(head, "ref", "") or "")[:200],
        "target_branch": (getattr(base, "ref", "") or "")[:200],
        "is_draft": bool(getattr(gh_pr, "draft", False)),
        "github_pr_id": getattr(gh_pr, "id", None) if isinstance(getattr(gh_pr, "id", None), int) else None,
        "installation_id": installation_id,
        "github_created_at": _dt(getattr(gh_pr, "created_at", None)),
        "github_updated_at": _dt(getattr(gh_pr, "updated_at", None)),
        "closed_at": _dt(getattr(gh_pr, "closed_at", None)),
        "merged_at": _dt(getattr(gh_pr, "merged_at", None)),
        "last_synced_at": timezone.now(),
        "sync_error": "",
    }
    return PullRequest.objects.update_or_create(repository=db_repo, number=gh_pr.number, defaults=defaults)


# ─────────────────────────────────────────────────────────────────────────────
# Locking (so repeated clicks cannot run two syncs of the same repo at once)
# ─────────────────────────────────────────────────────────────────────────────
def _acquire_lock(db_repo: Repository) -> bool:
    now = timezone.now()
    claimed = (
        Repository.objects.filter(pk=db_repo.pk)
        .filter(~Q(last_sync_status="syncing") | Q(sync_started_at__isnull=True) | Q(sync_started_at__lt=now - LOCK_TIMEOUT))
        .update(last_sync_status="syncing", sync_started_at=now)
    )
    return claimed == 1


def _release_lock(db_repo: Repository, result: dict) -> None:
    fields = {
        "last_sync_status": "ok" if result["ok"] else "error",
        "last_sync_error": result["error"][:2000],
        "last_sync_count": result["fetched"],
        "last_synced_at": timezone.now(),
        "sync_started_at": None,
    }
    if result.get("installation_id"):
        fields["installation_id"] = result["installation_id"]
    Repository.objects.filter(pk=db_repo.pk).update(**fields)


# ─────────────────────────────────────────────────────────────────────────────
# One repository
# ─────────────────────────────────────────────────────────────────────────────
def _empty_result(db_repo: Repository) -> dict:
    return {
        "repository": db_repo.full_name, "repository_id": db_repo.pk,
        "ok": False, "skipped": False, "error": "", "warning": "",
        "auth_mode": "", "installation_id": None,
        "fetched": 0, "created": 0, "updated": 0, "refreshed": 0,
        "reviews_queued": 0, "reviews_retried": 0, "queue_error": None,
    }


def _queue_reviews(db_repo: Repository, prs: list[PullRequest], installation_id: int | None, result: dict) -> None:
    for pr in prs:
        if pr.state != PullRequest.State.OPEN:
            continue
        review, created = Review.objects.get_or_create(
            pull_request=pr,
            head_sha=pr.latest_head_sha,
            defaults={"status": Review.Status.PENDING, "installation_id": installation_id},
        )
        if created:
            result["reviews_queued"] += 1
        elif review.status == Review.Status.FAILED:
            reset_review(review)
            if installation_id:
                review.installation_id = installation_id
                review.save(update_fields=["installation_id"])
            result["reviews_retried"] += 1
        else:
            continue  # pending / running / completed: already handled for this commit
        result["queue_error"] = queue_review(review) or result["queue_error"]


def _refresh_stale_open_prs(gh_repo, db_repo: Repository, seen: set[int], installation_id: int | None, result: dict) -> None:
    """PRs we stored as open that GitHub no longer lists as open were closed or merged since."""
    stale = db_repo.pull_requests.filter(state=PullRequest.State.OPEN).exclude(number__in=seen)[:MAX_STALE_REFRESH]
    for pr in stale:
        try:
            upsert_pull_request(db_repo, gh_repo.get_pull(pr.number), installation_id)
            result["refreshed"] += 1
        except GithubException as exc:
            logger.warning("Could not refresh PR #%d of %s: %s", pr.number, db_repo.full_name, exc)


def sync_repository(db_repo: Repository, *, queue_reviews: bool = True, allow_oauth_fallback: bool = True) -> dict:
    """Synchronise one repository. Never raises: problems are returned (and stored) in the result."""
    result = _empty_result(db_repo)
    if not _acquire_lock(db_repo):
        result.update(ok=True, skipped=True, warning="A sync is already running for this repository.")
        return result

    try:
        access = client_for_repository(db_repo, allow_oauth_fallback=allow_oauth_fallback)
        result.update(auth_mode=access.auth_mode, installation_id=access.installation_id, warning=access.warning)

        gh_repo = access.client.get_repo(db_repo.full_name)
        pulls = list(itertools.islice(
            gh_repo.get_pulls(state="open", sort="updated", direction="desc"), MAX_PRS_PER_REPO))
        result["fetched"] = len(pulls)
        if len(pulls) >= MAX_PRS_PER_REPO:
            result["warning"] = (result["warning"] + f" Stopped at {MAX_PRS_PER_REPO} open PRs.").strip()

        synced: list[PullRequest] = []
        for gh_pr in pulls:
            pr, created = upsert_pull_request(db_repo, gh_pr, access.installation_id)
            if pr is None:
                continue
            synced.append(pr)
            result["created" if created else "updated"] += 1

        _refresh_stale_open_prs(gh_repo, db_repo, {p.number for p in synced}, access.installation_id, result)

        db_repo.default_branch = getattr(gh_repo, "default_branch", None) or db_repo.default_branch
        db_repo.save(update_fields=["default_branch", "updated_at"])

        if queue_reviews:
            _queue_reviews(db_repo, synced, access.installation_id, result)
        result["ok"] = True
        logger.info("Synced %s via %s: %d fetched (%d new), %d reviews queued, %d retried",
                    db_repo.full_name, access.auth_mode, result["fetched"], result["created"],
                    result["reviews_queued"], result["reviews_retried"])
    except GitHubAccessError as exc:
        result["error"] = str(exc)
        logger.error("PR sync failed for %s: %s", db_repo.full_name, exc)
    except GithubException as exc:
        data = exc.data if isinstance(exc.data, dict) else {}
        result["error"] = f"GitHub API error {getattr(exc, 'status', '?')}: {data.get('message') or exc}"
        logger.error("PR sync failed for %s: %s", db_repo.full_name, result["error"])
    except Exception as exc:  # noqa: BLE001 - one broken repo must not stop the rest
        result["error"] = f"Unexpected error: {exc.__class__.__name__}: {exc}"
        logger.exception("PR sync crashed for %s", db_repo.full_name)
    finally:
        _release_lock(db_repo, result)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Many repositories + status snapshot
# ─────────────────────────────────────────────────────────────────────────────
def review_snapshot(repos) -> dict:
    """
    Where do open PRs stand for their *current* commit?
    Counts: open_prs, not_reviewed, pending, processing, completed, failed.
    """
    open_prs = PullRequest.objects.filter(repository__in=repos, state=PullRequest.State.OPEN)
    current = Review.objects.filter(pull_request__in=open_prs, head_sha=F("pull_request__latest_head_sha"))
    by_status = {s["status"]: s["n"] for s in current.values("status").annotate(n=Count("id"))}
    total = open_prs.count()
    reviewed = sum(by_status.values())
    return {
        "open_prs": total,
        "not_reviewed": max(0, total - reviewed),
        "pending": by_status.get("pending", 0),
        "processing": by_status.get("running", 0),
        "completed": by_status.get("completed", 0),
        "failed": by_status.get("failed", 0),
    }


def sync_all(repos, *, queue_reviews: bool = True) -> dict:
    """Synchronise every repository in ``repos`` and return one combined report."""
    repos = list(repos)
    results = [sync_repository(r, queue_reviews=queue_reviews) for r in repos]
    ran = [r for r in results if not r["skipped"]]
    failed = [r for r in ran if not r["ok"]]

    warnings = [f'{r["repository"]}: {r["warning"]}' for r in results if r["warning"]]
    celery = celery_status() if queue_reviews else None
    if celery and celery["warning"]:
        warnings.append(celery["warning"])

    if not ran:
        status = "busy"
    elif not failed:
        status = "ok"
    elif len(failed) == len(ran):
        status = "failed"
    else:
        status = "partial"

    return {
        "status": status,
        "totals": {
            "repositories": len(repos),
            "succeeded": len(ran) - len(failed),
            "failed": len(failed),
            "skipped": len(results) - len(ran),
            "found": sum(r["fetched"] for r in results),
            "created": sum(r["created"] for r in results),
            "updated": sum(r["updated"] for r in results),
            "queued": sum(r["reviews_queued"] + r["reviews_retried"] for r in results),
        },
        "results": results,
        "reviews": review_snapshot(repos),
        "celery": celery,
        "warnings": warnings,
    }
