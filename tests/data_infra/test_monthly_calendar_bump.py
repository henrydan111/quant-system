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


def _write_valid_cal(path, cal_dates):
    # a VALID SSE calendar with a proper pretrade_date chain (first row blank; each open day -> the
    # prior open day) so it passes _validate_trade_cal, which the bump's _open_trading_days now enforces.
    cal_dates = [str(d) for d in cal_dates]
    pretrade = [""] + cal_dates[:-1]
    pd.DataFrame({"exchange": "SSE", "cal_date": cal_dates, "is_open": 1,
                  "pretrade_date": pretrade}).to_parquet(path)


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
    _write_valid_cal(tmp_path / "data" / "reference" / "trade_cal.parquet", days.strftime("%Y%m%d"))
    daily_dir = tmp_path / "data" / "market" / "daily" / "2026"
    daily_dir.mkdir(parents=True)
    for d in days.strftime("%Y%m%d"):
        pd.DataFrame({"ts_code": list(ts_codes)}).to_parquet(daily_dir / f"daily_{d}.parquet")


_TEST_CAL_ISO = ["2026-03-02", "2026-03-03", "2026-03-04", "2026-03-05", "2026-03-06"]


def _valid_close_bin(ncover: int) -> bytes:
    # Qlib .day.bin: float32[0]=start_index (0 here) then `ncover` values -> last covered pos = ncover-1.
    import struct
    return struct.pack("<f", 0.0) + b"\x00" * 4 * ncover


def _mk_features(prov, codes, *, close_cover=len(_TEST_CAL_ISO), other_cover=len(_TEST_CAL_ISO)):
    # provider calendar (ISO) for the bin-coverage check; created once
    (prov / "calendars").mkdir(parents=True, exist_ok=True)
    caltxt = prov / "calendars" / "day.txt"
    if not caltxt.exists():
        caltxt.write_text("\n".join(_TEST_CAL_ISO) + "\n", encoding="utf-8")
    for c in codes:
        cdir = prov / "features" / c
        cdir.mkdir(parents=True, exist_ok=True)
        for b in mcb.REQUIRED_PRICE_BINS:  # ALL core bins must exist AND span the raw-priced day
            (cdir / b).write_bytes(_valid_close_bin(close_cover if b == "close.day.bin" else other_cover))


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


def test_fresh_window_survivorship_audit_flags_day_not_in_provider_calendar(tmp_path, monkeypatch):
    # M1: a fresh raw-priced day ABSENT from the staged provider calendar -> the provider cannot
    # support the claimed target_end -> fail closed (not silently skipped).
    monkeypatch.setattr(mcb, "PROJECT_ROOT", tmp_path)
    _mk_fresh_window(tmp_path)
    prov = tmp_path / "prov"
    (prov / "instruments").mkdir(parents=True)
    (prov / "instruments" / "all_stocks.txt").write_text(
        "000001_SZ  2020-01-01  2030-01-01\n000002_SZ  2020-01-01  2030-01-01\n", encoding="utf-8")
    _mk_features(prov, ["000001_SZ", "000002_SZ"])
    # provider calendar MISSING the last fresh day (2026-03-06)
    (prov / "calendars" / "day.txt").write_text("\n".join(_TEST_CAL_ISO[:-1]) + "\n", encoding="utf-8")
    res = mcb.fresh_window_survivorship_audit(prov, "2026-02-28", "2026-03-06")
    assert res["ok"] is False
    assert any(v["type"] == "raw_price_day_not_in_provider_calendar" for v in res["violations"])


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


# ── B1: endpoint completeness (coverage vs a proven-complete daily) ──────────
def _write_endpoint(root, sub, ep, date, nrows, codes=None):
    d = root / "data" / sub / date[:4]
    d.mkdir(parents=True, exist_ok=True)
    ts = list(codes) if codes is not None else [f"{i:06d}.SZ" for i in range(nrows)]
    pd.DataFrame({"ts_code": ts, "trade_date": [date] * len(ts)}).to_parquet(d / f"{ep}_{date}.parquet")


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
    # 10 rows (>= floor) but DISJOINT names -> coverage 0.0
    _write_endpoint(tmp_path, "market/stk_limit", "stk_limit", d, 0,
                    codes=[f"9{i:05d}.SZ" for i in range(10)])
    ok, ev = mcb.endpoint_ready(d)
    assert ok is False and "stk_limit" in ev["reason"] and "coverage" in ev["reason"], ev


def test_daily_universe_partial_above_floor_caught(tmp_path, monkeypatch):
    # GPT B1 (the stated #1 residual): a daily file ABOVE the absolute floor but well below the
    # recent baseline (a partial fetch) must fail — the coverage denominator must be COMPLETE.
    monkeypatch.setattr(mcb, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(mcb, "MIN_PLAUSIBLE_DAILY_ROWS", 5)
    monkeypatch.setattr(mcb, "DAILY_BASELINE_WINDOW", 5)
    days = ["20260622", "20260623", "20260624", "20260625", "20260626", "20260629"]
    (tmp_path / "data" / "reference").mkdir(parents=True)
    _write_valid_cal(tmp_path / "data" / "reference" / "trade_cal.parquet", days)
    for d in days[:-1]:                                   # prior sessions: full universe of 20
        _write_endpoint(tmp_path, "market/daily", "daily", d, 20)
    _write_endpoint(tmp_path, "market/daily", "daily", days[-1], 12)  # target: partial (>= floor 5)
    codes, ok, ev = mcb._daily_universe(days[-1])
    assert ok is False and "PARTIAL" in ev.get("reason", ""), ev
    # and a full target passes
    _write_endpoint(tmp_path, "market/daily", "daily", days[-1], 20)
    codes, ok, ev = mcb._daily_universe(days[-1])
    assert ok is True, ev


def _mk_continuity_scaffold(tmp_path, *, sb_rows, susp_rows, prev_codes, prev="20260702", today="20260703"):
    (tmp_path / "data" / "reference").mkdir(parents=True, exist_ok=True)
    _write_valid_cal(tmp_path / "data" / "reference" / "trade_cal.parquet", [prev, today])
    pd.DataFrame(sb_rows).to_parquet(tmp_path / "data" / "reference" / "stock_basic.parquet")
    sd = tmp_path / "data" / "market" / "suspend_d" / today[:4]
    sd.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(susp_rows if susp_rows else {"ts_code": [], "trade_date": [], "suspend_type": []}
                 ).to_parquet(sd / f"suspend_d_{today}.parquet")
    _write_endpoint(tmp_path, "market/daily", "daily", prev, 0, codes=prev_codes)


def _sb_of(tmp_path):
    return pd.read_parquet(tmp_path / "data" / "reference" / "stock_basic.parquet")


def test_daily_continuity_flags_unexplained_vanished_name(tmp_path, monkeypatch):
    # GPT B1: a name TRADING yesterday that vanishes today WITHOUT a delist/suspend reason is a
    # survivorship hole the count baseline can't see -> fail closed. Prior set is passed EXPLICITLY
    # (the range gate supplies a VERIFIED prior — never an unverified read).
    monkeypatch.setattr(mcb, "PROJECT_ROOT", tmp_path)
    _mk_continuity_scaffold(
        tmp_path,
        sb_rows={"ts_code": ["A.SZ", "B.SZ", "C.SZ", "D.SZ"], "list_date": ["20200101"] * 4,
                 "delist_date": [None] * 4},
        susp_rows={"ts_code": ["C.SZ"], "trade_date": ["20260703"], "suspend_type": ["S"],
                   "suspend_timing": [""]},  # full-day suspension (empty timing)
        prev_codes=["A.SZ", "B.SZ", "C.SZ", "D.SZ"])
    sb, prior = _sb_of(tmp_path), {"A.SZ", "B.SZ", "C.SZ", "D.SZ"}
    # today: A,B present; C legitimately full-day suspended (absent OK); D VANISHED without reason
    ok, ev = mcb._daily_set_continuity_from_prior("20260703", "20260702", prior, {"A.SZ", "B.SZ"}, sb)
    assert ok is False and "D.SZ" in str(ev.get("reason", "")), ev
    ok, ev = mcb._daily_set_continuity_from_prior("20260703", "20260702", prior, {"A.SZ", "B.SZ", "D.SZ"}, sb)
    assert ok is True, ev


def test_daily_continuity_intraday_suspension_not_excused(tmp_path, monkeypatch):
    # GPT B1-b: an INTRADAY halt (suspend_timing set) still trades -> it must NOT excuse an absent
    # daily row. Only full-day (empty suspend_timing) suspensions excuse absence.
    monkeypatch.setattr(mcb, "PROJECT_ROOT", tmp_path)
    _mk_continuity_scaffold(
        tmp_path,
        sb_rows={"ts_code": ["A.SZ", "B.SZ", "C.SZ"], "list_date": ["20200101"] * 3,
                 "delist_date": [None] * 3},
        # C has an INTRADAY halt (timing 09:30-10:00) -> still trades -> absence is NOT excused
        susp_rows={"ts_code": ["C.SZ"], "trade_date": ["20260703"], "suspend_type": ["S"],
                   "suspend_timing": ["09:30-10:00"]},
        prev_codes=["A.SZ", "B.SZ", "C.SZ"])
    sb, prior = _sb_of(tmp_path), {"A.SZ", "B.SZ", "C.SZ"}
    ok, ev = mcb._daily_set_continuity_from_prior("20260703", "20260702", prior, {"A.SZ", "B.SZ"}, sb)
    assert ok is False and "C.SZ" in str(ev.get("reason", "")), ev  # intraday-halted C should trade
    # a FULL-DAY suspension (empty timing) DOES excuse it
    sd = tmp_path / "data" / "market" / "suspend_d" / "2026" / "suspend_d_20260703.parquet"
    pd.DataFrame({"ts_code": ["C.SZ"], "trade_date": ["20260703"], "suspend_type": ["S"],
                  "suspend_timing": [""]}).to_parquet(sd)
    ok, ev = mcb._daily_set_continuity_from_prior("20260703", "20260702", prior, {"A.SZ", "B.SZ"}, sb)
    assert ok is True, ev


def test_daily_continuity_legacy_suspend_without_timing_fails_if_s_rows(tmp_path, monkeypatch):
    # GPT B1-b: a legacy suspend_d file with S rows but NO suspend_timing column is AMBIGUOUS
    # (full-day vs intraday) -> the formal gate must FAIL CLOSED, not excuse the S names as full-day.
    monkeypatch.setattr(mcb, "PROJECT_ROOT", tmp_path)
    _mk_continuity_scaffold(
        tmp_path,
        sb_rows={"ts_code": ["A.SZ", "B.SZ", "C.SZ"], "list_date": ["20200101"] * 3,
                 "delist_date": [None] * 3},
        # C has an S row but the file has NO suspend_timing column (legacy)
        susp_rows={"ts_code": ["C.SZ"], "trade_date": ["20260703"], "suspend_type": ["S"]},
        prev_codes=["A.SZ", "B.SZ", "C.SZ"])
    sb, prior = _sb_of(tmp_path), {"A.SZ", "B.SZ", "C.SZ"}
    ok, ev = mcb._daily_set_continuity_from_prior("20260703", "20260702", prior, {"A.SZ", "B.SZ"}, sb)
    assert ok is False and "suspend_timing" in ev.get("reason", ""), ev


def test_daily_continuity_allows_delisted_and_flags_missing_ipo(tmp_path, monkeypatch):
    monkeypatch.setattr(mcb, "PROJECT_ROOT", tmp_path)
    _mk_continuity_scaffold(
        tmp_path,
        sb_rows={"ts_code": ["A.SZ", "B.SZ", "C.SZ", "E.SZ"],
                 "list_date": ["20200101", "20200101", "20200101", "20260703"],
                 "delist_date": [None, None, "20260703", None]},
        susp_rows=None, prev_codes=["A.SZ", "B.SZ", "C.SZ"])
    sb, prior = _sb_of(tmp_path), {"A.SZ", "B.SZ", "C.SZ"}
    # C delisted (absent OK), but the IPO E is missing from today -> fail
    ok, ev = mcb._daily_set_continuity_from_prior("20260703", "20260702", prior, {"A.SZ", "B.SZ"}, sb)
    assert ok is False and "E.SZ" in str(ev.get("reason", "")), ev
    ok, ev = mcb._daily_set_continuity_from_prior("20260703", "20260702", prior, {"A.SZ", "B.SZ", "E.SZ"}, sb)
    assert ok is True, ev


def test_daily_continuity_fails_closed_without_suspend_d(tmp_path, monkeypatch):
    monkeypatch.setattr(mcb, "PROJECT_ROOT", tmp_path)
    _mk_continuity_scaffold(
        tmp_path, sb_rows={"ts_code": ["A.SZ", "B.SZ", "C.SZ"], "list_date": ["20200101"] * 3,
                           "delist_date": [None] * 3},
        susp_rows=None, prev_codes=["A.SZ", "B.SZ", "C.SZ"])
    (tmp_path / "data" / "market" / "suspend_d" / "2026" / "suspend_d_20260703.parquet").unlink()
    sb, prior = _sb_of(tmp_path), {"A.SZ", "B.SZ", "C.SZ"}
    ok, ev = mcb._daily_set_continuity_from_prior("20260703", "20260702", prior, {"A.SZ", "B.SZ", "C.SZ"}, sb)
    assert ok is False and "suspend_d" in ev.get("reason", ""), ev


def test_daily_universe_flags_stale_trade_date(tmp_path, monkeypatch):
    # GPT B1 second form: a file named for `date` but carrying a DIFFERENT trade_date (stale/
    # mispartitioned) must not pass — date_ok proves the partition.
    monkeypatch.setattr(mcb, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(mcb, "MIN_PLAUSIBLE_DAILY_ROWS", 5)
    d = "20260703"
    dd = tmp_path / "data" / "market" / "daily" / "2026"
    dd.mkdir(parents=True)
    # file is daily_20260703.parquet but every row's trade_date is the PRIOR day
    pd.DataFrame({"ts_code": [f"{i:06d}.SZ" for i in range(20)],
                  "trade_date": ["20260702"] * 20}).to_parquet(dd / f"daily_{d}.parquet")
    codes, ok, ev = mcb._daily_universe(d)
    assert ok is False and "trade_date" in ev.get("reason", ""), ev


def test_cyq_perf_coverage_gate_flags_lagging(tmp_path, monkeypatch):
    # cyq_perf lags (fetched post-catch-up); an empty/absent cyq_perf must fail its coverage gate.
    monkeypatch.setattr(mcb, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(mcb, "MIN_ENDPOINT_ROWS", 3)
    d = "20260703"
    _write_endpoint(tmp_path, "market/daily", "daily", d, 5)
    daily_codes = {f"{i:06d}.SZ" for i in range(5)}
    ev = {}
    assert mcb._coverage_gate(d, mcb.READINESS_POSTCATCHUP, ev, daily_codes) is False
    assert "cyq_perf" in ev["reason"], ev
    _write_endpoint(tmp_path, "market/cyq_perf", "cyq_perf", d, 5)  # catch-up filled it
    ev = {}
    assert mcb._coverage_gate(d, mcb.READINESS_POSTCATCHUP, ev, daily_codes) is True, ev


def test_assert_endpoints_complete_range_chains_from_anchor(tmp_path, monkeypatch):
    # GPT B1-a: the formal gate chains continuity from the VERIFIED parent anchor through every new
    # day. A NEW day that drops a name without a delist/suspend reason fails — even if the drop is
    # small enough that the count baseline (relaxed here) would miss it.
    monkeypatch.setattr(mcb, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(mcb, "MIN_PLAUSIBLE_DAILY_ROWS", 3)
    monkeypatch.setattr(mcb, "MIN_ENDPOINT_ROWS", 3)
    monkeypatch.setattr(mcb, "DAILY_BASELINE_FLOOR", 0.5)  # let the continuity be the failing check
    (tmp_path / "data" / "reference").mkdir(parents=True)
    _write_valid_cal(tmp_path / "data" / "reference" / "trade_cal.parquet", ["20260701", "20260702"])
    pd.DataFrame({"ts_code": ["A.SZ", "B.SZ", "C.SZ", "D.SZ"], "list_date": ["20200101"] * 4,
                  "delist_date": [None] * 4}).to_parquet(tmp_path / "data" / "reference" / "stock_basic.parquet")
    sd = tmp_path / "data" / "market" / "suspend_d" / "2026"
    sd.mkdir(parents=True)
    pd.DataFrame({"ts_code": [], "trade_date": [], "suspend_type": []}).to_parquet(sd / "suspend_d_20260702.parquet")
    all4 = ["A.SZ", "B.SZ", "C.SZ", "D.SZ"]
    _write_endpoint(tmp_path, "market/daily", "daily", "20260701", 0, codes=all4)  # verified anchor
    for ep, sub in [("moneyflow", "market/moneyflow"), ("stk_limit", "market/stk_limit"),
                    ("cyq_perf", "market/cyq_perf")]:
        _write_endpoint(tmp_path, sub, ep, "20260702", 0, codes=all4)
    # new day drops D without a reason -> chained proof fails
    _write_endpoint(tmp_path, "market/daily", "daily", "20260702", 0, codes=["A.SZ", "B.SZ", "C.SZ"])
    ok, ev = mcb.assert_endpoints_complete("20260701", "20260702")
    assert ok is False and "D.SZ" in str(ev.get("reason", "")), ev
    # restore D -> passes end to end
    _write_endpoint(tmp_path, "market/daily", "daily", "20260702", 0, codes=all4)
    ok, ev = mcb.assert_endpoints_complete("20260701", "20260702")
    assert ok is True, ev


def test_full_raw_manifest_covers_readset_and_detects_mutation(tmp_path):
    # GPT REWORK-5 Blocker 3: the manifest must cover the builder's FULL read set (every DATASET_SPECS
    # dataset + reference), not a 6-dataset subset — mutating an `income` file (which the old manifest
    # ignored) must change the root AND fail verify-before-publish. Full-CONTENT SHA-256, so a same-size
    # byte-swap is caught.
    data_root = tmp_path / "data"
    income = data_root / "fundamentals" / "income" / "income_2020.parquet"
    income.parent.mkdir(parents=True)
    income.write_bytes(b"AAAA")
    (data_root / "reference").mkdir(parents=True)
    (data_root / "reference" / "trade_cal.parquet").write_bytes(b"CAL0")

    m1 = mcb._full_raw_manifest(data_root)
    assert m1["algo"] == "sha256" and m1["file_count"] >= 2
    assert any(r["path"].startswith("fundamentals/income/") for r in m1["files"]), "income must be covered"
    ok, _ = mcb._verify_raw_manifest(m1, data_root)
    assert ok  # unchanged -> verifies

    income.write_bytes(b"BBBB")  # same size, different content
    m2 = mcb._full_raw_manifest(data_root)
    assert m1["root"] != m2["root"], "a mutated income file MUST change the manifest root"
    bad, why = mcb._verify_raw_manifest(m1, data_root)
    assert not bad and "income" in why  # verify-before-publish catches the out-of-band mutation


# ── Phase 5-B B3.3-5: the atomic publish transaction ─────────────────────────
# phase_publish is now verify+swap+rebind+metadata in ONE lock scope. These tests drive
# the REAL transaction end-to-end against a synthetic staged/live pair (real renames,
# real manifest emission, real approval rewrites) — only the QA subprocess is stubbed.
import json as _json  # noqa: E402
import types as _types  # noqa: E402

import yaml as _yamlmod  # noqa: E402


class _PubArgs:
    i_reviewed_the_dryrun = True


def _publish_env(tmp_path, monkeypatch, *, qa_rc: int = 0):
    root = tmp_path
    data = root / "data"
    out = root / "out"
    out.mkdir(parents=True)
    (root / "policies").mkdir()
    (root / "approvals").mkdir()
    monkeypatch.setattr(mcb, "PROJECT_ROOT", root)
    monkeypatch.setattr(mcb, "OUT_DIR", out)
    monkeypatch.setattr(mcb, "POLICY_DIR", root / "policies")
    monkeypatch.setattr(mcb, "APPROVALS_DIR", root / "approvals")
    monkeypatch.setattr(mcb, "DRYRUN_REPORT_PATH", out / "monthly_bump_dryrun_report.json")
    monkeypatch.setattr(mcb, "FRESH_AUDIT_PATH", out / "fresh_window_survivorship_audit.json")
    monkeypatch.setattr(mcb, "RAW_MANIFEST_PATH", out / "raw_input_manifest.json")
    monkeypatch.setattr(mcb, "PUBLISH_RECORD_PATH", out / "publish_record.json")
    monkeypatch.setattr(mcb, "TRANSACTION_JOURNAL_PATH", out / "publish_transaction_journal.json")
    monkeypatch.setattr(mcb, "_run_post_publish_qa", lambda: qa_rc)

    parent_pb, parent_cp = "parent_build_1", "frozen_20260701_thaw_step1"
    new_pb, new_cp = "thaw_20990101_120000", "frozen_20990101_thaw_step2"

    # live provider (the parent)
    qlib = data / "qlib_data"
    (qlib / "metadata").mkdir(parents=True)
    (qlib / "calendars").mkdir()
    (qlib / "calendars" / "day.txt").write_text("2008-01-02\n2026-07-01\n", encoding="utf-8")
    (qlib / "LIVE_MARKER.txt").write_text("parent", encoding="utf-8")
    (qlib / "metadata" / "provider_build.json").write_text(_json.dumps(
        {"provider_build_id": parent_pb, "calendar_policy_id": parent_cp}), encoding="utf-8")

    # staged provider (the child) at the canonical build path — incl. a feature BIN whose
    # bytes the full-content attestation must protect (GPT re-review Blocker 4)
    staged = data / "qlib_builds" / new_pb / "provider"
    (staged / "calendars").mkdir(parents=True)
    (staged / "calendars" / "day.txt").write_text("2008-01-02\n2099-01-01\n", encoding="utf-8")
    (staged / "instruments").mkdir()
    (staged / "instruments" / "all_stocks.txt").write_text(
        "000001_SZ\t2008-01-02\t2099-01-01\n", encoding="utf-8")
    (staged / "features" / "000001_sz").mkdir(parents=True)
    (staged / "features" / "000001_sz" / "close.day.bin").write_bytes(b"\x01\x02\x03\x04")
    (staged / "STAGED_MARKER.txt").write_text("child", encoding="utf-8")
    (data / "qlib_builds" / new_pb / "manifest.json").write_text("{}", encoding="utf-8")

    # the minted policy the report points at
    (root / "policies" / f"{new_cp}.yaml").write_text(_yamlmod.safe_dump({
        "policy_id": new_cp, "policy_schema_version": 1,
        "calendar_start_date": "2008-01-02", "calendar_end_date": "2099-01-01",
        "data_end_date": "2099-01-01", "frozen": True, "reason": "test",
        "established_at": "2099-01-01", "spent_oos_end": mcb.SPENT_OOS_END,
        "fresh_holdout_start": mcb.FRESH_HOLDOUT_START,
        "require_raw_input_attestation": True,
        "allowed_modes": ["formal"], "default_formal_behavior": "require_explicit_policy",
    }, sort_keys=False), encoding="utf-8")

    # bound approvals in BOTH quoting styles + one exempt admin record
    a1 = root / "approvals" / "a1.yaml"
    a1.write_text(f'approval_id: a1\ndataset_id: d1\nto_status: approved\ndate: "2026-07-01"\n'
                  f'provider_build_id: "{parent_pb}"\ncalendar_policy_id: {parent_cp}\n',
                  encoding="utf-8")
    a2 = root / "approvals" / "a2.yaml"
    a2.write_text(f"approval_id: a2\ndataset_id: d2\nto_status: approved\ndate: '2026-07-01'\n"
                  f"provider_build_id: {parent_pb}\ncalendar_policy_id: '{parent_cp}'\n",
                  encoding="utf-8")
    (root / "approvals" / "exempt.yaml").write_text(
        "approval_id: x\nbinding_exempt: true\nbinding_exempt_reason: admin-only record\n",
        encoding="utf-8")

    # raw cut + full-readset manifest sidecar over it
    raw = data / "reference" / "trade_cal.parquet"
    raw.parent.mkdir(parents=True)
    raw.write_bytes(b"CAL0")
    manifest = mcb._full_raw_manifest(data)
    (out / "raw_input_manifest.json").write_text(_json.dumps(manifest), encoding="utf-8")

    # audit artifacts + the full transaction attestation set, pinned into the dry-run report
    fp = out / "frozen_prefix_audit.json"
    fp.write_text(_json.dumps({"staged": str(staged), "ok": True}), encoding="utf-8")
    fw = out / "fresh_window_survivorship_audit.json"
    fw.write_text(_json.dumps({"ok": True, "violations": []}), encoding="utf-8")
    monkeypatch.setattr(mcb, "_git_state", lambda: ("testsha0123", "clean"))
    att = mcb._staged_content_attestation(staged)
    (out / f"staged_content_manifest_{new_pb}.json").write_text(
        _json.dumps(att), encoding="utf-8")
    appr_att = mcb._approvals_attestation()
    policy_file = root / "policies" / f"{new_cp}.yaml"
    report = {
        "target_end": "20990101", "new_policy_id": new_cp, "staged_build_id": new_pb,
        "staged_provider_dir": str(staged), "parent_build_id": parent_pb,
        "parent_policy_id": parent_cp, "raw_input_manifest_root": manifest["root"],
        "frozen_prefix_audit_sha256": mcb._sha256_file(fp),
        "fresh_window_audit_sha256": mcb._sha256_file(fw),
        "staged_content_root": att["root"],
        "staged_content_file_count": att["file_count"],
        "staged_content_total_bytes": att["total_bytes"],
        "staged_content_manifest_artifact": f"staged_content_manifest_{new_pb}.json",
        "approvals_attestation_root": appr_att["root"],
        "approvals_file_count": appr_att["file_count"],
        "approvals_bound_count": appr_att["bound_count"],
        "new_policy_sha256": mcb._sha256_file(policy_file),
        "source_git_commit": "testsha0123",
        "git_dirty_digest": "clean",
    }
    (out / "monthly_bump_dryrun_report.json").write_text(_json.dumps(report), encoding="utf-8")

    def _builder(build_id: str):
        from data_infra.pit_backend import StagedQlibBackendBuilder
        return StagedQlibBackendBuilder(data_root=str(data), qlib_dir=str(qlib), build_id=build_id)

    monkeypatch.setattr(mcb, "_make_publish_builder", _builder)
    return _types.SimpleNamespace(
        root=root, data=data, qlib=qlib, staged=staged, out=out, raw=raw,
        staged_bin=staged / "features" / "000001_sz" / "close.day.bin",
        policy_file=policy_file,
        parent_pb=parent_pb, parent_cp=parent_cp, new_pb=new_pb, new_cp=new_cp,
        manifest=manifest, a1=a1, a2=a2,
        a1_bytes=a1.read_bytes(), a2_bytes=a2.read_bytes())


def _publish_state_of(qlib) -> str | None:
    p = qlib / "metadata" / "publish_state.json"
    return _json.loads(p.read_text(encoding="utf-8"))["state"] if p.exists() else None


def _assert_untouched(env):
    """The refusal contract: NOTHING durable mutated — parent still live, staged still
    staged, approvals byte-identical."""
    assert (env.qlib / "LIVE_MARKER.txt").exists(), "parent must still be live"
    assert (env.staged / "STAGED_MARKER.txt").exists(), "staged tree must stay staged"
    assert env.a1.read_bytes() == env.a1_bytes and env.a2.read_bytes() == env.a2_bytes
    assert not (env.data / f"qlib_data.bak_{env.new_pb}").exists(), "no backup may appear"


def test_publish_transaction_happy_path(tmp_path, monkeypatch):
    env = _publish_env(tmp_path, monkeypatch)
    assert mcb.phase_publish(_PubArgs()) == 0
    # swap: child live, parent retained as .bak
    assert (env.qlib / "STAGED_MARKER.txt").exists()
    bak = env.data / f"qlib_data.bak_{env.new_pb}"
    assert (bak / "LIVE_MARKER.txt").exists()
    # metadata: the live manifest binds build -> policy -> raw cut -> parent
    m = _json.loads((env.qlib / "metadata" / "provider_build.json").read_text(encoding="utf-8"))
    assert m["provider_build_id"] == env.new_pb
    assert m["calendar_policy_id"] == env.new_cp
    assert m["raw_input_manifest_root"] == env.manifest["root"]
    assert m["parent_provider_build_id"] == env.parent_pb
    assert m["source_git_commit"] == "testsha0123"  # the EXECUTE-time commit, not publish-time
    assert _publish_state_of(env.qlib) == "ready"   # QA passed -> quarantine lifted
    # rebind: both quoting styles preserved, values swapped; exempt untouched
    t1 = env.a1.read_text(encoding="utf-8")
    assert f'provider_build_id: "{env.new_pb}"' in t1 and f"calendar_policy_id: {env.new_cp}" in t1
    t2 = env.a2.read_text(encoding="utf-8")
    assert f"provider_build_id: {env.new_pb}" in t2 and f"calendar_policy_id: '{env.new_cp}'" in t2
    from data_infra.approval_evidence import evaluate_approval_evidence_bindings
    drifts = evaluate_approval_evidence_bindings(
        approvals_dir=env.root / "approvals",
        manifest_path=env.qlib / "metadata" / "provider_build.json")
    assert drifts and not any(d.drift for d in drifts)
    # records
    assert (env.out / "publish_record.json").exists()
    assert (env.out / "publish_transaction_journal.json").exists()
    assert list((env.root / "approvals").glob(f"*_rebind_to_{env.new_pb}.md"))


def test_publish_refuses_parent_drift(tmp_path, monkeypatch):
    env = _publish_env(tmp_path, monkeypatch)
    (env.qlib / "metadata" / "provider_build.json").write_text(_json.dumps(
        {"provider_build_id": "someone_else", "calendar_policy_id": env.parent_cp}), encoding="utf-8")
    assert mcb.phase_publish(_PubArgs()) == 2
    assert (env.qlib / "LIVE_MARKER.txt").exists() and (env.staged / "STAGED_MARKER.txt").exists()
    assert env.a1.read_bytes() == env.a1_bytes


def test_publish_refuses_raw_input_mutation(tmp_path, monkeypatch):
    env = _publish_env(tmp_path, monkeypatch)
    env.raw.write_bytes(b"CALX")  # same size, different content — content hash must catch it
    assert mcb.phase_publish(_PubArgs()) == 2
    _assert_untouched(env)


def test_publish_refuses_audit_artifact_drift(tmp_path, monkeypatch):
    env = _publish_env(tmp_path, monkeypatch)
    fp = env.out / "frozen_prefix_audit.json"
    fp.write_text(_json.dumps({"staged": str(env.staged), "ok": True, "edited": 1}), encoding="utf-8")
    assert mcb.phase_publish(_PubArgs()) == 2
    _assert_untouched(env)


def test_publish_refuses_staged_tree_drift(tmp_path, monkeypatch):
    env = _publish_env(tmp_path, monkeypatch)
    cal = env.staged / "calendars" / "day.txt"
    cal.write_text(cal.read_text(encoding="utf-8") + "2099-01-02\n", encoding="utf-8")
    assert mcb.phase_publish(_PubArgs()) == 2
    _assert_untouched(env)


def test_publish_refuses_foreign_approval_binding(tmp_path, monkeypatch):
    env = _publish_env(tmp_path, monkeypatch)
    env.a2.write_text("approval_id: a2\ndataset_id: d2\nto_status: approved\ndate: '2026-07-01'\n"
                      "provider_build_id: other_build\ncalendar_policy_id: other_policy\n",
                      encoding="utf-8")
    assert mcb.phase_publish(_PubArgs()) == 2
    assert (env.qlib / "LIVE_MARKER.txt").exists() and (env.staged / "STAGED_MARKER.txt").exists()


def test_publish_refuses_pre_phase5b_report(tmp_path, monkeypatch):
    # A report produced by the pre-transaction driver (no attestation fields) must refuse
    # — publish verifies exactly what execute attested, or nothing.
    env = _publish_env(tmp_path, monkeypatch)
    rep = _json.loads((env.out / "monthly_bump_dryrun_report.json").read_text(encoding="utf-8"))
    del rep["staged_content_root"]
    (env.out / "monthly_bump_dryrun_report.json").write_text(_json.dumps(rep), encoding="utf-8")
    assert mcb.phase_publish(_PubArgs()) == 2
    _assert_untouched(env)


def test_publish_rolls_back_on_postswap_failure(tmp_path, monkeypatch):
    # A failure AFTER the swap (here: the rebind-record write) must restore the approval
    # bytes AND roll the swap back — parent live again, staged tree back for a clean retry.
    env = _publish_env(tmp_path, monkeypatch)

    def _boom(**kwargs):
        raise RuntimeError("record write failed")

    monkeypatch.setattr(mcb, "_write_rebind_record", _boom)
    assert mcb.phase_publish(_PubArgs()) == 4
    assert (env.qlib / "LIVE_MARKER.txt").exists(), "parent live provider must be restored"
    assert (env.staged / "STAGED_MARKER.txt").exists(), "staged tree must be back at provider_dir"
    assert mcb.live_provider_ids() == (env.parent_pb, env.parent_cp)
    assert env.a1.read_bytes() == env.a1_bytes and env.a2.read_bytes() == env.a2_bytes
    assert not (env.data / f"qlib_data.bak_{env.new_pb}").exists(), "rollback must consume the backup"
    # this transaction's artifacts must not survive a rollback (GPT re-review Blocker 2b):
    assert not (env.out / "publish_record.json").exists(), "publish record must be removed"
    assert not list((env.root / "approvals").glob("*_rebind_to_*.md")), "no rebind md may remain"
    # ... and the returned staged tree is stripped back to its ATTESTED content, so a
    # clean retry passes the content re-attestation:
    assert not (env.staged / "metadata" / "provider_build.json").exists()
    assert not (env.staged / "metadata" / "publish_state.json").exists()
    rep = _json.loads((env.out / "monthly_bump_dryrun_report.json").read_text(encoding="utf-8"))
    assert mcb._staged_content_attestation(env.staged)["root"] == rep["staged_content_root"]
    steps = _json.loads((env.out / "publish_transaction_journal.json").read_text(encoding="utf-8"))["steps"]
    assert any(s["step"] == "bind" and s["status"] == "failed_rolled_back" for s in steps)


def test_publish_rolls_back_when_manifest_emission_fails(tmp_path, monkeypatch):
    # The builder's emit path is deliberately non-raising; the transaction must catch the
    # absent/short manifest via _verify_live_manifest and roll the whole swap back.
    env = _publish_env(tmp_path, monkeypatch)
    import data_infra.provider_manifest as pm

    def _boom(**kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(pm, "emit_manifest_at_publish", _boom)
    assert mcb.phase_publish(_PubArgs()) == 4
    assert (env.qlib / "LIVE_MARKER.txt").exists()
    assert (env.staged / "STAGED_MARKER.txt").exists()
    assert mcb.live_provider_ids() == (env.parent_pb, env.parent_cp)
    assert env.a1.read_bytes() == env.a1_bytes


def test_publish_qa_failure_returns_6_and_quarantines(tmp_path, monkeypatch):
    # QA runs OUTSIDE the transaction: a QA failure alarms (exit 6) and does not undo a
    # consistent swap+rebind+metadata — but the publish-state marker QUARANTINES gated
    # reads mechanically (GPT re-review Blocker 6), and --finalize-qa lifts it on a pass.
    env = _publish_env(tmp_path, monkeypatch, qa_rc=1)
    assert mcb.phase_publish(_PubArgs()) == 6
    assert (env.qlib / "STAGED_MARKER.txt").exists(), "the published provider stays live"
    m = _json.loads((env.qlib / "metadata" / "provider_build.json").read_text(encoding="utf-8"))
    assert m["provider_build_id"] == env.new_pb
    assert f'provider_build_id: "{env.new_pb}"' in env.a1.read_text(encoding="utf-8")
    assert _publish_state_of(env.qlib) == "qa_failed", "quarantine marker must persist"
    # the marker is load-bearing at the gate:
    from src.research_orchestrator.release_gate import evaluate_provider_publish_state
    gate = evaluate_provider_publish_state(qlib_dir=env.qlib, policy=object(), manifest=None)
    assert not gate.eligible and any("qa_failed" in r for r in gate.reasons)
    # QA resolved -> --finalize-qa flips to ready
    monkeypatch.setattr(mcb, "_run_post_publish_qa", lambda: 0)
    assert mcb.phase_finalize_qa(_PubArgs()) == 0
    assert _publish_state_of(env.qlib) == "ready"
    assert evaluate_provider_publish_state(qlib_dir=env.qlib, policy=object(), manifest=None).eligible


def test_generate_thaw_policy_requires_raw_attestation(tmp_path, monkeypatch):
    # Every bump-minted policy makes the raw-input attestation load-bearing for formal runs.
    monkeypatch.setattr(mcb, "POLICY_DIR", tmp_path)
    _pid, path = mcb.generate_thaw_policy("20990131", "pb", write=True)
    body = _yamlmod.safe_load(path.read_text(encoding="utf-8"))
    assert body["require_raw_input_attestation"] is True


# ── GPT re-review probes (Blockers 1-4, 7 + Majors) ──────────────────────────
def test_publish_survives_journal_write_failure_after_swap(tmp_path, monkeypatch):
    # GPT Blocker 1 probe: the first post-swap journal write previously sat OUTSIDE the
    # rollback domain — a journal fault left the child live with stale approvals and no
    # rollback. Now the journal is a non-raising breadcrumb: the transaction completes.
    env = _publish_env(tmp_path, monkeypatch)
    monkeypatch.setattr(mcb, "TRANSACTION_JOURNAL_PATH", env.out)  # a DIRECTORY -> every write fails
    assert mcb.phase_publish(_PubArgs()) == 0
    assert (env.qlib / "STAGED_MARKER.txt").exists() and _publish_state_of(env.qlib) == "ready"
    assert f'provider_build_id: "{env.new_pb}"' in env.a1.read_text(encoding="utf-8")


def _selective_write_fault(monkeypatch, should_fail):
    """Patch mcb._atomic_write_bytes with a predicate-driven fault injector; all other
    writes pass through to the real implementation."""
    real = mcb._atomic_write_bytes

    def fake(path, data):
        if should_fail(Path(path), data):
            raise OSError("injected write fault")
        real(path, data)

    monkeypatch.setattr(mcb, "_atomic_write_bytes", fake)


def test_publish_rolls_back_when_rebind_write_fails_midway(tmp_path, monkeypatch):
    # GPT Blocker 2 probe: fail the SECOND approval write mid-rebind. The caller holds
    # every original (pure planner), restores + VERIFIES, rolls the swap back -> exit 4
    # with byte-identical approvals and the parent live again.
    env = _publish_env(tmp_path, monkeypatch)
    seen: list[Path] = []

    def fail_second_approval(path, _data):
        if path.parent == env.root / "approvals" and path.suffix == ".yaml":
            seen.append(path)
            return len(seen) == 2
        return False

    _selective_write_fault(monkeypatch, fail_second_approval)
    assert mcb.phase_publish(_PubArgs()) == 4
    assert env.a1.read_bytes() == env.a1_bytes and env.a2.read_bytes() == env.a2_bytes
    assert (env.qlib / "LIVE_MARKER.txt").exists()
    assert mcb.live_provider_ids() == (env.parent_pb, env.parent_cp)
    assert not list((env.root / "approvals").glob("*_rebind_to_*.md"))


def test_publish_reports_5_when_restore_also_fails(tmp_path, monkeypatch):
    # GPT Blocker 2 probe (double fault): a1 is rebound, a2's write fails (triggering the
    # rollback), and then RESTORING a1 also fails — the transaction must NOT claim a
    # verified rollback (the old code returned exit 4 with a half-rebound approvals dir);
    # exit 5 with the journal naming the inconsistent file.
    env = _publish_env(tmp_path, monkeypatch)
    a1_writes: dict[str, int] = {}

    def fault(path, _data):
        if path.name == "a2.yaml":
            return True  # rebind write of a2 fails -> handler engages with written=[a1]
        if path.name == "a1.yaml":
            a1_writes["n"] = a1_writes.get("n", 0) + 1
            return a1_writes["n"] == 2  # 1st = rebind OK, 2nd = the RESTORE fails
        return False

    _selective_write_fault(monkeypatch, fault)
    assert mcb.phase_publish(_PubArgs()) == 5
    steps = _json.loads((env.out / "publish_transaction_journal.json").read_text(encoding="utf-8"))["steps"]
    bad = [s for s in steps if s["status"] == "failed_rollback_incomplete"]
    assert bad and any("a1.yaml" in p for p in bad[0]["problems"])


def test_publish_rolls_back_when_record_write_fails(tmp_path, monkeypatch):
    # GPT Blocker 2b probe: the publish-record write fails AFTER the rebind — everything
    # (approvals, provider, state marker, record artifacts) must be restored; the
    # governance rebind md is written LAST so no false 'completed rebind' record survives.
    env = _publish_env(tmp_path, monkeypatch)
    _selective_write_fault(monkeypatch, lambda p, _d: p.name == "publish_record.json")
    assert mcb.phase_publish(_PubArgs()) == 4
    assert env.a1.read_bytes() == env.a1_bytes and env.a2.read_bytes() == env.a2_bytes
    assert (env.qlib / "LIVE_MARKER.txt").exists()
    assert not list((env.root / "approvals").glob("*_rebind_to_*.md")), \
        "a false 'successful rebind' governance record must not survive the rollback"
    assert not (env.staged / "metadata" / "publish_state.json").exists()
    assert not (env.out / "publish_record.json").exists()


def test_publish_refuses_deleted_approvals(tmp_path, monkeypatch):
    # GPT Blocker 3 probe: deleting bound approval YAMLs between execute and publish
    # previously published with `approvals_rebound: 0`. The pinned governance-set
    # attestation now refuses — including the delete-ALL case.
    env = _publish_env(tmp_path, monkeypatch)
    env.a2.unlink()
    assert mcb.phase_publish(_PubArgs()) == 2
    env.a1.unlink()
    (env.root / "approvals" / "exempt.yaml").unlink()
    assert mcb.phase_publish(_PubArgs()) == 2
    assert (env.qlib / "LIVE_MARKER.txt").exists() and (env.staged / "STAGED_MARKER.txt").exists()


def test_publish_refuses_added_approval(tmp_path, monkeypatch):
    # The set pin is two-sided: an approval ADDED after the review also refuses (it would
    # be silently rebound without ever having been part of the reviewed report).
    env = _publish_env(tmp_path, monkeypatch)
    (env.root / "approvals" / "a3_new.yaml").write_text(
        f"approval_id: a3\ndataset_id: d3\nto_status: approved\ndate: '2026-07-10'\n"
        f"provider_build_id: {env.parent_pb}\ncalendar_policy_id: {env.parent_cp}\n",
        encoding="utf-8")
    assert mcb.phase_publish(_PubArgs()) == 2
    _assert_untouched(env)


def test_publish_refuses_feature_bin_mutation(tmp_path, monkeypatch):
    # GPT Blocker 4 probe: mutate a feature BIN's bytes (same size) after the audited
    # build — the FULL-CONTENT re-attestation must refuse to publish the changed bytes.
    env = _publish_env(tmp_path, monkeypatch)
    env.staged_bin.write_bytes(b"\x09\x09\x09\x09")  # same size, different content
    assert mcb.phase_publish(_PubArgs()) == 2
    _assert_untouched(env)


def test_publish_refuses_git_state_drift(tmp_path, monkeypatch):
    # GPT Major 2 probe: code moved between execute and publish — the manifest would
    # misattribute the build; refuse.
    env = _publish_env(tmp_path, monkeypatch)
    monkeypatch.setattr(mcb, "_git_state", lambda: ("othersha", "clean"))
    assert mcb.phase_publish(_PubArgs()) == 2
    _assert_untouched(env)


def test_publish_refuses_policy_file_drift(tmp_path, monkeypatch):
    # GPT Major 1 probe: the minted policy FILE (not just a few fields) is pinned by
    # hash — any edit refuses.
    env = _publish_env(tmp_path, monkeypatch)
    env.policy_file.write_text(
        env.policy_file.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
    assert mcb.phase_publish(_PubArgs()) == 2
    _assert_untouched(env)


def test_builder_publish_acquires_global_lock(tmp_path, monkeypatch):
    # GPT Blocker 7: the publish LOCK lives at the common chokepoint — a bare
    # StagedQlibBackendBuilder.publish() (any entrypoint) acquires it, and the singleton
    # FileLock makes the monthly transaction's nested acquisition reentrant (the happy-path
    # test exercises the nesting for real).
    import data_infra.tushare_lock as tl
    from data_infra.pit_backend import StagedQlibBackendBuilder

    entered = []
    from contextlib import contextmanager

    @contextmanager
    def recording(timeout: float = 7200.0):
        entered.append(timeout)
        yield

    monkeypatch.setattr(tl, "provider_publish_lock", recording)
    data = tmp_path / "data"
    staged = data / "qlib_builds" / "lockprobe" / "provider"
    staged.mkdir(parents=True)
    (staged / "x.txt").write_text("x", encoding="utf-8")
    b = StagedQlibBackendBuilder(data_root=str(data), qlib_dir=str(data / "qlib_data"),
                                 build_id="lockprobe")
    b.publish(calendar_policy_id="frozen_20260701_thaw_step1", emit_manifest=False)
    assert entered, "publish() must acquire the global provider-publish lock"
