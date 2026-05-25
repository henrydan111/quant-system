"""JoinQuant-API compatibility shim — lets JoinQuant strategies run locally
with minimal porting. The shim exposes the most-used JoinQuant research
APIs, backed by the local JoinQuant PIT cache (``data/external/jq_pit_cache/``)
and the local Tushare/Qlib data infrastructure.

Usage in a ported JoinQuant strategy:

    # JoinQuant original:
    #     from jqdata import *
    # Local replacement:
    from src.data_infra.jqdata_local import (
        get_index_stocks, get_fundamentals, get_current_data,
        query, valuation,
    )

Coverage as of 2026-05-22 (v1):
  - ``get_index_stocks(index_jq_code, date=None)`` — PIT cache; honors date
    if provided, else uses today (research-environment semantics).
  - ``get_fundamentals(q, date=...)`` — minimal SQLAlchemy-style query
    interface supporting ``valuation.market_cap`` / ``valuation.code``
    columns with ``order_by(...)`` / ``filter(.in_(universe))``.
  - ``get_current_data()`` — returns a CurrentDataProxy with ``.is_st``,
    ``.paused``, ``.day_open``, ``.high_limit``, ``.low_limit``,
    ``.last_price``, ``.name`` per stock. Backed by PIT cache flags +
    local Qlib OHLCV. Requires a context-date set via ``set_context_date``.

Not yet covered (raise NotImplementedError):
  - ``get_price`` with minute frequency
  - ``get_extras`` for fields other than is_st
  - ``order_target_value`` (use the local backtest engine instead)

This shim is for STRATEGY-LOGIC verification, not order routing. A ported
JoinQuant strategy should be wrapped in the local
``EventDrivenBacktester`` for actual execution simulation.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Iterable, Optional

import pandas as pd

from .jq_pit_cache import JoinQuantPITLoader, jq_to_tushare, tushare_to_jq

logger = logging.getLogger(__name__)


# ─── Context (single thread-local "current date") ────────────────────
#
# JoinQuant strategies don't pass `date` explicitly to most calls —
# `get_current_data()` returns data as of `context.current_dt`. Our shim
# requires the caller to set the context date before reading. The
# local backtest engine sets this at the start of each bar.

_LOCAL_CTX = threading.local()


def set_context_date(date) -> None:
    """Set the context date used by `get_current_data()` and any
    `get_index_stocks(date=None)` calls. The local engine should call
    this once per bar before invoking strategy methods.
    """
    _LOCAL_CTX.date = pd.Timestamp(date).normalize()


def get_context_date() -> Optional[pd.Timestamp]:
    return getattr(_LOCAL_CTX, "date", None)


# ─── get_index_stocks ────────────────────────────────────────────────

_loader = JoinQuantPITLoader()


def get_index_stocks(index_jq_code: str, date=None,
                     return_format: str = "jq") -> list[str]:
    """JoinQuant-compatible ``get_index_stocks``. Returns the PIT-correct
    membership at ``date`` (or the context date) as JoinQuant codes by
    default. Pass ``return_format='tushare'`` for Tushare codes.

    Raises:
        ValueError: if neither ``date`` nor a context date is set.
    """
    eff = pd.Timestamp(date).normalize() if date is not None else get_context_date()
    if eff is None:
        raise ValueError(
            "get_index_stocks requires either a date arg or a context date "
            "(call jqdata_local.set_context_date(d) first)."
        )
    members_ts = _loader.get_index_stocks(index_jq_code, eff)
    if return_format == "tushare":
        return members_ts
    return [tushare_to_jq(c) for c in members_ts]


# ─── valuation table + query DSL ─────────────────────────────────────
#
# Minimal SQLAlchemy-style replica of JoinQuant's pattern:
#
#     q = query(valuation.code, valuation.market_cap) \
#           .filter(valuation.code.in_(initial_list))   \
#           .order_by(valuation.market_cap.asc())
#     df = get_fundamentals(q, date=...)


class _Column:
    def __init__(self, table_name: str, col_name: str):
        self.table_name = table_name
        self.col_name = col_name

    def in_(self, values):
        return ("filter_in", self, list(values))

    def asc(self):
        return ("order_asc", self)

    def desc(self):
        return ("order_desc", self)


class _Valuation:
    code = _Column("valuation", "code")
    market_cap = _Column("valuation", "market_cap")
    circulating_market_cap = _Column("valuation", "circulating_market_cap")
    pe_ratio = _Column("valuation", "pe")
    pb_ratio = _Column("valuation", "pb")


valuation = _Valuation()


@dataclass
class _Query:
    select: list
    filters: list
    order_by: list

    def filter(self, *expressions) -> "_Query":
        self.filters.extend(expressions)
        return self

    def order_by(self, *expressions) -> "_Query":
        self.order_by.extend(expressions)
        return self


def query(*columns) -> _Query:
    return _Query(select=list(columns), filters=[], order_by=[])


def get_fundamentals(q: _Query, date=None) -> pd.DataFrame:
    """Execute the query against the local PIT cache valuation snapshot.

    Returns a DataFrame with a ``code`` column (JoinQuant format) and the
    selected valuation columns, sorted by ``order_by`` clauses.
    """
    eff = pd.Timestamp(date).normalize() if date is not None else get_context_date()
    if eff is None:
        raise ValueError(
            "get_fundamentals requires either a date arg or a context date."
        )
    snap = _loader.get_valuation_snapshot(eff)   # raises CacheMissError if empty
    # Apply filters
    for f in q.filters:
        if isinstance(f, tuple) and f[0] == "filter_in":
            col, values = f[1], f[2]
            # values are JoinQuant codes from caller; convert to ts_code
            ts_codes = [jq_to_tushare(v) for v in values]
            snap = snap[snap["ts_code"].isin(ts_codes)]
    # Apply ordering
    sort_keys, sort_dirs = [], []
    for o in q.order_by:
        if isinstance(o, tuple) and o[0] in ("order_asc", "order_desc"):
            col = o[1]
            sort_keys.append(col.col_name)
            sort_dirs.append(o[0] == "order_asc")
    if sort_keys:
        snap = snap.sort_values(by=sort_keys, ascending=sort_dirs)
    # Project to selected columns
    out = snap.copy()
    out["code"] = out["ts_code"].map(tushare_to_jq)
    selected_cols = ["code"]
    for c in q.select:
        if c.col_name == "code":
            continue
        if c.col_name in out.columns:
            selected_cols.append(c.col_name)
    return out[selected_cols].reset_index(drop=True)


# ─── get_current_data ────────────────────────────────────────────────

class _StockCurrentData:
    """Per-stock view, populated from PIT cache flags + local Qlib OHLCV
    for the day. NaN-safe — fields default to None or False when missing."""

    __slots__ = ("name", "is_st", "paused", "day_open",
                 "high_limit", "low_limit", "last_price")

    def __init__(self):
        self.name = ""
        self.is_st = False
        self.paused = False
        self.day_open = None
        self.high_limit = None
        self.low_limit = None
        self.last_price = None


class _CurrentDataProxy(dict):
    """Dict-like that lazily materializes _StockCurrentData on first access.

    Backed by:
      - flags (is_st, paused) → PIT cache
      - day_open / high_limit / low_limit / last_price → local Qlib
        (caller injects via ``inject_day_quotes``)
    """

    def __init__(self, ctx_date: pd.Timestamp,
                 day_quotes: Optional[dict] = None):
        super().__init__()
        self.ctx_date = ctx_date
        self.day_quotes = day_quotes or {}

    def __missing__(self, jq_code: str):
        # Build on demand
        s = _StockCurrentData()
        ts_code = jq_to_tushare(jq_code)
        try:
            s.is_st = _loader.is_st(ts_code, self.ctx_date)
            s.paused = _loader.is_paused(ts_code, self.ctx_date)
        except Exception:
            pass
        q = self.day_quotes.get(ts_code) or self.day_quotes.get(jq_code) or {}
        s.day_open = q.get("open")
        s.high_limit = q.get("high_limit") or q.get("up_limit")
        s.low_limit = q.get("low_limit") or q.get("down_limit")
        s.last_price = q.get("close") if q.get("close") is not None else s.day_open
        self[jq_code] = s
        return s


_current_data_proxy: Optional[_CurrentDataProxy] = None


def inject_day_quotes(day_quotes: dict) -> None:
    """The local backtest engine calls this at the start of each bar with
    a ``{ts_code: {'open':..., 'close':..., 'up_limit':..., 'down_limit':...}}``
    dict so ``get_current_data()`` returns matching values.
    """
    global _current_data_proxy
    d = get_context_date()
    if d is None:
        raise ValueError(
            "inject_day_quotes requires set_context_date first."
        )
    _current_data_proxy = _CurrentDataProxy(d, day_quotes)


def get_current_data() -> _CurrentDataProxy:
    """JoinQuant-compatible ``get_current_data()`` returning a dict-like that
    indexes on JoinQuant ts_codes (``'002001.XSHE'``)."""
    global _current_data_proxy
    if _current_data_proxy is None:
        d = get_context_date()
        if d is None:
            raise ValueError(
                "get_current_data requires set_context_date first. "
                "Call inject_day_quotes(day_quotes) at the start of each bar."
            )
        _current_data_proxy = _CurrentDataProxy(d, {})
    return _current_data_proxy


# ─── Convenience: a single import banner ─────────────────────────────

__all__ = [
    "set_context_date",
    "get_context_date",
    "inject_day_quotes",
    "get_index_stocks",
    "get_fundamentals",
    "get_current_data",
    "query",
    "valuation",
]
