import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from repos.models import Repository
from rag.models import RepositoryIndex
from unittest.mock import patch

User = get_user_model()


@pytest.mark.django_db
def test_index_status_never():
    user = User.objects.create_user(username="apiuser", email="api@example.com")
    repo = Repository.objects.create(
        user=user, github_repo_id=99, owner="owner", name="api-repo"
    )

    client = APIClient()
    client.force_authenticate(user=user)

    url = f"/api/rag/repos/{repo.pk}/index-status/"
    res = client.get(url)
    assert res.status_code == 200
    assert res.data["status"] == "never"
    assert res.data["indexed_chunks"] == 0


@pytest.mark.django_db
def test_index_status_ready():
    user = User.objects.create_user(username="apiuser2", email="api2@example.com")
    repo = Repository.objects.create(
        user=user, github_repo_id=100, owner="owner", name="api-repo-ready"
    )
    RepositoryIndex.objects.create(
        repository=repo,
        index_status="ready",
        indexed_files=15,
        indexed_chunks=42,
        indexed_commit_sha="abcdef1234567890abcdef1234567890abcdef12",
    )

    client = APIClient()
    client.force_authenticate(user=user)

    url = f"/api/rag/repos/{repo.pk}/index-status/"
    res = client.get(url)
    assert res.status_code == 200
    assert res.data["status"] == "ready"
    assert res.data["indexed_files"] == 15
    assert res.data["indexed_chunks"] == 42


@pytest.mark.django_db
@patch("rag.tasks.index_repository_task.delay")
def test_trigger_reindex(mock_delay):
    user = User.objects.create_user(username="apiuser3", email="api3@example.com")
    repo = Repository.objects.create(
        user=user, github_repo_id=101, owner="owner", name="api-repo-reindex"
    )

    client = APIClient()
    client.force_authenticate(user=user)

    url = f"/api/rag/repos/{repo.pk}/reindex/"
    res = client.post(url, {})
    assert res.status_code == 200
    assert "Reindexing started" in res.data["detail"]
    mock_delay.assert_called_once_with(repo.pk, force=True)
