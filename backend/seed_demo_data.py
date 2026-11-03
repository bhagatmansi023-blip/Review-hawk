"""
seed_demo_data.py
=================
Seeds realistic-looking PRs, reviews, and findings into the database using
the REAL connected repositories already in the DB.  Safe to run multiple times
(uses get_or_create everywhere).

Run:
    python seed_demo_data.py
"""
import os, sys, django, random
from datetime import timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from django.utils import timezone
from repos.models import Repository, PullRequest
from reviews.models import Review, ReviewComment

now = timezone.now()

# Real connected repos
repos = list(Repository.objects.filter(is_enabled=True).order_by("id"))
if not repos:
    print("No enabled repos — connect at least one first.")
    sys.exit(1)

print(f"Using {len(repos)} repos: {[r.full_name for r in repos]}")

# ---------------------------------------------------------------------------
# Demo PRs — spread across repos
# ---------------------------------------------------------------------------
DEMO_PRS = [
    {
        "number": 1,
        "title": "feat: add OAuth2 authentication with GitHub provider",
        "author": "bawahemangi",
        "state": "open",
        "sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "body": "Implements GitHub OAuth2 login flow using django-allauth. Adds social token storage and session management.",
    },
    {
        "number": 2,
        "title": "fix: resolve N+1 query in pull request list endpoint",
        "author": "bawahemangi",
        "state": "open",
        "sha": "b2c3d4e5f6b2c3d4e5f6b2c3d4e5f6b2c3d4e5f6",
        "body": "The /api/repos/<id>/pulls/ endpoint was issuing one DB query per PR to fetch the latest review. Fixed with select_related and prefetch_related.",
    },
    {
        "number": 3,
        "title": "feat: integrate Google Gemini LLM for automated code review",
        "author": "bawahemangi",
        "state": "merged",
        "sha": "c3d4e5f6c3d4e5f6c3d4e5f6c3d4e5f6c3d4e5f6",
        "body": "Adds the core AI review engine using Gemini 2.5 Flash. Parses PR diffs, calls the LLM, and posts inline comments back to GitHub.",
    },
    {
        "number": 4,
        "title": "chore: upgrade dependencies and patch CVE-2024-35195",
        "author": "bawahemangi",
        "state": "open",
        "sha": "d4e5f6d4e5f6d4e5f6d4e5f6d4e5f6d4e5f6d4e5",
        "body": "Updates requests, PyGithub, and django to latest versions. Patches a known security vulnerability in the requests library.",
    },
    {
        "number": 5,
        "title": "feat: add tree-sitter static analysis for Python files",
        "author": "bawahemangi",
        "state": "open",
        "sha": "e5f6e5f6e5f6e5f6e5f6e5f6e5f6e5f6e5f6e5f6",
        "body": "Integrates tree-sitter to detect unused imports, bare excepts, deep nesting, long functions, and hardcoded secrets in Python code.",
    },
    {
        "number": 6,
        "title": "fix: handle webhook signature verification edge cases",
        "author": "bawahemangi",
        "state": "merged",
        "sha": "f6f7f8f6f7f8f6f7f8f6f7f8f6f7f8f6f7f8f6f7",
        "body": "Fixes a bug where empty webhook secret caused all deliveries to be rejected. Adds proper error logging.",
    },
]

# ---------------------------------------------------------------------------
# Finding templates — will be mixed per review
# ---------------------------------------------------------------------------
ALL_FINDINGS = [
    # Static (tree-sitter)
    dict(source="static", rule_id="TS-PY-001", severity="warning", category="maintainability",
         file_path="src/api/views.py", line_number=12,
         message="Unused import: 'os' imported but never used.",
         suggestion="Remove the unused import statement."),
    dict(source="static", rule_id="TS-PY-003", severity="error", category="bug",
         file_path="src/api/views.py", line_number=58,
         message="Bare `except:` clause catches all exceptions including SystemExit.",
         suggestion="Use `except Exception:` to avoid catching system signals."),
    dict(source="static", rule_id="TS-PY-005", severity="error", category="security",
         file_path="src/config/settings_local.py", line_number=4,
         message="Hardcoded secret detected: SECRET_KEY = 'django-insecure-...' (CWE-798).",
         suggestion="Move secrets to environment variables and load with python-decouple."),
    dict(source="static", rule_id="TS-PY-002", severity="info", category="maintainability",
         file_path="src/services/processor.py", line_number=22,
         message="Function 'process_pull_request' is 78 lines (threshold: 50).",
         suggestion="Break into smaller helper functions for readability."),
    dict(source="static", rule_id="TS-PY-004", severity="warning", category="maintainability",
         file_path="src/services/processor.py", line_number=45,
         message="Deep nesting: 5 levels of indentation detected (threshold: 4).",
         suggestion="Use early returns or extract nested logic into separate functions."),
    # LLM (AI review)
    dict(source="llm", rule_id="", severity="error", category="security",
         file_path="src/api/auth.py", line_number=34,
         message="SQL injection risk: user input directly concatenated into query string without parameterization.",
         suggestion="Use parameterized queries: `cursor.execute('SELECT * FROM users WHERE id = %s', [user_id])`"),
    dict(source="llm", rule_id="", severity="warning", category="performance",
         file_path="src/api/views.py", line_number=91,
         message="N+1 query pattern: DB query inside a loop causes O(n) database hits.",
         suggestion="Use `select_related('review')` or `prefetch_related('comments')` to batch queries."),
    dict(source="llm", rule_id="", severity="warning", category="bug",
         file_path="src/models/pull_request.py", line_number=63,
         message="Race condition: check-then-act pattern on `status` field is not atomic under concurrent requests.",
         suggestion="Use `update_or_create` with `F()` expressions or database-level locking."),
    dict(source="llm", rule_id="", severity="info", category="style",
         file_path="src/utils/helpers.py", line_number=15,
         message="Variable name `x` is not descriptive. Consider using a more meaningful name.",
         suggestion="Rename to `retry_count` or `batch_size` based on its purpose."),
    dict(source="llm", rule_id="", severity="info", category="maintainability",
         file_path="src/utils/helpers.py", line_number=28,
         message="Function lacks a docstring. Documentation improves maintainability.",
         suggestion="Add a docstring explaining parameters, return value, and side effects."),
    dict(source="llm", rule_id="", severity="warning", category="security",
         file_path="src/api/auth.py", line_number=19,
         message="Token stored in localStorage is vulnerable to XSS attacks.",
         suggestion="Use httpOnly cookies for token storage to prevent JavaScript access."),
    dict(source="llm", rule_id="", severity="error", category="bug",
         file_path="src/tasks/celery_tasks.py", line_number=47,
         message="Exception swallowed silently: `except Exception: pass` hides task failures from monitoring.",
         suggestion="At minimum log the exception: `except Exception as e: logger.exception('Task failed: %s', e)`"),
]

def health_from_findings(findings):
    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    infos = sum(1 for f in findings if f["severity"] == "info")
    score = max(0, 100 - errors * 20 - warnings * 8 - infos * 2)
    grade = (
        "A+" if score >= 95 else
        "A"  if score >= 85 else
        "B"  if score >= 70 else
        "C"  if score >= 55 else
        "D"  if score >= 40 else "F"
    )
    return score, grade, {
        "summary": f"Code health: {score}/100 ({grade}). Found {errors} critical, {warnings} warnings, {infos} notes.",
        "signals": {"critical_issues": errors, "warnings": warnings, "info_notes": infos},
        "badges": [
            {"label": "Security",        "status": "fail" if errors > 0 else "pass"},
            {"label": "Performance",     "status": "warn" if warnings > 1 else "pass"},
            {"label": "Maintainability", "status": "warn" if warnings > 0 else "pass"},
            {"label": "Style",           "status": "pass"},
        ],
        "tips": [
            "Resolve all security findings before merging.",
            "Add unit tests for the authentication flow.",
            "Run the linter as part of CI to catch style issues automatically.",
        ],
    }

# ---------------------------------------------------------------------------
# Create data
# ---------------------------------------------------------------------------
created_prs = created_reviews = created_comments = 0

for i, pr_def in enumerate(DEMO_PRS):
    repo = repos[i % len(repos)]
    pr, pr_created = PullRequest.objects.get_or_create(
        repository=repo,
        number=pr_def["number"],
        defaults=dict(
            title=pr_def["title"],
            author=pr_def["author"],
            state=pr_def["state"],
            html_url=f"https://github.com/{repo.full_name}/pull/{pr_def['number']}",
            latest_head_sha=pr_def["sha"],
        ),
    )
    if not pr_created:
        # Update state in case it changed
        pr.title = pr_def["title"]
        pr.state = pr_def["state"]
        pr.latest_head_sha = pr_def["sha"]
        pr.save(update_fields=["title", "state", "latest_head_sha", "updated_at"])

    days_ago = random.randint(1, 21)
    PullRequest.objects.filter(pk=pr.pk).update(
        created_at=now - timedelta(days=days_ago, hours=random.randint(0, 12))
    )
    created_prs += (1 if pr_created else 0)

    # Select a random subset of findings
    n = random.randint(4, min(9, len(ALL_FINDINGS)))
    selected = random.sample(ALL_FINDINGS, n)
    score, grade, health_report = health_from_findings(selected)

    started_at = now - timedelta(days=days_ago, minutes=random.randint(2, 60))
    finished_at = started_at + timedelta(seconds=random.randint(8, 45))

    review, rev_created = Review.objects.get_or_create(
        pull_request=pr,
        head_sha=pr_def["sha"],
        defaults=dict(
            status=Review.Status.COMPLETED,
            summary=(
                f"This PR introduces changes across {random.randint(3, 12)} files. "
                f"Found {sum(1 for f in selected if f['severity'] == 'error')} critical issue(s), "
                f"{sum(1 for f in selected if f['severity'] == 'warning')} warning(s). "
                f"Overall health: {grade} ({score}/100)."
            ),
            llm_model="gemini-2.5-flash",
            input_tokens=random.randint(2500, 9000),
            output_tokens=random.randint(400, 1800),
            files_reviewed=random.randint(3, 12),
            health_score=score,
            health_grade=grade,
            health_report=health_report,
            started_at=started_at,
            finished_at=finished_at,
        ),
    )

    if not rev_created:
        # Update health and status on existing review
        review.status = Review.Status.COMPLETED
        review.health_score = score
        review.health_grade = grade
        review.health_report = health_report
        review.save(update_fields=["status", "health_score", "health_grade", "health_report"])

    Review.objects.filter(pk=review.pk).update(
        created_at=now - timedelta(days=days_ago, minutes=random.randint(1, 10))
    )
    created_reviews += (1 if rev_created else 0)

    # Delete old comments then recreate for idempotency
    if not rev_created:
        review.comments.all().delete()

    for f in selected:
        ReviewComment.objects.create(
            review=review,
            file_path=f["file_path"],
            line_number=f["line_number"],
            severity=f["severity"],
            category=f["category"],
            message=f["message"],
            suggestion=f.get("suggestion", ""),
            source=f["source"],
            rule_id=f.get("rule_id", ""),
            posted=True,
        )
        created_comments += 1

    status = "CREATED" if pr_created else "UPDATED"
    print(f"[{status}] {repo.full_name} PR #{pr_def['number']}: {pr_def['title'][:55]}")
    print(f"         Review: {grade} ({score}/100), {n} findings")

print()
print(f"Done. {created_prs} new PRs, {created_reviews} new reviews, {created_comments} comments seeded.")
print(f"Open http://localhost:5173/pull-requests to see them.")
