"""
The whole flow in one test:

  GitHub PR -> sync -> Postgres/SQLite -> Celery task -> Tree-sitter + Gemini -> saved findings
  -> GitHub review -> dashboard API

GitHub and Gemini are mocked (and the GitHub review is a mock), so nothing real is called or posted.
Celery runs eagerly, which executes the very same task code a worker would.
"""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from repos.models import Repository
from reviews.github_app import RepoAccess
from reviews.models import Review, ReviewComment
from reviews.tests.gh_fakes import FakeClient, FakeRepo, gh_pr
from reviews.tests.test_review_task import Env

User = get_user_model()
pytestmark = pytest.mark.django_db


def test_sync_then_review_then_dashboard():
    user = User.objects.create_user(username="hemangi", password="x")
    repo = Repository.objects.create(user=user, github_repo_id=1, owner="o", name="r", is_enabled=True)
    client = APIClient()
    client.force_authenticate(user)

    github = FakeClient({"o/r": FakeRepo([gh_pr(3, title="Add app", login="mansi", sha="c" * 40)])})
    access = lambda db_repo, **_: RepoAccess(client=github, installation_id=5, auth_mode="app")  # noqa: E731

    # 1. The dashboard button
    with Env() as env, patch("reviews.pr_sync.client_for_repository", side_effect=access):
        sync = client.post("/api/sync/", {}, format="json").json()

    assert sync["status"] == "ok" and sync["totals"]["found"] == 1 and sync["totals"]["queued"] == 1

    # 2. The review really ran (eager Celery) and was saved
    review = Review.objects.get()
    assert review.status == "completed" and review.head_sha == "c" * 40 and review.installation_id == 5
    assert review.summary == "Found a problem." and review.files_reviewed == 1 and review.health_grade
    sources = set(ReviewComment.objects.filter(review=review).values_list("source", flat=True))
    assert sources == {"llm", "static"}
    assert env.gh_pr.create_review.call_count == 1                                    # the (mock) GitHub review
    assert sync["reviews"]["completed"] == 1 and sync["reviews"]["pending"] == 0     # eager Celery finished it during the sync

    # 3. The dashboard shows the real PR with its analysis
    listing = client.get("/api/pull-requests/").json()
    row = listing["results"][0]
    assert (row["repository_name"], row["number"], row["author"], row["review_status"]) == ("o/r", 3, "mansi", "completed")
    detail = client.get(f"/api/pull-requests/{row['id']}/").json()["latest_review"]
    assert detail["status"] == "completed" and detail["counts"]["total"] == review.comments.count() >= 2
    assert {c["source_label"] for c in detail["comments"]} == {"AI review", "Tree-sitter"}
    assert detail["health"]["score"] == review.health_score

    # 4. Syncing again neither duplicates the PR nor re-reviews the same commit
    with Env() as env2, patch("reviews.pr_sync.client_for_repository", side_effect=access):
        again = client.post("/api/sync/", {}, format="json").json()
    assert again["totals"]["queued"] == 0 and again["totals"]["updated"] == 1
    assert Review.objects.count() == 1 and env2.gh_pr.create_review.call_count == 0
    assert client.get("/api/stats/").json()["totals"]["findings"] == review.comments.count()


def test_when_gemini_fails_the_dashboard_shows_the_failure_and_no_fake_findings():
    user = User.objects.create_user(username="hemangi", password="x")
    Repository.objects.create(user=user, github_repo_id=1, owner="o", name="r", is_enabled=True)
    client = APIClient()
    client.force_authenticate(user)
    github = FakeClient({"o/r": FakeRepo([gh_pr(3)])})
    access = lambda db_repo, **_: RepoAccess(client=github, installation_id=5, auth_mode="app")  # noqa: E731

    with Env(gemini=RuntimeError("404 models/gemini-x is not found")) as env, \
         patch("reviews.pr_sync.client_for_repository", side_effect=access):
        sync = client.post("/api/sync/", {}, format="json").json()

    row = client.get("/api/pull-requests/").json()["results"][0]
    detail = client.get(f"/api/pull-requests/{row['id']}/").json()["latest_review"]
    assert row["review_status"] == "failed" and detail["status"] == "failed"
    assert "models/gemini-x is not found" in detail["error_message"]
    assert detail["comments"] == [] and detail["health_score"] is None and detail["summary"] == ""
    assert env.gh_pr.create_review.call_count == 0
    assert client.get("/api/stats/").json()["totals"]["findings"] == 0
    assert sync["status"] == "ok"                                                     # the sync itself worked; the review failed
