"""Small fake GitHub objects shared by the sync tests (no MagicMock surprises)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace as NS

from github import GithubException

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def gh_pr(number, *, title="Add feature", state="open", merged=False, sha=None, login="dev",
          body="Describes the change", head_ref="feature/x", base_ref="main", draft=False):
    return NS(
        number=number, id=9000 + number, title=title, body=body, state=state,
        merged_at=NOW if merged else None, closed_at=NOW if state == "closed" else None,
        created_at=NOW, updated_at=NOW, draft=draft,
        html_url=f"https://github.com/o/r/pull/{number}", user=NS(login=login),
        head=NS(sha=sha or f"{number:040d}", ref=head_ref), base=NS(ref=base_ref),
    )


class PagedList:
    """Behaves like PyGithub's PaginatedList: pages are fetched lazily while iterating."""

    def __init__(self, items, per_page=100):
        self.items, self.per_page, self.pages_fetched = list(items), per_page, 0

    def __iter__(self):
        for start in range(0, len(self.items), self.per_page):
            self.pages_fetched += 1
            yield from self.items[start:start + self.per_page]


class FakeRepo:
    def __init__(self, open_prs=(), other_prs=(), default_branch="main"):
        self.open_prs = open_prs if isinstance(open_prs, PagedList) else PagedList(open_prs)
        self.by_number = {p.number: p for p in [*self.open_prs.items, *other_prs]}
        self.default_branch = default_branch
        self.get_pulls_kwargs = None

    def get_pulls(self, **kwargs):
        self.get_pulls_kwargs = kwargs
        return self.open_prs

    def get_pull(self, number):
        if number not in self.by_number:
            raise GithubException(404, {"message": "Not Found"}, {})
        return self.by_number[number]


class FakeClient:
    def __init__(self, repos):
        self.repos = repos  # {"owner/name": FakeRepo}

    def get_repo(self, full_name):
        if full_name not in self.repos:
            raise GithubException(404, {"message": "Not Found"}, {})
        return self.repos[full_name]
