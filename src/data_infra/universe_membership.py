"""Research-side universe membership: PIT daily boolean masks from reference data.

This module turns *reference* datasets into daily membership/exclusion masks for the
multi-universe factor-evaluation framework (CICC-style 股票池). It deliberately contains
only masks derivable from reference data — index snapshots, ST ranges, listing dates.
Market-data screens (停牌 ``vol==0``/NaN proxy, 一字板 ``high==low`` at limit, microcap /
liquidity ranks) need a price panel and live in
``alpha_research.factor_eval.universes`` (Layer-2: masks, never row drops — see §8.1).

Index membership PIT semantics
------------------------------
Source: monthly Tushare ``index_weight`` snapshots under
``data/normalized/universe/index_weights/`` (vendor granularity is monthly — daily
constituent snapshots do not exist upstream; see Tushare数据接口 doc_id=96). A date ``t``
uses the latest snapshot **<= t** (as-of carry-forward), which is PIT-safe because a
snapshot is public on its own ``trade_date``.

Known staleness window: CSI semi-annual rebalances take effect mid-June / mid-December
(next trading day after the second Friday) while vendor snapshots land at month
start/end — e.g. 2023-06 snapshots are 06-01/06-02/06-30, so the ~5-10% changed
constituents are stale for up to ~9 trading days, twice a year. Monthly-rebalance
protocols whose rebalance dates coincide with snapshot dates (the CICC truth protocol)
are unaffected.

All masks share one shape convention: ``DataFrame(bool, index=dates, columns=instruments)``
with instruments in the Qlib upper-case underscore form (``000001_SZ``).
"""
from __future__ import annotations

import glob
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd

from data_infra.provider_metadata import ts_code_to_qlib

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INDEX_WEIGHTS_DIR = _PROJECT_ROOT / "data" / "normalized" / "universe" / "index_weights"
DEFAULT_ST_STOCKS_PATH = _PROJECT_ROOT / "data" / "qlib_data" / "instruments" / "st_stocks.txt"
DEFAULT_STOCK_BASIC_PATH = _PROJECT_ROOT / "data" / "reference" / "stock_basic.parquet"

#: CICC 股票池 exclusion: stocks listed less than one year (calendar days).
MIN_LISTING_AGE_DAYS_CICC = 365


def load_index_snapshots(
    index_code: str,
    weights_dir: str | os.PathLike | None = None,
) -> pd.DataFrame:
    """Load all monthly membership snapshots for one index.

    Returns a DataFrame with columns ``snapshot_date`` (Timestamp) and ``instrument``
    (Qlib upper form), one row per (snapshot, constituent). Empty DataFrame when the
    index has no snapshots at all.
    """
    weights_dir = Path(weights_dir) if weights_dir is not None else DEFAULT_INDEX_WEIGHTS_DIR
    frames: list[pd.DataFrame] = []
    for fp in sorted(glob.glob(str(weights_dir / "index_weights_*.parquet"))):
        df = pd.read_parquet(fp, columns=["index_code", "con_code", "trade_date"])
        df = df.loc[df["index_code"] == index_code]
        if df.empty:
            continue
        frames.append(df[["con_code", "trade_date"]])
    if not frames:
        return pd.DataFrame(columns=["snapshot_date", "instrument"])
    out = pd.concat(frames, ignore_index=True)
    out["snapshot_date"] = pd.to_datetime(out["trade_date"], errors="coerce")
    out = out.dropna(subset=["snapshot_date", "con_code"])
    out["instrument"] = [ts_code_to_qlib(c, lower=False) for c in out["con_code"]]
    return (
        out[["snapshot_date", "instrument"]]
        .drop_duplicates()
        .sort_values(["snapshot_date", "instrument"])
        .reset_index(drop=True)
    )


def index_membership_mask(
    index_code: str,
    dates: pd.DatetimeIndex,
    instruments: list[str],
    *,
    weights_dir: str | os.PathLike | None = None,
    snapshots: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Daily as-of membership mask for one index.

    Each date uses the latest snapshot ``<= date``. Dates before the first available
    snapshot are all-``False`` (e.g. CSI1000 before 2014-10 — the index did not exist;
    callers evaluating that domain must start at the first snapshot, mirroring the
    CICC "中证1000范围内测试从2014.11.01开始" rule).

    ``snapshots`` may be passed to reuse a :func:`load_index_snapshots` result.
    """
    if snapshots is None:
        snapshots = load_index_snapshots(index_code, weights_dir=weights_dir)
    mask = pd.DataFrame(False, index=dates, columns=instruments)
    if snapshots.empty:
        logger.warning("index_membership_mask(%s): no snapshots found — all-False mask", index_code)
        return mask

    inst_pos = {inst: i for i, inst in enumerate(instruments)}
    snap_dates = np.sort(snapshots["snapshot_date"].unique())
    members_by_snap: dict[pd.Timestamp, np.ndarray] = {}
    for snap, group in snapshots.groupby("snapshot_date"):
        cols = [inst_pos[i] for i in group["instrument"] if i in inst_pos]
        members_by_snap[snap] = np.asarray(sorted(cols), dtype=int)

    values = mask.to_numpy()
    # as-of: index of latest snapshot <= each date (-1 = before first snapshot)
    asof_idx = np.searchsorted(snap_dates, dates.to_numpy(), side="right") - 1
    for snap_i in np.unique(asof_idx):
        if snap_i < 0:
            continue
        row_sel = asof_idx == snap_i
        cols = members_by_snap[pd.Timestamp(snap_dates[snap_i])]
        if cols.size:
            values[np.ix_(row_sel, cols)] = True
    return pd.DataFrame(values, index=dates, columns=instruments)


def load_st_intervals(st_path: str | os.PathLike | None = None) -> pd.DataFrame:
    """Load the authoritative ST ranges file (instrument, start, end) — see §3.1."""
    st_path = Path(st_path) if st_path is not None else DEFAULT_ST_STOCKS_PATH
    df = pd.read_csv(
        st_path, sep="\t", header=None, names=["instrument", "start", "end"],
    )
    df["start"] = pd.to_datetime(df["start"], errors="coerce")
    df["end"] = pd.to_datetime(df["end"], errors="coerce")
    return df.dropna(subset=["instrument", "start", "end"])


def st_mask(
    dates: pd.DatetimeIndex,
    instruments: list[str],
    *,
    st_path: str | os.PathLike | None = None,
    intervals: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """``True`` where the stock is under ST/*ST on that date (interval-inclusive both ends)."""
    if intervals is None:
        intervals = load_st_intervals(st_path)
    mask = pd.DataFrame(False, index=dates, columns=instruments)
    values = mask.to_numpy()
    inst_pos = {inst: i for i, inst in enumerate(instruments)}
    date_arr = dates.to_numpy()
    for inst, start, end in intervals[["instrument", "start", "end"]].itertuples(index=False):
        col = inst_pos.get(inst)
        if col is None:
            continue
        row_sel = (date_arr >= np.datetime64(start)) & (date_arr <= np.datetime64(end))
        if row_sel.any():
            values[row_sel, col] = True
    return pd.DataFrame(values, index=dates, columns=instruments)


def _load_stock_basic(stock_basic_path: str | os.PathLike | None = None) -> pd.DataFrame:
    path = Path(stock_basic_path) if stock_basic_path is not None else DEFAULT_STOCK_BASIC_PATH
    return pd.read_parquet(path)


def listing_status_masks(
    dates: pd.DatetimeIndex,
    instruments: list[str],
    *,
    stock_basic: pd.DataFrame | None = None,
    stock_basic_path: str | os.PathLike | None = None,
    min_listing_age_days: int = MIN_LISTING_AGE_DAYS_CICC,
) -> dict[str, pd.DataFrame]:
    """Listing-derived masks from ``stock_basic`` (list_date / delist_date).

    Returns ``{"listed": ..., "young": ...}`` where

    - ``listed``: True when ``list_date <= t`` and (no delist or ``t < delist_date``).
      This is the base population for ``univ_all``.
    - ``young``: True when listed but for fewer than ``min_listing_age_days`` calendar
      days (the CICC 上市未满一年 exclusion; boundary: day ``list_date + 365`` is the
      first NON-young day).

    Instruments missing from ``stock_basic`` are never ``listed`` (fail-closed) — a
    warning is logged with the count.
    """
    if stock_basic is None:
        stock_basic = _load_stock_basic(stock_basic_path)
    ref = stock_basic.copy()
    ref["instrument"] = [ts_code_to_qlib(c, lower=False) for c in ref["ts_code"].astype(str)]
    ref["list_dt"] = pd.to_datetime(ref["list_date"], errors="coerce")
    ref["delist_dt"] = pd.to_datetime(ref.get("delist_date"), errors="coerce")
    ref = ref.drop_duplicates(subset=["instrument"], keep="first").set_index("instrument")

    n = len(instruments)
    list_arr = np.full(n, np.datetime64("NaT"), dtype="datetime64[ns]")
    delist_arr = np.full(n, np.datetime64("NaT"), dtype="datetime64[ns]")
    missing = 0
    for i, inst in enumerate(instruments):
        if inst in ref.index:
            row = ref.loc[inst]
            list_arr[i] = row["list_dt"] if pd.notna(row["list_dt"]) else np.datetime64("NaT")
            delist_arr[i] = row["delist_dt"] if pd.notna(row["delist_dt"]) else np.datetime64("NaT")
        else:
            missing += 1
    if missing:
        logger.warning("listing_status_masks: %d/%d instruments absent from stock_basic (never listed)",
                       missing, n)

    date_col = dates.to_numpy()[:, None]  # (T,1) broadcast vs (N,)
    has_list = ~np.isnat(list_arr)
    listed = has_list[None, :] & (date_col >= list_arr[None, :])
    delisted = ~np.isnat(delist_arr)[None, :] & (date_col >= delist_arr[None, :])
    listed &= ~delisted

    age_ok_from = list_arr + np.timedelta64(min_listing_age_days, "D")
    young = listed & (date_col < age_ok_from[None, :])

    return {
        "listed": pd.DataFrame(listed, index=dates, columns=instruments),
        "young": pd.DataFrame(young, index=dates, columns=instruments),
    }
