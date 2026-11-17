from django.db import models
from repos.models import Repository


class RepositoryIndex(models.Model):
    """Tracks the RAG indexing state for a repository."""

    class IndexStatus(models.TextChoices):
        NEVER = "never", "Never Indexed"
        PENDING = "pending", "Pending"
        INDEXING = "indexing", "Indexing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    repository = models.OneToOneField(
        Repository,
        on_delete=models.CASCADE,
        related_name="index",
    )
    index_status = models.CharField(
        max_length=20,
        choices=IndexStatus.choices,
        default=IndexStatus.NEVER,
    )
    indexed_commit_sha = models.CharField(max_length=40, blank=True, default="")
    indexed_at = models.DateTimeField(null=True, blank=True)
    indexed_files = models.IntegerField(default=0)
    indexed_chunks = models.IntegerField(default=0)
    index_error = models.TextField(blank=True, default="")
    index_started_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.repository.full_name} [{self.index_status}]"


class CodeChunk(models.Model):
    """A chunk of source code with its embedding for semantic search."""

    class ChunkType(models.TextChoices):
        FUNCTION = "function", "Function"
        CLASS = "class", "Class"
        METHOD = "method", "Method"
        MODULE = "module", "Module"
        DOCUMENTATION = "documentation", "Documentation"
        CONFIG = "config", "Config"
        BLOCK = "block", "Block"

    repository = models.ForeignKey(
        Repository,
        on_delete=models.CASCADE,
        related_name="code_chunks",
    )
    file_path = models.CharField(max_length=500)
    language = models.CharField(max_length=50)
    chunk_type = models.CharField(
        max_length=20,
        choices=ChunkType.choices,
        default=ChunkType.BLOCK,
    )
    symbol_name = models.CharField(max_length=200, blank=True, default="")
    content = models.TextField()
    content_hash = models.CharField(max_length=64)
    start_line = models.IntegerField()
    end_line = models.IntegerField()
    commit_sha = models.CharField(max_length=40)
    # Stores list[float] since pgvector is not installed.
    # When pgvector is available a migration can convert this to a VectorField.
    embedding = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["repository", "file_path"], name="rag_chunk_repo_path_idx"),
            models.Index(fields=["repository", "chunk_type"], name="rag_chunk_repo_type_idx"),
            models.Index(fields=["content_hash"], name="rag_chunk_hash_idx"),
        ]

    def __str__(self):
        return f"{self.repository.full_name}:{self.file_path}:{self.start_line}-{self.end_line}"
