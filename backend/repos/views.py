import logging

from allauth.socialaccount.models import SocialToken
from decouple import config
from github import Github, GithubException
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Repository
from .serializers import GitHubRepoSerializer, RepositorySerializer

logger = logging.getLogger(__name__)

WEBHOOK_URL = config("WEBHOOK_URL", default="")
GITHUB_WEBHOOK_SECRET = config("GITHUB_WEBHOOK_SECRET", default="")


def _get_github_client(user) -> Github | None:
    """
    Return an authenticated PyGithub client for *user* by looking up the
    OAuth token stored by django-allauth.  Returns None if no token exists.
    """
    token_obj = (
        SocialToken.objects.filter(account__user=user, account__provider="github")
        .order_by("-expires_at")
        .first()
    )
    if not token_obj:
        return None
    return Github(token_obj.token)


# ---------------------------------------------------------------------------
# GET /api/repos/
# ---------------------------------------------------------------------------

class ListGitHubReposView(APIView):
    """
    Return all repos the authenticated user can access on GitHub.

    The response mixes a ``registered`` flag into each item so the frontend
    knows which repos are already tracked in the database.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        gh = _get_github_client(request.user)
        if gh is None:
            return Response(
                {"detail": "No GitHub OAuth token found. Please connect your GitHub account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            github_repos = gh.get_user().get_repos(type="all", sort="updated")
        except GithubException as exc:
            logger.error("GitHub API error while listing repos: %s", exc)
            return Response(
                {"detail": f"GitHub API error: {exc.data.get('message', str(exc))}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # IDs already registered by this user
        registered_ids = set(
            Repository.objects.filter(user=request.user).values_list("github_repo_id", flat=True)
        )

        data = []
        for repo in github_repos:
            data.append(
                {
                    "github_repo_id": repo.id,
                    "owner": repo.owner.login,
                    "name": repo.name,
                    "full_name": repo.full_name,
                    "default_branch": repo.default_branch or "main",
                    "is_private": repo.private,
                    "html_url": repo.html_url,
                    "description": repo.description,
                    "registered": repo.id in registered_ids,
                }
            )

        serializer = GitHubRepoSerializer(data, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# POST /api/repos/register/
# ---------------------------------------------------------------------------

class RegisterWebhookView(APIView):
    """
    Register a PR/push webhook on one or more GitHub repos and persist them.

    Request body (JSON):
        {
            "repos": [
                {"github_repo_id": 123456789, "owner": "acme", "name": "my-repo"},
                ...
            ]
        }

    For each entry:
    - Creates (or retrieves) the local Repository row.
    - Calls the GitHub API to create the webhook if one is not already stored.
    - Saves the returned webhook_id and sets is_enabled=True.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not WEBHOOK_URL:
            return Response(
                {"detail": "WEBHOOK_URL is not configured on the server."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        repos_input = request.data.get("repos", [])
        if not repos_input:
            return Response(
                {"detail": "Provide at least one repo in the 'repos' list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        gh = _get_github_client(request.user)
        if gh is None:
            return Response(
                {"detail": "No GitHub OAuth token found. Please connect your GitHub account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = []

        for repo_input in repos_input:
            github_repo_id = repo_input.get("github_repo_id")
            owner = repo_input.get("owner", "").strip()
            name = repo_input.get("name", "").strip()

            if not (github_repo_id and owner and name):
                results.append(
                    {
                        "full_name": f"{owner}/{name}",
                        "success": False,
                        "detail": "Missing required fields: github_repo_id, owner, name.",
                    }
                )
                continue

            # ── Fetch from GitHub ──────────────────────────────────────────
            try:
                gh_repo = gh.get_repo(f"{owner}/{name}")
            except GithubException as exc:
                logger.warning("Could not fetch repo %s/%s: %s", owner, name, exc)
                results.append(
                    {
                        "full_name": f"{owner}/{name}",
                        "success": False,
                        "detail": f"GitHub API error: {exc.data.get('message', str(exc))}",
                    }
                )
                continue

            # ── Get-or-create the local DB row ─────────────────────────────
            db_repo, _ = Repository.objects.get_or_create(
                github_repo_id=github_repo_id,
                defaults={
                    "user": request.user,
                    "owner": owner,
                    "name": name,
                    "default_branch": gh_repo.default_branch or "main",
                    "is_private": gh_repo.private,
                },
            )

            # ── Register webhook if not already done ───────────────────────
            if db_repo.webhook_id:
                # Already registered — just make sure it's enabled
                db_repo.is_enabled = True
                db_repo.save(update_fields=["is_enabled", "updated_at"])
                results.append(
                    {
                        "full_name": f"{owner}/{name}",
                        "success": True,
                        "detail": "Webhook already registered.",
                        "repo": RepositorySerializer(db_repo).data,
                    }
                )
                continue

            hook_config = {
                "url": WEBHOOK_URL,
                "content_type": "json",
                "insecure_ssl": "0",
            }
            if GITHUB_WEBHOOK_SECRET:
                hook_config["secret"] = GITHUB_WEBHOOK_SECRET

            try:
                hook = gh_repo.create_hook(
                    name="web",
                    config=hook_config,
                    events=["pull_request", "push"],
                    active=True,
                )
            except GithubException as exc:
                logger.error(
                    "Failed to create webhook for %s/%s: %s", owner, name, exc
                )
                results.append(
                    {
                        "full_name": f"{owner}/{name}",
                        "success": False,
                        "detail": f"Webhook creation failed: {exc.data.get('message', str(exc))}",
                    }
                )
                continue

            db_repo.webhook_id = hook.id
            db_repo.is_enabled = True
            db_repo.save(update_fields=["webhook_id", "is_enabled", "updated_at"])

            logger.info("Registered webhook %s for %s/%s", hook.id, owner, name)
            results.append(
                {
                    "full_name": f"{owner}/{name}",
                    "success": True,
                    "detail": "Webhook registered successfully.",
                    "repo": RepositorySerializer(db_repo).data,
                }
            )

        all_ok = all(r["success"] for r in results)
        http_status = status.HTTP_200_OK if all_ok else status.HTTP_207_MULTI_STATUS
        return Response({"results": results}, status=http_status)


# ---------------------------------------------------------------------------
# DELETE /api/repos/<github_repo_id>/unregister/
# ---------------------------------------------------------------------------

class UnregisterWebhookView(APIView):
    """
    Remove the webhook from GitHub and mark the repo as disabled.

    The local Repository row is kept so history is preserved.
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request, github_repo_id: int):
        try:
            db_repo = Repository.objects.get(
                github_repo_id=github_repo_id, user=request.user
            )
        except Repository.DoesNotExist:
            return Response(
                {"detail": "Repository not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if db_repo.webhook_id:
            gh = _get_github_client(request.user)
            if gh:
                try:
                    gh_repo = gh.get_repo(db_repo.full_name)
                    hook = gh_repo.get_hook(db_repo.webhook_id)
                    hook.delete()
                    logger.info(
                        "Deleted webhook %s for %s", db_repo.webhook_id, db_repo.full_name
                    )
                except GithubException as exc:
                    # Log but don't fail — the webhook may already be gone
                    logger.warning(
                        "Could not delete webhook %s: %s", db_repo.webhook_id, exc
                    )

        db_repo.webhook_id = None
        db_repo.is_enabled = False
        db_repo.save(update_fields=["webhook_id", "is_enabled", "updated_at"])

        return Response(
            {"detail": f"Webhook removed and {db_repo.full_name} disabled."},
            status=status.HTTP_200_OK,
        )
