"""
health_scorer.py
----------------
Defines, tunes, and evaluates rule-based signals to compute a PR Health Score (0-100),
assign a Health Grade (A+ to F), determine Risk Level, and generate actionable recommendations.

SIGNALS EVALUATED:
1. Size & Scope (lines changed, file sprawl)
2. Test Ratio (presence of tests when source logic changes)
3. Documentation & Context (PR description quality)
4. Static AST Analysis (syntax errors, secrets, complexity, docstrings, unused imports)
5. LLM Findings (critical, warning, suggestion, praise counts)
"""

from dataclasses import dataclass, field
from typing import Optional, Sequence
import re


# ─────────────────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class HealthSignal:
    """A single evaluated rule-based signal contribution to the PR health score."""
    code: str              # Unique signal identifier e.g. "LARGE_PR_SIZE"
    category: str          # "size", "test", "docs", "ast", "llm"
    score_delta: int       # Positive bonus or negative penalty
    severity: str          # "positive", "info", "warning", "critical"
    description: str       # Clear human-readable message
    badge: Optional[str] = None  # Optional UI/Markdown badge e.g. "⚡ Huge Diff"


@dataclass
class PRHealthReport:
    """Complete health evaluation result for a Pull Request."""
    score: int                           # Clamped 0 - 100
    grade: str                           # A+, A, B, C, D, F
    risk_level: str                      # Low, Medium, High, Critical
    status_emoji: str                    # Visual emoji for summary header
    signals: list[HealthSignal] = field(default_factory=list)
    badges: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    
    # Raw metrics summary
    total_additions: int = 0
    total_deletions: int = 0
    total_files_changed: int = 0
    has_tests: bool = False
    ast_critical_count: int = 0
    ast_warning_count: int = 0
    llm_critical_count: int = 0
    llm_warning_count: int = 0

    def to_dict(self) -> dict:
        """Convert report to dictionary for JSON APIs and database storage."""
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
                "ast_critical": self.ast_critical_count,
                "ast_warning": self.ast_warning_count,
                "llm_critical": self.llm_critical_count,
                "llm_warning": self.llm_warning_count,
            },
        }


# ─────────────────────────────────────────────────────────────────────────────
# Configurable Weights & Threshold Tuning
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class HealthScorerConfig:
    """Tunable thresholds and signal weights for health scoring."""
    base_score: int = 100

    # Diff Size Thresholds
    small_pr_max_lines: int = 100        # Bonus if <= 100 lines
    medium_pr_max_lines: int = 300       # Neutral
    large_pr_max_lines: int = 600        # Minor penalty
    very_large_pr_max_lines: int = 1000  # Major penalty

    # Signal Deltas (Points)
    bonus_small_pr: int = 5
    penalty_medium_large_pr: int = -10
    penalty_large_pr: int = -20
    penalty_very_large_pr: int = -35

    # File Sprawl Thresholds
    medium_files_threshold: int = 6      # -5 pts
    high_files_threshold: int = 15       # -15 pts
    penalty_medium_files: int = -5
    penalty_high_files: int = -15

    # Tests & Docs Deltas
    penalty_no_tests: int = -15
    bonus_tests_included: int = 5
    penalty_empty_description: int = -10
    bonus_rich_description: int = 5

    # Static AST Analysis Deltas
    penalty_ast_syntax_error: int = -50
    penalty_ast_secret: int = -30
    penalty_ast_complexity: int = -10
    penalty_ast_missing_docstring: int = -2
    max_penalty_docstrings: int = -10
    penalty_ast_unused_import: int = -2
    max_penalty_unused_imports: int = -10

    # LLM Findings Deltas
    penalty_llm_critical: int = -25
    penalty_llm_warning: int = -12
    penalty_llm_suggestion: int = -3
    max_penalty_llm_suggestions: int = -12
    bonus_llm_praise: int = 2
    max_bonus_llm_praise: int = 6


DEFAULT_CONFIG = HealthScorerConfig()


# ─────────────────────────────────────────────────────────────────────────────
# Health Scorer Engine
# ─────────────────────────────────────────────────────────────────────────────

def _is_test_file(filename: str) -> bool:
    """Check if a filename represents a test file."""
    f = filename.lower()
    return (
        "test" in f
        or f.startswith("tests/")
        or f.endswith("_test.py")
        or f.endswith("_test.js")
        or f.endswith("_test.ts")
        or f.endswith(".spec.js")
        or f.endswith(".spec.ts")
    )


def calculate_health_score(
    changed_files: list[str],
    raw_diff: str,
    pr_title: str = "",
    pr_description: str = "",
    ast_findings: Optional[Sequence] = None,
    llm_comments: Optional[Sequence] = None,
    config: HealthScorerConfig = DEFAULT_CONFIG,
) -> PRHealthReport:
    """
    Compute rule-based health score, grade, signals, and recommendations for a PR.

    Args:
        changed_files   : List of file path strings changed in the PR
        raw_diff        : Unified diff string
        pr_title        : PR title string
        pr_description  : PR body string
        ast_findings    : List of ASTFinding objects (from ast_checker)
        llm_comments    : List of ReviewComment objects (from llm_reviewer)
        config          : Custom HealthScorerConfig tuning parameters

    Returns:
        PRHealthReport object
    """
    ast_findings = ast_findings or []
    llm_comments = llm_comments or []

    signals: list[HealthSignal] = []
    badges: list[str] = []
    recommendations: list[str] = []

    # ── 1. Calculate Diff Statistics ─────────────────────────────────────────
    additions = 0
    deletions = 0
    for line in raw_diff.splitlines():
        if line.startswith('+') and not line.startswith('+++'):
            additions += 1
        elif line.startswith('-') and not line.startswith('---'):
            deletions += 1

    total_changes = additions + deletions
    total_files = len(changed_files)

    # ── 2. Size & Scope Signals ──────────────────────────────────────────────
    if total_changes <= config.small_pr_max_lines:
        signals.append(HealthSignal(
            code="SMALL_PR_SIZE",
            category="size",
            score_delta=config.bonus_small_pr,
            severity="positive",
            description=f"Compact PR size ({total_changes} lines changed) — fast and easy to review.",
            badge="✨ Concise PR",
        ))
    elif total_changes > config.very_large_pr_max_lines:
        signals.append(HealthSignal(
            code="VERY_LARGE_PR_SIZE",
            category="size",
            score_delta=config.penalty_very_large_pr,
            severity="critical",
            description=f"Monolithic PR diff ({total_changes} lines changed). High review fatigue and risk.",
            badge="⚡ Massive Diff (>1k lines)",
        ))
        badges.append("⚡ Massive Diff")
        recommendations.append(
            f"Consider splitting this PR into smaller, atomic pull requests. "
            f"Currently changing {total_changes} lines across {total_files} files."
        )
    elif total_changes > config.large_pr_max_lines:
        signals.append(HealthSignal(
            code="LARGE_PR_SIZE",
            category="size",
            score_delta=config.penalty_large_pr,
            severity="warning",
            description=f"Large PR diff ({total_changes} lines changed). May slow down code review.",
            badge="🐘 Large Diff (>600 lines)",
        ))
        badges.append("🐘 Large Diff")
    elif total_changes > config.medium_pr_max_lines:
        signals.append(HealthSignal(
            code="MEDIUM_LARGE_PR_SIZE",
            category="size",
            score_delta=config.penalty_medium_large_pr,
            severity="info",
            description=f"Slightly large PR diff ({total_changes} lines changed).",
        ))

    # File Sprawl Signal
    if total_files > config.high_files_threshold:
        signals.append(HealthSignal(
            code="HIGH_FILE_SPRAWL",
            category="size",
            score_delta=config.penalty_high_files,
            severity="warning",
            description=f"High file sprawl ({total_files} files changed). High context-switching cost.",
            badge="📂 File Sprawl (>15 files)",
        ))
        badges.append("📂 File Sprawl")
    elif total_files >= config.medium_files_threshold:
        signals.append(HealthSignal(
            code="MEDIUM_FILE_SPRAWL",
            category="size",
            score_delta=config.penalty_medium_files,
            severity="info",
            description=f"Moderate file sprawl ({total_files} files changed).",
        ))

    # ── 3. Test Coverage & Signals ───────────────────────────────────────────
    test_files = [f for f in changed_files if _is_test_file(f)]
    non_test_files = [f for f in changed_files if not _is_test_file(f)]
    has_tests = len(test_files) > 0

    if has_tests:
        signals.append(HealthSignal(
            code="TESTS_INCLUDED",
            category="test",
            score_delta=config.bonus_tests_included,
            severity="positive",
            description=f"Includes test file updates ({len(test_files)} test file(s) modified).",
            badge="🧪 Tests Included",
        ))
        badges.append("🧪 Tests Included")
    elif len(non_test_files) > 0 and total_changes > 50:
        signals.append(HealthSignal(
            code="NO_TESTS_INCLUDED",
            category="test",
            score_delta=config.penalty_no_tests,
            severity="warning",
            description="Source code modified with over 50 lines changed, but no test files modified.",
            badge="⚠️ No Tests",
        ))
        badges.append("⚠️ No Tests")
        recommendations.append("Add unit or integration test cases to cover the modified logic.")

    # ── 4. PR Context & Description Signals ─────────────────────────────────
    clean_desc = pr_description.strip() if pr_description else ""
    if len(clean_desc) < 20:
        signals.append(HealthSignal(
            code="EMPTY_OR_MINIMAL_DESCRIPTION",
            category="docs",
            score_delta=config.penalty_empty_description,
            severity="warning",
            description="PR description is missing or minimal (<20 chars). Reviewers lack context.",
            badge="📝 Sparse Description",
        ))
        badges.append("📝 Sparse Description")
        recommendations.append("Provide a detailed PR description explaining the 'why', testing steps, and background.")
    elif len(clean_desc) >= 100:
        signals.append(HealthSignal(
            code="RICH_DESCRIPTION",
            category="docs",
            score_delta=config.bonus_rich_description,
            severity="positive",
            description="Detailed PR description provided with comprehensive context.",
            badge="📖 Well Documented",
        ))

    # ── 5. Static AST Analysis Signals (tree-sitter) ─────────────────────────
    ast_critical_count = 0
    ast_warning_count = 0

    syntax_errors = [f for f in ast_findings if getattr(f, "check", "") == "SYNTAX_ERROR"]
    secrets = [f for f in ast_findings if getattr(f, "check", "") == "HARDCODED_SECRET"]
    complexities = [f for f in ast_findings if getattr(f, "check", "") == "COMPLEXITY"]
    missing_docstrings = [f for f in ast_findings if getattr(f, "check", "") == "MISSING_DOCSTRING"]
    unused_imports = [f for f in ast_findings if getattr(f, "check", "") == "UNUSED_IMPORT"]

    if syntax_errors:
        ast_critical_count += len(syntax_errors)
        delta = config.penalty_ast_syntax_error * len(syntax_errors)
        signals.append(HealthSignal(
            code="AST_SYNTAX_ERRORS",
            category="ast",
            score_delta=delta,
            severity="critical",
            description=f"Syntax error(s) detected in {len(syntax_errors)} location(s). Code cannot parse.",
            badge="🔴 Syntax Error",
        ))
        badges.append("🔴 Syntax Error")
        recommendations.append("Fix syntax errors before merging — the codebase will fail to parse/execute.")

    if secrets:
        ast_critical_count += len(secrets)
        delta = config.penalty_ast_secret * len(secrets)
        signals.append(HealthSignal(
            code="AST_HARDCODED_SECRETS",
            category="ast",
            score_delta=delta,
            severity="critical",
            description=f"Potential hardcoded secret(s) found in {len(secrets)} location(s).",
            badge="🔒 Secret Detected",
        ))
        badges.append("🔒 Secret Detected")
        recommendations.append("Remove hardcoded secrets and place credentials into environment variables.")

    if complexities:
        ast_warning_count += len(complexities)
        delta = config.penalty_ast_complexity * len(complexities)
        signals.append(HealthSignal(
            code="AST_HIGH_COMPLEXITY",
            category="ast",
            score_delta=delta,
            severity="warning",
            description=f"High code complexity detected in {len(complexities)} function/method(s).",
            badge="⚙️ High Complexity",
        ))
        recommendations.append("Refactor complex functions to improve maintainability and readability.")

    if missing_docstrings:
        raw_delta = config.penalty_ast_missing_docstring * len(missing_docstrings)
        delta = max(config.max_penalty_docstrings, raw_delta)
        signals.append(HealthSignal(
            code="AST_MISSING_DOCSTRINGS",
            category="ast",
            score_delta=delta,
            severity="info",
            description=f"{len(missing_docstrings)} public class/function(s) missing docstrings.",
        ))

    if unused_imports:
        raw_delta = config.penalty_ast_unused_import * len(unused_imports)
        delta = max(config.max_penalty_unused_imports, raw_delta)
        signals.append(HealthSignal(
            code="AST_UNUSED_IMPORTS",
            category="ast",
            score_delta=delta,
            severity="info",
            description=f"{len(unused_imports)} unused import(s) detected.",
        ))

    # ── 6. LLM Review Severity Signals ───────────────────────────────────────
    llm_critical_count = 0
    llm_warning_count = 0

    llm_crits = [c for c in llm_comments if getattr(c, "severity", "") == "critical"]
    llm_warns = [c for c in llm_comments if getattr(c, "severity", "") == "warning"]
    llm_suggs = [c for c in llm_comments if getattr(c, "severity", "") == "suggestion"]
    llm_praises = [c for c in llm_comments if getattr(c, "severity", "") == "praise"]

    if llm_crits:
        llm_critical_count += len(llm_crits)
        delta = config.penalty_llm_critical * len(llm_crits)
        signals.append(HealthSignal(
            code="LLM_CRITICAL_FINDINGS",
            category="llm",
            score_delta=delta,
            severity="critical",
            description=f"AI Review identified {len(llm_crits)} critical issue(s) (bugs/security/breaking changes).",
            badge="🚨 AI Critical Issue",
        ))
        badges.append("🚨 AI Critical Issue")

    if llm_warns:
        llm_warning_count += len(llm_warns)
        delta = config.penalty_llm_warning * len(llm_warns)
        signals.append(HealthSignal(
            code="LLM_WARNING_FINDINGS",
            category="llm",
            score_delta=delta,
            severity="warning",
            description=f"AI Review identified {len(llm_warns)} warning-level issue(s).",
        ))

    if llm_suggs:
        raw_delta = config.penalty_llm_suggestion * len(llm_suggs)
        delta = max(config.max_penalty_llm_suggestions, raw_delta)
        signals.append(HealthSignal(
            code="LLM_SUGGESTION_FINDINGS",
            category="llm",
            score_delta=delta,
            severity="info",
            description=f"AI Review provided {len(llm_suggs)} suggestion(s) for optimization/style.",
        ))

    if llm_praises:
        raw_bonus = config.bonus_llm_praise * len(llm_praises)
        bonus = min(config.max_bonus_llm_praise, raw_bonus)
        signals.append(HealthSignal(
            code="LLM_PRAISE_COMMENTS",
            category="llm",
            score_delta=bonus,
            severity="positive",
            description=f"AI Review highlighted {len(llm_praises)} good pattern(s) in the code.",
        ))

    # ── 7. Score Calculation & Grading ───────────────────────────────────────
    raw_score = config.base_score + sum(s.score_delta for s in signals)
    score = max(0, min(100, raw_score))

    # Grade & Risk Mapping
    if score >= 90:
        grade = "A+"
        risk_level = "Low"
        status_emoji = "💚"
    elif score >= 80:
        grade = "A"
        risk_level = "Low"
        status_emoji = "🟢"
    elif score >= 70:
        grade = "B"
        risk_level = "Medium"
        status_emoji = "🟡"
    elif score >= 60:
        grade = "C"
        risk_level = "Medium"
        status_emoji = "🟠"
    elif score >= 40:
        grade = "D"
        risk_level = "High"
        status_emoji = "🔴"
    else:
        grade = "F"
        risk_level = "Critical"
        status_emoji = "🚨"

    # Deduplicate recommendations while preserving order
    unique_recs = list(dict.fromkeys(recommendations))

    return PRHealthReport(
        score=score,
        grade=grade,
        risk_level=risk_level,
        status_emoji=status_emoji,
        signals=signals,
        badges=badges,
        recommendations=unique_recs,
        total_additions=additions,
        total_deletions=deletions,
        total_files_changed=total_files,
        has_tests=has_tests,
        ast_critical_count=ast_critical_count,
        ast_warning_count=ast_warning_count,
        llm_critical_count=llm_critical_count,
        llm_warning_count=llm_warning_count,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Markdown Formatter for GitHub Summary
# ─────────────────────────────────────────────────────────────────────────────

def format_health_score_markdown(report: PRHealthReport) -> str:
    """
    Format the PRHealthReport into a clean GitHub-flavored markdown widget.

    Example Output:
    ### 📊 PR Health Score: 85/100 (Grade: A) 🟢
    **Risk Level:** Low | **Badges:** `✨ Concise PR` `🧪 Tests Included`
    """
    badges_str = " ".join(f"`{b}`" for b in report.badges) if report.badges else "_None_"
    
    lines = [
        f"### 📊 PR Health Score: **{report.score}/100** (Grade: **{report.grade}**) {report.status_emoji}\n",
        f"**Risk Level:** `{report.risk_level}` | **Badges:** {badges_str}\n",
    ]

    # Signal breakdown table or summary
    positive_signals = [s for s in report.signals if s.score_delta > 0]
    negative_signals = [s for s in report.signals if s.score_delta < 0]

    if negative_signals:
        lines.append("<details><summary><b>⚠️ Health Deductions & Signals</b></summary>\n")
        lines.append("| Signal | Category | Impact | Description |")
        lines.append("| :--- | :--- | :---: | :--- |")
        for s in negative_signals:
            lines.append(f"| `{s.code}` | _{s.category.capitalize()}_ | `{s.score_delta}` | {s.description} |")
        lines.append("</details>\n")

    if report.recommendations:
        lines.append("**💡 Key Recommendations:**")
        for rec in report.recommendations:
            lines.append(f"- {rec}")
        lines.append("")

    return "\n".join(lines)
