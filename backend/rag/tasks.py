import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60, ignore_result=True)
def index_repository_task(self, repo_id: int, force: bool = False) -> None:
    """
    Celery task: index a repository's source code for RAG.
    Uses RepositoryIndex.index_status as a lock to prevent concurrent runs.
    """
    from rag.models import RepositoryIndex
    from rag.indexer import index_repository, RAG_ENABLED
    from repos.models import Repository
    from allauth.socialaccount.models import SocialToken
    from github import Github

    if not RAG_ENABLED:
        logger.info("RAG disabled — skipping index_repository_task for repo %d", repo_id)
        return

    try:
        repo = Repository.objects.select_related("user").get(pk=repo_id)
    except Repository.DoesNotExist:
        logger.error("index_repository_task: repo %d not found", repo_id)
        return

    idx, _ = RepositoryIndex.objects.get_or_create(repository=repo)

    # Prevent concurrent indexing
    if idx.index_status == "indexing" and not force:
        logger.info("Repository %d is already being indexed — skipping.", repo_id)
        return

    # Mark as indexing
    idx.index_status = "indexing"
    idx.index_started_at = timezone.now()
    idx.index_error = ""
    idx.save(update_fields=["index_status", "index_started_at", "index_error"])

    try:
        # Get GitHub client for the repo owner
        token_obj = (
            SocialToken.objects.filter(account__user=repo.user, account__provider="github")
            .order_by("-expires_at")
            .first()
        )
        if not token_obj:
            raise RuntimeError(f"No GitHub token for user {repo.user}")

        gh = Github(token_obj.token)
        gh_repo = gh.get_repo(repo.full_name)
        commit_sha = gh_repo.get_branch(repo.default_branch).commit.sha

        # Skip if already indexed at this commit (unless forced)
        if not force and idx.indexed_commit_sha == commit_sha and idx.index_status == "ready":
            logger.info("Repository %d already indexed at %s — skipping.", repo_id, commit_sha[:7])
            return

        result = index_repository(repo_id, gh, commit_sha)

        idx.index_status = "ready"
        idx.indexed_commit_sha = commit_sha
        idx.indexed_at = timezone.now()
        idx.indexed_files = result["files_indexed"]
        idx.indexed_chunks = result["chunks_created"] + result.get("chunks_updated", 0)
        idx.index_error = "; ".join(result.get("errors", []))[:2000]
        idx.save(update_fields=[
            "index_status", "indexed_commit_sha", "indexed_at",
            "indexed_files", "indexed_chunks", "index_error",
        ])
        logger.info(
            "Repository %d indexed: %d files, %d chunks",
            repo_id, idx.indexed_files, idx.indexed_chunks,
        )

    except Exception as exc:
        logger.exception("index_repository_task failed for repo %d: %s", repo_id, exc)
        idx.index_status = "failed"
        idx.index_error = f"{exc.__class__.__name__}: {exc}"[:2000]
        idx.save(update_fields=["index_status", "index_error"])
        try:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            logger.error("Max retries exceeded for index_repository_task repo %d", repo_id)
