import hashlib
import logging
import re
from pathlib import Path
from typing import Optional

from decouple import config

logger = logging.getLogger(__name__)

GEMINI_API_KEY = config("GEMINI_API_KEY", default="")
GEMINI_EMBEDDING_MODEL = config("GEMINI_EMBEDDING_MODEL", default="text-embedding-004")
RAG_ENABLED = config("RAG_ENABLED", default=True, cast=bool)

EXCLUDED_PATH_PATTERNS = [
    r"node_modules/", r"\.git/", r"venv/", r"\.venv/", r"env/",
    r"__pycache__/", r"\.pyc$", r"dist/", r"build/", r"\.egg-info/",
    r"\.min\.(js|css)$", r"package-lock\.json$", r"yarn\.lock$",
    r"poetry\.lock$", r"Pipfile\.lock$", r"\.env$", r"\.env\.",
    r"\.(jpg|jpeg|png|gif|svg|ico|woff|woff2|ttf|eot|pdf|zip|gz|tar|bin|exe|dll|so|dylib)$",
]

SUPPORTED_EXTENSIONS = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".jsx": "javascript", ".tsx": "typescript", ".java": "java",
    ".go": "go", ".rb": "ruby", ".php": "php", ".cs": "csharp",
    ".cpp": "cpp", ".c": "c", ".h": "c", ".hpp": "cpp",
    ".rs": "rust", ".swift": "swift", ".kt": "kotlin",
    ".md": "markdown", ".rst": "rst", ".txt": "text",
    ".yml": "yaml", ".yaml": "yaml", ".json": "json",
    ".toml": "toml", ".ini": "ini", ".cfg": "ini",
    ".sh": "bash", ".bash": "bash",
}

MAX_FILE_SIZE_BYTES = 100_000  # 100KB max per file
MAX_CHUNK_SIZE_CHARS = 2000
CHUNK_OVERLAP_LINES = 3


def is_excluded(path: str) -> bool:
    for pattern in EXCLUDED_PATH_PATTERNS:
        if re.search(pattern, path):
            return True
    return False


def get_language(path: str) -> Optional[str]:
    suffix = Path(path).suffix.lower()
    return SUPPORTED_EXTENSIONS.get(suffix)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_chunks_python(source: str, file_path: str, commit_sha: str) -> list:
    """Use tree-sitter to extract functions/classes from Python source."""
    chunks = []
    try:
        import tree_sitter_python as tspython
        from tree_sitter import Language, Parser

        PY_LANG = Language(tspython.language())
        parser = Parser(PY_LANG)
        tree = parser.parse(source.encode("utf-8"))
        root = tree.root_node
        lines = source.splitlines()

        def _extract_node(node, chunk_type):
            name_node = node.child_by_field_name("name")
            symbol = name_node.text.decode("utf-8") if name_node else ""
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            content_text = "\n".join(lines[node.start_point[0]:node.end_point[0] + 1])
            if len(content_text) > MAX_CHUNK_SIZE_CHARS:
                content_text = content_text[:MAX_CHUNK_SIZE_CHARS]
            chunks.append({
                "file_path": file_path, "language": "python", "chunk_type": chunk_type,
                "symbol_name": symbol, "content": content_text,
                "content_hash": content_hash(content_text),
                "start_line": start_line, "end_line": end_line, "commit_sha": commit_sha,
            })

        for child in root.children:
            if child.type == "function_definition":
                _extract_node(child, "function")
            elif child.type == "class_definition":
                _extract_node(child, "class")
                for grandchild in child.children:
                    if grandchild.type == "block":
                        for item in grandchild.children:
                            if item.type == "function_definition":
                                _extract_node(item, "method")
    except Exception as exc:
        logger.warning("Python tree-sitter extraction failed for %s: %s", file_path, exc)
        # Fall back to generic chunking
        chunks = extract_chunks_generic(source, file_path, "python", commit_sha)
    return chunks


def extract_chunks_generic(source: str, file_path: str, language: str, commit_sha: str) -> list:
    """Sliding window chunking for non-Python files."""
    lines = source.splitlines()
    chunks = []
    chunk_size = 50  # lines per chunk
    step = chunk_size - CHUNK_OVERLAP_LINES
    for i in range(0, max(1, len(lines)), step):
        chunk_lines = lines[i:i + chunk_size]
        content_text = "\n".join(chunk_lines)
        if len(content_text) > MAX_CHUNK_SIZE_CHARS:
            content_text = content_text[:MAX_CHUNK_SIZE_CHARS]
        if content_text.strip():
            chunks.append({
                "file_path": file_path, "language": language, "chunk_type": "block",
                "symbol_name": "", "content": content_text,
                "content_hash": content_hash(content_text),
                "start_line": i + 1, "end_line": min(i + chunk_size, len(lines)),
                "commit_sha": commit_sha,
            })
        if i + chunk_size >= len(lines):
            break
    return chunks


def generate_embedding(text: str) -> list:
    """Call Gemini embedding API. Returns list of 768 floats."""
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        result = client.models.embed_content(
            model=GEMINI_EMBEDDING_MODEL,
            contents=text,
        )
        # result.embeddings is a list of ContentEmbedding objects
        if result.embeddings:
            return result.embeddings[0].values
        return []
    except Exception as exc:
        logger.error("Embedding generation failed: %s", exc)
        raise


def index_repository(repo_id: int, github_client, commit_sha: str) -> dict:
    """
    Fetch source files from GitHub, chunk them, generate embeddings, and store in DB.
    Returns dict with counts: {files_indexed, chunks_created, chunks_updated, errors}.
    """
    from rag.models import CodeChunk, RepositoryIndex
    from repos.models import Repository

    repo = Repository.objects.get(pk=repo_id)
    idx, _ = RepositoryIndex.objects.get_or_create(repository=repo)

    files_indexed = 0
    chunks_created = 0
    chunks_updated = 0
    errors = []

    try:
        gh_repo = github_client.get_repo(repo.full_name)
        # Get file tree
        try:
            contents = gh_repo.get_git_tree(commit_sha, recursive=True)
        except Exception as exc:
            raise RuntimeError(f"Could not fetch git tree: {exc}") from exc

        for item in contents.tree:
            if item.type != "blob":
                continue
            path = item.path
            if is_excluded(path):
                continue
            language = get_language(path)
            if language is None:
                continue
            # Skip large files
            if item.size and item.size > MAX_FILE_SIZE_BYTES:
                logger.debug("Skipping large file %s (%d bytes)", path, item.size)
                continue

            try:
                file_content = gh_repo.get_contents(path, ref=commit_sha)
                try:
                    source = file_content.decoded_content.decode("utf-8", errors="replace")
                except Exception:
                    continue  # binary file

                if language == "python":
                    file_chunks = extract_chunks_python(source, path, commit_sha)
                else:
                    file_chunks = extract_chunks_generic(source, path, language, commit_sha)

                if not file_chunks:
                    continue

                # Upsert by content_hash — skip unchanged, update changed
                for chunk_data in file_chunks:
                    ch = chunk_data["content_hash"]
                    existing = CodeChunk.objects.filter(
                        repository=repo, file_path=path,
                        start_line=chunk_data["start_line"],
                    ).first()

                    if existing and existing.content_hash == ch:
                        # Unchanged — skip embedding regeneration
                        continue

                    # Generate embedding
                    try:
                        emb = generate_embedding(chunk_data["content"])
                    except Exception as emb_exc:
                        errors.append(f"{path}: embedding failed: {emb_exc}")
                        continue

                    if existing:
                        existing.language = language
                        existing.chunk_type = chunk_data["chunk_type"]
                        existing.symbol_name = chunk_data["symbol_name"]
                        existing.content = chunk_data["content"]
                        existing.content_hash = ch
                        existing.end_line = chunk_data["end_line"]
                        existing.commit_sha = commit_sha
                        existing.embedding = emb
                        existing.save()
                        chunks_updated += 1
                    else:
                        CodeChunk.objects.create(
                            repository=repo,
                            embedding=emb,
                            **{k: v for k, v in chunk_data.items() if k != "content_hash"},
                            content_hash=ch,
                        )
                        chunks_created += 1

                files_indexed += 1

            except Exception as file_exc:
                errors.append(f"{path}: {file_exc}")
                logger.warning("Failed to process %s: %s", path, file_exc)
                continue

    except Exception as exc:
        raise RuntimeError(f"index_repository failed: {exc}") from exc

    return {
        "files_indexed": files_indexed,
        "chunks_created": chunks_created,
        "chunks_updated": chunks_updated,
        "errors": errors,
    }
