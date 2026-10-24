from rest_framework import serializers

from .models import Repository


class RepositorySerializer(serializers.ModelSerializer):
    """Serialise a stored Repository row."""

    full_name = serializers.ReadOnlyField()

    class Meta:
        model = Repository
        fields = [
            "id",
            "github_repo_id",
            "owner",
            "name",
            "full_name",
            "default_branch",
            "is_private",
            "webhook_id",
            "is_enabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["webhook_id", "created_at", "updated_at"]


class GitHubRepoSerializer(serializers.Serializer):
    """
    Lightweight serialiser for raw repo data returned by the GitHub API
    (before the repo is persisted locally).
    """

    github_repo_id = serializers.IntegerField()
    owner = serializers.CharField()
    name = serializers.CharField()
    full_name = serializers.CharField()
    default_branch = serializers.CharField()
    is_private = serializers.BooleanField()
    html_url = serializers.URLField()
    description = serializers.CharField(allow_null=True, allow_blank=True)
