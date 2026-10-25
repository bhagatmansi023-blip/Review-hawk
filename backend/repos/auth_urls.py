from django.urls import path
from .auth_views import CurrentUserView, LogoutView, GitHubOAuthCallbackView

urlpatterns = [
    # GET  /api/auth/user/             -> returns current logged-in user or 401
    path("user/", CurrentUserView.as_view(), name="auth-current-user"),

    # POST /api/auth/logout/           -> logs out current user session
    path("logout/", LogoutView.as_view(), name="auth-logout"),

    # POST /api/auth/github/callback/  -> exchanges GitHub code for session
    path("github/callback/", GitHubOAuthCallbackView.as_view(), name="auth-github-callback"),
]
