import pytest
from unittest.mock import MagicMock, patch
from django.contrib.auth import get_user_model
from django.core.management import call_command
from repos.models import Repository, PullRequest
from reviews.models import Review

@pytest.mark.django_db
def test_sync_repos_imports_prs():
    u = get_user_model().objects.create_user("u", password="x")
    Repository.objects.create(user=u, github_repo_id=1, owner="o", name="n", is_enabled=True)
    pr = MagicMock(number=7, title="t", html_url="http://x", state="open")
    pr.user.login = "a"; pr.head.sha = "a"*40
    gh_repo = MagicMock(); gh_repo.get_hooks.return_value = []
    gh_repo.get_hook.return_value = MagicMock()
    gh_repo.create_hook.return_value = MagicMock(id=99)
    gh_repo.get_pulls.return_value = [pr]
    gh = MagicMock(); gh.get_repo.return_value = gh_repo
    with patch("reviews.management.commands.sync_repos._get_github_client", return_value=gh), \
         patch("reviews.sync.run_llm_review") as task, \
         patch("reviews.sync.WEBHOOK_URL", "https://x.ngrok-free.app/api/webhook/webhook/"):
        call_command("sync_repos")
    assert PullRequest.objects.filter(number=7).exists()
    assert Review.objects.count() == 1
    task.delay.assert_called_once()
    assert Repository.objects.get().webhook_id == 99
