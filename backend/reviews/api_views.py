"""
reviews/api_views.py
====================
Read-only REST API behind the dashboard:

  GET /api/repos/<repo_id>/pulls/     pull requests of one repo (+ latest review)
  GET /api/pull-requests/<id>/        one PR with findings + health breakdown
  GET /api/reviews/                   review history (filters: repo, status, q)
  GET /api/reviews/<id>/              one review with all findings
  GET /api/stats/?days=30&repo=<id>   numbers and chart series for the dashboard

Every query is restricted to repositories owned by the logged-in user.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timedelta

from django.db.models import Avg, Count, Prefetch, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from repos.models import PullRequest, Repository

from .models import Review, ReviewComment
from .serializers import (
    RULE_LABELS,
    PullRequestDetailSerializer,
    PullRequestSerializer,
    ReviewDetailSerializer,
    ReviewSummarySerializer,
)

SEVERITIES = ["error", "warning", "info"]
GRADES = ["A+", "A", "B", "C", "D", "F"]


class StandardPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


def _user_repo(user, repo_id: int) -> Repository:
    """Repo by local id, falling back to GitHub's repo id. 404 if not the user's."""
    repos = Repository.objects.filter(user=user)
    repo = repos.filter(pk=repo_id).first() or repos.filter(github_repo_id=repo_id).first()
    if repo is None:
        from rest_framework.exceptions import NotFound
        raise NotFound("Repository not found.")
    return repo


def _prs_with_reviews(qs):
    """Prefetch reviews newest-first with their comments (avoids N+1 queries)."""
    return qs.select_related("repository").prefetch_related(
        Prefetch(
            "reviews",
            queryset=Review.objects.select_related("pull_request__repository")
            .prefetch_related("comments")
            .order_by("-created_at"),
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pull requests
# ─────────────────────────────────────────────────────────────────────────────


class RepoPullRequestListView(ListAPIView):
    """GET /api/repos/<repo_id>/pulls/?state=&search=&page="""

    permission_classes = [IsAuthenticated]
    serializer_class = PullRequestSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        repo = _user_repo(self.request.user, self.kwargs["repo_id"])
        qs = _prs_with_reviews(PullRequest.objects.filter(repository=repo))

        state = self.request.query_params.get("state", "").lower()
        if state in {"open", "closed", "merged"}:
            qs = qs.filter(state=state)

        search = self.request.query_params.get("search", "").strip()
        if search:
            cond = Q(title__icontains=search) | Q(author__icontains=search)
            if search.lstrip("#").isdigit():
                cond |= Q(number=int(search.lstrip("#")))
            qs = qs.filter(cond)
        return qs.order_by("-updated_at")


class PullRequestListView(ListAPIView):
    """GET /api/pull-requests/?state=&search=&page=

    Returns pull requests across all repositories owned by the logged-in user.
    Optionally scoped by ?repository=<id>.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = PullRequestSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = _prs_with_reviews(
            PullRequest.objects.filter(repository__user=self.request.user)
        )

        repo_param = self.request.query_params.get("repository", "").strip()
        if repo_param.isdigit():
            qs = qs.filter(repository_id=int(repo_param))

        state = self.request.query_params.get("state", "").lower()
        if state in {"open", "closed", "merged"}:
            qs = qs.filter(state=state)

        search = self.request.query_params.get("search", "").strip()
        if search:
            cond = Q(title__icontains=search) | Q(author__icontains=search)
            if search.lstrip("#").isdigit():
                cond |= Q(number=int(search.lstrip("#")))
            qs = qs.filter(cond)
        return qs.order_by("-updated_at")


class PullRequestDetailView(RetrieveAPIView):
    """GET /api/pull-requests/<id>/"""

    permission_classes = [IsAuthenticated]
    serializer_class = PullRequestDetailSerializer

    def get_queryset(self):
        return _prs_with_reviews(
            PullRequest.objects.filter(repository__user=self.request.user)
        )


# ─────────────────────────────────────────────────────────────────────────────
# Reviews
# ─────────────────────────────────────────────────────────────────────────────


def _annotated_reviews(user):
    return (
        Review.objects.filter(pull_request__repository__user=user)
        .select_related("pull_request__repository")
        .annotate(
            total_count=Count("comments"),
            error_count=Count("comments", filter=Q(comments__severity="error")),
            warning_count=Count("comments", filter=Q(comments__severity="warning")),
            info_count=Count("comments", filter=Q(comments__severity="info")),
            llm_count=Count("comments", filter=Q(comments__source="llm")),
            static_count=Count("comments", filter=Q(comments__source="static")),
        )
    )


class ReviewListView(ListAPIView):
    """GET /api/reviews/?repo=<id>&status=<status>&q=<text>"""

    permission_classes = [IsAuthenticated]
    serializer_class = ReviewSummarySerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = _annotated_reviews(self.request.user)
        params = self.request.query_params

        repo = params.get("repo")
        if repo and repo.isdigit():
            qs = qs.filter(pull_request__repository_id=int(repo))

        status = params.get("status", "").lower()
        if status in {s.value for s in Review.Status}:
            qs = qs.filter(status=status)

        q = params.get("q", "").strip()
        if q:
            cond = Q(pull_request__title__icontains=q) | Q(pull_request__author__icontains=q)
            if q.lstrip("#").isdigit():
                cond |= Q(pull_request__number=int(q.lstrip("#")))
            qs = qs.filter(cond)
        return qs.order_by("-created_at")


class ReviewDetailView(RetrieveAPIView):
    """GET /api/reviews/<id>/"""

    permission_classes = [IsAuthenticated]
    serializer_class = ReviewDetailSerializer

    def get_queryset(self):
        return _annotated_reviews(self.request.user).prefetch_related("comments")


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard statistics
# ─────────────────────────────────────────────────────────────────────────────


class StatsView(APIView):
    """GET /api/stats/?days=30&repo=<local repo id>"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            days = max(1, min(365, int(request.query_params.get("days", 30))))
        except ValueError:
            days = 30

        repos = Repository.objects.filter(user=request.user)
        repo_param = request.query_params.get("repo")
        if repo_param and repo_param.isdigit():
            repos = repos.filter(pk=int(repo_param))

        today = timezone.now().date()
        start_date = today - timedelta(days=days - 1)
        since = timezone.make_aware(datetime.combine(start_date, time.min))

        reviews = Review.objects.filter(pull_request__repository__in=repos, created_at__gte=since)
        comments = ReviewComment.objects.filter(review__in=reviews)

        # ── totals ─────────────────────────────────────────────────────────
        rv = reviews.aggregate(
            total=Count("id"),
            completed=Count("id", filter=Q(status=Review.Status.COMPLETED)),
            failed=Count("id", filter=Q(status=Review.Status.FAILED)),
            avg_health=Avg("health_score"),
        )
        cm = comments.aggregate(
            total=Count("id"),
            llm=Count("id", filter=Q(source="llm")),
            static=Count("id", filter=Q(source="static")),
        )
        durations = [
            (f - s).total_seconds()
            for s, f in reviews.filter(
                status=Review.Status.COMPLETED, started_at__isnull=False, finished_at__isnull=False
            ).values_list("started_at", "finished_at")[:1000]
        ]
        totals = {
            "repositories": repos.count(),
            "pull_requests_reviewed": reviews.values("pull_request").distinct().count(),
            "reviews": rv["total"],
            "completed": rv["completed"],
            "failed": rv["failed"],
            "findings": cm["total"],
            "ai_findings": cm["llm"],
            "static_findings": cm["static"],
            "avg_health_score": round(rv["avg_health"], 1) if rv["avg_health"] is not None else None,
            "avg_review_seconds": round(sum(durations) / len(durations), 1) if durations else None,
        }

        # ── breakdowns ─────────────────────────────────────────────────────
        sev_counts = {r["severity"]: r["n"] for r in comments.values("severity").annotate(n=Count("id"))}
        severity_breakdown = [{"severity": s, "count": sev_counts.get(s, 0)} for s in SEVERITIES]

        category_breakdown = [
            {"category": r["category"], "count": r["n"]}
            for r in comments.values("category").annotate(n=Count("id")).order_by("-n")
        ]
        source_breakdown = [
            {"source": "llm", "label": "AI review", "count": cm["llm"]},
            {"source": "static", "label": "Tree-sitter", "count": cm["static"]},
        ]
        top_rules = [
            {"rule_id": r["rule_id"], "label": RULE_LABELS.get(r["rule_id"], r["rule_id"]), "count": r["n"]}
            for r in comments.filter(source="static").exclude(rule_id="")
            .values("rule_id").annotate(n=Count("id")).order_by("-n")[:5]
        ]

        grade_counts = {
            r["health_grade"]: r["n"]
            for r in reviews.exclude(health_grade="").values("health_grade").annotate(n=Count("id"))
        }
        health_distribution = [{"grade": g, "count": grade_counts.get(g, 0)} for g in GRADES]

        # ── time series (zero-filled so charts have no gaps) ───────────────
        per_day = defaultdict(lambda: {"error": 0, "warning": 0, "info": 0, "reviews": 0})
        for r in (comments.annotate(day=TruncDate("created_at"))
                  .values("day", "severity").annotate(n=Count("id"))):
            if r["severity"] in SEVERITIES:
                per_day[r["day"]][r["severity"]] += r["n"]
        for r in reviews.annotate(day=TruncDate("created_at")).values("day").annotate(n=Count("id")):
            per_day[r["day"]]["reviews"] += r["n"]

        issues_over_time = []
        for i in range(days):
            d = start_date + timedelta(days=i)
            row = per_day.get(d, {"error": 0, "warning": 0, "info": 0, "reviews": 0})
            issues_over_time.append({
                "date": d.isoformat(),
                **{k: row[k] for k in ("error", "warning", "info")},
                "total": row["error"] + row["warning"] + row["info"],
                "reviews": row["reviews"],
            })

        # ── per repository ─────────────────────────────────────────────────
        findings_by_repo = {
            r["review__pull_request__repository_id"]: r["n"]
            for r in comments.values("review__pull_request__repository_id").annotate(n=Count("id"))
        }
        per_repo = []
        for r in (reviews.values("pull_request__repository_id", "pull_request__repository__owner",
                                 "pull_request__repository__name")
                  .annotate(n=Count("id"), avg=Avg("health_score")).order_by("-n")):
            rid = r["pull_request__repository_id"]
            per_repo.append({
                "repository_id": rid,
                "repository_name": f'{r["pull_request__repository__owner"]}/{r["pull_request__repository__name"]}',
                "reviews": r["n"],
                "findings": findings_by_repo.get(rid, 0),
                "avg_health_score": round(r["avg"], 1) if r["avg"] is not None else None,
            })

        recent = _annotated_reviews(request.user).filter(pull_request__repository__in=repos).order_by("-created_at")[:5]

        return Response({
            "range_days": days,
            "totals": totals,
            "severity_breakdown": severity_breakdown,
            "category_breakdown": category_breakdown,
            "source_breakdown": source_breakdown,
            "top_rules": top_rules,
            "health_distribution": health_distribution,
            "issues_over_time": issues_over_time,
            "per_repository": per_repo,
            "recent_reviews": ReviewSummarySerializer(recent, many=True, context={"request": request}).data,
        })
