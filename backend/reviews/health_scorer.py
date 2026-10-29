"""
reviews/health_scorer.py
========================
Rule-based **PR Health Score** (0-100) with a letter grade, risk level,
badges and recommendations.

The score starts at ``base_score`` (100) and every *signal* adds or removes
points. Nothing here is machine-learned: each rule is explicit, so every point
can be explained in a viva ("why did this PR get a C?" -> read the signal list).

Signals
-------
1. size    - lines changed, number of files touched
2. test    - are tests touched when source logic changes?
3. docs    - is there a useful PR description?
4. static  - Tree-sitter findings (rule ids TS-PY-001 ... TS-PY-005)
5. llm     - AI review findings (severity: error / warning / info)

Inputs match what the pipeline already has:
  * static findings -> ``reviews.tree_sitter_analyzer.Finding`` (needs ``rule_id``)
  * LLM comments    -> ``LLMComment`` or ``ReviewComment`` (needs ``severity``)

Tuning
------
All weights and thresholds live in :class:`HealthScorerConfig`. To tune, change a
value there and run ``pytest reviews/tests/test_health_scorer.py``; the scenario
tests show which sample PRs move to a different grade. See docs/HEALTH_SCORING.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Sequence

# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class HealthSignal:
    """One evaluated rule and its contribution to the score."""

    code: str                     # e.g. "LARGE_PR_SIZE"
    category: str                 # "size" | "test" | "docs" | "static" | "llm"
    score_delta: int              # positive = bonus, negative = penalty
    severity: str                 # "positive" | "info" | "warning" | "critical"
    description: str
    badge: Optional[str] = None


@dataclass
class PRHealthReport:
    """Complete health evaluation for one pull request review."""

    score: int
    grade: str
    risk_level: str
    status_emoji: str
    signals: list[HealthSignal] = field(default_factory=list)
    badges: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    total_additions: int = 0
    total_deletions: int = 0
    total_files_changed: int = 0
    has_tests: bool = False
    static_critical_count: int = 0
    static_warning_count: int = 0
    llm_error_count: int = 0
    llm_warning_count: int = 0

    def to_dict(self) -> dict:
        """JSON-safe dict for the database (Review.health_report) and the API."""
        return {
            "score": self.score,
            "grade": self.grade,
            "risk_level": self.risk_level,
            "status_emoji": self.status_emoji,
            "badges": self.badges,
            "recommendations": self.recommendations,
            "signals": [
                {
                    "code": s.code,
                    "category": s.category,
                    "score_delta": s.score_delta,
                    "severity": s.severity,
                    "description": s.description,
                    "badge": s.badge,
                }
                for s in self.signals
            ],
            "metrics": {
                "additions": self.total_additions,
                "deletions": self.total_deletions,
                "files_changed": self.total_files_changed,
                "has_tests": self.has_tests,
                "static_critical": self.static_critical_count,
                "static_warning": self.static_warning_count,
                "llm_errors": self.llm_error_count,
                "llm_warnings": self.llm_warning_count,
            },
        }


# ─────────────────────────────────────────────────────────────────────────────
# Tunable configuration
# ─────────────────────────────────────────────────────────────────────────────


def _default_static_rules() -> dict[str, dict]:
    """
    Penalty per Tree-sitter rule. ``per`` is applied once per finding, ``cap`` is
    the most that rule can remove in total (so 30 unused imports can't zero a PR).
    """
    return {
        "TS-PY-001": {"code": "STATIC_UNUSED_IMPORTS", "label": "unused import(s)",
                      "per": -2, "cap": -10, "severity": "info"},
        "TS-PY-002": {"code": "STATIC_LONG_FUNCTIONS", "label": "overly long function(s)",
                      "per": -5, "cap": -15, "severity": "info"},
        "TS-PY-003": {"code": "STATIC_BARE_EXCEPT", "label": "bare or empty except block(s)",
                      "per": -8, "cap": -24, "severity": "warning"},
        "TS-PY-004": {"code": "STATIC_DEEP_NESTING", "label": "deeply nested block(s)",
                      "per": -8, "cap": -24, "severity": "warning"},
        "TS-PY-005": {"code": "STATIC_HARDCODED_SECRETS", "label": "hardcoded secret(s)",
                      "per": -30, "cap": -60, "severity": "critical"},
    }


@dataclass
class HealthScorerConfig:
    """Every threshold and weight used by :func:`calculate_health_score`."""

    base_score: int = 100

    # --- size (lines changed = additions + deletions) ---
    small_pr_max_lines: int = 100
    medium_pr_max_lines: int = 300
    large_pr_max_lines: int = 600
    very_large_pr_max_lines: int = 1000
    bonus_small_pr: int = 5
    penalty_medium_large_pr: int = -8
    penalty_large_pr: int = -18
    penalty_very_large_pr: int = -30

    # --- file sprawl ---
    medium_files_threshold: int = 6
    high_files_threshold: int = 15
    penalty_medium_files: int = -4
    penalty_high_files: int = -12

    # --- tests / docs ---
    min_lines_requiring_tests: int = 50
    penalty_no_tests: int = -15
    bonus_tests_included: int = 5
    minimal_description_chars: int = 20
    rich_description_chars: int = 100
    penalty_empty_description: int = -8
    bonus_rich_description: int = 3

    # --- static analysis (Tree-sitter) ---
    static_rules: dict = field(default_factory=_default_static_rules)

    # --- LLM findings (severity -> per-finding penalty, with caps) ---
    penalty_llm_error: int = -20
    max_penalty_llm_errors: int = -50
    penalty_llm_warning: int = -8
    max_penalty_llm_warnings: int = -30
    penalty_llm_info: int = -2
    max_penalty_llm_info: int = -10

    # --- grade boundaries (minimum score for each grade) ---
    grade_a_plus: int = 90
    grade_a: int = 80
    grade_b: int = 70
    grade_c: int = 60
    grade_d: int = 40


DEFAULT_CONFIG = HealthScorerConfig()

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_DIFF_FILE_HEADER = re.compile(r"^diff --git a/.+ b/(.+)$")
_TEST_NAME = re.compile(
    r"(^|/)(tests?|__tests__|spec)/"      # tests/ , test/ , __tests__/ , spec/
    r"|(^|/)test_[^/]*$"                  # test_foo.py
    r"|_test\.[a-z]+$"                    # foo_test.py / foo_test.go
    r"|\.(test|spec)\.[a-z]+$",           # foo.test.js / foo.spec.ts
    re.IGNORECASE,
)


def extract_changed_files(raw_diff: str) -> list[str]:
    """Return every file path touched by a unified diff, in order, without duplicates."""
    files: list[str] = []
    for line in raw_diff.splitlines():
        m = _DIFF_FILE_HEADER.match(line)
        if m and m.group(1) not in files:
            files.append(m.group(1))
    return files


def is_test_file(path: str) -> bool:
    """True for typical test file locations and names (Python and JS/TS)."""
    return bool(_TEST_NAME.search(path))


def _count_diff_lines(raw_diff: str) -> tuple[int, int]:
    additions = deletions = 0
    for line in raw_diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1
    return additions, deletions


def _grade_for(score: int, cfg: HealthScorerConfig) -> tuple[str, str, str]:
    if score >= cfg.grade_a_plus:
        return "A+", "Low", "💚"
    if score >= cfg.grade_a:
        return "A", "Low", "🟢"
    if score >= cfg.grade_b:
        return "B", "Medium", "🟡"
    if score >= cfg.grade_c:
        return "C", "Medium", "🟠"
    if score >= cfg.grade_d:
        return "D", "High", "🔴"
    return "F", "Critical", "🚨"


# ─────────────────────────────────────────────────────────────────────────────
# Scoring engine
# ─────────────────────────────────────────────────────────────────────────────


def calculate_health_score(
    changed_files: Sequence[str],
    raw_diff: str,
    pr_title: str = "",
    pr_description: str = "",
    ast_findings: Optional[Sequence] = None,
    llm_comments: Optional[Sequence] = None,
    config: HealthScorerConfig = DEFAULT_CONFIG,
) -> PRHealthReport:
    """
    Compute the health report for one PR.

    ``ast_findings``: objects with ``rule_id`` (Tree-sitter findings).
    ``llm_comments``: objects with ``severity`` in {"error", "warning", "info"}.
    """
    cfg = config
    ast_findings = list(ast_findings or [])
    llm_comments = list(llm_comments or [])
    changed_files = list(changed_files or [])

    signals: list[HealthSignal] = []
    badges: list[str] = []
    recommendations: list[str] = []

    additions, deletions = _count_diff_lines(raw_diff or "")
    total_changes = additions + deletions
    total_files = len(changed_files)

    # 1. Size ----------------------------------------------------------------
    if total_changes <= cfg.small_pr_max_lines:
        signals.append(HealthSignal(
            "SMALL_PR_SIZE", "size", cfg.bonus_small_pr, "positive",
            f"Compact PR ({total_changes} lines changed): quick to review.", "✨ Concise PR"))
        badges.append("✨ Concise PR")
    elif total_changes > cfg.very_large_pr_max_lines:
        signals.append(HealthSignal(
            "VERY_LARGE_PR_SIZE", "size", cfg.penalty_very_large_pr, "critical",
            f"Very large diff ({total_changes} lines changed): high review fatigue and risk.",
            "⚡ Massive Diff"))
        badges.append("⚡ Massive Diff")
        recommendations.append(
            f"Split this PR into smaller, focused pull requests "
            f"({total_changes} lines across {total_files} files).")
    elif total_changes > cfg.large_pr_max_lines:
        signals.append(HealthSignal(
            "LARGE_PR_SIZE", "size", cfg.penalty_large_pr, "warning",
            f"Large diff ({total_changes} lines changed): may slow down review.", "🐘 Large Diff"))
        badges.append("🐘 Large Diff")
    elif total_changes > cfg.medium_pr_max_lines:
        signals.append(HealthSignal(
            "MEDIUM_PR_SIZE", "size", cfg.penalty_medium_large_pr, "info",
            f"Slightly large diff ({total_changes} lines changed)."))

    if total_files > cfg.high_files_threshold:
        signals.append(HealthSignal(
            "HIGH_FILE_SPRAWL", "size", cfg.penalty_high_files, "warning",
            f"{total_files} files changed: high context-switching cost.", "📂 File Sprawl"))
        badges.append("📂 File Sprawl")
    elif total_files >= cfg.medium_files_threshold:
        signals.append(HealthSignal(
            "MEDIUM_FILE_SPRAWL", "size", cfg.penalty_medium_files, "info",
            f"{total_files} files changed."))

    # 2. Tests ---------------------------------------------------------------
    test_files = [f for f in changed_files if is_test_file(f)]
    source_files = [f for f in changed_files if not is_test_file(f)]
    has_tests = bool(test_files)
    if has_tests:
        signals.append(HealthSignal(
            "TESTS_INCLUDED", "test", cfg.bonus_tests_included, "positive",
            f"Touches {len(test_files)} test file(s).", "🧪 Tests Included"))
        badges.append("🧪 Tests Included")
    elif source_files and total_changes > cfg.min_lines_requiring_tests:
        signals.append(HealthSignal(
            "NO_TESTS_INCLUDED", "test", cfg.penalty_no_tests, "warning",
            f"More than {cfg.min_lines_requiring_tests} lines of source changed but no test file was touched.",
            "⚠️ No Tests"))
        badges.append("⚠️ No Tests")
        recommendations.append("Add unit or integration tests for the changed logic.")

    # 3. Description ---------------------------------------------------------
    desc = (pr_description or "").strip()
    if len(desc) < cfg.minimal_description_chars:
        signals.append(HealthSignal(
            "MINIMAL_DESCRIPTION", "docs", cfg.penalty_empty_description, "warning",
            f"PR description is missing or under {cfg.minimal_description_chars} characters.",
            "📝 Sparse Description"))
        badges.append("📝 Sparse Description")
        recommendations.append("Explain the why, how to test, and any risks in the PR description.")
    elif len(desc) >= cfg.rich_description_chars:
        signals.append(HealthSignal(
            "RICH_DESCRIPTION", "docs", cfg.bonus_rich_description, "positive",
            "Detailed PR description gives reviewers context.", "📖 Well Documented"))

    # 4. Static analysis (Tree-sitter) ----------------------------------------
    static_critical = static_warning = 0
    for rule_id, rule in cfg.static_rules.items():
        hits = [f for f in ast_findings if getattr(f, "rule_id", "") == rule_id]
        if not hits:
            continue
        delta = max(rule["cap"], rule["per"] * len(hits))
        sev = rule["severity"]
        if sev == "critical":
            static_critical += len(hits)
        elif sev == "warning":
            static_warning += len(hits)
        badge = "🔒 Secret Detected" if rule_id == "TS-PY-005" else None
        signals.append(HealthSignal(
            rule["code"], "static", delta, sev,
            f"Static check found {len(hits)} {rule['label']}.", badge))
        if badge:
            badges.append(badge)
            recommendations.append("Remove hardcoded secrets and load them from environment variables.")
        elif rule_id == "TS-PY-003":
            recommendations.append("Catch specific exceptions and log or handle the error instead of ignoring it.")
        elif rule_id == "TS-PY-004":
            recommendations.append("Flatten deeply nested code with early returns or helper functions.")

    # 5. LLM findings --------------------------------------------------------
    errors = [c for c in llm_comments if getattr(c, "severity", "") == "error"]
    warnings = [c for c in llm_comments if getattr(c, "severity", "") == "warning"]
    infos = [c for c in llm_comments if getattr(c, "severity", "") == "info"]

    if errors:
        signals.append(HealthSignal(
            "LLM_ERROR_FINDINGS", "llm",
            max(cfg.max_penalty_llm_errors, cfg.penalty_llm_error * len(errors)), "critical",
            f"AI review found {len(errors)} error-level issue(s) (bugs, security or breaking changes).",
            "🚨 AI Error"))
        badges.append("🚨 AI Error")
        recommendations.append("Fix the error-level issues flagged by the AI review before merging.")
    if warnings:
        signals.append(HealthSignal(
            "LLM_WARNING_FINDINGS", "llm",
            max(cfg.max_penalty_llm_warnings, cfg.penalty_llm_warning * len(warnings)), "warning",
            f"AI review found {len(warnings)} warning-level issue(s)."))
    if infos:
        signals.append(HealthSignal(
            "LLM_INFO_FINDINGS", "llm",
            max(cfg.max_penalty_llm_info, cfg.penalty_llm_info * len(infos)), "info",
            f"AI review made {len(infos)} minor suggestion(s)."))

    # 6. Final score ---------------------------------------------------------
    score = max(0, min(100, cfg.base_score + sum(s.score_delta for s in signals)))
    grade, risk, emoji = _grade_for(score, cfg)

    return PRHealthReport(
        score=score,
        grade=grade,
        risk_level=risk,
        status_emoji=emoji,
        signals=signals,
        badges=list(dict.fromkeys(badges)),
        recommendations=list(dict.fromkeys(recommendations)),
        total_additions=additions,
        total_deletions=deletions,
        total_files_changed=total_files,
        has_tests=has_tests,
        static_critical_count=static_critical,
        static_warning_count=static_warning,
        llm_error_count=len(errors),
        llm_warning_count=len(warnings),
    )


# ─────────────────────────────────────────────────────────────────────────────
# GitHub markdown widget
# ─────────────────────────────────────────────────────────────────────────────


def format_health_score_markdown(report: PRHealthReport) -> str:
    """Compact markdown block appended to the GitHub review summary."""
    badges = " ".join(f"`{b}`" for b in report.badges) if report.badges else "_none_"
    lines = [
        f"### 📊 PR Health: **{report.score}/100** (Grade **{report.grade}**) {report.status_emoji}",
        "",
        f"**Risk level:** `{report.risk_level}` | **Badges:** {badges}",
    ]
    deductions = [s for s in report.signals if s.score_delta < 0]
    if deductions:
        lines += ["", "<details><summary><b>Why this score?</b></summary>", "",
                  "| Signal | Impact | Detail |", "| :--- | :---: | :--- |"]
        for s in deductions:
            lines.append(f"| `{s.code}` | `{s.score_delta}` | {s.description} |")
        lines += ["", "</details>"]
    if report.recommendations:
        lines += ["", "**💡 Recommendations**"]
        lines += [f"- {r}" for r in report.recommendations]
    return "\n".join(lines)
