"""Helpers for provider metadata and instrument sidecars.

This module keeps universe and sidecar generation out of the staged Qlib
builder so the same logic can be reused by the pipeline entrypoints and the
manual maintenance scripts.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable

import pandas as pd

logger = logging.getLogger(__name__)

IPO_LAG_DAYS = 90
STOCK_ST_START = pd.Timestamp("2016-01-04")
INDEX_UNIVERSE_MAP = {
    "000300.SH": "csi300",
    "000905.SH": "csi500",
    "000852.SH": "csi1000",
}
INDEX_CODES = {"000001.SH", "000300.SH", "000688.SH", "000852.SH", "000905.SH"}


def ts_code_to_qlib(ts_code: str, lower: bool = True) -> str:
    """Convert Tushare ``ts_code`` into the repo's Qlib code convention."""
    if pd.isna(ts_code):
        return ""
    code = str(ts_code).replace(".", "_")
    return code.lower() if lower else code.upper()


class SuspensionLookup:
    """P1-1: Range-based suspension lookup for the backtester.

    Built from ``data/market/suspension/suspension_ranges.parquet`` produced
    by ``scripts/fetch_suspend_d_historical.py``. Used by the event-driven
    backtester's ``exchange.is_suspended()`` method as the authoritative
    source, with ``vol == 0`` as fallback only.

    Usage:
        lookup = SuspensionLookup.from_ranges_file(ranges_path)
        lookup.is_suspended("000001.SZ", pd.Timestamp("2024-06-15"))  # -> bool
    """

    def __init__(self, ranges_by_ts_code: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]]):
        self._ranges = ranges_by_ts_code

    @classmethod
    def from_ranges_file(cls, ranges_path: str) -> "SuspensionLookup":
        """Load a ``suspension_ranges.parquet`` and index by ts_code."""
        if not os.path.exists(ranges_path):
            logger.warning("Suspension ranges file missing: %s (falling back to empty)", ranges_path)
            return cls({})
        df = pd.read_parquet(ranges_path)
        if df.empty:
            return cls({})
        df["suspend_start"] = pd.to_datetime(df["suspend_start"])
        df["suspend_end"] = pd.to_datetime(df["suspend_end"])
        ranges: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]] = {}
        for _, row in df.iterrows():
            ts_code = str(row["ts_code"])
            ranges.setdefault(ts_code, []).append((row["suspend_start"], row["suspend_end"]))
        for ts_code in ranges:
            ranges[ts_code].sort()
        logger.info("Loaded %d suspension ranges across %d symbols", len(df), len(ranges))
        return cls(ranges)

    def is_suspended(self, ts_code: str, date: pd.Timestamp) -> bool | None:
        """Return True/False if the table has coverage, None otherwise.

        Returning None allows the backtester to fall back to its ``vol == 0``
        proxy for dates or symbols not covered by the authoritative table.
        """
        # Normalize ts_code to the Tushare format used in the ranges file
        normalized = ts_code.upper()
        if "_" in normalized and "." not in normalized:
            # Convert Qlib-format (000001_SZ) back to Tushare format
            normalized = normalized.replace("_", ".")
        if normalized not in self._ranges:
            return None
        date_ts = pd.Timestamp(date)
        for start, end in self._ranges[normalized]:
            if date_ts < start:
                return False  # sorted — all later ranges are also later
            if start <= date_ts <= end:
                return True
        return False


def stock_basic_bounds(
    stock_basic: pd.DataFrame,
    ts_code: str,
    ipo_lag_days: int = IPO_LAG_DAYS,
) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Return the effective ``(list_date + IPO_LAG, delist_date)`` bounds.

    This is the single source of truth for determining when a stock is
    "investable" according to the same contract enforced at the instruments
    sidecar layer by :func:`build_all_stocks_universe`. Consumers that read
    the PIT ledgers directly under ``data/pit_ledger/`` bypass the
    instruments sidecar guard and should use this helper to apply the same
    filter manually.

    Args:
        stock_basic: Reference DataFrame loaded from
            ``data/reference/stock_basic.parquet``. Must contain ``ts_code``,
            ``list_date``, and (optionally) ``delist_date`` columns.
        ts_code: Tushare ``ts_code`` (e.g. ``"000001.SZ"``). Case-insensitive.
        ipo_lag_days: Grace period applied to the raw ``list_date``.
            Default matches the project-wide ``IPO_LAG_DAYS`` constant.

    Returns:
        ``(effective_list_date, delist_date)`` where:
            - ``effective_list_date = list_date + ipo_lag_days`` (None if
              ``list_date`` is missing in ``stock_basic``)
            - ``delist_date`` (None if the stock is still listed or the
              row is absent)

    The caller should mask any ``(ts_code, query_date)`` rows where:
        query_date < effective_list_date  OR  query_date > delist_date

    Reference: see ``CLAUDE.md §3`` "Delist contract" and
    :func:`build_all_stocks_universe` for the provider-side implementation.
    """
    if stock_basic is None or stock_basic.empty:
        return None, None
    normalized = str(ts_code).upper()
    subset = stock_basic.loc[stock_basic["ts_code"].astype(str).str.upper() == normalized]
    if subset.empty:
        return None, None
    row = subset.iloc[0]

    list_date_raw = row.get("list_date")
    list_date = pd.to_datetime(list_date_raw, errors="coerce") if list_date_raw is not None else pd.NaT
    effective_list: pd.Timestamp | None = None
    if not pd.isna(list_date):
        effective_list = list_date + pd.Timedelta(days=ipo_lag_days)

    delist_date_raw = row.get("delist_date")
    delist_date = pd.to_datetime(delist_date_raw, errors="coerce") if delist_date_raw is not None else pd.NaT
    delist_out: pd.Timestamp | None = None if pd.isna(delist_date) else delist_date

    return effective_list, delist_out


def ensure_directory(path: str) -> None:
    """Create ``path`` if it does not exist."""
    os.makedirs(path, exist_ok=True)


def write_instruments_file(records: Iterable[tuple[str, pd.Timestamp, pd.Timestamp]], output_path: str) -> None:
    """Write a Qlib instruments file."""
    lines = []
    for code, start, end in records:
        lines.append(f"{code}\t{start.strftime('%Y-%m-%d')}\t{end.strftime('%Y-%m-%d')}")
    lines.sort()
    ensure_directory(os.path.dirname(output_path))
    with open(output_path, "w", encoding="utf-8") as handle:
        if lines:
            handle.write("\n".join(lines))
            handle.write("\n")
    logger.info("Wrote %d instrument rows to %s", len(lines), output_path)


def _merge_intervals(intervals: list[tuple[pd.Timestamp, pd.Timestamp]]) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Merge overlapping date intervals."""
    if not intervals:
        return []
    merged: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1] + pd.Timedelta(days=1):
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def build_all_stocks_universe(
    security_master: pd.DataFrame,
    price_ranges: pd.DataFrame,
    instruments_dir: str,
    metadata_dir: str,
    ipo_lag_days: int = IPO_LAG_DAYS,
) -> dict[str, int]:
    """Build ``all_stocks.txt`` and the unlagged base-universe sidecar."""
    ensure_directory(instruments_dir)
    ensure_directory(metadata_dir)

    master = security_master.copy()
    master["qlib_code"] = master["ts_code"].map(lambda value: ts_code_to_qlib(value, lower=False))
    master["list_date"] = pd.to_datetime(master["list_date"], errors="coerce")
    master["delist_date"] = pd.to_datetime(master["delist_date"], errors="coerce")
    merged = price_ranges.merge(
        master[
            [
                "ts_code",
                "qlib_code",
                "exchange",
                "market",
                "list_status",
                "list_date",
                "delist_date",
            ]
        ],
        on=["ts_code", "qlib_code"],
        how="left",
    )

    # Keep A-share style equities only for the stock universe.
    merged = merged[merged["ts_code"].str.endswith((".SH", ".SZ", ".BJ"), na=False)].copy()
    merged = merged[~merged["ts_code"].isin(INDEX_CODES)].copy()
    merged["numeric_code"] = merged["ts_code"].str.split(".").str[0]
    merged = merged[~merged["exchange"].eq("BJ")]
    merged = merged[~merged["numeric_code"].str.startswith("200", na=False)]
    merged = merged[
        ~(
            merged["numeric_code"].str.startswith("900", na=False)
            & merged["ts_code"].str.endswith(".SH", na=False)
        )
    ]

    merged["base_start"] = merged[["list_date", "price_start"]].max(axis=1)
    merged["base_end"] = merged["price_end"]
    has_delist = merged["delist_date"].notna()
    merged.loc[has_delist, "base_end"] = merged.loc[has_delist, ["base_end", "delist_date"]].min(axis=1)
    merged = merged[merged["base_start"].notna() & merged["base_end"].notna()].copy()
    merged = merged[merged["base_start"] <= merged["base_end"]].copy()

    base_path = os.path.join(metadata_dir, "all_stocks_unlagged.parquet")
    merged[
        [
            "ts_code",
            "qlib_code",
            "price_start",
            "price_end",
            "base_start",
            "base_end",
            "list_date",
            "delist_date",
            "exchange",
            "market",
            "list_status",
        ]
    ].to_parquet(base_path, index=False)

    lagged = merged.copy()
    lagged["lagged_start"] = lagged["base_start"] + pd.to_timedelta(ipo_lag_days, unit="D")
    lagged = lagged[lagged["lagged_start"] <= lagged["base_end"]].copy()
    records = [
        (row.qlib_code, row.lagged_start.normalize(), row.base_end.normalize())
        for row in lagged.itertuples(index=False)
    ]
    write_instruments_file(records, os.path.join(instruments_dir, "all_stocks.txt"))
    logger.info(
        "Built all_stocks universe with %d lagged entries and %d unlagged rows",
        len(records),
        len(merged),
    )
    return {"lagged_rows": len(records), "unlagged_rows": len(merged)}


def build_index_universes(index_weights: pd.DataFrame, instruments_dir: str) -> dict[str, int]:
    """Build monthly-snapshot index universe files from ``index_weights``."""
    ensure_directory(instruments_dir)
    summary: dict[str, int] = {}
    weights = index_weights.copy()
    weights["trade_date"] = pd.to_datetime(weights["trade_date"], errors="coerce")
    weights = weights.dropna(subset=["index_code", "con_code", "trade_date"])

    for index_code, file_stem in INDEX_UNIVERSE_MAP.items():
        idx_df = weights[weights["index_code"] == index_code].copy()
        if idx_df.empty:
            summary[file_stem] = 0
            continue
        snapshots = sorted(idx_df["trade_date"].unique())
        members_by_snapshot = {
            snapshot: set(idx_df.loc[idx_df["trade_date"] == snapshot, "con_code"].tolist())
            for snapshot in snapshots
        }
        records: list[tuple[str, pd.Timestamp, pd.Timestamp]] = []
        for con_code in sorted(idx_df["con_code"].dropna().unique()):
            in_index = False
            start_date: pd.Timestamp | None = None
            for pos, snapshot in enumerate(snapshots):
                present = con_code in members_by_snapshot[snapshot]
                if present and not in_index:
                    in_index = True
                    start_date = snapshot
                    continue
                if not present and in_index:
                    records.append(
                        (
                            ts_code_to_qlib(con_code, lower=False),
                            start_date.normalize(),
                            (snapshot - pd.Timedelta(days=1)).normalize(),
                        )
                    )
                    in_index = False
                    start_date = None
            if in_index and start_date is not None:
                records.append(
                    (
                        ts_code_to_qlib(con_code, lower=False),
                        start_date.normalize(),
                        pd.Timestamp(snapshots[-1]).normalize(),
                    )
                )
        write_instruments_file(records, os.path.join(instruments_dir, f"{file_stem}.txt"))
        summary[file_stem] = len(records)

    return summary


def _daily_st_intervals(stock_st_daily: pd.DataFrame, trading_calendar: pd.DatetimeIndex) -> pd.DataFrame:
    """Convert daily ST membership rows into interval ranges."""
    if stock_st_daily.empty:
        return pd.DataFrame(columns=["instrument", "start_date", "end_date"])

    calendar_index = {date: idx for idx, date in enumerate(trading_calendar)}
    daily = stock_st_daily.copy()
    daily["trade_date"] = pd.to_datetime(daily["trade_date"], errors="coerce")
    daily = daily.dropna(subset=["ts_code", "trade_date"])
    daily = daily[daily["trade_date"].isin(calendar_index)]
    daily["instrument"] = daily["ts_code"].map(lambda value: ts_code_to_qlib(value, lower=False))

    intervals: list[dict[str, pd.Timestamp | str]] = []
    for instrument, group in daily.groupby("instrument"):
        positions = sorted(calendar_index[date] for date in group["trade_date"].unique())
        if not positions:
            continue
        start = positions[0]
        prev = positions[0]
        for pos in positions[1:]:
            if pos != prev + 1:
                intervals.append(
                    {
                        "instrument": instrument,
                        "start_date": trading_calendar[start].normalize(),
                        "end_date": trading_calendar[prev].normalize(),
                    }
                )
                start = pos
            prev = pos
        intervals.append(
            {
                "instrument": instrument,
                "start_date": trading_calendar[start].normalize(),
                "end_date": trading_calendar[prev].normalize(),
            }
        )

    return pd.DataFrame(intervals)


def _namechange_st_intervals(namechange: pd.DataFrame) -> pd.DataFrame:
    """Create pre-2016 ST intervals from the name-change ledger."""
    if namechange.empty:
        return pd.DataFrame(columns=["instrument", "start_date", "end_date"])

    cutoff_end = STOCK_ST_START - timedelta(days=1)
    nc = namechange.copy()
    nc["start_date"] = pd.to_datetime(nc["start_date"], errors="coerce")
    nc["end_date"] = pd.to_datetime(nc["end_date"], errors="coerce")
    nc = nc.dropna(subset=["ts_code", "name", "start_date"])
    nc = nc[nc["name"].str.upper().str.contains("ST", na=False)].copy()
    nc["end_date"] = nc["end_date"].fillna(cutoff_end)
    nc["end_date"] = nc["end_date"].clip(upper=cutoff_end)
    nc = nc[nc["start_date"] <= cutoff_end].copy()
    nc["instrument"] = nc["ts_code"].map(lambda value: ts_code_to_qlib(value, lower=False))

    intervals: list[dict[str, pd.Timestamp | str]] = []
    for instrument, group in nc.groupby("instrument"):
        merged = _merge_intervals(
            [
                (row.start_date.normalize(), row.end_date.normalize())
                for row in group.itertuples(index=False)
            ]
        )
        for start, end in merged:
            intervals.append({"instrument": instrument, "start_date": start, "end_date": end})
    return pd.DataFrame(intervals)


def build_st_universe(
    stock_st_daily: pd.DataFrame,
    namechange: pd.DataFrame,
    trading_calendar: pd.DatetimeIndex,
    output_path: str,
) -> int:
    """Build the authoritative ``st_stocks.txt`` instruments file."""
    api_intervals = _daily_st_intervals(stock_st_daily, trading_calendar)
    namechange_intervals = _namechange_st_intervals(namechange)
    combined = pd.concat([namechange_intervals, api_intervals], ignore_index=True)
    if combined.empty:
        write_instruments_file([], output_path)
        return 0

    merged_records: list[tuple[str, pd.Timestamp, pd.Timestamp]] = []
    for instrument, group in combined.groupby("instrument"):
        intervals = _merge_intervals(
            [
                (pd.Timestamp(row.start_date).normalize(), pd.Timestamp(row.end_date).normalize())
                for row in group.itertuples(index=False)
            ]
        )
        merged_records.extend((instrument, start, end) for start, end in intervals)

    write_instruments_file(merged_records, output_path)
    return len(merged_records)


def write_instruments_readme(instruments_dir: str) -> str:
    """Write a short provider README describing the universe sidecars."""
    ensure_directory(instruments_dir)
    path = os.path.join(instruments_dir, "README.md")
    content = """# Provider Instruments

- `all.txt`: raw provider instrument coverage emitted by the Qlib dump step.
- `all_stocks.txt`: A-share stock universe with the repo's 90-day IPO lag preserved for research compatibility.
- `csi300.txt`, `csi500.txt`, `csi1000.txt`: monthly-snapshot PIT approximations derived from `index_weights`.
- `st_stocks.txt`: authoritative ST interval sidecar rebuilt from `stock_st_daily` plus the pre-2016 `namechange` fallback.
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return path


@dataclass
class ProviderMetadataSummary:
    """Compact summary of generated provider sidecars."""

    all_stocks_rows: int = 0
    unlagged_rows: int = 0
    st_rows: int = 0
    csi300_rows: int = 0
    csi500_rows: int = 0
    csi1000_rows: int = 0


# ──────────────────────────────────────────────────────────────────────
# Shenwan SW2021 historical industry membership
#
# Helpers that load the time-varying SW2021 stock-to-industry mapping
# from `data/universe/industry_sw2021_members/industry_sw2021_members.parquet`
# and provide PIT-safe lookups for research code.
#
# Bootstrap script: scripts/fetch_sw_industry_members.py
# Coverage audit:   scripts/verify_sw_industry_coverage.py
# Coverage report:  workspace/outputs/sw_industry_coverage_audit_20260427.md
#
# Coverage caveat (2026-04-27): pre-2014 coverage is 94-97% of the daily
# trading universe due to Shenwan's own backfill thinness — NOT survivorship
# bias (rigorously verified). Stocks unclassified for an as-of date return
# None / pd.NA, which `factor_eval.neutralization` handles via notna() mask.
# Strict-coverage research should restrict to dates >= 2014-01-01.
# ──────────────────────────────────────────────────────────────────────

_SW_MEMBERS_PATH_DEFAULT = (
    "data/universe/industry_sw2021_members/industry_sw2021_members.parquet"
)
_SW_MEMBERS_CACHE: dict[str, pd.DataFrame] = {}
_LEVEL_TO_COL = {"L1": "l1_code", "L2": "l2_code", "L3": "l3_code"}


def _normalize_ts_code(code: str) -> str:
    """Normalize any of '000001.SZ', '000001_SZ', '000001_sz' → '000001.SZ'.

    Research code uses uppercase Qlib codes (`ts_to_qlib_code` at
    workspace/research/alpha_mining/event_driven_strategy_research.py:292),
    while `ts_code_to_qlib(..., lower=True)` defaults to lowercase. Membership
    storage keeps Tushare dot-form, so all 3 inputs must round-trip.
    """
    return str(code).strip().upper().replace("_", ".")


def load_sw_members(
    *,
    project_root: str | os.PathLike | None = None,
    force_reload: bool = False,
) -> pd.DataFrame:
    """Cached load of the SW2021 historical membership table.

    Returns the DataFrame as written by `scripts/fetch_sw_industry_members.py`
    with columns: l1_code, l1_name, l2_code, l2_name, l3_code, l3_name,
    ts_code (Tushare dot-form), name, in_date (Timestamp), out_date
    (Timestamp; `2099-12-31` sentinel = still active), is_new ('Y'/'N').

    Cached per resolved-path to avoid repeat parquet reads in research code.
    Use `force_reload=True` after a fresh bootstrap.
    """
    if project_root is None:
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
    path = os.path.join(str(project_root), _SW_MEMBERS_PATH_DEFAULT)
    if not force_reload and path in _SW_MEMBERS_CACHE:
        return _SW_MEMBERS_CACHE[path]
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"SW2021 members file not found at {path}. "
            "Run scripts/fetch_sw_industry_members.py first."
        )
    df = pd.read_parquet(path)
    # Defensive: ensure date columns are datetime
    if not pd.api.types.is_datetime64_any_dtype(df["in_date"]):
        df["in_date"] = pd.to_datetime(df["in_date"], errors="coerce")
    if not pd.api.types.is_datetime64_any_dtype(df["out_date"]):
        df["out_date"] = pd.to_datetime(df["out_date"], errors="coerce")
    _SW_MEMBERS_CACHE[path] = df
    return df


def industry_as_of(
    ts_code: str, as_of_date, level: str = "L1"
) -> str | None:
    """Return the SW2021 industry code a stock belonged to on as_of_date.

    Args:
        ts_code: Tushare format '000001.SZ' OR Qlib '000001_SZ' / '000001_sz'.
            Auto-normalized via `_normalize_ts_code`.
        as_of_date: pd.Timestamp / datetime / 'YYYY-MM-DD' string.
        level: 'L1' / 'L2' / 'L3'.

    Returns:
        Industry code like '801780.SI' (银行 / Banks), or None if the stock
        was never classified or has no membership covering as_of_date. Null
        return is the canonical "skip from industry-aware computations"
        signal — see coverage caveat in module header.
    """
    if level not in _LEVEL_TO_COL:
        raise ValueError(f"level must be 'L1', 'L2', or 'L3'; got {level!r}")
    code_col = _LEVEL_TO_COL[level]
    members = load_sw_members()
    norm = _normalize_ts_code(ts_code)
    as_of = pd.Timestamp(as_of_date)

    rows = members[members["ts_code"] == norm]
    if rows.empty:
        return None
    hit = rows[(rows["in_date"] <= as_of) & (rows["out_date"] >= as_of)]
    if hit.empty:
        return None
    # Multiple matches (overlapping windows shouldn't happen; defensive):
    # take the row with the latest in_date.
    if len(hit) > 1:
        hit = hit.sort_values("in_date", ascending=False).head(1)
    value = hit.iloc[0][code_col]
    if pd.isna(value):
        return None
    return str(value)


def build_industry_series_asof(
    index: pd.MultiIndex, level: str = "L1"
) -> pd.Series:
    """Vectorized time-varying industry label for a (datetime, instrument)
    or (instrument, datetime) MultiIndex.

    Auto-detects MultiIndex ordering via the level names (or first-level
    dtype if names are absent) and restores the input ordering on return.

    Algorithm: per-instrument membership lookup using a vectorized
    merge_asof on the in_date dimension, then a forward boundary check on
    out_date. Avoids constructing a full 22M-row cartesian product
    (Codex review-1 Finding 4 — naive merge_asof is memory-hostile).
    Performance gate: < 2s on a 1-year fixture (250d × 5k stocks).

    Args:
        index: pd.MultiIndex with datetime + instrument levels (either order).
        level: 'L1' / 'L2' / 'L3'.

    Returns:
        pd.Series of industry codes aligned to ``index``. NaN for any
        (datetime, instrument) without an active SW2021 classification on
        that date — research code should treat as "skip from industry-aware
        computations".
    """
    if level not in _LEVEL_TO_COL:
        raise ValueError(f"level must be 'L1', 'L2', or 'L3'; got {level!r}")
    code_col = _LEVEL_TO_COL[level]

    # Detect index ordering
    names = list(index.names)
    if "datetime" in names and "instrument" in names:
        dt_pos = names.index("datetime")
        inst_pos = names.index("instrument")
    else:
        # Fallback: assume first level is datetime if it has a datetime dtype
        first_vals = index.get_level_values(0)
        if pd.api.types.is_datetime64_any_dtype(first_vals):
            dt_pos, inst_pos = 0, 1
        else:
            dt_pos, inst_pos = 1, 0

    dt_vals = index.get_level_values(dt_pos)
    inst_vals = index.get_level_values(inst_pos)

    # Build query DataFrame in original order (so we can restore later)
    query = pd.DataFrame(
        {
            "datetime": pd.to_datetime(dt_vals),
            # Normalize each instrument code (handle SH/sz/_/. variants)
            "ts_code_norm": [_normalize_ts_code(c) for c in inst_vals],
            "_orig_pos": range(len(index)),
        }
    )

    members = load_sw_members()[
        ["ts_code", "in_date", "out_date", code_col]
    ].copy()
    members = members.rename(columns={"ts_code": "ts_code_norm"})

    # Per-instrument merge_asof on in_date (much cheaper than full cartesian).
    # pd.merge_asof with `by=` requires both sides sorted by the ON key
    # (datetime / in_date) globally; the `by` grouping keys do not need
    # their own ordering.
    query_sorted = query.sort_values("datetime", kind="mergesort").reset_index(
        drop=True
    )
    members_sorted = members.sort_values("in_date", kind="mergesort").reset_index(
        drop=True
    )
    merged = pd.merge_asof(
        query_sorted,
        members_sorted,
        left_on="datetime",
        right_on="in_date",
        by="ts_code_norm",
        direction="backward",
    )
    # Enforce out_date guard: reject rows where in_date <= dt > out_date
    invalid = merged["out_date"].notna() & (
        merged["datetime"] > merged["out_date"]
    )
    merged.loc[invalid, code_col] = pd.NA

    # Restore original ordering and emit Series aligned to input index
    merged = merged.sort_values("_orig_pos").reset_index(drop=True)
    return pd.Series(
        merged[code_col].values, index=index, name=f"sw2021_{level.lower()}"
    )

