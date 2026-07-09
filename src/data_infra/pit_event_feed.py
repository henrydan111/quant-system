"""Sanctioned EVENT-LEVEL door into the PIT ledgers (row-level, not panel).

Why this module exists
----------------------
``pit_research_loader`` serves **as-of panels** (field value per date). Event
consumers (the intel-center universal event store) need **row-level events**
with a visibility timestamp: "业绩预告 arrived, visible from date X". Reading
``data/pit_ledger/*`` directly is banned outside the sanctioned layer (PIT002
hard error); this module is the third blessed reader (after the loader and the
builder), deliberately NARROW:

- **whitelisted datasets + payload fields only** (``EVENT_FEED_SPECS``) —
  unknown dataset / field → refuse;
- **visibility = the ledger's own validated anchor**: ``effective_date`` where
  the ledger carries it; ``dividends`` (no effective_date column) derives it as
  ``strictly_next_open_trade_day(disclosure_date)`` — the same load-bearing
  helper the builder uses (§3.2), never re-implemented;
- **D3 born-sealed clamp**: requests past the live spent-OOS boundary are
  refused (same rule as the research loader — no seal escape here);
- **provider-bounds guard (§3.1)**: direct ledger readers MUST filter via
  ``provider_metadata.stock_basic_bounds``; rows whose visible_at falls outside
  ``[list_date+IPO_LAG, delist_date]`` are dropped;
- rows with null visibility are dropped and COUNTED (fail-closed, logged).

Enforced by: tests/data_infra/test_pit_event_feed.py.
Allowlisted for PIT002 in config/lint/unsafe_pit_dates_allowlist.yaml.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from data_infra.pit_backend import strictly_next_open_trade_day
from data_infra.pit_research_loader import live_spent_oos_end
from data_infra.provider_metadata import stock_basic_bounds

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_LEDGER_ROOT = _PROJECT_ROOT / "data" / "pit_ledger"
_TRADE_CAL = _PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet"
_STOCK_BASIC = _PROJECT_ROOT / "data" / "reference" / "stock_basic.parquet"


class PitEventFeedError(RuntimeError):
    """Fail-closed error for the event-level ledger door."""


#: The full contract: dataset -> visibility rule + payload whitelist.
#: Adding a dataset/field here is a config change (review + tests), never ad hoc.
EVENT_FEED_SPECS: dict[str, dict] = {
    "forecast": {
        "visible_col": "effective_date",
        "payload": ["ann_date", "end_date", "type", "p_change_min", "p_change_max",
                     "net_profit_min", "net_profit_max", "summary"],
    },
    "stk_holdertrade": {
        "visible_col": "effective_date",
        "payload": ["ann_date", "holder_name", "holder_type", "in_de",
                     "change_vol", "change_ratio", "avg_price", "after_ratio"],
    },
    "holder_number": {
        "visible_col": "effective_date",
        "payload": ["ann_date", "end_date", "holder_num"],
    },
    "dividends": {
        "visible_col": None,                       # derived from disclosure_date
        "derive_from": "disclosure_date",
        "payload": ["ann_date", "end_date", "div_proc", "stk_div", "cash_div",
                     "cash_div_tax", "record_date", "ex_date"],
    },
    # ---- 辅助账本(scripts/build_aux_pit_ledgers.py;事件/卡片用途,非因子字段)----
    "express": {
        "visible_col": "effective_date",
        "payload": ["ann_date", "end_date", "revenue", "operate_profit", "n_income",
                     "diluted_eps", "diluted_roe", "yoy_net_profit", "yoy_sales"],
    },
    "fina_audit": {
        "visible_col": "effective_date",
        "payload": ["ann_date", "end_date", "audit_result", "audit_agency"],
    },
    "fina_mainbz": {
        # 可见性 = 同期定期报告 ann_date 的严格次开盘日(builder 内 join income 账本推导)
        "visible_col": "effective_date",
        "payload": ["ann_date", "end_date", "bz_item", "bz_sales", "bz_profit", "curr_type"],
    },
}


def _open_calendar() -> pd.DatetimeIndex:
    """Sorted+deduped open-day calendar — MUST match pit_backend.open_calendar()
    (trade_cal carries duplicate/unsorted rows; searchsorted breaks otherwise)."""
    cal = pd.read_parquet(_TRADE_CAL)
    dates = pd.to_datetime(cal.loc[cal["is_open"] == 1, "cal_date"].astype(str))
    return pd.DatetimeIndex(dates.sort_values().unique())


def load_event_feed(
    dataset: str,
    *,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    instruments: list[str] | None = None,
) -> pd.DataFrame:
    """Return event rows with a validated ``visible_at`` for ``dataset``.

    Columns: ``ts_code``, ``visible_at`` (Timestamp; PIT anchor), ``dataset``,
    plus the spec's whitelisted payload columns. Sorted by visible_at.

    Fail-closed on: unknown dataset, window past the spent-OOS boundary,
    missing ledger file. Null-visibility rows and rows outside the §3.1
    listing bounds are dropped (counts logged).
    """
    spec = EVENT_FEED_SPECS.get(dataset)
    if spec is None:
        raise PitEventFeedError(
            f"dataset {dataset!r} is not in EVENT_FEED_SPECS — the event door is "
            f"whitelist-only (known: {sorted(EVENT_FEED_SPECS)})")

    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    boundary = live_spent_oos_end()
    if end_ts > boundary:
        raise PitEventFeedError(
            f"window end {end_ts.date()} exceeds the spent-OOS boundary "
            f"{boundary.date()} (D3 born-sealed; no seal escape at this door)")

    path = _LEDGER_ROOT / dataset / f"{dataset}.parquet"
    if not path.exists():
        raise PitEventFeedError(f"ledger missing for {dataset}: {path}")
    led = pd.read_parquet(path)

    # ---- visibility ----
    if spec["visible_col"] is not None:
        vis = pd.to_datetime(led[spec["visible_col"]], errors="coerce")
    else:
        base = pd.to_datetime(led[spec["derive_from"]], errors="coerce")
        vis = strictly_next_open_trade_day(base, _open_calendar())
    led = led.assign(visible_at=vis)
    n_null = int(led["visible_at"].isna().sum())
    led = led[led["visible_at"].notna()]

    led = led[(led["visible_at"] >= start_ts) & (led["visible_at"] <= end_ts)]
    if instruments is not None:
        led = led[led["ts_code"].isin(set(instruments))]

    # ---- §3.1 provider bounds guard ----
    sb = pd.read_parquet(_STOCK_BASIC)
    dropped_bounds = 0
    keep_mask = pd.Series(True, index=led.index)
    for code in led["ts_code"].unique():
        lo, hi = stock_basic_bounds(sb, code)
        m = led["ts_code"] == code
        ok = pd.Series(True, index=led.index[m])
        if lo is not None:
            ok &= led.loc[m, "visible_at"] >= lo
        if hi is not None:
            ok &= led.loc[m, "visible_at"] <= hi
        keep_mask.loc[m] = ok
    dropped_bounds = int((~keep_mask).sum())
    led = led[keep_mask]

    if n_null or dropped_bounds:
        logger.info("event_feed[%s]: dropped %d null-visibility + %d out-of-bounds rows",
                    dataset, n_null, dropped_bounds)

    cols = ["ts_code", "visible_at"] + [c for c in spec["payload"] if c in led.columns]
    out = led[cols].copy()
    out["dataset"] = dataset
    return out.sort_values("visible_at").reset_index(drop=True)
