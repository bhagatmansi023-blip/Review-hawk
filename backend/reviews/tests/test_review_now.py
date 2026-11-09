"""Tests for POST /api/pull-requests/<id>/review/ (run or retry one review). GitHub and Celery are mocked."""
from types import SimpleNamespace as NS
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
ACCESS = "reviews.action_views.client_for_repository"
QUEUE = "reviews.queueing.run_llm_review"


@pytest.fixture
def world():
    me = User.objects.create_user(username="me", password="x")
    other = User.objects.create_user(username="other", password="x")
    repo = Repository.objects.create(user=me, github_repo_id=1, owner="o", name="r", is_enabled=True)
    other_repo = Repository.objects.create(user=other, github_repo_id=2, owner="x", name="y", is_enabled=True)
    client = APIClient()
    client.force_authenticate(me)
    pr = PullRequest.objects.create(repository=repo, number=7, title="Add x", author="dev", latest_head_sha="a" * 40)
    return NS(repo=repo, other_repo=other_repo, client=client, pr=pr)


def access(pr_obj=None, installation_id=11):
    fake = FakeRepo([pr_obj] if pr_obj else [])
    return RepoAccess(client=FakeClient({"o/r": fake}), installation_id=installation_id, auth_mode="app")


def post(world, url_suffix=""):
    return world.client.post(f"/api/pull-requests/{world.pr.id}/review/{url_suffix}")


def test_queues_a_review_for_the_commit_github_shows_now(world):
    with patch(ACCESS, return_value=access(gh_pr(7, title="Add x v2", sha="b" * 40))), patch(QUEUE) as task:
        res = post(world)
    assert res.status_code == 202 and res.json()["queued"] and res.json()["head_sha"] == "b" * 40
    review = Review.objects.get()
    assert (review.head_sha, review.status, review.installation_id) == ("b" * 40, "pending", 11)
    task.delay.assert_called_once_with(review.pk)
    world.pr.refresh_from_db()
    assert world.pr.latest_head_sha == "b" * 40 and world.pr.title == "Add x v2"


def test_falls_back_to_the_stored_commit_when_github_cannot_be_reached(world):
    with patch(ACCESS, side_effect=GitHubAccessError("not installed")), patch(QUEUE):
        res = post(world)
    assert res.status_code == 202 and res.json()["head_sha"] == "a" * 40


def test_completed_reviews_need_force(world):
    done = Review.objects.create(pull_request=world.pr, head_sha="a" * 40, status="completed", summary="old", health_score=70)
    ReviewComment.objects.create(review=done, file_path="a.py", line_number=1, message="m", source="llm")
    with patch(ACCESS, side_effect=GitHubAccessError("x")), patch(QUEUE) as task:
        assert post(world).status_code == 409 and task.delay.call_count == 0
        assert post(world, "?force=1").status_code == 202
    done.refresh_from_db()
    assert done.status == "pending" and done.summary == "" and done.health_score is None and done.comments.count() == 0
    assert Review.objects.count() == 1


def test_failed_reviews_are_retried_without_force(world):
    failed = Review.objects.create(pull_request=world.pr, head_sha="a" * 40, status="failed", error_message="boom", github_post_error="x")
    with patch(ACCESS, side_effect=GitHubAccessError("x")), patch(QUEUE) as task:
        assert post(world).status_code == 202
    failed.refresh_from_db()
    assert (failed.status, failed.error_message, failed.github_post_error) == ("pending", "", "") and task.delay.call_count == 1


def test_pending_and_running_reviews_are_not_queued_twice(world):
    review = Review.objects.create(pull_request=world.pr, head_sha="a" * 40, status="running")
    with patch(ACCESS, side_effect=GitHubAccessError("x")), patch(QUEUE) as task:
        assert post(world).status_code == 409
        Review.objects.filter(pk=review.pk).update(status="pending")
        assert post(world).status_code == 409
    assert task.delay.call_count == 0


def test_redis_down_is_reported_with_a_503(world):
    with patch(ACCESS, side_effect=GitHubAccessError("x")), patch(QUEUE) as task:
        task.delay.side_effect = ConnectionError("no redis")
        res = post(world)
    assert res.status_code == 503 and "Redis" in res.json()["detail"]
    assert Review.objects.get().status == "failed"


def test_other_users_prs_are_off_limits(world):
    foreign = PullRequest.objects.create(repository=world.other_repo, number=1, title="x", author="a", latest_head_sha="c" * 40)
    assert world.client.post(f"/api/pull-requests/{foreign.id}/review/").status_code == 404
    assert APIClient().post(f"/api/pull-requests/{world.pr.id}/review/").status_code in (401, 403)
