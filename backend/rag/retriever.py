import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)


def cosine_similarity(a: list, b: list) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def retrieve_context(
    repo_id: int,
    query_text: str,
    limit: int = 10,
    similarity_threshold: float = 0.6,
) -> list:
    """
    Retrieve relevant CodeChunk objects for a repository given a query string.
    Always filters by repository_id first (security boundary).
    Returns list of CodeChunk objects, ordered by cosine similarity descending.
    Falls back to keyword search if embedding fails.
    """
    from rag.models import CodeChunk, RepositoryIndex
    from rag.indexer import generate_embedding

    # Check index is ready
    try:
        idx = RepositoryIndex.objects.get(repository_id=repo_id, index_status="ready")
    except RepositoryIndex.DoesNotExist:
        logger.debug("RAG: no ready index for repo %d — skipping retrieval", repo_id)
        return []

    # Try embedding-based retrieval
    try:
        query_embedding = generate_embedding(query_text)
        if not query_embedding:
            raise ValueError("Empty embedding returned")

        # Fetch all chunks for this repo (bounded by limit*30 to avoid massive loads)
        chunks = list(
            CodeChunk.objects.filter(repository_id=repo_id)
            .exclude(embedding=[])
            .values(
                "id", "file_path", "language", "chunk_type", "symbol_name",
                "content", "start_line", "end_line", "embedding",
            )[:limit * 30]
        )

        # Score by cosine similarity
        scored = []
        for chunk in chunks:
            emb = chunk.get("embedding") or []
            if isinstance(emb, list) and emb:
                sim = cosine_similarity(query_embedding, emb)
                if sim >= similarity_threshold:
                    scored.append((sim, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_ids = [c["id"] for _, c in scored[:limit]]

        if top_ids:
            # Fetch full ORM objects in order
            chunks_qs = CodeChunk.objects.filter(repository_id=repo_id, id__in=top_ids)
            id_to_chunk = {c.pk: c for c in chunks_qs}
            return [id_to_chunk[i] for i in top_ids if i in id_to_chunk]

    except Exception as exc:
        logger.warning("RAG: embedding retrieval failed for repo %d: %s", repo_id, exc)

    # Keyword fallback: extract identifiers from query
    keywords = [w for w in query_text.split() if len(w) > 4 and w.isidentifier()][:3]
    if not keywords:
        return []

    from django.db.models import Q

    q = Q()
    for kw in keywords:
        q |= Q(content__icontains=kw)

    return list(
        CodeChunk.objects.filter(repository_id=repo_id).filter(q)[:limit]
    )


def build_rag_context_string(chunks: list, max_chars: int = 20000) -> str:
    """Format CodeChunk objects as a context string for the LLM prompt."""
    if not chunks:
        return ""

    parts = []
    total = 0
    for chunk in chunks:
        header = f"### {chunk.file_path} (lines {chunk.start_line}-{chunk.end_line}"
        if chunk.symbol_name:
            header += f", {chunk.chunk_type}: {chunk.symbol_name}"
        header += ")"
        body = chunk.content
        section = f"{header}\n```{chunk.language}\n{body}\n```\n"
        if total + len(section) > max_chars:
            break
        parts.append(section)
        total += len(section)

    return "\n".join(parts)
