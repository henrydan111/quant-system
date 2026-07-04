"""Phase 5-B monthly_calendar_bump driver — unit tests for the new PIT-relevant helpers
(M1 endpoint-readiness target_end, M2 fresh-window survivorship audit, M3 typed exceptions,
policy generation with a frozen spent_oos_end)."""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("monthly_calendar_bump", ROOT / "scripts" / "monthly_calendar_bump.py")
mcb = importlib.util.module_from_spec(_spec)
sys.modules["monthly_calendar_bump"] = mcb
_spec.loader.exec_module(mcb)

sys.path.insert(0, str(ROOT / "src"))
from src.research_orchestrator.calendar_policy import CalendarPolicy, resolve_spent_oos_boundary  # noqa: E402


# ── M1: determine_target_end ─────────────────────────────────────────────────
def _ready(ok: bool, **ev):
    return (ok, {"daily_rows": ev.get("daily_rows", 5000), **ev})


def test_target_end_rolls_back_when_today_not_past_update_hour():
    # A trading "today" before the latest vendor update hour is NOT complete -> roll back.
    days = mcb._open_trading_days()
    today = next((d for d in days if d >= "20260601"), days[-1])
    now = datetime(int(today[:4]), int(today[4:6]), int(today[6:]), 8, 0)  # 08:00, before hour 22
    te, ev = mcb.determine_target_end(now, probe_ready=lambda d: _ready(True))
    assert te is not None and te < today, f"today {today} must not be target_end pre-update-hour; got {te}"


def test_target_end_rejects_partial_daily_via_probe():
    days = mcb._open_trading_days()
    d0 = next((d for d in days if d >= "20260601"), days[-1])
    now = datetime(int(d0[:4]), int(d0[4:6]), int(d0[6:]), 23, 0)  # past all update hours
    # the readiness probe FAILS d0 (the latest), passes the prior -> roll back once
    full_days = [d for d in days if d <= d0]
    partial = full_days[-1]
    te, ev = mcb.determine_target_end(
        now, probe_ready=lambda d: _ready(d != partial, daily_rows=100 if d == partial else 5000))
    assert te is not None and te < partial, "a not-ready endpoint day must not authorize target_end"


def test_target_end_accepts_complete_day():
    days = mcb._open_trading_days()
    d0 = next((d for d in days if d >= "20260601"), days[-1])
    now = datetime(int(d0[:4]), int(d0[4:6]), int(d0[6:]), 23, 0)
    te, ev = mcb.determine_target_end(now, probe_ready=lambda d: _ready(True))
    assert te == d0


# ── policy generation: spent_oos_end FROZEN + append-only ────────────────────
def test_generate_thaw_policy_freezes_spent_oos_end_and_parses():
    policy_id, path = mcb.generate_thaw_policy("20260831", "parent_build_x", write=False)
    assert policy_id.startswith("frozen_20260831_thaw_step")
    # reconstruct the body the way generate_thaw_policy would and validate via CalendarPolicy
    body = {
        "policy_id": policy_id, "policy_schema_version": 1,
        "calendar_start_date": "2008-01-02", "calendar_end_date": "2026-08-31",
        "data_end_date": "2026-08-31", "frozen": True, "reason": "t", "established_at": "2026-08-31",
        "spent_oos_end": mcb.SPENT_OOS_END, "fresh_holdout_start": mcb.FRESH_HOLDOUT_START,
        "allowed_modes": ["formal"], "default_formal_behavior": "require_explicit_policy",
    }
    pol = CalendarPolicy.from_dict(body)
    # the fresh window grows (calendar 2026-08-31) but spent_oos_end stays 2026-02-27
    boundary = resolve_spent_oos_boundary(pol, "2026-08-31")
    assert boundary.spent_oos_end == "2026-02-27"
    assert boundary.fresh_holdout_start == "2026-02-28"


def test_parent_policy_fields_normalize_to_driver_constants():
    # phase_execute's D3-regression guard compares load_calendar_policy(parent).spent_oos_end
    # to the STRING constants. yaml.safe_load parses `spent_oos_end: 2026-02-27` to a
    # datetime.date, which would false-fail a string compare — the typed loader must normalize
    # it to the string form. Exercised against the live parent policy (the exact guard path).
    from src.research_orchestrator.calendar_policy import load_calendar_policy
    _, parent_policy = mcb.live_provider_ids()
    pol = load_calendar_policy(parent_policy)
    assert pol.spent_oos_end == mcb.SPENT_OOS_END, "D3 spent_oos_end must normalize to the constant"
    assert pol.fresh_holdout_start == mcb.FRESH_HOLDOUT_START


def test_generate_thaw_policy_is_append_only(tmp_path, monkeypatch):
    # Append-only: successive bumps never clobber a prior policy file — the step number
    # auto-increments, and a pre-existing exact policy id is refused.
    monkeypatch.setattr(mcb, "POLICY_DIR", tmp_path)
    pid1, path1 = mcb.generate_thaw_policy("20260930", "pb", write=True)
    pid2, path2 = mcb.generate_thaw_policy("20261031", "pb", write=True)
    assert pid1.endswith("thaw_step1") and pid2.endswith("thaw_step2")  # increments
    assert path1.exists() and path2.exists() and path1 != path2         # both survive
    # the first file's spent_oos_end stays frozen — the second write did not touch it
    import yaml as _yaml
    b1 = _yaml.safe_load(path1.read_text(encoding="utf-8"))
    assert b1["spent_oos_end"] == mcb.SPENT_OOS_END and b1["calendar_end_date"] == "2026-09-30"


# ── M3: typed exceptions registry ────────────────────────────────────────────
def test_exception_registry_rejects_wildcards(tmp_path):
    reg = mcb.ExceptionRegistry(tmp_path / "exc.json")
    with pytest.raises(ValueError, match="wildcard"):
        reg.add(exc_type="t", root_cause="r", dataset="d", symbols="*", date_range="2026",
                gross=1, net_after=0, reviewer="u", expiry="e", evidence="p", diff_hash="h")
    with pytest.raises(ValueError, match="wildcard"):
        reg.add(exc_type="t", root_cause="r", dataset="d", symbols=["000001_SZ"], date_range="all",
                gross=1, net_after=0, reviewer="u", expiry="e", evidence="p", diff_hash="h")


def test_exception_registry_flags_recurring_type(tmp_path):
    p = tmp_path / "exc.json"
    reg = mcb.ExceptionRegistry(p)
    reg.add(exc_type="report_rc_overlap", root_cause="r", dataset="report_rc", symbols=["a"],
            date_range="202602", gross=1, net_after=0, reviewer="u", expiry="e", evidence="p", diff_hash="h1")
    reg.commit()
    reg2 = mcb.ExceptionRegistry(p)  # next bump
    reg2.add(exc_type="report_rc_overlap", root_cause="r", dataset="report_rc", symbols=["b"],
             date_range="202603", gross=1, net_after=0, reviewer="u", expiry="e", evidence="p", diff_hash="h2")
    assert "report_rc_overlap" in reg2.recurring_types(), "a type recurring 2 bumps must be flagged"


# ── M2: fresh-window survivorship audit ──────────────────────────────────────
def _mk_fresh_window(tmp_path, ts_codes=("000001.SZ", "000002.SZ")):
    """Scaffold a fresh-window provider: trade_cal + daily raw files carrying ts_codes."""
    (tmp_path / "data" / "reference").mkdir(parents=True)
    days = pd.bdate_range("2026-03-02", "2026-03-06")
    pd.DataFrame({"exchange": "SSE", "cal_date": days.strftime("%Y%m%d"), "is_open": 1,
                  "pretrade_date": ""}).to_parquet(tmp_path / "data" / "reference" / "trade_cal.parquet")
    daily_dir = tmp_path / "data" / "market" / "daily" / "2026"
    daily_dir.mkdir(parents=True)
    for d in days.strftime("%Y%m%d"):
        pd.DataFrame({"ts_code": list(ts_codes)}).to_parquet(daily_dir / f"daily_{d}.parquet")


_TEST_CAL_ISO = ["2026-03-02", "2026-03-03", "2026-03-04", "2026-03-05", "2026-03-06"]


def _valid_close_bin(ncover: int) -> bytes:
    # Qlib .day.bin: float32[0]=start_index (0 here) then `ncover` values -> last covered pos = ncover-1.
    import struct
    return struct.pack("<f", 0.0) + b"\x00" * 4 * ncover


def _mk_features(prov, codes, *, close_cover=len(_TEST_CAL_ISO)):
    # provider calendar (ISO) for the bin-coverage check; created once
    (prov / "calendars").mkdir(parents=True, exist_ok=True)
    caltxt = prov / "calendars" / "day.txt"
    if not caltxt.exists():
        caltxt.write_text("\n".join(_TEST_CAL_ISO) + "\n", encoding="utf-8")
    for c in codes:
        cdir = prov / "features" / c
        cdir.mkdir(parents=True, exist_ok=True)
        for b in mcb.REQUIRED_PRICE_BINS:  # a code counts as present only with the full core bin set
            if b == "close.day.bin":
                (cdir / b).write_bytes(_valid_close_bin(close_cover))  # decoded for length
            else:
                (cdir / b).write_bytes(b"\x00" * 8)  # presence only


def test_fresh_window_survivorship_audit_flags_missing_universe_member(tmp_path, monkeypatch):
    # A ts_code with a raw daily price row but ABSENT from all_stocks on that day = a
    # survivorship hole -> the audit FAILS (no blanket exception).
    monkeypatch.setattr(mcb, "PROJECT_ROOT", tmp_path)
    _mk_fresh_window(tmp_path)
    prov = tmp_path / "prov"
    (prov / "instruments").mkdir(parents=True)
    _mk_features(prov, ["000001_SZ", "000002_SZ"])  # feature tree complete; only universe hole
    # all_stocks includes 000001 but OMITS 000002 (the survivorship hole)
    (prov / "instruments" / "all_stocks.txt").write_text(
        "000001_SZ  2020-01-01  2030-01-01\n", encoding="utf-8")
    res = mcb.fresh_window_survivorship_audit(prov, "2026-02-28", "2026-03-06")
    assert res["ok"] is False
    assert any(v["type"] == "raw_price_not_in_universe" for v in res["violations"])


def test_fresh_window_survivorship_audit_flags_missing_feature_tree(tmp_path, monkeypatch):
    # B4: a raw-priced code in all_stocks but ABSENT from the provider feature tree is a
    # feature-incomplete hole downstream research would silently operate on -> FAIL.
    monkeypatch.setattr(mcb, "PROJECT_ROOT", tmp_path)
    _mk_fresh_window(tmp_path)
    prov = tmp_path / "prov"
    (prov / "instruments").mkdir(parents=True)
    (prov / "instruments" / "all_stocks.txt").write_text(
        "000001_SZ  2020-01-01  2030-01-01\n000002_SZ  2020-01-01  2030-01-01\n", encoding="utf-8")
    _mk_features(prov, ["000001_SZ"])  # 000002 in universe but NOT in features/
    res = mcb.fresh_window_survivorship_audit(prov, "2026-02-28", "2026-03-06")
    assert res["ok"] is False
    assert any(v["type"] == "raw_price_not_in_feature_tree" for v in res["violations"])


def test_fresh_window_survivorship_audit_flags_incomplete_bins(tmp_path, monkeypatch):
    # M1: a code in all_stocks with a features/<code>/ dir but MISSING a core price bin is
    # feature-incomplete -> flagged (directory presence alone is not completeness).
    monkeypatch.setattr(mcb, "PROJECT_ROOT", tmp_path)
    _mk_fresh_window(tmp_path)
    prov = tmp_path / "prov"
    (prov / "instruments").mkdir(parents=True)
    (prov / "instruments" / "all_stocks.txt").write_text(
        "000001_SZ  2020-01-01  2030-01-01\n000002_SZ  2020-01-01  2030-01-01\n", encoding="utf-8")
    _mk_features(prov, ["000001_SZ"])                       # 000001 complete
    (prov / "features" / "000002_SZ").mkdir(parents=True)   # 000002 dir exists but only close.bin
    (prov / "features" / "000002_SZ" / "close.day.bin").write_bytes(b"\x00")
    res = mcb.fresh_window_survivorship_audit(prov, "2026-02-28", "2026-03-06")
    assert res["ok"] is False
    assert any(v["type"] == "raw_price_not_in_feature_tree" for v in res["violations"])


def test_fresh_window_survivorship_audit_flags_short_bins(tmp_path, monkeypatch):
    # M1: a code with ALL core bins present but whose close.day.bin is TRUNCATED before a fresh
    # trading day (covers fewer calendar positions) -> flagged raw_price_bins_short_through_day.
    monkeypatch.setattr(mcb, "PROJECT_ROOT", tmp_path)
    _mk_fresh_window(tmp_path)
    prov = tmp_path / "prov"
    (prov / "instruments").mkdir(parents=True)
    (prov / "instruments" / "all_stocks.txt").write_text(
        "000001_SZ  2020-01-01  2030-01-01\n000002_SZ  2020-01-01  2030-01-01\n", encoding="utf-8")
    _mk_features(prov, ["000001_SZ"])                    # full 5-position coverage
    _mk_features(prov, ["000002_SZ"], close_cover=2)     # close.day.bin covers only 2 positions
    res = mcb.fresh_window_survivorship_audit(prov, "2026-02-28", "2026-03-06")
    assert res["ok"] is False
    assert any(v["type"] == "raw_price_bins_short_through_day" for v in res["violations"])


def test_fresh_window_survivorship_audit_passes_when_universe_complete(tmp_path, monkeypatch):
    monkeypatch.setattr(mcb, "PROJECT_ROOT", tmp_path)
    _mk_fresh_window(tmp_path)
    prov = tmp_path / "prov"
    (prov / "instruments").mkdir(parents=True)
    (prov / "instruments" / "all_stocks.txt").write_text(
        "000001_SZ  2020-01-01  2030-01-01\n000002_SZ  2020-01-01  2030-01-01\n", encoding="utf-8")
    _mk_features(prov, ["000001_SZ", "000002_SZ"])  # universe + feature tree + bin coverage complete
    res = mcb.fresh_window_survivorship_audit(prov, "2026-02-28", "2026-03-06")
    assert res["ok"] is True, res["violations"]


# ── B1: endpoint completeness (row-count, split pre/post-catch-up) ───────────
def _write_endpoint(root, sub, ep, date, nrows):
    d = root / "data" / sub / date[:4]
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"ts_code": [f"{i:06d}.SZ" for i in range(nrows)]}).to_parquet(d / f"{ep}_{date}.parquet")


def test_endpoint_ready_coverage_not_existence(tmp_path, monkeypatch):
    monkeypatch.setattr(mcb, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(mcb, "MIN_PLAUSIBLE_DAILY_ROWS", 3)
    monkeypatch.setattr(mcb, "MIN_ENDPOINT_ROWS", 3)
    d = "20260703"
    _write_endpoint(tmp_path, "market/daily", "daily", d, 5)
    _write_endpoint(tmp_path, "market/moneyflow", "moneyflow", d, 5)
    _write_endpoint(tmp_path, "market/stk_limit", "stk_limit", d, 1)  # EXISTS but covers 1/5 of daily
    ok, ev = mcb.endpoint_ready(d)
    assert ok is False and "stk_limit" in ev["reason"], ev  # existence/low coverage is not enough
    _write_endpoint(tmp_path, "market/stk_limit", "stk_limit", d, 5)  # now full coverage
    ok, ev = mcb.endpoint_ready(d)
    assert ok is True, ev


def test_endpoint_ready_high_rows_low_coverage_fails(tmp_path, monkeypatch):
    # GPT B1: plenty of ROWS but LOW COVERAGE of the daily universe (a partial fetch returning
    # DIFFERENT names) must fail — a fixed row floor alone (3001 of ~5500) is not completeness.
    monkeypatch.setattr(mcb, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(mcb, "MIN_PLAUSIBLE_DAILY_ROWS", 3)
    monkeypatch.setattr(mcb, "MIN_ENDPOINT_ROWS", 3)
    d = "20260703"
    _write_endpoint(tmp_path, "market/daily", "daily", d, 10)        # universe 000000..000009
    _write_endpoint(tmp_path, "market/moneyflow", "moneyflow", d, 10)  # full coverage
    dd = tmp_path / "data" / "market" / "stk_limit" / "2026"
    dd.mkdir(parents=True)
    # 10 rows (>= floor) but DISJOINT names -> coverage 0.0
    pd.DataFrame({"ts_code": [f"9{i:05d}.SZ" for i in range(10)]}).to_parquet(dd / f"stk_limit_{d}.parquet")
    ok, ev = mcb.endpoint_ready(d)
    assert ok is False and "stk_limit" in ev["reason"] and "coverage" in ev["reason"], ev


def test_assert_endpoints_complete_flags_lagging_cyq_perf(tmp_path, monkeypatch):
    # cyq_perf lags (fetched post-catch-up); an empty/absent cyq_perf for target_end must fail
    # the POST-catch-up completeness gate even when the daily-fresh endpoints are complete.
    monkeypatch.setattr(mcb, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(mcb, "MIN_PLAUSIBLE_DAILY_ROWS", 3)
    monkeypatch.setattr(mcb, "MIN_ENDPOINT_ROWS", 3)
    d = "20260703"
    _write_endpoint(tmp_path, "market/daily", "daily", d, 5)
    _write_endpoint(tmp_path, "market/moneyflow", "moneyflow", d, 5)
    _write_endpoint(tmp_path, "market/stk_limit", "stk_limit", d, 5)
    ok, ev = mcb.assert_endpoints_complete(d)  # cyq_perf absent
    assert ok is False and "cyq_perf" in ev["reason"], ev
    _write_endpoint(tmp_path, "market/cyq_perf", "cyq_perf", d, 5)  # catch-up filled it
    ok, ev = mcb.assert_endpoints_complete(d)
    assert ok is True, ev
