"""B7/B4: every forward gate FAILS CLOSED — stale provider calendar, failed or
stale text pull, config-hash drift, and post-open decision times are all
refused before any LLM call."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

SCRIPT = (PROJECT_ROOT / "workspace" / "research" / "mvp_pool_book"
          / "run_forward_cycle.py")


@pytest.fixture(scope="module")
def fwd():
    spec = importlib.util.spec_from_file_location("run_forward_cycle_under_test3", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cal(days_open: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"cal_date": days_open, "is_open": [1] * len(days_open)})


def test_stale_provider_calendar_refused(fwd):
    # 6 open days between calendar end and fill date > max 5 -> refuse
    open_days = ["20260720", "20260721", "20260722", "20260723", "20260724",
                 "20260727", "20260728"]
    with pytest.raises(fwd.ForwardGateError, match="stale"):
        fwd.check_calendar_freshness("20260717", "20260729", _cal(open_days))


def test_fresh_provider_calendar_passes(fwd):
    open_days = ["20260720", "20260721", "20260722"]
    staleness = fwd.check_calendar_freshness("20260717", "20260723", _cal(open_days))
    assert staleness == 3


def test_failed_text_pull_refused(fwd):
    bad = {"ok": False, "failures": ["anns_d@20260802: boom"],
           "run_ts": "2026-08-03T20:35:00"}
    with pytest.raises(fwd.ForwardGateError, match="incomplete"):
        fwd.check_pull_manifest(bad, pd.Timestamp("2026-08-03 21:00:00"))


def test_stale_text_pull_refused(fwd):
    old = {"ok": True, "run_ts": "2026-07-30T20:35:00"}
    with pytest.raises(fwd.ForwardGateError, match="old"):
        fwd.check_pull_manifest(old, pd.Timestamp("2026-08-03 21:00:00"))


def test_future_dated_pull_manifest_refused(fwd):
    future = {"ok": True, "run_ts": "2026-08-05T00:00:00"}   # clock skew / tamper
    with pytest.raises(fwd.ForwardGateError):
        fwd.check_pull_manifest(future, pd.Timestamp("2026-08-03 21:00:00"))


def test_config_hash_drift_refused(fwd):
    with pytest.raises(fwd.ForwardGateError, match="frozen artifact"):
        fwd.check_config_hash("aaaa", "bbbb")
    fwd.check_config_hash("same", "same")   # no raise


def test_post_open_decision_refused(fwd):
    fill = pd.Timestamp("2026-08-04")
    with pytest.raises(fwd.ForwardGateError, match="backfill"):
        fwd.check_decision_before_fill_open(pd.Timestamp("2026-08-04 09:30:00"), fill)
    fwd.check_decision_before_fill_open(pd.Timestamp("2026-08-03 20:45:00"), fill)
