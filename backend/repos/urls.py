from django.urls import path

from .views import ListGitHubReposView, RegisterWebhookView, UnregisterWebhookView

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
]
