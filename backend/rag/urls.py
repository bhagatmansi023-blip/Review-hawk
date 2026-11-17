from django.urls import path
from .views import RepositoryIndexStatusView, TriggerReindexView

urlpatterns = [
    path("repos/<int:repo_id>/index-status/", RepositoryIndexStatusView.as_view(), name="rag-index-status"),
    path("repos/<int:repo_id>/reindex/", TriggerReindexView.as_view(), name="rag-reindex"),
]
