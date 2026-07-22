"""
Daily Data Updater
Fetches the latest market data, checks for new quarterly fundamental
announcements, and optionally refreshes index weights, then triggers
Qlib binary conversion.

This script is designed to run daily after market close (e.g., 18:00 CST).
By default, it updates both daily market data AND checks for new quarterly
fundamental announcements. Use --skip-fundamentals to skip the latter.

Usage:
    python src/data_infra/pipeline/update_daily_data.py
    python src/data_infra/pipeline/update_daily_data.py --date 20260303
    python src/data_infra/pipeline/update_daily_data.py --skip-fundamentals
    python src/data_infra/pipeline/update_daily_data.py --rebuild-qlib
"""
import sys
import os
import argparse
import logging
import re
import tempfile
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
import pandas as pd
import glob
from tqdm import tqdm

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..', '..', '..'))
sys.path.append(os.path.join(project_root, 'src'))

from data_infra.daily_merge import DailyMergeError, merge_daily_legs
from data_infra.fetchers import TushareFetcher
from data_infra.pipeline.build_qlib_backend import _resolve_paths, build_unified_qlib
from data_infra.storage import StorageManager

# Set up logging with RotatingFileHandler
log_dir = os.path.join(project_root, 'logs')
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            os.path.join(log_dir, f'update_daily_data_{datetime.now().strftime("%Y%m")}.log'),
            maxBytes=10*1024*1024,
            backupCount=5
        ),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Major indices whose weights we track
TRACKED_INDICES = [
    '000001.SH', '000300.SH', '000905.SH', '000852.SH',
    '399001.SZ', '399006.SZ', '000688.SH'
]

TARGET_INDEX_NAMES = {
    '000001.SH': '上证指数', '000300.SH': '沪深300', '000905.SH': '中证500',
    '000852.SH': '中证1000', '399001.SZ': '深证成指', '399006.SZ': '创业板指',
    '000688.SH': '科创50'
}


EXPECTED_EMPTY_DATE_FILES = {
    "moneyflow": "moneyflow_known_empty_dates.txt",
    "northbound": "northbound_nonconnect_days.txt",
}


class MarketDataError(RuntimeError):
    """A PRESENT trading session is incomplete/invalid for a required field (adj_factor is
    ENGINE-required; daily_basic required) — raised by update_market_data so an incomplete session can
    NEVER be silently committed and NEVER read back as success via an optional side channel (GPT 5-C
    Blocker 3). The prior daily file is preserved (the validated write is atomic temp+replace)."""


# canonical daily raw fields the engine needs from the `daily` endpoint (up_limit/down_limit come from
# stk_limit, adj_factor from fetch_adj_factor — validated separately). A session missing any of these is
# NOT complete just because "some OHLCV exists" (GPT REWORK-5 M1).
DAILY_REQUIRED_COLS = ("ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount", "pre_close")


def _validate_endpoint_frame(df, *, name: str, target_date: str, required_cols, key_cols=("ts_code", "trade_date")):
    """One shared required-frame validator (GPT REWORK-5 M1): schema (required columns present), TARGET
    DATE (every trade_date == target_date — a wrong-date frame merged all-null before), and natural-key
    UNIQUENESS (duplicate keys wrote duplicate output). Raises MarketDataError; never coerces."""
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise MarketDataError(f"market {target_date}: {name} missing required columns {missing}")
    if "trade_date" in df.columns:
        td = df["trade_date"].astype(str).str.replace("-", "", regex=False)
        stray = sorted(set(td) - {target_date})
        if stray:
            raise MarketDataError(f"market {target_date}: {name} carries other trade_dates {stray[:3]} "
                                  f"(stale/mispartitioned response)")
    if all(k in df.columns for k in key_cols) and df.duplicated(subset=list(key_cols)).any():
        raise MarketDataError(f"market {target_date}: {name} has duplicate {tuple(key_cols)} keys")


class DailyDataUpdater:
    """
    Daily incremental updater for market data, fundamentals, and index weights.

    On each run:
    1. Updates reference data (stock_basic, trade_cal) for new IPOs/delistings
    2. Checks if the target date is a trading day
    3. Fetches and merges daily OHLCV + valuation + adj_factor data
    4. Checks for newly-announced quarterly financials (income, balance sheet, indicators)
    5. Checks if current month's index weights need updating
    6. Triggers Qlib binary conversion

    Args:
        config_path: Path to config.yaml.
        data_root: Override data root. Defaults to config value.
    """

    def __init__(self, config_path: str, data_root: str = None):
        # P1-3: base_sleep=1.5 matches the fetcher default and complies with
        # CLAUDE.md §6.1 "Tushare Safety" ("default base_sleep=1.5 should not
        # be reduced without evidence"). Previously this was 1.0 without any
        # documented evidence for the reduction.
        self.fetcher = TushareFetcher(config_path=config_path, max_retries=5, base_sleep=1.5)
        self.storage = StorageManager(data_root=data_root)

        self.data_dir = self.storage.data_root
        self.market_daily_dir = os.path.join(self.data_dir, 'market', 'daily')
        self.index_dir = os.path.join(self.data_dir, 'market', 'index')
        self.ref_dir = os.path.join(self.data_dir, 'reference')

    def update_for_date(self, target_date: str, skip_fundamentals: bool = False, skip_phase3: bool = False):
        """
        Fetch all data for a single day and append/save.

        Args:
            target_date: Date string in YYYYMMDD format.
            skip_fundamentals: If True, skip the Phase 2 quarterly fundamentals check.
            skip_phase3: If True, skip Phase 3 periodic and daily refreshes.

        Returns:
            dict: Status summary including touched symbols and datasets.
        """
        logger.info(f"{'='*50}")
        logger.info(f"  Daily Update for {target_date}")
        logger.info(f"{'='*50}")

        # 1. Update Reference Data (stock_basic, trade_cal)
        self.update_reference_data(target_date)

        # 2. Trading-day membership (GPT M2). trade_cal is fetched with is_open='1', so it holds ONLY
        # open days — a closed date is ABSENT (not present with is_open==0). Absence WITHIN calendar
        # coverage = non-trading (legit skip, exit 0); a date BEYOND coverage = insufficient calendar
        # (an error, not a silent skip).
        trade_cal_path = os.path.join(self.ref_dir, "trade_cal.parquet")
        if os.path.exists(trade_cal_path):
            cal = pd.read_parquet(trade_cal_path)
            dates = cal['cal_date'].astype(str)
            open_days = set(dates[cal['is_open'] == 1]) if 'is_open' in cal.columns else set(dates)
            if target_date not in open_days:
                covered = not dates.empty and dates.min() <= target_date <= dates.max()
                if covered:
                    logger.info(f"{target_date} is not a trading day. Skipping market data.")
                    return {
                        "market_ok": False, "is_trading_day": False,  # legit skip -> exit 0
                        "touched_symbols": set(),
                        "affected_datasets": {"stock_basic", "trade_cal"},
                        # a reference-refresh failure is still surfaced even on a closed date (M2)
                        "errors": [self._reference_error] if getattr(self, '_reference_error', None) else [],
                    }
                logger.error("%s is BEYOND trade_cal coverage [%s..%s] — insufficient calendar",
                             target_date, dates.min() if not dates.empty else "?",
                             dates.max() if not dates.empty else "?")
                return {
                    "market_ok": False, "is_trading_day": True,  # unknown -> fail (M1 exit-code)
                    "touched_symbols": set(), "affected_datasets": set(),
                    "errors": [f"{target_date} beyond trade_cal coverage — refresh the calendar"],
                }

        # 3. Update Daily Market Data. A required-field failure RAISES MarketDataError (non-ignorable,
        # no side channel) — capture it into the errors so market_ok is False + the session is incomplete.
        market_error = None
        try:
            market_symbols = self.update_market_data(target_date)
        except MarketDataError as exc:
            market_symbols = set()
            market_error = str(exc)
            logger.error(market_error)
        market_ok = bool(market_symbols) and market_error is None

        # 4. Update Indices
        self.update_index_data(target_date)
        affected_datasets = {"stock_basic", "trade_cal", "index_daily"}
        if market_ok:
            affected_datasets.add("daily")

        # 5. Check for new quarterly fundamentals (always-on by default)
        fundamental_symbols = set()
        fundamental_datasets = set()
        if not skip_fundamentals:
            fundamental_symbols, fundamental_datasets = self.update_fundamentals(target_date)
            affected_datasets.update(fundamental_datasets)

        self._suspend_error = None
        phase3_symbols = set()
        if not skip_phase3:
            if market_ok:
                phase3_daily_symbols, phase3_daily_datasets = self.update_phase3_daily_market(target_date)
                phase3_symbols.update(phase3_daily_symbols)
                affected_datasets.update(phase3_daily_datasets)
            phase3_periodic_symbols, phase3_periodic_datasets = self.update_phase3_periodic(target_date)
            phase3_symbols.update(phase3_periodic_symbols)
            affected_datasets.update(phase3_periodic_datasets)

        # 6. Check for current month's index weights
        if self.update_index_weights(target_date):
            affected_datasets.add("index_weights")

        errors = []
        if getattr(self, '_reference_error', None):
            errors.append(self._reference_error)
        if market_error:  # required-field incomplete (adj_factor/daily_basic) — typed, non-ignorable (B3)
            errors.append(market_error)
        elif not market_ok:
            errors.append(f"daily market data missing for trading day {target_date}")
        if self._suspend_error:
            errors.append(self._suspend_error)
        errors.extend(getattr(self, '_phase3_errors', []))  # required moneyflow/stk_limit failures
        return {
            "market_ok": market_ok,
            "is_trading_day": True,
            "touched_symbols": set(market_symbols) | set(fundamental_symbols) | set(phase3_symbols),
            "affected_datasets": affected_datasets,
            "errors": errors,
        }

    def _expected_empty_dates(self, dataset_name: str) -> set[str]:
        reference_file = EXPECTED_EMPTY_DATE_FILES.get(dataset_name)
        if reference_file is None:
            return set()
        path = os.path.join(self.ref_dir, reference_file)
        if not os.path.exists(path):
            return set()
        with open(path, "r", encoding="utf-8") as handle:
            return {line.strip() for line in handle if line.strip() and not line.lstrip().startswith('#')}

    def update_reference_data(self, target_date: str):
        """Update stock_basic and trade_cal for new IPOs/delistings. trade_cal is fetched a FORWARD
        horizon and MERGED by (exchange, cal_date) — NEVER a target-bounded overwrite, which would
        truncate the future-aware calendar the selector + QA depend on and freeze the job on its first
        run (GPT B1). The merge is dtype-normalized + column-validated so a mixed int/string cal_date
        can't crash the sort (previously swallowed, leaving a stale calendar — GPT M4), and written
        via a unique temp + atomic replace. A failure is surfaced to the exit contract (GPT M2)."""
        self._reference_error = None
        logger.info("Updating reference data...")
        try:
            df_basic = self.fetcher.fetch_stock_basic()
            if df_basic.empty:  # an empty ground-truth response is an ERROR, not a successful no-op
                raise ValueError("stock_basic fetch returned EMPTY")
            _atomic_write_parquet(df_basic, os.path.join(self.ref_dir, "stock_basic.parquet"))

            horizon_end = f"{int(target_date[:4]) + 1}1231"  # always extend past today
            df_cal = self.fetcher.fetch_trade_cal(end_date=horizon_end)
            if df_cal.empty:
                raise ValueError("trade_cal fetch returned EMPTY")
            cal_path = os.path.join(self.ref_dir, "trade_cal.parquet")
            df_cal = _validate_trade_cal(df_cal, fresh=True)
            if os.path.exists(cal_path):
                old = _validate_trade_cal(pd.read_parquet(cal_path), fresh=False)
                df_cal = (pd.concat([old, df_cal], ignore_index=True)
                          .drop_duplicates(subset=["exchange", "cal_date"], keep="last"))
            df_cal = df_cal.sort_values(["exchange", "cal_date"]).reset_index(drop=True)
            df_cal = _validate_trade_cal(df_cal, fresh=False)  # revalidate the MERGED result (continuity)
            _atomic_write_parquet(df_cal, cal_path)
        except Exception as e:
            logger.error(f"Error updating reference data: {e}")
            self._reference_error = f"reference data update failed: {e}"

    def update_index_data(self, target_date: str):
        """Update major index daily data for the target date."""
        for ts_code, name in tqdm(
            TARGET_INDEX_NAMES.items(),
            total=len(TARGET_INDEX_NAMES),
            desc=f"Index daily {target_date}",
            unit="index",
            dynamic_ncols=True,
            leave=False,
        ):
            try:
                df_new = self.fetcher.fetch_index_daily(
                    ts_code=ts_code, start_date=target_date, end_date=target_date
                )
                if df_new.empty:
                    continue

                file_path = os.path.join(self.index_dir, f"index_{ts_code}.parquet")
                if os.path.exists(file_path):
                    df_old = pd.read_parquet(file_path)
                    df_old = df_old[df_old['trade_date'] != target_date]
                    df_combined = pd.concat([df_old, df_new], ignore_index=True)
                    df_combined.to_parquet(file_path, index=False)
                else:
                    df_new.to_parquet(file_path, index=False)
            except Exception as e:
                logger.error(f"Error updating index {name}: {e}")

    def update_market_data(self, target_date: str):
        """Fetch + merge daily OHLCV + valuation + adj_factor for `target_date`, VALIDATING every
        required field BEFORE committing.

        Returns set[str] of ts_codes on success. Returns an EMPTY set when the daily endpoint itself is
        empty (vendor not ready / non-trading — the caller decides via is_trading_day). RAISES
        MarketDataError — and does NOT write the file, preserving the prior — when a PRESENT session is
        incomplete/invalid: wrong trade_date, duplicate keys, or adj_factor (ENGINE-required) /
        daily_basic below coverage, or post-merge adj_factor non-null coverage below floor. There is NO
        `_market_error` side channel — an incomplete session cannot be read back as success (GPT B3)."""
        logger.info(f"Fetching market data for {target_date}...")

        df_daily = self.fetcher.fetch_daily_data(trade_date=target_date)
        if df_daily.empty:
            logger.warning(f"No daily market data for {target_date}. API may not be updated yet.")
            return set()

        # full daily schema + target-date + key uniqueness BEFORE anything commits (GPT REWORK-5 M1: a
        # daily frame omitting open/high/low/vol/amount/pre_close is NOT a complete session).
        _validate_endpoint_frame(df_daily, name="daily", target_date=target_date,
                                 required_cols=DAILY_REQUIRED_COLS)

        df_basic = self.fetcher.fetch_fundamentals(trade_date=target_date)
        df_adj = self.fetcher.fetch_adj_factor(trade_date=target_date)

        # adj_factor (ENGINE-required) + daily_basic (required): validate schema/date/keys, then coverage.
        if df_adj.empty:
            raise MarketDataError(f"market {target_date}: adj_factor EMPTY (required field)")
        if df_basic.empty:
            raise MarketDataError(f"market {target_date}: daily_basic EMPTY (required field)")
        _validate_endpoint_frame(df_adj, name="adj_factor", target_date=target_date,
                                 required_cols=("ts_code", "trade_date", "adj_factor"))
        _validate_endpoint_frame(df_basic, name="daily_basic", target_date=target_date,
                                 required_cols=("ts_code", "trade_date"))

        # The 3-leg merge + every pre/post-merge invariant lives in ONE canonical function that the
        # raw-store recovery calls too, so recovered history and live history cannot drift apart
        # (adapter design v4, F9). Consolidating the two implementations strengthened BOTH sides — see
        # daily_merge.py's module docstring for what each was missing.
        try:
            df_merged = merge_daily_legs(df_daily, df_basic, df_adj, target_date)
        except DailyMergeError as exc:
            raise MarketDataError(str(exc)) from exc

        file_path = os.path.join(self.market_daily_dir, target_date[:4], f"daily_{target_date}.parquet")
        _atomic_write_parquet(df_merged, file_path)  # validated -> atomic temp+replace (prior preserved)
        logger.info(f"Saved daily data ({len(df_merged)} stocks) to {file_path}")
        return set(df_merged['ts_code'].dropna().astype(str).tolist())

    def update_fundamentals(self, target_date: str):
        """
        Check for newly-announced quarterly financials since the last sync.

        Uses the target_date as the announcement date filter to fetch only
        reports that were published on or near this date.
        This is lightweight — typically only a handful of stocks announce
        on any given day outside of earnings season.
        """
        logger.info("Checking for new quarterly fundamental announcements...")

        # Determine date range to check: last 7 days (to catch weekend announcements)
        from datetime import datetime, timedelta
        target_dt = datetime.strptime(target_date, '%Y%m%d')
        lookback_date = (target_dt - timedelta(days=7)).strftime('%Y%m%d')

        categories = [
            ('income', lambda **kwargs: self.fetcher.fetch_income_vip(report_type='1', **kwargs), 'income'),
            ('income_quarterly', self.fetcher.fetch_income_quarterly_vip, 'income_quarterly'),
            ('balancesheet', lambda **kwargs: self.fetcher.fetch_balancesheet_vip(report_type='1', **kwargs), 'balancesheet'),
            ('indicators', self.fetcher.fetch_fina_indicator_vip, 'indicators'),
        ]

        total_new_records = 0
        touched_symbols = set()
        affected_datasets = set()

        for name, fetch_func, storage_cat in tqdm(
            categories,
            total=len(categories),
            desc=f"Phase 2 PIT {target_date}",
            unit="dataset",
            dynamic_ncols=True,
            leave=False,
        ):
            try:
                # Fetch announcements from the lookback window
                df = fetch_func(start_date=lookback_date, end_date=target_date)
                if not df.empty:
                    df_clean = df.dropna(how='all', axis=1)
                    self.storage.insert_fundamental_data(df_clean, storage_cat)
                    total_new_records += len(df_clean)
                    touched_symbols.update(df_clean['ts_code'].dropna().astype(str).tolist())
                    affected_datasets.add(storage_cat)
                    logger.info(f"  {name}: {len(df_clean)} new rows")
            except Exception as e:
                logger.error(f"Error fetching {name} announcements: {e}")

        if total_new_records > 0:
            logger.info(f"Fundamentals sync complete: {total_new_records} total new records")
        else:
            logger.info("No new fundamental announcements found.")

        return touched_symbols, affected_datasets

    def update_phase3_periodic(self, target_date: str):
        """Fetch Phase 3 periodic/event disclosures from the recent announcement window."""
        logger.info("Checking for Phase 3 PIT datasets...")

        target_dt = datetime.strptime(target_date, '%Y%m%d')
        lookback_date = (target_dt - timedelta(days=7)).strftime('%Y%m%d')
        periodic_categories = [
            ("cashflow", lambda **kwargs: self.fetcher.fetch_cashflow_vip(report_type='1', **kwargs), self.storage.insert_fundamental_data, "cashflow"),
            ("cashflow_quarterly", self.fetcher.fetch_cashflow_quarterly_vip, self.storage.insert_fundamental_data, "cashflow_quarterly"),
            ("holder_number", self.fetcher.fetch_stk_holdernumber, self.storage.insert_corporate_data, "holder_number"),
        ]

        total_new_records = 0
        touched_symbols = set()
        affected_datasets = set()

        for name, fetch_func, insert_func, storage_cat in tqdm(
            periodic_categories,
            total=len(periodic_categories),
            desc=f"Phase 3 PIT {target_date}",
            unit="dataset",
            dynamic_ncols=True,
            leave=False,
        ):
            try:
                df = fetch_func(start_date=lookback_date, end_date=target_date)
                if df.empty:
                    continue
                df_clean = df.dropna(how='all', axis=1)
                insert_func(df_clean, storage_cat)
                total_new_records += len(df_clean)
                touched_symbols.update(df_clean['ts_code'].dropna().astype(str).tolist())
                affected_datasets.add(name)
                logger.info("  %s: %d new rows", name, len(df_clean))
            except Exception as e:
                logger.error("Error fetching %s announcements: %s", name, e)

        forecast_frames = []
        ann_dates = pd.date_range(start=lookback_date, end=target_date, freq='D')
        for ann_date in tqdm(
            ann_dates,
            total=len(ann_dates),
            desc=f"Forecast dates {target_date}",
            unit="day",
            dynamic_ncols=True,
            leave=False,
        ):
            ann_date_str = ann_date.strftime('%Y%m%d')
            try:
                df = self.fetcher.fetch_forecast(ann_date=ann_date_str)
                if not df.empty:
                    forecast_frames.append(df.dropna(how='all', axis=1))
            except Exception as e:
                logger.error("Error fetching forecast announcements for %s: %s", ann_date_str, e)

        if forecast_frames:
            forecast_df = pd.concat(forecast_frames, ignore_index=True).drop_duplicates()
            self.storage.insert_fundamental_data(forecast_df, "forecast")
            total_new_records += len(forecast_df)
            touched_symbols.update(forecast_df['ts_code'].dropna().astype(str).tolist())
            affected_datasets.add("forecast")
            logger.info("  forecast: %d new rows", len(forecast_df))

        if total_new_records > 0:
            logger.info("Phase 3 PIT sync complete: %d total new records", total_new_records)
        else:
            logger.info("No new Phase 3 PIT announcements found.")

        return touched_symbols, affected_datasets

    # Phase-3 endpoints whose ABSENCE on a trading day is a deployment-relevant failure (surfaced to
    # the exit contract, GPT M2). The event-like ones (top_list/top_inst/block_trade) + northbound
    # (partial/declining coverage) are legitimately sparse and are NOT required.
    REQUIRED_PHASE3 = {"moneyflow", "stk_limit"}

    def update_phase3_daily_market(self, target_date: str):
        """Fetch Phase 3 daily market datasets for the target trade date."""
        logger.info("Fetching Phase 3 daily market data for %s...", target_date)
        self._phase3_errors = []

        categories = [
            ("moneyflow", self.fetcher.fetch_moneyflow),
            ("northbound", self.fetcher.fetch_hk_hold),
            ("margin", self.fetcher.fetch_margin_detail),
            ("stk_limit", self.fetcher.fetch_stk_limit),
            # New alpha endpoints (added 2026-04-14)
            ("top_list", self.fetcher.fetch_top_list),
            ("top_inst", self.fetcher.fetch_top_inst),
            ("block_trade", self.fetcher.fetch_block_trade),
        ]
        touched_symbols = set()
        affected_datasets = set()

        for name, fetch_func in tqdm(
            categories,
            total=len(categories),
            desc=f"Phase 3 daily {target_date}",
            unit="dataset",
            dynamic_ncols=True,
            leave=False,
        ):
            try:
                df = fetch_func(trade_date=target_date)
                if not df.empty:
                    df_clean = df.dropna(how='all', axis=1)
                    self.storage.insert_market_data(df_clean, name)
                    if 'ts_code' in df_clean.columns:
                        touched_symbols.update(df_clean['ts_code'].dropna().astype(str).tolist())
                    affected_datasets.add(name)
                    logger.info("  %s: %d new rows", name, len(df_clean))
                    continue

                if target_date in self._expected_empty_dates(name):
                    affected_datasets.add(name)
                    logger.info("  %s: expected source-empty date %s", name, target_date)
                else:
                    logger.info("  %s: no rows returned for %s", name, target_date)
                    if name in self.REQUIRED_PHASE3:
                        self._phase3_errors.append(f"{name} empty for trading day {target_date}")
            except Exception as e:
                logger.error("Error fetching %s for %s: %s", name, target_date, e)
                if name in self.REQUIRED_PHASE3:
                    self._phase3_errors.append(f"{name} failed for {target_date}: {e}")

        # suspend_d (Phase 5-C/C2): a complete same-date snapshot, stored via ATOMIC OVERWRITE (not
        # the merge path) so it preserves suspend_timing — load-bearing for the monthly-bump
        # full-day-vs-intraday daily-completeness proof (Phase 5-B). Cheap, per trade_date.
        try:
            susp = self.write_suspend_d(target_date)
            affected_datasets.add("suspend_d")
            logger.info("  suspend_d: %d rows (timing=%s)", susp["suspend_rows"], susp["suspend_timing_present"])
        except Exception as e:
            logger.error("Error fetching suspend_d for %s: %s", target_date, e)
            self._suspend_error = f"suspend_d {target_date}: {e}"  # surfaced to the M1 exit code

        return touched_symbols, affected_datasets

    def write_suspend_d(self, target_date: str) -> dict:
        """Fetch + store suspend_d(target_date) as a complete same-date snapshot via ATOMIC OVERWRITE
        (not insert_market_data's merge, which would duplicate rows + drop suspend_timing on a schema
        change). suspend_timing distinguishes a full-day suspension from an intraday halt — the
        monthly-bump daily-completeness proof (Phase 5-B) fails closed without it. Cheap, per date.

        VALIDATES before replacing a valid snapshot (GPT M3): a nonempty response must carry all four
        columns AND every row's trade_date == target_date; otherwise RAISE (preserving the prior
        snapshot) — never silently overwrite with malformed/wrong-date data. Uses a UNIQUE temp file
        (a fixed .tmp would collide with an overlapping monthly job) + atomic replace."""
        df = self.fetcher.fetch_suspend_d(trade_date=target_date)
        year_dir = os.path.join(self.data_dir, 'market', 'suspend_d', target_date[:4])
        os.makedirs(year_dir, exist_ok=True)
        path = os.path.join(year_dir, f"suspend_d_{target_date}.parquet")
        if not df.empty:
            missing = {'ts_code', 'trade_date', 'suspend_type', 'suspend_timing'} - set(df.columns)
            if missing:
                raise ValueError(f"suspend_d {target_date}: response missing columns {sorted(missing)} "
                                 "— prior snapshot preserved")
            td = set(df['trade_date'].astype(str).str.replace('-', '', regex=False).unique())
            if td != {target_date}:
                raise ValueError(f"suspend_d {target_date}: response carries other trade_dates "
                                 f"{sorted(td)[:5]} — prior snapshot preserved")
            out = df[['ts_code', 'trade_date', 'suspend_type', 'suspend_timing']]
        else:
            out = pd.DataFrame(columns=['ts_code', 'trade_date', 'suspend_type', 'suspend_timing'])
        fd, tmp = tempfile.mkstemp(dir=year_dir, prefix=f".suspend_d_{target_date}_", suffix=".tmp")
        os.close(fd)
        try:
            out.to_parquet(tmp, index=False)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        return {"suspend_rows": int(len(df)), "suspend_timing_present": True}

    def update_index_weights(self, target_date: str):
        """
        Check if current month's index weights have already been fetched.
        If not, fetch and save them.
        """
        current_month = target_date[:6]  # YYYYMM
        weights_dir = os.path.join(self.data_dir, 'universe', 'index_weights')

        # Check if this month's weights already exist
        expected_file = os.path.join(weights_dir, f"index_weights_{current_month}.parquet")
        if os.path.exists(expected_file):
            return False  # Already fetched this month

        logger.info(f"Fetching index weights for month {current_month}...")
        start_d = f"{current_month}01"
        end_d = target_date

        for idx_code in tqdm(
            TRACKED_INDICES,
            total=len(TRACKED_INDICES),
            desc=f"Index weights {current_month}",
            unit="index",
            dynamic_ncols=True,
            leave=False,
        ):
            try:
                w_df = self.fetcher.fetch_index_weight(
                    index_code=idx_code, start_date=start_d, end_date=end_d
                )
                if not w_df.empty:
                    self.storage.insert_universe_data(w_df, "index_weights")
                    logger.info(f"  {idx_code}: {len(w_df)} weight records")
            except Exception as e:
                logger.error(f"Error fetching weights for {idx_code}: {e}")
        return True


def _live_calendar_policy_id(qlib_dir: str) -> str:
    """Read the calendar_policy_id RECORDED by the live provider manifest.

    A daily update republishes the same provider under the same policy — the
    manifest is the artifact-recorded source (UNFREEZE_PLAN.md D1: publish
    requires an explicit policy id; the live manifest's own record is the
    correct one for an in-place refresh, never a module default).
    """
    from data_infra.provider_manifest import load_provider_manifest

    return load_provider_manifest(qlib_dir).calendar_policy_id


def trigger_qlib_rebuild():
    """Trigger the full Qlib backend rebuild via build_qlib_backend.py."""
    logger.info("Triggering full Qlib backend rebuild...")
    data_root, qlib_dir = _resolve_paths()
    build_unified_qlib(
        data_root, qlib_dir, mode="all", publish=True,
        calendar_policy_id=_live_calendar_policy_id(qlib_dir),
    )


def trigger_qlib_incremental(touched_symbols=None, affected_datasets=None):
    """Trigger staged incremental Qlib update for touched symbols."""
    logger.info("Triggering incremental Qlib update...")
    data_root, qlib_dir = _resolve_paths()
    try:
        build_unified_qlib(
            data_root=data_root,
            qlib_dir=qlib_dir,
            mode="update",
            publish=True,
            touched_symbols=sorted(touched_symbols) if touched_symbols else None,
            datasets=sorted(affected_datasets) if affected_datasets else None,
            include_phase3=True,
            allow_exceptions=True,
            calendar_policy_id=_live_calendar_policy_id(qlib_dir),
        )
    except Exception as e:
        logger.error(f"Incremental Qlib update failed: {e}")


def _atomic_write_parquet(df, path: str) -> None:
    """Write via a UNIQUE temp + atomic replace — a fixed `path + '.tmp'` collides with a concurrent
    writer of the same file (GPT M4)."""
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix="." + os.path.basename(path) + ".", suffix=".tmp")
    os.close(fd)
    try:
        df.to_parquet(tmp, index=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _validate_trade_cal(df, *, fresh: bool):
    """Validate + normalize trade_cal STRICTLY — REJECT malformed ground truth, never coerce it. The
    prior normalizer turned is_open='BAD' -> 0 (an open day silently becomes closed) and every
    consumer (selector, gap walker, QA, watchdog, monthly bump) then agrees on the same wrong result
    (GPT 5-C Blocker 2). `fresh`=True for a just-fetched frame (fetched with is_open='1', so every
    row MUST be open); False for an on-disk merge base (may hold historical is_open=0 rows)."""
    missing = {"exchange", "cal_date", "is_open"} - set(df.columns)
    if missing:
        raise ValueError(f"trade_cal missing required columns {sorted(missing)}")
    out = df.copy()
    out["exchange"] = out["exchange"].astype(str).str.strip()
    if (out["exchange"].isin(["", "nan", "None"])).any():
        raise ValueError("trade_cal has null/blank exchange")
    out["cal_date"] = out["cal_date"].astype(str).str.replace("-", "", regex=False).str.strip()
    if not out["cal_date"].str.fullmatch(r"\d{8}").all():
        raise ValueError("trade_cal has non-8-digit cal_date values")
    # REAL Gregorian dates, not just 8-digit shape — `20260230` passed the regex and then poisoned
    # every downstream consumer incl. the attested provider floor (GPT REWORK-6 M2).
    parsed = pd.to_datetime(out["cal_date"], format="%Y%m%d", errors="coerce")
    if parsed.isna().any():
        bad = out.loc[parsed.isna(), "cal_date"].head(3).tolist()
        raise ValueError(f"trade_cal has impossible calendar dates {bad}")
    io = pd.to_numeric(out["is_open"], errors="coerce")
    if io.isna().any() or not io.isin([0, 1]).all():
        raise ValueError("trade_cal has is_open outside {0,1}")
    out["is_open"] = io.astype(int)
    if fresh and not (out["is_open"] == 1).all():
        raise ValueError("fresh trade_cal (fetched is_open='1') contains non-open rows")
    if out.duplicated(subset=["exchange", "cal_date"]).any():
        raise ValueError("trade_cal has duplicate (exchange, cal_date) keys")
    # SSE-only (GPT Blocker 2): this system stores a SINGLE market calendar. A second exchange (SZSE/
    # BSE) would double every date and make `_open_days`/`cands[-2]` double-count; a genuine per-exchange
    # holiday divergence cannot be represented by one calendar and must fail closed until an explicit
    # per-instrument calendar policy exists. SSE is the canonical A-share trading calendar.
    exchanges = set(out["exchange"].unique())
    if exchanges - {"SSE"}:
        raise ValueError(f"trade_cal contains non-SSE exchange(s) {sorted(exchanges - {'SSE'})} — this "
                         f"system stores a single SSE market calendar; refusing (GPT B2)")
    if "pretrade_date" not in out.columns:
        if fresh:
            raise ValueError("fresh trade_cal missing pretrade_date")
        out["pretrade_date"] = ""
    out["pretrade_date"] = out["pretrade_date"].astype(str).str.replace("-", "", regex=False)
    # CONTINUITY (GPT Blocker 2): per exchange, each OPEN day (after the first) must carry a valid
    # pretrade_date EQUAL to the immediately-preceding OPEN cal_date — a silently-MISSING trading day
    # breaks the chain (a purely syntactic check would accept 20260701,20260703 with
    # 20260703.pretrade_date=20260702). Validate EACH subsequent row INDEPENDENTLY; do NOT gate the
    # whole chain on `.all()` of the pretrade_date format — the live calendar's FIRST pretrade_date is
    # None, so `.all()` was False and the entire continuity check was silently skipped for every
    # fresh=False validation (the exact defect GPT reproduced). The first open row is exempt (its
    # predecessor may legitimately sit outside the frame / be blank on the earliest historical row).
    for ex, g in out[out["is_open"] == 1].groupby("exchange"):
        g = g.sort_values("cal_date").reset_index(drop=True)
        cal_dates = g["cal_date"].tolist()
        pretrades = g["pretrade_date"].tolist()
        for i in range(1, len(g)):
            pt = pretrades[i]
            if not re.fullmatch(r"\d{8}", pt):
                raise ValueError(f"trade_cal {ex}: open day {cal_dates[i]} has malformed pretrade_date "
                                 f"{pt!r} (continuity unverifiable)")
            if pt != cal_dates[i - 1]:
                raise ValueError(f"trade_cal continuity break (missing session?) {ex}: {cal_dates[i]} "
                                 f"pretrade_date={pt} != prior open session {cal_dates[i - 1]}")
    return out[["exchange", "cal_date", "is_open", "pretrade_date"]]


def resolve_last_complete_session(ref_dir: str, close_hhmm: str = "1730", now=None) -> str:
    """The last COMPLETE trading day as of now (CST). A trading day is complete once we are past the
    vendor daily-file close (~17:30 CST — kline ~16:00, daily_basic to ~17:00, + margin); before
    that, today's file is partial, so fall back to the prior trading day. Uses China time (the vendor
    close is CST, not the host's local time). This is the LENIENT daily-job readiness (idempotent,
    non-publishing, retry-tolerant); the FORMAL bump's target_end uses the stricter multi-endpoint
    contract (Phase 5-B). FAILS CLOSED if the calendar is not future-aware through today (a truncated
    calendar would otherwise freeze the selector on a stale session — GPT B1) or if the only
    candidate is a pre-close today. `now` injectable for tests."""
    if now is None:
        try:
            from zoneinfo import ZoneInfo
            now = datetime.now(ZoneInfo("Asia/Shanghai"))
        except Exception:  # pragma: no cover — zoneinfo present on 3.9+
            now = datetime.now()
    today = now.strftime('%Y%m%d')
    cal = pd.read_parquet(os.path.join(ref_dir, "trade_cal.parquet"))
    # DEDUP (GPT B2): a multi-exchange calendar repeats each date, so a duplicated `today` would make
    # cands[-2] STILL today (a pre-close run would then not fall back to the prior session). trade_cal
    # is SSE-only by enforcement, but dedup defensively so this selector is correct regardless.
    all_days = sorted(set(cal['cal_date'].astype(str)))
    if not all_days or all_days[-1] < today:
        raise SystemExit(f"trade_cal coverage ends {all_days[-1] if all_days else 'EMPTY'} < today "
                         f"{today} (CST) — calendar not future-aware; refusing a stale session")
    opens = sorted(set(cal[cal['is_open'] == 1]['cal_date'].astype(str)))
    cands = [d for d in opens if d <= today]
    if not cands:
        raise SystemExit("resolve_last_complete_session: no open trading day <= today in trade_cal")
    latest = cands[-1]
    if latest == today and now.strftime('%H%M') < close_hhmm:  # today still pre-close -> prior session
        if len(cands) < 2:
            raise SystemExit(f"today {today} is the only candidate and it is pre-close "
                             f"({now.strftime('%H%M')} < {close_hhmm}); refusing a partial session")
        return cands[-2]
    return latest


def main():
    parser = argparse.ArgumentParser(
        description="Daily Data Updater (Market + Fundamentals + Index Weights)"
    )
    parser.add_argument('--date', type=str, default=None,
                        help='Date to update (YYYYMMDD). Defaults to today.')
    parser.add_argument('--last-complete-session', action='store_true',
                        help='Update the last COMPLETE trading day (CST close-aware) instead of the '
                             'calendar today — the unattended daily-raw job (Phase 5-C).')
    parser.add_argument('--data-root', type=str, default=None,
                        help='Override data root directory (default: from config.yaml)')
    parser.add_argument('--skip-fundamentals', action='store_true',
                        help='Skip checking for new quarterly announcements')
    parser.add_argument('--skip-phase3', action='store_true',
                        help='Skip Phase 3 periodic and daily dataset refreshes')
    parser.add_argument('--no-qlib', action='store_true',
                        help='Skip Qlib binary conversion entirely')
    parser.add_argument('--rebuild-qlib', action='store_true',
                        help='Trigger full Qlib rebuild instead of incremental update')

    args = parser.parse_args()

    config_path = os.path.join(project_root, 'config.yaml')
    updater = DailyDataUpdater(config_path=config_path, data_root=args.data_root)

    if args.date:
        target_date = args.date
    elif args.last_complete_session:
        target_date = resolve_last_complete_session(updater.ref_dir)
        logger.info("--last-complete-session resolved to %s (CST close-aware)", target_date)
    else:
        target_date = datetime.now().strftime('%Y%m%d')

    # process-exclusive raw-maintenance lock (kernel-held; §6.1) so a direct run serializes with the
    # monthly bump's catch-up + the daily orchestrator (GPT 5-C Blocker 1). Per-call account safety is
    # additionally enforced inside TushareFetcher._safe_api_call.
    from data_infra.tushare_lock import raw_maintenance_lock
    with raw_maintenance_lock():
        result = updater.update_for_date(
            target_date,
            skip_fundamentals=args.skip_fundamentals,
            skip_phase3=args.skip_phase3,
        )
    success = bool(result["market_ok"])

    # Qlib conversion
    if not args.no_qlib:
        if args.rebuild_qlib:
            trigger_qlib_rebuild()
        elif result["touched_symbols"]:
            trigger_qlib_incremental(
                touched_symbols=result["touched_symbols"],
                affected_datasets=result["affected_datasets"],
            )

    # Summary
    logger.info(f"{'='*50}")
    logger.info(f"  Daily update complete for {target_date}")
    logger.info(f"  Market data: {'✅' if success else '⏭️ Skipped (non-trading day or no data)'}")
    logger.info(f"  Fundamentals: {'⏭️ Skipped' if args.skip_fundamentals else '✅ Checked'}")
    logger.info(f"  Qlib: {'⏭️ Skipped' if args.no_qlib else ('🔄 Full rebuild' if args.rebuild_qlib else '✅ Incremental')}")
    logger.info(f"{'='*50}")

    # M1: propagate a real EXIT CODE so Task Scheduler / the wrapper see a failed run (logging a
    # swallowed error then exiting 0 hides an updater crash behind QA's exit code). A non-trading day
    # is a legitimate skip (exit 0); a trading day with missing daily data or a suspend_d error fails.
    errors = result.get("errors", [])
    if result.get("is_trading_day", True) and errors:
        for e in errors:
            logger.error("DAILY UPDATE FAILURE: %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
