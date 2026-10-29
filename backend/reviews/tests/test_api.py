"""Tests for the dashboard API (reviews/api_views.py)."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from repos.models import PullRequest, Repository
from reviews.models import Review, ReviewComment

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def world():
    me = User.objects.create_user(username="me", password="x")
    other = User.objects.create_user(username="other", password="x")
    repo = Repository.objects.create(user=me, github_repo_id=1001, owner="me", name="app", is_enabled=True)
    other_repo = Repository.objects.create(user=other, github_repo_id=2002, owner="other", name="secret", is_enabled=True)
    client = APIClient()
    client.force_authenticate(me)
    return NS(me=me, other=other, repo=repo, other_repo=other_repo, client=client)


from types import SimpleNamespace as NS  # noqa: E402


def make_pr(repo, number, title="Add feature", state="open", author="dev"):
    return PullRequest.objects.create(
        repository=repo, number=number, title=title, author=author, state=state,
        html_url=f"https://github.com/{repo.full_name}/pull/{number}", latest_head_sha="a" * 40)


def make_review(pr, sha="a", status="completed", score=85, grade="A", days_ago=0, findings=()):
    r = Review.objects.create(pull_request=pr, head_sha=(sha * 40)[:40], status=status,
                              health_score=score, health_grade=grade, summary="ok", files_reviewed=2,
                              health_report={"score": score, "grade": grade, "signals": []})
    stamp = timezone.now() - timedelta(days=days_ago)
    Review.objects.filter(pk=r.pk).update(created_at=stamp, started_at=stamp,
                                          finished_at=stamp + timedelta(seconds=30))
    for severity, source, category, rule in findings:
        c = ReviewComment.objects.create(review=r, file_path="a.py", line_number=3, severity=severity,
                                         category=category, message="msg", source=source, rule_id=rule)
        ReviewComment.objects.filter(pk=c.pk).update(created_at=stamp)
    r.refresh_from_db()
    return r


MIXED = [("error", "static", "security", "TS-PY-005"), ("warning", "llm", "bug", ""), ("info", "static", "maintainability", "TS-PY-001")]


# ── auth & isolation ────────────────────────────────────────────────────────
@pytest.mark.parametrize("url", ["/api/stats/", "/api/reviews/", "/api/reviews/1/", "/api/pull-requests/1/", "/api/repos/1/pulls/"])
def test_endpoints_require_login(url):
    assert APIClient().get(url).status_code in (401, 403)


def test_cannot_see_other_users_data(world):
    pr = make_pr(world.other_repo, 1)
    rev = make_review(pr, findings=MIXED)
    c = world.client
    assert c.get(f"/api/repos/{world.other_repo.id}/pulls/").status_code == 404
    assert c.get(f"/api/pull-requests/{pr.id}/").status_code == 404
    assert c.get(f"/api/reviews/{rev.id}/").status_code == 404
    assert c.get("/api/reviews/").json()["count"] == 0
    assert c.get("/api/stats/").json()["totals"]["findings"] == 0


# ── pull requests ───────────────────────────────────────────────────────────
def test_repo_pulls_list_shape_and_latest_review(world):
    pr = make_pr(world.repo, 7, title="Fix login")
    make_review(pr, sha="a", days_ago=2, score=60, grade="C")
    make_review(pr, sha="b", days_ago=0, score=92, grade="A+", findings=MIXED)
    body = world.client.get(f"/api/repos/{world.repo.id}/pulls/").json()
    assert body["count"] == 1
    row = body["results"][0]
    assert row["number"] == 7 and row["review_status"] == "completed" and row["review_count"] == 2
    assert row["latest_review"]["health_grade"] == "A+"            # newest review wins
    assert row["latest_review"]["counts"] == {"error": 1, "warning": 1, "info": 1, "total": 3, "llm": 1, "static": 2}
    assert row["target_branch"] == "main"


def test_repo_pulls_accepts_github_repo_id(world):
    make_pr(world.repo, 1)
    assert world.client.get(f"/api/repos/{world.repo.github_repo_id}/pulls/").json()["count"] == 1


def test_repo_pulls_filters_and_pagination(world):
    for i in range(1, 13):
        make_pr(world.repo, i, title=f"PR {i}", state="merged" if i % 2 == 0 else "open", author="alice" if i == 3 else "bob")
    url = f"/api/repos/{world.repo.id}/pulls/"
    c = world.client
    assert c.get(url).json()["count"] == 12 and len(c.get(url).json()["results"]) == 10
    assert c.get(url + "?page=2").json()["next"] is None
    assert c.get(url + "?state=merged").json()["count"] == 6
    assert c.get(url + "?search=alice").json()["count"] == 1
    assert c.get(url + "?search=%2311").json()["results"][0]["number"] == 11


def test_pull_request_detail_has_findings_and_health(world):
    pr = make_pr(world.repo, 5)
    make_review(pr, findings=MIXED)
    data = world.client.get(f"/api/pull-requests/{pr.id}/").json()
    review = data["latest_review"]
    assert review["health"]["grade"] == "A" and len(data["review_history"]) == 1
    by_source = {c["source"]: c for c in review["comments"]}
    assert by_source["static"]["source_label"] == "Tree-sitter"
    assert by_source["llm"]["source_label"] == "AI review"
    rules = {c["rule_id"]: c["rule_label"] for c in review["comments"] if c["rule_id"]}
    assert rules["TS-PY-005"] == "Hardcoded secret"


def test_pull_request_without_review_is_handled(world):
    pr = make_pr(world.repo, 9)
    data = world.client.get(f"/api/pull-requests/{pr.id}/").json()
    assert data["latest_review"] is None and data["review_status"] == ""


# ── reviews ─────────────────────────────────────────────────────────────────
def test_review_list_filters_and_ordering(world):
    a = make_review(make_pr(world.repo, 1, title="Login bug"), days_ago=3, findings=MIXED)
    b = make_review(make_pr(world.repo, 2, title="Docs"), sha="b", status="failed", score=None, grade="")
    c = world.client
    ids = [r["id"] for r in c.get("/api/reviews/").json()["results"]]
    assert ids == [b.id, a.id]                                   # newest first
    assert c.get("/api/reviews/?status=failed").json()["count"] == 1
    assert c.get("/api/reviews/?q=login").json()["count"] == 1
    assert c.get(f"/api/reviews/?repo={world.repo.id}").json()["count"] == 2
    row = next(r for r in c.get("/api/reviews/").json()["results"] if r["id"] == a.id)
    assert row["counts"]["total"] == 3 and row["counts"]["static"] == 2 and row["repository_name"] == "me/app"


def test_review_detail_lists_all_findings(world):
    rev = make_review(make_pr(world.repo, 1), findings=MIXED)
    data = world.client.get(f"/api/reviews/{rev.id}/").json()
    assert len(data["comments"]) == 3 and data["health"]["score"] == 85


# ── stats ───────────────────────────────────────────────────────────────────
def test_stats_empty_state(world):
    s = world.client.get("/api/stats/").json()
    assert s["totals"]["reviews"] == 0 and s["totals"]["avg_health_score"] is None
    assert len(s["issues_over_time"]) == 30 and sum(d["total"] for d in s["issues_over_time"]) == 0
    assert [x["count"] for x in s["severity_breakdown"]] == [0, 0, 0]


def test_stats_totals_and_breakdowns(world):
    make_review(make_pr(world.repo, 1), score=90, grade="A+", findings=MIXED)
    make_review(make_pr(world.repo, 2), score=70, grade="B", findings=[("error", "llm", "bug", "")])
    make_review(make_pr(world.repo, 3), status="failed", score=None, grade="")
    s = world.client.get("/api/stats/").json()
    t = s["totals"]
    assert (t["reviews"], t["completed"], t["failed"], t["pull_requests_reviewed"]) == (3, 2, 1, 3)
    assert (t["findings"], t["ai_findings"], t["static_findings"]) == (4, 2, 2)
    assert t["avg_health_score"] == 80.0 and t["avg_review_seconds"] == 30.0
    assert {x["severity"]: x["count"] for x in s["severity_breakdown"]} == {"error": 2, "warning": 1, "info": 1}
    assert {x["source"]: x["count"] for x in s["source_breakdown"]} == {"llm": 2, "static": 2}
    assert {x["grade"]: x["count"] for x in s["health_distribution"]}["A+"] == 1
    assert s["top_rules"][0]["count"] == 1 and s["top_rules"][0]["rule_id"].startswith("TS-PY")
    assert s["per_repository"][0]["repository_name"] == "me/app" and s["per_repository"][0]["findings"] == 4


def test_stats_time_series_is_zero_filled_and_dated(world):
    make_review(make_pr(world.repo, 1), days_ago=0, findings=MIXED)
    make_review(make_pr(world.repo, 2), sha="b", days_ago=2, findings=[("error", "llm", "bug", "")])
    s = world.client.get("/api/stats/?days=7").json()
    series = s["issues_over_time"]
    assert len(series) == 7 and series[-1]["date"] == timezone.now().date().isoformat()
    assert series[-1]["total"] == 3 and series[-1]["reviews"] == 1
    assert series[-3]["error"] == 1 and series[-2]["total"] == 0


def test_stats_range_and_repo_filters(world):
    other_mine = Repository.objects.create(user=world.me, github_repo_id=3003, owner="me", name="b", is_enabled=True)
    make_review(make_pr(world.repo, 1), findings=MIXED)
    make_review(make_pr(other_mine, 1), days_ago=40, findings=MIXED)
    c = world.client
    assert c.get("/api/stats/?days=30").json()["totals"]["reviews"] == 1      # 40-day-old review excluded
    assert c.get("/api/stats/?days=90").json()["totals"]["reviews"] == 2
    assert c.get(f"/api/stats/?days=90&repo={other_mine.id}").json()["totals"]["reviews"] == 1
    assert len(c.get("/api/stats/?days=9999").json()["issues_over_time"]) == 365  # clamped
    assert len(c.get("/api/stats/?days=abc").json()["issues_over_time"]) == 30    # bad input -> default
