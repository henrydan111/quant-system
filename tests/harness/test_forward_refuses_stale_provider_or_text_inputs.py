"""B7/B4 + R2 Blockers 4/5/6: every forward gate FAILS CLOSED — stale or
OVER-FRESH provider calendar (as-of upper bound), failed/stale/per-source-bad
text pull, config drift, post-open decisions under Asia/Shanghai semantics,
and dirty git worktrees are all refused before any LLM spend."""
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


# ---------------------------------------------------- staleness (lower bound)

def test_stale_provider_calendar_refused(fwd):
    open_days = ["20260720", "20260721", "20260722", "20260723", "20260724",
                 "20260727", "20260728"]
    with pytest.raises(fwd.ForwardGateError, match="stale"):
        fwd.check_calendar_freshness("20260717", "20260729", _cal(open_days))


def test_fresh_provider_calendar_passes(fwd):
    open_days = ["20260720", "20260721", "20260722"]
    assert fwd.check_calendar_freshness("20260717", "20260723", _cal(open_days)) == 3


# ------------------------------------------- as-of upper bound (R2 Blocker-4)

def test_provider_beyond_asof_bound_refused(fwd):
    # provider thawed THROUGH the fill date -> same-day rows would leak
    with pytest.raises(fwd.ForwardGateError, match="exceeds the latest allowed as-of"):
        fwd.check_provider_asof_bound("2026-08-04", "2026-08-03")


def test_provider_at_asof_bound_passes(fwd):
    fwd.check_provider_asof_bound("2026-08-03", "2026-08-03")
    fwd.check_provider_asof_bound("2026-07-31", "2026-08-03")


def test_previous_open_day_is_strictly_before_fill(fwd):
    cal = _cal(["20260731", "20260803", "20260804"])
    assert fwd.previous_open_day("2026-08-04", cal) == pd.Timestamp("2026-08-03")
    assert fwd.previous_open_day("2026-08-03", cal) == pd.Timestamp("2026-07-31")


# ------------------------------------------------------- text pull manifests

def _dt(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz="Asia/Shanghai")


def test_failed_text_pull_refused(fwd):
    bad = {"ok": False, "failures": ["anns_d@20260802: boom"],
           "run_ts": "2026-08-03T20:35:00+08:00"}
    with pytest.raises(fwd.ForwardGateError, match="incomplete"):
        fwd.check_pull_manifest(bad, _dt("2026-08-03 21:00:00"))


def test_stale_text_pull_refused(fwd):
    old = {"ok": True, "run_ts": "2026-07-30T20:35:00+08:00"}
    with pytest.raises(fwd.ForwardGateError, match="old"):
        fwd.check_pull_manifest(old, _dt("2026-08-03 21:00:00"))


def test_future_dated_pull_manifest_refused(fwd):
    future = {"ok": True, "run_ts": "2026-08-05T00:00:00+08:00"}
    with pytest.raises(fwd.ForwardGateError):
        fwd.check_pull_manifest(future, _dt("2026-08-03 21:00:00"))


def test_required_source_without_ok_status_refused(fwd):
    # R2 Blocker-6: ok=True overall but one required source missing/failed
    m = {"ok": True, "run_ts": "2026-08-03T20:35:00+08:00",
         "source_status": {"anns_d": "ok_nonzero_rows",
                           "research_report": "ok_zero_rows"}}
    with pytest.raises(fwd.ForwardGateError, match="without ok pull status"):
        fwd.check_pull_manifest(m, _dt("2026-08-03 21:00:00"),
                                ["anns_d", "research_report", "irm_qa_sh"])
    # all present + ok passes
    m["source_status"]["irm_qa_sh"] = "ok_nonzero_rows"
    fwd.check_pull_manifest(m, _dt("2026-08-03 21:00:00"),
                            ["anns_d", "research_report", "irm_qa_sh"])


# ----------------------------------------------------- config / time / git

def test_config_hash_drift_refused(fwd):
    with pytest.raises(fwd.ForwardGateError, match="frozen artifact"):
        fwd.check_config_hash("aaaa", "bbbb")
    fwd.check_config_hash("same", "same")


def test_post_open_decision_refused_in_cn_time(fwd):
    fill = pd.Timestamp("2026-08-04")
    with pytest.raises(fwd.ForwardGateError, match="backfill"):
        fwd.check_decision_before_fill_open(_dt("2026-08-04 09:30:00"), fill)
    fwd.check_decision_before_fill_open(_dt("2026-08-03 20:45:00"), fill)


def test_utc_clock_cannot_fake_pre_open(fwd):
    # R2 Blocker-5: 02:00 UTC on fill day = 10:00 CN — market already open
    utc_after_open = pd.Timestamp("2026-08-04 02:00:00", tz="UTC")
    with pytest.raises(fwd.ForwardGateError, match="backfill"):
        fwd.check_decision_before_fill_open(utc_after_open, pd.Timestamp("2026-08-04"))
    # 00:30 UTC = 08:30 CN — genuinely pre-open, passes
    fwd.check_decision_before_fill_open(
        pd.Timestamp("2026-08-04 00:30:00", tz="UTC"), pd.Timestamp("2026-08-04"))


def test_dirty_worktree_refused(fwd):
    with pytest.raises(fwd.ForwardGateError, match="DIRTY"):
        fwd.check_worktree_clean(" M src/ai_layer/scorecard.py\n?? junk.py\n")
    fwd.check_worktree_clean("")
    fwd.check_worktree_clean("\n")
