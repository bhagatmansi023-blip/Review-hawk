
"""Dashboard API routes (mounted at /api/ in config/urls.py)."""
from django.urls import path

from . import action_views as a
from . import api_views as v

urlpatterns = [
    # Global sync: sync all connected repositories at once (dashboard button)
    path("sync/", a.SyncAllPullRequestsView.as_view(), name="sync-all"),
    path("sync/status/", a.SyncStatusView.as_view(), name="sync-status"),

    path("repos/<int:repo_id>/pulls/", v.RepoPullRequestListView.as_view(), name="repo-pulls"),
    path("pull-requests/<int:pk>/", v.PullRequestDetailView.as_view(), name="pull-request-detail"),
    path("reviews/", v.ReviewListView.as_view(), name="review-list"),
    path("reviews/<int:pk>/", v.ReviewDetailView.as_view(), name="review-detail"),
    path("stats/", v.StatsView.as_view(), name="stats"),

    # Sync pull requests for a single repository
    path("repos/<int:repo_id>/sync/", a.SyncPullRequestsView.as_view(), name="repo-sync"),

    # Manually trigger an AI review
    path("pull-requests/<int:pk>/review/", a.ReviewNowView.as_view(), name="pull-request-review-now"),
]
