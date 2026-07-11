"""Phase 5-C daily-raw job: last-complete-session resolution (CST close-aware) + the canonical
timing-preserving suspend_d writer."""
from __future__ import annotations

import sys
import types
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from data_infra.pipeline.update_daily_data import (  # noqa: E402
    DailyDataUpdater, resolve_last_complete_session)
from data_infra.pipeline.daily_ops import account_lock, missing_open_sessions  # noqa: E402


def _stub_updater(ref_dir):
    stub = DailyDataUpdater.__new__(DailyDataUpdater)  # bypass __init__ (no Tushare/config)
    stub.ref_dir = str(ref_dir)
    stub.update_reference_data = lambda d: None  # no-op the fetch
    return stub


def test_update_for_date_saturday_is_non_trading_skip(tmp_path):
    # GPT M2: the calendar holds ONLY open days (is_open='1' fetch); a Saturday is ABSENT -> a
    # legitimate non-trading skip (exit 0), NOT "missing daily data".
    ref = tmp_path / "reference"
    ref.mkdir(parents=True)
    pd.DataFrame({"exchange": "SSE", "cal_date": ["20260703", "20260706", "20260707"], "is_open": 1,
                  "pretrade_date": ""}).to_parquet(ref / "trade_cal.parquet")
    res = DailyDataUpdater.update_for_date(_stub_updater(ref), "20260704")  # Saturday
    assert res["is_trading_day"] is False and res["errors"] == []


def test_update_for_date_beyond_coverage_is_error(tmp_path):
    # GPT M2: a date beyond calendar coverage is an ERROR (insufficient calendar), not a silent skip.
    ref = tmp_path / "reference"
    ref.mkdir(parents=True)
    pd.DataFrame({"exchange": "SSE", "cal_date": ["20260703"], "is_open": 1,
                  "pretrade_date": ""}).to_parquet(ref / "trade_cal.parquet")
    res = DailyDataUpdater.update_for_date(_stub_updater(ref), "20260710")  # > max 20260703
    assert res["is_trading_day"] is True and res["errors"]


def test_account_lock_serializes(tmp_path):
    # GPT M4: the account lock is cross-process — a second acquire blocks until release; a stale lock
    # is stolen. Here: acquire, verify a fast re-acquire times out, then release + re-acquire.
    logs = str(tmp_path / "logs")
    import pytest as _pytest
    with account_lock(logs):
        with _pytest.raises(TimeoutError):
            with account_lock(logs, timeout=0.2, poll=0.05):
                pass
    with account_lock(logs):  # released -> re-acquirable
        pass


def test_missing_open_sessions_oldest_first(tmp_path):
    # GPT M3: the gap walker returns open sessions with no daily file, oldest-first (bounded).
    ref = tmp_path / "reference"
    ref.mkdir(parents=True)
    opens = ["20260701", "20260702", "20260703"]
    pd.DataFrame({"exchange": "SSE", "cal_date": opens, "is_open": 1,
                  "pretrade_date": ""}).to_parquet(ref / "trade_cal.parquet")
    daily_root = tmp_path / "daily"
    (daily_root / "2026").mkdir(parents=True)
    # only 20260703 has a file -> 0701, 0702 are the gaps
    pd.DataFrame({"ts_code": ["A"]}).to_parquet(daily_root / "2026" / "daily_20260703.parquet")
    gaps = missing_open_sessions(str(ref), str(daily_root), "20260703")
    assert gaps == ["20260701", "20260702"]


def _trade_cal(tmp_path, open_days):
    ref = tmp_path / "reference"
    ref.mkdir(parents=True, exist_ok=True)
    # a full week Mon..Sun; is_open=1 only for open_days
    days = ["20260629", "20260630", "20260701", "20260702", "20260703", "20260704", "20260705"]
    pd.DataFrame({"exchange": "SSE", "cal_date": days,
                  "is_open": [1 if d in open_days else 0 for d in days],
                  "pretrade_date": ""}).to_parquet(ref / "trade_cal.parquet")
    return str(ref)


OPEN = {"20260629", "20260630", "20260701", "20260702", "20260703"}  # Mon..Fri


def test_last_complete_session_before_close_rolls_back(tmp_path):
    ref = _trade_cal(tmp_path, OPEN)
    # Friday 20260703 at 14:00 CST — today's data not yet complete -> prior session (Thu 0702)
    assert resolve_last_complete_session(ref, now=datetime(2026, 7, 3, 14, 0)) == "20260702"


def test_last_complete_session_after_close_is_today(tmp_path):
    ref = _trade_cal(tmp_path, OPEN)
    # Friday 20260703 at 18:00 CST — past close -> today
    assert resolve_last_complete_session(ref, now=datetime(2026, 7, 3, 18, 0)) == "20260703"


def test_last_complete_session_on_weekend_uses_last_trading_day(tmp_path):
    ref = _trade_cal(tmp_path, OPEN)
    # Saturday 20260704 (closed) -> the last open day <= today = Friday 0703 (complete)
    assert resolve_last_complete_session(ref, now=datetime(2026, 7, 4, 12, 0)) == "20260703"


def test_last_complete_session_fails_closed_on_stale_calendar(tmp_path):
    # GPT B1: a calendar not future-aware through today (e.g. truncated by a prior buggy run) must
    # FAIL, not silently pick a stale session.
    ref = _trade_cal(tmp_path, OPEN)  # calendar ends 20260705
    with pytest.raises(SystemExit, match="future-aware|stale"):
        resolve_last_complete_session(ref, now=datetime(2026, 7, 10, 18, 0))  # today > calendar end


def test_last_complete_session_fails_when_only_preclose_today(tmp_path):
    # m2: if the only candidate is a pre-close today, refuse a partial session rather than return it.
    ref = _trade_cal(tmp_path, {"20260629"})  # only one open day, which is "today"
    with pytest.raises(SystemExit, match="pre-close|partial"):
        resolve_last_complete_session(ref, now=datetime(2026, 6, 29, 9, 0))


def test_update_reference_data_merges_calendar_not_truncate(tmp_path):
    # GPT B1 regression: a daily run must NOT truncate the future-aware calendar to target_date (which
    # freezes the selector). update_reference_data fetches a forward horizon and MERGES; a Monday run
    # must leave Tuesday selectable.
    ref = tmp_path / "reference"
    ref.mkdir(parents=True)
    pd.DataFrame({"exchange": "SSE",
                  "cal_date": pd.bdate_range("20260101", "20261231").strftime("%Y%m%d"),
                  "is_open": 1, "pretrade_date": ""}).to_parquet(ref / "trade_cal.parquet")
    fetched = pd.DataFrame({"exchange": "SSE",
                            "cal_date": pd.bdate_range("20260101", "20271231").strftime("%Y%m%d"),
                            "is_open": 1, "pretrade_date": ""})
    stub = types.SimpleNamespace(ref_dir=str(ref), fetcher=types.SimpleNamespace(
        fetch_stock_basic=lambda: pd.DataFrame(),
        fetch_trade_cal=lambda end_date: fetched))
    DailyDataUpdater.update_reference_data(stub, "20260706")  # a "Monday" run
    cal = pd.read_parquet(ref / "trade_cal.parquet")
    assert cal["cal_date"].astype(str).max() > "20260706", "future calendar must NOT be truncated"
    # Tuesday selector (post-close) returns Tuesday — the job advances, not stuck on Monday
    assert resolve_last_complete_session(str(ref), now=datetime(2026, 7, 7, 18, 0)) == "20260707"


def test_write_suspend_d_preserves_timing_atomic_overwrite(tmp_path):
    # the canonical writer keeps suspend_timing and overwrites (replaces) the same-date snapshot.
    df = pd.DataFrame({"ts_code": ["000001.SZ", "600000.SH"], "trade_date": ["20260703", "20260703"],
                       "suspend_type": ["S", "S"], "suspend_timing": ["", "09:30-10:00"],
                       "extra_col": [1, 2]})  # extra_col must be dropped
    stub = types.SimpleNamespace(
        data_dir=str(tmp_path),
        fetcher=types.SimpleNamespace(fetch_suspend_d=lambda trade_date: df))
    res = DailyDataUpdater.write_suspend_d(stub, "20260703")
    assert res["suspend_rows"] == 2 and res["suspend_timing_present"] is True
    out = pd.read_parquet(tmp_path / "market" / "suspend_d" / "2026" / "suspend_d_20260703.parquet")
    assert list(out.columns) == ["ts_code", "trade_date", "suspend_type", "suspend_timing"]
    assert set(out["suspend_timing"]) == {"", "09:30-10:00"}
    # re-fetch with fewer rows REPLACES (not merges) the snapshot
    df2 = pd.DataFrame({"ts_code": ["000001.SZ"], "trade_date": ["20260703"], "suspend_type": ["S"],
                        "suspend_timing": [""]})
    stub.fetcher = types.SimpleNamespace(fetch_suspend_d=lambda trade_date: df2)
    DailyDataUpdater.write_suspend_d(stub, "20260703")
    out2 = pd.read_parquet(tmp_path / "market" / "suspend_d" / "2026" / "suspend_d_20260703.parquet")
    assert len(out2) == 1  # replaced, not accumulated


def test_write_suspend_d_empty_day_writes_schema(tmp_path):
    stub = types.SimpleNamespace(
        data_dir=str(tmp_path),
        fetcher=types.SimpleNamespace(fetch_suspend_d=lambda trade_date: pd.DataFrame()))
    res = DailyDataUpdater.write_suspend_d(stub, "20260703")
    assert res["suspend_rows"] == 0
    out = pd.read_parquet(tmp_path / "market" / "suspend_d" / "2026" / "suspend_d_20260703.parquet")
    assert len(out) == 0 and "suspend_timing" in out.columns  # empty snapshot with the expected schema


def test_write_suspend_d_rejects_wrong_date_and_preserves_prior(tmp_path):
    # GPT M3: a response carrying the WRONG trade_date must RAISE and preserve the prior valid snapshot.
    good = pd.DataFrame({"ts_code": ["000001.SZ"], "trade_date": ["20260703"], "suspend_type": ["S"],
                         "suspend_timing": [""]})
    stub = types.SimpleNamespace(data_dir=str(tmp_path),
                                 fetcher=types.SimpleNamespace(fetch_suspend_d=lambda trade_date: good))
    DailyDataUpdater.write_suspend_d(stub, "20260703")
    path = tmp_path / "market" / "suspend_d" / "2026" / "suspend_d_20260703.parquet"
    assert len(pd.read_parquet(path)) == 1
    bad = pd.DataFrame({"ts_code": ["000002.SZ"], "trade_date": ["20260702"], "suspend_type": ["S"],
                        "suspend_timing": [""]})  # wrong date
    stub.fetcher = types.SimpleNamespace(fetch_suspend_d=lambda trade_date: bad)
    with pytest.raises(ValueError, match="trade_date"):
        DailyDataUpdater.write_suspend_d(stub, "20260703")
    assert list(pd.read_parquet(path)["ts_code"]) == ["000001.SZ"]  # prior snapshot intact


def test_write_suspend_d_rejects_missing_timing(tmp_path):
    # GPT M3: a nonempty response without suspend_timing is ambiguous -> RAISE (don't write).
    bad = pd.DataFrame({"ts_code": ["000001.SZ"], "trade_date": ["20260703"], "suspend_type": ["S"]})
    stub = types.SimpleNamespace(data_dir=str(tmp_path),
                                 fetcher=types.SimpleNamespace(fetch_suspend_d=lambda trade_date: bad))
    with pytest.raises(ValueError, match="missing columns|suspend_timing"):
        DailyDataUpdater.write_suspend_d(stub, "20260703")
    assert not (tmp_path / "market" / "suspend_d" / "2026" / "suspend_d_20260703.parquet").exists()
