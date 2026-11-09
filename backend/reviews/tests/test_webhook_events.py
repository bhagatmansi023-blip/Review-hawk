"""
Webhook behaviour for pull_request events, sent through the real URLs with real HMAC signatures.
Celery is mocked, so no review ever runs here.
"""
import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from repos.models import PullRequest, Repository
from reviews.models import Review, WebhookEvent

User = get_user_model()
pytestmark = pytest.mark.django_db
SECRET = "test-webhook-secret"
SHA1, SHA2 = "a" * 40, "b" * 40


def payload(action="opened", number=3, sha=SHA1, repo_id=99, state="open", merged=False, installation=4242):
    return {
        "action": action,
        "installation": {"id": installation},
        "repository": {"id": repo_id, "full_name": "o/r"},
        "pull_request": {
            "id": 555, "number": number, "title": "Add login", "body": "Adds JWT login", "state": state, "merged": merged,
            "merged_at": "2026-11-01T10:00:00Z" if merged else None, "closed_at": "2026-11-01T10:00:00Z" if state == "closed" else None,
            "created_at": "2026-10-31T09:00:00Z", "updated_at": "2026-11-01T09:30:00Z", "draft": False,
            "html_url": f"https://github.com/o/r/pull/{number}", "user": {"login": "mansi"},
            "head": {"sha": sha, "ref": "feature/login"}, "base": {"ref": "main"},
        },
    }


def send(body, *, delivery="d-1", event="pull_request", url="/api/webhook/", secret=SECRET, signature=None):
    raw = json.dumps(body).encode()
    sig = signature or "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    with patch("reviews.views.GITHUB_WEBHOOK_SECRET", SECRET):
        return Client().post(url, data=raw, content_type="application/json", HTTP_X_HUB_SIGNATURE_256=sig,
                             HTTP_X_GITHUB_EVENT=event, HTTP_X_GITHUB_DELIVERY=delivery)


@pytest.fixture
def repo():
    user = User.objects.create_user(username="u", password="x")
    return Repository.objects.create(user=user, github_repo_id=99, owner="o", name="r", is_enabled=True)


@pytest.fixture(autouse=True)
def queue():
    with patch("reviews.views.run_llm_review") as task:
        yield task


# ── endpoints and signatures ────────────────────────────────────────────────
@pytest.mark.parametrize("url", ["/api/webhook/", "/api/webhook/webhook/"])
def test_both_webhook_urls_work(repo, queue, url):
    assert send(payload(), url=url).status_code == 200
    assert queue.delay.call_count == 1


def test_bad_or_missing_signature_is_rejected(repo, queue):
    assert send(payload(), secret="wrong").status_code == 403
    assert send(payload(), signature="sha256=00").status_code == 403
    assert not PullRequest.objects.exists() and queue.delay.call_count == 0


def test_ping_is_acknowledged(repo):
    res = send({"zen": "Keep it logically awesome."}, event="ping")
    assert res.status_code == 200
    assert WebhookEvent.objects.get().outcome == "ping acknowledged"


# ── opened ──────────────────────────────────────────────────────────────────
def test_opened_saves_the_pr_and_queues_one_review(repo, queue):
    assert send(payload()).status_code == 200
    pr = PullRequest.objects.get(repository=repo, number=3)
    assert (pr.title, pr.body, pr.author, pr.state) == ("Add login", "Adds JWT login", "mansi", "open")
    assert (pr.latest_head_sha, pr.source_branch, pr.target_branch) == (SHA1, "feature/login", "main")
    assert pr.html_url.endswith("/pull/3") and pr.installation_id == 4242 and pr.github_pr_id == 555
    review = Review.objects.get(pull_request=pr)
    assert (review.status, review.head_sha, review.installation_id) == ("pending", SHA1, 4242)
    queue.delay.assert_called_once_with(review.pk)
    repo.refresh_from_db()
    assert repo.installation_id == 4242                                               # remembered for the sync
    event = WebhookEvent.objects.get()
    assert event.processed and event.error == "" and "queued" in event.outcome and event.repository == repo


# ── synchronize / reopened ──────────────────────────────────────────────────
def test_synchronize_with_a_new_commit_creates_a_second_review(repo, queue):
    send(payload("opened"), delivery="d-1")
    send(payload("synchronize", sha=SHA2), delivery="d-2")
    pr = PullRequest.objects.get(repository=repo, number=3)
    assert pr.latest_head_sha == SHA2 and PullRequest.objects.count() == 1
    assert sorted(Review.objects.filter(pull_request=pr).values_list("head_sha", flat=True)) == [SHA1, SHA2]
    assert queue.delay.call_count == 2


def test_reopened_retries_a_failed_review_but_not_a_completed_one(repo, queue):
    send(payload("opened"), delivery="d-1")
    Review.objects.update(status="failed", error_message="Gemini 429")
    send(payload("reopened"), delivery="d-2")
    review = Review.objects.get()
    assert review.status == "pending" and review.error_message == "" and queue.delay.call_count == 2
    Review.objects.update(status="completed")
    send(payload("reopened"), delivery="d-3")
    assert queue.delay.call_count == 2 and Review.objects.get().status == "completed"


def test_other_actions_refresh_the_pr_but_never_review(repo, queue):
    send(payload("opened"), delivery="d-1")
    body = payload("edited", sha=SHA1)
    body["pull_request"]["title"] = "Better title"
    send(body, delivery="d-2")
    assert PullRequest.objects.get().title == "Better title" and queue.delay.call_count == 1
    assert "no review needed" in WebhookEvent.objects.get(delivery_id="d-2").outcome


# ── closed ──────────────────────────────────────────────────────────────────
def test_closed_updates_the_state_and_queues_nothing(repo, queue):
    send(payload("opened"), delivery="d-1")
    send(payload("closed", state="closed"), delivery="d-2")
    assert PullRequest.objects.get().state == "closed" and queue.delay.call_count == 1
    assert Review.objects.count() == 1


def test_merged_prs_are_marked_merged(repo, queue):
    send(payload("closed", state="closed", merged=True))
    pr = PullRequest.objects.get()
    assert pr.state == "merged" and pr.merged_at is not None and queue.delay.call_count == 0


# ── duplicates ──────────────────────────────────────────────────────────────
def test_the_same_delivery_twice_creates_one_review(repo, queue):
    assert send(payload(), delivery="same").status_code == 200
    second = send(payload(), delivery="same")
    assert second.json() == {"status": "skipped", "reason": "already processed"}
    assert Review.objects.count() == 1 and queue.delay.call_count == 1 and WebhookEvent.objects.count() == 1


def test_a_different_delivery_for_the_same_commit_creates_no_second_review(repo, queue):
    send(payload(), delivery="d-1")                                                   # e.g. the app hook and a repo hook
    send(payload(), delivery="d-2")
    assert Review.objects.count() == 1 and queue.delay.call_count == 1
    assert "already exists" in WebhookEvent.objects.get(delivery_id="d-2").outcome


# ── repositories we do not review ───────────────────────────────────────────
def test_unregistered_repository_is_ignored_and_recorded(repo, queue):
    res = send(payload(repo_id=12345))
    assert res.status_code == 200 and not PullRequest.objects.exists() and queue.delay.call_count == 0
    event = WebhookEvent.objects.get()
    assert event.repository is None and "not connected" in event.outcome


def test_disabled_repository_saves_the_pr_but_does_not_review(repo, queue):
    Repository.objects.filter(pk=repo.pk).update(is_enabled=False)
    send(payload())
    assert PullRequest.objects.count() == 1 and Review.objects.count() == 0 and queue.delay.call_count == 0
    assert "disabled" in WebhookEvent.objects.get().outcome


# ── failures ────────────────────────────────────────────────────────────────
def test_redis_down_marks_the_review_failed_instead_of_crashing(repo, queue):
    queue.delay.side_effect = ConnectionError("Error 10061 connecting to localhost:6379")
    assert send(payload()).status_code == 200
    review = Review.objects.get()
    assert review.status == "failed" and "Is Redis running?" in review.error_message


def test_a_crash_is_recorded_and_a_redelivery_is_processed(repo, queue):
    with patch("reviews.views._handle_pull_request", side_effect=RuntimeError("database exploded")):
        res = send(payload(), delivery="d-1")
    assert res.status_code == 500
    event = WebhookEvent.objects.get()
    assert not event.processed and "RuntimeError: database exploded" in event.error
    assert send(payload(), delivery="d-1").status_code == 200                         # GitHub "Redeliver"
    event.refresh_from_db()
    assert event.processed and event.error == "" and Review.objects.count() == 1
