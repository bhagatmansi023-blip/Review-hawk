"""
reviews/action_views.py
=======================
Manual actions that do not depend on GitHub webhook delivery:

  POST /api/repos/<repo_id>/sync/           import this repo's pull requests from GitHub
                                            (body {"review": true} also queues reviews for open PRs)
  POST /api/pull-requests/<id>/review/      (re)run the AI review for a PR's latest commit

Why these exist: pull requests normally appear in the dashboard only when GitHub
sends a webhook. PRs opened before the app was installed, or while the tunnel
(ngrok/smee) was down, would otherwise never show up.
"""
from __future__ import annotations

import logging
from datetime import datetime
from itertools import islice

from django.shortcuts import get_object_or_404
from github import GithubException
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from repos.models import PullRequest
from repos.views import _get_github_client

from .api_views import _user_repo
from .models import Review
from .tasks import run_llm_review

logger = logging.getLogger(__name__)

MAX_SYNC_PRS = 50          # newest PRs imported per sync
MAX_REVIEWS_PER_SYNC = 5   # keeps Gemini free-tier usage sane


def _truthy(value) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _github_error(exc: GithubException) -> str:
    data = exc.data if isinstance(exc.data, dict) else {}
    return data.get("message") or str(exc)


def _pr_state(gh_pr) -> str:
    merged = getattr(gh_pr, "merged", False) is True or isinstance(getattr(gh_pr, "merged_at", None), datetime)
    if merged:
        return PullRequest.State.MERGED
    return PullRequest.State.CLOSED if getattr(gh_pr, "state", "open") == "closed" else PullRequest.State.OPEN


def _queue(review: Review) -> str | None:
    """
    Hand the review to Celery. Returns an error message if the broker is
    unreachable (the usual cause is Redis not running); the review is then
    marked failed so the UI shows why instead of staying 'pending' forever.
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


def _reset_review(review: Review) -> None:
    """Return a finished/failed review to a clean 'pending' state for another run."""
    review.comments.all().delete()
    review.status = Review.Status.PENDING
    review.summary = ""
    review.error_message = ""
    review.llm_model = ""
    review.input_tokens = review.output_tokens = review.files_reviewed = 0
    review.github_review_id = None
    review.posted_at = review.started_at = review.finished_at = None
    review.health_score = None
    review.health_grade = ""
    review.health_report = {}
    review.save()


class SyncPullRequestsView(APIView):
    """POST /api/repos/<repo_id>/sync/"""

    permission_classes = [IsAuthenticated]

    def post(self, request, repo_id: int):
        repo = _user_repo(request.user, repo_id)
        gh = _get_github_client(request.user)
        if gh is None:
            return Response(
                {"detail": "No GitHub OAuth token found. Please sign in with GitHub again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            gh_prs = list(islice(
                gh.get_repo(repo.full_name).get_pulls(state="all", sort="updated", direction="desc"),
                MAX_SYNC_PRS,
            ))
        except GithubException as exc:
            return Response(
                {"detail": f"GitHub API error: {_github_error(exc)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        created = updated = 0
        synced: list[PullRequest] = []
        for gh_pr in gh_prs:
            obj, was_created = PullRequest.objects.update_or_create(
                repository=repo,
                number=gh_pr.number,
                defaults={
                    "title": (gh_pr.title or "")[:500],
                    "author": (gh_pr.user.login if gh_pr.user else "")[:100],
                    "state": _pr_state(gh_pr),
                    "html_url": gh_pr.html_url or "",
                    "latest_head_sha": gh_pr.head.sha,
                },
            )
            created += was_created
            updated += not was_created
            synced.append(obj)

        queued = 0
        queue_error = None
        if _truthy(request.data.get("review")):
            for pr in synced:
                if queued >= MAX_REVIEWS_PER_SYNC:
                    break
                if pr.state != PullRequest.State.OPEN:
                    continue
                if Review.objects.filter(pull_request=pr, head_sha=pr.latest_head_sha).exists():
                    continue
                review = Review.objects.create(
                    pull_request=pr, head_sha=pr.latest_head_sha, status=Review.Status.PENDING
                )
                queue_error = _queue(review) or queue_error
                queued += 1

        logger.info("Synced %s: %d new, %d updated, %d reviews queued", repo.full_name, created, updated, queued)
        return Response({
            "repository": repo.full_name,
            "created": created,
            "updated": updated,
            "total": len(synced),
            "reviews_queued": queued,
            "queue_error": queue_error,
        })


class ReviewNowView(APIView):
    """POST /api/pull-requests/<id>/review/  (add ?force=1 or {"force": true} to re-run a finished review)"""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        pr = get_object_or_404(PullRequest.objects.select_related("repository"), pk=pk, repository__user=request.user)
        force = _truthy(request.data.get("force")) or _truthy(request.query_params.get("force"))

        # Use the commit GitHub currently shows; fall back to what we have stored.
        sha = pr.latest_head_sha
        gh = _get_github_client(request.user)
        if gh is not None:
            try:
                gh_pr = gh.get_repo(pr.repository.full_name).get_pull(pr.number)
                sha = gh_pr.head.sha or sha
                pr.title, pr.state, pr.latest_head_sha = (gh_pr.title or pr.title)[:500], _pr_state(gh_pr), sha
                pr.save(update_fields=["title", "state", "latest_head_sha", "updated_at"])
            except GithubException as exc:
                logger.warning("Could not refresh PR #%d from GitHub: %s", pr.number, _github_error(exc))
        if not sha:
            return Response({"detail": "This pull request has no commit to review."}, status=status.HTTP_400_BAD_REQUEST)

        review = Review.objects.filter(pull_request=pr, head_sha=sha).first()
        if review is None:
            review = Review.objects.create(pull_request=pr, head_sha=sha, status=Review.Status.PENDING)
        elif review.status in (Review.Status.RUNNING, Review.Status.PENDING) and not force:
            return Response(
                {"detail": "A review for this commit is already queued or running.", "review_id": review.pk,
                 "status": review.status},
                status=status.HTTP_409_CONFLICT,
            )
        elif review.status == Review.Status.COMPLETED and not force:
            return Response(
                {"detail": "This commit has already been reviewed. Send force=true to run it again.",
                 "review_id": review.pk, "status": review.status},
                status=status.HTTP_409_CONFLICT,
            )
        else:
            _reset_review(review)

        queue_error = _queue(review)
        review.refresh_from_db()
        return Response(
            {"review_id": review.pk, "status": review.status, "head_sha": sha,
             "queued": queue_error is None, "queue_error": queue_error,
             **({"detail": queue_error} if queue_error else {})},
            status=status.HTTP_202_ACCEPTED if queue_error is None else status.HTTP_503_SERVICE_UNAVAILABLE,
        )
