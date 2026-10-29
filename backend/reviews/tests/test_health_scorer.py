"""
Tests and tuning scenarios for reviews/health_scorer.py.

The SCENARIOS table doubles as documentation: each row is a realistic PR and the
grade we expect. If you change a weight in HealthScorerConfig, re-run this file
and see which scenarios move.
"""
import json
from types import SimpleNamespace as NS

import pytest

from reviews.health_scorer import (
    HealthScorerConfig,
    calculate_health_score,
    extract_changed_files,
    format_health_score_markdown,
    is_test_file,
)

GOOD_DESC = "Adds retry logic to the webhook handler. Tested locally with duplicate deliveries."


def diff_of(n_added: int, n_removed: int = 0) -> str:
    return "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n" + "+x\n" * n_added + "-y\n" * n_removed


def static(rule_id, n=1):
    return [NS(rule_id=rule_id, severity="info") for _ in range(n)]


def llm(severity, n=1):
    return [NS(severity=severity) for _ in range(n)]


# name, files, added lines, description, static findings, llm findings, expected grade
SCENARIOS = [
    ("tiny clean PR with tests and docs", ["app/a.py", "tests/test_a.py"], 40, GOOD_DESC, [], [], "A+"),
    ("tiny PR, no description", ["app/a.py"], 30, "", [], [], "A+"),
    ("medium PR, no tests, short description", ["app/a.py"], 120, "fix", [], [], "B"),
    ("hardcoded secret", ["app/a.py"], 40, GOOD_DESC, static("TS-PY-005"), [], "B"),
    ("secret + AI error", ["app/a.py"], 40, GOOD_DESC, static("TS-PY-005"), llm("error"), "D"),
    ("huge sprawling PR, no tests, no docs", [f"f{i}.py" for i in range(20)], 1500, "", [], [], "F"),
    ("only style suggestions", ["app/a.py", "tests/test_a.py"], 80, GOOD_DESC, static("TS-PY-001", 3), llm("info", 3), "A+"),
]


@pytest.mark.parametrize("name,files,added,desc,ast,llm_c,grade", SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_scenarios_get_expected_grade(name, files, added, desc, ast, llm_c, grade):
    report = calculate_health_score(files, diff_of(added), "title", desc, ast, llm_c)
    assert report.grade == grade, f"{name}: score={report.score}, signals={[s.code for s in report.signals]}"


def test_score_is_clamped_between_0_and_100():
    best = calculate_health_score(["a.py", "tests/test_a.py"], diff_of(5), "t", GOOD_DESC)
    worst = calculate_health_score(
        [f"f{i}.py" for i in range(30)], diff_of(3000), "t", "",
        static("TS-PY-005", 5), llm("error", 10),
    )
    assert best.score == 100
    assert worst.score == 0 and worst.grade == "F" and worst.risk_level == "Critical"


def test_static_rule_penalty_is_capped():
    many = calculate_health_score(["a.py"], diff_of(10), "t", GOOD_DESC, static("TS-PY-001", 40))
    penalty = next(s for s in many.signals if s.code == "STATIC_UNUSED_IMPORTS")
    assert penalty.score_delta == -10  # 40 findings would be -80 without the cap


def test_llm_penalties_are_capped_per_severity():
    r = calculate_health_score(["a.py"], diff_of(10), "t", GOOD_DESC, [], llm("error", 6) + llm("warning", 9))
    deltas = {s.code: s.score_delta for s in r.signals}
    assert deltas["LLM_ERROR_FINDINGS"] == -50
    assert deltas["LLM_WARNING_FINDINGS"] == -30


def test_no_tests_penalty_only_when_enough_source_changed():
    small = calculate_health_score(["a.py"], diff_of(20), "t", GOOD_DESC)
    big = calculate_health_score(["a.py"], diff_of(200), "t", GOOD_DESC)
    assert "NO_TESTS_INCLUDED" not in [s.code for s in small.signals]
    assert "NO_TESTS_INCLUDED" in [s.code for s in big.signals]


def test_each_static_rule_maps_to_its_own_signal():
    expected = {
        "TS-PY-001": "STATIC_UNUSED_IMPORTS", "TS-PY-002": "STATIC_LONG_FUNCTIONS",
        "TS-PY-003": "STATIC_BARE_EXCEPT", "TS-PY-004": "STATIC_DEEP_NESTING",
        "TS-PY-005": "STATIC_HARDCODED_SECRETS",
    }
    for rule, code in expected.items():
        r = calculate_health_score(["a.py"], diff_of(10), "t", GOOD_DESC, static(rule))
        assert code in [s.code for s in r.signals], rule


def test_unknown_rule_ids_are_ignored():
    r = calculate_health_score(["a.py"], diff_of(10), "t", GOOD_DESC, static("TS-PY-999"))
    assert not [s for s in r.signals if s.category == "static"]


def test_tuning_changes_the_grade():
    """Raising the secret penalty moves the 'hardcoded secret' PR down a grade."""
    args = (["app/a.py"], diff_of(40), "t", GOOD_DESC, static("TS-PY-005"))
    default = calculate_health_score(*args)
    strict_cfg = HealthScorerConfig()
    strict_cfg.static_rules["TS-PY-005"]["per"] = -50
    strict = calculate_health_score(*args, config=strict_cfg)
    assert strict.score < default.score


def test_grade_boundaries_are_configurable():
    cfg = HealthScorerConfig(grade_a_plus=101)  # nothing can be A+
    r = calculate_health_score(["a.py", "tests/test_a.py"], diff_of(5), "t", GOOD_DESC, config=cfg)
    assert r.grade == "A"


@pytest.mark.parametrize("path,expected", [
    ("tests/test_views.py", True), ("app/test_views.py", True), ("src/app.test.js", True),
    ("src/app.spec.ts", True), ("pkg/models_test.py", True), ("src/test/helper.py", True),
    ("app/latest.py", False), ("app/contest.py", False), ("app/views.py", False),
])
def test_is_test_file(path, expected):
    assert is_test_file(path) is expected


def test_extract_changed_files_dedupes_and_keeps_order():
    diff = ("diff --git a/x.py b/x.py\n+a\n" "diff --git a/y/z.py b/y/z.py\n+b\n" "diff --git a/x.py b/x.py\n+c\n")
    assert extract_changed_files(diff) == ["x.py", "y/z.py"]


def test_report_is_json_serialisable_and_has_breakdown():
    r = calculate_health_score(["a.py"], diff_of(200), "t", "", static("TS-PY-005"), llm("error"))
    data = json.loads(json.dumps(r.to_dict()))
    assert {"score", "grade", "risk_level", "signals", "badges", "recommendations", "metrics"} <= data.keys()
    assert data["metrics"]["static_critical"] == 1 and data["metrics"]["llm_errors"] == 1


def test_markdown_explains_deductions():
    r = calculate_health_score(["a.py"], diff_of(200), "t", "", static("TS-PY-005"))
    md = format_health_score_markdown(r)
    assert f"{r.score}/100" in md and "Why this score?" in md and "STATIC_HARDCODED_SECRETS" in md
