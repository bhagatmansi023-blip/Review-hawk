"""
Django management command: sync_repos

Synchronize enabled GitHub repositories:
1. Obtain the connected user's GitHub OAuth client.
2. Ensure the repository webhook exists.
3. Import currently open pull requests and queue reviews for new head SHAs.

Usage:
    python manage.py sync_repos
"""

from __future__ import annotations

import logging

from allauth.socialaccount.models import SocialToken
from django.core.management.base import BaseCommand
from github import Github, GithubException

from repos.models import Repository
from reviews.sync import ensure_repo_webhook, sync_open_pull_requests

logger = logging.getLogger(__name__)


def _get_github_client(db_repo: Repository) -> Github | None:
    """Return an authenticated GitHub client for the repository owner."""
    token_obj = (
        SocialToken.objects.filter(
            account__user=db_repo.user,
            account__provider="github",
        )
        .order_by("-expires_at")
        .first()
    )

    if not token_obj:
        return None

    return Github(token_obj.token)


class Command(BaseCommand):
    help = "Register GitHub webhooks and synchronize open pull requests."

    def add_arguments(self, parser):
        parser.add_argument(
            "--repo",
            type=str,
            default=None,
            help="Only sync one repository (format: owner/name).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of open PRs to import per repository.",
        )

    def handle(self, *args, **options):
        repo_filter = options["repo"]
        limit = options["limit"]

        repos = Repository.objects.filter(is_enabled=True).select_related("user")

        if repo_filter:
            parts = repo_filter.split("/", 1)
            if len(parts) != 2:
                self.stderr.write(
                    self.style.ERROR(
                        f"Invalid repository '{repo_filter}'. Use owner/name."
                    )
                )
                return

            repos = repos.filter(owner=parts[0], name=parts[1])

        repos = list(repos)
        self.stdout.write(f"Synchronizing {len(repos)} enabled repository/repositories.")

        total_imported = 0

        for db_repo in repos:
            self.stdout.write(f"\n--- {db_repo.full_name} ---")

            try:
                gh = _get_github_client(db_repo)
                if gh is None:
                    self.stderr.write(
                        f"  No GitHub OAuth token for {db_repo.user.username}; skipping."
                    )
                    continue

                gh_repo = gh.get_repo(db_repo.full_name)

                webhook_message = ensure_repo_webhook(gh_repo, db_repo)
                self.stdout.write(f"  Webhook: {webhook_message}")

                imported = sync_open_pull_requests(
                    gh_repo,
                    db_repo,
                    limit=limit,
                )
                total_imported += imported
                self.stdout.write(f"  Imported/updated {imported} open PR(s).")

            except GithubException as exc:
                logger.exception("GitHub sync failed for %s", db_repo.full_name)
                self.stderr.write(
                    f"  GitHub error for {db_repo.full_name}: {exc}"
                )
            except Exception as exc:
                logger.exception("Repository sync failed for %s", db_repo.full_name)
                self.stderr.write(
                    f"  Could not sync {db_repo.full_name}: {exc}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSync complete. {total_imported} open PR(s) imported/updated."
            )
        )
