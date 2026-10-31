from django.db import models

from repos.models import PullRequest, Repository


class WebhookEvent(models.Model):
    """Audit log of every webhook GitHub sends. Useful for debugging and
    for idempotency (GitHub redelivers; delivery_id is unique)."""

    delivery_id = models.CharField(max_length=64, unique=True)  # X-GitHub-Delivery header
    event_type = models.CharField(max_length=50)  # X-GitHub-Event header, e.g. "pull_request"
    action = models.CharField(max_length=50, blank=True)  # e.g. "opened", "synchronize"
    repository = models.ForeignKey(
        Repository, null=True, blank=True, on_delete=models.SET_NULL, related_name="webhook_events"
    )
    payload = models.JSONField()
    processed = models.BooleanField(default=False)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.event_type}.{self.action} ({self.delivery_id[:8]})"


class Review(models.Model):
    """One review run for one PR at one commit (head_sha)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    pull_request = models.ForeignKey(PullRequest, on_delete=models.CASCADE, related_name="reviews")
    head_sha = models.CharField(max_length=40)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    summary = models.TextField(blank=True)
    error_message = models.TextField(blank=True)

    # Stats for the dashboard
    llm_model = models.CharField(max_length=100, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    files_reviewed = models.PositiveIntegerField(default=0)

    # Rule-based PR health score (see reviews/health_scorer.py)
    health_score = models.PositiveSmallIntegerField(null=True, blank=True)  # 0-100
    health_grade = models.CharField(max_length=2, blank=True)               # A+ .. F
    health_report = models.JSONField(default=dict, blank=True)              # signals, badges, tips

    github_review_id = models.BigIntegerField(null=True, blank=True)  # set once posted
    installation_id = models.BigIntegerField(null=True, blank=True)   # GitHub App installation
    posted_at = models.DateTimeField(null=True, blank=True)           # when review was posted
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Prevents duplicate reviews when GitHub redelivers a webhook.
            models.UniqueConstraint(fields=["pull_request", "head_sha"], name="uniq_review_per_sha"),
        ]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["-created_at"]),
        ]

    @property
    def total_tokens(self):
        return self.input_tokens + self.output_tokens

    @property
    def duration_seconds(self):
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None

    def __str__(self):
        return f"Review of {self.pull_request} @ {self.head_sha[:7]} ({self.status})"


class ReviewComment(models.Model):
    """A single finding, from the LLM or from a tree-sitter rule."""

    class Severity(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"

    class Category(models.TextChoices):
        BUG = "bug", "Bug"
        SECURITY = "security", "Security"
        PERFORMANCE = "performance", "Performance"
        STYLE = "style", "Style"
        MAINTAINABILITY = "maintainability", "Maintainability"
        OTHER = "other", "Other"

    class Source(models.TextChoices):
        LLM = "llm", "LLM"
        STATIC = "static", "Static check"

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="comments")
    file_path = models.CharField(max_length=500)
    line_number = models.PositiveIntegerField()
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.INFO)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    message = models.TextField()
    suggestion = models.TextField(blank=True)  # optional proposed fix
    source = models.CharField(max_length=10, choices=Source.choices)
    rule_id = models.CharField(max_length=100, blank=True)  # e.g. "bare-except" for static checks

    # Filled in once the comment is actually posted on GitHub
    posted = models.BooleanField(default=False)
    github_comment_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["file_path", "line_number"]
        indexes = [
            models.Index(fields=["severity"]),
            models.Index(fields=["source"]),
        ]

    def __str__(self):
        return f"{self.file_path}:{self.line_number} [{self.severity}]"

