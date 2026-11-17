import pytest
from unittest.mock import MagicMock, patch
from rag.indexer import (
    is_excluded,
    get_language,
    content_hash,
    extract_chunks_python,
    extract_chunks_generic,
    index_repository,
)
from repos.models import Repository
from django.contrib.auth import get_user_model

User = get_user_model()


def test_is_excluded():
    assert is_excluded("node_modules/package/index.js")
    assert is_excluded(".git/HEAD")
    assert is_excluded("venv/lib/site-packages/os.py")
    assert is_excluded("dist/bundle.js")
    assert is_excluded(".env")
    assert is_excluded(".env.production")
    assert is_excluded("image.png")
    assert not is_excluded("src/components/App.jsx")
    assert not is_excluded("backend/reviews/views.py")


def test_get_language():
    assert get_language("main.py") == "python"
    assert get_language("App.jsx") == "javascript"
    assert get_language("index.ts") == "typescript"
    assert get_language("README.md") == "markdown"
    assert get_language("config.yaml") == "yaml"
    assert get_language("unknown.xyz") is None


def test_content_hash():
    h1 = content_hash("hello world")
    h2 = content_hash("hello world")
    h3 = content_hash("different")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 64


def test_extract_chunks_python():
    code = """def add(a, b):
    return a + b

class Calculator:
    def multiply(self, x, y):
        return x * y
"""
    chunks = extract_chunks_python(code, "calc.py", "abc1234")
    assert len(chunks) >= 2
    symbols = [c["symbol_name"] for c in chunks]
    assert "add" in symbols
    assert "Calculator" in symbols


def test_extract_chunks_generic():
    lines = [f"line {i}" for i in range(120)]
    source = "\n".join(lines)
    chunks = extract_chunks_generic(source, "data.txt", "text", "commit1")
    assert len(chunks) > 1
    assert chunks[0]["file_path"] == "data.txt"
    assert chunks[0]["language"] == "text"


@pytest.mark.django_db
@patch("rag.indexer.generate_embedding")
def test_index_repository(mock_emb):
    mock_emb.return_value = [0.1] * 768

    user = User.objects.create_user(username="testuser", email="test@example.com")
    repo = Repository.objects.create(
        user=user,
        github_repo_id=12345,
        owner="owner",
        name="testrepo",
        default_branch="main",
    )

    # Mock GitHub objects
    mock_gh = MagicMock()
    mock_gh_repo = MagicMock()
    mock_gh.get_repo.return_value = mock_gh_repo

    item1 = MagicMock()
    item1.type = "blob"
    item1.path = "app.py"
    item1.size = 200

    tree_mock = MagicMock()
    tree_mock.tree = [item1]
    mock_gh_repo.get_git_tree.return_value = tree_mock

    content_mock = MagicMock()
    content_mock.decoded_content = b"def greet():\n    return 'hello'\n"
    mock_gh_repo.get_contents.return_value = content_mock

    result = index_repository(repo.pk, mock_gh, "commitsha123")

    assert result["files_indexed"] == 1
    assert result["chunks_created"] >= 1
    assert len(result["errors"]) == 0

    from rag.models import CodeChunk
    assert CodeChunk.objects.filter(repository=repo).count() >= 1
