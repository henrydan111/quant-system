"""Keep the §0 Canonical Function Map in ``src/system.md`` honest.

The reuse map only prevents wheel-reinvention if its entries stay valid. A
map that points at a renamed or moved function is *worse* than no map — it
actively misleads. These tests fail loudly when:

  1. any committed repo path cited in the §0 map no longer exists
     (catches a module move/rename), or
  2. any canonical symbol the map advertises is no longer defined at its
     module (catches a function/class rename), or
  3. the map text drops a symbol that is still registered here
     (catches the doc and the registry drifting apart).

Wired into ``scripts/run_daily_qa.py`` as the ``canonical_function_map``
check. It is pure-Python (ast + regex), needs no Qlib/Tushare/data, and is
fast.

When you legitimately rename or move a canonical entry, update BOTH the §0
map in ``src/system.md`` AND the matching row in ``CANONICAL_SYMBOLS`` below
in the same change. ``data/`` paths are intentionally NOT existence-checked
(that tree is gitignored and absent on CI / fresh clones); this guard is for
code drift, not data presence.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYSTEM_MD = PROJECT_ROOT / "src" / "system.md"

# (bare symbol, module path relative to repo root). Each verified present
# 2026-06-04. ``symbol`` is the def/class/method/constant name; for a method
# it is the unqualified name (ast.walk descends into class bodies).
CANONICAL_SYMBOLS: tuple[tuple[str, str], ...] = (
    ("load_pit_signal_panel", "src/data_infra/pit_research_loader.py"),
    ("load_pit_asof_panel", "src/data_infra/pit_research_loader.py"),
    ("qlib_windowed_features", "src/research_orchestrator/qlib_windowed_features.py"),
    ("resolve_field", "src/data_infra/field_registry.py"),
    ("validate_expression", "src/data_infra/field_registry.py"),
    ("extract_qlib_fields", "src/data_infra/field_registry.py"),
    ("get_factor_catalog", "src/alpha_research/factor_library/catalog.py"),
    ("get_composite_defs", "src/alpha_research/factor_library/catalog.py"),
    ("get_industry_relative_defs", "src/alpha_research/factor_library/catalog.py"),
    ("compute_factors", "src/alpha_research/factor_library/operators.py"),
    ("add_composites", "src/alpha_research/factor_library/operators.py"),
    ("add_industry_relative_composites", "src/alpha_research/factor_library/operators.py"),
    ("get_factors", "src/alpha_research/factor_library/selection.py"),
    ("get_factor_selection", "src/alpha_research/factor_library/selection.py"),
    ("run_batch_screening", "src/alpha_research/factor_eval/batch_screening.py"),
    ("VectorizedBacktester", "src/backtest_engine/vectorized/__init__.py"),
    ("EventDrivenBacktester", "src/backtest_engine/event_driven/__init__.py"),
    ("compute_buy_cost_breakdown", "src/backtest_engine/event_driven/exchange.py"),
    ("compute_sell_cost_breakdown", "src/backtest_engine/event_driven/exchange.py"),
    ("realistic_china", "src/backtest_engine/event_driven/exchange.py"),
    ("JOINQUANT_DEFAULT_SLIPPAGE", "src/backtest_engine/event_driven/exchange.py"),
    ("CONSERVATIVE_SLIPPAGE_10BPS", "src/backtest_engine/event_driven/exchange.py"),
    ("BacktestReport", "src/result_analysis/report.py"),
    ("ExperimentTracker", "src/alpha_research/mlflow_tracker.py"),
    ("produce_promotion_evidence", "src/research_orchestrator/promotion_evidence.py"),
    ("PortfolioOptimizer", "src/portfolio_risk/optimizer.py"),
)

# Committed top-level dirs whose paths the §0 map may cite and that MUST
# exist. ``data/`` is excluded on purpose (gitignored, host-local).
_CHECKED_PREFIXES = ("src/", "tests/", "scripts/", "config/", "schemas/", "workspace/")

_SYMBOL_IDS = [s for s, _ in CANONICAL_SYMBOLS]


def _defined_names(py_path: Path) -> set[str]:
    """All def/class/method/module-constant names bound in a .py file."""
    tree = ast.parse(py_path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):  # descends into class bodies -> methods count
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _section0_text() -> str:
    text = SYSTEM_MD.read_text(encoding="utf-8")
    # §0 runs from its "## 0." header to the next level-2 "## " header.
    match = re.search(r"^## 0\. .*?(?=^## )", text, re.M | re.S)
    assert match, "§0 Canonical Function Map header not found in src/system.md"
    return match.group(0)


def test_section0_present_and_substantial() -> None:
    section = _section0_text()
    assert "Canonical Function Map" in section
    assert section.count("Call this") >= 3, "§0 map tables look truncated"


@pytest.mark.parametrize("symbol,rel", CANONICAL_SYMBOLS, ids=_SYMBOL_IDS)
def test_canonical_symbol_is_defined(symbol: str, rel: str) -> None:
    path = PROJECT_ROOT / rel
    assert path.exists(), f"{rel} (cited for `{symbol}`) does not exist"
    names = _defined_names(path)
    assert symbol in names, (
        f"`{symbol}` is no longer defined in {rel}. The §0 Canonical Function "
        f"Map in src/system.md is now stale — update the map AND CANONICAL_SYMBOLS."
    )


@pytest.mark.parametrize("symbol,rel", CANONICAL_SYMBOLS, ids=_SYMBOL_IDS)
def test_canonical_symbol_is_documented(symbol: str, rel: str) -> None:
    section = _section0_text()
    assert symbol in section, (
        f"`{symbol}` is registered in CANONICAL_SYMBOLS but no longer appears "
        f"in the §0 map — re-add it to src/system.md or drop the registry row."
    )


def test_all_committed_paths_cited_in_map_exist() -> None:
    section = _section0_text()
    cited = set(re.findall(r"`([^`]+)`", section))
    repo_paths = {
        tok
        for tok in cited
        if tok.startswith(_CHECKED_PREFIXES) and "*" not in tok
    }
    # Sanity: the map should cite a meaningful number of real module paths.
    assert len(repo_paths) >= 10, f"too few path tokens parsed from §0: {repo_paths}"
    missing = sorted(p for p in repo_paths if not (PROJECT_ROOT / p).exists())
    assert not missing, f"§0 Canonical Function Map cites non-existent paths: {missing}"
