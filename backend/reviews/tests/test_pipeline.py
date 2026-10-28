"""
reviews/tests/test_pipeline.py
================================
Integration tests for the Review-hawk review pipeline.

Coverage
--------
  1.  Webhook HMAC signature — valid accepts, invalid rejects
  2.  Duplicate webhook delivery returns 200 (idempotency)
  3.  Concurrent duplicate (IntegrityError on Review.create) returns 200
  4.  Diff position mapping on a multi-hunk fixture
  5.  Inline comment cap (MAX_INLINE_COMMENTS=20)
  6.  GitHub 422 fallback: retry without inline comments
  7.  Installation auth used when installation_id is present
  8.  Transient error (timeout) → Celery retry fires
  9.  Permanent error (bad JSON) → Review.FAILED, no Celery retry
 10.  No double-post: completed review is skipped on re-delivery
 11.  DB rows: Review + ReviewComment correctly saved after full cycle
 12.  End-to-end: fake webhook → posted payload + saved rows

Run with:
    python -m pytest reviews/tests/test_pipeline.py -v

All network calls are mocked — no real GitHub/Gemini calls are made.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import pytest
from django.test import RequestFactory, TestCase, override_settings
from django.contrib.auth import get_user_model

from repos.models import PullRequest, Repository
from reviews.models import Review, ReviewComment, WebhookEvent
from reviews.llm_reviewer import (
    build_diff_position_map,
    extract_changed_lines,
    _is_transient,
    MAX_INLINE_COMMENTS,
)
from reviews.views import github_webhook, verify_signature

User = get_user_model()

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

WEBHOOK_SECRET = "test-secret-abc123"

# A small multi-hunk unified diff for position-mapping tests
MULTI_HUNK_DIFF = """\
diff --git a/foo.py b/foo.py
index 1234567..abcdefg 100644
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,4 @@
 line_context_1
+line_added_2
 line_context_3
 line_context_4
@@ -10,3 +11,4 @@
 line_context_10
+line_added_11
 line_context_12
 line_context_13
"""

MINIMAL_GEMINI_JSON = json.dumps({
    "summary": "Looks fine.",
    "score": 8,
    "comments": [],
    "security_flags": [],
})

GEMINI_WITH_COMMENTS = json.dumps({
    "summary": "Several issues found.",
    "score": 5,
    "comments": [
        {
            "file_path": "foo.py",
            "line_number": 2,
            "severity": "warning",
            "category": "maintainability",
            "message": "Test issue",
            "suggestion": "Fix it",
        }
    ],
    "security_flags": [],
})


def _make_signature(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(
        secret.encode(), msg=body, digestmod=hashlib.sha256
    ).hexdigest()


def _make_webhook_request(factory, payload: dict, secret: str = WEBHOOK_SECRET,
                           event: str = "pull_request",
                           delivery_id: str = "delivery-001"):
    body = json.dumps(payload).encode()
    sig = _make_signature(secret, body)
    req = factory.post(
        "/api/webhook/webhook/",
        data=body,
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256=sig,
        HTTP_X_GITHUB_EVENT=event,
        HTTP_X_GITHUB_DELIVERY=delivery_id,
    )
    return req


def _pr_payload(repo_id: int = 99, pr_number: int = 1, sha: str = "abc" * 13 + "a",
                action: str = "opened", installation_id: int | None = 42) -> dict:
    payload: dict = {
        "action": action,
        "installation": {"id": installation_id} if installation_id else {},
        "repository": {"id": repo_id, "full_name": "owner/repo"},
        "pull_request": {
            "number": pr_number,
            "title": "Test PR",
            "head": {"sha": sha},
            "user": {"login": "testuser"},
            "html_url": "https://github.com/owner/repo/pull/1",
            "state": "open",
        },
    }
    return payload


@pytest.fixture
def db_objects(db):
    """Create minimal DB objects: User → Repository → (nothing yet for PR)."""
    user = User.objects.create_user(username="testuser", password="pass")
    repo = Repository.objects.create(
        user=user,
        github_repo_id=99,
        owner="owner",
        name="repo",
        default_branch="main",
        is_enabled=True,
    )
    return user, repo


# ---------------------------------------------------------------------------
# 1. HMAC signature verification
# ---------------------------------------------------------------------------

class TestVerifySignature:
    def test_valid_signature_accepted(self):
        body = b"hello"
        sig = _make_signature(WEBHOOK_SECRET, body)
        assert verify_signature(body, WEBHOOK_SECRET, sig) is True

    def test_invalid_signature_rejected(self):
        assert verify_signature(b"hello", WEBHOOK_SECRET, "sha256=bad") is False

    def test_missing_signature_rejected(self):
        assert verify_signature(b"hello", WEBHOOK_SECRET, None) is False


# ---------------------------------------------------------------------------
# 2 & 3. Duplicate delivery / concurrent IntegrityError
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@override_settings(GITHUB_WEBHOOK_SECRET=WEBHOOK_SECRET)
def test_duplicate_delivery_returns_200(db_objects):
    """Same delivery_id twice → second call returns 200 with status=skipped."""
    user, repo = db_objects
    factory = RequestFactory()
    payload = _pr_payload()

    # First delivery — create the WebhookEvent
    WebhookEvent.objects.create(
        delivery_id="delivery-dup",
        event_type="pull_request",
        action="opened",
        repository=repo,
        payload=payload,
    )

    req = _make_webhook_request(factory, payload, delivery_id="delivery-dup")
    with patch("reviews.views.GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET), \
         patch("reviews.views.run_llm_review") as mock_task:
        from reviews.views import github_webhook
        resp = github_webhook(req)

    assert resp.status_code == 200
    data = json.loads(resp.content)
    assert data["status"] == "skipped"
    mock_task.delay.assert_not_called()


@pytest.mark.django_db
@override_settings(GITHUB_WEBHOOK_SECRET=WEBHOOK_SECRET)
def test_concurrent_duplicate_integrity_error_returns_200(db_objects):
    """Concurrent redelivery hitting IntegrityError → still returns 200."""
    user, repo = db_objects
    factory = RequestFactory()
    payload = _pr_payload()

    from django.db import IntegrityError as DjangoIntegrityError

    req = _make_webhook_request(factory, payload)
    with patch("reviews.views.GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET), \
         patch("reviews.views.Review.objects.create", side_effect=DjangoIntegrityError), \
         patch("reviews.views.Review.objects.filter") as mock_filter, \
         patch("reviews.views.run_llm_review") as mock_task:
        mock_filter.return_value.exists.return_value = False
        resp = github_webhook(req)

    assert resp.status_code == 200
    mock_task.delay.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Diff position mapping — multi-hunk fixture
# ---------------------------------------------------------------------------

class TestDiffPositionMap:
    def test_first_hunk_added_line(self):
        pos_map = build_diff_position_map(MULTI_HUNK_DIFF)
        # Line 2 in foo.py is the added line in hunk 1
        assert ("foo.py", 2) in pos_map

    def test_second_hunk_added_line(self):
        pos_map = build_diff_position_map(MULTI_HUNK_DIFF)
        # Line 12 in foo.py is the added line in hunk 2
        assert ("foo.py", 12) in pos_map

    def test_positions_are_sequential_per_file(self):
        pos_map = build_diff_position_map(MULTI_HUNK_DIFF)
        positions = sorted(v for (f, _), v in pos_map.items() if f == "foo.py")
        assert positions == sorted(set(positions)), "positions should be unique and increasing"

    def test_extract_changed_lines_only_additions(self):
        changed = extract_changed_lines(MULTI_HUNK_DIFF)
        assert 2 in changed["foo.py"]
        assert 12 in changed["foo.py"]
        # Context lines should NOT be in changed set
        assert 1 not in changed["foo.py"]

    def test_nonexistent_line_not_in_map(self):
        pos_map = build_diff_position_map(MULTI_HUNK_DIFF)
        assert ("foo.py", 999) not in pos_map


# ---------------------------------------------------------------------------
# 5. Inline comment cap
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_inline_cap_at_20(db_objects):
    """_post_github_review caps inline comments at MAX_INLINE_COMMENTS."""
    from reviews.llm_reviewer import _post_github_review, LLMReviewResult, LLMComment

    user, repo = db_objects
    pr = PullRequest.objects.create(
        repository=repo, number=1, title="T", author="u",
        latest_head_sha="a" * 40,
    )
    review = Review.objects.create(
        pull_request=pr, head_sha="a" * 40, status=Review.Status.RUNNING,
        installation_id=None,
    )

    # Build 25 LLM comments all on mappable lines
    comments = [
        LLMComment(file_path="f.py", line_number=i, severity="info",
                   category="other", message=f"msg {i}")
        for i in range(1, 26)
    ]
    # Position map: every line maps somewhere
    pos_map = {("f.py", i): i for i in range(1, 26)}

    result = LLMReviewResult(summary="s", score=7, comments=comments)

    mock_gh_review = MagicMock()
    mock_gh_review.id = 9999
    mock_pr = MagicMock()
    mock_pr.create_review.return_value = mock_gh_review
    mock_pr.diff_url = "https://example.com/diff"
    mock_repo_obj = MagicMock()
    mock_repo_obj.get_pull.return_value = mock_pr
    mock_repo_obj.get_commit.return_value = MagicMock()
    mock_gh = MagicMock()
    mock_gh.get_repo.return_value = mock_repo_obj

    _post_github_review(
        gh=mock_gh,
        review=review,
        result=result,
        static_findings=[],
        position_map=pos_map,
    )

    # create_review was called once; inspect inline comments count
    call_kwargs = mock_pr.create_review.call_args.kwargs
    assert len(call_kwargs["comments"]) == MAX_INLINE_COMMENTS


# ---------------------------------------------------------------------------
# 6. GitHub 422 fallback
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_422_fallback_retries_without_inline(db_objects):
    """On GitHub 422, _post_github_review retries with empty inline list."""
    from reviews.llm_reviewer import _post_github_review, LLMReviewResult, LLMComment
    from github import GithubException

    user, repo = db_objects
    pr = PullRequest.objects.create(
        repository=repo, number=2, title="T", author="u",
        latest_head_sha="b" * 40,
    )
    review = Review.objects.create(
        pull_request=pr, head_sha="b" * 40, status=Review.Status.RUNNING,
    )

    comments = [LLMComment(file_path="f.py", line_number=1, severity="info",
                            category="other", message="m")]
    pos_map = {("f.py", 1): 1}
    result = LLMReviewResult(summary="s", score=7, comments=comments)

    mock_gh_review = MagicMock()
    mock_gh_review.id = 1234
    mock_pr = MagicMock()
    # First call raises 422, second succeeds
    mock_pr.create_review.side_effect = [
        GithubException(422, {"message": "Unprocessable"}, {}),
        mock_gh_review,
    ]
    mock_repo_obj = MagicMock()
    mock_repo_obj.get_pull.return_value = mock_pr
    mock_repo_obj.get_commit.return_value = MagicMock()
    mock_gh = MagicMock()
    mock_gh.get_repo.return_value = mock_repo_obj

    gh_id = _post_github_review(
        gh=mock_gh,
        review=review,
        result=result,
        static_findings=[],
        position_map=pos_map,
    )

    assert gh_id == 1234
    assert mock_pr.create_review.call_count == 2
    # Second call must have empty comments list
    second_call_kwargs = mock_pr.create_review.call_args_list[1].kwargs
    assert second_call_kwargs["comments"] == []


# ---------------------------------------------------------------------------
# 7. Installation auth used when installation_id present
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_app_auth_used_when_installation_id_set(db_objects):
    """_get_github_client uses GithubIntegration when installation_id is set."""
    from reviews.llm_reviewer import _get_github_client
    import reviews.llm_reviewer as reviewer_mod

    user, repo = db_objects
    pr = PullRequest.objects.create(
        repository=repo, number=3, title="T", author="u",
        latest_head_sha="c" * 40,
    )
    review = Review.objects.create(
        pull_request=pr, head_sha="c" * 40, status=Review.Status.RUNNING,
        installation_id=12345,
    )

    mock_token = MagicMock()
    mock_token.token = "ghs_installtoken"
    mock_install = MagicMock()
    mock_install.id = 12345
    mock_integration = MagicMock()
    mock_integration.get_installation.return_value = mock_install
    mock_integration.get_access_token.return_value = mock_token

    with patch.object(reviewer_mod, "GITHUB_APP_ID", "99999"), \
         patch.object(reviewer_mod, "GITHUB_PRIVATE_KEY_PATH", "/fake/key.pem"), \
         patch("builtins.open", MagicMock(return_value=MagicMock(
             __enter__=lambda s: MagicMock(read=lambda: "FAKE_KEY"),
             __exit__=MagicMock(return_value=False)))), \
         patch("reviews.llm_reviewer.GithubIntegration", return_value=mock_integration) as MockGI, \
         patch("reviews.llm_reviewer.Github") as MockGh:

        _get_github_client(review)

    MockGI.assert_called_once_with(integration_id=99999, private_key="FAKE_KEY")
    MockGh.assert_called_once_with("ghs_installtoken")


# ---------------------------------------------------------------------------
# 8. Transient error classification
# ---------------------------------------------------------------------------

class TestIsTransient:
    def test_timeout_is_transient(self):
        import requests as req_lib
        assert _is_transient(req_lib.Timeout()) is True

    def test_connection_error_is_transient(self):
        import requests as req_lib
        assert _is_transient(req_lib.ConnectionError()) is True

    def test_github_5xx_is_transient(self):
        from github import GithubException
        assert _is_transient(GithubException(503, {}, {})) is True

    def test_github_403_is_transient(self):
        from github import GithubException
        assert _is_transient(GithubException(403, {}, {})) is True

    def test_github_404_is_not_transient(self):
        from github import GithubException
        assert _is_transient(GithubException(404, {}, {})) is False

    def test_github_422_is_not_transient(self):
        from github import GithubException
        assert _is_transient(GithubException(422, {}, {})) is False

    def test_runtime_error_is_not_transient(self):
        assert _is_transient(RuntimeError("bad JSON")) is False

    def test_value_error_is_not_transient(self):
        assert _is_transient(ValueError("oops")) is False


# ---------------------------------------------------------------------------
# 9. Transient retry via Celery + permanent failure → Review.FAILED
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_transient_error_raises_for_celery_retry(db_objects):
    """run_review re-raises transient errors so Celery can retry."""
    from reviews.llm_reviewer import run_review
    import requests as req_lib

    user, repo = db_objects
    pr = PullRequest.objects.create(
        repository=repo, number=10, title="T", author="u",
        latest_head_sha="d" * 40,
    )
    review = Review.objects.create(
        pull_request=pr, head_sha="d" * 40, status=Review.Status.PENDING,
    )

    with patch("reviews.llm_reviewer._get_github_client", side_effect=req_lib.Timeout()):
        with pytest.raises(req_lib.Timeout):
            run_review(review.pk)

    review.refresh_from_db()
    # Status should still be RUNNING (transient — Celery will retry)
    assert review.status == Review.Status.RUNNING


@pytest.mark.django_db
def test_permanent_error_marks_review_failed(db_objects):
    """Permanent error → Review.FAILED, error_message set, no re-raise."""
    from reviews.llm_reviewer import run_review

    user, repo = db_objects
    pr = PullRequest.objects.create(
        repository=repo, number=11, title="T", author="u",
        latest_head_sha="e" * 40,
    )
    review = Review.objects.create(
        pull_request=pr, head_sha="e" * 40, status=Review.Status.PENDING,
    )

    with patch("reviews.llm_reviewer._get_github_client",
               side_effect=RuntimeError("bad JSON from LLM")):
        # Should NOT raise — permanent errors are swallowed
        run_review(review.pk)

    review.refresh_from_db()
    assert review.status == Review.Status.FAILED
    assert "bad JSON" in review.error_message


# ---------------------------------------------------------------------------
# 10. No double-post: completed review is skipped
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_completed_review_is_not_reprocessed(db_objects):
    """run_review bails out immediately if review is already COMPLETED."""
    from reviews.llm_reviewer import run_review

    user, repo = db_objects
    pr = PullRequest.objects.create(
        repository=repo, number=12, title="T", author="u",
        latest_head_sha="f" * 40,
    )
    review = Review.objects.create(
        pull_request=pr, head_sha="f" * 40, status=Review.Status.COMPLETED,
        github_review_id=777,
    )

    with patch("reviews.llm_reviewer._get_github_client") as mock_auth:
        run_review(review.pk)

    mock_auth.assert_not_called()
    review.refresh_from_db()
    assert review.github_review_id == 777   # unchanged


# ---------------------------------------------------------------------------
# 11. DB rows saved correctly
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_review_comment_rows_saved(db_objects):
    """After a successful _do_review, ReviewComment rows exist in the DB."""
    from reviews.llm_reviewer import _do_review, LLMReviewResult, LLMComment

    user, repo = db_objects
    pr = PullRequest.objects.create(
        repository=repo, number=20, title="T", author="u",
        latest_head_sha="0" * 40,
    )
    review = Review.objects.create(
        pull_request=pr, head_sha="0" * 40, status=Review.Status.RUNNING,
    )

    mock_gh_review = MagicMock()
    mock_gh_review.id = 55555
    mock_gh_pr = MagicMock()
    mock_gh_pr.body = ""
    mock_gh_pr.diff_url = "https://example.com/diff"
    mock_gh_pr.create_review.return_value = mock_gh_review
    mock_gh_repo = MagicMock()
    mock_gh_repo.get_pull.return_value = mock_gh_pr
    mock_gh_repo.get_commit.return_value = MagicMock()
    mock_gh = MagicMock()
    mock_gh.get_repo.return_value = mock_gh_repo

    # Fake diff with one added line
    fake_diff = (
        "diff --git a/app.py b/app.py\n"
        "--- a/app.py\n+++ b/app.py\n"
        "@@ -1 +1,2 @@\n"
        " existing_line\n"
        "+new_line\n"
    )

    with patch("reviews.llm_reviewer._get_github_client", return_value=mock_gh), \
         patch("reviews.llm_reviewer.http_requests.get") as mock_get, \
         patch("reviews.llm_reviewer._call_gemini",
               return_value=(GEMINI_WITH_COMMENTS, 100, 50)), \
         patch("reviews.tree_sitter_analyzer.TREE_SITTER_AVAILABLE", False):

        mock_resp = MagicMock()
        mock_resp.text = fake_diff
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        _do_review(review, pr, repo)

    review.refresh_from_db()
    assert review.status == Review.Status.COMPLETED
    assert review.github_review_id == 55555
    assert review.posted_at is not None

    comments = ReviewComment.objects.filter(review=review)
    assert comments.count() >= 1
    llm_comment = comments.filter(source=ReviewComment.Source.LLM).first()
    assert llm_comment is not None
    assert llm_comment.file_path == "foo.py"   # matches GEMINI_WITH_COMMENTS fixture



# ---------------------------------------------------------------------------
# 12. End-to-end: fake webhook → _do_review called → DB rows saved
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@override_settings(GITHUB_WEBHOOK_SECRET=WEBHOOK_SECRET, CELERY_TASK_ALWAYS_EAGER=True)
def test_e2e_webhook_to_db_rows(db_objects):
    """
    Fake a full webhook POST → webhook view → task dispatched → _do_review
    runs (all IO mocked) → ReviewComment rows exist in DB.
    """
    user, repo = db_objects
    factory = RequestFactory()

    sha = "a" * 40
    payload = _pr_payload(repo_id=99, pr_number=50, sha=sha,
                          action="opened", installation_id=88)
    req = _make_webhook_request(factory, payload, delivery_id="e2e-001")

    fake_diff = (
        "diff --git a/main.py b/main.py\n"
        "--- a/main.py\n+++ b/main.py\n"
        "@@ -1 +1,2 @@\n"
        " x = 1\n"
        "+y = 2\n"
    )

    mock_gh_review = MagicMock()
    mock_gh_review.id = 77777
    mock_gh_pr = MagicMock()
    mock_gh_pr.body = ""
    mock_gh_pr.diff_url = "https://example.com/diff"
    mock_gh_pr.create_review.return_value = mock_gh_review
    mock_gh_repo = MagicMock()
    mock_gh_repo.get_pull.return_value = mock_gh_pr
    mock_gh_repo.get_commit.return_value = MagicMock()
    mock_gh = MagicMock()
    mock_gh.get_repo.return_value = mock_gh_repo

    with patch("reviews.views.GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET), \
         patch("reviews.llm_reviewer._get_github_client", return_value=mock_gh), \
         patch("reviews.llm_reviewer.http_requests.get") as mock_get, \
         patch("reviews.llm_reviewer._call_gemini",
               return_value=(GEMINI_WITH_COMMENTS, 200, 80)), \
         patch("reviews.tree_sitter_analyzer.TREE_SITTER_AVAILABLE", False):

        mock_resp = MagicMock()
        mock_resp.text = fake_diff
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        resp = github_webhook(req)

    assert resp.status_code == 200

    # DB assertions
    review = Review.objects.get(pull_request__number=50, head_sha=sha)
    assert review.status == Review.Status.COMPLETED
    assert review.installation_id == 88
    assert review.github_review_id == 77777
    assert ReviewComment.objects.filter(review=review).count() >= 1
