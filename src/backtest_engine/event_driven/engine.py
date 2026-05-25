"""
Backtest Engine — Main Simulation Loop

Orchestrates the event-driven backtest:
1. Preloads data and validates inputs
2. Iterates through trading calendar
3. Processes corporate actions, delistings, strategy orders
4. Records daily portfolio state and holdings
5. Builds BacktestResult with 7 DataFrames + metrics
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from .data_feeder import QlibDataFeeder
from .portfolio import Portfolio
from .exchange import Exchange
from .corporate_actions import CorporateActionHandler
from .strategy import Strategy, BacktestContext, Order

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """Complete backtest results with 7 DataFrames for analysis.

    Attributes:
        report: Daily portfolio-level metrics (return, cost, bench, etc.).
        trades: Every executed trade with shares, price, cost, reason.
        order_log: All orders including blocked, with status and detail.
        daily_holdings: Per-stock daily snapshot with weight and P&L.
        corporate_actions: Dividends and bonus shares credited.
        config: Backtest configuration parameters.
    """
    report: pd.DataFrame
    trades: pd.DataFrame
    order_log: pd.DataFrame
    daily_holdings: pd.DataFrame
    corporate_actions: pd.DataFrame
    config: dict = field(default_factory=dict)

    @property
    def equity_curve(self) -> pd.Series:
        """Normalized equity curve starting at 1.0."""
        return (1 + self.report['return']).cumprod()

    @property
    def cumulative_return(self) -> float:
        """Total return over the backtest period."""
        ec = self.equity_curve
        return ec.iloc[-1] - 1 if len(ec) > 0 else 0.0

    @property
    def max_drawdown(self) -> float:
        """Maximum peak-to-trough drawdown (negative value)."""
        ec = self.equity_curve
        if ec.empty:
            return 0.0
        peak = ec.cummax()
        dd = (ec - peak) / peak
        return dd.min()

    @property
    def daily_returns(self) -> pd.Series:
        """Daily returns as a pd.Series indexed by date."""
        return self.report['return']

    @property
    def excess_returns(self) -> pd.Series:
        """Daily excess returns over benchmark."""
        return self.report['return'] - self.report['bench']

    @property
    def summary(self) -> dict:
        """Compute all JoinQuant-compatible performance metrics.

        Metrics alignment with JoinQuant:
        - 胜率/盈亏比/盈利次数/亏损次数: TRADE-level (rotation P&L)
        - 日胜率: daily positive return days
        - Sharpe/Sortino/Vol: daily return series, rf=0

        Returns:
            Dict of 21+ metrics matching JQ's backtest summary.
        """
        # Import lazily to avoid circular imports
        from src.result_analysis.metrics import (
            calculate_total_return, calculate_cagr, calculate_volatility,
            calculate_sharpe_ratio, calculate_sortino_ratio,
            calculate_max_drawdown, calculate_alpha_beta,
            calculate_information_ratio, calculate_win_rate,
        )

        r = self.report['return']
        b = self.report['bench']
        excess = r - b

        alpha, beta = calculate_alpha_beta(r, b)

        # ─── Trade-level metrics (JQ definition) ─────────────
        # Compute per-trade P&L from completed round-trips in trades DF
        trade_returns = self._compute_trade_returns()
        trade_wins = trade_returns[trade_returns > 0]
        trade_losses = trade_returns[trade_returns < 0]

        if len(trade_losses) > 0 and len(trade_wins) > 0:
            pl_ratio = trade_wins.mean() / abs(trade_losses.mean())
        elif len(trade_wins) > 0:
            pl_ratio = float('inf')
        else:
            pl_ratio = 0.0

        trade_win_rate = (
            float(len(trade_wins) / len(trade_returns))
            if len(trade_returns) > 0 else 0.0
        )

        # Max drawdown period
        dd_start, dd_end = self._max_drawdown_period(r)
        excess_dd_start, excess_dd_end = self._max_drawdown_period(excess)

        return {
            '策略收益 (Total Return)': calculate_total_return(r),
            '策略年化收益 (CAGR)': calculate_cagr(r),
            '基准收益 (Benchmark Return)': calculate_total_return(b),
            '超额收益 (Excess Return)': calculate_total_return(excess),
            '阿尔法 (Alpha)': alpha,
            '贝塔 (Beta)': beta,
            '夏普比率 (Sharpe)': calculate_sharpe_ratio(r),
            '索提诺比率 (Sortino)': calculate_sortino_ratio(r),
            '信息比率 (Information Ratio)': calculate_information_ratio(r, b),
            '最大回撤 (Max Drawdown)': abs(calculate_max_drawdown(r)),
            '最大回撤区间 (DD Period)': f'{dd_start},{dd_end}',
            '超额收益最大回撤 (Excess Max DD)': abs(calculate_max_drawdown(excess)),
            '超额收益最大回撤区间': f'{excess_dd_start},{excess_dd_end}',
            '胜率 (Win Rate)': trade_win_rate,
            '日胜率 (Daily Win Rate)': float((r > 0).sum() / max(len(r), 1)),
            '盈亏比 (P/L Ratio)': pl_ratio,
            '盈利次数 (Win Count)': int(len(trade_wins)),
            '亏损次数 (Loss Count)': int(len(trade_losses)),
            '策略波动率 (Strategy Vol)': calculate_volatility(r),
            '基准波动率 (Benchmark Vol)': calculate_volatility(b),
            '日均超额收益 (Avg Daily Excess)': float(excess.mean()),
            '超额收益夏普比率 (Excess Sharpe)': calculate_sharpe_ratio(
                excess, risk_free_rate=0),
            '交易天数 (Trading Days)': len(r),
        }

    def _compute_trade_returns(self) -> pd.Series:
        """Compute per-trade returns from completed sell trades.

        JoinQuant counts each sell as a closed trade and computes
        its return as (sell_value - buy_cost) / buy_cost.
        We approximate using order_log buy/sell pairs.

        Returns:
            pd.Series of per-trade return values.
        """
        if self.trades.empty:
            return pd.Series(dtype=float)

        sells = self.trades[self.trades['direction'] == 'sell']
        if sells.empty:
            return pd.Series(dtype=float)

        # For each sell, look up the avg_cost from daily_holdings
        trade_rets = []
        for _, sell in sells.iterrows():
            code = sell['code']
            sell_price = sell['price']
            sell_date = sell['date']

            # Find avg_cost from day before (the most recent holding snapshot)
            if not self.daily_holdings.empty:
                mask = (
                    (self.daily_holdings['code'] == code) &
                    (self.daily_holdings['date'] < sell_date)
                )
                prev_holdings = self.daily_holdings[mask]
                if not prev_holdings.empty:
                    avg_cost = prev_holdings.iloc[-1]['avg_cost']
                    if avg_cost > 0:
                        trade_ret = (sell_price / avg_cost) - 1
                        trade_rets.append(trade_ret)
                        continue

            # Fallback: look at buy trades for same stock
            buys = self.trades[
                (self.trades['code'] == code) &
                (self.trades['direction'] == 'buy') &
                (self.trades['date'] <= sell_date)
            ]
            if not buys.empty:
                avg_buy_price = (
                    (buys['price'] * buys['shares']).sum() /
                    buys['shares'].sum()
                )
                if avg_buy_price > 0:
                    trade_ret = (sell_price / avg_buy_price) - 1
                    trade_rets.append(trade_ret)

        return pd.Series(trade_rets, dtype=float)


    @staticmethod
    def _max_drawdown_period(returns: pd.Series) -> tuple[str, str]:
        """Find the start and end dates of the maximum drawdown period.

        Args:
            returns: Daily return series.

        Returns:
            (start_date, end_date) as 'YYYY/MM/DD' strings.
        """
        if returns.empty:
            return ('', '')
        cumulative = (1 + returns).cumprod()
        peak = cumulative.expanding(min_periods=1).max()
        dd = (cumulative - peak) / peak
        end_idx = dd.idxmin()
        peak_before = cumulative.loc[:end_idx]
        start_idx = peak_before.idxmax()
        return (start_idx.strftime('%Y/%m/%d'), end_idx.strftime('%Y/%m/%d'))


class BacktestEngine:
    """Main event-driven backtest engine.

    Orchestrates the daily simulation loop. Two fill models supported:

      ``fill_mode='open_close'`` (DEFAULT — closest to live execution)
        Phase 1: ``before_market_open`` → orders fill at OPEN
        Phase 2: ``on_bar`` (EOD)       → orders fill at CLOSE

      ``fill_mode='jq_daily_avg'`` (JOINQUANT DAILY-BACKTEST PARITY)
        Both phases fill at the day's AVERAGE price ``(open + close) / 2``.
        Matches JoinQuant's daily-frequency simulator behavior
        (API doc line 1252: 成交价 = unit-time average ± slippage/2).
        Use this when the strategy will be deployed via JoinQuant's daily
        backtest path and you want local CAGR to predict JoinQuant CAGR.

    Args:
        feeder: QlibDataFeeder instance.
        exchange: Exchange instance.
        strategy: Strategy instance.
        initial_cash: Starting cash balance in ¥.
        corp_action_handler: Optional CorporateActionHandler.
        fill_mode: 'open_close' (default) or 'jq_daily_avg'.
    """

    _FILL_MODES = ('open_close', 'jq_daily_avg')

    def __init__(self, feeder: QlibDataFeeder,
                 exchange: Exchange,
                 strategy: Strategy,
                 initial_cash: float = 100_000,
                 corp_action_handler: Optional[CorporateActionHandler] = None,
                 fill_mode: str = 'open_close'):
        if fill_mode not in self._FILL_MODES:
            raise ValueError(
                f"fill_mode must be one of {self._FILL_MODES}, got {fill_mode!r}"
            )
        self.fill_mode = fill_mode
        self.feeder = feeder
        self.exchange = exchange
        self.strategy = strategy
        self.initial_cash = initial_cash
        self.portfolio = Portfolio(initial_cash)
        self.corp_action_handler = corp_action_handler

        # Internal state
        self._current_date: Optional[pd.Timestamp] = None
        self._prev_total_value = float(initial_cash)
        self._order_log: list[dict] = []
        self._daily_records: list[dict] = []
        self._daily_holdings: list[dict] = []
        self._benchmark_returns: pd.Series = pd.Series(dtype=float)

        # Instrumentation (plan ``snappy-buzzing-meerkat`` v5 verification gate).
        # Per-day wall-clock timing for the full day loop iteration, used by
        # ``EventDrivenBacktester.run`` to write the harness-instrumentation
        # JSON. The validation gate requires p95 < 0.5 sec post-fix.
        self._day_wall_seconds: list[float] = []

    def run(self, start_date: str, end_date: str,
            benchmark_code: Optional[str] = None) -> BacktestResult:
        """Run the backtest.

        Args:
            start_date: Start date ('YYYY-MM-DD' or 'YYYYMMDD').
            end_date: End date ('YYYY-MM-DD' or 'YYYYMMDD').
            benchmark_code: Optional benchmark index code (e.g., '000852.SH').

        Returns:
            BacktestResult with all outputs.

        Raises:
            ValueError: If inputs are invalid.
            FileNotFoundError: If benchmark file not found.
        """
        # Validate inputs
        start, end, calendar = self._validate_inputs(
            start_date, end_date, benchmark_code
        )

        # Get prev_date for before_market_open context
        prev_date = self.feeder.get_prev_trading_day(calendar[0])

        # Preload all daily data (INCLUDING prev_date)
        preload_start = prev_date if prev_date else start
        self.feeder.preload(preload_start, end)

        # Load benchmark
        if benchmark_code:
            self._benchmark_returns = self._load_benchmark(
                benchmark_code, calendar
            )

        total_days = len(calendar)

        # Warmup: fetch day before start for before_market_open context
        prev_day_data = (self._fetch_day_data(prev_date)
                         if prev_date else pd.DataFrame())

        # Initialize strategy
        init_context = BacktestContext(
            date=calendar[0],
            day_data=pd.DataFrame(),
            day_data_indexed=pd.DataFrame(),
            prev_day_data=prev_day_data,
            portfolio=self.portfolio,
            exchange=self.exchange,
            feeder=self.feeder,
            total_days=total_days,
        )
        self.strategy.initialize(init_context)

        # Main loop
        import time as _time
        for i, date in enumerate(calendar):
            _day_t0 = _time.perf_counter()
            self._current_date = date
            day_data = self._fetch_day_data(date)
            # Ensure day_data has the expected structure before setting index
            if not day_data.empty:
                day_indexed = day_data.set_index('ts_code')
            else:
                day_indexed = pd.DataFrame(columns=['ts_code']).set_index('ts_code')

            # Daily progress log
            logger.info(
                'Day %d/%d %s | value=%.2f cash=%.2f pos=%d',
                i + 1, total_days, date.strftime('%Y-%m-%d'),
                self._prev_total_value, self.portfolio.cash,
                len(self.portfolio.positions)
            )

            # Start of day: T+1 unlock, reset daily counters
            self.portfolio.start_new_day()

            # Corporate actions: credit dividends, add bonus shares
            if self.corp_action_handler:
                self.corp_action_handler.process(date, self.portfolio)

            # Delisting check
            self._handle_delistings(day_data, prev_day_data, date)

            # Phase 1: Pre-market — strategy sees prev_day_data only
            context = BacktestContext(
                date=date,
                day_data=day_data,
                day_data_indexed=day_indexed,
                prev_day_data=prev_day_data,
                portfolio=self.portfolio,
                exchange=self.exchange,
                feeder=self.feeder,
                trading_day_index=i,
                total_days=total_days,
                phase='pre_open',
            )
            # Resolve fill-price columns once per day per fill_mode. For
            # 'jq_daily_avg' both phases use the synthetic raw_avg column
            # (= (raw_open + raw_close) / 2) — see _ensure_raw_avg_column.
            if self.fill_mode == 'jq_daily_avg':
                day_indexed = self._ensure_raw_avg_column(day_indexed)
                open_fill_col = close_fill_col = 'raw_avg'
            else:  # 'open_close' (default)
                open_fill_col, close_fill_col = 'raw_open', 'raw_close'

            open_orders = self.strategy.before_market_open(context)
            if open_orders:
                self._execute_orders(open_orders, day_indexed, date, open_fill_col)

            # Phase 2: EOD bar — strategy sees full OHLCV
            context.phase = 'on_bar'
            close_orders = self.strategy.on_bar(context)
            if close_orders:
                self._execute_orders(close_orders, day_indexed, date, close_fill_col)

            # Phase 3: After close — bookkeeping only
            context.phase = 'after_close'
            self.strategy.after_market_close(context)

            # Record daily state — use RAW (unadjusted) close for valuation
            if 'raw_close' in day_data.columns:
                prices = dict(zip(day_data['ts_code'], day_data['raw_close']))
            else:
                prices = dict(zip(day_data['ts_code'], day_data['close']))
            self._record_day(date, prices)
            prev_day_data = day_data
            self._day_wall_seconds.append(_time.perf_counter() - _day_t0)

        logger.info('Backtest complete: %d days, final_value=%.2f',
                   total_days, self._prev_total_value)
        return self._build_result()

    def _fetch_day_data(self, date: pd.Timestamp) -> pd.DataFrame:
        """Fetch daily data from Qlib for all active stocks on `date`.

        Returns a DataFrame with both adjusted prices (for signals) and
        raw/unadjusted prices (for execution).  Adjusted columns are
        ``open, close, high, low, pre_close``.  Raw columns are
        ``raw_open, raw_close, raw_high, raw_low, raw_pre_close``.
        """
        # Get all stocks valid on this date
        universe = self.feeder.get_index_constituents('all', date)
        if not universe:
            return pd.DataFrame()

        # Get required fields for engine execution (including adj_factor)
        fields = ['$open', '$close', '$high', '$low', '$vol', '$amount',
                  '$pre_close', '$adj_factor']
        df_multi = self.feeder.get_features(universe, fields, date, date)

        if df_multi.empty:
            return pd.DataFrame()

        # Flatten MultiIndex to match old parquet format
        df = df_multi.reset_index()
        # Drop the datetime column to match traditional day_data
        if 'datetime' in df.columns:
            df = df.drop(columns=['datetime'])

        df = df.rename(columns={
            'instrument': 'ts_code',
            '$open': 'open',
            '$close': 'close',
            '$high': 'high',
            '$low': 'low',
            '$vol': 'vol',
            '$amount': 'amount',
            '$pre_close': 'pre_close',
            '$adj_factor': 'adj_factor',
        })

        # ── Raw (unadjusted) price columns ─────────────────────────
        # Our Qlib backend stores raw (unadjusted) prices directly
        # (verified: Qlib $open == Tushare raw open, ratio=1.0000).
        # We still create raw_* columns so the engine's execution path
        # explicitly uses "raw" intent, future-proofing against backends
        # that may apply forward adjustment.
        for col in ('open', 'close', 'high', 'low', 'pre_close'):
            df[f'raw_{col}'] = df[col]

        return df

    # ─── Validation ───────────────────────────────────────────────

    def _validate_inputs(self, start_date: str, end_date: str,
                         benchmark_code: Optional[str]) -> tuple:
        """Validate all inputs. Fail fast with clear errors.

        Returns:
            (start_ts, end_ts, calendar) tuple.
        """
        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)

        if start >= end:
            raise ValueError(
                f'start_date ({start}) must be before end_date ({end})'
            )
        if start < pd.Timestamp('2008-01-02'):
            raise ValueError(
                f'start_date ({start}) is before earliest data (2008-01-02)'
            )
        if self.initial_cash <= 0:
            raise ValueError(
                f'initial_cash must be positive, got {self.initial_cash}'
            )
        if benchmark_code:
            bench_path = os.path.join(
                self.feeder.data_dir, 'market', 'index',
                f'index_{benchmark_code}.parquet'
            )
            if not os.path.exists(bench_path):
                raise FileNotFoundError(
                    f'Benchmark file not found: {bench_path}'
                )

        calendar = self.feeder.get_trading_calendar(start_date, end_date)
        if len(calendar) == 0:
            raise ValueError(
                f'No trading days between {start} and {end}'
            )

        return start, end, calendar

    # ─── Benchmark ────────────────────────────────────────────────

    def _load_benchmark(self, code: str,
                        calendar: list[pd.Timestamp]) -> pd.Series:
        """Load benchmark index returns aligned to trading calendar.

        Args:
            code: Index code (e.g., '000852.SH').
            calendar: List of trading days.

        Returns:
            pd.Series of daily benchmark returns.
        """
        path = os.path.join(
            self.feeder.data_dir, 'market', 'index',
            f'index_{code}.parquet'
        )
        idx = pd.read_parquet(path)
        idx['trade_date'] = pd.to_datetime(
            idx['trade_date'], format='%Y%m%d'
        )
        idx = idx.set_index('trade_date').sort_index()
        idx['bench_return'] = idx['close'].pct_change()
        return idx['bench_return'].reindex(calendar).fillna(0)

    # ─── Delistings ───────────────────────────────────────────────

    def _handle_delistings(self, day_data: pd.DataFrame,
                           prev_day_data: pd.DataFrame,
                           date: pd.Timestamp) -> None:
        """Force-close positions for stocks missing from today's data.

        Uses last known close from prev_day or falls back to avg_cost.

        Args:
            day_data: Today's market data.
            prev_day_data: Yesterday's market data.
            date: Current trading date.
        """
        today_codes = set(day_data['ts_code'])
        prev_indexed = (
            prev_day_data.set_index('ts_code')
            if len(prev_day_data) > 0
            else pd.DataFrame()
        )

        for code in list(self.portfolio.positions.keys()):
            if code not in today_codes:
                pos = self.portfolio.positions[code]
                if code in prev_indexed.index:
                    last_price = prev_indexed.loc[code, 'close']
                else:
                    last_price = pos.avg_cost
                logger.warning(
                    'Delisting detected: %s on %s, force-closing %d '
                    'shares at %.2f',
                    code, date, pos.shares, last_price
                )
                self.portfolio.force_close(code, price=last_price)

    # ─── Fill-price column synthesis ──────────────────────────────

    @staticmethod
    def _ensure_raw_avg_column(day_indexed: pd.DataFrame) -> pd.DataFrame:
        """Add ``raw_avg = (raw_open + raw_close) / 2`` to the day-indexed frame
        if missing. Used by ``fill_mode='jq_daily_avg'`` to approximate
        JoinQuant's daily-frequency fill at the unit-time average.

        Returns the same frame (mutated in place when possible) for caller
        convenience. NaN open/close rows produce NaN raw_avg — the engine's
        downstream ``pd.isna(price)`` guard handles them.
        """
        if 'raw_avg' in day_indexed.columns:
            return day_indexed
        if 'raw_open' not in day_indexed.columns or 'raw_close' not in day_indexed.columns:
            # Caller is responsible for ensuring raw columns exist; we
            # cannot synthesize from adjusted prices without adj_factor.
            return day_indexed
        day_indexed['raw_avg'] = (day_indexed['raw_open'] + day_indexed['raw_close']) / 2.0
        return day_indexed

    # ─── Order Execution ──────────────────────────────────────────

    def _execute_orders(self, orders: list[Order],
                        day_indexed: pd.DataFrame,
                        date: pd.Timestamp,
                        fill_price: str) -> None:
        """Execute a list of orders.

        Process sells before buys to free up cash.

        Args:
            orders: List of Order objects.
            day_indexed: Day data indexed by ts_code.
            date: Trading date.
            fill_price: 'open' or 'close'.
        """
        sells = [o for o in orders if o.direction == 'sell']
        buys = [o for o in orders if o.direction == 'buy']

        for order in sells:
            if order.code not in day_indexed.index:
                self._log_order(order, 'BLOCKED', 'no data (delisted?)')
                continue
            row = day_indexed.loc[order.code]
            if not self.exchange.can_sell(row, order.code, date):
                self._log_order(order, 'BLOCKED', 'not tradable for sell')
                continue
            if not self.portfolio.can_sell(order.code):
                self._log_order(order, 'BLOCKED', 'T+1: no closeable shares')
                continue

            # Volume constraint
            max_shares = self.exchange.max_sellable_shares(row)
            pos = self.portfolio.get_position(order.code)
            target = (order.target_shares
                      if order.target_shares is not None
                      else pos.closeable_amount)
            actual_shares = min(target, max_shares, pos.closeable_amount)
            if actual_shares <= 0:
                self._log_order(order, 'BLOCKED', 'zero sellable shares')
                continue

            # P0-5: detect volume-capped partial fill
            is_partial_sell = actual_shares < target

            price = self.exchange.apply_slippage(
                row[fill_price], 'sell', row
            )

            # P0-8: NaN price guard (symmetric with the buy path at line 618)
            if pd.isna(price) or price <= 0:
                self._log_order(order, 'BLOCKED', f'invalid sell price {price}')
                continue

            # P0-1: Exchange is the single source of truth for costs.
            # No inline stamp-tax date check here — that logic lives in
            # exchange.compute_sell_cost_breakdown() only.
            sell_breakdown = self.exchange.compute_sell_cost_breakdown(
                actual_shares * price, date
            )
            proceeds = self.portfolio.sell(
                order.code, price, actual_shares, date,
                total_cost=sell_breakdown.total,
            )
            self._log_order(
                order, 'FILLED',
                f'{actual_shares}@{price:.2f}={proceeds:.2f}',
                shares=actual_shares, price=price, cost=sell_breakdown.total,
                partial_fill=is_partial_sell,
                fill_detail=f'{target}->{actual_shares}' if is_partial_sell else '',
            )

        for order in buys:
            if order.code not in day_indexed.index:
                self._log_order(order, 'BLOCKED', 'no data')
                continue
            row = day_indexed.loc[order.code]
            if not self.exchange.can_buy(row, order.code, date):
                self._log_order(order, 'BLOCKED', 'not tradable for buy')
                continue

            # Volume constraint
            max_value = self.exchange.max_buyable_value(row)
            actual_value = min(order.target_value, max_value)
            if actual_value <= 0:
                self._log_order(order, 'BLOCKED', 'zero buyable value')
                continue

            # P0-5: detect volume-capped partial fill
            is_partial_buy = actual_value < order.target_value

            price = self.exchange.apply_slippage(
                row[fill_price], 'buy', row
            )
            if pd.isna(price) or price <= 0:
                self._log_order(order, 'BLOCKED', f'invalid price {price}')
                continue
            lot_size = self.exchange.get_lot_size(order.code)

            # P0-4b: Exchange is the single source of truth for buy costs.
            buy_breakdown = self.exchange.compute_buy_cost_breakdown(actual_value, date)
            invested = self.portfolio.buy(
                order.code, price, actual_value, date,
                lot_size=lot_size,
                total_cost=buy_breakdown.total,
            )
            if invested > 0:
                self._log_order(
                    order, 'FILLED',
                    f'{invested:.2f} invested @ {price:.2f}',
                    shares=int(invested / price) if price > 0 else 0,
                    price=price, cost=buy_breakdown.total,
                    partial_fill=is_partial_buy,
                    fill_detail=f'{order.target_value:.0f}->{actual_value:.0f}' if is_partial_buy else '',
                )
            else:
                self._log_order(order, 'BLOCKED', 'insufficient cash/lots')

    def _log_order(self, order: Order, status: str, detail: str,
                   shares: int = 0, price: float = 0.0,
                   cost: float = 0.0,
                   partial_fill: bool = False,
                   fill_detail: str = '') -> None:
        """Append to order audit trail for post-hoc analysis.

        Args:
            order: The Order object.
            status: 'FILLED' or 'BLOCKED'.
            detail: Human-readable detail string.
            shares: Actual shares traded (0 if blocked).
            price: Fill price (0 if blocked).
            cost: Total trade cost (0 if blocked).
            partial_fill: True if order was volume-capped (P0-5). Status
                remains 'FILLED' so ``result.trades`` still includes the
                execution. Researchers grep ``partial_fill==True`` to
                find volume-capped orders.
            fill_detail: Human-readable '{target}->{actual}' when
                partial_fill is True. Empty for full fills and blocks.
        """
        self._order_log.append({
            'date': self._current_date,
            'code': order.code,
            'direction': order.direction,
            'status': status,
            'shares': shares,
            'price': price,
            'value': shares * price,
            'cost': cost,
            'cash_after': self.portfolio.cash,
            'detail': detail,
            'reason': order.reason,
            'partial_fill': partial_fill,
            'fill_detail': fill_detail,
        })
        logger.debug('Order %s %s %s: %s (%s)',
                     status, order.direction, order.code,
                     detail, order.reason)

    # ─── Daily Recording ──────────────────────────────────────────

    def _record_day(self, date: pd.Timestamp,
                    prices: dict[str, float]) -> None:
        """Record end-of-day portfolio state and per-stock holdings.

        Args:
            date: Trading date.
            prices: Dict of {ts_code: close_price}.
        """
        total_value = self.portfolio.total_value(prices)
        daily_cost = self.portfolio.get_today_costs()

        # Guard: prevent division by zero
        if self._prev_total_value <= 0:
            logger.error(
                'Portfolio value hit 0 on %s, cannot compute return', date
            )
            daily_return = 0.0
        else:
            daily_return = (
                (total_value - self._prev_total_value) /
                self._prev_total_value
            )

        bench_return = (self._benchmark_returns.get(date, 0)
                        if not self._benchmark_returns.empty else 0)
        turnover = (self.portfolio.get_today_turnover() /
                    max(total_value, 1))

        self._daily_records.append({
            'date': date,
            'return': daily_return,
            'cost': daily_cost / max(self._prev_total_value, 1),
            'bench': bench_return,
            'turnover': turnover,
            'total_value': total_value,
            'cash': self.portfolio.cash,
            'market_value': total_value - self.portfolio.cash,
            'n_positions': len(self.portfolio.positions),
        })

        # Per-stock holdings snapshot
        for code, pos in self.portfolio.positions.items():
            mkt_price = prices.get(code, pos.avg_cost)
            self._daily_holdings.append({
                'date': date,
                'code': code,
                'shares': pos.shares,
                'closeable': pos.closeable_amount,
                'avg_cost': pos.avg_cost,
                'market_price': mkt_price,
                'market_value': pos.shares * mkt_price,
                'weight': (pos.shares * mkt_price) / max(total_value, 1),
                'unrealized_pnl': (mkt_price - pos.avg_cost) * pos.shares,
                'pnl_pct': ((mkt_price / pos.avg_cost - 1)
                            if pos.avg_cost > 0 else 0),
            })

        self._prev_total_value = total_value

    # ─── Build Result ─────────────────────────────────────────────

    def _build_result(self) -> BacktestResult:
        """Build the final BacktestResult from recorded data.

        Returns:
            BacktestResult with all DataFrames populated.
        """
        # Report
        report = pd.DataFrame(self._daily_records)
        if not report.empty:
            report = report.set_index('date')

        # Trades (filled orders only)
        all_orders = pd.DataFrame(self._order_log)
        if all_orders.empty:
            trades = pd.DataFrame(
                columns=['date', 'code', 'direction', 'shares',
                         'price', 'value', 'cost', 'cash_after', 'reason']
            )
            order_log = pd.DataFrame(
                columns=['date', 'code', 'direction', 'status',
                         'shares', 'price', 'value', 'cost',
                         'cash_after', 'detail', 'reason']
            )
        else:
            trades = all_orders[all_orders['status'] == 'FILLED'][
                ['date', 'code', 'direction', 'shares', 'price',
                 'value', 'cost', 'cash_after', 'reason']
            ].copy()
            order_log = all_orders.copy()

        # Daily holdings
        daily_holdings = pd.DataFrame(self._daily_holdings)

        # Corporate actions
        corp_actions = pd.DataFrame()
        if (self.corp_action_handler and
                self.corp_action_handler.action_log):
            corp_actions = pd.DataFrame(
                self.corp_action_handler.action_log
            )

        return BacktestResult(
            report=report,
            trades=trades,
            order_log=order_log,
            daily_holdings=daily_holdings,
            corporate_actions=corp_actions,
            config={
                'initial_cash': self.initial_cash,
                'start_date': str(self._daily_records[0]['date'])
                    if self._daily_records else '',
                'end_date': str(self._daily_records[-1]['date'])
                    if self._daily_records else '',
                'n_days': len(self._daily_records),
            },
        )
