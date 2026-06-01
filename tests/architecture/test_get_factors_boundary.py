"""Phase 3 — formal-gate-bypass guard for the sandbox-only factor readers.

``get_factors`` / ``get_factor_selection`` (src/alpha_research/factor_library/selection.py)
are SANDBOX/DISCOVERY convenience readers. They are explicitly NOT the formal gate —
formal factor resolution must go through the registry resolver allow-set (P1.2,
``handle_validation_object_resolver``) + the definition-binding gate (P1.3,
``_assert_no_definition_drift``). The readers refuse formal stages at runtime; this
test is the defense-in-depth second layer the design review required.

It scans the **AST** (not raw text) of every formal-path module for any IMPORT (by real
name, so an ``as`` alias is still caught) or any attribute/name USAGE of the two
reader names. A text scan would be wrong here: formal-path modules LEGITIMATELY import
the sibling ``get_factor_catalog`` from the same module, so an import-substring check
would both false-positive on the allowed sibling and miss aliased usage.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# The convenience-reader names that must never appear in a formal path.
FORBIDDEN_NAMES: frozenset[str] = frozenset({"get_factors", "get_factor_selection"})

# Formal-path modules/dirs that resolve factors or run formal validation/backtests.
FORMAL_PATHS: tuple[Path, ...] = (
    PROJECT_ROOT / "src" / "research_orchestrator" / "validation_steps.py",
    PROJECT_ROOT / "src" / "research_orchestrator" / "release_gate.py",
    PROJECT_ROOT / "src" / "research_orchestrator" / "resolver.py",
    PROJECT_ROOT / "src" / "research_orchestrator" / "steps.py",
    PROJECT_ROOT / "src" / "research_orchestrator" / "sealed_backtest_runner.py",
    # Gate C of hypothesis_validation: universe materialization on the formal compute
    # path (imported by validation_steps.py). Reviewer-flagged (PR #32).
    PROJECT_ROOT / "src" / "research_orchestrator" / "prescription_runtime.py",
    PROJECT_ROOT / "src" / "backtest_engine" / "event_driven",
    PROJECT_ROOT / "src" / "backtest_engine" / "vectorized",
)


def _iter_python_files(root: Path) -> list[Path]:
    if root.is_file() and root.suffix == ".py":
        return [root]
    if root.is_dir():
        return sorted(root.rglob("*.py"))
    return []


def _forbidden_usage(tree: ast.AST) -> list[str]:
    """Return human-readable hits for any forbidden import/attribute/name usage."""
    hits: list[str] = []
    for node in ast.walk(tree):
        # Import of the real name, regardless of `as` alias.
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in FORBIDDEN_NAMES:
                    hits.append(f"line {node.lineno}: from {node.module or ''} import {alias.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in FORBIDDEN_NAMES:
                    hits.append(f"line {node.lineno}: import {alias.name}")
        # `module.get_factors(...)` attribute access.
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_NAMES:
            hits.append(f"line {getattr(node, 'lineno', '?')}: attribute .{node.attr}")
        # Direct name reference (call/use) of an imported reader.
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            hits.append(f"line {getattr(node, 'lineno', '?')}: name {node.id}")
    return hits


@pytest.mark.parametrize("formal_path", FORMAL_PATHS, ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
def test_formal_path_does_not_use_sandbox_factor_readers(formal_path: Path) -> None:
    """No formal-path module may import or reference ``get_factors`` /
    ``get_factor_selection`` — those are sandbox-only. Formal resolution stays under the
    P1.2 resolver allow-set + P1.3 definition-binding gate."""
    files = _iter_python_files(formal_path)
    if not files:
        pytest.skip(f"{formal_path} contains no Python files yet")
    failures: list[str] = []
    for file in files:
        try:
            tree = ast.parse(file.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as exc:  # pragma: no cover - a parse failure is itself a problem
            failures.append(f"{file.relative_to(PROJECT_ROOT)}: could not parse ({exc})")
            continue
        for hit in _forbidden_usage(tree):
            failures.append(f"{file.relative_to(PROJECT_ROOT)}: {hit}")
    assert not failures, (
        "Formal-path module(s) reference the sandbox-only factor readers "
        "(get_factors/get_factor_selection). Formal factor resolution must use the "
        "resolver allow-set (P1.2) + definition-binding gate (P1.3):\n  "
        + "\n  ".join(failures)
    )


def test_allowed_sibling_get_factor_catalog_is_not_flagged() -> None:
    """Guard against over-broad matching: importing the SIBLING ``get_factor_catalog``
    (which formal paths legitimately use) must NOT trip the AST scan."""
    sample = (
        "from src.alpha_research.factor_library.catalog import get_factor_catalog\n"
        "def f():\n    return get_factor_catalog(include_new_data=True)\n"
    )
    assert _forbidden_usage(ast.parse(sample)) == []


def test_scan_catches_aliased_import() -> None:
    """The AST scan must catch an aliased import that a name-only scan would miss."""
    sample = "from src.alpha_research.factor_library.selection import get_factors as gf\n"
    hits = _forbidden_usage(ast.parse(sample))
    assert any("get_factors" in h for h in hits), hits
