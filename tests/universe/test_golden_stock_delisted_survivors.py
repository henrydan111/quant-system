"""C3 test_stub: survivorship — later-delisted/unknown names STAY in the universe.

Contract (CONTRACTS.md C3): the universe includes delisted, suspended, renamed,
ST, merged, later-untradable names. The ledger must not be filtered against any
CURRENT vendor/master table (a code absent from today's stock_basic must still
appear historically). Tradability is applied only in execution, never here.
Every event carries provenance (source file, broker, row hash).
"""
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from data_infra.golden_stock_universe import (  # noqa: E402
    golden_stock_universe,
    load_golden_stock_events,
)


def _write_weekday_calendar(path: Path, start: str, end: str) -> None:
    days = pd.date_range(start, end, freq="D")
    cal = pd.DataFrame(
        {
            "cal_date": days.strftime("%Y%m%d"),
            "is_open": (days.dayofweek < 5).astype(int),
        }
    )
    cal.to_parquet(path, index=False)


def test_delisted_and_unknown_codes_survive(tmp_path: Path):
    data_dir = tmp_path / "broker_recommend"
    data_dir.mkdir()
    # 300280.SZ: a real later-delisted name; 999999.BJ: absent from EVERY master
    df = pd.DataFrame(
        {
            "month": ["202105", "202105"],
            "broker": ["券商X", "券商Y"],
            "ts_code": ["300280.SZ", "999999.BJ"],
            "name": ["紫天科技", "不存在的公司"],
        }
    )
    df.to_parquet(data_dir / "broker_recommend_202105.parquet", index=False)
    cal_path = tmp_path / "trade_cal.parquet"
    _write_weekday_calendar(cal_path, "2021-04-01", "2021-07-31")

    events = load_golden_stock_events(data_dir=data_dir, trade_cal_path=cal_path)
    # both names present in the ledger — no current-master filtering happened
    assert set(events["ts_code"]) == {"300280.SZ", "999999.BJ"}

    # both ACTIVE historically (2021-05-06 = first trading day >= day 4; 05-04..05 Tue/Wed
    # are weekdays -> activation 2021-05-04)
    act = events["activation_date"].iloc[0]
    u = golden_stock_universe(act, events=events)
    assert u == frozenset({"300280.SZ", "999999.BJ"})


def test_events_carry_provenance(tmp_path: Path):
    data_dir = tmp_path / "broker_recommend"
    data_dir.mkdir()
    pd.DataFrame(
        {
            "month": ["202105"],
            "broker": ["券商X"],
            "ts_code": ["300280.SZ"],
            "name": ["紫天科技"],
        }
    ).to_parquet(data_dir / "broker_recommend_202105.parquet", index=False)
    cal_path = tmp_path / "trade_cal.parquet"
    _write_weekday_calendar(cal_path, "2021-04-01", "2021-07-31")

    events = load_golden_stock_events(data_dir=data_dir, trade_cal_path=cal_path)
    row = events.iloc[0]
    for col in ("source_file", "broker", "row_hash", "activation_date"):
        assert col in events.columns
    # row_hash = sha256 hex (64 chars), deterministic provenance
    assert isinstance(row["row_hash"], str) and len(row["row_hash"]) == 64
