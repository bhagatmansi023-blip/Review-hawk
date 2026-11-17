import logging
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class RepositoryIndexStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, repo_id: int):
        from rag.models import RepositoryIndex
        from repos.models import Repository

        try:
            repo = Repository.objects.get(pk=repo_id, user=request.user)
        except Repository.DoesNotExist:
            return Response({"detail": "Repository not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            idx = RepositoryIndex.objects.get(repository=repo)
            return Response({
                "repo_id": repo_id,
                "status": idx.index_status,
                "indexed_at": idx.indexed_at,
                "indexed_files": idx.indexed_files,
                "indexed_chunks": idx.indexed_chunks,
                "indexed_commit_sha": idx.indexed_commit_sha,
                "index_started_at": idx.index_started_at,
                "error": idx.index_error,
            })
        except RepositoryIndex.DoesNotExist:
            return Response({
                "repo_id": repo_id,
                "status": "never",
                "indexed_at": None,
                "indexed_files": 0,
                "indexed_chunks": 0,
                "indexed_commit_sha": "",
                "index_started_at": None,
                "error": "",
            })


class TriggerReindexView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, repo_id: int):
        from rag.tasks import index_repository_task
        from repos.models import Repository

        try:
            repo = Repository.objects.get(pk=repo_id, user=request.user)
        except Repository.DoesNotExist:
            return Response({"detail": "Repository not found."}, status=status.HTTP_404_NOT_FOUND)

        index_repository_task.delay(repo.pk, force=True)
        return Response({"detail": f"Reindexing started for {repo.full_name}."})
