"""
reviews/llm_reviewer.py
=======================
Core AI review engine for Review-hawk.

Responsibilities
----------------
1. Fetch the PR diff and metadata from the GitHub API.
2. Build a structured prompt for Google Gemini.
3. Parse the LLM JSON response into typed dataclasses.
4. Map each LLM comment's (file_path, line_number) to a GitHub diff *position*
   so that comments can be posted as proper inline PR review comments.
5. Persist findings to the DB (Review + ReviewComment rows).
6. Post the review back to GitHub via the Checks/Pull-Requests API.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import google.generativeai as genai
from decouple import config
from github import Github, GithubException

from repos.models import PullRequest, Repository
from reviews.models import Review, ReviewComment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GEMINI_API_KEY = config("GEMINI_API_KEY", default="")
GEMINI_MODEL = config("GEMINI_MODEL", default="gemini-2.5-flash")

# Maximum characters of diff we send to the model.  Keeps token cost sane.
MAX_DIFF_CHARS = 80_000

# ---------------------------------------------------------------------------
# Structured response types
# ---------------------------------------------------------------------------


@dataclass
class LLMComment:
    """One inline code comment produced by the LLM."""

    file_path: str
    line_number: int
    severity: str  # "info" | "warning" | "error"
    category: str  # matches ReviewComment.Category choices
    message: str
    suggestion: str = ""


@dataclass
class LLMReviewResult:
    """Full structured result from one Gemini call."""

    summary: str
    score: float  # 0-10
    comments: list[LLMComment] = field(default_factory=list)
    security_flags: list[str] = field(default_factory=list)
    raw_response: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


# ---------------------------------------------------------------------------
# Diff parsing & position mapping
# ---------------------------------------------------------------------------

_DIFF_FILE_HEADER = re.compile(r"^diff --git a/.+ b/(.+)$")
_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def build_diff_position_map(raw_diff: str) -> dict[tuple[str, int], int]:
    """
    Parse a unified diff and return a mapping:
        (file_path, new_file_line_number) -> diff_position

    *diff_position* is the 1-based sequential count of lines inside the diff
    body (excluding the ``diff --git`` / ``---`` / ``+++`` headers) that the
    GitHub API expects for inline review comments.

    Only lines present in the *new* file (i.e. context lines and ``+`` lines)
    are mapped — removed lines (``-``) have no position in the new file.
    """
    position_map: dict[tuple[str, int], int] = {}
    current_file: str | None = None
    diff_position = 0        # resets to 0 at each new file header
    new_line_number = 0      # tracks the current line in the new file

    for raw_line in raw_diff.splitlines():
        # New file diff block
        file_match = _DIFF_FILE_HEADER.match(raw_line)
        if file_match:
            current_file = file_match.group(1)
            diff_position = 0
            new_line_number = 0
            continue

        # Skip the --- / +++ header lines (don't count toward position)
        if raw_line.startswith("--- ") or raw_line.startswith("+++ "):
            continue

        # Hunk header: @@ -old_start,count +new_start,count @@
        hunk_match = _HUNK_HEADER.match(raw_line)
        if hunk_match:
            diff_position += 1
            new_line_number = int(hunk_match.group(1))
            continue

        if current_file is None:
            continue

        if raw_line.startswith("+"):
            # Added line — exists in new file
            position_map[(current_file, new_line_number)] = diff_position
            diff_position += 1
            new_line_number += 1
        elif raw_line.startswith("-"):
            # Removed line — no new_line_number advance
            diff_position += 1
        else:
            # Context line — exists in both old and new files
            position_map[(current_file, new_line_number)] = diff_position
            diff_position += 1
            new_line_number += 1

    return position_map


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are Review-hawk, an expert senior software engineer performing a \
thorough code review of a GitHub pull request.

Your goal is to identify:
- Bugs, logic errors, and edge-case failures
- Security vulnerabilities (injection, auth issues, secrets in code, etc.)
- Performance bottlenecks
- Maintainability and readability problems
- Style and convention violations

You MUST respond with a single, valid JSON object — no markdown fences, no \
extra prose.  The schema is:

{
  "summary": "<concise overall PR summary, 2-4 sentences>",
  "score": <integer 0-10, 10 = perfect>,
  "security_flags": ["<brief description of critical security issue>", ...],
  "comments": [
    {
      "file_path": "<relative file path exactly as it appears in the diff>",
      "line_number": <positive integer, line in the NEW version of the file>,
      "severity": "<info|warning|error>",
      "category": "<bug|security|performance|style|maintainability|other>",
      "message": "<clear, actionable explanation of the issue>",
      "suggestion": "<optional: concrete code fix or recommendation>"
    },
    ...
  ]
}

Rules:
- Only comment on lines that appear in the diff (changed or added lines).
- Omit the "suggestion" key if you have nothing concrete to add.
- Keep each "message" under 400 characters.
- Limit to at most 25 comments; prioritise high-severity findings.
- If the PR is clean, return an empty "comments" array and a high score.
- Do NOT wrap your JSON in markdown code fences.
"""


def _build_user_prompt(
    pr_title: str,
    pr_body: str,
    author: str,
    base_branch: str,
    head_sha: str,
    diff: str,
) -> str:
    """Compose the per-PR user message sent to Gemini."""
    truncated = diff[:MAX_DIFF_CHARS]
    if len(diff) > MAX_DIFF_CHARS:
        truncated += "\n\n[... diff truncated for length ...]"

    return f"""\
## Pull Request

**Title:** {pr_title}
**Author:** {author}
**Base branch:** {base_branch}
**Head SHA:** {head_sha[:7]}

**Description:**
{pr_body or "(no description provided)"}

---

## Unified Diff

```diff
{truncated}
```

Review the diff above and return your JSON response now.
"""


# ---------------------------------------------------------------------------
# Gemini caller
# ---------------------------------------------------------------------------


def _call_gemini(user_prompt: str) -> tuple[str, int, int]:
    """
    Send the prompt to Gemini and return (raw_text, input_tokens, output_tokens).
    Raises RuntimeError on API failure.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=SYSTEM_PROMPT,
        generation_config=genai.types.GenerationConfig(
            temperature=0.2,         # low randomness for deterministic reviews
            response_mime_type="application/json",
        ),
    )

    response = model.generate_content(user_prompt)

    raw_text = response.text or ""
    usage = response.usage_metadata
    input_tokens = getattr(usage, "prompt_token_count", 0) or 0
    output_tokens = getattr(usage, "candidates_token_count", 0) or 0

    return raw_text, input_tokens, output_tokens


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

_SEVERITY_VALUES = {"info", "warning", "error"}
_CATEGORY_VALUES = {"bug", "security", "performance", "style", "maintainability", "other"}


def _parse_llm_response(raw: str) -> LLMReviewResult:
    """
    Parse raw Gemini text into an LLMReviewResult.

    Strips markdown fences defensively (even though we ask for raw JSON) and
    validates each comment field, dropping malformed entries with a warning.
    """
    # Strip optional ```json ... ``` wrapper the model may emit despite instructions
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("Gemini returned non-JSON response: %s\n---\n%s", exc, raw[:500])
        raise RuntimeError(f"LLM returned invalid JSON: {exc}") from exc

    summary = str(data.get("summary", "")).strip()
    raw_score = data.get("score", 5)
    try:
        score = max(0.0, min(10.0, float(raw_score)))
    except (TypeError, ValueError):
        score = 5.0

    security_flags = [str(f) for f in data.get("security_flags", []) if f]

    comments: list[LLMComment] = []
    for i, raw_comment in enumerate(data.get("comments", [])):
        if not isinstance(raw_comment, dict):
            logger.warning("Skipping comment[%d]: not a dict", i)
            continue

        file_path = str(raw_comment.get("file_path", "")).strip()
        if not file_path:
            logger.warning("Skipping comment[%d]: missing file_path", i)
            continue

        try:
            line_number = int(raw_comment["line_number"])
        except (KeyError, TypeError, ValueError):
            logger.warning("Skipping comment[%d]: invalid line_number", i)
            continue

        severity = str(raw_comment.get("severity", "info")).lower()
        if severity not in _SEVERITY_VALUES:
            severity = "info"

        category = str(raw_comment.get("category", "other")).lower()
        if category not in _CATEGORY_VALUES:
            category = "other"

        message = str(raw_comment.get("message", "")).strip()
        if not message:
            logger.warning("Skipping comment[%d]: empty message", i)
            continue

        suggestion = str(raw_comment.get("suggestion", "")).strip()

        comments.append(
            LLMComment(
                file_path=file_path,
                line_number=line_number,
                severity=severity,
                category=category,
                message=message,
                suggestion=suggestion,
            )
        )

    return LLMReviewResult(
        summary=summary,
        score=score,
        comments=comments,
        security_flags=security_flags,
    )


# ---------------------------------------------------------------------------
# GitHub helpers
# ---------------------------------------------------------------------------


def _get_installation_token(repo: Repository) -> str:
    """
    Return the OAuth token stored in the DB for the repository owner.
    For now we reuse the user's OAuth token (sufficient for user-installed apps).
    """
    from allauth.socialaccount.models import SocialToken

    token_obj = (
        SocialToken.objects.filter(
            account__user=repo.user,
            account__provider="github",
        )
        .order_by("-expires_at")
        .first()
    )
    if not token_obj:
        raise RuntimeError(
            f"No GitHub OAuth token found for user {repo.user}. "
            "Cannot post review to GitHub."
        )
    return token_obj.token


def _post_github_review(
    gh: Github,
    repo: Repository,
    pr_number: int,
    head_sha: str,
    result: LLMReviewResult,
    position_map: dict[tuple[str, int], int],
) -> int:
    """
    Post the LLM findings as a GitHub pull request review.

    Returns the GitHub review ID.
    """
    gh_repo = gh.get_repo(repo.full_name)
    gh_pr = gh_repo.get_pull(pr_number)

    # Build the inline comment list — only for positions we can map
    inline_comments = []
    skipped = 0
    for comment in result.comments:
        pos = position_map.get((comment.file_path, comment.line_number))
        if pos is None:
            # Line not in diff — post as a general body note instead
            skipped += 1
            continue

        body = f"**[{comment.severity.upper()}]** {comment.message}"
        if comment.suggestion:
            body += f"\n\n> **Suggestion:** {comment.suggestion}"

        inline_comments.append(
            {
                "path": comment.file_path,
                "position": pos,
                "body": body,
            }
        )

    if skipped:
        logger.info(
            "%d comment(s) skipped — line not present in diff (will appear in summary only)",
            skipped,
        )

    # Build the review body (summary + score + security flags)
    review_body_parts = [
        f"## Review-hawk AI Review",
        f"",
        f"**Score:** {result.score:.0f}/10",
        f"",
        result.summary,
    ]

    if result.security_flags:
        review_body_parts += [
            "",
            "### 🔴 Security Flags",
            *[f"- {flag}" for flag in result.security_flags],
        ]

    if skipped:
        review_body_parts += [
            "",
            f"*{skipped} finding(s) could not be posted inline (lines not in diff) — see full report in the DB.*",
        ]

    review_body = "\n".join(review_body_parts)

    # Determine event type
    has_errors = any(c.severity == "error" for c in result.comments) or bool(result.security_flags)
    event = "REQUEST_CHANGES" if has_errors else "COMMENT"

    review = gh_pr.create_review(
        commit=gh_repo.get_commit(head_sha),
        body=review_body,
        event=event,
        comments=inline_comments,
    )
    return review.id


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_review(review_id: int) -> None:
    """
    Execute a full AI review cycle for the given ``Review`` DB row.

    Called by the Celery task in ``reviews/tasks.py``.

    Flow
    ----
    1. Load the Review + PullRequest from DB.
    2. Fetch the PR diff from GitHub.
    3. Build diff-position map.
    4. Call Gemini, parse the structured JSON response.
    5. Persist Review + ReviewComment rows.
    6. Post the GitHub pull request review.
    """
    try:
        review = Review.objects.select_related("pull_request__repository__user").get(
            pk=review_id
        )
    except Review.DoesNotExist:
        logger.error("Review %d not found in DB — aborting.", review_id)
        return

    pr: PullRequest = review.pull_request
    repo: Repository = pr.repository

    # Mark as running
    review.status = Review.Status.RUNNING
    review.started_at = datetime.now(tz=timezone.utc)
    review.save(update_fields=["status", "started_at"])

    try:
        _do_review(review, pr, repo)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Review %d failed: %s", review_id, exc)
        review.status = Review.Status.FAILED
        review.error_message = str(exc)
        review.finished_at = datetime.now(tz=timezone.utc)
        review.save(update_fields=["status", "error_message", "finished_at"])


def _do_review(review: Review, pr: PullRequest, repo: Repository) -> None:
    """Inner function — all failures bubble up to ``run_review``."""

    # ── 1. Authenticate with GitHub ────────────────────────────────────────
    token = _get_installation_token(repo)
    gh = Github(token)

    gh_repo = gh.get_repo(repo.full_name)
    gh_pr = gh_repo.get_pull(pr.number)

    # ── 2. Fetch PR diff ───────────────────────────────────────────────────
    # PyGithub doesn't expose diff directly; use the raw comparison API.
    import requests as http_requests

    diff_url = gh_pr.diff_url
    diff_resp = http_requests.get(
        diff_url,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3.diff",
        },
        timeout=30,
    )
    diff_resp.raise_for_status()
    raw_diff = diff_resp.text

    # ── 3. Build diff-position map ─────────────────────────────────────────
    position_map = build_diff_position_map(raw_diff)
    logger.info(
        "Diff-position map built: %d mappable positions across %d file(s)",
        len(position_map),
        len({fp for fp, _ in position_map}),
    )

    # ── 4. Call Gemini ─────────────────────────────────────────────────────
    user_prompt = _build_user_prompt(
        pr_title=pr.title,
        pr_body=gh_pr.body or "",
        author=pr.author,
        base_branch=repo.default_branch,
        head_sha=review.head_sha,
        diff=raw_diff,
    )

    logger.info("Calling Gemini model=%s for review_id=%d …", GEMINI_MODEL, review.pk)
    raw_text, input_tokens, output_tokens = _call_gemini(user_prompt)
    logger.info(
        "Gemini response received: %d input tokens, %d output tokens",
        input_tokens,
        output_tokens,
    )

    # ── 5. Parse the structured JSON response ──────────────────────────────
    result = _parse_llm_response(raw_text)
    result.raw_response = raw_text
    result.input_tokens = input_tokens
    result.output_tokens = output_tokens

    # ── 6. Persist Review summary ──────────────────────────────────────────
    review.summary = result.summary
    review.llm_model = GEMINI_MODEL
    review.input_tokens = input_tokens
    review.output_tokens = output_tokens
    review.files_reviewed = len({c.file_path for c in result.comments})
    review.save(
        update_fields=[
            "summary",
            "llm_model",
            "input_tokens",
            "output_tokens",
            "files_reviewed",
        ]
    )

    # ── 7. Persist ReviewComment rows ──────────────────────────────────────
    db_comments = []
    for comment in result.comments:
        db_comments.append(
            ReviewComment(
                review=review,
                file_path=comment.file_path,
                line_number=comment.line_number,
                severity=comment.severity,
                category=comment.category,
                message=comment.message,
                suggestion=comment.suggestion,
                source=ReviewComment.Source.LLM,
            )
        )
    ReviewComment.objects.bulk_create(db_comments)
    logger.info("Saved %d ReviewComment(s) to DB", len(db_comments))

    # ── 8. Post GitHub PR Review ───────────────────────────────────────────
    github_review_id = _post_github_review(
        gh=gh,
        repo=pr.repository,
        pr_number=pr.number,
        head_sha=review.head_sha,
        result=result,
        position_map=position_map,
    )
    logger.info("Posted GitHub PR review id=%d", github_review_id)

    # ── 9. Mark complete ───────────────────────────────────────────────────
    review.status = Review.Status.COMPLETED
    review.github_review_id = github_review_id
    review.finished_at = datetime.now(tz=timezone.utc)
    review.save(update_fields=["status", "github_review_id", "finished_at"])
    logger.info("Review %d completed successfully.", review.pk)
