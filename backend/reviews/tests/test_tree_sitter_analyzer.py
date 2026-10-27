"""
reviews/tests/test_tree_sitter_analyzer.py
==========================================
Unit tests for the tree-sitter static analysis engine.

One snippet per check (dirty + clean) so each rule is exercised in isolation.
Run with:  python -m pytest reviews/tests/test_tree_sitter_analyzer.py -v
"""

import pytest

# Skip entire module if tree-sitter is not installed (CI without optional deps)
pytest.importorskip("tree_sitter", reason="tree-sitter not installed")
pytest.importorskip("tree_sitter_python", reason="tree-sitter-python not installed")

from reviews.tree_sitter_analyzer import (  # noqa: E402
    analyze_python,
    _check_unused_imports,
    _check_long_functions,
    _check_bare_except,
    _check_deep_nesting,
    _check_hardcoded_secrets,
    _PARSER,
    TREE_SITTER_AVAILABLE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse(source: str):
    """Return the root node of *source* after parsing."""
    tree = _PARSER.parse(source.encode("utf-8"))
    return tree.root_node


def _all_lines(source: str) -> set[int]:
    """Return a set of every line number in source (1-based)."""
    return set(range(1, source.count("\n") + 2))


# ---------------------------------------------------------------------------
# Guard: skip if unavailable
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")
def test_tree_sitter_available():
    assert TREE_SITTER_AVAILABLE, "tree-sitter should be importable in this env"


# ===========================================================================
# TS-PY-001  Unused imports
# ===========================================================================

UNUSED_IMPORT_DIRTY = """\
import os
import sys
import json

x = os.getcwd()
"""

UNUSED_IMPORT_CLEAN = """\
import os
import sys

x = os.getcwd()
path = sys.argv[0]
"""

UNUSED_IMPORT_ALL_USED = """\
import os
import sys
import json

x = os.getcwd()
y = sys.argv
z = json.dumps({})
"""


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")
def test_unused_import_detected():
    root = _parse(UNUSED_IMPORT_DIRTY)
    findings = _check_unused_imports(root, UNUSED_IMPORT_DIRTY.splitlines())
    rule_ids = [f.rule_id for f in findings]
    assert "TS-PY-001" in rule_ids, "Should flag at least one unused import"
    # 'sys' and 'json' are unused
    messages = " ".join(f.message for f in findings)
    assert "sys" in messages or "json" in messages


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")
def test_unused_import_clean():
    root = _parse(UNUSED_IMPORT_ALL_USED)
    findings = _check_unused_imports(root, UNUSED_IMPORT_ALL_USED.splitlines())
    assert findings == [], f"Expected no findings, got {findings}"


# ===========================================================================
# TS-PY-002  Long functions
# ===========================================================================

def _make_long_function(n_lines: int) -> str:
    """Return a function definition that is exactly n_lines lines long."""
    body = "\n".join(f"    x_{i} = {i}" for i in range(n_lines - 1))
    return f"def long_func():\n{body}\n    return x_0\n"


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")
def test_long_function_detected():
    source = _make_long_function(55)
    root = _parse(source)
    findings = _check_long_functions(root)
    assert any(f.rule_id == "TS-PY-002" for f in findings), "55-line function should be flagged"


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")
def test_short_function_clean():
    source = "def short():\n    return 42\n"
    root = _parse(source)
    findings = _check_long_functions(root)
    assert findings == [], "Short function should not be flagged"


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")
def test_long_function_exactly_at_threshold_not_flagged():
    # _make_long_function(n) produces: def(1) + n-1 body lines + return(1) = n+1 lines total.
    # To get exactly 50 lines (the threshold), pass n=49.
    source = _make_long_function(49)
    root = _parse(source)
    findings = _check_long_functions(root)
    assert findings == [], "Exactly-50-line function should not be flagged"



# ===========================================================================
# TS-PY-003  Bare / empty except
# ===========================================================================

BARE_EXCEPT_DIRTY = """\
try:
    x = int(input())
except:
    pass
"""

EMPTY_EXCEPT_DIRTY = """\
try:
    x = int(input())
except ValueError:
    pass
"""

EXCEPT_CLEAN = """\
import logging
logger = logging.getLogger(__name__)

try:
    x = int(input())
except ValueError as e:
    logger.warning("Bad value: %s", e)
"""


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")
def test_bare_except_detected():
    root = _parse(BARE_EXCEPT_DIRTY)
    findings = _check_bare_except(root)
    assert any(f.rule_id == "TS-PY-003" for f in findings), "Bare except should be flagged"


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")
def test_empty_except_detected():
    root = _parse(EMPTY_EXCEPT_DIRTY)
    findings = _check_bare_except(root)
    assert any(f.rule_id == "TS-PY-003" for f in findings), "Empty except body should be flagged"


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")
def test_good_except_clean():
    root = _parse(EXCEPT_CLEAN)
    findings = _check_bare_except(root)
    assert findings == [], f"Good except should not be flagged, got {findings}"


# ===========================================================================
# TS-PY-004  Deep nesting
# ===========================================================================

DEEP_NESTING_DIRTY = """\
def process(items):
    for item in items:
        if item:
            for sub in item:
                if sub:
                    with open("f") as f:
                        pass
"""

SHALLOW_NESTING_CLEAN = """\
def process(items):
    for item in items:
        if item:
            handle(item)

def handle(item):
    pass
"""


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")
def test_deep_nesting_detected():
    root = _parse(DEEP_NESTING_DIRTY)
    findings = _check_deep_nesting(root)
    assert any(f.rule_id == "TS-PY-004" for f in findings), "Deep nesting should be flagged"


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")
def test_shallow_nesting_clean():
    root = _parse(SHALLOW_NESTING_CLEAN)
    findings = _check_deep_nesting(root)
    assert findings == [], f"Shallow nesting should not be flagged, got {findings}"


# ===========================================================================
# TS-PY-005  Hardcoded secrets
# ===========================================================================

SECRET_DIRTY = """\
API_KEY = "sk-abc123realtoken"
DATABASE_PASSWORD = "SuperSecret99!"
"""

SECRET_PLACEHOLDER = """\
API_KEY = "your-api-key-here"
PASSWORD = ""
TOKEN = "changeme"
"""

SECRET_ENV_CLEAN = """\
import os
from decouple import config

API_KEY = os.environ["API_KEY"]
PASSWORD = config("DB_PASSWORD")
"""


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")
def test_hardcoded_secret_detected():
    root = _parse(SECRET_DIRTY)
    findings = _check_hardcoded_secrets(root)
    assert any(f.rule_id == "TS-PY-005" for f in findings), "Hardcoded secret should be flagged"
    rule_findings = [f for f in findings if f.rule_id == "TS-PY-005"]
    messages = " ".join(f.message for f in rule_findings)
    assert "API_KEY" in messages or "DATABASE_PASSWORD" in messages


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")
def test_placeholder_secret_not_flagged():
    root = _parse(SECRET_PLACEHOLDER)
    findings = _check_hardcoded_secrets(root)
    assert findings == [], f"Placeholder values should not be flagged, got {findings}"


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")
def test_env_var_secret_clean():
    root = _parse(SECRET_ENV_CLEAN)
    findings = _check_hardcoded_secrets(root)
    assert findings == [], f"Env-var reads should not be flagged, got {findings}"


# ===========================================================================
# Integration: analyze_python()  — changed_lines filtering
# ===========================================================================

MIXED_SOURCE = """\
import os
import sys

API_KEY = "real-secret-key-abc"

def short():
    return 42
"""


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")
def test_analyze_python_filters_to_changed_lines():
    # Only line 4 is "changed" — that's where API_KEY is
    changed = {4}
    findings = analyze_python(MIXED_SOURCE, "mymodule.py", changed)
    # Should include the secret finding (line 4)
    assert any(f.rule_id == "TS-PY-005" for f in findings), \
        "Secret on changed line should appear"
    # Should NOT include unused import findings (lines 1-2)
    for f in findings:
        assert f.line_number in changed, \
            f"Finding on line {f.line_number} should not appear (not in changed_lines)"


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")
def test_analyze_python_clean_file_no_findings():
    clean = """\
import os

def fetch_value():
    return os.environ.get("KEY", "default")
"""
    findings = analyze_python(clean, "clean.py", _all_lines(clean))
    assert findings == [], f"Clean file should produce no findings, got {findings}"


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")
def test_analyze_python_sets_file_path():
    findings = analyze_python(SECRET_DIRTY, "backend/service.py", _all_lines(SECRET_DIRTY))
    for f in findings:
        assert f.file_path == "backend/service.py", "file_path should be set by analyze_python"


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")
def test_analyze_python_empty_changed_lines_returns_nothing():
    findings = analyze_python(SECRET_DIRTY, "service.py", set())
    assert findings == [], "Empty changed_lines should yield no findings"
