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
5. Run tree-sitter static analysis on changed Python files.
6. Merge & dedupe LLM + static findings (same line → keep static, note LLM agreement).
7. Persist findings to the DB (Review + ReviewComment rows).
8. Post the review back to GitHub via the Pull-Requests API.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import google.generativeai as genai
import requests as http_requests
from decouple import config
from github import Github, GithubException, GithubIntegration

from repos.models import PullRequest, Repository
from reviews.models import Review, ReviewComment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GEMINI_API_KEY = config("GEMINI_API_KEY", default="")
GEMINI_MODEL = config("GEMINI_MODEL", default="gemini-2.5-flash")
GITHUB_APP_ID = config("GITHUB_APP_ID", default="")
GITHUB_PRIVATE_KEY_PATH = config("GITHUB_PRIVATE_KEY_PATH", default="")

# Maximum characters of diff we send to the model.  Keeps token cost sane.
MAX_DIFF_CHARS = 80_000

# Maximum inline comments per GitHub review (GitHub may reject more)
MAX_INLINE_COMMENTS = 20

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


def extract_changed_lines(raw_diff: str) -> dict[str, set[int]]:
    """
    Parse a unified diff and return a mapping:
        file_path -> set of new-file line numbers that were ADDED in the PR.

    Used to filter tree-sitter findings to only lines touched by this PR.
    Context lines (unchanged) are intentionally excluded — only ``+`` lines
    are considered "changed" for the purpose of static-analysis gating.
    """
    changed: dict[str, set[int]] = {}
    current_file: str | None = None
    new_line_number = 0

    for raw_line in raw_diff.splitlines():
        file_match = _DIFF_FILE_HEADER.match(raw_line)
        if file_match:
            current_file = file_match.group(1)
            changed.setdefault(current_file, set())
            new_line_number = 0
            continue

        if raw_line.startswith("--- ") or raw_line.startswith("+++ "):
            continue

        hunk_match = _HUNK_HEADER.match(raw_line)
        if hunk_match:
            new_line_number = int(hunk_match.group(1))
            continue

        if current_file is None:
            continue

        if raw_line.startswith("+"):
            changed[current_file].add(new_line_number)
            new_line_number += 1
        elif raw_line.startswith("-"):
            pass  # removed line — no new-file line number
        else:
            new_line_number += 1  # context line

    return changed


# ---------------------------------------------------------------------------
# Merge & dedupe  (LLM + tree-sitter findings)
# ---------------------------------------------------------------------------


def merge_and_dedupe(
    llm_comments: list["LLMComment"],
    static_findings: list,
) -> tuple[list["LLMComment"], list]:
    """
    Merge LLM and tree-sitter findings, deduplicating by (file_path, line_number).

    Strategy
    --------
    - If both flag the **same line**: keep the tree-sitter finding (deterministic,
      rule-based) and append ``[LLM also flagged]`` to its message.  Drop the
      duplicate LLM comment for that line.
    - Lines flagged only by LLM → kept as-is.
    - Lines flagged only by tree-sitter → kept as-is.

    Returns
    -------
    (filtered_llm_comments, annotated_static_findings)
    """
    # Build lookup: lines covered by static findings
    static_keys: set[tuple[str, int]] = {
        (f.file_path, f.line_number) for f in static_findings
    }
    llm_keys: set[tuple[str, int]] = {
        (c.file_path, c.line_number) for c in llm_comments
    }

    # Annotate static findings confirmed by the LLM
    annotated_static: list = []
    for finding in static_findings:
        key = (finding.file_path, finding.line_number)
        if key in llm_keys:
            finding.message += "  \u26a0\ufe0f *LLM also flagged this line.*"
        annotated_static.append(finding)

    # Drop LLM comments that duplicate a static finding on the same line
    filtered_llm = [
        c for c in llm_comments
        if (c.file_path, c.line_number) not in static_keys
    ]

    logger.info(
        "merge_and_dedupe: %d LLM + %d static → %d LLM kept, %d static kept",
        len(llm_comments),
        len(static_findings),
        len(filtered_llm),
        len(annotated_static),
    )
    return filtered_llm, annotated_static


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
# GitHub auth helper
# ---------------------------------------------------------------------------


def _get_github_client(review: Review) -> Github:
    """
    Return an authenticated PyGithub client.

    Preference order
    ----------------
    1. GitHub App auth: read GITHUB_APP_ID + GITHUB_PRIVATE_KEY_PATH, create
       a JWT, exchange it for an installation token using review.installation_id.
       This posts the review *as the App* (not as the user).
    2. User OAuth fallback: use the SocialToken stored by django-allauth.
       Logs a warning so it's easy to spot in production.

    Raises
    ------
    RuntimeError if neither method yields a token.
    """
    installation_id: int | None = review.installation_id

    if GITHUB_APP_ID and GITHUB_PRIVATE_KEY_PATH and installation_id:
        try:
            with open(GITHUB_PRIVATE_KEY_PATH, "r") as fh:
                private_key = fh.read()
            integration = GithubIntegration(
                integration_id=int(GITHUB_APP_ID),
                private_key=private_key,
            )
            install = integration.get_installation(
                review.pull_request.repository.owner,
                review.pull_request.repository.name,
            )
            token = integration.get_access_token(install.id).token
            logger.info("Using GitHub App auth (installation_id=%d)", installation_id)
            return Github(token)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "GitHub App auth failed (installation_id=%s): %s — falling back to user token.",
                installation_id, exc,
            )

    # ── Fallback: user OAuth token ─────────────────────────────────────────────
    from allauth.socialaccount.models import SocialToken

    repo = review.pull_request.repository
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
            f"No GitHub token available for user '{repo.user}' "
            "(App auth not configured and no OAuth token found)."
        )
    logger.warning(
        "Using user OAuth token for review_id=%d — configure GITHUB_APP_ID and "
        "GITHUB_PRIVATE_KEY_PATH to post as the App instead.",
        review.pk,
    )
    return Github(token_obj.token)


# ---------------------------------------------------------------------------
# Transient error detection
# ---------------------------------------------------------------------------


def _is_transient(exc: BaseException) -> bool:
    """
    Return True for errors that are worth retrying (rate-limits, timeouts,
    server-side 5xx).  Return False for permanent errors (bad auth, not found,
    invalid JSON, etc.).
    """
    if isinstance(exc, http_requests.Timeout):
        return True
    if isinstance(exc, http_requests.ConnectionError):
        return True
    if isinstance(exc, GithubException):
        status = getattr(exc, "status", 0)
        # 403 can mean rate-limited; 500/502/503 are GitHub server errors
        if status in {403, 429, 500, 502, 503}:
            return True
    if isinstance(exc, Exception):
        # Gemini 429 / 5xx surfaces as google.api_core.exceptions
        module = type(exc).__module__ or ""
        if "google" in module:
            msg = str(exc).lower()
            if any(k in msg for k in ("429", "quota", "rate", "unavailable", "internal")):
                return True
    return False


def _post_github_review(
    gh: Github,
    review: Review,
    result: LLMReviewResult,
    static_findings: list,
    position_map: dict[tuple[str, int], int],
    health_markdown: str = "",
) -> int:
    """
    Post findings as a GitHub pull request review and update ReviewComment rows.

    Rules
    -----
    - event is always ``COMMENT`` (never REQUEST_CHANGES) to avoid blocking PRs.
    - Inline comments are capped at MAX_INLINE_COMMENTS (20) total.
    - On GitHub 422 (unprocessable, e.g. stale diff position), retries once
      with an empty inline list; overflowed findings move into the summary body.
    - Sets ReviewComment.posted=True and github_comment_id for each inline hit.

    Returns the GitHub review ID.
    """
    repo = review.pull_request.repository
    pr_number = review.pull_request.number
    head_sha = review.head_sha

    gh_repo = gh.get_repo(repo.full_name)
    gh_pr = gh_repo.get_pull(pr_number)
    commit = gh_repo.get_commit(head_sha)

    # ── Build candidate inline comments ───────────────────────────────────
    # Each entry: (body_str, ReviewComment_db_obj_or_None, path, position)
    candidates: list[tuple[str, object, str, int]] = []

    for comment in result.comments:
        pos = position_map.get((comment.file_path, comment.line_number))
        if pos is None:
            continue
        body = f"**[{comment.severity.upper()}]** {comment.message}"
        if comment.suggestion:
            body += f"\n\n> **Suggestion:** {comment.suggestion}"
        candidates.append((body, None, comment.file_path, pos))

    for finding in static_findings:
        pos = position_map.get((finding.file_path, finding.line_number))
        if pos is None:
            continue
        icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(finding.severity, "🔵")
        body = f"{icon} **[{finding.rule_id}]** {finding.message}"
        if finding.suggestion:
            body += f"\n\n> **Fix:** {finding.suggestion}"
        candidates.append((body, None, finding.file_path, pos))

    # ── Cap at MAX_INLINE_COMMENTS ───────────────────────────────────────
    inline_candidates = candidates[:MAX_INLINE_COMMENTS]
    overflow = candidates[MAX_INLINE_COMMENTS:]
    skipped_no_pos = (
        len(result.comments) + len(static_findings) - len(candidates)
    )

    inline_payload = [
        {"path": path, "position": pos, "body": body}
        for body, _, path, pos in inline_candidates
    ]

    # ── Build review summary body ───────────────────────────────────────
    body_parts = [
        "## Review-hawk AI Review",
        "",
        f"**Score:** {result.score:.0f}/10",
        "",
        result.summary,
    ]
    if result.security_flags:
        body_parts += [
            "",
            "### 🔴 Security Flags",
            *[f"- {flag}" for flag in result.security_flags],
        ]
    if static_findings:
        body_parts += [
            "",
            f"### 🔬 Static Analysis ({len(static_findings)} finding(s))",
            "*Deterministic checks via tree-sitter — no AI guessing.*",
        ]
    if health_markdown:
        body_parts += ["", health_markdown]
    if overflow:
        body_parts += [
            "",
            f"### ⚠️ {len(overflow)} finding(s) not posted inline (cap={MAX_INLINE_COMMENTS})",
        ]
        for body, _, path, pos in overflow:
            body_parts.append(f"- `{path}` pos {pos}: {body[:120]}")
    if skipped_no_pos:
        body_parts.append(
            f"\n*{skipped_no_pos} finding(s) skipped — line not in diff.*"
        )

    review_body = "\n".join(body_parts)

    # ── Post to GitHub (always COMMENT, retry once on 422) ────────────────
    def _create(comments_payload: list) -> object:
        return gh_pr.create_review(
            commit=commit,
            body=review_body,
            event="COMMENT",
            comments=comments_payload,
        )

    try:
        gh_review = _create(inline_payload)
    except GithubException as exc:
        if getattr(exc, "status", 0) == 422:
            logger.warning(
                "GitHub 422 with %d inline comments — retrying without inline.",
                len(inline_payload),
            )
            gh_review = _create([])
            inline_payload = []  # nothing was posted inline
        else:
            raise

    logger.info("Posted GitHub review id=%d with %d inline comment(s)", gh_review.id, len(inline_payload))
    return gh_review.id


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_review(review_id: int) -> None:
    """
    Execute a full AI review cycle for the given ``Review`` DB row.

    Called by the Celery task in ``reviews/tasks.py``.

    Error handling
    --------------
    - Transient errors (timeouts, rate-limits, 5xx) are re-raised so that the
      Celery task can retry them with exponential backoff.
    - Permanent errors (invalid JSON, 404, bad auth) are caught here, written
      to Review.error_message, and NOT re-raised (no Celery retry).
    """
    try:
        review = Review.objects.select_related("pull_request__repository__user").get(
            pk=review_id
        )
    except Review.DoesNotExist:
        logger.error("Review %d not found in DB — aborting.", review_id)
        return

    # Guard: already completed — prevents double-post on Celery re-delivery
    if review.status == Review.Status.COMPLETED:
        logger.info("Review %d already completed — skipping.", review_id)
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
        if _is_transient(exc):
            # Let the Celery task handle retry
            logger.warning("Transient error in review %d: %s — will retry.", review_id, exc)
            raise
        # Permanent failure — record it and don't retry
        logger.exception("Permanent failure in review %d: %s", review_id, exc)
        review.status = Review.Status.FAILED
        review.error_message = str(exc)
        review.finished_at = datetime.now(tz=timezone.utc)
        review.save(update_fields=["status", "error_message", "finished_at"])


def _do_review(review: Review, pr: PullRequest, repo: Repository) -> None:
    """Inner function — transient errors bubble up; permanent ones do not."""
    from reviews.tree_sitter_analyzer import analyze_python, TREE_SITTER_AVAILABLE
    from reviews.health_scorer import (
        calculate_health_score,
        extract_changed_files,
        format_health_score_markdown,
    )

    # ── 1. Authenticate with GitHub ────────────────────────────────────────
    gh = _get_github_client(review)

    gh_repo = gh.get_repo(repo.full_name)
    gh_pr = gh_repo.get_pull(pr.number)

    # ── 2. Fetch PR diff ───────────────────────────────────────────────────
    diff_resp = http_requests.get(
        gh_pr.diff_url,
        headers={"Accept": "application/vnd.github.v3.diff"},
        timeout=30,
    )
    diff_resp.raise_for_status()
    raw_diff = diff_resp.text

    # ── 3. Build diff-position map + extract changed lines per file ────────
    position_map = build_diff_position_map(raw_diff)
    changed_lines_map = extract_changed_lines(raw_diff)
    logger.info(
        "Diff parsed: %d mappable positions, %d file(s) touched",
        len(position_map), len(changed_lines_map),
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
    logger.info("Gemini response: %d in, %d out tokens", input_tokens, output_tokens)

    # ── 5. Parse LLM response ───────────────────────────────────────────────
    result = _parse_llm_response(raw_text)
    result.raw_response = raw_text
    result.input_tokens = input_tokens
    result.output_tokens = output_tokens

    # ── 6. Tree-sitter static analysis ─────────────────────────────────────
    static_findings: list = []
    if TREE_SITTER_AVAILABLE:
        python_files = [fp for fp in changed_lines_map if fp.endswith(".py")]
        logger.info("Running tree-sitter on %d Python file(s)", len(python_files))
        for file_path in python_files:
            try:
                content_obj = gh_repo.get_contents(file_path, ref=review.head_sha)
                source = content_obj.decoded_content.decode("utf-8", errors="replace")
                findings = analyze_python(source, file_path, changed_lines_map.get(file_path, set()))
                static_findings.extend(findings)
            except Exception as exc:  # noqa: BLE001
                logger.warning("tree-sitter failed for %s: %s", file_path, exc)

    # ── 7. Merge & dedupe ──────────────────────────────────────────────────
    final_llm, final_static = merge_and_dedupe(result.comments, static_findings)
    result.comments = final_llm

    # ── 7b. Rule-based PR health score (never allowed to fail the review) ───
    health = None
    health_markdown = ""
    try:
        health = calculate_health_score(
            changed_files=extract_changed_files(raw_diff),
            raw_diff=raw_diff,
            pr_title=pr.title,
            pr_description=gh_pr.body or "",
            ast_findings=final_static,
            llm_comments=final_llm,
        )
        health_markdown = format_health_score_markdown(health)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Health scoring failed for review %d: %s", review.pk, exc)

    # ── 8. Persist Review summary ──────────────────────────────────────────
    all_files = {c.file_path for c in result.comments} | {f.file_path for f in final_static}
    review.summary = result.summary
    review.llm_model = GEMINI_MODEL
    review.input_tokens = input_tokens
    review.output_tokens = output_tokens
    review.files_reviewed = len(all_files)
    update_fields = ["summary", "llm_model", "input_tokens", "output_tokens", "files_reviewed"]
    if health is not None:
        review.health_score = health.score
        review.health_grade = health.grade
        review.health_report = health.to_dict()
        update_fields += ["health_score", "health_grade", "health_report"]
    review.save(update_fields=update_fields)

    # ── 9. Persist ReviewComment rows ───────────────────────────────────────
    db_comments: list[ReviewComment] = []
    for comment in result.comments:
        db_comments.append(ReviewComment(
            review=review,
            file_path=comment.file_path,
            line_number=comment.line_number,
            severity=comment.severity,
            category=comment.category,
            message=comment.message,
            suggestion=comment.suggestion,
            source=ReviewComment.Source.LLM,
        ))
    for finding in final_static:
        db_comments.append(ReviewComment(
            review=review,
            file_path=finding.file_path,
            line_number=finding.line_number,
            severity=finding.severity,
            category=finding.category,
            message=finding.message,
            suggestion=finding.suggestion,
            source=ReviewComment.Source.STATIC,
            rule_id=finding.rule_id,
        ))
    ReviewComment.objects.bulk_create(db_comments)
    logger.info("Saved %d comments (%d LLM, %d static)", len(db_comments), len(result.comments), len(final_static))

    # ── 10. Post to GitHub ──────────────────────────────────────────────────
    github_review_id = _post_github_review(
        gh=gh,
        review=review,
        result=result,
        static_findings=final_static,
        position_map=position_map,
        health_markdown=health_markdown,
    )

    # ── 11. Mark posted + complete ──────────────────────────────────────────
    now = datetime.now(tz=timezone.utc)
    review.status = Review.Status.COMPLETED
    review.github_review_id = github_review_id
    review.posted_at = now
    review.finished_at = now
    review.save(update_fields=["status", "github_review_id", "posted_at", "finished_at"])
    logger.info("Review %d completed (github_review_id=%d).", review.pk, github_review_id)
