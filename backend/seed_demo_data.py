"""
seed_demo_data.py — Run once to populate demo PRs + reviews + findings.

Usage:
    cd backend
    .\venv\Scripts\python seed_demo_data.py

Creates realistic-looking demo data across your connected repositories
so the dashboard, PR list, PR details, health cards, and findings panels
all render correctly for your presentation.
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

# ── Pick real repos from DB ──────────────────────────────────────────────────
repos = list(Repository.objects.filter(is_enabled=True))
if not repos:
    print("❌  No enabled repositories found. Connect a repo first via the dashboard.")
    sys.exit(1)

print(f"📦  Found {len(repos)} enabled repos: {[r.full_name for r in repos]}")

# ── Demo PR definitions ──────────────────────────────────────────────────────
DEMO_PRS = [
    {
        "number": 101,
        "title": "feat: add user authentication with OAuth2",
        "author": "alice-dev",
        "state": "open",
        "sha": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
    },
    {
        "number": 102,
        "title": "fix: resolve database connection pooling leak",
        "author": "bob-engineer",
        "state": "open",
        "sha": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1",
    },
    {
        "number": 103,
        "title": "refactor: migrate API endpoints to REST conventions",
        "author": "carol-backend",
        "state": "merged",
        "sha": "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2",
    },
    {
        "number": 104,
        "title": "chore: upgrade dependencies and fix security vulnerabilities",
        "author": "dave-ops",
        "state": "open",
        "sha": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3",
    },
    {
        "number": 105,
        "title": "feat: implement real-time notifications via WebSockets",
        "author": "eve-fullstack",
        "state": "closed",
        "sha": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4",
    },
]

# ── Demo review findings (comments) ─────────────────────────────────────────
DEMO_COMMENTS = [
    # Static / tree-sitter findings
    {
        "source": "static", "rule_id": "TS-PY-001", "severity": "warning",
        "category": "maintainability", "file_path": "src/auth/oauth.py", "line_number": 3,
        "message": "Unused import: 'os' is imported but never used in this module.",
        "suggestion": "Remove the unused import to keep the code clean.",
    },
    {
        "source": "static", "rule_id": "TS-PY-003", "severity": "error",
        "category": "bug", "file_path": "src/auth/oauth.py", "line_number": 45,
        "message": "Bare except clause catches all exceptions including SystemExit and KeyboardInterrupt.",
        "suggestion": "Use 'except Exception:' instead of bare 'except:'.",
    },
    {
        "source": "static", "rule_id": "TS-PY-005", "severity": "error",
        "category": "security", "file_path": "src/config/settings.py", "line_number": 12,
        "message": "Hardcoded secret detected: API_KEY = 'sk-live-abc123...' (CWE-798).",
        "suggestion": "Move secrets to environment variables or a .env file.",
    },
    {
        "source": "static", "rule_id": "TS-PY-002", "severity": "info",
        "category": "maintainability", "file_path": "src/services/data_processor.py", "line_number": 15,
        "message": "Function 'process_batch' is 73 lines long (exceeds 50-line threshold).",
        "suggestion": "Consider breaking this function into smaller, focused helper functions.",
    },
    {
        "source": "static", "rule_id": "TS-PY-004", "severity": "warning",
        "category": "maintainability", "file_path": "src/services/data_processor.py", "line_number": 38,
        "message": "Deep nesting detected: 5 levels of indentation (threshold is 4).",
        "suggestion": "Use early returns or extract nested logic into separate functions.",
    },
    # LLM / AI findings
    {
        "source": "llm", "rule_id": "", "severity": "error",
        "category": "security", "file_path": "src/api/endpoints.py", "line_number": 22,
        "message": "SQL injection vulnerability: user input is concatenated directly into a query string without parameterization.",
        "suggestion": "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = %s', [user_id])",
    },
    {
        "source": "llm", "rule_id": "", "severity": "warning",
        "category": "performance", "file_path": "src/api/endpoints.py", "line_number": 58,
        "message": "N+1 query pattern detected: database query inside a loop will cause performance degradation with large datasets.",
        "suggestion": "Use select_related() or prefetch_related() to batch the queries.",
    },
    {
        "source": "llm", "rule_id": "", "severity": "warning",
        "category": "bug", "file_path": "src/models/user.py", "line_number": 31,
        "message": "Potential race condition: checking and updating the counter is not atomic, which may lead to data inconsistency under concurrent access.",
        "suggestion": "Use F() expressions or database-level locks for atomic counter updates.",
    },
    {
        "source": "llm", "rule_id": "", "severity": "info",
        "category": "style", "file_path": "src/utils/helpers.py", "line_number": 7,
        "message": "Variable name 'x' is not descriptive. Consider using a meaningful name that describes its purpose.",
        "suggestion": "Rename to something like 'retry_count' or 'batch_size'.",
    },
    {
        "source": "llm", "rule_id": "", "severity": "info",
        "category": "maintainability", "file_path": "src/utils/helpers.py", "line_number": 19,
        "message": "This function lacks a docstring. Adding documentation improves code maintainability.",
        "suggestion": "Add a docstring explaining the function's purpose, parameters, and return value.",
    },
]

# ── Health report template ──────────────────────────────────────────────────
def make_health_report(score, grade, errors, warnings, infos):
    return {
        "summary": f"Code health score: {score}/100 ({grade})",
        "signals": {
            "critical_issues": errors,
            "warnings": warnings,
            "info_notes": infos,
            "security_issues": 1 if errors > 0 else 0,
        },
        "badges": [
            {"label": "Security", "status": "fail" if errors > 0 else "pass"},
            {"label": "Maintainability", "status": "warn" if warnings > 1 else "pass"},
            {"label": "Performance", "status": "pass"},
            {"label": "Style", "status": "pass"},
        ],
        "tips": [
            "Address all security findings before merging.",
            "Consider adding unit tests for the new authentication flow.",
        ],
    }

# ── Create data ──────────────────────────────────────────────────────────────
created_prs = 0
created_reviews = 0
created_comments = 0

for i, pr_def in enumerate(DEMO_PRS):
    # Spread PRs across available repos
    repo = repos[i % len(repos)]

    pr, pr_created = PullRequest.objects.get_or_create(
        repository=repo,
        number=pr_def["number"],
        defaults={
            "title": pr_def["title"],
            "author": pr_def["author"],
            "state": pr_def["state"],
            "html_url": f"https://github.com/{repo.full_name}/pull/{pr_def['number']}",
            "latest_head_sha": pr_def["sha"],
        },
    )
    if pr_created:
        # Backdate slightly so time-series charts have data spread
        pr.created_at = now - timedelta(days=random.randint(1, 14), hours=random.randint(0, 12))
        PullRequest.objects.filter(pk=pr.pk).update(created_at=pr.created_at)
        created_prs += 1
        print(f"  ✅ Created PR #{pr_def['number']} on {repo.full_name}")
    else:
        print(f"  ℹ️  PR #{pr_def['number']} already exists on {repo.full_name}")

    # ── Review (completed, with health data) ──────────────────────────────
    # Pick a subset of comments for this review
    num_comments = random.randint(3, len(DEMO_COMMENTS))
    selected_comments = random.sample(DEMO_COMMENTS, num_comments)

    errors = sum(1 for c in selected_comments if c["severity"] == "error")
    warnings = sum(1 for c in selected_comments if c["severity"] == "warning")
    infos = sum(1 for c in selected_comments if c["severity"] == "info")

    # Health score: fewer errors = higher score
    score = max(0, 100 - (errors * 20) - (warnings * 8) - (infos * 2))
    if score >= 95: grade = "A+"
    elif score >= 85: grade = "A"
    elif score >= 70: grade = "B"
    elif score >= 55: grade = "C"
    elif score >= 40: grade = "D"
    else: grade = "F"

    started = now - timedelta(days=random.randint(0, 7), minutes=random.randint(5, 120))
    finished = started + timedelta(seconds=random.randint(8, 45))

    review, rev_created = Review.objects.get_or_create(
        pull_request=pr,
        head_sha=pr_def["sha"],
        defaults={
            "status": Review.Status.COMPLETED,
            "summary": f"Automated review found {errors} error(s), {warnings} warning(s), and {infos} info note(s). "
                       f"Overall code health: {grade} ({score}/100).",
            "llm_model": "gemini-2.0-flash",
            "input_tokens": random.randint(2000, 8000),
            "output_tokens": random.randint(500, 2000),
            "files_reviewed": random.randint(3, 12),
            "health_score": score,
            "health_grade": grade,
            "health_report": make_health_report(score, grade, errors, warnings, infos),
            "started_at": started,
            "finished_at": finished,
        },
    )
    if rev_created:
        # Backdate to match PR
        Review.objects.filter(pk=review.pk).update(created_at=pr.created_at + timedelta(minutes=5))
        created_reviews += 1
        print(f"    📝 Created Review (score={score}, grade={grade}, {num_comments} findings)")
    else:
        print(f"    ℹ️  Review already exists for this SHA")
        continue  # don't re-create comments

    # ── Comments ─────────────────────────────────────────────────────────
    for c_def in selected_comments:
        ReviewComment.objects.create(
            review=review,
            file_path=c_def["file_path"],
            line_number=c_def["line_number"],
            severity=c_def["severity"],
            category=c_def["category"],
            message=c_def["message"],
            suggestion=c_def.get("suggestion", ""),
            source=c_def["source"],
            rule_id=c_def.get("rule_id", ""),
            posted=True,
        )
        created_comments += 1

print(f"\n🎉  Done! Created {created_prs} PRs, {created_reviews} reviews, {created_comments} comments.")
print(f"    Open http://localhost:5173/pull-requests to see them.\n")
