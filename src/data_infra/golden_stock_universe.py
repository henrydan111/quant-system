"""C3 · 券商金股 PIT universe ledger (CONTRACTS.md C3, gates Phase 0).

Builds a point-in-time boolean membership universe from the raw monthly
broker_recommend files (``data/analyst/broker_recommend/broker_recommend_{YYYYMM}.parquet``,
schema ``month/broker/ts_code/name`` — no per-row disclosure timestamp).

PIT visibility anchor
---------------------
Month M's list is populated by the vendor within days 1-3 of the month with no
per-row timestamp, so visibility is conservatively **calendar day 4**; a
recommendation enters no earlier than the next eligible trading decision:
``activation_date = first trading day on/after day 4 of month M`` (holidays push
it later, never earlier). Membership expires at the NEXT month's activation
(``expiry_date``), giving clean non-overlapping ~1-month windows. This is the
same anchor validated in ``workspace/research/broker_recommend_alpha`` (2026-06-28).

Survivorship (the C3 core)
--------------------------
The ledger is built ONLY from recommendation events. It is NEVER joined against
a current vendor/master table — delisted, suspended, renamed, ST, merged and
otherwise later-untradable names stay in the historical universe. Tradability
(suspension, limit-up/down, T+1, liquidity) is applied ONLY in execution.

Provenance: every event row carries ``source_file`` and a sha256 ``row_hash``
over ``month|broker|ts_code|name``.

Enforced by: tests/universe/test_golden_stock_pit_membership.py,
tests/universe/test_golden_stock_delisted_survivors.py,
tests/execution/test_golden_stock_activation_after_publication.py.
"""
from __future__ import annotations

import glob
import hashlib
import logging
import os
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = _PROJECT_ROOT / "data" / "analyst" / "broker_recommend"
DEFAULT_TRADE_CAL_PATH = _PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet"

_REQUIRED_COLUMNS = ("month", "broker", "ts_code", "name")
_MONTH_RE = re.compile(r"^\d{6}$")


class GoldenStockUniverseError(Exception):
    """Fail-closed error for the 金股 PIT universe ledger."""


def _load_open_days(trade_cal_path: str | os.PathLike | None) -> np.ndarray:
    path = Path(trade_cal_path) if trade_cal_path is not None else DEFAULT_TRADE_CAL_PATH
    if not path.exists():
        raise GoldenStockUniverseError(f"trade calendar not found: {path}")
    cal = pd.read_parquet(path)
    if "is_open" not in cal.columns or "cal_date" not in cal.columns:
        raise GoldenStockUniverseError(
            f"trade calendar missing cal_date/is_open columns: {path}"
        )
    open_days = (
        pd.to_datetime(cal.loc[cal["is_open"] == 1, "cal_date"].astype(str), format="%Y%m%d")
        .drop_duplicates()
        .sort_values()
        .to_numpy()
    )
    if len(open_days) == 0:
        raise GoldenStockUniverseError(f"trade calendar has no open days: {path}")
    return open_days


def _first_trading_on_or_after(open_days: np.ndarray, target: datetime) -> pd.Timestamp | None:
    idx = int(np.searchsorted(open_days, np.datetime64(target), side="left"))
    if idx >= len(open_days):
        return None
    return pd.Timestamp(open_days[idx])


def _month_anchor(open_days: np.ndarray, month: str) -> pd.Timestamp | None:
    """First trading day on/after calendar day 4 of ``month`` (YYYYMM)."""
    y, m = int(month[:4]), int(month[4:6])
    return _first_trading_on_or_after(open_days, datetime(y, m, 4))


def _next_month(month: str) -> str:
    y, m = int(month[:4]), int(month[4:6])
    if m == 12:
        return f"{y + 1}01"
    return f"{y}{m + 1:02d}"


def _row_hash(month: str, broker: str, ts_code: str, name: str) -> str:
    payload = f"{month}|{broker}|{ts_code}|{name}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_golden_stock_events(
    data_dir: str | os.PathLike | None = None,
    trade_cal_path: str | os.PathLike | None = None,
) -> pd.DataFrame:
    """Load the full recommendation-event ledger with PIT activation windows.

    Returns one row per (month, broker, ts_code) with columns:
    ``month, broker, ts_code, name, source_file, row_hash, activation_date,
    expiry_date``. Months whose activation cannot be resolved inside the trade
    calendar are DROPPED with a warning (no trading decision exists for them);
    an unresolvable expiry (last usable month) is left as NaT = open-ended
    until calendar end.
    """
    data_dir = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
    files = sorted(glob.glob(str(data_dir / "broker_recommend_*.parquet")))
    if not files:
        raise GoldenStockUniverseError(f"no broker_recommend_*.parquet under {data_dir}")

    open_days = _load_open_days(trade_cal_path)

    frames: list[pd.DataFrame] = []
    for fp in files:
        df = pd.read_parquet(fp)
        missing = [c for c in _REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise GoldenStockUniverseError(f"{fp} missing columns {missing}")
        df = df[list(_REQUIRED_COLUMNS)].copy()
        df["month"] = df["month"].astype(str)
        bad = ~df["month"].str.match(_MONTH_RE)
        if bad.any():
            raise GoldenStockUniverseError(
                f"{fp} has malformed month values: {df.loc[bad, 'month'].unique()[:5]}"
            )
        df["source_file"] = Path(fp).name
        frames.append(df)

    events = pd.concat(frames, ignore_index=True)
    events = events.drop_duplicates(subset=["month", "broker", "ts_code"], keep="first")
    events["row_hash"] = [
        _row_hash(m, b, t, n)
        for m, b, t, n in zip(events["month"], events["broker"], events["ts_code"], events["name"])
    ]

    anchors: dict[str, pd.Timestamp | None] = {}
    expiries: dict[str, pd.Timestamp | None] = {}
    for month in sorted(events["month"].unique()):
        anchors[month] = _month_anchor(open_days, month)
        expiries[month] = _month_anchor(open_days, _next_month(month))

    unresolved = [m for m, a in anchors.items() if a is None]
    if unresolved:
        logger.warning(
            "golden_stock_universe: dropping %d month(s) beyond the trade calendar "
            "(no activation resolvable): %s",
            len(unresolved),
            unresolved,
        )
        events = events[~events["month"].isin(unresolved)]
        if events.empty:
            raise GoldenStockUniverseError(
                "no month has a resolvable activation inside the trade calendar"
            )

    events["activation_date"] = events["month"].map(anchors)
    events["expiry_date"] = events["month"].map(expiries)  # NaT when beyond calendar
    events = events.reset_index(drop=True)
    return events[
        ["month", "broker", "ts_code", "name", "source_file", "row_hash",
         "activation_date", "expiry_date"]
    ]


def golden_stock_universe(
    date: str | pd.Timestamp,
    *,
    events: pd.DataFrame | None = None,
    data_dir: str | os.PathLike | None = None,
    trade_cal_path: str | os.PathLike | None = None,
) -> frozenset[str]:
    """PIT membership at decision time ``date``: activation <= date < expiry.

    Only recommendation events already visible (activation <= date) enter; a
    NaT expiry (last usable month) means open-ended until calendar end. The
    result is a set of Tushare ``ts_code`` — convert with
    ``provider_metadata.ts_code_to_qlib`` for provider joins (C8).
    """
    if events is None:
        events = load_golden_stock_events(data_dir=data_dir, trade_cal_path=trade_cal_path)
    t = pd.Timestamp(date)
    active = events[
        (events["activation_date"] <= t)
        & (events["expiry_date"].isna() | (t < events["expiry_date"]))
    ]
    return frozenset(active["ts_code"].unique())


def golden_stock_membership_mask(
    dates: pd.DatetimeIndex,
    *,
    events: pd.DataFrame | None = None,
    data_dir: str | os.PathLike | None = None,
    trade_cal_path: str | os.PathLike | None = None,
    qlib_form: bool = True,
) -> pd.DataFrame:
    """Daily boolean mask ``DataFrame(index=dates, columns=instruments)``.

    Columns are Qlib upper-underscore instruments when ``qlib_form`` (C8 join
    convention: ``000001.SZ -> 000001_SZ``), else raw ts_code. Layer-2
    discipline: this is a mask, never a row drop.
    """
    if events is None:
        events = load_golden_stock_events(data_dir=data_dir, trade_cal_path=trade_cal_path)
    codes = sorted(events["ts_code"].unique())
    columns = [c.replace(".", "_") for c in codes] if qlib_form else codes
    mask = pd.DataFrame(False, index=pd.DatetimeIndex(dates), columns=columns)
    col_of = dict(zip(codes, columns))
    for _, ev in events.drop_duplicates(subset=["month", "ts_code"]).iterrows():
        start = ev["activation_date"]
        end = ev["expiry_date"]
        in_win = (mask.index >= start) & (mask.index < end if pd.notna(end) else True)
        mask.loc[in_win, col_of[ev["ts_code"]]] = True
    return mask
