"""
Tests for GitHub pull request synchronisation (reviews/pr_sync.py).

GitHub is faked and no review is ever executed or posted: queueing is patched.
"""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from repos.models import PullRequest, Repository
from reviews import pr_sync
from reviews.github_app import GitHubAccessError, RepoAccess
from reviews.models import Review
from reviews.pr_sync import review_snapshot, sync_all, sync_repository
from reviews.tests.gh_fakes import FakeClient, FakeRepo, PagedList, gh_pr

User = get_user_model()
pytestmark = pytest.mark.django_db

ACCESS = "reviews.pr_sync.client_for_repository"
QUEUE = "reviews.queueing.run_llm_review"


@pytest.fixture
def user():
    return User.objects.create_user(username="hemangi", password="x")


def connect(user, name, gh_id, **kw):
    return Repository.objects.create(user=user, github_repo_id=gh_id, owner="o", name=name, is_enabled=True, **kw)


def access_for(fake_repos, installation_id=77, mode="app", warning=""):
    """client_for_repository replacement: every repo gets the same fake client."""
    def _access(db_repo, **_):
        return RepoAccess(client=FakeClient(fake_repos), installation_id=installation_id, auth_mode=mode, warning=warning)
    return _access


# ── fetching from several repositories ──────────────────────────────────────
def test_syncs_prs_from_every_connected_repository(user):
    repos = [connect(user, f"repo{i}", i) for i in range(1, 7)]                      # the "six repositories"
    fakes = {r.full_name: FakeRepo([gh_pr(n) for n in range(1, i + 2)]) for i, r in enumerate(repos, 1)}
    with patch(ACCESS, side_effect=access_for(fakes)), patch(QUEUE):
        report = sync_all(repos)
    assert report["status"] == "ok" and report["totals"]["repositories"] == 6
    assert report["totals"]["found"] == sum(range(2, 8)) == 27
    for i, r in enumerate(repos, 1):
        assert PullRequest.objects.filter(repository=r).count() == i + 1
    assert [x["fetched"] for x in report["results"]] == [2, 3, 4, 5, 6, 7]


def test_follows_pagination_to_the_last_page(user):
    repo = connect(user, "big", 1)
    paged = PagedList([gh_pr(n) for n in range(1, 251)], per_page=100)             # 3 pages
    fake = FakeRepo(paged)
    with patch(ACCESS, side_effect=access_for({repo.full_name: fake})), patch(QUEUE):
        result = sync_repository(repo)
    assert result["fetched"] == 250 and paged.pages_fetched == 3
    assert PullRequest.objects.filter(repository=repo).count() == 250
    assert fake.get_pulls_kwargs["state"] == "open"


def test_stops_at_the_safety_cap_and_says_so(user):
    repo = connect(user, "huge", 1)
    fake = FakeRepo([gh_pr(n) for n in range(1, 31)])
    with patch(ACCESS, side_effect=access_for({repo.full_name: fake})), patch(QUEUE), patch.object(pr_sync, "MAX_PRS_PER_REPO", 20):
        result = sync_repository(repo)
    assert result["fetched"] == 20 and "Stopped at 20" in result["warning"]


# ── saving and updating ─────────────────────────────────────────────────────
def test_saves_every_field_of_a_pull_request(user):
    repo = connect(user, "r", 1)
    pr = gh_pr(5, title="Add login", body="Adds JWT login", login="mansi", sha="a" * 40, head_ref="feature/login", base_ref="develop", draft=True)
    with patch(ACCESS, side_effect=access_for({repo.full_name: FakeRepo([pr])}, installation_id=4242)), patch(QUEUE):
        sync_repository(repo)
    row = PullRequest.objects.get(repository=repo, number=5)
    assert (row.title, row.body, row.author, row.state) == ("Add login", "Adds JWT login", "mansi", "open")
    assert row.html_url == "https://github.com/o/r/pull/5"
    assert (row.latest_head_sha, row.source_branch, row.target_branch) == ("a" * 40, "feature/login", "develop")
    assert row.is_draft and row.installation_id == 4242 and row.github_pr_id == 9005
    assert row.last_synced_at is not None and row.sync_error == ""


def test_updates_existing_pull_requests_instead_of_duplicating(user):
    repo = connect(user, "r", 1)
    with patch(ACCESS, side_effect=access_for({repo.full_name: FakeRepo([gh_pr(1, title="Old", sha="a" * 40)])})), patch(QUEUE):
        first = sync_repository(repo)
    with patch(ACCESS, side_effect=access_for({repo.full_name: FakeRepo([gh_pr(1, title="New title", sha="b" * 40)])})), patch(QUEUE):
        second = sync_repository(repo)
    assert (first["created"], first["updated"]) == (1, 0) and (second["created"], second["updated"]) == (0, 1)
    row = PullRequest.objects.get(repository=repo)
    assert PullRequest.objects.filter(repository=repo).count() == 1
    assert (row.title, row.latest_head_sha) == ("New title", "b" * 40)


def test_pr_closed_or_merged_since_last_sync_is_refreshed(user):
    repo = connect(user, "r", 1)
    gone_merged = PullRequest.objects.create(repository=repo, number=8, title="m", author="a", latest_head_sha="c" * 40)
    gone_closed = PullRequest.objects.create(repository=repo, number=9, title="c", author="a", latest_head_sha="d" * 40)
    fake = FakeRepo([gh_pr(1)], other_prs=[gh_pr(8, state="closed", merged=True), gh_pr(9, state="closed")])
    with patch(ACCESS, side_effect=access_for({repo.full_name: fake})), patch(QUEUE):
        result = sync_repository(repo)
    assert result["refreshed"] == 2
    gone_merged.refresh_from_db(); gone_closed.refresh_from_db()
    assert (gone_merged.state, gone_closed.state) == ("merged", "closed")


# ── failures are reported, never silent ─────────────────────────────────────
def test_one_failing_repository_does_not_stop_the_others(user):
    good, no_app, missing = connect(user, "good", 1), connect(user, "noapp", 2), connect(user, "gone", 3)
    fakes = {good.full_name: FakeRepo([gh_pr(1)])}                                   # "gone" is not on GitHub

    def access(db_repo, **_):
        if db_repo.name == "noapp":
            raise GitHubAccessError("The GitHub App is not installed on o/noapp.")
        return RepoAccess(client=FakeClient(fakes), installation_id=5, auth_mode="app")

    with patch(ACCESS, side_effect=access), patch(QUEUE):
        report = sync_all([good, no_app, missing])
    by_name = {r["repository"]: r for r in report["results"]}
    assert report["status"] == "partial" and report["totals"]["failed"] == 2 and report["totals"]["succeeded"] == 1
    assert by_name["o/good"]["ok"] and by_name["o/good"]["fetched"] == 1
    assert "not installed" in by_name["o/noapp"]["error"]
    assert "404" in by_name["o/gone"]["error"] and "Not Found" in by_name["o/gone"]["error"]
    no_app.refresh_from_db()
    assert no_app.last_sync_status == "error" and "not installed" in no_app.last_sync_error
    good.refresh_from_db()
    assert good.last_sync_status == "ok" and good.last_sync_count == 1 and good.installation_id == 5


def test_unexpected_errors_are_caught_and_recorded(user):
    repo = connect(user, "r", 1)
    with patch(ACCESS, side_effect=RuntimeError("boom")):
        result = sync_repository(repo)
    assert not result["ok"] and "RuntimeError: boom" in result["error"]
    repo.refresh_from_db()
    assert repo.last_sync_status == "error" and repo.sync_started_at is None          # lock released


def test_every_repository_failing_reports_failed(user):
    repos = [connect(user, "a", 1), connect(user, "b", 2)]
    with patch(ACCESS, side_effect=GitHubAccessError("no credentials")):
        assert sync_all(repos)["status"] == "failed"


def test_oauth_fallback_is_flagged_in_the_report(user):
    repo = connect(user, "r", 1)
    fakes = {repo.full_name: FakeRepo([gh_pr(1)])}
    with patch(ACCESS, side_effect=access_for(fakes, mode="oauth", warning="The GitHub App is not installed on o/r.")), patch(QUEUE):
        report = sync_all([repo])
    assert report["results"][0]["auth_mode"] == "oauth"
    assert any("not installed" in w for w in report["warnings"])


# ── queueing reviews ────────────────────────────────────────────────────────
def test_queues_a_review_only_for_open_prs_without_one_for_the_current_commit(user):
    repo = connect(user, "r", 1)
    already = PullRequest.objects.create(repository=repo, number=2, title="t", author="a", latest_head_sha="2".zfill(40))
    Review.objects.create(pull_request=already, head_sha="2".zfill(40), status="completed")
    fake = FakeRepo([gh_pr(1), gh_pr(2)])
    with patch(ACCESS, side_effect=access_for({repo.full_name: fake}, installation_id=9)), patch(QUEUE) as task:
        result = sync_repository(repo)
    assert result["reviews_queued"] == 1 and task.delay.call_count == 1
    new = Review.objects.get(pull_request__number=1)
    assert (new.status, new.head_sha, new.installation_id) == ("pending", "1".zfill(40), 9)
    assert Review.objects.filter(pull_request=already).count() == 1


def test_a_second_sync_does_not_queue_duplicate_reviews(user):
    repo = connect(user, "r", 1)
    fakes = {repo.full_name: FakeRepo([gh_pr(1), gh_pr(2)])}
    with patch(ACCESS, side_effect=access_for(fakes)), patch(QUEUE) as task:
        first = sync_repository(repo)
        second = sync_repository(repo)
    assert first["reviews_queued"] == 2 and second["reviews_queued"] == 0 and second["reviews_retried"] == 0
    assert task.delay.call_count == 2 and Review.objects.count() == 2


def test_new_commit_gets_a_new_review_and_failed_reviews_are_retried(user):
    repo = connect(user, "r", 1)
    with patch(ACCESS, side_effect=access_for({repo.full_name: FakeRepo([gh_pr(1, sha="a" * 40), gh_pr(2)])})), patch(QUEUE):
        sync_repository(repo)
    Review.objects.filter(pull_request__number=2).update(status="failed", error_message="Gemini 429")
    with patch(ACCESS, side_effect=access_for({repo.full_name: FakeRepo([gh_pr(1, sha="b" * 40), gh_pr(2)])})), patch(QUEUE) as task:
        result = sync_repository(repo)
    assert result["reviews_queued"] == 1 and result["reviews_retried"] == 1 and task.delay.call_count == 2
    assert Review.objects.filter(pull_request__number=1).count() == 2                  # one per commit
    retried = Review.objects.get(pull_request__number=2)
    assert retried.status == "pending" and retried.error_message == ""


def test_pending_and_running_reviews_are_left_alone(user):
    repo = connect(user, "r", 1)
    fake = FakeRepo([gh_pr(1), gh_pr(2)])
    for n, st in ((1, "pending"), (2, "running")):
        pr = PullRequest.objects.create(repository=repo, number=n, title="t", author="a", latest_head_sha=str(n).zfill(40))
        Review.objects.create(pull_request=pr, head_sha=str(n).zfill(40), status=st)
    with patch(ACCESS, side_effect=access_for({repo.full_name: fake})), patch(QUEUE) as task:
        result = sync_repository(repo)
    assert result["reviews_queued"] == 0 and task.delay.call_count == 0


def test_sync_without_queueing_creates_no_reviews(user):
    repo = connect(user, "r", 1)
    with patch(ACCESS, side_effect=access_for({repo.full_name: FakeRepo([gh_pr(1)])})), patch(QUEUE) as task:
        report = sync_all([repo], queue_reviews=False)
    assert Review.objects.count() == 0 and task.delay.call_count == 0 and report["celery"] is None


def test_closed_pull_requests_are_stored_but_never_queued(user):
    repo = connect(user, "r", 1)
    fake = FakeRepo([gh_pr(1)], other_prs=[])
    PullRequest.objects.create(repository=repo, number=3, title="t", author="a", latest_head_sha="3".zfill(40), state="closed")
    with patch(ACCESS, side_effect=access_for({repo.full_name: fake})), patch(QUEUE) as task:
        sync_repository(repo)
    assert task.delay.call_count == 1 and not Review.objects.filter(pull_request__number=3).exists()


def test_redis_down_is_reported_and_marks_the_review_failed(user):
    repo = connect(user, "r", 1)
    with patch(ACCESS, side_effect=access_for({repo.full_name: FakeRepo([gh_pr(1)])})), patch(QUEUE) as task:
        task.delay.side_effect = ConnectionError("Error 10061 connecting to localhost:6379")
        result = sync_repository(repo)
    assert result["ok"] and "Redis" in result["queue_error"]
    review = Review.objects.get()
    assert review.status == "failed" and "Is Redis running?" in review.error_message


# ── locking: repeated clicks ────────────────────────────────────────────────
def test_a_running_sync_blocks_a_second_one(user):
    repo = connect(user, "r", 1)
    Repository.objects.filter(pk=repo.pk).update(last_sync_status="syncing", sync_started_at=timezone.now())
    repo.refresh_from_db()
    with patch(ACCESS) as access:
        result = sync_repository(repo)
        report = sync_all([repo])
    assert result["skipped"] and "already running" in result["warning"]
    assert report["status"] == "busy" and access.call_count == 0 and Review.objects.count() == 0


def test_a_stale_lock_is_taken_over_and_released_afterwards(user):
    repo = connect(user, "r", 1)
    Repository.objects.filter(pk=repo.pk).update(last_sync_status="syncing", sync_started_at=timezone.now() - timedelta(minutes=30))
    repo.refresh_from_db()
    with patch(ACCESS, side_effect=access_for({repo.full_name: FakeRepo([gh_pr(1)])})), patch(QUEUE):
        result = sync_repository(repo)
    assert result["ok"] and not result["skipped"]
    repo.refresh_from_db()
    assert repo.last_sync_status == "ok" and repo.sync_started_at is None


# ── status snapshot ─────────────────────────────────────────────────────────
def test_review_snapshot_counts_the_current_commit_only(user):
    repo = connect(user, "r", 1)
    for n, status in ((1, "completed"), (2, "failed"), (3, "pending"), (4, "running"), (5, None)):
        pr = PullRequest.objects.create(repository=repo, number=n, title="t", author="a", latest_head_sha=str(n).zfill(40))
        if status:
            Review.objects.create(pull_request=pr, head_sha=str(n).zfill(40), status=status)
    old_commit = PullRequest.objects.get(number=5)
    Review.objects.create(pull_request=old_commit, head_sha="f" * 40, status="completed")   # review of an older commit
    PullRequest.objects.create(repository=repo, number=6, title="t", author="a", latest_head_sha="6".zfill(40), state="closed")
    assert review_snapshot([repo]) == {"open_prs": 5, "not_reviewed": 1, "pending": 1, "processing": 1, "completed": 1, "failed": 1}
