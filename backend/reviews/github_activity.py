"""
reviews/github_activity.py
==========================
GitHub data-collection layer for repository health tracking.

Fetches raw repository activity metadata via PyGithub, isolates failures
across sub-calls, normalises datetimes and counts, and validates logical
consistency before returning clean, typed dataclasses.
"""

from __future__ import annotations

import itertools
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import requests as http_requests
from decouple import config
from github import Auth, Github, GithubException, GithubIntegration

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ValidationIssue:
    """One issue or warning identified during activity fetching or validation."""

    field: str
    severity: str  # "warning" | "error"
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "field": self.field,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass
class RepoActivity:
    """
    Clean, typed snapshot of repository activity and metadata.

    All datetimes are timezone-aware UTC. Real open issues exclude open PRs
    (GitHub's ``open_issues_count`` includes both).
    """

    full_name: str
    github_repo_id: int
    default_branch: str
    is_archived: bool
    is_fork: bool
    is_disabled: bool
    created_at: datetime | None
    pushed_at: datetime | None
    updated_at: datetime | None
    stars: int
    forks: int
    open_issues: int  # Real open issues (excluding PRs)
    open_prs: int
    closed_prs_30d: int
    merged_prs_30d: int
    commits_30d: int
    commits_90d: int
    unique_contributors_90d: int
    last_commit_at: datetime | None
    last_release_at: datetime | None
    latest_release_tag: str | None
    default_branch_protected: bool | None
    fetched_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation."""
        return {
            "full_name": self.full_name,
            "github_repo_id": self.github_repo_id,
            "default_branch": self.default_branch,
            "is_archived": self.is_archived,
            "is_fork": self.is_fork,
            "is_disabled": self.is_disabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "pushed_at": self.pushed_at.isoformat() if self.pushed_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "stars": self.stars,
            "forks": self.forks,
            "open_issues": self.open_issues,
            "open_prs": self.open_prs,
            "closed_prs_30d": self.closed_prs_30d,
            "merged_prs_30d": self.merged_prs_30d,
            "commits_30d": self.commits_30d,
            "commits_90d": self.commits_90d,
            "unique_contributors_90d": self.unique_contributors_90d,
            "last_commit_at": self.last_commit_at.isoformat() if self.last_commit_at else None,
            "last_release_at": self.last_release_at.isoformat() if self.last_release_at else None,
            "latest_release_tag": self.latest_release_tag,
            "default_branch_protected": self.default_branch_protected,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
        }


@dataclass
class ActivityResult:
    """Result of fetching or validating repository activity."""

    activity: RepoActivity | None = None
    issues: list[ValidationIssue] = field(default_factory=list)
    partial: bool = False
    stats_pending: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation."""
        return {
            "activity": self.activity.to_dict() if self.activity else None,
            "issues": [issue.to_dict() for issue in self.issues],
            "partial": self.partial,
            "stats_pending": self.stats_pending,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers & Error Handling
# ─────────────────────────────────────────────────────────────────────────────

_REPO_NAME_PATTERN = re.compile(r"^[^/\s]+/[^/\s]+$")


def _to_utc(dt: datetime | None) -> datetime | None:
    """Ensure datetime is timezone-aware UTC, or None if input is None."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _is_rate_limit_error(exc: BaseException) -> bool:
    """Return True if exc represents an exhausted GitHub rate limit."""
    if isinstance(exc, GithubException):
        status = getattr(exc, "status", 0)
        if status == 429:
            return True
        if status == 403:
            msg = str(getattr(exc, "data", "") or getattr(exc, "message", "") or str(exc)).lower()
            if "rate limit" in msg or "secondary rate" in msg:
                return True
            headers = getattr(exc, "headers", {}) or {}
            remaining = headers.get("x-ratelimit-remaining")
            if remaining is not None and str(remaining).strip() == "0":
                return True
    return False


try:
    from reviews.llm_reviewer import _is_transient
except Exception:  # pragma: no cover
    def _is_transient(exc: BaseException) -> bool:
        if isinstance(exc, (http_requests.Timeout, http_requests.ConnectionError)):
            return True
        if isinstance(exc, GithubException):
            status = getattr(exc, "status", 0)
            if status in {403, 429, 500, 502, 503}:
                return True
        return False


def _is_transient_github_error(exc: BaseException) -> bool:
    """
    Check if exc is transient for GitHub API calls.

    5xx, timeouts, connection errors, and rate limits (429 or 403 with quota exhausted)
    are transient and should be re-raised for Celery retries.
    403 permission denied (non-rate-limit), 404, 451, and 409 are permanent.
    """
    if _is_rate_limit_error(exc):
        return True
    if isinstance(exc, (http_requests.Timeout, http_requests.ConnectionError)):
        return True
    if isinstance(exc, GithubException):
        status = getattr(exc, "status", 0)
        if status in {429, 500, 502, 503, 504}:
            return True
        if status == 403:
            return _is_rate_limit_error(exc)
        return False
    return _is_transient(exc)


# ─────────────────────────────────────────────────────────────────────────────
# Activity Validation & Normalisation (Pure)
# ─────────────────────────────────────────────────────────────────────────────


def validate_activity(
    raw: RepoActivity,
    *,
    now: datetime | None = None,
) -> ActivityResult:
    """
    Validate and normalise raw repository activity data.

    Pure function with no network I/O.
    Rules:
    - Normalises all datetimes to timezone-aware UTC.
    - Non-negative counts (coerces None to 0 where 'none' means zero; keeps
      None for honest unknowns like branch protection).
    - Future timestamps (> now + 5 min clock skew) and created_at > pushed_at
      are flagged as warnings and nulled.
    - Checks logical consistency: contributors <= commits, 30d commits <= 90d commits,
      merged PRs <= closed PRs (merged counted within closed).
    - Validates owner/repo format and falls back to 'main' for blank default branch.
    """
    issues: list[ValidationIssue] = []

    if now is None:
        now = datetime.now(timezone.utc)
    now = _to_utc(now)
    clock_skew_threshold = now + timedelta(minutes=5)

    # 1. Name & Default Branch
    full_name = raw.full_name or ""
    if not _REPO_NAME_PATTERN.match(full_name):
        issues.append(
            ValidationIssue(
                field="full_name",
                severity="error",
                message=f"Repository name '{full_name}' does not match expected 'owner/name' format.",
            )
        )

    default_branch = (raw.default_branch or "").strip()
    if not default_branch:
        issues.append(
            ValidationIssue(
                field="default_branch",
                severity="warning",
                message="default_branch is empty; defaulting to 'main'.",
            )
        )
        default_branch = "main"

    # 2. Datetime Normalisation & Future Checks
    created_at = _to_utc(raw.created_at)
    pushed_at = _to_utc(raw.pushed_at)
    updated_at = _to_utc(raw.updated_at)
    last_commit_at = _to_utc(raw.last_commit_at)
    last_release_at = _to_utc(raw.last_release_at)
    fetched_at = _to_utc(raw.fetched_at) or now

    for field_name, dt_val in [
        ("created_at", created_at),
        ("pushed_at", pushed_at),
        ("updated_at", updated_at),
        ("last_commit_at", last_commit_at),
        ("last_release_at", last_release_at),
    ]:
        if dt_val and dt_val > clock_skew_threshold:
            issues.append(
                ValidationIssue(
                    field=field_name,
                    severity="warning",
                    message=f"{field_name} timestamp ({dt_val.isoformat()}) is in the future. Nulled.",
                )
            )
            if field_name == "created_at":
                created_at = None
            elif field_name == "pushed_at":
                pushed_at = None
            elif field_name == "updated_at":
                updated_at = None
            elif field_name == "last_commit_at":
                last_commit_at = None
            elif field_name == "last_release_at":
                last_release_at = None

    # Timestamp order check: created_at <= pushed_at (allowing 5 min clock skew)
    if created_at and pushed_at and (created_at > pushed_at + timedelta(minutes=5)):
        issues.append(
            ValidationIssue(
                field="pushed_at",
                severity="warning",
                message=f"pushed_at ({pushed_at.isoformat()}) precedes created_at ({created_at.isoformat()}). Nulled.",
            )
        )
        pushed_at = None

    # 3. Numeric Count Normalisation
    def _clean_count(val: Any, field_name: str) -> int:
        if val is None:
            return 0
        try:
            int_val = int(val)
        except (ValueError, TypeError):
            issues.append(
                ValidationIssue(
                    field=field_name,
                    severity="warning",
                    message=f"{field_name} value '{val}' could not be parsed as int; coerced to 0.",
                )
            )
            return 0
        if int_val < 0:
            issues.append(
                ValidationIssue(
                    field=field_name,
                    severity="warning",
                    message=f"{field_name} is negative ({int_val}); clamped to 0.",
                )
            )
            return 0
        return int_val

    stars = _clean_count(raw.stars, "stars")
    forks = _clean_count(raw.forks, "forks")
    open_issues = _clean_count(raw.open_issues, "open_issues")
    open_prs = _clean_count(raw.open_prs, "open_prs")
    closed_prs_30d = _clean_count(raw.closed_prs_30d, "closed_prs_30d")
    merged_prs_30d = _clean_count(raw.merged_prs_30d, "merged_prs_30d")
    commits_30d = _clean_count(raw.commits_30d, "commits_30d")
    commits_90d = _clean_count(raw.commits_90d, "commits_90d")
    unique_contributors_90d = _clean_count(raw.unique_contributors_90d, "unique_contributors_90d")

    # 4. Logical Consistency Checks
    if commits_30d > commits_90d:
        issues.append(
            ValidationIssue(
                field="commits_30d",
                severity="warning",
                message=f"commits_30d ({commits_30d}) exceeds commits_90d ({commits_90d}). Clamped to commits_90d.",
            )
        )
        commits_30d = commits_90d

    if unique_contributors_90d > commits_90d:
        issues.append(
            ValidationIssue(
                field="unique_contributors_90d",
                severity="warning",
                message=(
                    f"unique_contributors_90d ({unique_contributors_90d}) exceeds "
                    f"commits_90d ({commits_90d}). Clamped to commits_90d."
                ),
            )
        )
        unique_contributors_90d = commits_90d

    # GitHub counts merged PRs within closed PRs (state='closed' and merged_at is not None)
    if merged_prs_30d > closed_prs_30d:
        issues.append(
            ValidationIssue(
                field="merged_prs_30d",
                severity="warning",
                message=(
                    f"merged_prs_30d ({merged_prs_30d}) exceeds "
                    f"closed_prs_30d ({closed_prs_30d}). Clamped to closed_prs_30d."
                ),
            )
        )
        merged_prs_30d = closed_prs_30d

    # Honest unknowns (kept as None or parsed bool)
    default_branch_protected = (
        bool(raw.default_branch_protected)
        if raw.default_branch_protected is not None
        else None
    )

    clean_activity = RepoActivity(
        full_name=full_name,
        github_repo_id=raw.github_repo_id,
        default_branch=default_branch,
        is_archived=bool(raw.is_archived),
        is_fork=bool(raw.is_fork),
        is_disabled=bool(raw.is_disabled),
        created_at=created_at,
        pushed_at=pushed_at,
        updated_at=updated_at,
        stars=stars,
        forks=forks,
        open_issues=open_issues,
        open_prs=open_prs,
        closed_prs_30d=closed_prs_30d,
        merged_prs_30d=merged_prs_30d,
        commits_30d=commits_30d,
        commits_90d=commits_90d,
        unique_contributors_90d=unique_contributors_90d,
        last_commit_at=last_commit_at,
        last_release_at=last_release_at,
        latest_release_tag=raw.latest_release_tag,
        default_branch_protected=default_branch_protected,
        fetched_at=fetched_at,
    )

    return ActivityResult(activity=clean_activity, issues=issues)


# ─────────────────────────────────────────────────────────────────────────────
# PyGithub Data Collection
# ─────────────────────────────────────────────────────────────────────────────


def fetch_repo_activity(
    gh: Github,
    full_name: str,
    *,
    window_days: int = 90,
    max_items: int = 300,
) -> ActivityResult:
    """
    Fetch raw repository activity metadata via PyGithub.

    Isolation & Error Policy:
    - Pre-checks remaining API quota via gh.get_rate_limit().
    - Top-level failure (404, 451, permanent 403) returns ActivityResult with
      activity=None and an error ValidationIssue.
    - Transient errors (timeouts, 5xx, rate limits) are re-raised so Celery can retry.
    - Sub-calls (commits, branch protection, PRs, releases) are isolated: failure
      records a warning ValidationIssue, leaves the field None, and continues.
    - Detects empty repositories (409 Conflict) and handles zero releases.
    - True open issues are computed as max(0, repo.open_issues_count - open_prs)
      to avoid double-counting open PRs while conserving API quota.
    """
    issues: list[ValidationIssue] = []
    partial = False
    stats_pending = False
    now = datetime.now(timezone.utc)

    # 1. Rate Limit Pre-Check
    try:
        rate_limit = gh.get_rate_limit()
        if hasattr(rate_limit, "core") and getattr(rate_limit.core, "remaining", 100) < 10:
            rem = rate_limit.core.remaining
            logger.warning("GitHub API rate limit exhausted or near-empty (remaining=%s)", rem)
            raise GithubException(
                status=403,
                data={"message": f"API rate limit exhausted (remaining={rem})"},
                headers={"x-ratelimit-remaining": str(rem)},
            )
    except GithubException as exc:
        if _is_transient_github_error(exc):
            raise
    except Exception as exc:
        if _is_transient_github_error(exc):
            raise
        logger.debug("Rate limit check non-fatal exception: %s", exc)

    # 2. Top-Level Repository Fetch
    try:
        repo = gh.get_repo(full_name)
    except GithubException as exc:
        status = getattr(exc, "status", 0)
        if _is_transient_github_error(exc):
            raise
        if status in {404, 451}:
            return ActivityResult(
                activity=None,
                issues=[
                    ValidationIssue(
                        field="repository",
                        severity="error",
                        message=f"Repository '{full_name}' unavailable (HTTP {status}): {exc}",
                    )
                ],
            )
        if status == 403:
            return ActivityResult(
                activity=None,
                issues=[
                    ValidationIssue(
                        field="repository",
                        severity="error",
                        message=f"Access forbidden to repository '{full_name}' (403): {exc}",
                    )
                ],
            )
        return ActivityResult(
            activity=None,
            issues=[
                ValidationIssue(
                    field="repository",
                    severity="error",
                    message=f"Failed to fetch repository '{full_name}': {exc}",
                )
            ],
        )
    except Exception as exc:
        if _is_transient_github_error(exc):
            raise
        return ActivityResult(
            activity=None,
            issues=[
                ValidationIssue(
                    field="repository",
                    severity="error",
                    message=f"Unexpected error fetching repository '{full_name}': {exc}",
                )
            ],
        )

    # 3. Basic Metadata
    default_branch = repo.default_branch or "main"
    created_at = _to_utc(repo.created_at)
    pushed_at = _to_utc(repo.pushed_at)
    updated_at = _to_utc(repo.updated_at)
    stars = repo.stargazers_count if repo.stargazers_count is not None else 0
    forks = repo.forks_count if repo.forks_count is not None else 0

    # 4. Open Pull Requests & Issues (Open issues exclude PRs)
    open_prs = 0
    try:
        open_prs_list = repo.get_pulls(state="open")
        open_prs = open_prs_list.totalCount
    except Exception as exc:
        if _is_transient_github_error(exc):
            raise
        issues.append(
            ValidationIssue(
                field="open_prs",
                severity="warning",
                message=f"Failed to fetch open PR count: {exc}",
            )
        )

    # Note: GitHub repo.open_issues_count includes both PRs and issues.
    raw_open_issues_count = repo.open_issues_count if repo.open_issues_count is not None else 0
    open_issues = max(0, raw_open_issues_count - open_prs)

    # 5. Branch Protection Check
    default_branch_protected: bool | None = None
    try:
        branch = repo.get_branch(default_branch)
        default_branch_protected = bool(branch.protected)
    except Exception as exc:
        if _is_transient_github_error(exc):
            raise
        issues.append(
            ValidationIssue(
                field="default_branch_protected",
                severity="warning",
                message=f"Could not determine branch protection for '{default_branch}': {exc}",
            )
        )
        default_branch_protected = None

    # 6. Commits & Contributors in 90d window
    cutoff_90d = now - timedelta(days=window_days)
    cutoff_30d = now - timedelta(days=30)
    commits_30d = 0
    commits_90d = 0
    unique_contributors_90d = 0
    last_commit_at: datetime | None = None

    try:
        commit_paginator = repo.get_commits(since=cutoff_90d)
        fetched_commits = list(itertools.islice(commit_paginator, max_items + 1))
        if len(fetched_commits) > max_items:
            partial = True
            fetched_commits = fetched_commits[:max_items]
            issues.append(
                ValidationIssue(
                    field="commits_90d",
                    severity="warning",
                    message=f"Commit history truncated at {max_items} items.",
                )
            )

        commits_90d = len(fetched_commits)
        contributors_set: set[str] = set()

        for c in fetched_commits:
            c_dt = None
            if c.commit and c.commit.author and c.commit.author.date:
                c_dt = _to_utc(c.commit.author.date)

            if c_dt:
                if last_commit_at is None or c_dt > last_commit_at:
                    last_commit_at = c_dt
                if c_dt >= cutoff_30d:
                    commits_30d += 1

            author_id = None
            if c.author and getattr(c.author, "login", None):
                author_id = c.author.login
            elif c.commit and c.commit.author:
                author_id = c.commit.author.email or c.commit.author.name
            if author_id:
                contributors_set.add(author_id)

        unique_contributors_90d = len(contributors_set)
        if commits_90d > 0 and unique_contributors_90d == 0:
            unique_contributors_90d = 1

    except GithubException as exc:
        status = getattr(exc, "status", 0)
        if status == 409:
            # 409 Conflict indicates an empty Git repository
            commits_30d = 0
            commits_90d = 0
            unique_contributors_90d = 0
            last_commit_at = None
            issues.append(
                ValidationIssue(
                    field="commits",
                    severity="warning",
                    message="Repository is empty (HTTP 409 Conflict on commits).",
                )
            )
        elif _is_transient_github_error(exc):
            raise
        else:
            issues.append(
                ValidationIssue(
                    field="commits",
                    severity="warning",
                    message=f"Failed to fetch commits: {exc}",
                )
            )
    except Exception as exc:
        if _is_transient_github_error(exc):
            raise
        issues.append(
            ValidationIssue(
                field="commits",
                severity="warning",
                message=f"Failed to fetch commits: {exc}",
            )
        )

    # 7. Closed and Merged PRs in 30d window
    closed_prs_30d = 0
    merged_prs_30d = 0
    try:
        pull_paginator = repo.get_pulls(state="closed", sort="updated", direction="desc")
        fetched_pulls = []
        for pr in itertools.islice(pull_paginator, max_items + 1):
            fetched_pulls.append(pr)
            p_up = _to_utc(getattr(pr, "updated_at", None))
            if p_up and p_up < cutoff_30d:
                break

        if len(fetched_pulls) > max_items:
            partial = True
            fetched_pulls = fetched_pulls[:max_items]
            issues.append(
                ValidationIssue(
                    field="closed_prs_30d",
                    severity="warning",
                    message=f"Pull request history truncated at {max_items} items.",
                )
            )

        for pr in fetched_pulls:
            p_closed = _to_utc(getattr(pr, "closed_at", None))
            if p_closed and p_closed >= cutoff_30d:
                closed_prs_30d += 1
                if getattr(pr, "merged_at", None) is not None:
                    merged_prs_30d += 1

    except Exception as exc:
        if _is_transient_github_error(exc):
            raise
        issues.append(
            ValidationIssue(
                field="closed_prs_30d",
                severity="warning",
                message=f"Failed to fetch closed PRs: {exc}",
            )
        )

    # 8. Releases
    last_release_at: datetime | None = None
    latest_release_tag: str | None = None
    try:
        releases = repo.get_releases()
        first_release = list(itertools.islice(releases, 1))
        if first_release:
            rel = first_release[0]
            last_release_at = _to_utc(getattr(rel, "published_at", None) or getattr(rel, "created_at", None))
            latest_release_tag = getattr(rel, "tag_name", None)
    except GithubException as exc:
        status = getattr(exc, "status", 0)
        if status == 404:
            last_release_at = None
            latest_release_tag = None
        elif _is_transient_github_error(exc):
            raise
        else:
            issues.append(
                ValidationIssue(
                    field="releases",
                    severity="warning",
                    message=f"Failed to fetch releases: {exc}",
                )
            )
    except Exception as exc:
        if _is_transient_github_error(exc):
            raise
        issues.append(
            ValidationIssue(
                field="releases",
                severity="warning",
                message=f"Failed to fetch releases: {exc}",
            )
        )

    # 9. Stats Endpoints (Commit activity)
    try:
        commit_stats = repo.get_stats_commit_activity()
        if commit_stats is None:
            stats_pending = True
    except GithubException as exc:
        status = getattr(exc, "status", 0)
        if status == 202:
            stats_pending = True
        elif _is_transient_github_error(exc):
            raise
        else:
            issues.append(
                ValidationIssue(
                    field="stats",
                    severity="warning",
                    message=f"Failed to fetch stats: {exc}",
                )
            )
    except Exception as exc:
        if _is_transient_github_error(exc):
            raise
        issues.append(
            ValidationIssue(
                field="stats",
                severity="warning",
                message=f"Failed to fetch stats: {exc}",
            )
        )

    # 10. Assemble & Validate
    raw_activity = RepoActivity(
        full_name=full_name,
        github_repo_id=getattr(repo, "id", 0),
        default_branch=default_branch,
        is_archived=bool(getattr(repo, "archived", False)),
        is_fork=bool(getattr(repo, "fork", False)),
        is_disabled=bool(getattr(repo, "disabled", False)),
        created_at=created_at,
        pushed_at=pushed_at,
        updated_at=updated_at,
        stars=stars,
        forks=forks,
        open_issues=open_issues,
        open_prs=open_prs,
        closed_prs_30d=closed_prs_30d,
        merged_prs_30d=merged_prs_30d,
        commits_30d=commits_30d,
        commits_90d=commits_90d,
        unique_contributors_90d=unique_contributors_90d,
        last_commit_at=last_commit_at,
        last_release_at=last_release_at,
        latest_release_tag=latest_release_tag,
        default_branch_protected=default_branch_protected,
        fetched_at=now,
    )

    validated = validate_activity(raw_activity, now=now)
    all_issues = issues + validated.issues

    return ActivityResult(
        activity=validated.activity,
        issues=all_issues,
        partial=partial or validated.partial,
        stats_pending=stats_pending or validated.stats_pending,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Client Construction Helper
# ─────────────────────────────────────────────────────────────────────────────


def get_github_client_for_repo(repository: Any) -> Github:
    """
    Build an authenticated PyGithub client for a repository.

    Auth Preference:
    1. GitHub App authentication if GITHUB_APP_ID and GITHUB_PRIVATE_KEY_PATH
       are configured, exchanging the JWT for an installation token for the repo.
    2. Fallback to repository owner's allauth SocialToken.

    Uses `Github(auth=Auth.Token(token))` to ensure compatibility with PyGithub 2.5.0+.
    Raises RuntimeError if neither authentication method is available.
    """
    app_id = config("GITHUB_APP_ID", default="")
    private_key_path = config("GITHUB_PRIVATE_KEY_PATH", default="")

    if app_id and private_key_path:
        try:
            with open(private_key_path, "r", encoding="utf-8") as fh:
                private_key = fh.read()
            integration = GithubIntegration(
                integration_id=int(app_id),
                private_key=private_key,
            )
            install = integration.get_installation(
                repository.owner,
                repository.name,
            )
            token = integration.get_access_token(install.id).token
            logger.info("Using GitHub App auth for repo %s", getattr(repository, "full_name", ""))
            return Github(auth=Auth.Token(token))
        except Exception as exc:
            logger.warning(
                "GitHub App auth failed for %s: %s — falling back to user token.",
                getattr(repository, "full_name", ""),
                exc,
            )

    # Fallback to user's SocialToken
    from allauth.socialaccount.models import SocialToken

    user = getattr(repository, "user", None)
    token_obj = (
        SocialToken.objects.filter(
            account__user=user,
            account__provider="github",
        )
        .order_by("-expires_at")
        .first()
    )
    if not token_obj or not token_obj.token:
        raise RuntimeError(
            f"No GitHub token available for repository '{getattr(repository, 'full_name', '')}' "
            f"(user '{user}': App auth not configured and no OAuth token found)."
        )

    logger.info("Using user OAuth token for repo %s", getattr(repository, "full_name", ""))
    return Github(auth=Auth.Token(token_obj.token))
