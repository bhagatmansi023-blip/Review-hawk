from django.conf import settings
from django.db import models


class Repository(models.Model):
    """A GitHub repo a user has connected to the bot."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="repositories"
    )
    github_repo_id = models.BigIntegerField(unique=True)  # stable even if repo is renamed
    owner = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    default_branch = models.CharField(max_length=100, default="main")
    is_private = models.BooleanField(default=False)
    webhook_id = models.BigIntegerField(null=True, blank=True)  # set once webhook is registered
    is_enabled = models.BooleanField(default=False)  # bot only reviews when True
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "repositories"
        ordering = ["owner", "name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="uniq_repo_owner_name"),
        ]

    @property
    def full_name(self):
        return f"{self.owner}/{self.name}"

    def __str__(self):
        return self.full_name


class PullRequest(models.Model):
    """A pull request seen by the bot. One row per PR; reviews hang off it."""

    class State(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"
        MERGED = "merged", "Merged"

    repository = models.ForeignKey(
        Repository, on_delete=models.CASCADE, related_name="pull_requests"
    )
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=500)
    author = models.CharField(max_length=100)
    state = models.CharField(max_length=10, choices=State.choices, default=State.OPEN)
    html_url = models.URLField(blank=True)
    latest_head_sha = models.CharField(max_length=40)  # updated on every push

    # Extended metadata (populated from GitHub API on registration/sync)
    github_pr_id = models.BigIntegerField(null=True, blank=True)
    body = models.TextField(blank=True, default="")
    source_branch = models.CharField(max_length=200, blank=True, default="")
    target_branch = models.CharField(max_length=200, blank=True, default="")
    is_draft = models.BooleanField(default=False)
    additions = models.IntegerField(null=True, blank=True)
    deletions = models.IntegerField(null=True, blank=True)
    changed_files_count = models.IntegerField(null=True, blank=True)
    changed_files = models.JSONField(default=list, blank=True)
    commits_count = models.IntegerField(null=True, blank=True)
    github_created_at = models.DateTimeField(null=True, blank=True)
    github_updated_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    merged_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    sync_error = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["repository", "number"], name="uniq_pr_per_repo"),
        ]

    def __str__(self):
        return f"{self.repository} #{self.number}"
