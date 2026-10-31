"""Dashboard API routes (mounted at /api/ in config/urls.py)."""
from django.urls import path

from . import action_views as a
from . import api_views as v

urlpatterns = [
    path("repos/<int:repo_id>/pulls/", v.RepoPullRequestListView.as_view(), name="repo-pulls"),
    path("pull-requests/<int:pk>/", v.PullRequestDetailView.as_view(), name="pull-request-detail"),
    path("reviews/", v.ReviewListView.as_view(), name="review-list"),
    path("reviews/<int:pk>/", v.ReviewDetailView.as_view(), name="review-detail"),
    path("stats/", v.StatsView.as_view(), name="stats"),
    path("repos/<int:repo_id>/sync/", a.SyncPullRequestsView.as_view(), name="repo-sync"),
    path("pull-requests/<int:pk>/review/", a.ReviewNowView.as_view(), name="pull-request-review-now"),
]
