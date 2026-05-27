# ──────────────────────────────────────────────────────────────────────
# PR 7 of 2026-05-26 freeze plan — SCRIPT_STATUS header block.
# script_status: formal_candidate
# formal_research_allowed: true
# deployment_target: joinquant_daily
# execution_profile: joinquant_daily_sim
# requires_provider_manifest: true
# requires_preload_strict: true
# pr2_audit_class: A
# notes: |
#   Validation runner already on EventDrivenBacktester. PR 3's
#   ExecutionProfile contract is now available — when this script is
#   next touched, pass execution_profile='joinquant_daily_sim'
#   instead of composing fill_mode + cost + slippage individually.
# ──────────────────────────────────────────────────────────────────────
"""
Local Validation Backtest — Fixed-Universe Cheapest-4 Rotation

Cross-platform validation strategy designed for exact comparison
with JoinQuant. Uses EventDrivenBacktester.

Strategy:
    Universe:    10 fixed large-cap stocks (main board only)
    Ranking:     Previous-day close price ascending
    Hold:        Cheapest 4 stocks, equal weight
    Rebalance:   Every 5 trading days, fill at OPEN
    Skip sell:   Yesterday's limit-up stocks
    Costs:       Commission 0.035%, stamp 0.05%, min ¥5
    Slippage:    None
    Capital:     ¥100,000
    Period:      2024-06-03 to 2024-12-31

Usage:
    e:\\量化系统\\venv\\Scripts\\python.exe e:\\量化系统\\workspace\\scripts\\run_validation_backtest.py
"""

import os
import sys
import logging
import warnings

import pandas as pd

# Project setup
PROJECT_ROOT = r'e:\量化系统'
sys.path.insert(0, PROJECT_ROOT)

warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=UserWarning)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)
logger = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════
# CONFIGURATION
# ═════════════════════════════════════════════════════════

DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
START_DATE = '2024-06-03'      # First trading day in June 2024
END_DATE = '2024-12-31'
BENCHMARK = '000852.SH'        # CSI 1000
ACCOUNT = 100_000              # ¥100,000

# Strategy params
STOCK_NUM = 4                  # Hold 4 stocks
REBALANCE_INTERVAL = 5         # Rebalance every 5 trading days

# Fixed universe — 10 main board large/mid-cap stocks
# Tushare format (used throughout the local backtester)
UNIVERSE = [
    '600519.SH',   # 贵州茅台
    '000858.SZ',   # 五粮液
    '000001.SZ',   # 平安银行
    '601318.SH',   # 中国平安
    '600036.SH',   # 招商银行
    '000002.SZ',   # 万科A
    '000568.SZ',   # 泸州老窖
    '601888.SH',   # 中国中免
    '600276.SH',   # 恒瑞医药
    '000651.SZ',   # 格力电器
]

# Qlib fields to preload
PRELOAD_FIELDS = [
    '$open', '$close', '$high', '$low', '$vol', '$amount', '$pre_close',
]

# ═════════════════════════════════════════════════════════
# STRATEGY
# ═════════════════════════════════════════════════════════

from src.backtest_engine.event_driven import (
    EventDrivenBacktester, Strategy, BacktestContext, Order,
    CostConfig, NoSlippage,
)


class FixedUniverseStrategy(Strategy):
    """Cheapest-4 rotation on a fixed 10-stock universe.

    Matches JoinQuant's weekly_adjustment() logic:
    - Day counter starts at 0, rebalance on days 1, 6, 11, 16, ...
    - On rebalance day:
      1. Get prev-day close for all 10 stocks (skip suspended)
      2. Sort ascending → cheapest 4 = target portfolio
      3. Sell holdings NOT in target (skip yesterday's limit-up)
      4. Buy target stocks NOT already held, equal weight

    All orders placed in before_market_open() → filled at OPEN.
    """

    def initialize(self, ctx: BacktestContext) -> None:
        self.g.universe = UNIVERSE
        self.g.stock_num = STOCK_NUM
        self.g.rebalance_interval = REBALANCE_INTERVAL
        self.g.day_count = 0
        self.g.yesterday_HL_list = []
        self.g.trade_log = []
        logger.info('Strategy initialized: %d-stock universe, hold %d, '
                     'rebalance every %d days',
                     len(self.g.universe), self.g.stock_num,
                     self.g.rebalance_interval)

    def before_market_open(self, ctx: BacktestContext) -> list[Order]:
        """Pre-market: check limit-up from prev day, then rebalance."""
        self.g.day_count += 1
        date = ctx.date

        # ─── Track yesterday's limit-up stocks ───────────────
        self.g.yesterday_HL_list = []
        hold_codes = list(ctx.portfolio.positions.keys())
        if hold_codes and not ctx.prev_day_data.empty:
            prev_indexed = ctx.prev_day_data.set_index('ts_code')
            for code in hold_codes:
                if code not in prev_indexed.index:
                    continue
                row = prev_indexed.loc[code]
                if ctx.exchange.is_limit_up(row, code,
                                            ctx.feeder.get_prev_trading_day(date)):
                    self.g.yesterday_HL_list.append(code)

        if self.g.yesterday_HL_list:
            logger.info('Day %d [%s] HL stocks: %s',
                        self.g.day_count, date.strftime('%Y-%m-%d'),
                        self.g.yesterday_HL_list)

        # ─── Rebalance check ─────────────────────────────────
        if (self.g.day_count - 1) % self.g.rebalance_interval != 0:
            return []

        # ─── Get prev-day close for universe ─────────────────
        if ctx.prev_day_data.empty:
            logger.warning('Day %d: no prev_day_data, skipping rebalance',
                           self.g.day_count)
            return []

        prev_indexed = ctx.prev_day_data.set_index('ts_code')
        avail = []
        for code in self.g.universe:
            if code not in prev_indexed.index:
                continue
            row = prev_indexed.loc[code]
            vol = row.get('vol', 0)
            if pd.isna(vol) or vol == 0:
                continue  # Skip suspended stocks
            avail.append((code, row['close']))

        # Sort by close ascending → cheapest first
        avail.sort(key=lambda x: x[1])
        target = [code for code, _ in avail[:self.g.stock_num]]

        current_holds = set(ctx.portfolio.positions.keys())

        # Determine sells (skip yesterday's limit-up)
        sell_list = [
            s for s in current_holds
            if s not in target and s not in self.g.yesterday_HL_list
        ]

        # Determine buys
        buy_list = [s for s in target if s not in current_holds]

        logger.info(
            'Day %d [%s] REBALANCE | Target: %s | Sell: %s | Buy: %s',
            self.g.day_count, date.strftime('%Y-%m-%d'),
            target, sell_list, buy_list,
        )

        # Build orders: sells first, then buys
        orders = []

        for code in sell_list:
            orders.append(Order(code, 'sell', reason='rebalance_out'))
            self.g.trade_log.append({
                'day': self.g.day_count,
                'date': date,
                'code': code,
                'direction': 'sell',
                'reason': 'rebalance_out',
            })

        if buy_list:
            # Get current total value for equal weight calculation
            # Use prev-day prices for valuation (we don't have today's open yet)
            prices = {}
            for code in list(current_holds) + buy_list:
                if code in prev_indexed.index:
                    prices[code] = prev_indexed.loc[code, 'close']
            total_value = ctx.portfolio.total_value(prices)
            per_stock = total_value / self.g.stock_num

            for code in buy_list:
                orders.append(Order(
                    code, 'buy',
                    target_value=per_stock,
                    reason='rebalance_in',
                ))
                self.g.trade_log.append({
                    'day': self.g.day_count,
                    'date': date,
                    'code': code,
                    'direction': 'buy',
                    'target_value': per_stock,
                    'reason': 'rebalance_in',
                })

        return orders

    def after_market_close(self, ctx: BacktestContext) -> None:
        """Log daily portfolio state."""
        if ctx.day_data.empty:
            return
        prices = dict(zip(ctx.day_data['ts_code'], ctx.day_data['close']))
        total = ctx.portfolio.total_value(prices)
        n_pos = len(ctx.portfolio.positions)
        logger.info(
            'Day %d [%s] EOD | value=%.2f cash=%.2f positions=%d',
            self.g.day_count, ctx.date.strftime('%Y-%m-%d'),
            total, ctx.portfolio.cash, n_pos,
        )


# ═════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════

def main():
    logger.info('=' * 70)
    logger.info('Cross-Validation Backtest: EventDrivenBacktester')
    logger.info('Period: %s → %s', START_DATE, END_DATE)
    logger.info('Universe: %d stocks, hold %d, rebalance every %d days',
                len(UNIVERSE), STOCK_NUM, REBALANCE_INTERVAL)
    logger.info('=' * 70)

    # Cost config: match JoinQuant exactly
    # Commission: 万3.5 = 0.035% = 0.00035
    # Stamp tax: 0.05% after 2023-08-28 (our period is 2024)
    # Stamp tax: 0.10% before 2023-08-28
    cost_config = CostConfig(
        buy_commission=0.00035,
        sell_commission=0.00035,
        stamp_tax=0.0005,                # 0.05% (post 2023-08-28)
        stamp_tax_pre_20230828=0.001,     # 0.10% (pre 2023-08-28)
        min_commission=5.0,
    )

    strategy = FixedUniverseStrategy()

    bt = EventDrivenBacktester(data_dir=DATA_DIR)
    result = bt.run(
        strategy=strategy,
        start_time=START_DATE,
        end_time=END_DATE,
        benchmark=BENCHMARK,
        account=ACCOUNT,
        exchange_config=cost_config,
        slippage=NoSlippage(),
        volume_limit=0.25,
        preload_fields=PRELOAD_FIELDS,
    )

    # ─── Print Results ────────────────────────────────────
    logger.info('\n' + '=' * 70)
    logger.info('RESULTS')
    logger.info('=' * 70)

    summary = result.summary
    for key, val in summary.items():
        if isinstance(val, float):
            logger.info('  %-40s: %.4f', key, val)
        else:
            logger.info('  %-40s: %s', key, val)

    # Trade log
    trades = result.trades
    if not trades.empty:
        logger.info('\n--- TRADE LOG (%d trades) ---', len(trades))
        for _, t in trades.iterrows():
            logger.info(
                '  %s %s %s %d shares @ %.2f = %.2f (cost=%.2f)',
                t['date'].strftime('%Y-%m-%d') if hasattr(t['date'], 'strftime') else t['date'],
                t['direction'].upper(),
                t['code'],
                t['shares'],
                t['price'],
                t['value'],
                t['cost'],
            )
    else:
        logger.info('No trades executed!')

    # Order log (including blocked)
    blocked = result.order_log[result.order_log['status'] == 'BLOCKED']
    if not blocked.empty:
        logger.info('\n--- BLOCKED ORDERS (%d) ---', len(blocked))
        for _, o in blocked.iterrows():
            logger.info('  %s %s %s: %s',
                        o['date'].strftime('%Y-%m-%d') if hasattr(o['date'], 'strftime') else o['date'],
                        o['direction'],
                        o['code'],
                        o['detail'])

    # Daily portfolio values
    if not result.report.empty:
        logger.info('\n--- DAILY SUMMARY (first 10 + last 5) ---')
        for _, row in result.report.head(10).iterrows():
            logger.info(
                '  %s | ret=%.4f | value=%.2f | cash=%.2f | pos=%d',
                row.name.strftime('%Y-%m-%d'),
                row['return'], row['total_value'],
                row['cash'], row['n_positions'],
            )
        logger.info('  ...')
        for _, row in result.report.tail(5).iterrows():
            logger.info(
                '  %s | ret=%.4f | value=%.2f | cash=%.2f | pos=%d',
                row.name.strftime('%Y-%m-%d'),
                row['return'], row['total_value'],
                row['cash'], row['n_positions'],
            )

    # Save trade log to CSV for comparison
    output_dir = os.path.join(PROJECT_ROOT, 'workspace', 'outputs')
    os.makedirs(output_dir, exist_ok=True)

    if not trades.empty:
        trades_path = os.path.join(output_dir, 'validation_trades_local.csv')
        trades.to_csv(trades_path, index=False)
        logger.info('\nTrade log saved to: %s', trades_path)

    if not result.report.empty:
        report_path = os.path.join(output_dir, 'validation_report_local.csv')
        result.report.to_csv(report_path)
        logger.info('Daily report saved to: %s', report_path)

    logger.info('\nDone. Copy joinquant_validation.py to JQ and compare results.')


if __name__ == '__main__':
    main()
