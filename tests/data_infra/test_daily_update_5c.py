"""Phase 5-C daily-raw job: last-complete-session resolution (CST close-aware) + the canonical
timing-preserving suspend_d writer."""
from __future__ import annotations

import sys
import types
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from data_infra.pipeline.update_daily_data import (  # noqa: E402
    DailyDataUpdater, resolve_last_complete_session)


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
