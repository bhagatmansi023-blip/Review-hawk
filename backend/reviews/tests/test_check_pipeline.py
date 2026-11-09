"""Tests for `manage.py check_pipeline` and for the model/migration sanity it guards against."""
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from repos.models import PullRequest, Repository
from reviews.models import Review, WebhookEvent

pytestmark = pytest.mark.django_db


def run():
    out = StringIO()
    call_command("check_pipeline", "--skip-network", stdout=out)
    return out.getvalue()


def make_repo(**kw):
    user = get_user_model().objects.create_user(username="hemangi", password="x")
    return Repository.objects.create(user=user, github_repo_id=1, owner="o", name="r", is_enabled=True, **kw)


def test_review_model_has_the_fields_the_webhook_needs():
    """Regression: a pasted snippet once defined 'class Review' twice, leaving it with only health fields."""
    names = {f.name for f in Review._meta.get_fields()}
    assert {"pull_request", "head_sha", "status", "summary", "error_message", "health_score", "analysis_warnings"} <= names


def test_every_model_field_has_a_migration():
    """Regression: WebhookEvent.outcome existed in models.py but had no migration, so every webhook crashed."""
    call_command("makemigrations", "--check", "--dry-run", stdout=StringIO())    # raises SystemExit on drift


def test_reports_no_repo_and_no_webhooks_on_a_fresh_install():
    text = run()
    assert "No repository is connected" in text
    assert "No webhook from GitHub has arrived yet" in text and "Sync Pull Requests" in text
    assert "Review model has all required fields" in text


def test_reports_repositories_sync_state_and_webhooks():
    repo = make_repo(last_sync_status="error", last_sync_error="The GitHub App is not installed on o/r.")
    WebhookEvent.objects.create(delivery_id="d1", event_type="pull_request", action="opened", repository=repo, payload={},
                                processed=True, outcome="review 1 queued for abc1234")
    WebhookEvent.objects.create(delivery_id="d2", event_type="pull_request", action="opened", repository=None, payload={})
    text = run()
    assert "o/r (github id 1) enabled, connected by user 'hemangi'" in text
    assert "last sync failed: The GitHub App is not installed" in text
    assert "2 webhook event(s) received" in text and "review 1 queued for abc1234" in text and "repo NOT registered" in text


def test_shows_crashed_deliveries():
    repo = make_repo()
    WebhookEvent.objects.create(delivery_id="d1", event_type="pull_request", action="opened", repository=repo, payload={},
                                error="ProgrammingError: column outcome does not exist")
    text = run()
    assert "ERROR ProgrammingError" in text and "crashed while being processed" in text


def test_warns_when_only_non_pull_request_events_arrive():
    WebhookEvent.objects.create(delivery_id="d1", event_type="ping", action="", payload={})
    assert "none were pull_request events" in run()


def test_shows_failed_reviews_post_errors_and_stuck_pending():
    repo = make_repo()
    for n, kw in enumerate([{"status": "failed", "error_message": "Gemini quota exceeded"}, {"status": "pending"},
                            {"status": "completed", "github_post_error": "GitHub 403: Resource not accessible by integration"}], 1):
        pr = PullRequest.objects.create(repository=repo, number=n, title="t", author="a", latest_head_sha=str(n).zfill(40))
        Review.objects.create(pull_request=pr, head_sha=str(n).zfill(40), **kw)
    text = run()
    assert "Gemini quota exceeded" in text and "stuck in 'pending'" in text and "analysed but not posted to GitHub" in text
