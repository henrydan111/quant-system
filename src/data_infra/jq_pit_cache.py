"""JoinQuant PIT cache reader — the canonical local mirror of JoinQuant's
point-in-time views (`get_index_stocks`, `valuation.market_cap`, `is_st`,
`paused`) that Tushare either doesn't expose or computes differently.

This module is **read-only**. Refresh is performed manually via a JoinQuant
research notebook (see ``workspace/scripts/templates/jq_pit_cache_refresh.py``
and ``data/external/jq_pit_cache/README.md``).

Bidirectional verification use cases:
  1. Local strategy → JoinQuant deployment: a local backtest can use this
     cache to source the exact same universe membership / market_cap
     ranking JoinQuant uses, eliminating the ~5pp cross-stack noise
     attributable to data-source micro-differences.
  2. JoinQuant strategy → local verification: the
     ``src/data_infra/jqdata_local`` shim translates JoinQuant API calls
     (``get_index_stocks``, ``get_fundamentals(valuation.market_cap)``,
     ``get_current_data().is_st / paused``) into reads against this cache.

All stock codes returned are in **Tushare format** (``002001.SZ``,
``600519.SH``). The original JoinQuant codes (``002001.XSHE``,
``600519.XSHG``) are converted on write into the cache.
"""

from __future__ import annotations

import json
import logging
from datetime import date as _date
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)

# Default cache root — relative to project root.
_DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "external" / "jq_pit_cache"

DateLike = Union[str, pd.Timestamp, _date]


def _to_ts(d: DateLike) -> pd.Timestamp:
    return pd.Timestamp(d).normalize()


def jq_to_tushare(code: str) -> str:
    """Convert a single JoinQuant code to Tushare format.

    ``002001.XSHE`` → ``002001.SZ``
    ``600519.XSHG`` → ``600519.SH``
    """
    return code.replace(".XSHE", ".SZ").replace(".XSHG", ".SH")


def tushare_to_jq(code: str) -> str:
    """Convert a single Tushare code to JoinQuant format.

    ``002001.SZ`` → ``002001.XSHE``
    ``600519.SH`` → ``600519.XSHG``
    """
    return code.replace(".SZ", ".XSHE").replace(".SH", ".XSHG")


class CacheMissError(KeyError):
    """Raised when the requested date/code is outside cache coverage.

    Strategy code should catch this and either (a) skip the date, or
    (b) fall back to a local approximation. Never silently substitute
    a different value — PIT correctness depends on knowing when data
    is unavailable.
    """


class JoinQuantPITLoader:
    """Read-only accessor for the JoinQuant PIT cache.

    The loader is cheap to construct (just records the cache root) and
    memoizes parquet reads, so a strategy can hold one instance for the
    entire backtest.

    Args:
        cache_dir: Path to the cache root. Defaults to
            ``data/external/jq_pit_cache/`` resolved from the project root.

    Example:
        >>> loader = JoinQuantPITLoader()
        >>> members = loader.get_index_stocks('399101.XSHE',
        ...                                   '2015-07-28')
        >>> # forward-fills to the nearest prior available snapshot
        >>> 'SZ' in members[0]
        True
    """

    def __init__(self, cache_dir: Optional[Union[str, Path]] = None):
        self.cache_dir = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_DIR
        if not self.cache_dir.exists():
            logger.warning(
                "JoinQuant PIT cache dir does not exist: %s. "
                "Calls will raise CacheMissError until the cache is populated. "
                "See %s/README.md for refresh instructions.",
                self.cache_dir, self.cache_dir,
            )

    # ─── manifest + coverage ─────────────────────────────────────────

    def manifest(self) -> dict:
        """Return the cache manifest (or an empty stub if not present).

        Strategy code should call this once to verify the cache covers
        the backtest window before consuming any data.
        """
        path = self.cache_dir / "manifest.json"
        if not path.exists():
            return {
                "schema_version": None,
                "last_refresh_utc": None,
                "indices_tracked": [],
                "coverage": {},
                "notes": "manifest.json missing — run "
                         "scripts/refresh_jq_pit_cache_manifest.py to generate.",
            }
        return json.loads(path.read_text(encoding="utf-8"))

    def coverage(self) -> dict:
        """Convenience accessor returning the ``coverage`` block of the manifest."""
        return self.manifest().get("coverage", {})

    # ─── index_members ───────────────────────────────────────────────

    @lru_cache(maxsize=64)
    def _load_index_members_year(self, index_jq_code: str, year: int) -> pd.DataFrame:
        """Read one (index, year) parquet. Empty frame if the file doesn't exist."""
        path = self.cache_dir / "index_members" / index_jq_code / f"{year}.parquet"
        if not path.exists():
            return pd.DataFrame(columns=["date", "ts_code"])
        df = pd.read_parquet(path)
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        return df

    def available_index_snapshots(self, index_jq_code: str) -> list[pd.Timestamp]:
        """Return all dates for which we have a snapshot of ``index_jq_code``."""
        idx_dir = self.cache_dir / "index_members" / index_jq_code
        if not idx_dir.exists():
            return []
        dates = set()
        for f in sorted(idx_dir.glob("*.parquet")):
            try:
                year = int(f.stem)
            except ValueError:
                continue
            df = self._load_index_members_year(index_jq_code, year)
            dates.update(df["date"].unique())
        return sorted(pd.Timestamp(d) for d in dates)

    def get_index_stocks(self, index_jq_code: str, date: DateLike,
                         forward_fill: bool = True) -> list[str]:
        """Return the index membership at ``date`` in Tushare format.

        Args:
            index_jq_code: Index code in JoinQuant format (e.g.,
                ``'399101.XSHE'``, ``'000300.XSHG'``).
            date: Lookup date.
            forward_fill: When True (default), if ``date`` has no exact
                snapshot, returns the nearest prior snapshot's membership.
                When False, raises ``CacheMissError`` for non-snapshot dates.
                Most JoinQuant index reconstitutions are semi-annual, so
                forward-fill is the correct semantic for daily strategies.

        Returns:
            Sorted list of ts_codes (Tushare format).

        Raises:
            CacheMissError: When the cache has no snapshot at or before
                ``date``, or the index isn't tracked.
        """
        d = _to_ts(date)
        snaps = self.available_index_snapshots(index_jq_code)
        if not snaps:
            raise CacheMissError(
                f"No snapshots in cache for index {index_jq_code}. "
                f"Refresh via workspace/scripts/templates/jq_pit_cache_refresh.py."
            )
        if d < snaps[0] and not forward_fill:
            raise CacheMissError(
                f"Date {d.date()} is before earliest snapshot "
                f"({snaps[0].date()}) for {index_jq_code}."
            )
        # Find largest snap <= d (forward-fill); else earliest snap
        candidates = [s for s in snaps if s <= d]
        chosen = candidates[-1] if candidates else snaps[0]
        df = self._load_index_members_year(index_jq_code, chosen.year)
        members = df[df["date"] == chosen]["ts_code"].tolist()
        return sorted(set(members))

    # ─── valuation ───────────────────────────────────────────────────

    @lru_cache(maxsize=64)
    def _load_valuation_month(self, year: int, month: int) -> pd.DataFrame:
        path = self.cache_dir / "valuation" / f"{year:04d}-{month:02d}.parquet"
        if not path.exists():
            return pd.DataFrame(
                columns=["date", "ts_code", "market_cap",
                         "circulating_market_cap", "pe", "pb"]
            )
        df = pd.read_parquet(path)
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        return df

    def get_valuation_snapshot(self, date: DateLike) -> pd.DataFrame:
        """Return all (ts_code, market_cap, ...) rows for ``date``.

        Raises:
            CacheMissError: When the cache has no valuation rows for the
                target date.
        """
        d = _to_ts(date)
        df = self._load_valuation_month(d.year, d.month)
        slc = df[df["date"] == d]
        if slc.empty:
            raise CacheMissError(
                f"No valuation rows for {d.date()} "
                f"in {self.cache_dir / 'valuation'}. Refresh required."
            )
        return slc.reset_index(drop=True)

    def get_market_cap(self, ts_code: str, date: DateLike) -> float:
        """Return JoinQuant's ``valuation.market_cap`` (亿元) at ``date``.

        Raises:
            CacheMissError: When the (date, code) row is absent.
        """
        snap = self.get_valuation_snapshot(date)
        row = snap[snap["ts_code"] == ts_code]
        if row.empty:
            raise CacheMissError(
                f"No market_cap row for {ts_code} on {_to_ts(date).date()}."
            )
        return float(row.iloc[0]["market_cap"])

    def get_market_cap_batch(self, ts_codes: Iterable[str],
                             date: DateLike) -> pd.Series:
        """Return ``valuation.market_cap`` for many stocks at one date.

        Returns:
            ``pd.Series`` indexed by ts_code. Missing codes are absent
            from the result (caller may reindex if needed).
        """
        snap = self.get_valuation_snapshot(date)
        return snap[snap["ts_code"].isin(list(ts_codes))].set_index("ts_code")["market_cap"]

    # ─── flags (is_st, paused) ───────────────────────────────────────

    @lru_cache(maxsize=64)
    def _load_flags_month(self, year: int, month: int) -> pd.DataFrame:
        path = self.cache_dir / "flags" / f"{year:04d}-{month:02d}.parquet"
        if not path.exists():
            return pd.DataFrame(columns=["date", "ts_code", "is_st", "paused"])
        df = pd.read_parquet(path)
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        return df

    def is_st(self, ts_code: str, date: DateLike) -> bool:
        """Return JoinQuant's ``current_data[s].is_st`` view at ``date``.

        Falls back to ``False`` (not ST) when the row is missing — the
        caller should pair this with the local ``st_stocks.txt`` range
        table for full coverage during cache gaps. Document the fallback
        in any strategy that depends on it.
        """
        d = _to_ts(date)
        df = self._load_flags_month(d.year, d.month)
        row = df[(df["date"] == d) & (df["ts_code"] == ts_code)]
        if row.empty:
            return False
        return bool(row.iloc[0]["is_st"])

    def is_paused(self, ts_code: str, date: DateLike) -> bool:
        """Return JoinQuant's ``current_data[s].paused`` view at ``date``.

        Falls back to ``False`` when the row is missing.
        """
        d = _to_ts(date)
        df = self._load_flags_month(d.year, d.month)
        row = df[(df["date"] == d) & (df["ts_code"] == ts_code)]
        if row.empty:
            return False
        return bool(row.iloc[0]["paused"])
