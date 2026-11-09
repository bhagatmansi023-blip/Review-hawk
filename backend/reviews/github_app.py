"""
reviews/github_app.py
=====================
GitHub App authentication for reading pull requests.

The App authenticates with a JWT signed by its private key, then exchanges it for a
short-lived *installation* token scoped to the repositories the App is installed on.
That is the identity that should read PRs and post reviews (comments appear as the App,
not as a person).

If the App is not configured or not installed on a repository, the connecting user's
OAuth token can be used as a clearly-flagged fallback so the dashboard still works.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from allauth.socialaccount.models import SocialToken
from decouple import config
from github import Auth, Github, GithubException, GithubIntegration

logger = logging.getLogger(__name__)

GITHUB_APP_ID = config("GITHUB_APP_ID", default="")
GITHUB_PRIVATE_KEY_PATH = config("GITHUB_PRIVATE_KEY_PATH", default="")
PER_PAGE = 100  # GitHub's maximum, so listing PRs needs the fewest requests


class GitHubAccessError(Exception):
    """Raised when we cannot obtain GitHub credentials for a repository (message is user-facing)."""


@dataclass
class RepoAccess:
    client: Github
    installation_id: int | None
    auth_mode: str          # "app" (installation token) or "oauth" (fallback)
    warning: str = ""


def _github_message(exc: GithubException) -> str:
    data = exc.data if isinstance(exc.data, dict) else {}
    return data.get("message") or str(exc)


def _app_auth() -> Auth.AppAuth:
    if not (GITHUB_APP_ID and GITHUB_PRIVATE_KEY_PATH):
        raise GitHubAccessError("GITHUB_APP_ID or GITHUB_PRIVATE_KEY_PATH is not set in .env.")
    try:
        private_key = Path(GITHUB_PRIVATE_KEY_PATH).read_text()
    except OSError as exc:
        raise GitHubAccessError(
            f"Cannot read the GitHub App private key file ({exc.__class__.__name__}). "
            "Check GITHUB_PRIVATE_KEY_PATH."
        ) from exc
    try:
        return Auth.AppAuth(int(GITHUB_APP_ID), private_key)
    except ValueError as exc:
        raise GitHubAccessError("GITHUB_APP_ID must be a number.") from exc


def installation_for_repo(owner: str, name: str) -> tuple[int, Auth.AppAuth]:
    """Return (installation_id, app_auth) for the App installation covering owner/name."""
    app_auth = _app_auth()
    try:
        installation = GithubIntegration(auth=app_auth).get_repo_installation(owner, name)
    except GithubException as exc:
        status = getattr(exc, "status", 0)
        if status == 404:
            raise GitHubAccessError(
                f"The GitHub App is not installed on {owner}/{name}. "
                "Install it from the App's page (the repository owner must do this)."
            ) from exc
        if status in (401, 403):
            raise GitHubAccessError(
                "GitHub rejected the App credentials. Check GITHUB_APP_ID and the private key file."
            ) from exc
        raise GitHubAccessError(f"GitHub API error {status} while looking up the App installation: {_github_message(exc)}") from exc
    return installation.id, app_auth


def oauth_client(user) -> Github | None:
    """PyGithub client using the OAuth token stored by django-allauth for *user*."""
    token = (
        SocialToken.objects.filter(account__user=user, account__provider="github")
        .order_by("-expires_at")
        .first()
    )
    return Github(auth=Auth.Token(token.token), per_page=PER_PAGE) if token else None


def client_for_repository(db_repo, *, allow_oauth_fallback: bool = True) -> RepoAccess:
    """
    Best available GitHub client for a connected repository.

    1. GitHub App installation token (preferred).
    2. The connecting user's OAuth token, only if the App path fails and fallback is allowed.
       The returned ``warning`` says why, so it can be shown to the user.
    """
    try:
        installation_id, app_auth = installation_for_repo(db_repo.owner, db_repo.name)
        client = Github(auth=app_auth.get_installation_auth(installation_id), per_page=PER_PAGE)
        return RepoAccess(client=client, installation_id=installation_id, auth_mode="app")
    except GitHubAccessError as app_error:
        reason = str(app_error)

    if allow_oauth_fallback:
        client = oauth_client(db_repo.user)
        if client is not None:
            logger.warning("App auth unavailable for %s (%s); using the user's OAuth token.", db_repo.full_name, reason)
            return RepoAccess(
                client=client,
                installation_id=db_repo.installation_id,
                auth_mode="oauth",
                warning=f"{reason} Used the connecting user's OAuth token instead.",
            )
    raise GitHubAccessError(reason)
