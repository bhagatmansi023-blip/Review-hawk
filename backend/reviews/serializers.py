"""
reviews/serializers.py
======================
DRF Serializers for Review-hawk pull requests, reviews, and dashboard metrics.
"""

from rest_framework import serializers

from repos.models import PullRequest, Repository
from repos.serializers import RepositorySerializer
from reviews.models import Review, ReviewComment


class ReviewCommentSerializer(serializers.ModelSerializer):
    """Serializer for individual code review findings/comments."""

    class Meta:
        model = ReviewComment
        fields = [
            "id",
            "file_path",
            "line_number",
            "severity",
            "category",
            "message",
            "suggestion",
            "source",
            "rule_id",
            "posted",
            "github_comment_id",
            "created_at",
        ]


class ReviewSummarySerializer(serializers.ModelSerializer):
    """Compact review serializer for PR listings."""

    total_tokens = serializers.ReadOnlyField()
    duration_seconds = serializers.ReadOnlyField()

    class Meta:
        model = Review
        fields = [
            "id",
            "head_sha",
            "status",
            "summary",
            "error_message",
            "llm_model",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "duration_seconds",
            "files_reviewed",
            "created_at",
            "posted_at",
            "started_at",
            "finished_at",
        ]


class ReviewDetailSerializer(serializers.ModelSerializer):
    """Comprehensive review serializer including all comments/findings."""

    comments = ReviewCommentSerializer(many=True, read_only=True)
    total_tokens = serializers.ReadOnlyField()
    duration_seconds = serializers.ReadOnlyField()

    class Meta:
        model = Review
        fields = [
            "id",
            "head_sha",
            "status",
            "summary",
            "error_message",
            "llm_model",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "duration_seconds",
            "files_reviewed",
            "comments",
            "created_at",
            "posted_at",
            "started_at",
            "finished_at",
        ]


class PullRequestListSerializer(serializers.ModelSerializer):
    """PR list serializer with latest review status embedded."""

    latest_review = serializers.SerializerMethodField()
    repository_name = serializers.CharField(source="repository.name", read_only=True)
    repository_full_name = serializers.CharField(source="repository.full_name", read_only=True)

    class Meta:
        model = PullRequest
        fields = [
            "id",
            "number",
            "title",
            "author",
            "state",
            "html_url",
            "latest_head_sha",
            "repository_name",
            "repository_full_name",
            "created_at",
            "updated_at",
            "latest_review",
        ]

    def get_latest_review(self, obj: PullRequest) -> dict | None:
        latest = obj.reviews.order_by("-created_at").first()
        if latest is None:
            return None
        return ReviewSummarySerializer(latest).data


class PullRequestDetailSerializer(serializers.ModelSerializer):
    """Detailed PR serializer including repo context and full latest review with findings."""

    repository = RepositorySerializer(read_only=True)
    latest_review = serializers.SerializerMethodField()
    review_history = serializers.SerializerMethodField()

    class Meta:
        model = PullRequest
        fields = [
            "id",
            "number",
            "title",
            "author",
            "state",
            "html_url",
            "latest_head_sha",
            "created_at",
            "updated_at",
            "repository",
            "latest_review",
            "review_history",
        ]

    def get_latest_review(self, obj: PullRequest) -> dict | None:
        latest = obj.reviews.order_by("-created_at").first()
        if latest is None:
            return None
        return ReviewDetailSerializer(latest).data

    def get_review_history(self, obj: PullRequest) -> list[dict]:
        reviews = obj.reviews.order_by("-created_at")[:5]
        return ReviewSummarySerializer(reviews, many=True).data
