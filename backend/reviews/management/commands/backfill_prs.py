"""
Management command: backfill_prs
================================
Fetches real open (and optionally closed/merged) pull requests from GitHub
for all connected repositories and saves them to the database.

Usage:
    python manage.py backfill_prs
    python manage.py backfill_prs --state all --limit 20 --review
    python manage.py backfill_prs --repo bawahemangi/AgriDefenderX --review
"""
from __future__ import annotations

import logging

from django.core.management.base import BaseCommand, CommandError

from allauth.socialaccount.models import SocialToken
from github import Github, GithubException

from repos.models import Repository, PullRequest
from reviews.models import Review

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Backfill real GitHub pull requests for all connected repositories."

    def add_arguments(self, parser):
        parser.add_argument(
            "--repo",
            type=str,
            default=None,
            help="Only backfill a specific repo (format: owner/name). Default: all enabled repos.",
        )
        parser.add_argument(
            "--state",
            type=str,
            default="open",
            choices=["open", "closed", "all"],
            help="PR state to fetch: open (default), closed, all.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help="Max PRs to import per repo (default: 10).",
        )
        parser.add_argument(
            "--review",
            action="store_true",
            default=False,
            help="Queue an AI review for each newly imported PR.",
        )
        parser.add_argument(
            "--force-review",
            action="store_true",
            default=False,
            help="Re-queue review even if one already exists for that SHA.",
        )

    def handle(self, *args, **options):
        state = options["state"]
        limit = options["limit"]
        do_review = options["review"]
        force_review = options["force_review"]
        repo_filter = options["repo"]

        # Get repos to process
        qs = Repository.objects.filter(is_enabled=True).select_related("user")
        if repo_filter:
            parts = repo_filter.split("/", 1)
            if len(parts) != 2:
                raise CommandError(f"Invalid --repo format '{repo_filter}'. Use 'owner/name'.")
            qs = qs.filter(owner=parts[0], name=parts[1])
            if not qs.exists():
                raise CommandError(f"Repo '{repo_filter}' not found or not enabled in DB.")

        repos = list(qs)
        self.stdout.write(f"Processing {len(repos)} repo(s), state={state}, limit={limit}")

        total_prs = 0
        total_reviews = 0

        for db_repo in repos:
            self.stdout.write(f"\n--- {db_repo.full_name} ---")

            # Get OAuth token for this repo's owner
            token_obj = (
                SocialToken.objects.filter(
                    account__user=db_repo.user,
                    account__provider="github",
                )
                .order_by("-expires_at")
                .first()
            )
            if not token_obj:
                self.stderr.write(f"  No GitHub token for user '{db_repo.user.username}' — skipping.")
                continue

            gh = Github(token_obj.token)

            try:
                gh_repo = gh.get_repo(db_repo.full_name)
            except GithubException as exc:
                self.stderr.write(f"  Cannot access repo on GitHub: {exc} — skipping.")
                continue

            imported = 0
            try:
                import itertools
                pulls = gh_repo.get_pulls(state=state, sort="updated", direction="desc")
                for gh_pr in itertools.islice(pulls, limit):
                    # Determine state (GitHub uses 'closed' for both closed and merged)
                    pr_state = "open"
                    if gh_pr.state == "closed":
                        pr_state = "merged" if gh_pr.merged else "closed"

                    db_pr, created = PullRequest.objects.update_or_create(
                        repository=db_repo,
                        number=gh_pr.number,
                        defaults={
                            "title": gh_pr.title[:500],
                            "author": (gh_pr.user.login if gh_pr.user else "unknown")[:100],
                            "state": pr_state,
                            "html_url": gh_pr.html_url,
                            "latest_head_sha": gh_pr.head.sha,
                            "github_pr_id": gh_pr.id,
                            "body": gh_pr.body or "",
                            "source_branch": (gh_pr.head.ref or "")[:200],
                            "target_branch": (gh_pr.base.ref or "")[:200],
                            "is_draft": gh_pr.draft or False,
                            "additions": gh_pr.additions,
                            "deletions": gh_pr.deletions,
                            "changed_files_count": gh_pr.changed_files,
                            "github_created_at": gh_pr.created_at,
                            "github_updated_at": gh_pr.updated_at,
                            "closed_at": gh_pr.closed_at,
                            "merged_at": gh_pr.merged_at,
                        },
                    )
                    status_str = "CREATED" if created else "UPDATED"
                    self.stdout.write(
                        f"  [{status_str}] PR #{gh_pr.number}: {gh_pr.title[:60]}"
                    )
                    imported += 1
                    total_prs += 1

                    # Queue AI review
                    if do_review and pr_state == "open":
                        head_sha = gh_pr.head.sha
                        existing = Review.objects.filter(
                            pull_request=db_pr, head_sha=head_sha
                        ).first()

                        if existing and not force_review:
                            self.stdout.write(
                                f"    Review already exists (status={existing.status}) — skipping. Use --force-review to re-run."
                            )
                            continue

                        if existing and force_review:
                            # Reset failed/pending reviews so they run again
                            if existing.status in (Review.Status.FAILED, Review.Status.PENDING):
                                existing.status = Review.Status.PENDING
                                existing.error_message = ""
                                existing.save(update_fields=["status", "error_message"])
                                review = existing
                            else:
                                self.stdout.write(f"    Review status={existing.status} — skipping.")
                                continue
                        else:
                            review, _ = Review.objects.get_or_create(
                                pull_request=db_pr,
                                head_sha=head_sha,
                                defaults={"status": Review.Status.PENDING},
                            )

                        from reviews.tasks import run_llm_review
                        run_llm_review.delay(review.pk)
                        self.stdout.write(f"    Queued AI review (review_id={review.pk})")
                        total_reviews += 1

            except GithubException as exc:
                self.stderr.write(f"  GitHub error: {exc} — partial import ({imported} PRs).")

            self.stdout.write(f"  Imported {imported} PRs.")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {total_prs} PRs imported/updated, {total_reviews} reviews queued."
            )
        )
