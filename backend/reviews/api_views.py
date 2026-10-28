"""
reviews/api_views.py
====================
REST API endpoints for Review-hawk pull requests, reviews, and dashboard statistics.
"""

from __future__ import annotations

import logging
from django.db.models import Count, Q
from rest_framework import permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from repos.models import PullRequest, Repository
from reviews.models import Review, ReviewComment
from reviews.serializers import (
    PullRequestDetailSerializer,
    PullRequestListSerializer,
    ReviewDetailSerializer,
    ReviewSummarySerializer,
)

logger = logging.getLogger(__name__)


class StandardPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = "page_size"
    max_page_size = 100


class PullRequestListView(APIView):
    """
    GET /api/repos/{repo_id}/pulls/  or  GET /api/pull-requests/

    List pull requests with optional filtering:
    - ?state=open|closed|merged|all
    - ?search=keyword (matches title, author, or PR number)
    - ?repository=id_or_github_id
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, repo_id: int | None = None):
        user = request.user
        queryset = PullRequest.objects.filter(repository__user=user).select_related("repository")

        # Filter by repo_id from URL or query parameter
        target_repo_id = repo_id or request.query_params.get("repository")
        if target_repo_id:
            queryset = queryset.filter(
                Q(repository_id=target_repo_id) | Q(repository__github_repo_id=target_repo_id)
            )

        # Filter by state
        state = request.query_params.get("state")
        if state and state.lower() != "all":
            queryset = queryset.filter(state=state.lower())

        # Search filter
        search = request.query_params.get("search")
        if search:
            search = search.strip()
            num_filter = Q(number=int(search)) if search.isdigit() else Q()
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(author__icontains=search) | num_filter
            )

        queryset = queryset.order_by("-updated_at")

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = PullRequestListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = PullRequestListSerializer(queryset, many=True)
        return Response(serializer.data)


class PullRequestDetailView(APIView):
    """
    GET /api/pull-requests/{id}/  or  GET /api/repos/{repo_id}/pulls/{id}/

    Retrieve full details for a pull request, including repository metadata,
    latest review verdict, and all code findings/comments.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk: int | None = None, repo_id: int | None = None):
        user = request.user
        queryset = PullRequest.objects.filter(repository__user=user).select_related("repository")

        target_id = pk or self.kwargs.get("id")
        if repo_id:
            # Match either by PR PK or by PR number within the specific repo
            pr = queryset.filter(
                Q(repository_id=repo_id) | Q(repository__github_repo_id=repo_id)
            ).filter(Q(id=target_id) | Q(number=target_id)).first()
        else:
            pr = queryset.filter(Q(id=target_id) | Q(number=target_id)).first()

        if pr is None:
            return Response(
                {"detail": f"Pull request '{target_id}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = PullRequestDetailSerializer(pr)
        return Response(serializer.data)


class ReviewDetailView(APIView):
    """
    GET /api/reviews/{id}/

    Retrieve full review execution run and all comments.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk: int):
        user = request.user
        try:
            review = Review.objects.select_related("pull_request__repository").get(
                pk=pk, pull_request__repository__user=user
            )
        except Review.DoesNotExist:
            return Response(
                {"detail": f"Review {pk} not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = ReviewDetailSerializer(review)
        return Response(serializer.data)


class DashboardStatsView(APIView):
    """
    GET /api/dashboard/stats/

    Aggregated metrics and health overview for the Review Hawk command center.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        # User's connected repositories
        user_repos = Repository.objects.filter(user=user)
        connected_repos_count = user_repos.filter(is_enabled=True).count()
        total_repos_count = user_repos.count()

        # Reviews for this user's repos
        user_reviews = Review.objects.filter(pull_request__repository__user=user)
        total_prs_reviewed = user_reviews.filter(status=Review.Status.COMPLETED).values("pull_request").distinct().count()

        # Review findings / comments
        comments_qs = ReviewComment.objects.filter(review__pull_request__repository__user=user)
        total_findings_count = comments_qs.count()

        severity_counts = {
            "error": comments_qs.filter(severity=ReviewComment.Severity.ERROR).count(),
            "warning": comments_qs.filter(severity=ReviewComment.Severity.WARNING).count(),
            "info": comments_qs.filter(severity=ReviewComment.Severity.INFO).count(),
        }

        category_counts = {}
        for cat_choice in ReviewComment.Category.choices:
            cat_key = cat_choice[0]
            category_counts[cat_key] = comments_qs.filter(category=cat_key).count()

        # Recent review activity
        recent_reviews = user_reviews.select_related("pull_request__repository").order_by("-created_at")[:6]
        recent_activity_data = []
        for r in recent_reviews:
            recent_activity_data.append(
                {
                    "review_id": r.id,
                    "repo_name": r.pull_request.repository.name,
                    "pr_number": r.pull_request.number,
                    "pr_title": r.pull_request.title,
                    "status": r.status,
                    "head_sha": r.head_sha[:7],
                    "llm_model": r.llm_model,
                    "duration_seconds": r.duration_seconds,
                    "created_at": r.created_at,
                    "finished_at": r.finished_at,
                }
            )

        return Response(
            {
                "connected_repos_count": connected_repos_count,
                "total_repos_count": total_repos_count,
                "total_prs_reviewed": total_prs_reviewed,
                "total_findings_count": total_findings_count,
                "findings_by_severity": severity_counts,
                "findings_by_category": category_counts,
                "recent_activity": recent_activity_data,
            }
        )
