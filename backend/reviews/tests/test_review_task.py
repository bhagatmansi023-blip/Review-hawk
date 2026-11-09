"""
Celery task execution of a review: Tree-sitter + Gemini -> saved findings -> GitHub.
GitHub and Gemini are mocked, and the GitHub review is a mock, so nothing is ever posted.
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from github import GithubException

from repos.models import PullRequest, Repository
from reviews.models import Review, ReviewComment
from reviews.tasks import run_llm_review

User = get_user_model()
pytestmark = pytest.mark.django_db

SOURCE = 'import os\n\nAPI_KEY = "abcd1234secret"\n\ndef go():\n    return 1\n'
DIFF = ("diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -0,0 +1,6 @@\n"
        "+import os\n+\n+API_KEY = \"abcd1234secret\"\n+\n+def go():\n+    return 1\n")
GEMINI_OK = json.dumps({"summary": "Found a problem.", "score": 4, "security_flags": [],
                        "comments": [{"file_path": "app.py", "line_number": 6, "severity": "warning", "category": "bug",
                                      "message": "go() ignores its inputs.", "suggestion": "Use them."}]})


@pytest.fixture
def review():
    user = User.objects.create_user(username="u", password="x")
    repo = Repository.objects.create(user=user, github_repo_id=1, owner="o", name="r", is_enabled=True)
    pr = PullRequest.objects.create(repository=repo, number=3, title="Add app", author="dev", latest_head_sha="c" * 40)
    return Review.objects.create(pull_request=pr, head_sha="c" * 40, installation_id=5)


class Env:
    """Everything the review talks to, mocked."""

    def __init__(self, gemini=(GEMINI_OK, 100, 50), post_error=None):
        self.gh_review = MagicMock(id=4242)
        self.gh_pr = MagicMock(body="", title="Add app")
        if post_error:
            self.gh_pr.create_review.side_effect = post_error
        else:
            self.gh_pr.create_review.return_value = self.gh_review
        self.gh_repo = MagicMock()
        self.gh_repo.get_pull.return_value = self.gh_pr
        self.gh_repo.get_contents.return_value = MagicMock(decoded_content=SOURCE.encode())
        self.gh = MagicMock(_rh_token="ghs_installation_token")
        self.gh.get_repo.return_value = self.gh_repo
        self.http = MagicMock(text=DIFF, status_code=200)
        self.gemini = gemini

    def __enter__(self):
        gem = (patch("reviews.llm_reviewer._call_gemini", side_effect=self.gemini) if isinstance(self.gemini, BaseException)
               else patch("reviews.llm_reviewer._call_gemini", return_value=self.gemini))
        self.patches = [patch("reviews.llm_reviewer._get_github_client", return_value=self.gh),
                        patch("reviews.llm_reviewer.http_requests.get", return_value=self.http), gem]
        self.mocks = [p.start() for p in self.patches]
        self.get = self.mocks[1]
        return self

    def __exit__(self, *exc):
        for p in self.patches:
            p.stop()


def run(review):
    run_llm_review.delay(review.pk)                                                   # eager in tests, same code path as a worker
    review.refresh_from_db()
    return review


def test_successful_review_saves_everything_and_posts(review):
    with Env() as env:
        run(review)
    assert review.status == "completed" and review.error_message == "" and review.github_post_error == ""
    assert review.summary == "Found a problem." and review.files_reviewed == 1
    assert (review.input_tokens, review.output_tokens, review.llm_model) == (100, 50, review.llm_model) and review.llm_model
    assert review.github_review_id == 4242 and review.posted_at is not None
    assert review.health_score is not None and review.health_grade
    comments = ReviewComment.objects.filter(review=review)
    assert {c.source for c in comments} == {"llm", "static"}
    assert {"TS-PY-001", "TS-PY-005"} <= set(comments.filter(source="static").values_list("rule_id", flat=True))
    llm = comments.get(source="llm")
    assert (llm.file_path, llm.line_number, llm.severity, llm.message, llm.suggestion) == ("app.py", 6, "warning", "go() ignores its inputs.", "Use them.")
    assert env.gh_pr.create_review.call_count == 1                                    # one review posted, to the mock


def test_diff_is_downloaded_with_the_installation_token_for_private_repos(review):
    with Env() as env:
        run(review)
    url = env.get.call_args.args[0]
    headers = env.get.call_args.kwargs["headers"]
    assert url == "https://api.github.com/repos/o/r/pulls/3"
    assert headers["Authorization"] == "Bearer ghs_installation_token" and "diff" in headers["Accept"]


def test_a_refused_diff_endpoint_falls_back_to_the_file_list(review):
    with Env() as env:
        env.http.status_code = 406                                                    # diff too large for the diff endpoint
        env.gh_pr.get_files.return_value = [MagicMock(filename="app.py", patch=DIFF.split("+++ b/app.py\n")[1])]
        run(review)
    assert review.status == "completed" and ReviewComment.objects.filter(review=review, source="static").exists()


# ── Gemini ──────────────────────────────────────────────────────────────────
def test_gemini_failure_is_recorded_and_nothing_is_faked(review):
    with Env(gemini=RuntimeError("404 models/gemini-x is not found for API version v1beta")) as env:
        run(review)
    assert review.status == "failed"
    assert "RuntimeError" in review.error_message and "models/gemini-x is not found" in review.error_message
    assert not ReviewComment.objects.filter(review=review).exists() and review.summary == ""
    assert review.health_score is None and review.github_review_id is None
    assert env.gh_pr.create_review.call_count == 0                                    # nothing posted to GitHub


def test_unparseable_gemini_output_fails_the_review_with_the_reason(review):
    with Env(gemini=("this is not json", 10, 5)):
        run(review)
    assert review.status == "failed" and review.error_message and not review.comments.exists()


def quota_error():
    return type("ResourceExhausted", (Exception,), {"__module__": "google.api_core.exceptions"})("429 quota exceeded")


def test_gemini_quota_errors_wait_for_a_retry_and_show_why(review):
    from celery.exceptions import Retry
    with Env(gemini=quota_error()), patch.object(run_llm_review, "retry", side_effect=Retry("scheduled")):
        run_llm_review.apply(args=[review.pk], retries=0, throw=False)                # first attempt, retry is scheduled
    review.refresh_from_db()
    assert review.status == "pending"
    assert "Temporary error" in review.error_message and "quota exceeded" in review.error_message and "Retrying in 60s" in review.error_message


def test_when_retries_run_out_the_review_fails_with_the_real_error(review):
    with Env(gemini=quota_error()):
        run_llm_review.apply(args=[review.pk], retries=3, throw=False)                # last allowed attempt
    review.refresh_from_db()
    assert review.status == "failed"                                                   # never left "running" forever
    assert "Gave up after 4 attempts" in review.error_message and "quota exceeded" in review.error_message
    assert review.finished_at is not None


def test_missing_gemini_key_is_explained(review):
    with Env(), patch("reviews.llm_reviewer.GEMINI_API_KEY", ""), \
         patch("reviews.llm_reviewer._call_gemini", side_effect=RuntimeError("GEMINI_API_KEY is not configured.")):
        run(review)
    assert review.status == "failed" and "GEMINI_API_KEY is not configured" in review.error_message


# ── Tree-sitter ─────────────────────────────────────────────────────────────
def test_tree_sitter_failure_is_recorded_and_the_ai_review_still_runs(review):
    with Env(), patch("reviews.tree_sitter_analyzer.analyze_python", side_effect=ValueError("grammar exploded")):
        run(review)
    assert review.status == "completed"
    assert any("Tree-sitter could not analyse app.py" in w and "grammar exploded" in w for w in review.analysis_warnings)
    assert set(review.comments.values_list("source", flat=True)) == {"llm"}


def test_clean_run_has_no_warnings(review):
    with Env():
        run(review)
    assert review.analysis_warnings == []


# ── GitHub posting ──────────────────────────────────────────────────────────
def test_github_permission_error_keeps_the_analysis_and_shows_the_error(review):
    err = GithubException(403, {"message": "Resource not accessible by integration"}, {})
    with Env(post_error=err):
        run(review)
    assert review.status == "completed" and review.github_review_id is None and review.posted_at is None
    assert "403" in review.github_post_error and "Resource not accessible by integration" in review.github_post_error
    assert review.comments.count() >= 2                                               # findings are still saved


def test_a_retried_review_does_not_duplicate_its_findings(review):
    ReviewComment.objects.create(review=review, file_path="old.py", line_number=1, message="stale finding", source="llm")
    with Env():
        run(review)
    assert not review.comments.filter(file_path="old.py").exists()
    assert review.comments.filter(source="llm").count() == 1


def test_a_completed_review_is_not_run_or_posted_twice(review):
    with Env() as env:
        run(review)
        run(review)
    assert env.gh_pr.create_review.call_count == 1
