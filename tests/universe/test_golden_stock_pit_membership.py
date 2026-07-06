"""C3 test_stub: golden_stock_universe(date) is a PIT membership mask.

Contract (CONTRACTS.md C3): the universe at decision time T is built ONLY from
recommendation events whose activation (first eligible trading decision after
verified visibility = first trading day on/after the 4th calendar day of the
recommendation month) is <= T; a month's membership expires at the NEXT month's
activation. No lookahead: a June recommendation must be invisible in May.
"""
from pathlib import Path
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from data_infra.golden_stock_universe import (  # noqa: E402
    GoldenStockUniverseError,
    golden_stock_universe,
    load_golden_stock_events,
)


def _write_month(data_dir: Path, month: str, rows: list[tuple[str, str, str]]) -> None:
    df = pd.DataFrame(rows, columns=["broker", "ts_code", "name"])
    df.insert(0, "month", month)
    df.to_parquet(data_dir / f"broker_recommend_{month}.parquet", index=False)


def _write_weekday_calendar(path: Path, start: str, end: str) -> None:
    days = pd.date_range(start, end, freq="D")
    cal = pd.DataFrame(
        {
            "cal_date": days.strftime("%Y%m%d"),
            "is_open": (days.dayofweek < 5).astype(int),
        }
    )
    cal.to_parquet(path, index=False)


@pytest.fixture()
def fixture_env(tmp_path: Path):
    data_dir = tmp_path / "broker_recommend"
    data_dir.mkdir()
    # 2024-05: two brokers pick 000001.SZ, one picks 600000.SH
    _write_month(
        data_dir,
        "202405",
        [("券商A", "000001.SZ", "平安银行"), ("券商B", "000001.SZ", "平安银行"),
         ("券商A", "600000.SH", "浦发银行")],
    )
    # 2024-06: one pick, must NOT be visible in May (PIT)
    _write_month(data_dir, "202406", [("券商A", "300750.SZ", "宁德时代")])
    cal_path = tmp_path / "trade_cal.parquet"
    _write_weekday_calendar(cal_path, "2024-04-01", "2024-08-31")
    return data_dir, cal_path


def test_activation_is_first_trading_day_on_or_after_day4(fixture_env):
    data_dir, cal_path = fixture_env
    events = load_golden_stock_events(data_dir=data_dir, trade_cal_path=cal_path)
    # 2024-05-04 Sat, 05 Sun -> first trading day on/after day 4 = Mon 2024-05-06
    may = events[events["month"] == "202405"]
    assert (may["activation_date"] == pd.Timestamp("2024-05-06")).all()
    # expiry = June activation (2024-06-04 is a Tuesday)
    assert (may["expiry_date"] == pd.Timestamp("2024-06-04")).all()


def test_pit_membership_no_lookahead(fixture_env):
    data_dir, cal_path = fixture_env
    events = load_golden_stock_events(data_dir=data_dir, trade_cal_path=cal_path)

    # before May activation: nothing is visible
    assert golden_stock_universe("2024-05-02", events=events) == frozenset()
    # at May activation: May names in, June name ABSENT (published later)
    u = golden_stock_universe("2024-05-06", events=events)
    assert u == frozenset({"000001.SZ", "600000.SH"})
    # last May holding day (window is [activation, next_activation))
    assert golden_stock_universe("2024-06-03", events=events) == frozenset(
        {"000001.SZ", "600000.SH"}
    )
    # June activation: May expired, June active
    assert golden_stock_universe("2024-06-04", events=events) == frozenset({"300750.SZ"})
    # far before any data
    assert golden_stock_universe("2024-01-15", events=events) == frozenset()


def test_multi_broker_dedup_but_events_keep_provenance(fixture_env):
    data_dir, cal_path = fixture_env
    events = load_golden_stock_events(data_dir=data_dir, trade_cal_path=cal_path)
    # ledger keeps one row per (month, broker, ts_code)
    may_pab = events[(events["month"] == "202405") & (events["ts_code"] == "000001.SZ")]
    assert len(may_pab) == 2
    # membership mask dedups
    u = golden_stock_universe("2024-05-06", events=events)
    assert sorted(u) == ["000001.SZ", "600000.SH"]


def test_fail_closed_on_missing_data(tmp_path: Path):
    empty = tmp_path / "nothing"
    empty.mkdir()
    cal_path = tmp_path / "trade_cal.parquet"
    _write_weekday_calendar(cal_path, "2024-01-01", "2024-02-01")
    with pytest.raises(GoldenStockUniverseError):
        load_golden_stock_events(data_dir=empty, trade_cal_path=cal_path)
