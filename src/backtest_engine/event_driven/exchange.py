"""
A-Share Exchange Simulator for Event-Driven Backtester

Handles:
- Multi-tier price limits (Main/ST/ChiNext/STAR/BSE, date-aware)
- Tradability checks (suspension, limit-up/down, IPO period)
- Transaction cost calculation (date-aware stamp tax)
- Volume limits (default 25% of daily volume)
- Slippage models
- Lot sizes (100 for main/ChiNext/STAR, 200 for BSE)
- ST stock detection from st_stocks.txt
"""

import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ─── Configuration ────────────────────────────────────────────────

@dataclass
class CostBreakdown:
    """Itemized cost breakdown from Exchange.compute_*_cost_breakdown().

    All values are in ¥ (absolute amounts, not rates). Use ``total`` as
    the single source of truth for cash deduction in ``portfolio.buy()``
    or ``portfolio.sell()``. The individual components are available for
    audit and cost-attribution analysis.
    """
    commission: float
    stamp: float
    transfer_fee: float
    total: float


@dataclass
class CostConfig:
    """Transaction cost configuration.

    The DEFAULT values match JoinQuant's standard ``OrderCost`` so a local
    backtest run with default costs produces results directly comparable to
    a JoinQuant deployment. Specifically the JoinQuant defaults are:

      OrderCost(open_tax=0, close_tax=0.001, open_commission=2.5/10000,
                close_commission=2.5/10000, close_today_commission=0,
                min_commission=5)

    Which translates to: stamp tax 0.1% constant on sells (no 2023-08-28
    cut), 2.5 bps commission both sides, no transfer fee, ¥5 min commission.

    For backtests intended to reflect the ACTUAL Chinese exchange rules
    (including the 2023-08-28 stamp-tax cut from 0.1% → 0.05% and the
    0.2 bps transfer fee on both sides), use the
    ``CostConfig.realistic_china()`` factory instead.

    Attributes:
        buy_commission: Commission rate for buy orders (JQ default 0.025%).
        sell_commission: Commission rate for sell orders (JQ default 0.025%).
        stamp_tax: Stamp tax rate on sells. JQ default is 0.1% (constant);
            ``realistic_china()`` uses 0.05% post-2023-08-28.
        stamp_tax_pre_20230828: Pre-2023 stamp tax. JQ default ignores the
            change (same as ``stamp_tax``); ``realistic_china()`` uses 0.1%.
        min_commission: Minimum commission per trade in ¥.
        transfer_fee: Transfer fee (过户费) rate. JoinQuant does NOT model
            it (default 0); ``realistic_china()`` charges 0.002% (2 bps).

    Defaults changed 2026-05-22 from realistic-China to JoinQuant. See
    CLAUDE.md §3 (Exchange cost source of truth + Exchange default slippage)
    for the rationale: JoinQuant is the deployment medium, so local backtest
    defaults align with JoinQuant defaults. The realistic-China preset
    remains available via the factory below.
    """
    buy_commission: float = 0.00025
    sell_commission: float = 0.00025
    stamp_tax: float = 0.001                 # JoinQuant close_tax constant
    stamp_tax_pre_20230828: float = 0.001    # JoinQuant ignores the 2023 cut
    min_commission: float = 5.0
    transfer_fee: float = 0.0                # JoinQuant does NOT model 过户费

    @classmethod
    def joinquant_default(cls) -> 'CostConfig':
        """Explicit JoinQuant default — same as ``CostConfig()``."""
        return cls()

    @classmethod
    def realistic_china(cls) -> 'CostConfig':
        """Actual Chinese exchange rules: 2023-08-28 stamp tax cut +
        0.2 bps transfer fee on both sides. Use this for backtests intended
        to reflect the real exchange rather than a JoinQuant simulator.

        Returns:
            CostConfig with stamp_tax=0.0005 (post-2023), stamp_tax_pre=0.001,
            transfer_fee=0.00002.
        """
        return cls(
            buy_commission=0.00025,
            sell_commission=0.00025,
            stamp_tax=0.0005,
            stamp_tax_pre_20230828=0.001,
            min_commission=5.0,
            transfer_fee=0.00002,
        )


# ─── Slippage Models ─────────────────────────────────────────────

class SlippageModel(ABC):
    """Base slippage model. Override for custom behavior."""

    @abstractmethod
    def apply(self, price: float, direction: str,
              value: float, row: pd.Series) -> float:
        """Apply slippage to a fill price.

        Args:
            price: Raw fill price (open or close).
            direction: 'buy' or 'sell'.
            value: Trade value in ¥.
            row: Full daily data row for the stock.

        Returns:
            Adjusted price after slippage.
        """


class NoSlippage(SlippageModel):
    """No slippage — fills at exact price."""

    def apply(self, price: float, direction: str,
              value: float, row: pd.Series) -> float:
        """No adjustment.

        Args:
            price: Raw fill price.
            direction: Trade direction.
            value: Trade value.
            row: Daily data row.

        Returns:
            Unchanged price.
        """
        return price


class FixedSlippage(SlippageModel):
    """Fixed per-share slippage (matches JoinQuant's FixedSlippage convention).

    Adds/subtracts a fixed ¥-amount per share from the fill price:
      buy: price + spread, sell: max(price - spread, 0.01).

    The default ``spread=0.01`` ¥ per share matches JoinQuant's convention.
    Use ``spread=0.02`` for conservative stress-testing.

    Args:
        spread: Price spread per share in ¥ (default 0.01).
    """

    def __init__(self, spread: float = 0.01):
        self.spread = spread

    def apply(self, price: float, direction: str,
              value: float, row: pd.Series) -> float:
        """Apply fixed spread.

        Args:
            price: Raw fill price.
            direction: 'buy' or 'sell'.
            value: Trade value.
            row: Daily data row.

        Returns:
            Price +/- spread.
        """
        if direction == 'buy':
            return price + self.spread
        return max(price - self.spread, 0.01)


class PctSlippage(SlippageModel):
    """Percentage-based slippage.

    Args:
        rate: Slippage rate (e.g., 0.001 = 0.1%).
    """

    def __init__(self, rate: float = 0.001):
        self.rate = rate

    def apply(self, price: float, direction: str,
              value: float, row: pd.Series) -> float:
        """Apply percentage slippage.

        Args:
            price: Raw fill price.
            direction: 'buy' or 'sell'.
            value: Trade value.
            row: Daily data row.

        Returns:
            Price * (1 +/- rate).
        """
        if direction == 'buy':
            return price * (1 + self.rate)
        return price * (1 - self.rate)


# ─── Named slippage presets (added 2026-05-22) ────────────────────
#
# JOINQUANT_DEFAULT_SLIPPAGE matches JoinQuant's set_slippage(FixedSlippage(3/10000))
# — 0.0003 ¥/share = ~0.3 bps on a ¥10 stock. This is the NEW Exchange()
# default for JoinQuant-deployment parity (was PctSlippage(0.001) = 10 bps).
#
# CONSERVATIVE_SLIPPAGE_10BPS is the prior default, preserved as a named
# constant for research code that genuinely needs the conservative model.
# Pass it explicitly: ``Exchange(slippage_model=CONSERVATIVE_SLIPPAGE_10BPS)``.
#
# IMPORTANT — DOCUMENTATION-ERROR PROTECTION: PctSlippage(0.0003) is NOT the
# same as FixedSlippage(0.0003). PctSlippage(0.0003) = 0.03% = 3 bps, while
# FixedSlippage(0.0003) = ~0.3 bps for a ¥10 stock. The two differ by ~10×
# for typical microcap prices. Tests assert this in
# tests/backtest_engine/test_joinquant_parity.py.
JOINQUANT_DEFAULT_SLIPPAGE: 'SlippageModel'   # forward type ref; instantiated below
CONSERVATIVE_SLIPPAGE_10BPS: 'SlippageModel'


# ─── Exchange ─────────────────────────────────────────────────────

# Stamp tax change date threshold
_STAMP_TAX_CHANGE_DATE = pd.Timestamp('2023-08-28')


def _round_half_up_2dp(value: float) -> float:
    """Round to 2 decimal places using round-half-up (not banker's rounding).

    This matches the Shanghai/Shenzhen exchange convention for computing
    daily limit-up and limit-down prices. Python's built-in ``round()``
    uses round-half-to-even, which misclassifies borderline `.xx5` values
    (e.g., ``round(10.125, 2)`` → ``10.12`` instead of ``10.13``).

    Uses ``Decimal(str(value))`` to avoid float→Decimal representation
    errors per Codex cross-review finding #9.
    """
    from decimal import Decimal, ROUND_HALF_UP
    return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
# Board reform dates
_CHINEXT_REFORM_DATE = pd.Timestamp('2020-08-24')
_STAR_LAUNCH_DATE = pd.Timestamp('2019-07-22')
# 全面注册制 (comprehensive registration system) main-board reform: the first
# batch of registration-based main-board IPOs listed 2023-04-10. A main-board
# stock listed on/after this date has NO price limit for its first 5 trading
# days (then ±10%). BEFORE it, a main-board IPO's first day was the old
# +44% / −36% cap (an ASYMMETRIC but REAL, published limit) — NOT a no-limit day.
_MAIN_BOARD_REGISTRATION_DATE = pd.Timestamp('2023-04-10')

# stk_limit no-limit SENTINEL: on a genuine no-limit stock-day Tushare publishes
# an UNREACHABLE band, NOT NaN — up_limit ≈ 1e6 (main/ChiNext/STAR first days)
# or 99999.99 (BSE listing day), down_limit ≈ 0.01/0.00. The up-floor sits far
# above the highest real A-share limit (~¥3k for 贵州茅台) and just below the
# 99999.99 BSE sentinel, so it can never collide with a real limit price. See
# resolve_limit_prices + workspace/scripts/diag_stk_limit_nolimit_days.py.
_NO_LIMIT_UP_SENTINEL_FLOOR = 99999.0
_NO_LIMIT_DOWN_SENTINEL_CEIL = 0.01


class Exchange:
    """A-share exchange simulator.

    Handles tradability checks, limit detection, cost computation,
    and volume constraints. All checks are date-aware.

    Args:
        cost_config: Transaction cost parameters.
        st_data_path: Path to st_stocks.txt (Qlib instrument format).
        feeder: QlibDataFeeder instance for list_date lookups.
        volume_limit: Max fraction of daily volume for a single order.
        slippage_model: Slippage model to use.
    """

    def __init__(self, cost_config: Optional[CostConfig] = None,
                 st_data_path: Optional[str] = None,
                 feeder: Optional['QlibDataFeeder'] = None,
                 volume_limit: float = 0.25,
                 slippage_model: Optional[SlippageModel] = None,
                 suspension_ranges_path: Optional[str] = None):
        """Initialize the exchange simulator.

        Args:
            cost_config: Transaction cost parameters.
            st_data_path: Path to st_stocks.txt (Qlib instrument format).
            feeder: QlibDataFeeder instance for list_date lookups.
            volume_limit: Max fraction of daily volume for a single order.
            slippage_model: Slippage model to use.
            suspension_ranges_path: Path to ``data/market/suspension/suspension_ranges.parquet``
                (P1-1). When provided, is_suspended() prefers the authoritative
                Tushare suspend_d table and falls back to ``vol == 0`` only
                when the table lacks coverage for the (ts_code, date) query.
                When None (default), the backtester uses the legacy
                ``vol == 0`` proxy only.
        """
        self.cost_config = cost_config or CostConfig()
        self.volume_limit = volume_limit
        # 2026-05-22: Default slippage changed from PctSlippage(0.001)=10bps
        # to FixedSlippage(0.0003)=0.3bps to align with JoinQuant's standard
        # FixedSlippage(3/10000), which is the deployment medium for this
        # project. Research that wants the prior conservative default must
        # pass slippage_model=CONSERVATIVE_SLIPPAGE_10BPS (or equivalent)
        # explicitly. Zero-cost research must still explicitly pass
        # slippage_model=NoSlippage(). See CLAUDE.md §3 for the rationale.
        self.slippage_model = slippage_model if slippage_model is not None else FixedSlippage(0.0003)
        self._feeder = feeder

        # Load ST ranges
        self._st_map: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]] = {}
        if st_data_path:
            self._st_map = self._load_st_ranges(st_data_path)

        # P1-1: Load authoritative suspension lookup if available
        self._suspension_lookup = None
        if suspension_ranges_path:
            try:
                # Import here to avoid circular imports on exchange module load
                import sys as _sys
                from pathlib import Path as _Path
                _src_root = _Path(__file__).resolve().parents[3] / "src"
                if str(_src_root) not in _sys.path:
                    _sys.path.insert(0, str(_src_root))
                from data_infra.provider_metadata import SuspensionLookup
                self._suspension_lookup = SuspensionLookup.from_ranges_file(suspension_ranges_path)
                logger.info("Loaded authoritative suspension lookup from %s", suspension_ranges_path)
            except Exception as exc:
                logger.warning(
                    "Failed to load suspension lookup at %s: %s. "
                    "Falling back to vol==0 proxy.",
                    suspension_ranges_path,
                    exc,
                )
                self._suspension_lookup = None

    def _load_st_ranges(self, path: str) -> dict:
        """Load st_stocks.txt into a dict for fast is_st() queries.

        Note: st_stocks.txt uses Qlib format (000004_SZ) with tab
        delimiter and YYYY-MM-DD dates. All parquet data uses Tushare
        format (000004.SZ). Convert on load.

        Args:
            path: Path to st_stocks.txt.

        Returns:
            Dict {ts_code: [(start, end), ...]} of ST periods.
        """
        st_map = defaultdict(list)
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) < 3:
                    continue
                qlib_code, start_str, end_str = parts[0], parts[1], parts[2]
                ts_code = qlib_code.replace('_', '.')  # 000004_SZ -> 000004.SZ
                start = pd.Timestamp(start_str)
                end = pd.Timestamp(end_str)
                st_map[ts_code].append((start, end))
        logger.info('Loaded ST ranges for %d stocks', len(st_map))
        return dict(st_map)

    # ─── ST Detection ─────────────────────────────────────────────

    def is_st(self, code: str, date: pd.Timestamp) -> bool:
        """Check if a stock is ST on the given date.

        Args:
            code: Tushare ts_code (e.g., '000001.SZ').
            date: Trading date.

        Returns:
            True if stock is ST/\u002AST on this date.
        """
        ranges = self._st_map.get(code, [])
        for start, end in ranges:
            if start <= date <= end:
                return True
        return False

    # ─── Price Limits ─────────────────────────────────────────────

    def get_limit_pct(self, code: str, is_st: bool,
                      date: pd.Timestamp) -> float:
        """Get price limit percentage for a stock on a given date.

        Multi-tier limits:
        - ST: ±5%
        - ChiNext (300/301): ±20% since 2020-08-24, else ±10%
        - STAR (688/689): ±20% since 2019-07-22, else ±10%
        - BSE (83/87/43/92): ±30%
        - Main board: ±10%

        Args:
            code: Tushare ts_code (e.g., '300001.SZ').
            is_st: Whether stock is ST on this date.
            date: Trading date.

        Returns:
            Limit percentage as float (e.g., 0.10 for ±10%).
        """
        if is_st:
            return 0.05
        prefix = code[:3]
        if prefix in ('300', '301'):  # ChiNext (创业板)
            return 0.20 if date >= _CHINEXT_REFORM_DATE else 0.10
        if prefix in ('688', '689'):  # STAR (科创板)
            return 0.20 if date >= _STAR_LAUNCH_DATE else 0.10
        if code[:2] in ('83', '87', '43', '92'):  # BSE (北交所)
            return 0.30
        return 0.10  # Main board (主板) default

    def compute_limit_prices(self, pre_close: float,
                             limit_pct: float) -> tuple[float, float]:
        """Compute limit-up and limit-down prices.

        Uses Shanghai/Shenzhen exchange convention: **round half up** to
        2 decimal places (分). Python's default ``round()`` uses banker's
        rounding (round-half-to-even) which can misclassify borderline
        limit prices by ±0.01 ¥. The explicit round-half-up here matches
        the exchange's published convention.

        Args:
            pre_close: Previous close price (ex-rights adjusted on ex-dates).
            limit_pct: Limit percentage (e.g., 0.10).

        Returns:
            (limit_up_price, limit_down_price) tuple.
        """
        limit_up = _round_half_up_2dp(pre_close * (1 + limit_pct))
        limit_down = _round_half_up_2dp(pre_close * (1 - limit_pct))
        limit_down = max(limit_down, 0.01)  # Minimum price is 1分
        return limit_up, limit_down

    def resolve_limit_prices(self, row: pd.Series, code: str,
                             date: pd.Timestamp) -> tuple[float, float]:
        """Resolve ``(limit_up, limit_down)`` for a stock-day.

        **Primary source — Tushare ``stk_limit``**: when the row carries
        ``up_limit`` / ``down_limit`` (the exchange's own published daily
        limit prices, materialized as the ``$up_limit`` / ``$down_limit``
        Qlib bins), those values are used verbatim. They already encode the
        exact fen-rounding and the ex-rights adjustment the exchange applied,
        and they carry special regimes the band formula does not (e.g. the
        main-board IPO-first-day ±44% rule).

        **No-limit stock-days use a wide sentinel, NOT NaN**: on genuinely
        no-limit days (ChiNext / STAR / post-2023 main-board first 5 trading
        days; BSE listing day) Tushare publishes ``up_limit ≈ 1e5/1e6`` and
        ``down_limit ≈ 0.01/0.00`` — an unreachable band. The primary path
        uses these verbatim, so ``is_limit_up`` / ``is_limit_down`` both return
        False and the stock is correctly treated as freely tradable. (True
        non-stock instruments like indices are the only NaN rows; they never
        reach an order path.) Verified on real 2024 IPOs in
        ``workspace/scripts/diag_stk_limit_nolimit_days.py``.

        **Fallback — computed band**: when the Tushare fields are absent or
        NaN, fall back to ``compute_limit_prices(pre_close, band)``. Verified
        coverage holes that require this fallback (see
        ``workspace/scripts/diag_stk_limit_coverage.py``): Beijing Stock
        Exchange names during the 2021 launch window, sparse IPO no-limit days
        in older data, and a few legacy main-board stocks. Recent years (2024+)
        have zero holes.

        Both prices are raw (unadjusted), matching the raw ``close`` the
        limit checks compare against.
        """
        up = row.get('up_limit')
        down = row.get('down_limit')
        if up is not None and down is not None and pd.notna(up) and pd.notna(down):
            return float(up), float(down)
        # Fallback: compute from previous close × regulatory band.
        is_st = self.is_st(code, date)
        limit_pct = self.get_limit_pct(code, is_st, date)
        pre_close = row.get('raw_pre_close', row['pre_close'])
        return self.compute_limit_prices(pre_close, limit_pct)

    def is_limit_up(self, row: pd.Series, code: str,
                    date: pd.Timestamp, price_field: str = 'raw_close') -> bool:
        """Check if a stock is at limit-up at ``price_field`` (default raw_close).

        Cannot buy at limit-up (no sellers). Can still sell.

        ``price_field`` selects WHICH price the gate tests against the limit.
        The execution path passes the actual fill column so the gate matches the
        fill: an OPEN fill passes ``'raw_open'`` → blocks when the daily OPEN is at
        the limit (the daily-bar PROXY for a locked-at-open 一字 / 调仓时涨停). A
        name that opens BELOW the limit and merely CLOSES limit-up was buyable at
        the open, so the default close-based gate would wrongly block it (and would
        use end-of-day info to block an open trade). Caveat: a name that opens AT
        the limit but trades intraday (high>low) is not all-day-locked; blocking it
        is the conservative choice under a daily-bar fill — exact 09:35/open-time
        tradability needs minute or order-book data. Default ``'raw_close'``
        preserves the legacy close-fill semantics.

        Uses Tushare's published ``up_limit`` when available, else the computed
        band (see :meth:`resolve_limit_prices`).

        Args:
            row: Daily data row with the fill price (+ optional 'up_limit').
            code: Stock ts_code.
            date: Trading date.
            price_field: Fill column to test (e.g. 'raw_open' / 'raw_close' / 'raw_avg').

        Returns:
            True if ``price_field`` is at the limit-up price.
        """
        price = row.get(price_field)
        if price is None or pd.isna(price):           # NaN/absent fill field -> close fallback
            price = row.get('raw_close', row.get('close'))
        limit_up, _ = self.resolve_limit_prices(row, code, date)
        return bool(pd.notna(price) and abs(price - limit_up) < 0.005)  # within half a fen

    def is_limit_down(self, row: pd.Series, code: str,
                      date: pd.Timestamp, price_field: str = 'raw_close') -> bool:
        """Check if a stock is at limit-down at ``price_field`` (default raw_close).

        Cannot sell at limit-down (no buyers). Can still buy. Symmetric to
        :meth:`is_limit_up`: the execution path passes the fill column so an OPEN
        fill blocks a SELL only when the stock is locked-DOWN at the open. Default
        ``'raw_close'`` preserves the legacy close-fill semantics.

        Uses Tushare's published ``down_limit`` when available, else the computed
        band (see :meth:`resolve_limit_prices`).

        Args:
            row: Daily data row with the fill price (+ optional 'down_limit').
            code: Stock ts_code.
            date: Trading date.
            price_field: Fill column to test (e.g. 'raw_open' / 'raw_close' / 'raw_avg').

        Returns:
            True if ``price_field`` is at the limit-down price.
        """
        price = row.get(price_field)
        if price is None or pd.isna(price):           # NaN/absent fill field -> close fallback
            price = row.get('raw_close', row.get('close'))
        _, limit_down = self.resolve_limit_prices(row, code, date)
        return bool(pd.notna(price) and abs(price - limit_down) < 0.005)

    def is_suspended(
        self,
        row: pd.Series,
        code: Optional[str] = None,
        date: Optional[pd.Timestamp] = None,
    ) -> bool:
        """Check if a stock is suspended.

        P1-1 contract: prefer the authoritative Tushare suspend_d lookup
        when available (requires ``suspension_ranges_path`` to have been
        passed to the Exchange constructor AND ``code`` + ``date`` args to
        be provided here). Fall back to the legacy ``vol == 0`` proxy when
        the authoritative table lacks coverage for the (code, date) query.

        Args:
            row: Daily data row with 'vol' column (used for fallback).
            code: Stock ts_code (optional; required for authoritative lookup).
            date: Trading date (optional; required for authoritative lookup).

        Returns:
            True if stock is suspended.
        """
        if self._suspension_lookup is not None and code is not None and date is not None:
            result = self._suspension_lookup.is_suspended(code, date)
            if result is not None:
                return result
        vol = row.get('vol', 0)
        if pd.isna(vol) or vol == 0:
            return True
        return False

    def is_ipo_period(self, code: str, date: pd.Timestamp) -> bool:
        """Check if a stock is in its nominal IPO trading-day window.

        ⚠ NOT a no-limit-day predicate — DO NOT use it to bypass the limit
        gate. This answers "is the stock inside its board's IPO window" from
        board + days-since-listing ONLY; it does NOT know the listing-date
        regime, so it treats a *pre-registration-reform* main-board / ChiNext
        FIRST day (the old +44% / −36% cap, a REAL published limit) as if it
        were in-window. Buying a name locked at that +44% limit has no seller.
        Use :meth:`is_true_no_limit_day` for the buy-gate bypass (GPT
        cross-review 2026-06-22, Major-2). Retained only as the nominal-window
        helper / for diagnostics.

        Nominal IPO windows (by board, days since listing):
        - Main Board (沪深主板): 1 day (listing day only)
        - ChiNext (创业板, 300/301): 5 days since 2020-08-24
        - STAR (科创板, 688/689): 5 days since launch
        - BSE (北交所): 1 day

        Args:
            code: Stock ts_code.
            date: Trading date.

        Returns:
            True if stock is in its IPO no-limit period.
        """
        if self._feeder is None:
            return False

        sb = self._feeder.get_stock_basic()
        stock = sb[sb['ts_code'] == code]
        if stock.empty:
            return False

        list_date = stock.iloc[0]['list_date']
        if pd.isna(list_date):
            return False

        # Count trading days since listing.
        # count_trading_days(list_date, date) is INCLUSIVE on both ends,
        # so listing day counts as 1. Verified against
        # data_feeder.py:307-309 (2026-04-14, P1-2 verification pass).
        #
        # Convention:
        #   ChiNext (300/301) post-2020-08-24 reform: 5 trading days
        #   STAR (688/689): 5 trading days
        #   Main board, BSE: 1 trading day (listing day only)
        # All counts include the listing day itself.
        trading_days_since = self._feeder.count_trading_days(list_date, date)

        prefix = code[:3]
        if prefix in ('300', '301') and date >= _CHINEXT_REFORM_DATE:
            return trading_days_since <= 5
        if prefix in ('688', '689'):
            return trading_days_since <= 5
        # Main board and BSE: 1 day (listing day only)
        return trading_days_since <= 1

    def is_true_no_limit_day(self, code: str, date: pd.Timestamp,
                             row: Optional[pd.Series] = None) -> bool:
        """Return True iff this stock-day genuinely has NO price limit.

        This is the buy-gate's no-limit predicate, and it REPLACES the old
        ``is_ipo_period`` bypass in :meth:`can_buy`. ``is_ipo_period`` answered
        "is this stock inside its nominal IPO trading-day window" from board +
        days-since-listing ONLY — so it treated a *pre-registration-reform*
        main-board (or pre-2020-reform ChiNext) FIRST day as no-limit and
        wrongly let :meth:`can_buy` buy a name locked at its old +44% / −36%
        first-day limit. That first-day cap is a REAL published limit (Tushare
        carries it in ``up_limit`` / ``down_limit``; e.g. 002728.SZ 2014-07-31
        → up_limit 20.16 off a 14.0 issue price), so a buyer at the locked limit
        has no seller. (GPT cross-review 2026-06-22, Major-2.)

        A day is genuinely no-limit only when one of the following holds:

        1. **Published no-limit sentinel (primary, definitive).** On a real
           no-limit stock-day Tushare's ``stk_limit`` publishes an UNREACHABLE
           band — ``up_limit ≈ 1e6`` (main/ChiNext/STAR) or ``99999.99`` (BSE
           listing day) and ``down_limit ≈ 0.01/0.00`` — NOT NaN. When the row
           carries that sentinel the day is no-limit regardless of board/date.
           (On such a row :meth:`is_limit_up` already returns False, so the buy
           gate would not even block — but the predicate stands alone.)

        2. **Confirmed board + listing-date regime (fallback for ``stk_limit``
           coverage holes).** When the published field is absent/NaN the
           computed band can FALSELY flag a no-limit IPO day that happens to sit
           on the steady-state ±10/20% boundary as a limit. The regime check
           rescues exactly the windows that are genuinely no-limit, keyed on the
           LISTING-date regime (not the trade date):

             - ChiNext (300/301) listed on/after 2020-08-24 → first 5 trading days
             - STAR (688/689) → first 5 trading days (registration-based since launch)
             - Main board listed on/after 2023-04-10 (全面注册制) → first 5 days
             - BSE (83/87/43/92, incl. 920xxx) → listing day only

           It returns False for the OLD main-board / pre-2020 ChiNext +44% / −36%
           first day (``list_date`` before the board's reform date): that cap is
           a real published limit, not a no-limit window.

        Args:
            code: Stock ts_code.
            date: Trading date.
            row: Daily data row (optional). When present, its ``up_limit`` /
                ``down_limit`` are checked for the no-limit sentinel (branch 1).

        Returns:
            True iff the stock-day has no enforceable price limit.
        """
        # 1. Published no-limit sentinel — definitive when present.
        if row is not None:
            up = row.get('up_limit')
            down = row.get('down_limit')
            if (up is not None and down is not None
                    and pd.notna(up) and pd.notna(down)
                    and float(up) >= _NO_LIMIT_UP_SENTINEL_FLOOR
                    and float(down) <= _NO_LIMIT_DOWN_SENTINEL_CEIL):
                return True

        # 2. Board + listing-date regime fallback (stk_limit coverage holes).
        if self._feeder is None:
            return False
        sb = self._feeder.get_stock_basic()
        stock = sb[sb['ts_code'] == code]
        if stock.empty:
            return False
        list_date = stock.iloc[0]['list_date']
        if pd.isna(list_date):
            return False

        # count_trading_days is INCLUSIVE on both ends → listing day == 1.
        trading_days_since = self._feeder.count_trading_days(list_date, date)
        if trading_days_since < 1:
            return False  # date precedes listing — not an IPO no-limit day

        prefix = code[:3]
        if prefix in ('300', '301'):
            # ChiNext: 5-day no-limit window ONLY for post-reform listings;
            # a pre-reform ChiNext first day was the old +44% cap.
            return list_date >= _CHINEXT_REFORM_DATE and trading_days_since <= 5
        if prefix in ('688', '689'):
            # STAR has been registration-based since its 2019-07-22 launch.
            return trading_days_since <= 5
        if code[:2] in ('83', '87', '43', '92'):
            # BSE (北交所, incl. 920xxx via the '92' prefix): listing day only.
            return trading_days_since <= 1
        # Main board: 5-day no-limit window ONLY for 全面注册制 listings;
        # a pre-reform main-board first day was the old +44% cap.
        return list_date >= _MAIN_BOARD_REGISTRATION_DATE and trading_days_since <= 5

    # ─── Tradability ──────────────────────────────────────────────

    def can_buy(self, row: pd.Series, code: str,
                date: pd.Timestamp, price_field: str = 'raw_close',
                limit_gate: str = 'fill_price') -> bool:
        """Check if a stock can be bought.

        Cannot buy if:
        - Suspended (vol == 0)
        - Limit-up (no sellers), UNLESS the day is genuinely no-limit
          (see :meth:`is_true_no_limit_day` — a real no-limit IPO window or a
          published no-limit sentinel; NOT the old main-board +44% first day)

        ``limit_gate`` selects the limit-up test: ``'fill_price'`` (default) blocks
        when ``price_field`` is at the limit (correct for open/close fills);
        ``'all_day_lock'`` blocks only on a 一字 day (high==low==limit) — used for
        the daily-AVERAGE fill mode. ``price_field`` is forwarded to
        :meth:`is_limit_up`; the execution path passes the fill column (e.g.
        ``'raw_open'`` for a 09:35 fill) so the gate reflects buyability AT THE
        FILL, not at the close. Default ``'raw_close'`` preserves legacy semantics.

        Args:
            row: Daily data row.
            code: Stock ts_code.
            date: Trading date.
            price_field: Fill column to test against the limit.

        Returns:
            True if stock is buyable.
        """
        if self.is_suspended(row, code=code, date=date):
            return False
        locked = (self.is_all_day_limit_up(row, code, date) if limit_gate == 'all_day_lock'
                  else self.is_limit_up(row, code, date, price_field=price_field))
        if locked and not self.is_true_no_limit_day(code, date, row):
            return False
        return True

    def is_all_day_limit_up(self, row: pd.Series, code: str, date: pd.Timestamp) -> bool:
        """一字涨停: the bar never traded away from the upper limit
        (high == low == up_limit) -> genuinely unbuyable ALL DAY. Used for the
        daily-AVERAGE fill mode (jq_daily_avg), where the synthetic avg price is
        not itself a tradability state (raw_avg < up_limit can still be locked,
        and raw_avg == up_limit can have traded). GPT cross-review Major-1."""
        up, _ = self.resolve_limit_prices(row, code, date)
        low = row.get('raw_low', row.get('low'))
        high = row.get('raw_high', row.get('high'))
        if low is None or high is None or pd.isna(low) or pd.isna(high):
            return False
        return abs(low - up) < 0.005 and abs(high - up) < 0.005

    def is_all_day_limit_down(self, row: pd.Series, code: str, date: pd.Timestamp) -> bool:
        """一字跌停: high == low == down_limit -> unsellable all day (avg-fill gate)."""
        _, down = self.resolve_limit_prices(row, code, date)
        low = row.get('raw_low', row.get('low'))
        high = row.get('raw_high', row.get('high'))
        if low is None or high is None or pd.isna(low) or pd.isna(high):
            return False
        return abs(low - down) < 0.005 and abs(high - down) < 0.005

    def can_sell(self, row: pd.Series, code: str,
                 date: pd.Timestamp, price_field: str = 'raw_close',
                 limit_gate: str = 'fill_price') -> bool:
        """Check if a stock can be sold.

        Cannot sell if:
        - Suspended (vol == 0)
        - Limit-down (no buyers)

        ``limit_gate`` mirrors :meth:`can_buy`: ``'fill_price'`` blocks when
        ``price_field`` is at the down-limit; ``'all_day_lock'`` blocks only on a
        一字 down day. ``price_field`` is forwarded to :meth:`is_limit_down`; the
        execution path passes the fill column so an OPEN fill blocks a sell only
        when locked-down at the open. Default ``'raw_close'`` preserves legacy semantics.

        Args:
            row: Daily data row.
            code: Stock ts_code.
            date: Trading date.
            price_field: Fill column to test against the limit.
            limit_gate: 'fill_price' (default) or 'all_day_lock'.

        Returns:
            True if stock is sellable.
        """
        if self.is_suspended(row, code=code, date=date):
            return False
        locked = (self.is_all_day_limit_down(row, code, date) if limit_gate == 'all_day_lock'
                  else self.is_limit_down(row, code, date, price_field=price_field))
        if locked:
            return False
        return True

    # ─── Volume Constraints ───────────────────────────────────────

    def max_buyable_value(self, row: pd.Series, price_field: str = 'raw_open') -> float:
        """Maximum value that can be bought for a single stock.

        Capped at volume_limit fraction of daily volume, valued at the FILL price
        (``price_field``) — the execution path passes the fill column so the cap is
        consistent with the fill (close-fill -> raw_close, avg-fill -> raw_avg),
        not always the open. vol is in 手 (lots of 100 shares). GPT R2 Major-1.

        Args:
            row: Daily data row with 'vol' and the fill price.
            price_field: fill column to value the cap at (default 'raw_open').

        Returns:
            Maximum buy value in ¥ (0 if vol or price is missing/non-positive).
        """
        vol = row.get('vol', 0)
        if pd.isna(vol) or vol <= 0:
            return 0.0
        price = row.get(price_field)
        if price is None or pd.isna(price) or price <= 0:
            price = row.get('raw_open', row.get('open'))
        if price is None or pd.isna(price) or price <= 0:
            return 0.0
        max_shares = vol * 100 * self.volume_limit  # vol in 手 -> shares
        return float(max_shares * price)

    def max_sellable_shares(self, row: pd.Series) -> int:
        """Maximum shares that can be sold in one order.

        Capped at volume_limit fraction of daily volume.

        Args:
            row: Daily data row with 'vol'.

        Returns:
            Maximum sellable shares.
        """
        vol = row.get('vol', 0)
        if pd.isna(vol) or vol <= 0:
            return 0
        return int(vol * 100 * self.volume_limit)

    # ─── Execution ────────────────────────────────────────────────

    def apply_slippage(self, price: float, direction: str,
                       row: pd.Series, value: float = 0) -> float:
        """Apply slippage to a fill price.

        Args:
            price: Raw fill price (open or close).
            direction: 'buy' or 'sell'.
            row: Daily data row.
            value: Trade value (used by some slippage models).

        Returns:
            Adjusted price.
        """
        return self.slippage_model.apply(price, direction, value, row)

    def compute_buy_cost(self, value: float, date: pd.Timestamp) -> float:
        """Compute total cost for a buy trade (scalar, backward-compatible).

        Delegates to ``compute_buy_cost_breakdown()`` and returns the total.
        Existing callers that only need the scalar are unaffected.
        """
        return self.compute_buy_cost_breakdown(value, date).total

    def compute_buy_cost_breakdown(self, value: float, date: pd.Timestamp) -> CostBreakdown:
        """Compute itemized cost for a buy trade.

        Buy cost = commission + transfer fee (no stamp tax on buys).

        This is the **single source of truth** for buy-side costs. The
        engine passes ``breakdown.total`` to ``portfolio.buy()`` so the
        logged cost and the actual cash deduction always agree. See
        ``CLAUDE.md §3`` "Hard Invariants" for the full contract.

        Args:
            value: Trade value in ¥.
            date: Trade date.

        Returns:
            CostBreakdown with commission, stamp=0, transfer_fee, total.
        """
        commission = max(value * self.cost_config.buy_commission,
                         self.cost_config.min_commission)
        transfer_fee = value * self.cost_config.transfer_fee
        return CostBreakdown(
            commission=commission,
            stamp=0.0,
            transfer_fee=transfer_fee,
            total=commission + transfer_fee,
        )

    def compute_sell_cost(self, value: float, date: pd.Timestamp) -> float:
        """Compute total cost for a sell trade (scalar, backward-compatible).

        Delegates to ``compute_sell_cost_breakdown()`` and returns the total.
        Existing callers that only need the scalar are unaffected.
        """
        return self.compute_sell_cost_breakdown(value, date).total

    def compute_sell_cost_breakdown(self, value: float, date: pd.Timestamp) -> CostBreakdown:
        """Compute itemized cost for a sell trade.

        Sell cost = commission + stamp tax (date-aware) + transfer fee.

        This is the **single source of truth** for sell-side costs. The
        engine passes ``breakdown.total`` to ``portfolio.sell()`` so the
        logged cost and the actual cash deduction always agree. See
        ``CLAUDE.md §3`` "Hard Invariants" for the full contract.

        The ``_STAMP_TAX_CHANGE_DATE`` module constant is the single
        location for the 2023-08-28 rate-change boundary. Do NOT
        duplicate this date check elsewhere in the codebase.

        Args:
            value: Trade value in ¥.
            date: Trade date.

        Returns:
            CostBreakdown with commission, stamp, transfer_fee, total.
        """
        commission = max(value * self.cost_config.sell_commission,
                         self.cost_config.min_commission)
        stamp_rate = (self.cost_config.stamp_tax
                      if date >= _STAMP_TAX_CHANGE_DATE
                      else self.cost_config.stamp_tax_pre_20230828)
        stamp = value * stamp_rate
        transfer_fee = value * self.cost_config.transfer_fee
        return CostBreakdown(
            commission=commission,
            stamp=stamp,
            transfer_fee=transfer_fee,
            total=commission + stamp + transfer_fee,
        )

    # ─── Lot Size ─────────────────────────────────────────────────

    def get_lot_size(self, code: str) -> int:
        """Get the lot size for a stock.

        Main board, ChiNext, STAR: 100 shares.
        BSE (北交所): 100 shares (simplified; actual is 100).

        Args:
            code: Stock ts_code.

        Returns:
            Lot size in shares.
        """
        # All A-share boards use 100-share lots
        return 100


# ─── Slippage preset instantiations (must appear after class defs) ───────
#
# These are the actual instances referenced by the forward declarations near
# the top of the module. Strategies should prefer the named presets over
# inlining ``FixedSlippage(0.0003)`` etc. so a future preset change applies
# everywhere consistently.
JOINQUANT_DEFAULT_SLIPPAGE = FixedSlippage(0.0003)
"""JoinQuant FixedSlippage(3/10000) — 0.0003 ¥ per share. This is the
Exchange()-constructor default as of 2026-05-22 for JoinQuant-deployment
parity. ≈ 0.3 bps on a ¥10 stock; ≈ 0.6 bps on a ¥5 stock."""

CONSERVATIVE_SLIPPAGE_10BPS = PctSlippage(0.001)
"""Prior Exchange() default — 0.1% percentage slippage = 10 bps. Use this
when conservatism matters more than JoinQuant parity:
``Exchange(slippage_model=CONSERVATIVE_SLIPPAGE_10BPS)``."""
