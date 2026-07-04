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


def _mk_features(prov, codes):
    for c in codes:
        (prov / "features" / c).mkdir(parents=True, exist_ok=True)
        (prov / "features" / c / "close.day.bin").write_bytes(b"\x00")


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


def test_fresh_window_survivorship_audit_passes_when_universe_complete(tmp_path, monkeypatch):
    monkeypatch.setattr(mcb, "PROJECT_ROOT", tmp_path)
    _mk_fresh_window(tmp_path)
    prov = tmp_path / "prov"
    (prov / "instruments").mkdir(parents=True)
    (prov / "instruments" / "all_stocks.txt").write_text(
        "000001_SZ  2020-01-01  2030-01-01\n000002_SZ  2020-01-01  2030-01-01\n", encoding="utf-8")
    _mk_features(prov, ["000001_SZ", "000002_SZ"])  # universe AND feature tree complete
    res = mcb.fresh_window_survivorship_audit(prov, "2026-02-28", "2026-03-06")
    assert res["ok"] is True, res["violations"]
