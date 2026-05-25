"""
Verified-Factor Cross-Platform Validation — Local Backtest

Uses ONLY factors verified identical between Tushare/Qlib and JoinQuant:
  1. Market cap      (✅ 100% exact match) — smaller = better
  2. Turnover rate   (✅ 100% exact match) — lower = better (low turnover value trap)
  3. 20d Momentum    (✅ 96.4% match)     — lower = better (reversal)

Universe:  CSI300 main-board, not ST, not suspended
Hold:      Top 6, rebalance every 10 trading days at OPEN
Costs:     Commission 万3.5, stamp 0.05%, min ¥5, no slippage
Capital:   ¥200,000
Period:    2024-01-02 → 2024-12-31

Usage:
    e:\\量化系统\\venv\\Scripts\\python.exe e:\\量化系统\\workspace\\scripts\\run_verified_validation.py
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
BENCHMARK = '000300.SH'
ACCOUNT = 200_000

STOCK_NUM = 6
REBALANCE_INTERVAL = 10

# Qlib fields to preload
PRELOAD_FIELDS = [
    '$open', '$close', '$high', '$low', '$vol', '$amount', '$pre_close',
    '$total_mv',          # 总市值 (万元)
    '$turnover_rate',     # 换手率 (%)
]


# ═════════════════════════════════════════════════════════
# STRATEGY
# ═════════════════════════════════════════════════════════

from src.backtest_engine.event_driven import (
    EventDrivenBacktester, Strategy, BacktestContext, Order,
    CostConfig, NoSlippage,
)


class VerifiedFactorStrategy(Strategy):
    """3-factor strategy using ONLY verified-identical factors.

    Factor construction:
        1. Size:      Market cap (lower = better, rank ascending)
        2. Turnover:  Turnover rate (lower = better, rank ascending)
        3. Reversal:  20-day return (lower = better, rank ascending)

    Composite: Equal-weight percentile rank → highest composite = best.
    """

    def initialize(self, ctx: BacktestContext) -> None:
        self.g.stock_num = STOCK_NUM
        self.g.rebalance_interval = REBALANCE_INTERVAL
        self.g.day_count = 0
        self.g.yesterday_HL_list = []
        self.g.close_history = []
        # Skip first rebalance to match JQ's 01-16 start
        self.g.skip_first = True
        logger.info('VerifiedFactorStrategy initialized: hold %d, rebalance %d days (skip first)',
                     self.g.stock_num, self.g.rebalance_interval)

    def before_market_open(self, ctx: BacktestContext) -> list[Order]:
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

        # ─── Rebalance check ─────────────────────────────────
        if (self.g.day_count - 1) % self.g.rebalance_interval != 0:
            return []

        # Skip the very first rebalance to align with JQ
        if self.g.skip_first:
            self.g.skip_first = False
            logger.info('Day %d [%s]: skipping first rebalance (JQ alignment)',
                        self.g.day_count, date.strftime('%Y-%m-%d'))
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
        prev_date = ctx.feeder.get_prev_trading_day(date)
        prev_date_str = prev_date.strftime('%Y-%m-%d')

        # Fetch verified factors from cache
        fund_fields = ['$total_mv', '$turnover_rate', '$close', '$vol']
        fund_df = ctx.feeder.get_features(csi300, fund_fields, prev_date_str, prev_date_str)

        if fund_df.empty:
            logger.warning('Day %d: no data from feeder', self.g.day_count)
            return []

        fund_df = fund_df.reset_index()
        fund_df = fund_df.rename(columns={'instrument': 'ts_code'})
        if 'datetime' in fund_df.columns:
            fund_df = fund_df.drop(columns=['datetime'])
        fund_df = fund_df.set_index('ts_code')

        # ─── Compute 20d momentum from feeder (like JQ's get_price(count=21)) ──
        # Go back 21 trading days to get 20-period return
        lookback_date = prev_date
        for _ in range(20):
            lookback_date = ctx.feeder.get_prev_trading_day(lookback_date)
        lookback_str = lookback_date.strftime('%Y-%m-%d')

        hist_df = ctx.feeder.get_features(csi300, ['$close'], lookback_str, prev_date_str)
        mom_dict = {}
        if not hist_df.empty:
            hist_df = hist_df.reset_index()
            for code in csi300:
                stock_hist = hist_df[hist_df['instrument'] == code]['$close'].values
                if len(stock_hist) >= 21 and stock_hist[0] > 0 and not pd.isna(stock_hist[0]):
                    mom_dict[code] = stock_hist[-1] / stock_hist[0] - 1

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

            total_mv = row.get('$total_mv', np.nan)
            turnover = row.get('$turnover_rate', np.nan)

            if pd.isna(total_mv) or total_mv <= 0:
                continue
            if pd.isna(turnover):
                continue

            mom_20d = mom_dict.get(code, np.nan)

            records.append({
                'code': code,
                'total_mv': total_mv,
                'turnover': turnover,
                'mom_20d': mom_20d,
            })

        if not records:
            logger.warning('Day %d: no stocks pass filters', self.g.day_count)
            return []

        df = pd.DataFrame(records)

        # ─── Compute composite score ─────────────────────────
        # Lower market cap = better → 1 - rank
        df['v_size'] = 1 - df['total_mv'].rank(pct=True)

        # Lower turnover = better → 1 - rank
        df['v_turn'] = 1 - df['turnover'].rank(pct=True)

        # Lower momentum = better (reversal) → 1 - rank
        if df['mom_20d'].notna().sum() > 5:
            df['v_mom'] = 1 - df['mom_20d'].rank(pct=True)
        else:
            df['v_mom'] = 0.5

        # Equal-weight composite
        df['composite'] = (df['v_size'] + df['v_turn'] + df['v_mom']) / 3
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
                '  %-10s Turn=%.2f Mom=%.3f MV=%.0f亿 Score=%.3f',
                row['code'], row['turnover'],
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
    logger.info('Verified-Factor Cross-Platform Validation')
    logger.info('Period: %s → %s', START_DATE, END_DATE)
    logger.info('Factors: MarketCap, Turnover, 20d_Reversal (all verified ✅)')
    logger.info('Universe: CSI300 main-board, not ST, not suspended')
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

    strategy = VerifiedFactorStrategy()

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

    blocked = result.order_log[result.order_log['status'] == 'BLOCKED']
    if not blocked.empty:
        logger.info('\n--- BLOCKED ORDERS (%d) ---', len(blocked))

    if not result.report.empty:
        logger.info('\n--- DAILY SUMMARY (first 5 + last 5) ---')
        for _, row in result.report.head(5).iterrows():
            logger.info('  %s | ret=%.4f | value=%.2f | pos=%d',
                        row.name.strftime('%Y-%m-%d'),
                        row['return'], row['total_value'], row['n_positions'])
        logger.info('  ...')
        for _, row in result.report.tail(5).iterrows():
            logger.info('  %s | ret=%.4f | value=%.2f | pos=%d',
                        row.name.strftime('%Y-%m-%d'),
                        row['return'], row['total_value'], row['n_positions'])

    output_dir = os.path.join(PROJECT_ROOT, 'workspace', 'outputs')
    os.makedirs(output_dir, exist_ok=True)

    if not trades.empty:
        trades_path = os.path.join(output_dir, 'verified_trades_local.csv')
        trades.to_csv(trades_path, index=False)
        logger.info('\nTrade log saved to: %s', trades_path)

    if not result.report.empty:
        report_path = os.path.join(output_dir, 'verified_report_local.csv')
        result.report.to_csv(report_path)
        logger.info('Daily report saved to: %s', report_path)


if __name__ == '__main__':
    main()
