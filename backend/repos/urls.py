from django.urls import path

from .views import ListGitHubReposView, RegisterWebhookView, UnregisterWebhookView
from reviews.api_views import PullRequestDetailView, PullRequestListView

urlpatterns = [
    # GET  /api/repos/                                → list all GitHub repos
    path("", ListGitHubReposView.as_view(), name="repo-list"),

    # POST /api/repos/register/                       → register webhook(s)
    path("register/", RegisterWebhookView.as_view(), name="repo-register"),

    # DELETE /api/repos/<github_repo_id>/unregister/  → remove webhook
    path(
        "<int:github_repo_id>/unregister/",
        UnregisterWebhookView.as_view(),
        name="repo-unregister",
    ),

    # Nested PR routes: GET /api/repos/<repo_id>/pulls/ and /api/repos/<repo_id>/pulls/<pk>/
    path("<int:repo_id>/pulls/", PullRequestListView.as_view(), name="repo-pulls-list"),
    path("<int:repo_id>/pulls/<int:pk>/", PullRequestDetailView.as_view(), name="repo-pulls-detail"),
]
