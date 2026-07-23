# -*- coding: utf-8 -*-
"""The raw-store quiescence hook must be WIRED, not merely present.

`recovery_promotion.py` recorded, under a heading that says *"NOT YET TRUE, do not claim otherwise"*,
that `assert_no_active_recovery` had no production caller and that wiring it was a HARD PRE-PROMOTION
INTEGRATION GATE. The gate was not discharged before `market/daily` was promoted on 2026-07-22, and the
mistake that let that happen is worth naming: the sentinel was verified by calling the FUNCTION and
watching it refuse, which proves the function works and says nothing about whether anything calls it.
These tests check the wiring, not the function.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from data_infra.recovery_quiescence import (  # noqa: E402
    OVERRIDE_ENV, SENTINEL_NAME, RawStoreQuiescenceError, assert_no_active_recovery)

#: every entry point that reads or writes the raw store
RAW_CONSUMERS = [
    "src/data_infra/pipeline/update_daily_data.py",
    "src/data_infra/pipeline/build_qlib_backend.py",
    "src/data_infra/pipeline/verify_database.py",
    "src/data_infra/pipeline/init_market_data.py",
    "src/data_infra/pipeline/init_fundamentals_data.py",
    "src/data_infra/pipeline/init_factor_data.py",
    "src/data_infra/pipeline/refresh_indicator_history.py",
]


@pytest.mark.parametrize("rel", RAW_CONSUMERS)
def test_every_raw_consumer_calls_the_hook_in_main(rel):
    """DEFAULT-DENY by enumeration of the consumers, which is bounded and reviewable — unlike the
    unbounded 'any future reader' problem, the set of pipeline entry points is a real, small list."""
    import ast
    src = (ROOT / rel).read_text(encoding="utf-8")
    tree = ast.parse(src)
    main = next((n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
    assert main is not None, f"{rel} has no main() to guard"
    calls = {n.func.id for n in ast.walk(main)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "assert_no_active_recovery" in calls, (
        f"{rel}: main() does not call assert_no_active_recovery — a promotion could swap a raw tree "
        f"underneath it")


def test_the_hook_is_the_first_thing_main_does(request):
    """It must run BEFORE the work, not after a fetch has already started."""
    import ast
    for rel in RAW_CONSUMERS:
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        main = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "main")
        body = [s for s in main.body if not (isinstance(s, ast.Expr)
                                             and isinstance(s.value, ast.Constant))]  # skip docstring
        first_calls = []
        for stmt in body[:3]:
            for n in ast.walk(stmt):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                    first_calls.append(n.func.id)
        assert "assert_no_active_recovery" in first_calls, (
            f"{rel}: the quiescence check is not among the first statements of main()")


def test_the_sentinel_names_cannot_drift(tmp_path):
    """`src/` must not import from `scripts/`, so the name is stated in both places. If they diverge,
    the consumer guard silently watches a file the promoter never writes."""
    spec = importlib.util.spec_from_file_location("recovery_promotion",
                                                  ROOT / "scripts" / "recovery_promotion.py")
    rp = importlib.util.module_from_spec(spec)
    sys.modules["recovery_promotion"] = rp
    spec.loader.exec_module(rp)
    assert SENTINEL_NAME == rp.SENTINEL_NAME, (
        f"consumer guard watches {SENTINEL_NAME!r} but promotion writes {rp.SENTINEL_NAME!r}")


def test_the_hook_refuses_and_the_override_releases(tmp_path, monkeypatch):
    root = tmp_path / "data"
    root.mkdir()
    assert_no_active_recovery(root)                       # clean: passes
    (root / SENTINEL_NAME).write_text("run=x", encoding="utf-8")
    with pytest.raises(RawStoreQuiescenceError, match="RECOVERY_IN_PROGRESS"):
        assert_no_active_recovery(root)
    monkeypatch.setenv(OVERRIDE_ENV, "1")
    assert_no_active_recovery(root)                       # the operator's documented escape
    monkeypatch.setenv(OVERRIDE_ENV, "0")
    with pytest.raises(RawStoreQuiescenceError):
        assert_no_active_recovery(root)                   # only "1" releases it


def test_a_real_consumer_actually_refuses_end_to_end():
    """The property the earlier verification missed: not 'does the function refuse?' but 'does running
    the pipeline refuse?'. Runs verify_database in a fresh process against the REAL data root, which
    currently holds an armed sentinel from the market/daily promotion."""
    sentinel = ROOT / "data" / SENTINEL_NAME
    if not sentinel.exists():
        pytest.skip("no armed sentinel in the live data root (promotion QA already cleared it)")
    proc = subprocess.run([sys.executable, str(ROOT / "src/data_infra/pipeline/verify_database.py")],
                          capture_output=True, text=True, timeout=180, cwd=str(ROOT))
    assert proc.returncode != 0, "verify_database ran to completion while a promotion was in progress"
    assert "RECOVERY_IN_PROGRESS" in (proc.stderr + proc.stdout)
