"""
Qlib Data Feeder for Event-Driven Backtester

Reads market and fundamental data from Qlib, replacing the parquet-based
feeder. This guarantees point-in-time (PIT) correctness for fundamental data
and eliminates historical survivorship bias for index constituents.

All date comparisons use pd.Timestamp internally.
"""

import os
import logging
from typing import Iterable, Optional, Union

import pandas as pd
import qlib
from qlib.data import D
from qlib.config import REG_CN
from src.research_orchestrator.cache_manifest import CacheContext
from src.research_orchestrator.qlib_windowed_features import qlib_windowed_features

logger = logging.getLogger(__name__)


class PreloadCoverageError(RuntimeError):
    """Raised when strict_cache_only is on and a get_features call cache-misses.

    Added in PR 8 fix #2 of the 2026-05-26 freeze plan to close the gap where
    a formal backtest could pass ``assert_preloaded`` pre-loop and still
    silently degrade to per-day D.features fallback mid-loop.
    """


class QlibDataFeeder:
    """Feeds market and fundamental data from Qlib.

    Loads data lazily via Qlib's memory-mapped .bin files.
    Provides PIT-correct features and historical index constituents.

    Args:
        data_dir: Root data directory (e.g., 'e:/量化系统/data').
        qlib_dir: Path to qlib_data. Defaults to data_dir/qlib_data.
        stock_basic_path: Path to stock_basic.parquet.
    """

    def __init__(self, data_dir: str,
                 qlib_dir: Optional[str] = None,
                 stock_basic_path: Optional[str] = None,
                 stage: str = "is_only"):
        """Init.

        ``stage`` is plumbed through to every ``qlib_windowed_features`` call
        the feeder issues so the cache manifest carries the correct stage
        label (Part E, plan ``snappy-buzzing-meerkat`` v5). Callers that do
        not run inside an OOS sealed leg can leave the default ``"is_only"``.
        """
        self.data_dir = data_dir
        self._stage = str(stage) or "is_only"

        # Resolve default paths
        if qlib_dir is None:
            qlib_dir = os.path.normpath(os.path.join(data_dir, 'qlib_data'))
        if stock_basic_path is None:
            stock_basic_path = os.path.normpath(os.path.join(data_dir, 'reference', 'stock_basic.parquet'))

        # Keep Qlib single-process by default on this Windows setup; larger
        # joblib-based query fan-out is currently blocked by pipe permissions.
        qlib.init(provider_uri=qlib_dir, region=REG_CN, kernels=1)
        
        # Load trading calendar from Qlib
        # D.calendar() returns a numpy array of pd.Timestamp
        self._trading_days = pd.Series(D.calendar(start_time="1990-01-01", end_time="2099-12-31"))
        self._td_set = set(self._trading_days)
        self._td_list = self._trading_days.tolist()
        # Build index lookup for prev/next
        self._td_index = {d: i for i, d in enumerate(self._td_list)}

        # Load stock basic info for IPO/delisting and market type
        self._stock_basic = pd.read_parquet(stock_basic_path)
        # Convert list_date and delist_date to Timestamp
        self._stock_basic['list_date'] = pd.to_datetime(
            self._stock_basic['list_date'], format='%Y%m%d', errors='coerce'
        )
        self._stock_basic['delist_date'] = pd.to_datetime(
            self._stock_basic['delist_date'], format='%Y%m%d', errors='coerce'
        )

        self._cache_df: Optional[pd.DataFrame] = None
        self._latest_adj: dict[str, float] = {}

        # Instrumentation (plan ``snappy-buzzing-meerkat`` v5 verification gate).
        # ``preload_status`` is one of: "not_attempted", "success", "raised",
        # "swallowed_exception". ``cache_hit_count`` is incremented every time
        # ``get_features`` returns from the in-memory cache; ``direct_fallback_count``
        # is incremented every time it falls through to the per-day
        # ``qlib_windowed_features`` path. The validation gate requires
        # ``direct_fallback_count == 0`` after the perf fix lands.
        self._preload_status: str = "not_attempted"
        self._preload_wall_seconds: float = 0.0
        self._cache_hit_count: int = 0
        self._direct_fallback_count: int = 0

        # PR 8 fix #2: strict_cache_only mode. When enabled, get_features()
        # raises PreloadCoverageError on the FIRST cache miss instead of
        # silently falling through to the per-day D.features path. Formal
        # runs (BacktestEngine(require_preloaded=True)) flip this on so a
        # mid-loop coverage gap fails loudly rather than producing a
        # backtest that silently used direct fallback data.
        self._strict_cache_only: bool = False
        
    def _to_qlib_code(self, code: str) -> str:
        """Convert '000001.SZ' to '000001_SZ'"""
        if pd.isna(code): return code
        return str(code).replace('.', '_')
        
    def _to_tushare_code(self, qlib_code: str) -> str:
        """Convert '000001_SZ' to '000001.SZ'"""
        if pd.isna(qlib_code): return qlib_code
        return str(qlib_code).replace('_', '.')

    def set_strict_cache_only(self, enabled: bool) -> None:
        """Toggle strict-cache-only mode (PR 8 fix #2).

        When True, :meth:`get_features` raises ``PreloadCoverageError`` on the
        first cache miss instead of falling back to a per-day Qlib query. The
        engine sets this on whenever ``require_preloaded=True`` so formal
        runs fail at the first coverage gap rather than at end-of-run.
        """
        self._strict_cache_only = bool(enabled)

    def preload(self, start: pd.Timestamp, end: pd.Timestamp) -> None:
        """REMOVED in PR 2 of the 2026-05-26 freeze plan.

        The original implementation was a silent no-op that left ``_cache_df``
        as None and forced the engine into a per-day ``D.features`` fallback.
        That produced the ~100x slowdown discovered in plan
        ``snappy-buzzing-meerkat`` v5. Callers MUST use :meth:`preload_features`
        with explicit fields, dates, and ``strict`` flag.

        After PR 2 lands, this raises so any straggling caller is loud.
        """
        raise NotImplementedError(
            "QlibDataFeeder.preload(start, end) was a no-op and has been removed. "
            "Use preload_features(index_name, fields, start_time, end_time, "
            "strict=True) instead. Formal runs should go through "
            "EventDrivenBacktester.run(run_mode='formal', ...) which threads "
            "ENGINE_REQUIRED_FIELDS in automatically."
        )

    def assert_preloaded(
        self,
        *,
        required_fields: Iterable[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        require_zero_fallback: bool = True,
    ) -> None:
        """Hard-fail if the in-memory cache cannot serve [start, end] x required_fields.

        Called by ``BacktestEngine.run()`` when ``require_preloaded=True`` so
        formal runs cannot accidentally degrade into the per-day fallback path.

        Raises:
            RuntimeError: with a precise message naming which gate failed
                (preload never attempted / failed; missing fields; window
                shorter than required; non-zero fallback count).
        """
        if self._preload_status != "success":
            raise RuntimeError(
                f"assert_preloaded: preload_status={self._preload_status!r} "
                "(expected 'success'). Call preload_features(...) with "
                "strict=True before the backtest day loop starts."
            )
        if self._cache_df is None or self._cache_df.empty:
            raise RuntimeError(
                "assert_preloaded: in-memory cache is empty. preload_features "
                "did not populate _cache_df — check the cache-manifest log."
            )

        required = list(required_fields)
        cache_cols = set(self._cache_df.columns)
        missing_fields = [f for f in required if f not in cache_cols]
        if missing_fields:
            raise RuntimeError(
                f"assert_preloaded: missing required fields {missing_fields}. "
                f"Preloaded fields={sorted(cache_cols)!r}, required={required!r}. "
                "Pass the missing fields into preload_features(...) explicitly "
                "or via ENGINE_REQUIRED_FIELDS for the standard set."
            )

        if isinstance(self._cache_df.index, pd.MultiIndex):
            cache_dates = self._cache_df.index.get_level_values("datetime")
        else:
            cache_dates = self._cache_df.index
        cache_min = pd.Timestamp(cache_dates.min())
        cache_max = pd.Timestamp(cache_dates.max())
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        if cache_min > start_ts:
            raise RuntimeError(
                f"assert_preloaded: cache_min={cache_min} > requested start={start_ts}. "
                "Extend preload_features start_time to at least the previous "
                "trading day before backtest start."
            )
        if cache_max < end_ts:
            raise RuntimeError(
                f"assert_preloaded: cache_max={cache_max} < requested end={end_ts}. "
                "Extend preload_features end_time to at least the backtest end."
            )

        if require_zero_fallback and self._direct_fallback_count > 0:
            raise RuntimeError(
                f"assert_preloaded: direct_fallback_count={self._direct_fallback_count} > 0. "
                "The feeder already served fields outside the cache, which "
                "indicates a coverage gap. Re-check fields/dates passed to "
                "preload_features and ensure no get_features call asks for "
                "fields not preloaded."
            )

    def preload_features(self, index_name: str, fields: list[str],
                         start_time: Union[str, pd.Timestamp],
                         end_time: Union[str, pd.Timestamp],
                         strict: bool = False) -> None:
        """Pre-fetch and cache features in memory for faster backtesting.

        Automatically includes ``$adj_factor`` so that the engine can
        compute raw (unadjusted) prices for order execution.

        Args:
            index_name: Qlib instrument pool (e.g. 'all').
            fields: List of Qlib expressions.
            start_time: Start date.
            end_time: End date.
            strict: When True, re-raise on preload failure instead of logging
                an ERROR and silently falling through to per-day ``D.features``
                queries. Formal validation handlers must pass ``strict=True``
                so a cache-manifest collision becomes loud rather than a
                100x runtime regression. Plan ``snappy-buzzing-meerkat`` v5
                Phase 2.a.
        """
        # Always include $adj_factor for raw-price computation
        all_fields = list(dict.fromkeys(fields + ['$adj_factor']))

        start_str = pd.Timestamp(start_time).strftime('%Y-%m-%d')
        end_str = pd.Timestamp(end_time).strftime('%Y-%m-%d')
        logger.info(
            "Preloading features for %s from %s to %s (stage=%s, strict=%s)...",
            index_name, start_str, end_str, self._stage, strict,
        )

        import time as _time
        _t0 = _time.perf_counter()
        try:
            qlib_instruments = D.instruments(market=index_name)
            df = qlib_windowed_features(
                instruments=qlib_instruments,
                fields=all_fields,
                start_time=start_str,
                end_time=end_str,
                cache_context=CacheContext(),
                stage=self._stage,
            )
            if not df.empty and isinstance(df.index, pd.MultiIndex):
                new_index = df.index.set_levels(
                    [self._to_tushare_code(c) for c in df.index.levels[0]], level='instrument'
                )
                df.index = new_index
                df.sort_index(inplace=True)

            self._cache_df = df
            self._latest_adj = self._build_latest_adj_factors(df)
            self._preload_status = "success"
            logger.info(f"Preloaded cache dataset shape: {df.shape}")
            logger.info(f"Latest adj_factors computed for {len(self._latest_adj)} stocks")
        except Exception as e:
            logger.error(f"Failed to preload Qlib features: {e}")
            if strict:
                self._preload_status = "raised"
                self._preload_wall_seconds = _time.perf_counter() - _t0
                raise
            self._preload_status = "swallowed_exception"
        finally:
            if self._preload_wall_seconds == 0.0:
                self._preload_wall_seconds = _time.perf_counter() - _t0

    def get_features(self, instruments: list[str], fields: list[str], 
                     start_time: pd.Timestamp, end_time: pd.Timestamp,
                     freq: str = 'day') -> pd.DataFrame:
        """Get PIT-correct features from Qlib.
        
        Args:
            instruments: List of Tushare codes (e.g., '000001.SZ').
            fields: List of Qlib expressions (e.g., ['$close', '$n_income_attr_p']).
            start_time: Start date.
            end_time: End date.
            
        Returns:
            DataFrame with multi-index (instrument, datetime).
            Instruments are returned as Tushare codes. If empty, returns empty DataFrame.
        """
        if not instruments:
            return pd.DataFrame()
            
        start_ts = pd.Timestamp(start_time)
        end_ts = pd.Timestamp(end_time)
        
        # Check cache first
        if self._cache_df is not None:
            missing_fields = [f for f in fields if f not in self._cache_df.columns]
            if not missing_fields:
                try:
                    idx = pd.IndexSlice
                    # Intersect available instruments to avoid KeyError
                    avail_inst = list(set(instruments).intersection(self._cache_df.index.levels[0]))
                    if avail_inst:
                        sliced = self._cache_df.loc[idx[avail_inst, start_ts:end_ts], fields]
                        if sliced.empty:
                            logger.error(
                                "CACHE MISS: slice is empty for %s to %s. "
                                "Available dates: %s ... %s",
                                start_ts,
                                end_ts,
                                self._cache_df.index.levels[1].unique().tolist()[:5],
                                self._cache_df.index.levels[1].unique().tolist()[-5:],
                            )
                        # Instrumentation: cache hit path (fast path).
                        self._cache_hit_count += 1
                        return sliced.copy()
                    # Empty intersection still counts as cache-hit path
                    # (no fallback to D.features fired) — the caller asked
                    # for instruments not in the cache, which is normal.
                    self._cache_hit_count += 1
                    return pd.DataFrame()
                except Exception as e:
                    logger.warning(f"Cache slice failed, falling back to D.features: {e}")
            else:
                logger.debug(f"Cache miss for fields {missing_fields}, fetching from Qlib.")

        # PR 8 fix #2: strict_cache_only mode short-circuits the fallback.
        # Without this, a formal run could silently degrade DURING the day
        # loop even though the pre-loop assert_preloaded passed.
        if self._strict_cache_only:
            raise PreloadCoverageError(
                "Strict cache-only mode is enabled but a cache miss occurred. "
                f"Requested fields={list(fields)} for instruments[0:3]="
                f"{list(instruments)[:3]} over {start_ts}..{end_ts}. "
                "Preload these fields explicitly before the day loop, or "
                "disable strict_cache_only for sandbox runs."
            )

        # Fallback to direct D.features query
        # Instrumentation: increment fallback counter — the validation gate
        # requires this stays at 0 after the perf fix lands.
        self._direct_fallback_count += 1
        qlib_instruments = [self._to_qlib_code(c) for c in instruments]

        try:
            start_str = start_ts.strftime('%Y-%m-%d')
            end_str = end_ts.strftime('%Y-%m-%d')
            # Workaround Qlib DatasetD.dataset signature bug by using explicit kwargs
            df = qlib_windowed_features(
                instruments=qlib_instruments,
                fields=fields,
                start_time=start_str,
                end_time=end_str,
                cache_context=CacheContext(),
                stage=self._stage,
            )
        except Exception as e:
            logger.error(f"Error fetching Qlib features: {e}")
            return pd.DataFrame()
            
        # Convert Qlib codes back to Tushare codes in index
        if not df.empty and isinstance(df.index, pd.MultiIndex):
            new_index = df.index.set_levels(
                [self._to_tushare_code(c) for c in df.index.levels[0]], level='instrument'
            )
            df.index = new_index
            
        return df

    def _build_latest_adj_factors(self, df: pd.DataFrame) -> dict[str, float]:
        """Extract the latest (most recent) adj_factor per stock.

        The latest adj_factor is needed to reverse Qlib's forward
        adjustment:  ``raw_price = adjusted_price * latest_adj / adj_on_date``.

        Args:
            df: Preloaded cache DataFrame with MultiIndex (instrument, datetime)
                and ``$adj_factor`` column.

        Returns:
            Dict ``{ts_code: latest_adj_factor}``.
        """
        if '$adj_factor' not in df.columns or df.empty:
            return {}

        latest = {}
        for code in df.index.get_level_values('instrument').unique():
            sub = df.loc[code, '$adj_factor'].dropna()
            if not sub.empty:
                latest[code] = float(sub.iloc[-1])
        return latest

    def get_latest_adj_factors(self) -> dict[str, float]:
        """Return latest adj_factor per stock for raw-price computation.

        The engine uses this to convert forward-adjusted Qlib prices
        back to actual trading prices:

            ``raw_price = adjusted_price * (latest_adj / adj_factor_on_date)``

        Returns:
            Dict ``{ts_code: latest_adj_factor}``.  Empty dict if
            ``preload_features()`` was not called or ``$adj_factor``
            was unavailable.
        """
        return self._latest_adj

    def get_index_constituents(self, index_name: str, date: pd.Timestamp) -> list[str]:
        """Gets point-in-time index members to prevent survivorship bias.
        
        Args:
            index_name: Qlib instrument pool name (e.g., 'csi500', 'csi300', 'all').
            date: Point-in-time date.
            
        Returns:
            List of Tushare codes.
        """
        try:
            qlib_instruments = D.instruments(market=index_name)
            # D.list_instruments returns dict of {code: [[start, end], [start, end]]} valid on date
            valid_dict = D.list_instruments(instruments=qlib_instruments, start_time=date, end_time=date, as_list=True)
            if isinstance(valid_dict, list):
                codes = valid_dict
            else:
                codes = list(valid_dict.keys())
            return [self._to_tushare_code(c) for c in codes]
        except Exception as e:
            logger.error(f"Error getting index constituents for {index_name} on {date}: {e}")
            return []

    def get_trading_calendar(self, start: str, end: str) -> list[pd.Timestamp]:
        """Get list of trading days in [start, end] range."""
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        mask = (self._trading_days >= start_ts) & (self._trading_days <= end_ts)
        return self._trading_days[mask].tolist()

    def get_stock_basic(self) -> pd.DataFrame:
        """Get the full stock_basic reference table."""
        return self._stock_basic

    def get_prev_trading_day(self, date: pd.Timestamp) -> Optional[pd.Timestamp]:
        """Get the previous trading day before the given date."""
        idx = self._td_index.get(date)
        if idx is not None and idx > 0:
            return self._td_list[idx - 1]
        
        # Date not in calendar — find nearest before
        for d in reversed(self._td_list):
            if d < date:
                return d
        return None

    def get_next_trading_day(self, date: pd.Timestamp) -> Optional[pd.Timestamp]:
        """Get the next trading day after the given date."""
        idx = self._td_index.get(date)
        if idx is not None and idx < len(self._td_list) - 1:
            return self._td_list[idx + 1]
            
        # Date not in calendar — find nearest after
        for d in self._td_list:
            if d > date:
                return d
        return None

    def is_trading_day(self, date: pd.Timestamp) -> bool:
        """Check if a date is a trading day."""
        return date in self._td_set

    def count_trading_days(self, start: pd.Timestamp, end: pd.Timestamp) -> int:
        """Count trading days between start and end (inclusive)."""
        return sum(1 for d in self._td_list if start <= d <= end)
