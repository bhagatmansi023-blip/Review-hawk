"""
reviews/tests/test_github_activity.py
=====================================
Unit tests for the GitHub activity data collection layer and validation.

All PyGithub API interactions are mocked using unittest.mock.
No real network calls or tokens are used.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from github import Auth, GithubException

from reviews.github_activity import (
    ActivityResult,
    RepoActivity,
    ValidationIssue,
    _is_rate_limit_error,
    _is_transient,
    _to_utc,
    fetch_repo_activity,
    get_github_client_for_repo,
    validate_activity,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures & Mock Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_mock_commit(author_login="octocat", date=None, email="octocat@github.com"):
    """Helper to produce a mock PyGithub Commit."""
    commit_mock = MagicMock()
    commit_mock.author = MagicMock()
    commit_mock.author.login = author_login
    commit_mock.commit = MagicMock()
    commit_mock.commit.author = MagicMock()
    commit_mock.commit.author.date = date or datetime.now(timezone.utc)
    commit_mock.commit.author.email = email
    commit_mock.commit.author.name = "Octo Cat"
    return commit_mock


def _make_mock_pull(closed_at=None, updated_at=None, merged=False):
    """Helper to produce a mock PyGithub PullRequest."""
    pr_mock = MagicMock()
    pr_mock.closed_at = closed_at
    pr_mock.updated_at = updated_at or closed_at or datetime.now(timezone.utc)
    pr_mock.merged_at = datetime.now(timezone.utc) if merged else None
    return pr_mock


def _make_mock_release(tag_name="v1.0.0", published_at=None):
    """Helper to produce a mock PyGithub GitRelease."""
    rel_mock = MagicMock()
    rel_mock.tag_name = tag_name
    rel_mock.published_at = published_at or datetime.now(timezone.utc)
    rel_mock.created_at = rel_mock.published_at
    return rel_mock


def _build_mock_github(
    *,
    remaining_rate_limit: int = 5000,
    repo_raises: Exception | None = None,
    commits: list | None = None,
    commits_raises: Exception | None = None,
    closed_pulls: list | None = None,
    closed_pulls_raises: Exception | None = None,
    open_prs_count: int = 2,
    open_issues_count: int = 10,
    branch_protected: bool = True,
    branch_raises: Exception | None = None,
    releases: list | None = None,
    releases_raises: Exception | None = None,
    commit_stats=None,
    commit_stats_raises: Exception | None = None,
    archived: bool = False,
    disabled: bool = False,
    fork: bool = False,
) -> tuple[MagicMock, MagicMock]:
    """Assemble a mocked PyGithub Github client and Repository."""
    gh = MagicMock()

    # Rate limit
    rate_mock = MagicMock()
    rate_mock.core.remaining = remaining_rate_limit
    gh.get_rate_limit.return_value = rate_mock

    if repo_raises:
        gh.get_repo.side_effect = repo_raises
        return gh, None

    repo = MagicMock()
    gh.get_repo.return_value = repo

    repo.id = 123456
    repo.default_branch = "main"
    repo.archived = archived
    repo.disabled = disabled
    repo.fork = fork
    now = datetime.now(timezone.utc)
    repo.created_at = now - timedelta(days=200)
    repo.pushed_at = now - timedelta(days=1)
    repo.updated_at = now - timedelta(hours=2)
    repo.stargazers_count = 42
    repo.forks_count = 7
    repo.open_issues_count = open_issues_count

    # Open PRs
    open_pulls_mock = MagicMock()
    open_pulls_mock.totalCount = open_prs_count
    repo.get_pulls.side_effect = lambda state=None, **kwargs: (
        open_pulls_mock if state == "open" else (
            (closed_pulls_raises if closed_pulls_raises else closed_pulls)
            if closed_pulls is not None or closed_pulls_raises else []
        )
    )

    # Commits
    if commits_raises:
        repo.get_commits.side_effect = commits_raises
    else:
        repo.get_commits.return_value = iter(commits if commits is not None else [])

    # Closed PRs
    if closed_pulls_raises:
        def pulls_side_effect(state=None, **kwargs):
            if state == "open":
                return open_pulls_mock
            raise closed_pulls_raises
        repo.get_pulls.side_effect = pulls_side_effect
    elif closed_pulls is not None:
        def pulls_side_effect(state=None, **kwargs):
            if state == "open":
                return open_pulls_mock
            return iter(closed_pulls)
        repo.get_pulls.side_effect = pulls_side_effect

    # Branch protection
    if branch_raises:
        repo.get_branch.side_effect = branch_raises
    else:
        branch_mock = MagicMock()
        branch_mock.protected = branch_protected
        repo.get_branch.return_value = branch_mock

    # Releases
    if releases_raises:
        repo.get_releases.side_effect = releases_raises
    else:
        repo.get_releases.return_value = iter(releases if releases is not None else [])

    # Stats
    if commit_stats_raises:
        repo.get_stats_commit_activity.side_effect = commit_stats_raises
    else:
        repo.get_stats_commit_activity.return_value = commit_stats

    return gh, repo


# ─────────────────────────────────────────────────────────────────────────────
# Pure Validation Tests (validate_activity)
# ─────────────────────────────────────────────────────────────────────────────


def test_validate_activity_happy_path():
    """Clean, consistent activity passes validation with zero issues."""
    now = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    raw = RepoActivity(
        full_name="org/repo",
        github_repo_id=101,
        default_branch="main",
        is_archived=False,
        is_fork=False,
        is_disabled=False,
        created_at=now - timedelta(days=100),
        pushed_at=now - timedelta(days=1),
        updated_at=now - timedelta(hours=1),
        stars=50,
        forks=10,
        open_issues=8,
        open_prs=2,
        closed_prs_30d=5,
        merged_prs_30d=3,
        commits_30d=15,
        commits_90d=45,
        unique_contributors_90d=4,
        last_commit_at=now - timedelta(hours=2),
        last_release_at=now - timedelta(days=10),
        latest_release_tag="v1.2.0",
        default_branch_protected=True,
        fetched_at=now,
    )

    result = validate_activity(raw, now=now)
    assert result.activity is not None
    assert len(result.issues) == 0
    assert result.activity.full_name == "org/repo"
    assert result.activity.commits_30d == 15
    assert result.activity.merged_prs_30d == 3
    assert result.activity.default_branch_protected is True


def test_validate_activity_naive_datetimes_normalised():
    """Naive datetimes are converted to timezone-aware UTC."""
    now = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    naive_dt = datetime(2026, 1, 1, 10, 0, 0)  # no tzinfo

    raw = RepoActivity(
        full_name="owner/project",
        github_repo_id=1,
        default_branch="main",
        is_archived=False,
        is_fork=False,
        is_disabled=False,
        created_at=naive_dt,
        pushed_at=naive_dt,
        updated_at=naive_dt,
        stars=0,
        forks=0,
        open_issues=0,
        open_prs=0,
        closed_prs_30d=0,
        merged_prs_30d=0,
        commits_30d=0,
        commits_90d=0,
        unique_contributors_90d=0,
        last_commit_at=naive_dt,
        last_release_at=naive_dt,
        latest_release_tag=None,
        default_branch_protected=None,
        fetched_at=naive_dt,
    )

    result = validate_activity(raw, now=now)
    act = result.activity
    assert act is not None
    assert act.created_at.tzinfo == timezone.utc
    assert act.pushed_at.tzinfo == timezone.utc
    assert act.updated_at.tzinfo == timezone.utc
    assert act.last_commit_at.tzinfo == timezone.utc
    assert act.last_release_at.tzinfo == timezone.utc
    assert act.fetched_at.tzinfo == timezone.utc


def test_validate_activity_future_timestamp_nulled():
    """Timestamps in the future (> 5 min skew) are flagged as warnings and nulled."""
    now = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    far_future = now + timedelta(days=10)

    raw = RepoActivity(
        full_name="owner/repo",
        github_repo_id=1,
        default_branch="main",
        is_archived=False,
        is_fork=False,
        is_disabled=False,
        created_at=far_future,
        pushed_at=now,
        updated_at=far_future,
        stars=0,
        forks=0,
        open_issues=0,
        open_prs=0,
        closed_prs_30d=0,
        merged_prs_30d=0,
        commits_30d=0,
        commits_90d=0,
        unique_contributors_90d=0,
        last_commit_at=far_future,
        last_release_at=far_future,
        latest_release_tag="v1.0.0",
        default_branch_protected=None,
        fetched_at=now,
    )

    result = validate_activity(raw, now=now)
    act = result.activity
    assert act.created_at is None
    assert act.updated_at is None
    assert act.last_commit_at is None
    assert act.last_release_at is None
    warning_fields = {i.field for i in result.issues if i.severity == "warning"}
    assert "created_at" in warning_fields
    assert "updated_at" in warning_fields
    assert "last_commit_at" in warning_fields
    assert "last_release_at" in warning_fields


def test_validate_activity_clock_skew_allowed():
    """Timestamps within 5 minutes of future are tolerated (clock skew)."""
    now = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    skew_dt = now + timedelta(minutes=3)

    raw = RepoActivity(
        full_name="owner/repo",
        github_repo_id=1,
        default_branch="main",
        is_archived=False,
        is_fork=False,
        is_disabled=False,
        created_at=now - timedelta(days=10),
        pushed_at=skew_dt,
        updated_at=now,
        stars=0,
        forks=0,
        open_issues=0,
        open_prs=0,
        closed_prs_30d=0,
        merged_prs_30d=0,
        commits_30d=0,
        commits_90d=0,
        unique_contributors_90d=0,
        last_commit_at=skew_dt,
        last_release_at=None,
        latest_release_tag=None,
        default_branch_protected=None,
        fetched_at=now,
    )

    result = validate_activity(raw, now=now)
    assert result.activity.pushed_at == skew_dt
    assert result.activity.last_commit_at == skew_dt
    assert len(result.issues) == 0


def test_validate_activity_pushed_before_created_nulled():
    """If pushed_at strictly precedes created_at (>5 min), pushed_at is nulled."""
    now = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    created_at = now - timedelta(days=10)
    pushed_at = now - timedelta(days=20)  # 10 days before creation

    raw = RepoActivity(
        full_name="owner/repo",
        github_repo_id=1,
        default_branch="main",
        is_archived=False,
        is_fork=False,
        is_disabled=False,
        created_at=created_at,
        pushed_at=pushed_at,
        updated_at=now,
        stars=0,
        forks=0,
        open_issues=0,
        open_prs=0,
        closed_prs_30d=0,
        merged_prs_30d=0,
        commits_30d=0,
        commits_90d=0,
        unique_contributors_90d=0,
        last_commit_at=None,
        last_release_at=None,
        latest_release_tag=None,
        default_branch_protected=None,
        fetched_at=now,
    )

    result = validate_activity(raw, now=now)
    assert result.activity.pushed_at is None
    pushed_issues = [i for i in result.issues if i.field == "pushed_at"]
    assert len(pushed_issues) == 1
    assert pushed_issues[0].severity == "warning"


def test_validate_activity_negative_and_none_counts():
    """Negative counts are clamped to 0 with warnings; None counts coerced to 0."""
    now = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    raw = RepoActivity(
        full_name="owner/repo",
        github_repo_id=1,
        default_branch="main",
        is_archived=False,
        is_fork=False,
        is_disabled=False,
        created_at=now,
        pushed_at=now,
        updated_at=now,
        stars=-5,  # negative
        forks=None,  # none
        open_issues=-1,  # negative
        open_prs=None,
        closed_prs_30d=-2,
        merged_prs_30d=0,
        commits_30d=0,
        commits_90d=0,
        unique_contributors_90d=0,
        last_commit_at=None,
        last_release_at=None,
        latest_release_tag=None,
        default_branch_protected=None,  # honest unknown preserved
        fetched_at=now,
    )

    result = validate_activity(raw, now=now)
    act = result.activity
    assert act.stars == 0
    assert act.forks == 0
    assert act.open_issues == 0
    assert act.open_prs == 0
    assert act.closed_prs_30d == 0
    assert act.default_branch_protected is None  # preserved

    warning_fields = {i.field for i in result.issues if i.severity == "warning"}
    assert "stars" in warning_fields
    assert "open_issues" in warning_fields
    assert "closed_prs_30d" in warning_fields


def test_validate_activity_logical_inconsistencies_clamped():
    """Logical invariants: contributors <= commits, 30d commits <= 90d commits, merged <= closed."""
    now = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    raw = RepoActivity(
        full_name="owner/repo",
        github_repo_id=1,
        default_branch="main",
        is_archived=False,
        is_fork=False,
        is_disabled=False,
        created_at=now,
        pushed_at=now,
        updated_at=now,
        stars=0,
        forks=0,
        open_issues=0,
        open_prs=0,
        closed_prs_30d=2,
        merged_prs_30d=5,  # merged > closed
        commits_30d=20,  # 30d > 90d
        commits_90d=10,
        unique_contributors_90d=15,  # contributors > 90d commits
        last_commit_at=None,
        last_release_at=None,
        latest_release_tag=None,
        default_branch_protected=None,
        fetched_at=now,
    )

    result = validate_activity(raw, now=now)
    act = result.activity
    assert act.commits_30d == 10  # clamped to commits_90d
    assert act.unique_contributors_90d == 10  # clamped to commits_90d
    assert act.merged_prs_30d == 2  # clamped to closed_prs_30d

    fields = {i.field for i in result.issues}
    assert "commits_30d" in fields
    assert "unique_contributors_90d" in fields
    assert "merged_prs_30d" in fields


def test_validate_activity_invalid_name_and_empty_default_branch():
    """Invalid full_name generates an error; empty default_branch defaults to 'main'."""
    now = datetime.now(timezone.utc)
    raw = RepoActivity(
        full_name="invalid-name-without-slash",
        github_repo_id=1,
        default_branch="   ",
        is_archived=False,
        is_fork=False,
        is_disabled=False,
        created_at=now,
        pushed_at=now,
        updated_at=now,
        stars=0,
        forks=0,
        open_issues=0,
        open_prs=0,
        closed_prs_30d=0,
        merged_prs_30d=0,
        commits_30d=0,
        commits_90d=0,
        unique_contributors_90d=0,
        last_commit_at=None,
        last_release_at=None,
        latest_release_tag=None,
        default_branch_protected=None,
        fetched_at=now,
    )

    result = validate_activity(raw, now=now)
    assert result.activity.default_branch == "main"

    errors = [i for i in result.issues if i.severity == "error"]
    warnings = [i for i in result.issues if i.severity == "warning"]
    assert any(e.field == "full_name" for e in errors)
    assert any(w.field == "default_branch" for w in warnings)


def test_to_dict_serialization():
    """RepoActivity, ValidationIssue, and ActivityResult serialize cleanly to JSON-compatible dict."""
    now = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    raw = RepoActivity(
        full_name="owner/repo",
        github_repo_id=1,
        default_branch="main",
        is_archived=False,
        is_fork=False,
        is_disabled=False,
        created_at=now,
        pushed_at=now,
        updated_at=now,
        stars=10,
        forks=2,
        open_issues=5,
        open_prs=1,
        closed_prs_30d=3,
        merged_prs_30d=2,
        commits_30d=5,
        commits_90d=15,
        unique_contributors_90d=2,
        last_commit_at=now,
        last_release_at=now,
        latest_release_tag="v1.0.0",
        default_branch_protected=True,
        fetched_at=now,
    )

    issue = ValidationIssue(field="commits", severity="warning", message="Truncated")
    result = ActivityResult(activity=raw, issues=[issue], partial=True, stats_pending=False)

    data = result.to_dict()
    assert data["partial"] is True
    assert data["stats_pending"] is False
    assert data["activity"]["full_name"] == "owner/repo"
    assert data["activity"]["created_at"] == now.isoformat()
    assert data["issues"][0]["field"] == "commits"
    assert data["issues"][0]["severity"] == "warning"


# ─────────────────────────────────────────────────────────────────────────────
# PyGithub Fetch Tests (fetch_repo_activity)
# ─────────────────────────────────────────────────────────────────────────────


def test_fetch_repo_activity_happy_path():
    """Happy path: all sub-calls succeed and populate clean RepoActivity."""
    now = datetime.now(timezone.utc)
    commits = [
        _make_mock_commit("alice", now - timedelta(days=5)),
        _make_mock_commit("bob", now - timedelta(days=20)),
        _make_mock_commit("alice", now - timedelta(days=60)),
    ]
    closed_prs = [
        _make_mock_pull(closed_at=now - timedelta(days=10), merged=True),
        _make_mock_pull(closed_at=now - timedelta(days=25), merged=False),
    ]
    releases = [_make_mock_release(tag_name="v2.1.0", published_at=now - timedelta(days=12))]

    gh, _ = _build_mock_github(
        commits=commits,
        closed_pulls=closed_prs,
        releases=releases,
        open_prs_count=3,
        open_issues_count=13,  # GitHub total (PRs + issues) -> real open issues = 10
        commit_stats=[{"total": 5}],
    )

    res = fetch_repo_activity(gh, "test-owner/test-repo")
    assert res.activity is not None
    act = res.activity
    assert act.full_name == "test-owner/test-repo"
    assert act.commits_90d == 3
    assert act.commits_30d == 2
    assert act.unique_contributors_90d == 2
    assert act.closed_prs_30d == 2
    assert act.merged_prs_30d == 1
    assert act.open_prs == 3
    assert act.open_issues == 10  # 13 total - 3 open PRs = 10 real issues
    assert act.latest_release_tag == "v2.1.0"
    assert act.default_branch_protected is True
    assert res.partial is False
    assert res.stats_pending is False


def test_fetch_repo_activity_open_issues_never_negative():
    """If open_issues_count is smaller than open_prs (edge case), open_issues clamps to 0."""
    gh, _ = _build_mock_github(
        open_prs_count=10,
        open_issues_count=8,  # Edge case where reported issues < open PRs
    )

    res = fetch_repo_activity(gh, "owner/repo")
    assert res.activity is not None
    assert res.activity.open_prs == 10
    assert res.activity.open_issues == 0


def test_fetch_repo_activity_409_empty_repo():
    """Empty repo (commits endpoint raises 409) is handled gracefully with 0 commits."""
    exc_409 = GithubException(status=409, data={"message": "Git Repository is empty."}, headers={})
    gh, _ = _build_mock_github(commits_raises=exc_409)

    res = fetch_repo_activity(gh, "owner/empty-repo")
    assert res.activity is not None
    assert res.activity.commits_90d == 0
    assert res.activity.commits_30d == 0
    assert res.activity.unique_contributors_90d == 0
    assert res.activity.last_commit_at is None
    warning_fields = [i.field for i in res.issues if i.severity == "warning"]
    assert "commits" in warning_fields


def test_fetch_repo_activity_404_repo_not_found():
    """404 Not Found returns activity=None with error issue."""
    exc_404 = GithubException(status=404, data={"message": "Not Found"}, headers={})
    gh, _ = _build_mock_github(repo_raises=exc_404)

    res = fetch_repo_activity(gh, "owner/nonexistent")
    assert res.activity is None
    assert len(res.issues) == 1
    assert res.issues[0].severity == "error"
    assert res.issues[0].field == "repository"


def test_fetch_repo_activity_403_no_access():
    """403 Forbidden (permission denied, non-rate-limit) returns activity=None with error issue."""
    exc_403 = GithubException(
        status=403,
        data={"message": "Resource not accessible by integration"},
        headers={"x-ratelimit-remaining": "4950"},
    )
    gh, _ = _build_mock_github(repo_raises=exc_403)

    res = fetch_repo_activity(gh, "owner/private-no-access")
    assert res.activity is None
    assert len(res.issues) == 1
    assert res.issues[0].severity == "error"
    assert "forbidden" in res.issues[0].message.lower()


def test_fetch_repo_activity_403_rate_limit_re_raised():
    """403 rate-limit error is re-raised and classified as transient by _is_transient."""
    exc_rate = GithubException(
        status=403,
        data={"message": "API rate limit exceeded for user"},
        headers={"x-ratelimit-remaining": "0"},
    )
    gh, _ = _build_mock_github(repo_raises=exc_rate)

    assert _is_rate_limit_error(exc_rate) is True
    assert _is_transient(exc_rate) is True

    with pytest.raises(GithubException) as excinfo:
        fetch_repo_activity(gh, "owner/rate-limited")
    assert excinfo.value.status == 403


def test_fetch_repo_activity_rate_limit_pre_check_exhausted():
    """When gh.get_rate_limit() reports < 10 remaining quota, fetch is aborted immediately."""
    gh, _ = _build_mock_github(remaining_rate_limit=5)

    with pytest.raises(GithubException) as excinfo:
        fetch_repo_activity(gh, "owner/near-exhausted")
    assert excinfo.value.status == 403
    assert _is_transient(excinfo.value) is True


def test_fetch_repo_activity_stats_202_pending():
    """When stats endpoint returns None (202 computing), stats_pending is True."""
    gh, _ = _build_mock_github(commit_stats=None)

    res = fetch_repo_activity(gh, "owner/computing-stats")
    assert res.activity is not None
    assert res.stats_pending is True


def test_fetch_repo_activity_stats_202_exception_pending():
    """When stats endpoint raises GithubException with status 202, stats_pending is True."""
    exc_202 = GithubException(status=202, data={"message": "Computing"}, headers={})
    gh, _ = _build_mock_github(commit_stats_raises=exc_202)

    res = fetch_repo_activity(gh, "owner/computing-stats-202")
    assert res.activity is not None
    assert res.stats_pending is True


def test_fetch_repo_activity_subcall_isolation_branch_protection_failed():
    """Failure in get_branch (403/404) records warning, default_branch_protected is None, rest succeeds."""
    exc_branch = GithubException(
        status=403,
        data={"message": "Must have admin rights to Repository"},
        headers={"x-ratelimit-remaining": "4800"},
    )
    gh, _ = _build_mock_github(branch_raises=exc_branch)

    res = fetch_repo_activity(gh, "owner/read-only-branch")
    assert res.activity is not None
    assert res.activity.default_branch_protected is None
    warning_fields = [i.field for i in res.issues if i.severity == "warning"]
    assert "default_branch_protected" in warning_fields


def test_fetch_repo_activity_subcall_isolation_releases_failed():
    """Failure in get_releases (404 / 500) leaves release fields None without failing fetch."""
    exc_releases = GithubException(status=404, data={"message": "Not Found"}, headers={})
    gh, _ = _build_mock_github(releases_raises=exc_releases)

    res = fetch_repo_activity(gh, "owner/no-releases")
    assert res.activity is not None
    assert res.activity.last_release_at is None
    assert res.activity.latest_release_tag is None


def test_fetch_repo_activity_max_items_truncation():
    """When items exceed max_items, partial is set to True and warning is logged."""
    now = datetime.now(timezone.utc)
    # 5 commits with max_items=3
    commits = [_make_mock_commit(f"user_{i}", now - timedelta(days=i)) for i in range(5)]
    gh, _ = _build_mock_github(commits=commits)

    res = fetch_repo_activity(gh, "owner/busy-repo", max_items=3)
    assert res.activity is not None
    assert res.partial is True
    assert res.activity.commits_90d == 3
    warning_fields = [i.field for i in res.issues if i.severity == "warning"]
    assert "commits_90d" in warning_fields


def test_fetch_repo_activity_archived_and_disabled():
    """Archived and disabled repo flags are faithfully captured."""
    gh, _ = _build_mock_github(archived=True, disabled=True, fork=True)

    res = fetch_repo_activity(gh, "owner/archived-fork")
    assert res.activity is not None
    assert res.activity.is_archived is True
    assert res.activity.is_disabled is True
    assert res.activity.is_fork is True


# ─────────────────────────────────────────────────────────────────────────────
# Client Construction Helper Tests (get_github_client_for_repo)
# ─────────────────────────────────────────────────────────────────────────────


def test_get_github_client_for_repo_app_auth(monkeypatch, tmp_path):
    """When GitHub App credentials are configured, exchanges JWT for installation token."""
    pem_file = tmp_path / "test_private_key.pem"
    pem_file.write_text("FAKE_PEM_KEY", encoding="utf-8")

    monkeypatch.setattr("reviews.github_activity.config", lambda k, default="": {
        "GITHUB_APP_ID": "12345",
        "GITHUB_PRIVATE_KEY_PATH": str(pem_file),
    }.get(k, default))

    mock_repo_model = MagicMock()
    mock_repo_model.owner = "test-owner"
    mock_repo_model.name = "test-repo"
    mock_repo_model.full_name = "test-owner/test-repo"

    with patch("reviews.github_activity.GithubIntegration") as mock_integration_cls, \
         patch("reviews.github_activity.Github") as mock_github_cls:

        mock_integration = mock_integration_cls.return_value
        mock_install = MagicMock()
        mock_install.id = 999
        mock_integration.get_installation.return_value = mock_install
        mock_access_token = MagicMock()
        mock_access_token.token = "ghs_installation_token_abc"
        mock_integration.get_access_token.return_value = mock_access_token

        client = get_github_client_for_repo(mock_repo_model)

        mock_integration_cls.assert_called_once_with(
            integration_id=12345,
            private_key="FAKE_PEM_KEY",
        )
        mock_integration.get_installation.assert_called_once_with("test-owner", "test-repo")
        mock_integration.get_access_token.assert_called_once_with(999)

        # Ensure Auth.Token was passed to Github
        mock_github_cls.assert_called_once()
        call_kwargs = mock_github_cls.call_args.kwargs
        assert "auth" in call_kwargs
        assert isinstance(call_kwargs["auth"], Auth.Token)
        assert client == mock_github_cls.return_value


def test_get_github_client_for_repo_oauth_fallback(monkeypatch):
    """When App auth is not configured, falls back to owner's allauth SocialToken."""
    monkeypatch.setattr("reviews.github_activity.config", lambda k, default="": "")

    mock_user = MagicMock()
    mock_repo_model = MagicMock()
    mock_repo_model.owner = "test-owner"
    mock_repo_model.name = "test-repo"
    mock_repo_model.full_name = "test-owner/test-repo"
    mock_repo_model.user = mock_user

    mock_token = MagicMock()
    mock_token.token = "gho_user_oauth_token_xyz"

    mock_queryset = MagicMock()
    mock_queryset.order_by.return_value.first.return_value = mock_token

    with patch("allauth.socialaccount.models.SocialToken.objects.filter", return_value=mock_queryset), \
         patch("reviews.github_activity.Github") as mock_github_cls:

        client = get_github_client_for_repo(mock_repo_model)

        mock_github_cls.assert_called_once()
        call_kwargs = mock_github_cls.call_args.kwargs
        assert "auth" in call_kwargs
        assert isinstance(call_kwargs["auth"], Auth.Token)
        assert client == mock_github_cls.return_value


def test_get_github_client_for_repo_no_token_raises_runtime_error(monkeypatch):
    """When neither App auth nor OAuth token is available, raises RuntimeError."""
    monkeypatch.setattr("reviews.github_activity.config", lambda k, default="": "")

    mock_repo_model = MagicMock()
    mock_repo_model.owner = "test-owner"
    mock_repo_model.name = "test-repo"
    mock_repo_model.full_name = "test-owner/test-repo"
    mock_repo_model.user = MagicMock()

    mock_queryset = MagicMock()
    mock_queryset.order_by.return_value.first.return_value = None

    with patch("allauth.socialaccount.models.SocialToken.objects.filter", return_value=mock_queryset):
        with pytest.raises(RuntimeError) as excinfo:
            get_github_client_for_repo(mock_repo_model)
        assert "No GitHub token available" in str(excinfo.value)

