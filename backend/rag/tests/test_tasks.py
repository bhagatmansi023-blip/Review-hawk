import pytest
from unittest.mock import MagicMock, patch
from django.contrib.auth import get_user_model
from repos.models import Repository
from rag.models import RepositoryIndex
from rag.tasks import index_repository_task

User = get_user_model()


@pytest.mark.django_db
@patch("rag.indexer.index_repository")
@patch("github.Github")
@patch("allauth.socialaccount.models.SocialToken.objects.filter")
def test_index_repository_task_success(mock_token_filter, mock_gh_cls, mock_index_repo):
    user = User.objects.create_user(username="taskuser", email="task@example.com")
    repo = Repository.objects.create(
        user=user,
        github_repo_id=200,
        owner="owner",
        name="task-repo",
        default_branch="main",
    )

    mock_token = MagicMock()
    mock_token.token = "gho_mock_token"
    mock_token_filter.return_value.order_by.return_value.first.return_value = mock_token

    mock_gh = MagicMock()
    mock_gh_repo = MagicMock()
    mock_branch = MagicMock()
    mock_branch.commit.sha = "1234567890abcdef1234567890abcdef12345678"
    mock_gh_repo.get_branch.return_value = mock_branch
    mock_gh.get_repo.return_value = mock_gh_repo
    mock_gh_cls.return_value = mock_gh

    mock_index_repo.return_value = {
        "files_indexed": 10,
        "chunks_created": 25,
        "chunks_updated": 0,
        "errors": [],
    }

    index_repository_task(repo.pk, force=True)

    idx = RepositoryIndex.objects.get(repository=repo)
    assert idx.index_status == "ready"
    assert idx.indexed_files == 10
    assert idx.indexed_chunks == 25
    assert idx.indexed_commit_sha == "1234567890abcdef1234567890abcdef12345678"


@pytest.mark.django_db
def test_index_repository_task_nonexistent_repo():
    # Should not raise
    index_repository_task(999999)
