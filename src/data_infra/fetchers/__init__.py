"""
Tushare Pro Data Fetcher
Handles downloading market data, fundamental data, and reference data from Tushare.
"""
import tushare as ts
import pandas as pd
import yaml
import logging
import time
import os

from data_infra.tushare_lock import spaced_call  # cross-process account lock + spacing (§6.1, GPT 5-C)

DEFAULT_STATEMENT_LIMIT = 2000


class _LockedPro:
    """Wrap the raw Tushare client so EVERY endpoint call — internal (via _safe_api_call) OR external
    (a script doing `fetcher.pro.xxx`) — flows through the cross-process account lock + global rate
    spacing (GPT 5-C Major 1).

    This is DISCIPLINE, not a security boundary (GPT REWORK-4 Major 1): Python introspection can always
    reach the wrapped client (the returned closure's ``__closure__``, ``object.__getattribute__`` on the
    slot). ``__getattribute__`` + ``__slots__`` closes the CASUAL escape (``fetcher.pro._real`` no longer
    returns the client — a bare ``__getattr__`` would leave it readable), and the PRO001 lint
    (scripts/lint_no_bare_pro.py, in daily QA) fails the deliberate bypasses (raw construction, aliased
    imports, ``__closure__`` / slot introspection). The account-safety guarantee rests on the lint +
    convention, not on making the object tamper-proof. NOTE: external ``.pro`` calls get the lock +
    spacing but NOT the ``_safe_api_call`` RETRY — prefer the ``fetch_*`` methods for retrying reads."""

    __slots__ = ("_real", "_base_sleep")

    def __init__(self, real, base_sleep):
        object.__setattr__(self, "_real", real)
        object.__setattr__(self, "_base_sleep", base_sleep)

    def __getattribute__(self, name):
        # refuse the wrapper's own private slots / __dict__ so the raw client can't escape via the
        # CASUAL path (fetcher.pro._real). Determined introspection still can — that's the lint's job.
        if name == "__dict__" or (name.startswith("_") and not name.startswith("__")):
            raise AttributeError(f"_LockedPro: {name!r} is refused (no casual unlocked client handle)")
        if name.startswith("__"):  # dunders (repr/class/reduce) resolve on the wrapper itself
            return object.__getattribute__(self, name)
        real = object.__getattribute__(self, "_real")
        fn = getattr(real, name)  # a Tushare endpoint (no endpoint name starts with '_')
        if not callable(fn):
            return fn
        base_sleep = object.__getattribute__(self, "_base_sleep")

        def _wrapped(*args, **kwargs):
            return spaced_call(fn, base_sleep, *args, **kwargs)

        _wrapped.__name__ = name
        return _wrapped

    def __reduce__(self):
        # EXPLICITLY unpicklable (GPT REWORK-4 Major 1): a live Tushare client handle must never cross a
        # process boundary (Windows multiprocessing uses spawn -> pickle). Construct a fresh
        # TushareFetcher per process instead. Without this, pickling failed with an obscure missing-slot
        # error; make the refusal clear.
        raise TypeError("_LockedPro is not picklable — do not pass a Tushare client across processes; "
                        "build a fresh TushareFetcher in each process.")
VIP_ALL_STOCK_LIMIT = 10000
FINE_INDICATOR_LIMIT = 100

class TushareFetcher:
    def __init__(self, config_path="config.yaml", max_retries=3, base_sleep=1.5):
        # Load .env file if python-dotenv is available
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass  # dotenv not installed — rely on system env vars

        # Load config
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        
        # Resolve token: prefer env var, fall back to config value
        token = os.environ.get("TUSHARE_TOKEN") or self.config["data"]["tushare_token"]
        self.max_retries = max_retries
        # §6.1 central floor (GPT recovery B3 + non-finite minor): a constructor cannot lower the
        # account-wide spacing; nan/inf are invalid, not floored by max(). spaced_call floors again at
        # the chokepoint; this keeps self.base_sleep (retry backoff) honest too.
        import math as _math
        from data_infra.tushare_lock import MIN_BASE_SLEEP
        try:
            base_sleep = float(base_sleep)
        except (TypeError, ValueError):
            base_sleep = MIN_BASE_SLEEP
        if not _math.isfinite(base_sleep) or base_sleep < MIN_BASE_SLEEP:
            logging.warning("base_sleep %r invalid/below the §6.1 floor — raised to %.2f", base_sleep, MIN_BASE_SLEEP)
            base_sleep = MIN_BASE_SLEEP
        self.base_sleep = base_sleep
        try:
            ts.set_token(token)
            raw = ts.pro_api()
        except PermissionError:
            logging.warning(
                "tushare.set_token() could not write the local token cache; "
                "falling back to ts.pro_api(token)"
            )
            raw = ts.pro_api(token)
        # LOCKED proxy: every self.pro.xxx call (internal via _safe_api_call OR external direct) is
        # serialized + globally rate-spaced across processes (§6.1). No unlocked handle exists.
        self.pro = _LockedPro(raw, base_sleep)
        
        logging.info("Tushare API initialized.")

    def _safe_api_call(self, api_func, **kwargs):
        """Retry wrapper. api_func is a LOCKED-proxy method (self.pro.xxx) — the cross-process account
        lock + GLOBAL rate spacing/cooldown live in the proxy (tushare_lock.spaced_call), so this only
        handles retries (GPT 5-C Major 1: the lock is enforced at the proxy, not here)."""
        for attempt in range(self.max_retries):
            try:
                return api_func(**kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    func_name = getattr(api_func, '__name__', str(api_func))
                    logging.error(f"Max retries reached for {func_name} with args {kwargs}")
                    raise
                # a rate-limit already bumped the global cooldown in the proxy; add a light per-retry
                # backoff for transient errors (the proxy enforces the actual account-wide spacing).
                sleep_time = self.base_sleep * (2 ** attempt)
                logging.warning(f"API Error: {e}. Retrying in {sleep_time}s (attempt {attempt+1}/{self.max_retries})...")
                time.sleep(sleep_time)
        return pd.DataFrame()
        
    def _fetch_paginated(self, api_func, limit=100, **kwargs):
        """Fetch all pages for an endpoint, falling back to offset pagination only when needed."""
        all_data = []
        offset = 0
        while True:
            df = self._safe_api_call(api_func, limit=limit, offset=offset, **kwargs)
            if df is None or df.empty:
                break
            all_data.append(df)
            if len(df) < limit:
                break
            offset += limit
            
        if not all_data:
            return pd.DataFrame()
        if len(all_data) == 1:
            return all_data[0].reset_index(drop=True)
        return pd.concat(all_data, ignore_index=True)

    def _statement_kwargs(
        self,
        ts_code: str = None,
        period: str = None,
        start_date: str = None,
        end_date: str = None,
        ann_date: str = None,
        report_type: str = None,
        comp_type: str = None,
        fields: str = None,
    ) -> dict:
        """Build a clean kwargs payload for Tushare statement-style endpoints."""
        kwargs = {}
        for key, value in {
            "ts_code": ts_code,
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "ann_date": ann_date,
            "report_type": report_type,
            "comp_type": comp_type,
            "fields": fields,
        }.items():
            if value is not None:
                kwargs[key] = value
        return kwargs

    def _fetch_statement(
        self,
        api_func,
        *,
        limit: int,
        ts_code: str = None,
        period: str = None,
        start_date: str = None,
        end_date: str = None,
        ann_date: str = None,
        report_type: str = None,
        comp_type: str = None,
        fields: str = None,
    ) -> pd.DataFrame:
        """Fetch a statement-style endpoint with optional pagination and report-type filters."""
        kwargs = self._statement_kwargs(
            ts_code=ts_code,
            period=period,
            start_date=start_date,
            end_date=end_date,
            ann_date=ann_date,
            report_type=report_type,
            comp_type=comp_type,
            fields=fields,
        )
        return self._fetch_paginated(api_func, limit=limit, **kwargs)

    def _fetch_statement_report_types(
        self,
        api_func,
        report_types,
        *,
        limit: int,
        ts_code: str = None,
        period: str = None,
        start_date: str = None,
        end_date: str = None,
        ann_date: str = None,
        comp_type: str = None,
        fields: str = None,
    ) -> pd.DataFrame:
        """Fetch multiple report types and concatenate them into one dataframe."""
        frames = []
        for report_type in report_types:
            df = self._fetch_statement(
                api_func,
                limit=limit,
                ts_code=ts_code,
                period=period,
                start_date=start_date,
                end_date=end_date,
                ann_date=ann_date,
                report_type=str(report_type),
                comp_type=comp_type,
                fields=fields,
            )
            if df is not None and not df.empty:
                frames.append(df)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    def fetch_stock_basic(self) -> pd.DataFrame:
        """Fetch list of all stocks, including delisted and ST (L, D, P)."""
        logging.info("Fetching stock basics (L, D, P)...")
        return self._safe_api_call(self.pro.stock_basic, exchange='', list_status='L,D,P', fields='ts_code,symbol,name,area,industry,fullname,enname,cnspell,market,exchange,curr_type,list_status,list_date,delist_date,is_hs,act_name,act_ent_type')

    def fetch_trade_cal(self, start_date=None, end_date=None) -> pd.DataFrame:
        """Fetch trading calendar."""
        logging.info(f"Fetching trade calendar from {start_date} to {end_date}...")
        return self._safe_api_call(self.pro.trade_cal, start_date=start_date, end_date=end_date, is_open='1')

    def fetch_daily_data(self, trade_date: str = None, ts_code: str = None, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Fetch daily price/volume data (OHLCV)."""
        return self._safe_api_call(self.pro.daily, trade_date=trade_date, ts_code=ts_code, start_date=start_date, end_date=end_date)

    def fetch_adj_factor(self, trade_date: str = None, ts_code: str = None, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Fetch daily adjustment factors for restoration pricing."""
        return self._safe_api_call(self.pro.adj_factor, trade_date=trade_date, ts_code=ts_code, start_date=start_date, end_date=end_date)

    def fetch_suspend_d(self, trade_date: str = None, ts_code: str = None, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Fetch daily suspension info."""
        return self._safe_api_call(self.pro.suspend_d, trade_date=trade_date, ts_code=ts_code, start_date=start_date, end_date=end_date)

    def fetch_fundamentals(self, trade_date: str = None, ts_code: str = None, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Fetch daily valuation metrics (PE, PB, PS, Turnover)."""
        return self._safe_api_call(self.pro.daily_basic, trade_date=trade_date, ts_code=ts_code, start_date=start_date, end_date=end_date)

    def fetch_index_basic(self, market: str = 'SSE') -> pd.DataFrame:
        """Fetch index basics for a market (e.g., SSE, SZSE)."""
        return self._safe_api_call(self.pro.index_basic, market=market)

    def fetch_index_daily(self, ts_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Fetch daily index data (e.g. 000001.SH, 000300.SH)."""
        return self._safe_api_call(self.pro.index_daily, ts_code=ts_code, start_date=start_date, end_date=end_date)

    def fetch_index_weight(self, index_code: str, trade_date: str = None, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Fetch constituent weights for an index (e.g. 000300.SH weights)."""
        return self._safe_api_call(self.pro.index_weight, index_code=index_code, trade_date=trade_date, start_date=start_date, end_date=end_date)
        
    def fetch_income(
        self,
        ts_code: str = None,
        period: str = None,
        start_date: str = None,
        end_date: str = None,
        ann_date: str = None,
        report_type: str = None,
        comp_type: str = None,
        fields: str = None,
    ) -> pd.DataFrame:
        """
        Fetch income statements (Revenue, Net Income, Gross Profit, etc.).
        
        Note: Paginates automatically up to limit (2000).
        
        Args:
            ts_code (str, optional): Tushare stock code (e.g., '000001.SZ').
            period (str, optional): Reporting period (e.g., '20231231').
            start_date (str, optional): Start date for announcement (YYYYMMDD).
            end_date (str, optional): End date for announcement (YYYYMMDD).
            
        Returns:
            pd.DataFrame: A dataframe containing income statements.
        """
        return self._fetch_statement(
            self.pro.income,
            limit=DEFAULT_STATEMENT_LIMIT,
            ts_code=ts_code,
            period=period,
            start_date=start_date,
            end_date=end_date,
            ann_date=ann_date,
            report_type=report_type,
            comp_type=comp_type,
            fields=fields,
        )

    def fetch_income_vip(
        self,
        ts_code: str = None,
        period: str = None,
        start_date: str = None,
        end_date: str = None,
        ann_date: str = None,
        report_type: str = None,
        comp_type: str = None,
        fields: str = None,
    ) -> pd.DataFrame:
        """Fetch income statements via the VIP endpoint for all-stock or report-type queries."""
        return self._fetch_statement(
            self.pro.income_vip,
            limit=VIP_ALL_STOCK_LIMIT,
            ts_code=ts_code,
            period=period,
            start_date=start_date,
            end_date=end_date,
            ann_date=ann_date,
            report_type=report_type,
            comp_type=comp_type,
            fields=fields,
        )

    def fetch_income_quarterly_vip(
        self,
        ts_code: str = None,
        period: str = None,
        start_date: str = None,
        end_date: str = None,
        ann_date: str = None,
        comp_type: str = None,
        fields: str = None,
        report_types=("2", "3"),
    ) -> pd.DataFrame:
        """Fetch direct single-quarter income rows, preserving both report_type=2 and 3.

        Single-quarter (report_type 2/3) rows structurally lack cumulative-only fields
        (e.g. ``ebit``/``ebitda`` are never populated by Tushare for single quarters);
        we drop all-null columns so they are not stored as misleading empty columns.
        """
        df = self._fetch_statement_report_types(
            self.pro.income_vip,
            report_types=report_types,
            limit=VIP_ALL_STOCK_LIMIT,
            ts_code=ts_code,
            period=period,
            start_date=start_date,
            end_date=end_date,
            ann_date=ann_date,
            comp_type=comp_type,
            fields=fields,
        )
        return df.dropna(how="all", axis=1) if df is not None and not df.empty else df

    def fetch_balancesheet(
        self,
        ts_code: str = None,
        period: str = None,
        start_date: str = None,
        end_date: str = None,
        ann_date: str = None,
        report_type: str = None,
        comp_type: str = None,
        fields: str = None,
    ) -> pd.DataFrame:
        """
        Fetch balance sheets (Assets, Liabilities, Equity).
        
        Note: Paginates automatically up to limit (2000).
        
        Args:
            ts_code (str, optional): Tushare stock code (e.g., '000001.SZ').
            period (str, optional): Reporting period (e.g., '20231231').
            start_date (str, optional): Start date for announcement (YYYYMMDD).
            end_date (str, optional): End date for announcement (YYYYMMDD).
            
        Returns:
            pd.DataFrame: A dataframe containing balance sheets.
        """
        return self._fetch_statement(
            self.pro.balancesheet,
            limit=DEFAULT_STATEMENT_LIMIT,
            ts_code=ts_code,
            period=period,
            start_date=start_date,
            end_date=end_date,
            ann_date=ann_date,
            report_type=report_type,
            comp_type=comp_type,
            fields=fields,
        )

    def fetch_balancesheet_vip(
        self,
        ts_code: str = None,
        period: str = None,
        start_date: str = None,
        end_date: str = None,
        ann_date: str = None,
        report_type: str = None,
        comp_type: str = None,
        fields: str = None,
    ) -> pd.DataFrame:
        """Fetch balance sheets via the VIP endpoint."""
        return self._fetch_statement(
            self.pro.balancesheet_vip,
            limit=VIP_ALL_STOCK_LIMIT,
            ts_code=ts_code,
            period=period,
            start_date=start_date,
            end_date=end_date,
            ann_date=ann_date,
            report_type=report_type,
            comp_type=comp_type,
            fields=fields,
        )

    def fetch_balancesheet_quarterly_vip(
        self,
        ts_code: str = None,
        period: str = None,
        start_date: str = None,
        end_date: str = None,
        ann_date: str = None,
        comp_type: str = None,
        fields: str = None,
        report_types=("2", "3"),
    ) -> pd.DataFrame:
        """Fetch direct single-quarter balance-sheet rows, preserving report_type variants."""
        return self._fetch_statement_report_types(
            self.pro.balancesheet_vip,
            report_types=report_types,
            limit=VIP_ALL_STOCK_LIMIT,
            ts_code=ts_code,
            period=period,
            start_date=start_date,
            end_date=end_date,
            ann_date=ann_date,
            comp_type=comp_type,
            fields=fields,
        )

    def fetch_fina_indicator(
        self,
        ts_code: str = None,
        period: str = None,
        start_date: str = None,
        end_date: str = None,
        ann_date: str = None,
        fields: str = None,
    ) -> pd.DataFrame:
        """
        Fetch financial indicators (ROE, ROA, Current Ratio, etc.).
        
        Args:
            ts_code (str, optional): Tushare stock code (e.g., '000001.SZ').
            period (str, optional): Reporting period (e.g., '20231231').
            start_date (str, optional): Start date for announcement (YYYYMMDD).
            end_date (str, optional): End date for announcement (YYYYMMDD).
            
        Returns:
            pd.DataFrame: A dataframe containing requested financial indicators.
        """
        # Standard fina_indicator remains a low-limit endpoint.
        return self._fetch_statement(
            self.pro.fina_indicator,
            limit=FINE_INDICATOR_LIMIT,
            ts_code=ts_code,
            period=period,
            start_date=start_date,
            end_date=end_date,
            ann_date=ann_date,
            fields=fields,
        )

    def fetch_fina_indicator_vip(
        self,
        ts_code: str = None,
        period: str = None,
        start_date: str = None,
        end_date: str = None,
        ann_date: str = None,
        fields: str = None,
    ) -> pd.DataFrame:
        """Fetch financial indicators via the VIP endpoint for all-stock PIT refreshes."""
        return self._fetch_statement(
            self.pro.fina_indicator_vip,
            limit=VIP_ALL_STOCK_LIMIT,
            ts_code=ts_code,
            period=period,
            start_date=start_date,
            end_date=end_date,
            ann_date=ann_date,
            fields=fields,
        )

    def fetch_index_classify(self, level: str = None, src: str = 'SW2021') -> pd.DataFrame:
        """Fetch Shenwan or CITIC industry classifications. src: 'SW2021' or 'CITICS'"""
        return self._safe_api_call(self.pro.index_classify, level=level, src=src)

    def fetch_index_member_all(self, industry_code: str = None, ts_code: str = None,
                                is_new: str = None) -> pd.DataFrame:
        """Fetch Shenwan index constituent history (VIP tier).

        Returns the per-stock membership rows of an L1 (or L2/L3) Shenwan
        index, including the in_date / out_date interval and is_new flag.
        Combine `is_new='Y'` (current) + `is_new='N'` (historical) to get
        full history; calling with `is_new=None` returns only current
        members (verified against pro.index_member_all on 2026-04-27).

        Args:
            industry_code: Neutral kwarg for the L1/L2/L3 index code, e.g.
                '801780.SI' for Shenwan 银行. Internally maps to Tushare's
                `l1_code` parameter (verified by A0 probe at
                workspace/scripts/probe_index_member_all.py on 2026-04-27).
            ts_code: Filter to one stock's industry history.
            is_new: 'Y' = current members only, 'N' = historical only,
                None = current only (Tushare default behavior).

        Returns:
            DataFrame with columns: l1_code, l1_name, l2_code, l2_name,
                l3_code, l3_name, ts_code, name, in_date, out_date, is_new.
        """
        tushare_kwargs = {}
        if industry_code is not None:
            tushare_kwargs['l1_code'] = industry_code
        if ts_code is not None:
            tushare_kwargs['ts_code'] = ts_code
        if is_new is not None:
            tushare_kwargs['is_new'] = is_new
        return self._safe_api_call(self.pro.index_member_all, **tushare_kwargs)

    def fetch_namechange(self, ts_code: str = None, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Fetch historical stock name change records.

        Used to construct ST universe by tracking when stocks were renamed
        to/from ST, *ST, S*ST, etc.

        Args:
            ts_code: Tushare stock code (e.g., '600848.SH').
            start_date: Announcement start date (YYYYMMDD).
            end_date: Announcement end date (YYYYMMDD).

        Returns:
            DataFrame with columns: ts_code, name, start_date, end_date,
                ann_date, change_reason.
        """
        logging.info("Fetching namechange data (ts_code=%s)...", ts_code)
        return self._safe_api_call(
            self.pro.namechange,
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            fields='ts_code,name,start_date,end_date,ann_date,change_reason',
        )

    def fetch_dividend(self, ts_code: str = None, ann_date: str = None, record_date: str = None, imp_ann_date: str = None) -> pd.DataFrame:
        """Fetch dividend and corporate actions."""
        return self._safe_api_call(self.pro.dividend, ts_code=ts_code, ann_date=ann_date, record_date=record_date, imp_ann_date=imp_ann_date)

    # ------------------------------------------------------------------ #
    #  Phase 3: Factor Research Data Sources (7 new endpoints)            #
    # ------------------------------------------------------------------ #

    def fetch_cashflow(
        self,
        ts_code: str = None,
        period: str = None,
        start_date: str = None,
        end_date: str = None,
        ann_date: str = None,
        report_type: str = None,
        comp_type: str = None,
        fields: str = None,
    ) -> pd.DataFrame:
        """Fetch cash flow statements (quarterly/annual).

        Key fields: n_cashflow_act (OCF), n_cashflow_inv_act (investing CF),
        n_cash_flows_fnc_act (financing CF), c_pay_acq_const_fiolta (CapEx).
        Contains ann_date for PIT alignment.

        Args:
            ts_code: Tushare stock code (e.g., '000001.SZ').
            period: Reporting period (e.g., '20231231').
            start_date: Announcement start date (YYYYMMDD).
            end_date: Announcement end date (YYYYMMDD).

        Returns:
            DataFrame with cash flow statement data.
        """
        return self._fetch_statement(
            self.pro.cashflow,
            limit=DEFAULT_STATEMENT_LIMIT,
            ts_code=ts_code,
            period=period,
            start_date=start_date,
            end_date=end_date,
            ann_date=ann_date,
            report_type=report_type,
            comp_type=comp_type,
            fields=fields,
        )

    def fetch_cashflow_vip(
        self,
        ts_code: str = None,
        period: str = None,
        start_date: str = None,
        end_date: str = None,
        ann_date: str = None,
        report_type: str = None,
        comp_type: str = None,
        fields: str = None,
    ) -> pd.DataFrame:
        """Fetch cash flow statements via the VIP endpoint."""
        return self._fetch_statement(
            self.pro.cashflow_vip,
            limit=VIP_ALL_STOCK_LIMIT,
            ts_code=ts_code,
            period=period,
            start_date=start_date,
            end_date=end_date,
            ann_date=ann_date,
            report_type=report_type,
            comp_type=comp_type,
            fields=fields,
        )

    def fetch_cashflow_quarterly_vip(
        self,
        ts_code: str = None,
        period: str = None,
        start_date: str = None,
        end_date: str = None,
        ann_date: str = None,
        comp_type: str = None,
        fields: str = None,
        report_types=("2", "3"),
    ) -> pd.DataFrame:
        """Fetch direct single-quarter cashflow rows, preserving report_type variants.

        Drops all-null columns: single-quarter (report_type 2/3) rows structurally lack
        cumulative-only fields, which would otherwise be stored as empty columns.
        """
        df = self._fetch_statement_report_types(
            self.pro.cashflow_vip,
            report_types=report_types,
            limit=VIP_ALL_STOCK_LIMIT,
            ts_code=ts_code,
            period=period,
            start_date=start_date,
            end_date=end_date,
            ann_date=ann_date,
            comp_type=comp_type,
            fields=fields,
        )
        return df.dropna(how="all", axis=1) if df is not None and not df.empty else df

    def fetch_forecast(self, ts_code: str = None, period: str = None,
                       ann_date: str = None) -> pd.DataFrame:
        """Fetch earnings pre-announcements / forecasts.

        Key fields: type (预增/预减/略增/略减/续盈/亏损/扭亏),
        p_change_min, p_change_max, net_profit_min, net_profit_max.

        Args:
            ts_code: Tushare stock code.
            period: Reporting period (YYYYMMDD).
            ann_date: Announcement date (YYYYMMDD).

        Returns:
            DataFrame with earnings forecast data.
        """
        return self._safe_api_call(
            self.pro.forecast, ts_code=ts_code, period=period,
            ann_date=ann_date
        )

    def fetch_moneyflow(self, trade_date: str = None, ts_code: str = None,
                        start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Fetch daily capital flow data (large/medium/small order splits).

        Key fields: buy_lg_amount, sell_lg_amount, buy_md_amount, sell_md_amount,
        buy_sm_amount, sell_sm_amount, net_mf_amount (net capital flow).

        Args:
            trade_date: Trade date (YYYYMMDD) — fetches all stocks for that day.
            ts_code: Stock code — fetches time series for that stock.
            start_date: Range start (YYYYMMDD).
            end_date: Range end (YYYYMMDD).

        Returns:
            DataFrame with daily capital flow data.
        """
        return self._safe_api_call(
            self.pro.moneyflow, trade_date=trade_date, ts_code=ts_code,
            start_date=start_date, end_date=end_date
        )

    def fetch_hk_hold(self, trade_date: str = None, ts_code: str = None,
                      start_date: str = None, end_date: str = None,
                      exchange: str = None) -> pd.DataFrame:
        """Fetch northbound (HK Stock Connect) daily holding details.

        Key fields: ts_code, trade_date, vol (holding shares),
        ratio (holding % of free float).

        Args:
            trade_date: Trade date (YYYYMMDD).
            ts_code: Stock code.
            start_date: Range start.
            end_date: Range end.
            exchange: Exchange filter ('SH' or 'SZ').

        Returns:
            DataFrame with northbound holding data.
        """
        return self._safe_api_call(
            self.pro.hk_hold, trade_date=trade_date, ts_code=ts_code,
            start_date=start_date, end_date=end_date, exchange=exchange
        )

    def fetch_margin_detail(self, trade_date: str = None, ts_code: str = None,
                            start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Fetch daily margin trading details (融资融券明细).

        Key fields: rzye (margin balance), rzmre (margin buy amount),
        rqye (short-selling balance), rqmcl (short-sell volume).

        Args:
            trade_date: Trade date (YYYYMMDD).
            ts_code: Stock code.
            start_date: Range start.
            end_date: Range end.

        Returns:
            DataFrame with margin trading details.
        """
        return self._safe_api_call(
            self.pro.margin_detail, trade_date=trade_date, ts_code=ts_code,
            start_date=start_date, end_date=end_date
        )

    def fetch_stk_holdernumber(self, ts_code: str = None, enddate: str = None,
                               start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Fetch shareholder count data.

        Key fields: ts_code, ann_date, end_date, holder_num.
        Updated per quarter when companies disclose reports.

        Args:
            ts_code: Stock code.
            enddate: Specific end date for the report.
            start_date: Announcement start date.
            end_date: Announcement end date.

        Returns:
            DataFrame with shareholder count data.
        """
        return self._safe_api_call(
            self.pro.stk_holdernumber, ts_code=ts_code, enddate=enddate,
            start_date=start_date, end_date=end_date
        )

    def fetch_stk_limit(self, trade_date: str = None, ts_code: str = None,
                        start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Fetch daily limit-up/limit-down prices.

        Key fields: ts_code, trade_date, pre_close, up_limit, down_limit.

        Args:
            trade_date: Trade date (YYYYMMDD).
            ts_code: Stock code.
            start_date: Range start.
            end_date: Range end.

        Returns:
            DataFrame with daily limit prices.
        """
        return self._safe_api_call(
            self.pro.stk_limit, trade_date=trade_date, ts_code=ts_code,
            start_date=start_date, end_date=end_date
        )

    # ------------------------------------------------------------------ #
    #  Phase 3 — New Alpha Endpoints (5000积分 tier)                      #
    # ------------------------------------------------------------------ #

    def fetch_top_list(self, trade_date: str = None, ts_code: str = None) -> pd.DataFrame:
        """Fetch 龙虎榜每日明细 (hot-stock trading details).

        Daily after market close. Most days have 10-50 entries.
        Key signal fields: net_amount, l_buy, l_sell, reason.

        Args:
            trade_date: Trade date (YYYYMMDD, required for per-date fetch).
            ts_code: Optional stock filter.

        Returns:
            DataFrame with top_list entries for the date.
        """
        return self._safe_api_call(
            self.pro.top_list, trade_date=trade_date, ts_code=ts_code
        )

    def fetch_top_inst(self, trade_date: str = None, ts_code: str = None) -> pd.DataFrame:
        """Fetch 龙虎榜机构明细 (institutional trading on hot-stock days).

        Requires 5000积分. Daily after market close.
        Key signal fields: side, buy, sell, net_buy.

        Args:
            trade_date: Trade date (YYYYMMDD, required for per-date fetch).
            ts_code: Optional stock filter.

        Returns:
            DataFrame with institutional seat-level entries.
        """
        return self._safe_api_call(
            self.pro.top_inst, trade_date=trade_date, ts_code=ts_code
        )

    def fetch_block_trade(self, trade_date: str = None, ts_code: str = None,
                          start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Fetch 大宗交易 (block/negotiated trades).

        Daily after market close. Off-exchange large transactions.
        Key signal fields: price, vol, amount, buyer, seller.

        Args:
            trade_date: Trade date (YYYYMMDD).
            ts_code: Optional stock filter.
            start_date: Range start.
            end_date: Range end.

        Returns:
            DataFrame with block trade entries.
        """
        return self._safe_api_call(
            self.pro.block_trade, trade_date=trade_date, ts_code=ts_code,
            start_date=start_date, end_date=end_date
        )

    def fetch_stk_holdertrade(self, ts_code: str = None, ann_date: str = None,
                              start_date: str = None, end_date: str = None,
                              trade_type: str = None, holder_type: str = None) -> pd.DataFrame:
        """Fetch 股东增减持 (insider/major shareholder buy/sell transactions).

        Event-driven, disclosed via announcements. One of the strongest
        documented alpha signals in A-shares.
        Key signal fields: in_de, change_vol, change_ratio, after_ratio, avg_price.

        Args:
            ts_code: Stock code (for per-stock fetch).
            ann_date: Announcement date (YYYYMMDD).
            start_date: Range start for ann_date.
            end_date: Range end for ann_date.
            trade_type: Trade type filter (IN=增持, DE=减持).
            holder_type: Holder type filter (G=高管, P=个人, C=公司).

        Returns:
            DataFrame with shareholder trading disclosure entries.
        """
        return self._safe_api_call(
            self.pro.stk_holdertrade, ts_code=ts_code, ann_date=ann_date,
            start_date=start_date, end_date=end_date,
            trade_type=trade_type, holder_type=holder_type
        )

    def fetch_cyq_perf(self, ts_code: str, start_date: str = None,
                       end_date: str = None) -> pd.DataFrame:
        """Fetch 筹码分布 (chip distribution / cost basis analysis).

        Requires 5000积分. Daily frequency, per-stock API (ts_code required).
        Key signal fields: winner_rate, cost_5pct, cost_50pct, cost_85pct,
        cost_95pct, weight_avg.

        Args:
            ts_code: Stock code (REQUIRED for this endpoint).
            start_date: Range start (YYYYMMDD).
            end_date: Range end (YYYYMMDD).

        Returns:
            DataFrame with daily chip distribution metrics.
        """
        return self._safe_api_call(
            self.pro.cyq_perf, ts_code=ts_code,
            start_date=start_date, end_date=end_date
        )

    def fetch_broker_recommend(self, month: str) -> pd.DataFrame:
        """Fetch 券商月度金股 (broker monthly golden-stock recommendations).

        Endpoint: broker_recommend (doc_id=267). Requires 6000积分.
        Monthly frequency, queried per-month. Tushare updates the CURRENT
        month's list within 1-3 days of month start ("一般1日~3日内更新当月数据").

        PIT / visibility (CRITICAL — there is NO per-row disclosure date):
            The only date field is `month` (YYYYMM), which is the RECOMMENDATION
            month, not a visible-at timestamp. Because the list is populated
            within the first 1-3 days of month M, a month-M list must NOT be
            treated as tradable before that window closes. Consumers must anchor
            visibility on the first trading day on/after ~day 4 of month M
            (see the as-of membership builder), never on month start.

        Coverage: history effectively starts 2020-07 (earlier months return
            empty). Broker coverage is unstable month-to-month (~10-44 brokers,
            ~88-260 stocks), so conviction (broker count) is comparable only
            cross-sectionally WITHIN a month, never across months.

        Args:
            month: Recommendation month (YYYYMM, required).

        Returns:
            DataFrame with columns [month, broker, ts_code, name].
        """
        return self._safe_api_call(self.pro.broker_recommend, month=month)

    # ------------------------------------------------------------------
    # Text sources (大模型语料专题, doc-142 family) — Phase-2A, 单独权限.
    # PIT: raw frames MUST be persisted through data_infra.text_store.ingest_rows
    # (C1 stamps; nominal dates are never visibility). See data_dictionary.md.
    # ------------------------------------------------------------------

    def fetch_research_report(self, trade_date: str) -> pd.DataFrame:
        """Fetch 券商研究报告 abstracts for one nominal date (doc_id=415).

        ⚠ PIT: `trade_date` is a NOMINAL date (no timestamp; vendor updates
        twice daily — the report_rc-class backfill trap). Ingest with
        `published_col=None` so visibility falls back to first ingestion.
        1000 rows/call cap — a truncated day logs a warning downstream.
        """
        return self._safe_api_call(self.pro.research_report, trade_date=trade_date)

    def fetch_irm_qa_sh(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch 上证e互动 Q&A (doc_id=366; history from 2023-06; 3000/call).

        PIT anchor = `pub_time` (reply timestamp): ingest with
        `published_col="pub_time"`.
        """
        return self._safe_api_call(
            self.pro.irm_qa_sh, start_date=start_date, end_date=end_date
        )

    def fetch_irm_qa_sz(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch 深证互动易 Q&A (doc_id=367; history from 2010-10; 3000/call).

        PIT anchor = `pub_time`; extra `industry` column (涉及行业).
        """
        return self._safe_api_call(
            self.pro.irm_qa_sz, start_date=start_date, end_date=end_date
        )

    def fetch_anns_d(self, ann_date: str) -> pd.DataFrame:
        """Fetch 上市公司公告 titles+PDF URLs for one day (doc_id=176; 2000/call).

        PIT anchor = `rec_time` (发布时间, datetime) — NON-default, must be
        requested explicitly via `fields=`. Title record only; PDF text (if
        ever parsed) needs its own pdf_visible_at (C1).
        """
        return self._safe_api_call(
            self.pro.anns_d,
            ann_date=ann_date,
            fields="ann_date,ts_code,name,title,url,rec_time",
        )

    def fetch_npr(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch 国家政策库 (doc_id=406; 500/call, datetime params).

        PIT anchor = `pubtime` (发布时间, datetime): ingest with
        `published_col="pubtime"`. 量小(~9条/周),单窗单 call 够用。
        """
        return self._safe_api_call(self.pro.npr, start_date=start_date,
                                   end_date=end_date)

    def fetch_monetary_policy(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch 央行货币政策执行报告 (doc_id=465; 2001 起, 1000/call 一次拉全).

        ⚠ PIT: `pub_date` 仅日级(无时间戳) → ingest `published_col=None`,
        可见性回退入库时刻;历史回补用 pub_date+1 开盘日模拟锚。
        """
        return self._safe_api_call(self.pro.monetary_policy,
                                   start_date=start_date, end_date=end_date)

    def fetch_cctv_news(self, date: str) -> pd.DataFrame:
        """Fetch 新闻联播文字稿 (doc_id=154; 2017 起, 按日).

        ⚠ PIT: `date` 名义日,节目 19:00 播出 → ingest `published_col=None`;
        历史回补模拟锚 = date+1 开盘日(晚间播出,次晨可用)。
        """
        return self._safe_api_call(self.pro.cctv_news, date=date)

    #: NF wave (doc 143): whitelisted flash sources (cls disabled pending sub-permission)
    NEWS_SOURCES = ("sina", "wallstreetcn", "10jqka", "eastmoney")
    _NEWS_CAP = 1500

    def fetch_news(self, src: str, start: str, end: str) -> pd.DataFrame:
        """One 新闻快讯 call for [start, end] on one source (doc_id=143).

        `channels` is NON-default → requested explicitly. `src` is an INPUT
        param not returned as a column → injected here as a stamped column
        (doc-m2). PIT anchor = `datetime` (ingest with published_col="datetime").
        Only whitelisted sources are accepted (M1). The returned frame carries
        ``df.attrs['cap_hit']`` = True when the row count reached the 1500 cap
        (the caller MUST split, never treat a capped window as complete).
        """
        if src not in self.NEWS_SOURCES:
            raise ValueError(f"news source {src!r} not in whitelist {self.NEWS_SOURCES}")
        raw = self._safe_api_call(
            self.pro.news, src=src, start_date=start, end_date=end,
            fields="datetime,content,title,channels")
        # review M1: a None/failed response is NOT "zero news" — record response_ok
        # so the coverage layer seals it as source_unavailable, never confirmed_absent.
        response_ok = raw is not None
        df = (raw.copy() if response_ok
              else pd.DataFrame(columns=["datetime", "content", "title", "channels"]))
        df["src"] = src
        df.attrs["cap_hit"] = response_ok and len(df) >= self._NEWS_CAP
        df.attrs["response_ok"] = response_ok
        return df

    def _news_content_hashes(self, df: pd.DataFrame):
        """M5: dedup key via the SHARED text_store canonical hasher — so a
        fetcher-side overlap dedup is bit-identical to store-side idempotence."""
        from data_infra.text_store import content_hash_for
        cols = list(df.columns)
        return df.apply(lambda r: content_hash_for("news", r, cols), axis=1)

    def fetch_news_covered(self, src: str, start: str, end: str, *,
                           min_window_seconds: int = 60,
                           _depth: int = 0) -> tuple[pd.DataFrame, dict]:
        """Recursive window-split on the 1500 cap → complete coverage + a TYPED
        coverage artifact (NF design B2 / review M1). Bisects [start, end] whenever
        a window hits the cap so no flash is silently truncated. Serial (family rule).

        Returns (deduped_frame, coverage) where coverage = {src, start, end,
        rows, complete, windows:[...]}. ``complete`` is False iff any window was
        still capped at the minimum span (cap_at_min_window) — the caller MUST
        NOT freeze decision input nor advance a watermark on an incomplete pull.
        Overlap dedup uses the shared text_store content hash (M5).
        """
        t0, t1 = pd.Timestamp(start), pd.Timestamp(end)
        df = self.fetch_news(src, start, end)
        cap_hit = bool(df.attrs.get("cap_hit"))
        # review M1: a failed API response propagates as source_available=False so
        # the sealed coverage artifact is source_unavailable, not confirmed_absent.
        response_ok = bool(df.attrs.get("response_ok", True))
        span = (t1 - t0).total_seconds()
        if not response_ok or not cap_hit or span <= min_window_seconds:
            if not response_ok:
                status = "source_unavailable"
                logging.warning("news %s [%s,%s] API returned no response — coverage "
                                "SOURCE_UNAVAILABLE (not confirmed-absent)", src, start, end)
            elif cap_hit:
                status = "cap_at_min_window"
                logging.warning("news %s [%s,%s] capped at min window (%d rows) "
                                "— coverage INCOMPLETE", src, start, end, len(df))
            else:
                status = "ok"
            windows = [{"start": start, "end": end, "rows": len(df),
                        "cap_hit": cap_hit, "status": status, "depth": _depth}]
            return df, {"src": src, "start": start, "end": end, "rows": len(df),
                        "complete": (status == "ok"), "source_available": response_ok,
                        "windows": windows}
        # bisect into two GENUINELY-OVERLAPPING halves that share the boundary
        # second (right starts at mid, not mid+1s); the shared-hash dedup below
        # absorbs the overlap so an API that is inclusive on both ends can't lose
        # or double-count the boundary second. Record the capped parent as 'split'.
        split_entry = {"start": start, "end": end, "rows": len(df),
                       "cap_hit": True, "status": "split", "depth": _depth}
        mid = t0 + (t1 - t0) / 2
        mid_s = mid.strftime("%Y-%m-%d %H:%M:%S")
        left_df, left_c = self.fetch_news_covered(
            src, start, mid_s, min_window_seconds=min_window_seconds, _depth=_depth + 1)
        right_df, right_c = self.fetch_news_covered(
            src, mid_s, end, min_window_seconds=min_window_seconds, _depth=_depth + 1)
        both = pd.concat([left_df, right_df], ignore_index=True)
        if len(both):
            both = both[~self._news_content_hashes(both).duplicated()].reset_index(drop=True)
        windows = [split_entry] + left_c["windows"] + right_c["windows"]
        return both, {"src": src, "start": start, "end": end, "rows": len(both),
                      "complete": left_c["complete"] and right_c["complete"],
                      "source_available": (left_c.get("source_available", True)
                                           and right_c.get("source_available", True)),
                      "windows": windows}

    def fetch_anns_d_paged(self, ann_date: str, *, page_size: int = 2000,
                           max_pages: int = 6) -> pd.DataFrame:
        """anns_d with offset pagination (busy days exceed the 2000/call cap).

        impl-review M3: the returned frame carries ``df.attrs['truncated']`` —
        True when max_pages was exhausted with the last page still FULL (the
        day may extend beyond what was fetched); callers treating the pull as
        complete MUST check it and fail the day, not silently under-ingest.
        """
        frames: list[pd.DataFrame] = []
        seen_first: set[str] = set()
        truncated = False
        for page in range(max_pages):
            df = self._safe_api_call(
                self.pro.anns_d,
                ann_date=ann_date,
                limit=page_size,
                offset=page * page_size,
                fields="ann_date,ts_code,name,title,url,rec_time",
            )
            if df is None or df.empty:
                truncated = False
                break
            marker = f"{df.iloc[0]['ts_code']}|{df.iloc[0]['title']}"
            if marker in seen_first:  # offset unsupported -> same page again
                truncated = False
                break
            seen_first.add(marker)
            frames.append(df)
            if len(df) < page_size:
                truncated = False
                break
            truncated = True          # full page; a later break clears it
        if not frames:
            out = pd.DataFrame()
        else:
            out = pd.concat(frames, ignore_index=True).drop_duplicates()
        out.attrs["truncated"] = truncated
        return out
