"""
reviews/action_views.py
=======================
Manual actions that do not depend on GitHub webhook delivery:

  POST /api/sync/                         sync ALL connected repositories (the dashboard button)
  GET  /api/sync/status/                  last sync result per repository + review progress
  POST /api/repos/<repo_id>/sync/         sync one repository
  POST /api/pull-requests/<id>/review/    (re)run the AI review for a PR's latest commit

Pull requests normally appear only when GitHub sends a webhook. These endpoints read the real
state from the GitHub API instead (see reviews/pr_sync.py).
"""
from __future__ import annotations

import logging

from django.shortcuts import get_object_or_404
from github import GithubException
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from repos.models import PullRequest, Repository

from .api_views import _user_repo
from .github_app import GitHubAccessError, client_for_repository
from .models import Review
from .pr_sync import pr_state, review_snapshot, sync_all, sync_repository
from .queueing import celery_status, queue_review, reset_review

logger = logging.getLogger(__name__)


def _truthy(value) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _queue_flag(request) -> bool:
    """Reviews are queued unless the caller explicitly sends review=false."""
    value = request.data.get("review", True) if hasattr(request.data, "get") else True
    return value is True or _truthy(value)


class SyncAllPullRequestsView(APIView):
    """POST /api/sync/ — synchronise every connected repository of the logged-in user."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        repos = list(Repository.objects.filter(user=request.user, is_enabled=True))
        if not repos:
            return Response(
                {"detail": "No repository is connected. Connect one on the Repositories page first."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        report = sync_all(repos, queue_reviews=_queue_flag(request))
        http = status.HTTP_409_CONFLICT if report["status"] == "busy" else status.HTTP_200_OK
        return Response(report, status=http)


class SyncStatusView(APIView):
    """GET /api/sync/status/[?celery=1] — what the last sync did, plus review progress."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        repos = list(Repository.objects.filter(user=request.user, is_enabled=True))
        return Response({
            "repositories": [
                {
                    "repository_id": r.pk, "repository": r.full_name, "installation_id": r.installation_id,
                    "status": r.last_sync_status or "never", "error": r.last_sync_error,
                    "pull_requests_fetched": r.last_sync_count, "last_synced_at": r.last_synced_at,
                }
                for r in repos
            ],
            "reviews": review_snapshot(repos),
            "celery": celery_status() if _truthy(request.query_params.get("celery")) else None,
        })


class SyncPullRequestsView(APIView):
    """POST /api/repos/<repo_id>/sync/ — synchronise one repository."""

    permission_classes = [IsAuthenticated]

    def post(self, request, repo_id: int):
        repo = _user_repo(request.user, repo_id)
        result = sync_repository(repo, queue_reviews=_queue_flag(request))
        if result["skipped"]:
            return Response({**result, "detail": result["warning"]}, status=status.HTTP_409_CONFLICT)
        if not result["ok"]:
            return Response({**result, "detail": result["error"]}, status=status.HTTP_502_BAD_GATEWAY)
        # Keys kept for the Pull Requests page: total, created, updated, reviews_queued, queue_error
        return Response({
            **result,
            "total": result["fetched"],
            "reviews_queued": result["reviews_queued"] + result["reviews_retried"],
        })


class ReviewNowView(APIView):
    """POST /api/pull-requests/<id>/review/  (add ?force=1 or {"force": true} to re-run a finished review)"""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        pr = get_object_or_404(PullRequest.objects.select_related("repository"), pk=pk, repository__user=request.user)
        force = _truthy(request.data.get("force")) or _truthy(request.query_params.get("force"))

        # Use the commit GitHub currently shows; fall back to what we have stored.
        sha = pr.latest_head_sha
        installation_id = pr.installation_id or pr.repository.installation_id
        try:
            access = client_for_repository(pr.repository)
            installation_id = access.installation_id or installation_id
            gh_pr = access.client.get_repo(pr.repository.full_name).get_pull(pr.number)
            sha = gh_pr.head.sha or sha
            pr.title, pr.state, pr.latest_head_sha = (gh_pr.title or pr.title)[:500], pr_state(gh_pr), sha
            pr.save(update_fields=["title", "state", "latest_head_sha", "updated_at"])
        except (GitHubAccessError, GithubException) as exc:
            logger.warning("Could not refresh PR #%d from GitHub: %s", pr.number, exc)
        if not sha:
            return Response({"detail": "This pull request has no commit to review."}, status=status.HTTP_400_BAD_REQUEST)

        review = Review.objects.filter(pull_request=pr, head_sha=sha).first()
        if review is None:
            review = Review.objects.create(
                pull_request=pr, head_sha=sha, status=Review.Status.PENDING, installation_id=installation_id)
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
            reset_review(review)
            if installation_id:
                review.installation_id = installation_id
                review.save(update_fields=["installation_id"])

        queue_error = queue_review(review)
        review.refresh_from_db()
        return Response(
            {"review_id": review.pk, "status": review.status, "head_sha": sha,
             "queued": queue_error is None, "queue_error": queue_error,
             **({"detail": queue_error} if queue_error else {})},
            status=status.HTTP_202_ACCEPTED if queue_error is None else status.HTTP_503_SERVICE_UNAVAILABLE,
        )
        