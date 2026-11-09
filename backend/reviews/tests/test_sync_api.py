"""
Tests for the manual synchronisation endpoints and for the dashboard API returning real PRs
and their analysis. GitHub and Celery are mocked; nothing is posted anywhere.
"""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from repos.models import PullRequest, Repository
from reviews.github_app import GitHubAccessError, RepoAccess
from reviews.models import Review, ReviewComment
from reviews.tests.gh_fakes import FakeClient, FakeRepo, gh_pr

User = get_user_model()
pytestmark = pytest.mark.django_db
ACCESS = "reviews.pr_sync.client_for_repository"
QUEUE = "reviews.queueing.run_llm_review"


@pytest.fixture
def world():
    me = User.objects.create_user(username="me", password="x")
    other = User.objects.create_user(username="other", password="x")
    repos = [Repository.objects.create(user=me, github_repo_id=i, owner="me", name=f"app{i}", is_enabled=True) for i in (1, 2, 3)]
    theirs = Repository.objects.create(user=other, github_repo_id=99, owner="other", name="private", is_enabled=True)
    client = APIClient()
    client.force_authenticate(me)
    return type("W", (), {"me": me, "repos": repos, "theirs": theirs, "client": client})


def access_for(fakes, installation_id=5):
    def _access(db_repo, **_):
        if db_repo.full_name not in fakes:
            raise GitHubAccessError(f"The GitHub App is not installed on {db_repo.full_name}.")
        return RepoAccess(client=FakeClient({db_repo.full_name: fakes[db_repo.full_name]}), installation_id=installation_id, auth_mode="app")
    return _access


# ── POST /api/sync/ ─────────────────────────────────────────────────────────
def test_sync_all_fetches_every_connected_repo_and_reports_counts(world):
    fakes = {r.full_name: FakeRepo([gh_pr(n) for n in range(1, i + 2)]) for i, r in enumerate(world.repos, 1)}
    with patch(ACCESS, side_effect=access_for(fakes)), patch(QUEUE) as task:
        res = world.client.post("/api/sync/", {}, format="json")
    body = res.json()
    assert res.status_code == 200 and body["status"] == "ok"
    assert body["totals"] == {"repositories": 3, "succeeded": 3, "failed": 0, "skipped": 0,
                              "found": 9, "created": 9, "updated": 0, "queued": 9}
    assert task.delay.call_count == 9
    assert body["reviews"] == {"open_prs": 9, "not_reviewed": 0, "pending": 9, "processing": 0, "completed": 0, "failed": 0}
    assert {r["repository"] for r in body["results"]} == {r.full_name for r in world.repos}
    assert body["celery"] is not None
    assert not PullRequest.objects.filter(repository=world.theirs).exists()          # other users' repos untouched


def test_sync_all_can_skip_queueing_reviews(world):
    fakes = {r.full_name: FakeRepo([gh_pr(1)]) for r in world.repos}
    with patch(ACCESS, side_effect=access_for(fakes)), patch(QUEUE) as task:
        body = world.client.post("/api/sync/", {"review": False}, format="json").json()
    assert body["totals"]["found"] == 3 and body["totals"]["queued"] == 0 and task.delay.call_count == 0


def test_partial_failure_is_reported_per_repository(world):
    fakes = {world.repos[0].full_name: FakeRepo([gh_pr(1)])}                         # the other two are not installed
    with patch(ACCESS, side_effect=access_for(fakes)), patch(QUEUE):
        body = world.client.post("/api/sync/", {}, format="json").json()
    assert body["status"] == "partial" and body["totals"]["failed"] == 2
    errors = [r["error"] for r in body["results"] if not r["ok"]]
    assert len(errors) == 2 and all("not installed" in e for e in errors)


def test_a_second_click_while_syncing_is_rejected_without_duplicates(world):
    Repository.objects.filter(pk__in=[r.pk for r in world.repos]).update(last_sync_status="syncing", sync_started_at=__import__("django").utils.timezone.now())
    with patch(ACCESS) as access, patch(QUEUE) as task:
        res = world.client.post("/api/sync/", {}, format="json")
    assert res.status_code == 409 and res.json()["status"] == "busy"
    assert access.call_count == 0 and task.delay.call_count == 0 and Review.objects.count() == 0


def test_repeating_a_sync_never_duplicates_prs_or_reviews(world):
    fakes = {r.full_name: FakeRepo([gh_pr(1), gh_pr(2)]) for r in world.repos}
    with patch(ACCESS, side_effect=access_for(fakes)), patch(QUEUE) as task:
        world.client.post("/api/sync/", {}, format="json")
        second = world.client.post("/api/sync/", {}, format="json").json()
    assert PullRequest.objects.count() == 6 and Review.objects.count() == 6 and task.delay.call_count == 6
    assert second["totals"]["queued"] == 0 and second["totals"]["updated"] == 6


def test_celery_without_a_worker_is_flagged(world):
    fakes = {r.full_name: FakeRepo([gh_pr(1)]) for r in world.repos}
    warning = {"eager": False, "broker_ok": True, "workers": 0, "warning": "No Celery worker is running."}
    with patch(ACCESS, side_effect=access_for(fakes)), patch(QUEUE), patch("reviews.pr_sync.celery_status", return_value=warning):
        body = world.client.post("/api/sync/", {}, format="json").json()
    assert "No Celery worker is running." in body["warnings"]


def test_sync_all_needs_login_and_a_connected_repository(world):
    assert APIClient().post("/api/sync/").status_code in (401, 403)
    Repository.objects.filter(user=world.me).update(is_enabled=False)
    res = world.client.post("/api/sync/", {}, format="json")
    assert res.status_code == 400 and "Connect" in res.json()["detail"]


# ── GET /api/sync/status/ ───────────────────────────────────────────────────
def test_sync_status_shows_last_result_per_repository(world):
    fakes = {world.repos[0].full_name: FakeRepo([gh_pr(1), gh_pr(2)])}
    with patch(ACCESS, side_effect=access_for(fakes, installation_id=321)), patch(QUEUE):
        world.client.post("/api/sync/", {"review": False}, format="json")
    body = world.client.get("/api/sync/status/").json()
    rows = {r["repository"]: r for r in body["repositories"]}
    ok, bad = rows[world.repos[0].full_name], rows[world.repos[1].full_name]
    assert (ok["status"], ok["pull_requests_fetched"], ok["installation_id"]) == ("ok", 2, 321) and ok["last_synced_at"]
    assert bad["status"] == "error" and "not installed" in bad["error"]
    assert body["reviews"]["open_prs"] == 2 and body["celery"] is None
    assert world.client.get("/api/sync/status/?celery=1").json()["celery"] is not None


def test_sync_status_before_any_sync(world):
    rows = world.client.get("/api/sync/status/").json()["repositories"]
    assert [r["status"] for r in rows] == ["never"] * 3


# ── POST /api/repos/<id>/sync/ ──────────────────────────────────────────────
def test_single_repository_sync_keeps_the_keys_the_pull_requests_page_uses(world):
    repo = world.repos[0]
    with patch(ACCESS, side_effect=access_for({repo.full_name: FakeRepo([gh_pr(1), gh_pr(2)])})), patch(QUEUE):
        body = world.client.post(f"/api/repos/{repo.id}/sync/", {"review": True}, format="json").json()
    assert (body["total"], body["created"], body["reviews_queued"], body["queue_error"]) == (2, 2, 2, None)


def test_single_repository_sync_errors(world):
    repo = world.repos[0]
    with patch(ACCESS, side_effect=GitHubAccessError("The GitHub App is not installed on me/app1.")):
        res = world.client.post(f"/api/repos/{repo.id}/sync/", {}, format="json")
    assert res.status_code == 502 and "not installed" in res.json()["detail"]
    assert world.client.post(f"/api/repos/{world.theirs.id}/sync/", {}, format="json").status_code == 404


# ── dashboard API returns the real PRs and their analysis ───────────────────
def test_dashboard_lists_synced_prs_with_review_status_and_link(world):
    fakes = {r.full_name: FakeRepo([gh_pr(1, title="Add login", login="mansi")]) for r in world.repos}
    with patch(ACCESS, side_effect=access_for(fakes)), patch(QUEUE):
        world.client.post("/api/sync/", {}, format="json")
    body = world.client.get("/api/pull-requests/").json()
    assert body["count"] == 3
    row = next(r for r in body["results"] if r["repository_name"] == world.repos[0].full_name)
    assert (row["number"], row["title"], row["author"], row["state"]) == (1, "Add login", "mansi", "open")
    assert row["html_url"] == "https://github.com/o/r/pull/1" and row["review_status"] == "pending"
    assert row["updated_at"] and row["source_branch"] == "feature/x" and row["target_branch"] == "main"
    assert row["installation_id"] == 5 and row["last_synced_at"]


def make_analysed_pr(world, status="completed", **review_fields):
    pr = PullRequest.objects.create(repository=world.repos[0], number=7, title="Fix", author="dev", latest_head_sha="a" * 40,
                                    html_url="https://github.com/me/app1/pull/7")
    review = Review.objects.create(pull_request=pr, head_sha="a" * 40, status=status, **review_fields)
    return pr, review


def test_completed_analysis_is_visible_on_the_pr(world):
    pr, review = make_analysed_pr(world, summary="Login stores a secret.", files_reviewed=3, health_score=62, health_grade="C",
                                  health_report={"score": 62, "grade": "C", "signals": []},
                                  analysis_warnings=["Tree-sitter could not analyse x.py: SyntaxError"])
    ReviewComment.objects.create(review=review, file_path="auth.py", line_number=4, severity="error", category="security",
                                 message="Hardcoded secret", suggestion="Use env vars", source="static", rule_id="TS-PY-005")
    ReviewComment.objects.create(review=review, file_path="auth.py", line_number=9, severity="warning", category="bug",
                                 message="Token expiry compared as string", suggestion="Parse it", source="llm")
    data = world.client.get(f"/api/pull-requests/{pr.id}/").json()
    rv = data["latest_review"]
    assert (rv["status"], rv["summary"], rv["files_reviewed"], rv["health_grade"], rv["health_score"]) == ("completed", "Login stores a secret.", 3, "C", 62)
    assert rv["counts"] == {"error": 1, "warning": 1, "info": 0, "total": 2, "llm": 1, "static": 1}
    first = rv["comments"][0]
    assert (first["file_path"], first["line_number"], first["message"], first["suggestion"]) == ("auth.py", 4, "Hardcoded secret", "Use env vars")
    assert {c["source"] for c in rv["comments"]} == {"llm", "static"}
    assert rv["analysis_warnings"] == ["Tree-sitter could not analyse x.py: SyntaxError"]


def test_failed_analysis_exposes_the_real_error(world):
    pr, _ = make_analysed_pr(world, status="failed", error_message="NotFound: 404 models/gemini-x is not found")
    rv = world.client.get(f"/api/pull-requests/{pr.id}/").json()["latest_review"]
    assert rv["status"] == "failed" and rv["error_message"] == "NotFound: 404 models/gemini-x is not found"
    assert rv["comments"] == []                                                       # nothing fabricated


def test_github_post_failure_is_visible_but_the_analysis_is_kept(world):
    pr, review = make_analysed_pr(world, summary="ok", github_post_error="GitHub 403: Resource not accessible by integration")
    rv = world.client.get(f"/api/pull-requests/{pr.id}/").json()["latest_review"]
    assert rv["status"] == "completed" and "Resource not accessible" in rv["github_post_error"]


def test_dashboard_never_shows_other_users_prs(world):
    PullRequest.objects.create(repository=world.theirs, number=1, title="secret", author="x", latest_head_sha="b" * 40)
    assert world.client.get("/api/pull-requests/").json()["count"] == 0
