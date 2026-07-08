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


def test_worktree_whitelist_covers_generated_paths_only(fwd):
    # R3 Major-2: logs/outputs/.env are generated/local -> pass
    fwd.check_worktree_clean("?? logs/text_pull/pull_manifest_x.json\n"
                             "?? workspace/outputs/mvp_forward/attempts_ledger.jsonl\n"
                             " M .env\n")
    # but code/config/data/tests/prereg NEVER pass, even mixed with whitelisted
    for line in (" M config/ai_layer/rerank_v2.yaml",
                 " M src/data_infra/text_store.py",
                 "?? tests/harness/new_test.py",
                 " M workspace/research/mvp_pool_book/FORWARD_PREREG.md"):
        with pytest.raises(fwd.ForwardGateError, match="DIRTY"):
            fwd.check_worktree_clean("?? logs/x.log\n" + line + "\n")


# --------------------- R3 Blocker-3: text coverage history -------------------

import json  # noqa: E402


def _write_manifest(d: Path, name: str, *, start: str, end: str, ok=True,
                    statuses=None, failures=()):
    (d / f"pull_manifest_{name}.json").write_text(json.dumps({
        "run_ts": "2026-08-03T20:35:00+08:00",
        "window": {"start": start, "end": end},
        "source_status": statuses or {},
        "failures": list(failures),
        "ok": ok,
    }), encoding="utf-8")


SRC = ["anns_d", "research_report"]
DT = pd.Timestamp("2026-08-03 21:00:00", tz="Asia/Shanghai")


def test_full_coverage_passes_and_is_content_addressed(fwd, tmp_path):
    ok_st = {s: "ok_nonzero_rows" for s in SRC}
    _write_manifest(tmp_path, "20260720", start="2026-07-05",
                    end="2026-07-20", statuses=ok_st)
    _write_manifest(tmp_path, "20260803", start="2026-07-21",
                    end="2026-08-03", statuses=ok_st)
    rec = fwd.check_text_coverage_history(tmp_path, decision_time=DT,
                                          lookback_days=30, required_sources=SRC)
    assert rec["coverage_ok"] is True
    # R4 Blocker-3: every consulted manifest is sha256-pinned...
    assert set(rec["manifest_sha256_by_file"]) == {
        "pull_manifest_20260720.json", "pull_manifest_20260803.json"}
    import hashlib as _h
    p = tmp_path / "pull_manifest_20260803.json"
    assert rec["manifest_sha256_by_file"][p.name] == _h.sha256(p.read_bytes()).hexdigest()
    # ...and every covered (source, day) names its covering manifest
    assert rec["coverage_by_source_day"]["anns_d"]["2026-08-01"] == p.name
    assert len(rec["coverage_by_source_day"]["anns_d"]) == 30


def test_gap_inside_window_refuses(fwd, tmp_path):
    # daily task down 2026-07-22..2026-07-26 — latest pull is clean but window has a hole
    ok_st = {s: "ok_nonzero_rows" for s in SRC}
    _write_manifest(tmp_path, "20260721", start="2026-07-05",
                    end="2026-07-21", statuses=ok_st)
    _write_manifest(tmp_path, "20260803", start="2026-07-27",
                    end="2026-08-03", statuses=ok_st)
    with pytest.raises(fwd.ForwardGateError, match="coverage incomplete"):
        fwd.check_text_coverage_history(tmp_path, decision_time=DT,
                                        lookback_days=30, required_sources=SRC)


def test_per_source_gap_refuses_even_if_other_source_covered(fwd, tmp_path):
    _write_manifest(tmp_path, "20260803", start="2026-07-05",
                    end="2026-08-03",
                    statuses={"anns_d": "ok_nonzero_rows",
                              "research_report": "failed"})
    with pytest.raises(fwd.ForwardGateError, match="research_report"):
        fwd.check_text_coverage_history(tmp_path, decision_time=DT,
                                        lookback_days=30, required_sources=SRC)


def test_failed_manifest_recovered_by_later_clean_pull_passes(fwd, tmp_path):
    # D1 (GPT-accepted, conditional on hashing): a failed pull does not poison
    # the gate IF later overlapping clean pulls re-covered its dates — and the
    # failed manifest itself is content-hash pinned in the audit record
    ok_st = {s: "ok_nonzero_rows" for s in SRC}
    _write_manifest(tmp_path, "20260730", start="2026-07-05",
                    end="2026-07-30", statuses=ok_st)
    _write_manifest(tmp_path, "20260801", start="2026-07-29", end="2026-08-01",
                    ok=False, statuses={}, failures=["anns_d@20260801: boom"])
    _write_manifest(tmp_path, "20260803", start="2026-07-31", end="2026-08-03",
                    statuses=ok_st)
    rec = fwd.check_text_coverage_history(tmp_path, decision_time=DT,
                                          lookback_days=30, required_sources=SRC)
    assert rec["coverage_ok"] is True
    bad = rec["failed_manifests_recovered_later"]
    assert bad and bad[0]["sha256"]                     # audit trail is hashed
    assert "pull_manifest_20260801.json" in rec["manifest_sha256_by_file"]


# ------------------- R4 Blocker-3: bootstrap day-level form ------------------

def _write_bootstrap(d: Path, source: str, coverage_by_day: dict | None,
                     start: str, end: str):
    payload = {"run_ts": "2026-07-08T21:00:00+08:00", "bootstrap": True,
               "source": source, "window": {"start": start, "end": end},
               "failures": [], "ok": True}
    if coverage_by_day is not None:
        payload["coverage_by_day"] = coverage_by_day
    (d / f"pull_manifest_00000000_bootstrap_{source}.json").write_text(
        json.dumps(payload), encoding="utf-8")


def test_day_level_bootstrap_is_credited(fwd, tmp_path):
    ok_st = {s: "ok_nonzero_rows" for s in SRC}
    days = {str(d.date()): ("ok_zero_rows" if i % 3 == 0 else "ok_nonzero_rows")
            for i, d in enumerate(pd.date_range("2026-07-05", "2026-07-20"))}
    for s in SRC:
        _write_bootstrap(tmp_path, s, days, "2026-07-05", "2026-07-20")
    _write_manifest(tmp_path, "20260803", start="2026-07-21",
                    end="2026-08-03", statuses=ok_st)
    rec = fwd.check_text_coverage_history(tmp_path, decision_time=DT,
                                          lookback_days=30, required_sources=SRC)
    assert rec["coverage_ok"] is True
    assert rec["coverage_by_source_day"]["anns_d"]["2026-07-06"].startswith(
        "pull_manifest_00000000_bootstrap_anns_d")


def test_coarse_bootstrap_without_day_map_earns_no_credit(fwd, tmp_path):
    # retired min..max form: bootstrap flag but no coverage_by_day -> no credit
    ok_st = {s: "ok_nonzero_rows" for s in SRC}
    for s in SRC:
        _write_bootstrap(tmp_path, s, None, "2026-07-05", "2026-07-20")
    _write_manifest(tmp_path, "20260803", start="2026-07-21",
                    end="2026-08-03", statuses=ok_st)
    with pytest.raises(fwd.ForwardGateError, match="coverage incomplete"):
        fwd.check_text_coverage_history(tmp_path, decision_time=DT,
                                        lookback_days=30, required_sources=SRC)


def test_bootstrap_failed_day_earns_no_credit(fwd, tmp_path):
    ok_st = {s: "ok_nonzero_rows" for s in SRC}
    days = {str(d.date()): "ok_nonzero_rows"
            for d in pd.date_range("2026-07-05", "2026-07-20")}
    days["2026-07-10"] = "failed"
    for s in SRC:
        _write_bootstrap(tmp_path, s, days, "2026-07-05", "2026-07-20")
    _write_manifest(tmp_path, "20260803", start="2026-07-21",
                    end="2026-08-03", statuses=ok_st)
    with pytest.raises(fwd.ForwardGateError, match="2026-07-10"):
        fwd.check_text_coverage_history(tmp_path, decision_time=DT,
                                        lookback_days=30, required_sources=SRC)


# --------------- R4 Major-1: prereg pinned hash consistency ------------------

def test_prereg_pinned_hash_matches_frozen_config(fwd):
    import hashlib as _h
    cfg = (PROJECT_ROOT / "config" / "ai_layer" / "rerank_v2.yaml").read_text(encoding="utf-8")
    pe = (PROJECT_ROOT / "src" / "ai_layer" / "prompts" / "extract_v2.txt").read_text(encoding="utf-8")
    ps = (PROJECT_ROOT / "src" / "ai_layer" / "prompts" / "score_v2.txt").read_text(encoding="utf-8")
    live = _h.sha256((cfg + pe + ps).encode("utf-8")).hexdigest()[:16]
    assert fwd._load_pinned_hash() == live, (
        "FORWARD_PREREG config_hash_v2 pin does not match the frozen config — "
        "either a frozen artifact drifted or the prereg was not re-pinned")
    # the pin must also not be contradicted elsewhere in the prereg (R4 Major-1)
    prereg = (PROJECT_ROOT / "workspace" / "research" / "mvp_pool_book"
              / "FORWARD_PREREG.md").read_text(encoding="utf-8")
    import re
    hashes = set(re.findall(r"config_hash_v2[:\s`]+([0-9a-f]{16})", prereg))
    assert hashes == {live}, f"contradictory config_hash_v2 pins in prereg: {hashes}"
