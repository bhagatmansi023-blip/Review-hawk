import logging
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.models import SocialToken
from django.conf import settings

logger = logging.getLogger(__name__)


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom account adapter for CodeHawk.
    Appends the GitHub access token to the dashboard redirect URL so that
    the frontend SPA can store the token and maintain authentication
    even across different ports (localhost:5173 vs localhost:8000).
    """

    def get_login_redirect_url(self, request):
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
        user = request.user

        if user and user.is_authenticated:
            token_obj = (
                SocialToken.objects.filter(
                    account__user=user, account__provider="github"
                )
                .order_by("-id")
                .first()
            )
            if token_obj and token_obj.token:
                return f"{frontend_url}/dashboard?token={token_obj.token}"

        return f"{frontend_url}/dashboard"
