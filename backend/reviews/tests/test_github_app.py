"""Tests for GitHub App authentication (reviews/github_app.py). GitHub is mocked."""
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

import pytest
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
from django.contrib.auth import get_user_model
from github import GithubException

from repos.models import Repository
from reviews import github_app
from reviews.github_app import GitHubAccessError, client_for_repository

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def repo():
    user = User.objects.create_user(username="u", password="x")
    return Repository.objects.create(user=user, github_repo_id=1, owner="o", name="r", is_enabled=True)


def add_oauth_token(user):
    app = SocialApp.objects.create(provider="github", name="gh", client_id="id", secret="s")
    account = SocialAccount.objects.create(user=user, provider="github", uid="123")
    SocialToken.objects.create(app=app, account=account, token="gho_user_token")


def fake_app_auth():
    return NS(get_installation_auth=lambda installation_id: f"installation-auth-{installation_id}")


def patch_installation(result=None, error=None):
    """Patch the GitHub App JWT + installation lookup."""
    integration = MagicMock()
    if error:
        integration.get_repo_installation.side_effect = error
    else:
        integration.get_repo_installation.return_value = NS(id=result)
    return (patch.object(github_app, "_app_auth", return_value=fake_app_auth()),
            patch.object(github_app, "GithubIntegration", return_value=integration))


def test_uses_the_app_installation_token_when_installed(repo):
    p1, p2 = patch_installation(result=555)
    with p1, p2, patch.object(github_app, "Github") as gh_cls:
        access = client_for_repository(repo)
    assert (access.auth_mode, access.installation_id, access.warning) == ("app", 555, "")
    gh_cls.assert_called_once_with(auth="installation-auth-555", per_page=100)      # 100 per page = fewest requests


def test_not_installed_falls_back_to_the_users_oauth_token_with_a_warning(repo):
    add_oauth_token(repo.user)
    p1, p2 = patch_installation(error=GithubException(404, {"message": "Not Found"}, {}))
    with p1, p2:
        access = client_for_repository(repo)
    assert access.auth_mode == "oauth"
    assert "not installed on o/r" in access.warning and "OAuth token" in access.warning


def test_not_installed_and_no_fallback_raises_a_clear_error(repo):
    p1, p2 = patch_installation(error=GithubException(404, {"message": "Not Found"}, {}))
    with p1, p2, pytest.raises(GitHubAccessError, match="not installed on o/r"):
        client_for_repository(repo)                                                  # no OAuth token stored
    with p1, p2, pytest.raises(GitHubAccessError, match="not installed"):
        add_oauth_token(repo.user)
        client_for_repository(repo, allow_oauth_fallback=False)


def test_rejected_credentials_are_reported(repo):
    p1, p2 = patch_installation(error=GithubException(401, {"message": "Bad credentials"}, {}))
    with p1, p2, pytest.raises(GitHubAccessError, match="rejected the App credentials"):
        client_for_repository(repo)


def test_other_github_errors_include_the_status_code(repo):
    p1, p2 = patch_installation(error=GithubException(502, {"message": "Bad Gateway"}, {}))
    with p1, p2, pytest.raises(GitHubAccessError, match="502.*Bad Gateway"):
        client_for_repository(repo)


def test_missing_configuration_is_explained(repo):
    with patch.object(github_app, "GITHUB_APP_ID", ""), pytest.raises(GitHubAccessError, match="GITHUB_APP_ID"):
        client_for_repository(repo)


def test_unreadable_private_key_is_explained_without_leaking_the_path(repo):
    with patch.object(github_app, "GITHUB_APP_ID", "123"), \
         patch.object(github_app, "GITHUB_PRIVATE_KEY_PATH", "/definitely/not/here.pem"), \
         pytest.raises(GitHubAccessError) as err:
        client_for_repository(repo)
    assert "private key" in str(err.value) and "/definitely" not in str(err.value)


def test_non_numeric_app_id_is_explained(repo, tmp_path):
    key = tmp_path / "k.pem"
    key.write_text("not a real key")
    with patch.object(github_app, "GITHUB_APP_ID", "abc"), patch.object(github_app, "GITHUB_PRIVATE_KEY_PATH", str(key)), \
         pytest.raises(GitHubAccessError, match="must be a number"):
        client_for_repository(repo)
