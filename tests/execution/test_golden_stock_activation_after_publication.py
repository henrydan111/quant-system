"""C3 test_stub: a recommendation enters NO EARLIER than the next eligible
trading decision after verified visibility.

Contract (CONTRACTS.md C3): month M's list is populated by the vendor within
days 1-3 with no per-row disclosure timestamp, so visibility is conservatively
day 4; activation = first TRADING day on/after day 4 — holidays push it later,
never earlier. Before activation the name must be inactive.
"""
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from data_infra.golden_stock_universe import (  # noqa: E402
    golden_stock_universe,
    load_golden_stock_events,
)


def _write_calendar_with_holiday(path: Path) -> None:
    """Weekday calendar for 2024-04..08, but 2024-05-06 (Mon) is CLOSED."""
    days = pd.date_range("2024-04-01", "2024-08-31", freq="D")
    is_open = (days.dayofweek < 5).astype(int)
    cal = pd.DataFrame({"cal_date": days.strftime("%Y%m%d"), "is_open": is_open})
    cal.loc[cal["cal_date"] == "20240506", "is_open"] = 0
    cal.to_parquet(path, index=False)


def test_holiday_pushes_activation_later_never_earlier(tmp_path: Path):
    data_dir = tmp_path / "broker_recommend"
    data_dir.mkdir()
    pd.DataFrame(
        {
            "month": ["202405"],
            "broker": ["券商A"],
            "ts_code": ["000001.SZ"],
            "name": ["平安银行"],
        }
    ).to_parquet(data_dir / "broker_recommend_202405.parquet", index=False)
    cal_path = tmp_path / "trade_cal.parquet"
    _write_calendar_with_holiday(cal_path)

    events = load_golden_stock_events(data_dir=data_dir, trade_cal_path=cal_path)
    act = events["activation_date"].iloc[0]

    # 05-04 Sat, 05-05 Sun, 05-06 holiday -> activation = Tue 2024-05-07
    assert act == pd.Timestamp("2024-05-07")
    # activation is on/after calendar day 4 of the month
    assert act >= pd.Timestamp("2024-05-04")

    # inactive on every day before activation (incl. the closed Monday)
    for d in ("2024-05-03", "2024-05-04", "2024-05-05", "2024-05-06"):
        assert golden_stock_universe(d, events=events) == frozenset()
    # active exactly from activation
    assert golden_stock_universe("2024-05-07", events=events) == frozenset({"000001.SZ"})


def test_activation_always_a_trading_day(tmp_path: Path):
    data_dir = tmp_path / "broker_recommend"
    data_dir.mkdir()
    for month in ("202405", "202406", "202407"):
        pd.DataFrame(
            {
                "month": [month],
                "broker": ["券商A"],
                "ts_code": ["000001.SZ"],
                "name": ["平安银行"],
            }
        ).to_parquet(data_dir / f"broker_recommend_{month}.parquet", index=False)
    cal_path = tmp_path / "trade_cal.parquet"
    _write_calendar_with_holiday(cal_path)

    cal = pd.read_parquet(cal_path)
    open_days = set(
        pd.to_datetime(cal.loc[cal["is_open"] == 1, "cal_date"], format="%Y%m%d")
    )
    events = load_golden_stock_events(data_dir=data_dir, trade_cal_path=cal_path)
    assert events["activation_date"].isin(open_days).all()
    # day-of-month >= 4 for every activation
    assert (events["activation_date"].dt.day >= 4).all()
