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
Multi-Factor PIT Validation — Local EventDrivenBacktester

Tests Point-in-Time correctness by using PIT-critical fundamental factors
(PE_TTM, revenue growth) alongside technical factors (momentum reversal,
market cap). Designed for cross-platform comparison with JoinQuant.

Strategy:
    Universe:    CSI 300 constituents, main board, market cap > 50亿
    Factors:     PE_TTM (value), revenue QoQ growth, 20d reversal, market cap
    Composite:   Equal-weight z-score
    Hold:        Top 6 stocks by composite score
    Rebalance:   Every 10 trading days at OPEN
    Costs:       Commission 万3.5, stamp 0.05%, min ¥5, no slippage
    Capital:     ¥200,000
    Period:      2024-01-02 → 2024-12-31

Usage:
    e:\\量化系统\\venv\\Scripts\\python.exe e:\\量化系统\\workspace\\scripts\\run_multifactor_validation.py
"""

import os
import sys
import logging
import warnings

import numpy as np
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
START_DATE = '2024-01-02'
END_DATE = '2024-12-31'
BENCHMARK = '000300.SH'        # CSI 300
ACCOUNT = 200_000              # ¥200,000

# Strategy params
STOCK_NUM = 6                  # Hold 6 stocks
REBALANCE_INTERVAL = 10        # Rebalance every 10 trading days
MIN_MV_WAN = 500_000           # 50亿 in 万元 (Tushare unit)

# Qlib fields to preload
PRELOAD_FIELDS = [
    '$open', '$close', '$high', '$low', '$vol', '$amount', '$pre_close',
    '$total_mv',                # 总市值 (万元)
    '$pe_ttm',                  # PE TTM — PIT-critical
    '$revenue_q',               # 单季度营业收入 — PIT-critical
    '$pb',                      # 市净率
]


# ═════════════════════════════════════════════════════════
# STRATEGY
# ═════════════════════════════════════════════════════════

from src.backtest_engine.event_driven import (
    EventDrivenBacktester, Strategy, BacktestContext, Order,
    CostConfig, NoSlippage,
)


class MultiFactorStrategy(Strategy):
    """Multi-factor ranking strategy with PIT-critical fundamental factors.

    Factor construction:
        1. Value:    PE_TTM (lower = better, rank ascending)
        2. Growth:   Revenue QoQ growth (higher = better, rank descending)
        3. Reversal: 20-day return (lower = better, rank ascending)
        4. Size:     Market cap (lower = better, rank ascending)

    Composite: Equal-weight percentile rank → highest composite = best.
    """

    def initialize(self, ctx: BacktestContext) -> None:
        self.g.stock_num = STOCK_NUM
        self.g.rebalance_interval = REBALANCE_INTERVAL
        self.g.day_count = 0
        self.g.yesterday_HL_list = []
        self.g.prev_20d_close = {}  # {code: close_20d_ago}
        self.g.close_history = []   # Rolling 21-day close history
        logger.info('MultiFactorStrategy initialized: hold %d, rebalance %d days',
                     self.g.stock_num, self.g.rebalance_interval)

    def before_market_open(self, ctx: BacktestContext) -> list[Order]:
        """Pre-market factor ranking and rebalance."""
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

        # ─── Store close history for 20d momentum ───────────
        if not ctx.prev_day_data.empty:
            close_dict = dict(zip(ctx.prev_day_data['ts_code'],
                                  ctx.prev_day_data['close']))
            self.g.close_history.append(close_dict)
            # Keep only last 21 entries
            if len(self.g.close_history) > 21:
                self.g.close_history = self.g.close_history[-21:]

        # ─── Rebalance check ─────────────────────────────────
        if (self.g.day_count - 1) % self.g.rebalance_interval != 0:
            return []

        if ctx.prev_day_data.empty:
            logger.warning('Day %d: no prev_day_data, skipping', self.g.day_count)
            return []

        # ─── Get CSI 300 constituents ─────────────────────────
        try:
            csi300 = ctx.feeder.get_index_constituents(
                'csi300', ctx.feeder.get_prev_trading_day(date)
            )
        except Exception:
            csi300 = ctx.feeder.get_index_constituents('csi300', date)

        if not csi300:
            logger.warning('Day %d: empty CSI300 constituents', self.g.day_count)
            return []

        # ─── Build factor DataFrame ──────────────────────────
        # prev_day_data only has OHLCV; we need fundamental fields
        # from the preloaded cache via feeder.get_features()
        prev_date = ctx.feeder.get_prev_trading_day(date)
        prev_date_str = prev_date.strftime('%Y-%m-%d')

        # Fetch fundamental data from cache for all CSI300 members
        fund_fields = ['$pe_ttm', '$revenue_q', '$total_mv', '$close', '$vol']
        fund_df = ctx.feeder.get_features(csi300, fund_fields, prev_date_str, prev_date_str)

        if fund_df.empty:
            logger.warning('Day %d: no fundamental data from feeder', self.g.day_count)
            return []

        # Flatten MultiIndex to per-stock rows
        fund_df = fund_df.reset_index()
        fund_df = fund_df.rename(columns={'instrument': 'ts_code'})
        if 'datetime' in fund_df.columns:
            fund_df = fund_df.drop(columns=['datetime'])
        fund_df = fund_df.set_index('ts_code')

        records = []
        for code in csi300:
            if code not in fund_df.index:
                continue
            row = fund_df.loc[code]

            # Filter: suspended
            vol = row.get('$vol', 0)
            if pd.isna(vol) or vol == 0:
                continue

            # Filter: main board only
            prefix = code[:3]
            if prefix in ('300', '301', '688', '689'):
                continue
            if code[0] in ('8', '4', '9'):
                continue

            # Filter: ST
            if ctx.exchange.is_st(code, prev_date):
                continue

            # Factor values from feeder cache
            total_mv = row.get('$total_mv', np.nan)
            pe_ttm = row.get('$pe_ttm', np.nan)
            revenue_q = row.get('$revenue_q', np.nan)
            close = row.get('$close', np.nan)

            # Filter: market cap > 50亿
            if pd.isna(total_mv) or total_mv < MIN_MV_WAN:
                continue

            # Filter: PE > 0 (profitable)
            if pd.isna(pe_ttm) or pe_ttm <= 0:
                continue

            # Skip if missing revenue
            if pd.isna(revenue_q) or revenue_q <= 0:
                continue

            # 20-day momentum (reversal): need close from 20 days ago
            mom_20d = np.nan
            if len(self.g.close_history) >= 21:
                old_close = self.g.close_history[-21].get(code, np.nan)
                if not pd.isna(old_close) and old_close > 0:
                    mom_20d = (close / old_close) - 1

            records.append({
                'code': code,
                'total_mv': total_mv,
                'pe_ttm': pe_ttm,
                'revenue_q': revenue_q,
                'mom_20d': mom_20d,
                'close': close,
            })

        if not records:
            logger.warning('Day %d: no stocks pass filters (%d CSI300 members, '
                           '%d in feeder)', self.g.day_count, len(csi300), len(fund_df))
            return []


        df = pd.DataFrame(records)

        # ─── Compute composite score ─────────────────────────
        # Lower PE = better → rank ascending, then take 1-rank for "higher=better"
        df['v_pe'] = 1 - df['pe_ttm'].rank(pct=True)

        # Higher revenue = better → rank descending (higher pct = better)
        df['v_rev'] = df['revenue_q'].rank(pct=True)

        # Lower momentum = better (reversal) → rank ascending, then 1-rank
        if df['mom_20d'].notna().sum() > 5:
            df['v_mom'] = 1 - df['mom_20d'].rank(pct=True)
        else:
            df['v_mom'] = 0.5  # No momentum data available

        # Lower size = better → rank ascending, then 1-rank
        df['v_size'] = 1 - df['total_mv'].rank(pct=True)

        # Equal-weight composite
        df['composite'] = (df['v_pe'] + df['v_rev'] + df['v_mom'] + df['v_size']) / 4

        # Sort by composite descending → top N
        df = df.sort_values('composite', ascending=False)

        target = df.head(self.g.stock_num)['code'].tolist()

        # ─── Log factor rankings ──────────────────────────────
        logger.info(
            'Day %d [%s] REBALANCE | %d candidates | Top %d:',
            self.g.day_count, date.strftime('%Y-%m-%d'),
            len(df), self.g.stock_num,
        )
        for _, row in df.head(self.g.stock_num).iterrows():
            logger.info(
                '  %-10s PE=%.1f Rev=%.0f Mom=%.3f MV=%.0f亿 Score=%.3f',
                row['code'], row['pe_ttm'], row['revenue_q'],
                row['mom_20d'] if not pd.isna(row['mom_20d']) else 0,
                row['total_mv'] / 10000,
                row['composite'],
            )

        # ─── Build orders ─────────────────────────────────────
        current_holds = set(ctx.portfolio.positions.keys())

        sell_list = [
            s for s in current_holds
            if s not in target and s not in self.g.yesterday_HL_list
        ]
        buy_list = [s for s in target if s not in current_holds]

        logger.info(
            '  Target: %s | Sell: %s | Buy: %s',
            target, sell_list, buy_list,
        )

        orders = []

        for code in sell_list:
            orders.append(Order(code, 'sell', reason='factor_rebalance'))

        if buy_list:
            prices = {}
            for code in list(current_holds) + buy_list:
                if code in fund_df.index:
                    prices[code] = fund_df.loc[code, '$close']
            total_value = ctx.portfolio.total_value(prices)
            per_stock = total_value / self.g.stock_num

            for code in buy_list:
                orders.append(Order(
                    code, 'buy',
                    target_value=per_stock,
                    reason='factor_rebalance',
                ))

        return orders

    def after_market_close(self, ctx: BacktestContext) -> None:
        """Log daily portfolio state on rebalance days."""
        if self.g.day_count % self.g.rebalance_interval == 0:
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
    logger.info('Multi-Factor PIT Validation Backtest')
    logger.info('Period: %s → %s', START_DATE, END_DATE)
    logger.info('Factors: PE_TTM, Revenue_Q, 20d_Reversal, MarketCap')
    logger.info('Universe: CSI300 main-board, MV > 50亿, PE > 0')
    logger.info('Hold %d, rebalance every %d days, ¥%d capital',
                STOCK_NUM, REBALANCE_INTERVAL, ACCOUNT)
    logger.info('=' * 70)

    cost_config = CostConfig(
        buy_commission=0.00035,
        sell_commission=0.00035,
        stamp_tax=0.0005,
        stamp_tax_pre_20230828=0.001,
        min_commission=5.0,
    )

    strategy = MultiFactorStrategy()

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
                '  %s %s %-10s %d shares @ %.2f = %.2f (cost=%.2f) [%s]',
                t['date'].strftime('%Y-%m-%d') if hasattr(t['date'], 'strftime') else t['date'],
                t['direction'].upper().ljust(4),
                t['code'],
                t['shares'],
                t['price'],
                t['value'],
                t['cost'],
                t.get('reason', ''),
            )
    else:
        logger.info('No trades executed!')

    # Blocked orders
    blocked = result.order_log[result.order_log['status'] == 'BLOCKED']
    if not blocked.empty:
        logger.info('\n--- BLOCKED ORDERS (%d) ---', len(blocked))
        for _, o in blocked.iterrows():
            logger.info('  %s %s %-10s: %s',
                        o['date'].strftime('%Y-%m-%d') if hasattr(o['date'], 'strftime') else o['date'],
                        o['direction'],
                        o['code'],
                        o['detail'])

    # Daily returns (first/last)
    if not result.report.empty:
        logger.info('\n--- DAILY SUMMARY (first 5 + last 5) ---')
        for _, row in result.report.head(5).iterrows():
            logger.info(
                '  %s | ret=%.4f | value=%.2f | pos=%d',
                row.name.strftime('%Y-%m-%d'),
                row['return'], row['total_value'], row['n_positions'],
            )
        logger.info('  ...')
        for _, row in result.report.tail(5).iterrows():
            logger.info(
                '  %s | ret=%.4f | value=%.2f | pos=%d',
                row.name.strftime('%Y-%m-%d'),
                row['return'], row['total_value'], row['n_positions'],
            )

    # Save outputs
    output_dir = os.path.join(PROJECT_ROOT, 'workspace', 'outputs')
    os.makedirs(output_dir, exist_ok=True)

    if not trades.empty:
        trades_path = os.path.join(output_dir, 'multifactor_trades_local.csv')
        trades.to_csv(trades_path, index=False)
        logger.info('\nTrade log saved to: %s', trades_path)

    if not result.report.empty:
        report_path = os.path.join(output_dir, 'multifactor_report_local.csv')
        result.report.to_csv(report_path)
        logger.info('Daily report saved to: %s', report_path)


if __name__ == '__main__':
    main()
