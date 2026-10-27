"""
reviews/tree_sitter_analyzer.py
================================
Deterministic static analysis engine for Python using tree-sitter.

Uses only the stable tree-sitter Node API (.type, .children, .named_children,
.start_point, .end_point, .text, .child_by_field_name) so it works with
tree-sitter >= 0.22, including the 0.24+ releases that removed Language.query().

Checks
------
  TS-PY-001  Unused imports          (maintainability, info)
  TS-PY-002  Long function >50 lines (maintainability, info)
  TS-PY-003  Bare / empty except     (reliability,     warning)
  TS-PY-004  Deep nesting >4 levels  (maintainability, warning)
  TS-PY-005  Hardcoded secrets       (security,        error, CWE-798)

Public API
----------
    findings = analyze_python(source, file_path, changed_lines)

Only findings whose line_number is in *changed_lines* are returned.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional import — degrade gracefully if tree-sitter is not installed
# ---------------------------------------------------------------------------

try:
    from tree_sitter import Language, Parser  # type: ignore
    import tree_sitter_python as tspython    # type: ignore

    _PY_LANGUAGE = Language(tspython.language())
    _PARSER = Parser(_PY_LANGUAGE)
    TREE_SITTER_AVAILABLE = True
    logger.debug("tree-sitter %s loaded (Python grammar ready).", _PY_LANGUAGE.name)
except Exception as _ts_exc:  # noqa: BLE001
    TREE_SITTER_AVAILABLE = False
    _PY_LANGUAGE = None   # type: ignore
    _PARSER = None        # type: ignore
    logger.warning("tree-sitter unavailable — static analysis disabled. (%s)", _ts_exc)


# ---------------------------------------------------------------------------
# Finding dataclass  (same shape as LLMComment / ReviewComment)
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    """One static-analysis finding."""
    file_path: str
    line_number: int       # 1-based, new-file line
    severity: str          # "info" | "warning" | "error"
    category: str          # "maintainability" | "bug" | "security" | …
    message: str
    suggestion: str = ""
    rule_id: str = ""      # e.g. "TS-PY-001"
    source: str = "static" # ReviewComment.Source.STATIC


# ---------------------------------------------------------------------------
# Generic AST helpers  (no query API — works with all tree-sitter versions)
# ---------------------------------------------------------------------------

def _node_text(node) -> str:
    return node.text.decode("utf-8", errors="replace") if node.text else ""

def _line(node) -> int:
    return node.start_point[0] + 1   # 1-based

def _find_all(root, *node_types: str) -> list:
    """BFS walk — return every node whose .type is in node_types."""
    wanted = set(node_types)
    results = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type in wanted:
            results.append(node)
        stack.extend(node.children)
    return results

def _all_identifier_texts(root) -> set[str]:
    """Return set of every identifier text in the whole tree."""
    ids: set[str] = set()
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type == "identifier":
            ids.add(_node_text(node))
        stack.extend(node.children)
    return ids

def _count_identifier(root, name: str) -> int:
    """Count how many times *name* appears as an identifier in the tree."""
    count = 0
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type == "identifier" and _node_text(node) == name:
            count += 1
            if count > 1:
                return count   # early exit — we only need to know >1
        stack.extend(node.children)
    return count


# ---------------------------------------------------------------------------
# TS-PY-001  Unused imports
# ---------------------------------------------------------------------------

def _extract_import_aliases(import_node) -> list[tuple[str, int]]:
    """
    Return (alias_name, 1-based-line) pairs for an import_statement or
    import_from_statement node.

    Handles:
      import foo              → ("foo", line)
      import foo as bar       → ("bar", line)
      from foo import bar     → ("bar", line)
      from foo import bar as z→ ("z",   line)
      from foo import *       → (skipped)
    """
    aliases: list[tuple[str, int]] = []
    line = _line(import_node)

    for child in import_node.named_children:
        ctype = child.type
        if ctype == "dotted_name":
            parts = _node_text(child).split(".")
            if parts:
                aliases.append((parts[0], line))
        elif ctype == "aliased_import":
            alias = child.child_by_field_name("alias")
            if alias:
                aliases.append((_node_text(alias), line))
            else:
                name = child.child_by_field_name("name")
                if name:
                    aliases.append((_node_text(name).split(".")[0], line))
        elif ctype == "identifier":
            text = _node_text(child)
            if text:
                aliases.append((text, line))
        elif ctype == "wildcard_import":
            pass   # can't check `from x import *`
    return aliases


def _check_unused_imports(root, source_lines: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[str] = set()

    for imp_node in _find_all(root, "import_statement", "import_from_statement"):
        for name, line in _extract_import_aliases(imp_node):
            if name in seen:
                continue
            seen.add(name)
            # Count appears in entire tree; import site counts as 1
            if _count_identifier(root, name) <= 1:
                raw_line = source_lines[line - 1].strip() if line <= len(source_lines) else ""
                findings.append(Finding(
                    file_path="",
                    line_number=line,
                    severity="info",
                    category="maintainability",
                    message=f"Unused import '{name}' — imported but never referenced.",
                    suggestion=f"Remove `{raw_line}` or use the import.",
                    rule_id="TS-PY-001",
                ))
    return findings


# ---------------------------------------------------------------------------
# TS-PY-002  Long functions >50 lines
# ---------------------------------------------------------------------------

LONG_FUNC_THRESHOLD = 50


def _check_long_functions(root) -> list[Finding]:
    findings: list[Finding] = []
    for func_node in _find_all(root, "function_definition"):
        start = func_node.start_point[0]
        end   = func_node.end_point[0]
        length = end - start + 1
        if length > LONG_FUNC_THRESHOLD:
            name_node = func_node.child_by_field_name("name")
            func_name = _node_text(name_node) if name_node else "<anonymous>"
            findings.append(Finding(
                file_path="",
                line_number=start + 1,
                severity="info",
                category="maintainability",
                message=(
                    f"Function '{func_name}' is {length} lines long "
                    f"(threshold: {LONG_FUNC_THRESHOLD}). "
                    "Consider splitting it into smaller, focused functions."
                ),
                suggestion="Extract logical blocks into well-named helper functions.",
                rule_id="TS-PY-002",
            ))
    return findings


# ---------------------------------------------------------------------------
# TS-PY-003  Bare / empty except
# ---------------------------------------------------------------------------

def _is_bare_except(except_node) -> bool:
    """True if this except clause catches no specific exception type.

    From the AST output (tree-sitter 0.26):
    - bare `except:` has named_children = [block]
    - `except ValueError:` has named_children = [identifier, block]
    - `except ValueError as e:` has named_children = [as_pattern, block]

    So: bare iff the FIRST named child is 'block'.
    """
    first = next((c for c in except_node.named_children), None)
    if first is None:
        return True   # no children at all — treat as bare
    return first.type == "block"


def _body_is_only_pass(except_node) -> bool:
    """True if the except body is a single ``pass`` statement.

    The body is always a 'block' node (last named child of except_clause).
    Check whether that block contains only a pass_statement.
    """
    # The block is the LAST named child
    named = list(except_node.named_children)
    if not named:
        return False
    block = named[-1]
    if block.type != "block":
        return False
    non_comment = [c for c in block.named_children if c.type != "comment"]
    return len(non_comment) == 1 and non_comment[0].type == "pass_statement"


def _check_bare_except(root) -> list[Finding]:
    findings: list[Finding] = []
    for node in _find_all(root, "except_clause"):
        if _is_bare_except(node):
            findings.append(Finding(
                file_path="",
                line_number=_line(node),
                severity="warning",
                category="bug",
                message=(
                    "Bare `except:` catches ALL exceptions including "
                    "KeyboardInterrupt and SystemExit."
                ),
                suggestion="Replace with `except Exception as e:` or a more specific type.",
                rule_id="TS-PY-003",
            ))
        elif _body_is_only_pass(node):
            findings.append(Finding(
                file_path="",
                line_number=_line(node),
                severity="warning",
                category="bug",
                message=(
                    "Empty `except` block silently swallows exceptions. "
                    "At minimum log the error."
                ),
                suggestion="Add `logger.exception(...)` or re-raise inside the except block.",
                rule_id="TS-PY-003",
            ))
    return findings


# ---------------------------------------------------------------------------
# TS-PY-004  Deep nesting >4 levels
# ---------------------------------------------------------------------------

_NESTING_TYPES = frozenset([
    "if_statement", "for_statement", "while_statement",
    "with_statement", "try_statement", "match_statement",
])
_RESET_TYPES = frozenset(["function_definition", "class_definition", "lambda"])
NESTING_THRESHOLD = 4


def _find_deep_nesting(node, depth: int, reported: set[int]) -> list[Finding]:
    findings: list[Finding] = []

    # Reset depth at function/class boundaries
    if node.type in _RESET_TYPES and depth > 0:
        for child in node.named_children:
            findings.extend(_find_deep_nesting(child, 0, reported))
        return findings

    if node.type in _NESTING_TYPES:
        depth += 1
        if depth > NESTING_THRESHOLD:
            ln = _line(node)
            if ln not in reported:
                reported.add(ln)
                findings.append(Finding(
                    file_path="",
                    line_number=ln,
                    severity="warning",
                    category="maintainability",
                    message=(
                        f"Nesting depth {depth} exceeds threshold of "
                        f"{NESTING_THRESHOLD}. Deeply nested code is hard to read and test."
                    ),
                    suggestion=(
                        "Use early returns (guard clauses), extract helpers, "
                        "or flatten the logic."
                    ),
                    rule_id="TS-PY-004",
                ))

    for child in node.named_children:
        findings.extend(_find_deep_nesting(child, depth, reported))
    return findings


def _check_deep_nesting(root) -> list[Finding]:
    return _find_deep_nesting(root, 0, set())


# ---------------------------------------------------------------------------
# TS-PY-005  Hardcoded secrets  (CWE-798)
# ---------------------------------------------------------------------------

_SECRET_VAR_RE = re.compile(
    r"(?i)\b("
    r"api[_\-]?key|secret[_\-]?key?|password|passwd|pwd|"
    r"token|auth[_\-]?token|access[_\-]?key|private[_\-]?key|"
    r"db[_\-]?pass(?:word)?|client[_\-]?secret|webhook[_\-]?secret|"
    r"encryption[_\-]?key|signing[_\-]?key"
    r")\b"
)

_PLACEHOLDER_RE = re.compile(
    r"(?i)(your[_\-]?|change[_\-]?me|replace[_\-]?me|<.*?>|"
    r"\bexample\b|\bplaceholder\b|\bxxx+\b|\btest\b|\bdummy\b|\bfake\b|\btodo\b)"
)

_STRING_NODE_TYPES = {"string", "concatenated_string"}


def _is_non_trivial_string(value_node) -> bool:
    if value_node.type not in _STRING_NODE_TYPES:
        return False
    raw = _node_text(value_node)
    # Strip quote chars
    inner = raw.strip("\"' \t\n").strip('"""').strip("'''")
    if len(inner) < 4:
        return False
    if _PLACEHOLDER_RE.search(inner):
        return False
    return True


def _check_hardcoded_secrets(root) -> list[Finding]:
    findings: list[Finding] = []
    for assign_node in _find_all(root, "assignment"):
        left = assign_node.child_by_field_name("left")
        right = assign_node.child_by_field_name("right")
        if left is None or right is None:
            continue
        if left.type != "identifier":
            continue
        var_name = _node_text(left)
        if not _SECRET_VAR_RE.search(var_name):
            continue
        if not _is_non_trivial_string(right):
            continue
        findings.append(Finding(
            file_path="",
            line_number=_line(left),
            severity="error",
            category="security",
            message=(
                f"Possible hardcoded secret in variable '{var_name}' (CWE-798). "
                "Credentials must never be committed to source control."
            ),
            suggestion=(
                f"Use an environment variable: "
                f"`{var_name} = os.environ['ENV_VAR']` "
                "or python-decouple `config('{var_name}')`."
            ),
            rule_id="TS-PY-005",
        ))
    return findings


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def analyze_python(
    source: str,
    file_path: str,
    changed_lines: set[int],
) -> list[Finding]:
    """
    Run all 5 static checks on *source* (a full Python file).

    Parameters
    ----------
    source:
        Full text of the Python file at head SHA.
    file_path:
        Relative path as it appears in the diff.
    changed_lines:
        Set of 1-based line numbers added/modified in the PR diff.
        Only findings on these lines are returned.

    Returns
    -------
    List of Finding objects with file_path set and line_number in changed_lines.
    """
    if not TREE_SITTER_AVAILABLE:
        logger.warning("tree-sitter not available; skipping static analysis for %s", file_path)
        return []

    try:
        tree = _PARSER.parse(source.encode("utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("tree-sitter failed to parse %s: %s", file_path, exc)
        return []

    root = tree.root_node
    source_lines = source.splitlines()

    all_findings: list[Finding] = []
    all_findings.extend(_check_unused_imports(root, source_lines))
    all_findings.extend(_check_long_functions(root))
    all_findings.extend(_check_bare_except(root))
    all_findings.extend(_check_deep_nesting(root))
    all_findings.extend(_check_hardcoded_secrets(root))

    # Fill file_path and filter to changed lines only
    filtered: list[Finding] = []
    for f in all_findings:
        f.file_path = file_path
        if f.line_number in changed_lines:
            filtered.append(f)

    logger.info(
        "[tree-sitter] %s: %d total findings, %d on changed lines",
        file_path, len(all_findings), len(filtered),
    )
    return filtered
