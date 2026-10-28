"""
reviews/tests/test_merge_dedupe.py
==================================
Unit tests for proximity-aware merge & deduplication logic.
"""

from reviews.llm_reviewer import LLMComment, merge_and_dedupe
from reviews.tree_sitter_analyzer import Finding


def test_merge_exact_line_match():
    llm = [
        LLMComment(
            file_path="main.py",
            line_number=15,
            severity="warning",
            category="bug",
            message="Bare except caught. Catch specific error.",
            suggestion="except Exception as exc:",
        )
    ]
    static = [
        Finding(
            file_path="main.py",
            line_number=15,
            severity="warning",
            category="reliability",
            message="TS-PY-003 Bare except block",
            suggestion="",
            rule_id="TS-PY-003",
        )
    ]

    filtered_llm, annotated_static = merge_and_dedupe(llm, static)

    assert len(filtered_llm) == 0, "Duplicate LLM comment on same line should be dropped"
    assert len(annotated_static) == 1
    assert "TS-PY-003" in annotated_static[0].message
    assert "LLM also flagged this line" in annotated_static[0].message
    assert annotated_static[0].suggestion == "except Exception as exc:", "Should inherit LLM suggestion"


def test_merge_proximity_line_match():
    # Tree-sitter flags line 10, LLM flags line 12 (within proximity_window=2)
    llm = [
        LLMComment(
            file_path="main.py",
            line_number=12,
            severity="error",
            category="security",
            message="Hardcoded password variable found.",
            suggestion="os.environ.get('PASSWORD')",
        )
    ]
    static = [
        Finding(
            file_path="main.py",
            line_number=10,
            severity="warning",
            category="security",
            message="TS-PY-005 Hardcoded secret",
            rule_id="TS-PY-005",
        )
    ]

    filtered_llm, annotated_static = merge_and_dedupe(llm, static, proximity_window=2)

    assert len(filtered_llm) == 0, "Nearby duplicate LLM comment should be merged and dropped"
    assert len(annotated_static) == 1
    # Severity upgraded from warning to error
    assert annotated_static[0].severity == "error"
    assert annotated_static[0].suggestion == "os.environ.get('PASSWORD')"
    assert "nearby line 12" in annotated_static[0].message


def test_no_dedupe_on_different_files_or_far_lines():
    llm = [
        LLMComment(
            file_path="utils.py",
            line_number=10,
            severity="info",
            category="style",
            message="Function docstring missing.",
        )
    ]
    static = [
        Finding(
            file_path="main.py",
            line_number=10,
            severity="warning",
            category="reliability",
            message="Bare except",
            rule_id="TS-PY-003",
        )
    ]

    filtered_llm, annotated_static = merge_and_dedupe(llm, static)

    assert len(filtered_llm) == 1, "Different files must not be merged"
    assert len(annotated_static) == 1
