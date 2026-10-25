import logging
import requests
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from allauth.socialaccount.models import SocialAccount, SocialToken
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class CurrentUserView(APIView):
    """
    GET /api/auth/user/
    Returns the currently logged-in user profile with GitHub social metadata.
    Returns 401 Unauthorized if not logged in.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        user = request.user if (request.user and request.user.is_authenticated) else None

        # Fallback: check Bearer token if session cookie was not provided
        if not user:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token_str = auth_header.split(" ", 1)[1].strip()
                social_token = (
                    SocialToken.objects.filter(token=token_str, account__provider="github")
                    .select_related("account", "account__user")
                    .first()
                )
                if social_token and social_token.account:
                    user = social_token.account.user
                    try:
                        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                    except Exception:
                        pass

        if not user:
            return Response(
                {"detail": "Authentication credentials were not provided."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        social_account = SocialAccount.objects.filter(
            user=user, provider="github"
        ).first()

        extra_data = social_account.extra_data if social_account else {}
        avatar_url = extra_data.get("avatar_url") or ""
        email = user.email or extra_data.get("email") or ""
        name = extra_data.get("name") or user.get_full_name() or user.username

        return Response({
            "id": user.id,
            "username": user.username,
            "email": email,
            "name": name,
            "avatar_url": avatar_url,
            "github_connected": social_account is not None,
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Logs out the current user and clears the Django session.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)


class GitHubOAuthCallbackView(APIView):
    """
    POST /api/auth/github/callback/
    Exchanges a GitHub authorization code for an access token, registers/logs in
    the user in Django session, and returns the user payload.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        code = request.data.get("code")
        if not code:
            return Response(
                {"detail": "Missing authorization code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        github_config = getattr(settings, "SOCIALACCOUNT_PROVIDERS", {}).get("github", {})
        apps = github_config.get("APPS", [])
        client_id = apps[0].get("client_id") if apps else getattr(settings, "GITHUB_CLIENT_ID", "")
        client_secret = apps[0].get("secret") if apps else getattr(settings, "GITHUB_CLIENT_SECRET", "")

        if not client_id or not client_secret:
            return Response(
                {"detail": "GitHub OAuth is not configured on the backend."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Exchange authorization code with GitHub
        try:
            token_res = requests.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                },
                timeout=10,
            )
            token_data = token_res.json()
        except Exception as exc:
            logger.error("Failed to exchange GitHub code: %s", exc)
            return Response(
                {"detail": "Failed to connect to GitHub OAuth server."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        access_token = token_data.get("access_token")
        if not access_token:
            err_msg = (
                token_data.get("error_description")
                or token_data.get("error")
                or "GitHub authorization code exchange failed."
            )
            return Response({"detail": err_msg}, status=status.HTTP_400_BAD_REQUEST)

        # Retrieve user profile from GitHub
        try:
            gh_res = requests.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                timeout=10,
            )
            gh_user = gh_res.json()
        except Exception as exc:
            logger.error("Failed to fetch GitHub user: %s", exc)
            return Response(
                {"detail": "Failed to retrieve GitHub profile."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        gh_uid = str(gh_user.get("id"))
        username = gh_user.get("login") or f"github_{gh_uid}"
        email = gh_user.get("email") or ""

        # Fetch primary email if hidden
        if not email:
            try:
                emails_res = requests.get(
                    "https://api.github.com/user/emails",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                    timeout=10,
                )
                if emails_res.status_code == 200:
                    for em in emails_res.json():
                        if em.get("primary"):
                            email = em.get("email")
                            break
            except Exception:
                pass

        # Find or create User & SocialAccount
        social_account = SocialAccount.objects.filter(provider="github", uid=gh_uid).first()
        if social_account:
            user = social_account.user
        else:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={"email": email, "first_name": gh_user.get("name") or ""},
            )
            social_account = SocialAccount.objects.create(
                user=user,
                provider="github",
                uid=gh_uid,
                extra_data=gh_user,
            )

        social_account.extra_data = gh_user
        social_account.save()

        # Update SocialToken
        token_obj, _ = SocialToken.objects.get_or_create(
            account=social_account,
            defaults={"token": access_token},
        )
        token_obj.token = access_token
        token_obj.save()

        # Login session in Django
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")

        return Response({
            "token": access_token,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": email or user.email,
                "name": gh_user.get("name") or user.username,
                "avatar_url": gh_user.get("avatar_url") or "",
                "github_connected": True,
            },
        }, status=status.HTTP_200_OK)
