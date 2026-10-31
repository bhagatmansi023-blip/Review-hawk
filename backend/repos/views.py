import logging

from allauth.socialaccount.models import SocialToken
from decouple import config
from github import Github, GithubException
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from reviews.sync import ensure_repo_webhook, remove_repo_webhook, sync_open_pull_requests

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
    Enable AI reviews for one or more GitHub repos.

    NOTE: This app uses a GitHub App, which delivers webhook events via a
    single centrally-configured webhook URL (set in the GitHub App settings).
    There is no need — and no permission — to create per-repo webhooks via
    the API.  This view simply registers the repo in the local DB and marks
    it as enabled so the webhook handler knows to review its PRs.

    Request body (JSON):
        {
            "repos": [
                {"github_repo_id": 123456789, "owner": "acme", "name": "my-repo"},
                ...
            ]
        }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
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

            # ── Fetch repo metadata from GitHub ────────────────────────────
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

            # ── Get-or-create the local DB row, mark enabled ───────────────
            db_repo, created = Repository.objects.get_or_create(
                github_repo_id=github_repo_id,
                defaults={
                    "user": request.user,
                    "owner": owner,
                    "name": name,
                    "default_branch": gh_repo.default_branch or "main",
                    "is_private": gh_repo.private,
                    "is_enabled": True,
                },
            )

            if not created:
                db_repo.is_enabled = True
                db_repo.save(update_fields=["is_enabled", "updated_at"])

            detail = "Repository registered for AI review." if created else "Repository re-enabled for AI review."
            logger.info("%s %s/%s", detail, owner, name)

            # Make GitHub actually send PR events, and import PRs that are already open.
            webhook_msg = ensure_repo_webhook(gh_repo, db_repo)
            imported = sync_open_pull_requests(gh_repo, db_repo)

            results.append(
                {
                    "full_name": f"{owner}/{name}",
                    "success": True,
                    "detail": detail,
                    "webhook": webhook_msg,
                    "pull_requests_imported": imported,
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
    Disable AI reviews for a repo and remove it from tracking.

    NOTE: With a GitHub App, there is no per-repo webhook to delete — the
    App's central webhook continues to receive events.  We simply mark the
    repo as disabled so the webhook handler ignores its PR events.
    The local Repository row is kept so review history is preserved.
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

        db_repo.is_enabled = False
        db_repo.save(update_fields=["is_enabled", "updated_at"])
        gh = _get_github_client(request.user)
        if gh is not None and db_repo.webhook_id:
            try:
                remove_repo_webhook(gh.get_repo(db_repo.full_name), db_repo)
            except GithubException as exc:
                logger.warning("Could not clean up webhook for %s: %s", db_repo.full_name, exc)
        logger.info("Disabled AI reviews for %s", db_repo.full_name)

        return Response(
            {"detail": f"AI reviews disabled for {db_repo.full_name}."},
            status=status.HTTP_200_OK,
        )
