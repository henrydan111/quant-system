"""PR 7 of 2026-05-26 freeze plan — durable import-boundary guard for
dormant subsystems.

The pre-flight audit on 2026-05-26 confirmed that ``src/portfolio_risk/``
(MultiFactorRiskModel, PortfolioOptimizer, MarketImpactModel) is dormant —
no production code imports it, only its own tests and docs. Its current
state includes a hardcoded ``predict_portfolio_risk()`` return of 0.05 and
a no-op ``MultiFactorRiskModel.fit()``. That dormant state is acceptable
because nothing depends on it; if anything starts depending on it, the
result becomes silently wrong.

These tests convert the audit result into an active guardrail: they fail
the moment any formal-path module imports any of the dormant symbols,
forcing the developer to either (a) promote portfolio_risk maturity to
P0 first, or (b) explain in the test why the dormant symbol is now safe
to import.

If you legitimately want to promote portfolio_risk, follow the freeze plan
P2 workstream: implement covariance shrinkage / PSD repair, replace the
hardcoded predict, update tests, then remove the corresponding line from
``DORMANT_SYMBOLS`` here.

Also enforces that workspace scripts archived to
``workspace/scripts/archive/`` are not referenced from ``src/``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ─────────────────────────────────────────────────────────────────────────
# Dormant portfolio_risk symbols (2026-05-26 audit baseline)
# ─────────────────────────────────────────────────────────────────────────

DORMANT_SYMBOLS: tuple[str, ...] = (
    "MultiFactorRiskModel",
    "predict_portfolio_risk",
    "MarketImpactModel",
)

# Formal-path paths that MUST NOT import dormant symbols.
FORMAL_PATHS: tuple[Path, ...] = (
    PROJECT_ROOT / "src" / "research_orchestrator" / "release_gate.py",
    PROJECT_ROOT / "src" / "research_orchestrator" / "validation_steps.py",
    PROJECT_ROOT / "src" / "backtest_engine" / "event_driven",
    PROJECT_ROOT / "src" / "alpha_research" / "factor_library",
    PROJECT_ROOT / "src" / "result_analysis",
)


def _iter_python_files(root: Path) -> list[Path]:
    if root.is_file() and root.suffix == ".py":
        return [root]
    if root.is_dir():
        return sorted(root.rglob("*.py"))
    return []


@pytest.mark.parametrize("formal_path", FORMAL_PATHS, ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
def test_formal_path_does_not_import_dormant_portfolio_risk(formal_path: Path) -> None:
    """Until portfolio_risk leaves P2, formal-path modules cannot import it."""
    files = _iter_python_files(formal_path)
    if not files:
        pytest.skip(f"{formal_path} contains no Python files yet")
    failures: list[str] = []
    for file in files:
        text = file.read_text(encoding="utf-8", errors="replace")
        # Look for top-level imports of the symbols. We tolerate the symbol
        # appearing inside a STRING LITERAL (docstring / error message) by
        # also checking for `import ` or `from src.portfolio_risk` proximity.
        if "src.portfolio_risk" in text or "from src.portfolio_risk" in text or "from portfolio_risk" in text:
            failures.append(
                f"{file.relative_to(PROJECT_ROOT)}: imports src.portfolio_risk. "
                "portfolio_risk is dormant per the 2026-05-26 audit; promote "
                "its maturity (P2 → P0) before importing it from a formal path."
            )
        for symbol in DORMANT_SYMBOLS:
            # We use a very simple substring check; a more elaborate AST walk
            # could parse imports, but for the audit guard we want a low
            # false-negative rate. Mention in a docstring is fine because
            # the import would be required to actually call the symbol.
            #
            # The check fires if the symbol appears in a usage pattern (e.g.
            # `MultiFactorRiskModel(`, `predict_portfolio_risk(`).
            usage_patterns = (f"{symbol}(", f".{symbol}(")
            if any(pattern in text for pattern in usage_patterns):
                failures.append(
                    f"{file.relative_to(PROJECT_ROOT)}: uses dormant symbol "
                    f"{symbol}. The 2026-05-26 audit confirmed this symbol "
                    "is not implemented for formal use (hardcoded return / "
                    "no-op fit). Promote portfolio_risk maturity first."
                )
    if failures:
        msg = "\n".join(failures)
        pytest.fail(f"Dormant portfolio_risk boundary violated:\n{msg}")


def test_archived_workspace_scripts_not_referenced_from_src() -> None:
    """Class-D archived scripts (workspace/scripts/archive/) must not be
    referenced by import or by hardcoded path from src/.

    This catches the failure mode where a contributor un-archives a
    superseded mimic script by re-importing it instead of recovering and
    re-classifying it through the PR 2 audit workflow.
    """
    archive_dir = PROJECT_ROOT / "workspace" / "scripts" / "archive" / "p1_jq_g5a2_investigation_2026_05"
    if not archive_dir.exists():
        pytest.skip("Archive directory does not exist on this host")

    archived_stems = sorted(p.stem for p in archive_dir.glob("*.py"))
    if not archived_stems:
        pytest.skip("Archive directory is empty")

    src_root = PROJECT_ROOT / "src"
    failures: list[str] = []
    for py_file in src_root.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8", errors="replace")
        for stem in archived_stems:
            for needle in (f"import {stem}", f"from {stem}", f"workspace/scripts/archive/p1_jq_g5a2_investigation_2026_05/{stem}"):
                if needle in text:
                    failures.append(
                        f"{py_file.relative_to(PROJECT_ROOT)}: references "
                        f"archived script {stem}. Archived scripts are "
                        "historical investigation only — pull the logic into "
                        "a properly classified workspace script or into src/."
                    )
    if failures:
        msg = "\n".join(failures)
        pytest.fail(f"Archived workspace script referenced from src/:\n{msg}")


def test_archive_directory_exists_and_has_d_class_scripts() -> None:
    """Sanity: PR 7 must have moved the 14 D-class mimic scripts."""
    archive_dir = PROJECT_ROOT / "workspace" / "scripts" / "archive" / "p1_jq_g5a2_investigation_2026_05"
    if not archive_dir.exists():
        pytest.skip("Archive directory does not exist on this host (fresh clone)")
    archived_count = len(list(archive_dir.glob("p1_jq_g5a2_mimic_v*.py")))
    assert archived_count >= 14, (
        f"Expected at least 14 archived D-class mimic scripts, found {archived_count}. "
        "Re-run scripts/apply_workspace_script_headers.py --apply."
    )


def test_workspace_scripts_outside_archive_carry_script_status_header() -> None:
    """Every workspace/scripts/*.py that the PR 2 audit classified must
    carry the PR 7 SCRIPT_STATUS header block (or be in archive/).
    """
    scripts_dir = PROJECT_ROOT / "workspace" / "scripts"
    if not scripts_dir.exists():
        pytest.skip("workspace/scripts/ does not exist on this host")
    audit_csv = scripts_dir / "_audit" / "direct_engine_classification.csv"
    if not audit_csv.exists():
        pytest.skip("PR 2 audit CSV not present (run scripts/audit_direct_engine_use.py)")

    import csv
    classified_files: dict[str, str] = {}
    with open(audit_csv, "r", encoding="utf-8", newline="") as h:
        for row in csv.DictReader(h):
            classified_files[row["file"]] = row["class"]

    missing: list[str] = []
    for filename, cls in classified_files.items():
        if cls == "D":
            continue  # archived
        target = scripts_dir / filename
        if not target.exists():
            continue
        head = "".join(target.read_text(encoding="utf-8").splitlines(keepends=True)[:30])
        if "# script_status:" not in head:
            missing.append(f"{filename} ({cls}): SCRIPT_STATUS header missing")

    if missing:
        msg = "\n".join(missing)
        pytest.fail(
            f"PR 7 SCRIPT_STATUS header missing on {len(missing)} workspace scripts:\n"
            f"{msg}\nRun: venv/Scripts/python.exe scripts/apply_workspace_script_headers.py --apply"
        )
