import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model
from repos.models import Repository
from rag.models import CodeChunk, RepositoryIndex
from rag.retriever import retrieve_context, build_rag_context_string, cosine_similarity

User = get_user_model()


def test_cosine_similarity():
    v1 = [1.0, 0.0]
    v2 = [1.0, 0.0]
    v3 = [0.0, 1.0]
    assert pytest.approx(cosine_similarity(v1, v2)) == 1.0
    assert pytest.approx(cosine_similarity(v1, v3)) == 0.0
    assert cosine_similarity([], []) == 0.0


@pytest.mark.django_db
@patch("rag.indexer.generate_embedding")
def test_retrieve_context_embedding_and_isolation(mock_emb):
    mock_emb.return_value = [1.0, 0.0, 0.0]

    user = User.objects.create_user(username="u1", email="u1@example.com")
    repo1 = Repository.objects.create(
        user=user, github_repo_id=1, owner="own", name="repo1"
    )
    repo2 = Repository.objects.create(
        user=user, github_repo_id=2, owner="own", name="repo2"
    )

    RepositoryIndex.objects.create(repository=repo1, index_status="ready")
    RepositoryIndex.objects.create(repository=repo2, index_status="ready")

    chunk1 = CodeChunk.objects.create(
        repository=repo1,
        file_path="service.py",
        language="python",
        chunk_type="function",
        symbol_name="auth_user",
        content="def auth_user(): pass",
        content_hash="h1",
        start_line=1,
        end_line=2,
        commit_sha="c1",
        embedding=[0.9, 0.1, 0.0],
    )

    chunk2 = CodeChunk.objects.create(
        repository=repo2,
        file_path="secret.py",
        language="python",
        chunk_type="function",
        symbol_name="secret_key",
        content="def secret(): pass",
        content_hash="h2",
        start_line=1,
        end_line=2,
        commit_sha="c2",
        embedding=[1.0, 0.0, 0.0],
    )

    # Retrieval for repo1 must NEVER return chunks from repo2
    results = retrieve_context(repo1.pk, "auth_user function", limit=5, similarity_threshold=0.5)
    assert len(results) == 1
    assert results[0].pk == chunk1.pk
    assert all(c.repository_id == repo1.pk for c in results)


@pytest.mark.django_db
def test_retrieve_context_not_ready():
    user = User.objects.create_user(username="u2", email="u2@example.com")
    repo = Repository.objects.create(
        user=user, github_repo_id=10, owner="own", name="repo10"
    )
    RepositoryIndex.objects.create(repository=repo, index_status="indexing")

    results = retrieve_context(repo.pk, "something", limit=5)
    assert results == []


def test_build_rag_context_string():
    class DummyChunk:
        file_path = "app/models.py"
        start_line = 10
        end_line = 25
        symbol_name = "User"
        chunk_type = "class"
        language = "python"
        content = "class User:\n    pass"

    text = build_rag_context_string([DummyChunk()])
    assert "### app/models.py (lines 10-25, class: User)" in text
    assert "class User:" in text
