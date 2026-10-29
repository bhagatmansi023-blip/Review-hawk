"""
reviews/serializers.py
======================
JSON shapes for the dashboard API. The pull-request shape matches what the
React pages already expect (id, number, title, author, state, html_url,
latest_head_sha, review_status, latest_review, ...).
"""
from __future__ import annotations

from rest_framework import serializers

from repos.models import PullRequest

from .models import Review, ReviewComment

SOURCE_LABELS = {
    ReviewComment.Source.LLM: "AI review",
    ReviewComment.Source.STATIC: "Tree-sitter",
}

# Human-readable names for the Tree-sitter rules in tree_sitter_analyzer.py
RULE_LABELS = {
    "TS-PY-001": "Unused import",
    "TS-PY-002": "Long function",
    "TS-PY-003": "Bare / empty except",
    "TS-PY-004": "Deep nesting",
    "TS-PY-005": "Hardcoded secret",
}


def count_comments(review: Review) -> dict:
    """
    Severity/source counts for one review. Uses queryset annotations when the
    view provided them, otherwise falls back to (prefetched) comment rows.
    """
    if hasattr(review, "error_count"):
        return {
            "error": review.error_count,
            "warning": review.warning_count,
            "info": review.info_count,
            "total": review.total_count,
            "llm": review.llm_count,
            "static": review.static_count,
        }
    out = {"error": 0, "warning": 0, "info": 0, "total": 0, "llm": 0, "static": 0}
    for c in review.comments.all():
        out["total"] += 1
        if c.severity in out:
            out[c.severity] += 1
        if c.source in ("llm", "static"):
            out[c.source] += 1
    return out


class ReviewCommentSerializer(serializers.ModelSerializer):
    """One finding, tagged with where it came from (AI vs Tree-sitter)."""

    source_label = serializers.SerializerMethodField()
    rule_label = serializers.SerializerMethodField()

    class Meta:
        model = ReviewComment
        fields = [
            "id", "file_path", "line_number", "severity", "category", "message",
            "suggestion", "source", "source_label", "rule_id", "rule_label", "posted",
        ]

    def get_source_label(self, obj) -> str:
        return SOURCE_LABELS.get(obj.source, obj.source)

    def get_rule_label(self, obj) -> str:
        return RULE_LABELS.get(obj.rule_id, "")


class ReviewSummarySerializer(serializers.ModelSerializer):
    """Review row for lists and for 'latest_review' inside a pull request."""

    pr_id = serializers.IntegerField(source="pull_request_id", read_only=True)
    pr_number = serializers.IntegerField(source="pull_request.number", read_only=True)
    pr_title = serializers.CharField(source="pull_request.title", read_only=True)
    pr_author = serializers.CharField(source="pull_request.author", read_only=True)
    pr_html_url = serializers.CharField(source="pull_request.html_url", read_only=True)
    repository_id = serializers.IntegerField(source="pull_request.repository_id", read_only=True)
    repository_name = serializers.CharField(source="pull_request.repository.full_name", read_only=True)
    duration_seconds = serializers.FloatField(read_only=True)
    total_tokens = serializers.IntegerField(read_only=True)
    counts = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id", "pr_id", "pr_number", "pr_title", "pr_author", "pr_html_url",
            "repository_id", "repository_name", "head_sha", "status", "summary",
            "llm_model", "input_tokens", "output_tokens", "total_tokens",
            "files_reviewed", "duration_seconds", "created_at", "finished_at",
            "health_score", "health_grade", "counts",
        ]

    def get_counts(self, obj) -> dict:
        return count_comments(obj)


class ReviewDetailSerializer(ReviewSummarySerializer):
    """Full review: adds every finding and the health breakdown."""

    comments = ReviewCommentSerializer(many=True, read_only=True)
    health = serializers.JSONField(source="health_report", read_only=True)

    class Meta(ReviewSummarySerializer.Meta):
        fields = ReviewSummarySerializer.Meta.fields + [
            "error_message", "github_review_id", "posted_at", "health", "comments",
        ]


def _latest_review(pr: PullRequest):
    """Newest review of a PR, using the prefetched list when available."""
    reviews = list(pr.reviews.all())
    return reviews[0] if reviews else None  # prefetch is ordered newest-first


class PullRequestSerializer(serializers.ModelSerializer):
    """Pull request row for the list page."""

    user = serializers.CharField(source="author", read_only=True)
    repository = serializers.IntegerField(source="repository_id", read_only=True)
    repository_name = serializers.CharField(source="repository.full_name", read_only=True)
    target_branch = serializers.CharField(source="repository.default_branch", read_only=True)
    source_branch = serializers.SerializerMethodField()
    review_status = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    latest_review = serializers.SerializerMethodField()

    class Meta:
        model = PullRequest
        fields = [
            "id", "number", "title", "author", "user", "state", "html_url",
            "latest_head_sha", "repository", "repository_name", "source_branch",
            "target_branch", "created_at", "updated_at", "review_status",
            "review_count", "latest_review",
        ]

    def get_source_branch(self, obj):
        return None  # not stored by the webhook handler yet

    def get_review_status(self, obj) -> str:
        r = _latest_review(obj)
        return r.status if r else ""

    def get_review_count(self, obj) -> int:
        return len(list(obj.reviews.all()))

    def _review_serializer(self):
        return ReviewSummarySerializer

    def get_latest_review(self, obj):
        r = _latest_review(obj)
        return self._review_serializer()(r, context=self.context).data if r else None


class PullRequestDetailSerializer(PullRequestSerializer):
    """Detail page: latest review includes all findings; plus review history."""

    review_history = serializers.SerializerMethodField()

    class Meta(PullRequestSerializer.Meta):
        fields = PullRequestSerializer.Meta.fields + ["review_history"]

    def _review_serializer(self):
        return ReviewDetailSerializer

    def get_review_history(self, obj) -> list:
        return [
            {
                "id": r.id,
                "head_sha": r.head_sha,
                "status": r.status,
                "created_at": r.created_at,
                "health_score": r.health_score,
                "health_grade": r.health_grade,
                "counts": count_comments(r),
            }
            for r in obj.reviews.all()
        ]
