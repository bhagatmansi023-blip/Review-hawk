"""
reviews/tests/test_api_views.py
===============================
Unit and integration tests for PR, Review, and Dashboard REST APIs.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from repos.models import PullRequest, Repository
from reviews.models import Review, ReviewComment

User = get_user_model()


class TestDashboardAndPRAPIs(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="testdev", password="password123")
        self.client.force_authenticate(user=self.user)

        self.repo = Repository.objects.create(
            user=self.user,
            github_repo_id=12345,
            owner="octo-org",
            name="demo-service",
            is_enabled=True,
        )

        self.pr = PullRequest.objects.create(
            repository=self.repo,
            number=101,
            title="Refactor auth token validation",
            author="octo-dev",
            state="open",
            latest_head_sha="deadbeef1234",
        )

        self.review = Review.objects.create(
            pull_request=self.pr,
            head_sha="deadbeef1234",
            status=Review.Status.COMPLETED,
            summary="Review completed. 1 warning found.",
            llm_model="gemini-2.5-flash",
            input_tokens=1500,
            output_tokens=300,
            files_reviewed=2,
        )

        self.comment = ReviewComment.objects.create(
            review=self.review,
            file_path="auth.py",
            line_number=25,
            severity=ReviewComment.Severity.WARNING,
            category=ReviewComment.Category.SECURITY,
            message="[TS-PY-005] Hardcoded token detected",
            suggestion="os.environ.get('AUTH_TOKEN')",
            source=ReviewComment.Source.STATIC,
            rule_id="TS-PY-005",
            posted=True,
        )

    def test_dashboard_stats_endpoint(self):
        """GET /api/dashboard/stats/ returns aggregated metrics."""
        response = self.client.get("/api/dashboard/stats/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["connected_repos_count"], 1)
        self.assertEqual(data["total_prs_reviewed"], 1)
        self.assertEqual(data["total_findings_count"], 1)
        self.assertEqual(data["findings_by_severity"]["warning"], 1)
        self.assertEqual(len(data["recent_activity"]), 1)
        self.assertEqual(data["recent_activity"][0]["pr_title"], "Refactor auth token validation")

    def test_pull_requests_list_endpoint(self):
        """GET /api/pull-requests/ returns list with embedded latest review."""
        response = self.client.get("/api/pull-requests/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        results = data.get("results", data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Refactor auth token validation")
        self.assertIsNotNone(results[0]["latest_review"])
        self.assertEqual(results[0]["latest_review"]["status"], "completed")

    def test_nested_repo_pulls_list_endpoint(self):
        """GET /api/repos/<repo_id>/pulls/ returns PRs for specific repo."""
        response = self.client.get(f"/api/repos/{self.repo.id}/pulls/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        results = data.get("results", data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["number"], 101)

    def test_pull_request_detail_endpoint(self):
        """GET /api/pull-requests/<id>/ returns full PR + review findings."""
        response = self.client.get(f"/api/pull-requests/{self.pr.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["id"], self.pr.id)
        self.assertEqual(data["repository"]["full_name"], "octo-org/demo-service")
        self.assertEqual(data["latest_review"]["llm_model"], "gemini-2.5-flash")
        self.assertEqual(len(data["latest_review"]["comments"]), 1)
        self.assertEqual(data["latest_review"]["comments"][0]["rule_id"], "TS-PY-005")

    def test_review_detail_endpoint(self):
        """GET /api/reviews/<id>/ returns review execution details."""
        response = self.client.get(f"/api/reviews/{self.review.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["id"], self.review.id)
        self.assertEqual(data["total_tokens"], 1800)
