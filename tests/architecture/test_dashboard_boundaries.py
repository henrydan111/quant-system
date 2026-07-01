"""Architecture guard: the dashboard is a READ-ONLY projection.

CLAUDE.md §6.2 contract: src/dashboard only *reads* the other modules' outputs /
registries / governance and projects them into derived artifacts (root
index.html, workspace/outputs/dashboard/*). Two structural invariants keep
"factor layer == projection of the registry" true:

1. No formal module imports the dashboard (it must never sit on a research/data
   path — a dashboard bug must not be able to affect research outputs).
2. Dashboard code never writes under data/ (registries, ledgers, qlib backend)
   — its write surface is derived artifacts only.

These were previously contract-only; this test makes them executable.
"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src"
FORMAL_MODULES = [
    "data_infra", "alpha_research", "backtest_engine",
    "portfolio_risk", "result_analysis", "research_orchestrator",
]

IMPORT_RE = re.compile(
    r"^\s*(?:from\s+(?:src\.)?dashboard|import\s+(?:src\.)?dashboard)\b", re.M
)


def _py_files(root: Path):
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


class TestNoFormalPathImportsDashboard:
    def test_formal_modules_do_not_import_dashboard(self):
        offenders = []
        for mod in FORMAL_MODULES:
            for p in _py_files(SRC / mod):
                if IMPORT_RE.search(p.read_text(encoding="utf-8", errors="replace")):
                    offenders.append(str(p.relative_to(PROJECT_ROOT)))
        assert not offenders, (
            "dashboard is a read-only auxiliary and must never be imported into a "
            f"formal module (CLAUDE.md §6.2). Offenders: {offenders}"
        )


class TestDashboardNeverWritesData:
    # write APIs that could mutate persistent state, paired with a data/ target
    WRITE_CALL_RE = re.compile(
        r"\.(?:to_parquet|to_csv|to_pickle|write_text|write_bytes)\s*\(|open\s*\([^)]*['\"]w",
    )
    DATA_PATH_RE = re.compile(r"['\"](?:data[\\/]|\.\./data)|PROJECT_ROOT\s*/\s*['\"]data['\"]")

    def test_no_write_statement_targets_data_dir(self):
        offenders = []
        for p in _py_files(SRC / "dashboard"):
            text = p.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                if self.WRITE_CALL_RE.search(line) and self.DATA_PATH_RE.search(line):
                    offenders.append(f"{p.relative_to(PROJECT_ROOT)}:{i}")
        assert not offenders, (
            "dashboard write surface must be derived artifacts only (index.html, "
            f"workspace/outputs/dashboard) — never data/. Offenders: {offenders}"
        )

    def test_registry_paths_only_read(self):
        """Any mention of factor_registry parquets in dashboard code must be a read."""
        offenders = []
        for p in _py_files(SRC / "dashboard"):
            for i, line in enumerate(
                    p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if "factor_registry" in line and self.WRITE_CALL_RE.search(line):
                    offenders.append(f"{p.relative_to(PROJECT_ROOT)}:{i}")
        assert not offenders, f"registry must be read-only from dashboard: {offenders}"
