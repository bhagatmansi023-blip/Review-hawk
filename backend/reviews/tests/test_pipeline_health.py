"""
Full-pipeline test: Tree-sitter findings and AI findings are saved together,
the PR health score is stored, and the health block is posted to GitHub.
All network calls are mocked.
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model

from repos.models import PullRequest, Repository
from reviews.models import Review, ReviewComment

User = get_user_model()
pytestmark = pytest.mark.django_db

SOURCE = 'import os\n\nAPI_KEY = "abcd1234secret"\n\ndef go():\n    return 1\n'
DIFF = (
    "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -0,0 +1,6 @@\n"
    "+import os\n+\n+API_KEY = \"abcd1234secret\"\n+\n+def go():\n+    return 1\n"
)
GEMINI = json.dumps({
    "summary": "Found a problem.", "score": 4, "security_flags": [],
    "comments": [{"file_path": "app.py", "line_number": 6, "severity": "warning",
                  "category": "bug", "message": "go() ignores its inputs.", "suggestion": "Use them."}],
})


def test_tree_sitter_and_ai_findings_saved_together_with_health_score():
    user = User.objects.create_user(username="u", password="x")
    repo = Repository.objects.create(user=user, github_repo_id=1, owner="o", name="r", is_enabled=True)
    pr = PullRequest.objects.create(repository=repo, number=3, title="Add app", author="dev", latest_head_sha="c" * 40)
    review = Review.objects.create(pull_request=pr, head_sha="c" * 40, installation_id=5)

    gh_review = MagicMock(id=4242)
    gh_pr = MagicMock(body="", diff_url="https://example.test/diff")
    gh_pr.create_review.return_value = gh_review
    gh_repo = MagicMock()
    gh_repo.get_pull.return_value = gh_pr
    gh_repo.get_contents.return_value = MagicMock(decoded_content=SOURCE.encode())
    gh = MagicMock()
    gh.get_repo.return_value = gh_repo
    resp = MagicMock(text=DIFF)

    with patch("reviews.llm_reviewer._get_github_client", return_value=gh), \
         patch("reviews.llm_reviewer.http_requests.get", return_value=resp), \
         patch("reviews.llm_reviewer._call_gemini", return_value=(GEMINI, 100, 50)):
        from reviews.llm_reviewer import run_review
        run_review(review.id)

    review.refresh_from_db()
    assert review.status == Review.Status.COMPLETED

    sources = set(ReviewComment.objects.filter(review=review).values_list("source", flat=True))
    assert sources == {"llm", "static"}                                   # both detectors show up
    rules = set(ReviewComment.objects.filter(review=review, source="static").values_list("rule_id", flat=True))
    assert {"TS-PY-001", "TS-PY-005"} <= rules                            # unused import + hardcoded secret

    assert review.health_score is not None and review.health_score < 90
    codes = {s["code"] for s in review.health_report["signals"]}
    assert {"STATIC_HARDCODED_SECRETS", "LLM_WARNING_FINDINGS"} <= codes

    posted_body = gh_pr.create_review.call_args.kwargs["body"]
    assert "PR Health" in posted_body
