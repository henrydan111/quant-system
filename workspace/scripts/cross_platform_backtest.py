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
Cross-Platform Validation Backtest: Small-Cap Weekly Rotation

Simplified version of the JoinQuant small-cap strategy for cross-platform
comparison. Both local and JQ versions use identical rules:

Strategy Rules:
    1. Universe: All A-shares
    2. Filter: Main board only (600/601/603/000/001/002/003)
    3. Filter: Not ST
    4. Filter: Not suspended (vol == 0)
    5. Filter: Not limit-up (can't buy new positions)
    6. Filter: IPO > 375 calendar days
    7. Filter: close price <= 50
    8. Filter: Market cap between 10亿 and 100亿
    9. Sort: Market cap ascending (smallest first)
    11. Hold: Top 4 stocks
    12. Rebalance: Every 5 trading days (≈ weekly) at OPEN
    13. T+1: Cannot sell stocks bought today
    14. Skip selling yesterday's limit-up stocks (hold 1 more day)
    15. Equal weight across all target positions

Costs (matching JQ template):
    - Buy commission: 0.035% (万3.5)
    - Sell commission: 0.035%
    - Stamp tax: 0.1% (sell only, pre 2023-08-28) / 0.05% (post)
    - Min commission: ¥5
    - Slippage: None (for exact comparison)

Period: 2024-01-02 to 2024-12-31
Benchmark: 中证1000 (000852.SH)
Cash: ¥100,000
"""

import sys
import os
import logging

sys.path.insert(0, r'e:\量化系统')

import pandas as pd
import numpy as np

from src.backtest_engine.event_driven import (
    EventDrivenBacktester, Strategy, Order, BacktestContext,
    CostConfig, NoSlippage,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)
logging.getLogger('src.backtest_engine.event_driven').setLevel(logging.WARNING)

DATA_DIR = r'e:\量化系统\data'

# Main board prefixes (exclude ChiNext 300/301, STAR 688/689, BSE 8xx/4xx)
MAIN_BOARD_PREFIXES = ('600', '601', '603', '000', '001', '002', '003')


class SmallCapRotation(Strategy):
    """Simplified small-cap weekly rotation strategy.

    Replicates JQ template strategy with daily-only data access.
    Weekly rebalance, market cap 10-100亿, main board, not ST,
    IPO > 375d, sort by market cap asc, buy top 4.
    """

    def initialize(self, context: BacktestContext) -> None:
        """Set strategy parameters."""
        self.g.stock_num = 4
        self.g.min_mv = 100_000      # 10亿 = 100,000 万元
        self.g.max_mv = 1_000_000    # 100亿 = 1,000,000 万元
        self.g.highest = 50          # Max price per share
        self.g.rebalance_interval = 5  # Every 5 trading days
        self.g.yesterday_hl_list = []

        # Pre-load stock_basic for IPO date filter
        sb = context.feeder.get_stock_basic()
        sb['list_date'] = pd.to_datetime(
            sb['list_date'], format='%Y%m%d', errors='coerce'
        )
        self.g.stock_basic = sb

        logger.info(
            'Strategy initialized: stock_num=%d, mv=[%.0f, %.0f]万',
            self.g.stock_num, self.g.min_mv, self.g.max_mv,
        )

    def _filter_and_rank(self, context: BacktestContext, date: pd.Timestamp) -> list[str]:
        """Apply all filters and return ranked candidate list.

        Args:
            context: Backtest context for DB access.
            date: Date of the data (prev_date).

        Returns:
            List of ts_codes sorted by market cap ascending.
        """
        df = context.prev_day_data.copy()

        # 1. Main board only
        df = df[df['ts_code'].str[:3].isin(MAIN_BOARD_PREFIXES)]

        # 2. Not suspended
        df = df[df['vol'].notna() & (df['vol'] > 0)]

        # 3. Price <= highest
        df = df[df['close'] <= self.g.highest]
        
        stocks = df['ts_code'].tolist()
        if not stocks:
            return []
            
        # 4. Fetch fundamental features from Qlib for eligible stocks
        # Market cap 10-100亿
        features = context.feeder.get_features(
            stocks, ['$total_mv'], start_time=date, end_time=date
        )
        if not features.empty:
            features = features.reset_index().rename(
                columns={'instrument': 'ts_code', '$total_mv': 'total_mv'}
            )
            if 'datetime' in features.columns:
                features = features.drop(columns=['datetime'])
            df = pd.merge(df, features, on='ts_code', how='inner')
        else:
            return []
            
        if 'total_mv' in df.columns:
            df = df[df['total_mv'].between(self.g.min_mv, self.g.max_mv)]

        # 5. IPO > 375 days
        ipo_cutoff = date - pd.Timedelta(days=375)
        eligible = self.g.stock_basic[
            self.g.stock_basic['list_date'] <= ipo_cutoff
        ]['ts_code'].values
        df = df[df['ts_code'].isin(eligible)]

        # 6. Not ST
        exchange = context.exchange
        df = df[~df['ts_code'].apply(lambda c: exchange.is_st(c, date))]

        # 8. Not limit-up (可买入)
        if 'pre_close' in df.columns:
            def not_limit_up(row):
                is_st = exchange.is_st(row['ts_code'], date)
                pct = exchange.get_limit_pct(row['ts_code'], is_st, date)
                limit_up = round(row['pre_close'] * (1 + pct), 2)
                return abs(row['close'] - limit_up) >= 0.005
            df = df[df.apply(not_limit_up, axis=1)]

        # Sort by market cap ascending
        if 'total_mv' in df.columns:
            df = df.sort_values('total_mv', ascending=True)

        return list(df['ts_code'].head(self.g.stock_num * 3))

    def before_market_open(self, context: BacktestContext) -> list[Order]:
        """Weekly rebalance at open.

        Sells-before-buys are handled by the engine automatically.

        Returns:
            List of sell and buy orders.
        """
        orders = []
        date = context.date
        day_idx = context.trading_day_index

        # --- Track yesterday's limit-up stocks ---
        prev_date = context.feeder.get_prev_trading_day(date)
        if len(context.prev_day_data) > 0 and prev_date is not None:
            prev_indexed = context.prev_day_data.set_index('ts_code')
            new_hl = []
            for code in context.portfolio.positions:
                if code in prev_indexed.index:
                    row = prev_indexed.loc[code]
                    if context.exchange.is_limit_up(row, code, prev_date):
                        new_hl.append(code)
            self.g.yesterday_hl_list = new_hl
        else:
            self.g.yesterday_hl_list = []

        # --- Only rebalance every N days ---
        if day_idx % self.g.rebalance_interval != 0:
            return orders

        if len(context.prev_day_data) == 0:
            return orders

        # --- Get candidates from PREVIOUS day's data (no lookahead) ---
        prev_date = context.feeder.get_prev_trading_day(date)
        candidates = self._filter_and_rank(context, prev_date)

        if not candidates:
            logger.info('[%s] No candidates found', date.strftime('%Y-%m-%d'))
            return orders

        # --- Determine target portfolio ---
        current_holds = set(context.portfolio.positions.keys())
        target = candidates[:self.g.stock_num]

        # Determine sells: stocks we hold that are NOT in target
        # BUT skip yesterday's limit-up stocks (hold 1 extra day)
        sell_list = [
            c for c in current_holds
            if c not in target and c not in self.g.yesterday_hl_list
        ]

        # Determine buys: stocks in target that we don't hold
        buy_list = [c for c in target if c not in current_holds]

        if sell_list or buy_list:
            logger.info(
                '[%s] Rebalance day %d: target=%s, sell=%s, buy=%s, hl=%s',
                date.strftime('%Y-%m-%d'), day_idx,
                target, sell_list, buy_list, self.g.yesterday_hl_list
            )

        # --- Generate sell orders first ---
        for code in sell_list:
            orders.append(Order(code, 'sell', reason='rebalance_out'))

        # --- Generate buy orders with equal weight ---
        if buy_list:
            # Estimate available cash = current cash + value of sell positions
            prices_prev = dict(zip(
                context.prev_day_data['ts_code'],
                context.prev_day_data['close'],
            ))
            total_val = context.portfolio.total_value(prices_prev)

            # Equal weight per target slot
            per_stock = total_val / self.g.stock_num

            for code in buy_list:
                orders.append(Order(
                    code, 'buy',
                    target_value=per_stock,
                    reason='rebalance_in',
                ))

        return orders


def main():
    """Run the local backtest and print results."""
    print('=' * 70)
    print('Cross-Platform Validation: Small-Cap Weekly Rotation')
    print('=' * 70)

    cost_config = CostConfig(
        buy_commission=0.00035,
        sell_commission=0.00035,
        stamp_tax=0.0005,
        stamp_tax_pre_20230828=0.001,
        min_commission=5.0,
    )

    bt = EventDrivenBacktester(data_dir=DATA_DIR)
    result = bt.run(
        strategy=SmallCapRotation(),
        start_time='2024-01-02',
        end_time='2024-12-31',
        benchmark='000852.SH',
        account=100_000,
        exchange_config=cost_config,
        slippage=NoSlippage(),
        volume_limit=0.25,
        preload_fields=['$open', '$close', '$high', '$low', '$vol', '$amount', '$pre_close', '$total_mv'],
    )

    # Print results
    print('\n' + '=' * 70)
    print('BACKTEST RESULTS')
    print('=' * 70)

    print('\n--- Daily Report (first 10 days) ---')
    print(result.report[
        ['return', 'total_value', 'cash', 'n_positions']
    ].head(10))

    print('\n--- Daily Report (last 10 days) ---')
    print(result.report[
        ['return', 'total_value', 'cash', 'n_positions']
    ].tail(10))

    print('\n--- Trade Summary ---')
    fills = result.trades
    buys = fills[fills['direction'] == 'buy']
    sells = fills[fills['direction'] == 'sell']
    print(f'Total trades: {len(fills)}')
    print(f'  Buys: {len(buys)}, Sells: {len(sells)}')
    if len(fills) > 0:
        print(f'  Total costs: Y{fills["cost"].sum():.2f}')

    print('\n--- First 30 Trades ---')
    if len(fills) > 0:
        print(fills[
            ['date', 'code', 'direction', 'shares', 'price', 'value', 'cost']
        ].head(30).to_string())

    print('\n--- Performance Summary (JoinQuant-Compatible) ---')
    s = result.summary
    for k, v in s.items():
        if isinstance(v, float):
            print(f'  {k}: {v:.6f}')
        else:
            print(f'  {k}: {v}')

    print('\n--- Equity Curve ---')
    ec = result.equity_curve
    print(f'  Start: {ec.iloc[0]:.4f}')
    print(f'  End:   {ec.iloc[-1]:.4f}')
    print(f'  Min:   {ec.min():.4f}')
    print(f'  Max:   {ec.max():.4f}')

    print('\n--- Blocked Orders (first 20) ---')
    blocked = result.order_log[result.order_log['status'] == 'BLOCKED']
    print(f'Total blocked: {len(blocked)}')
    if len(blocked) > 0:
        print(blocked[
            ['date', 'code', 'direction', 'detail']
        ].head(20).to_string())

    print('\n--- Unique Stocks Traded ---')
    if len(fills) > 0:
        unique = fills['code'].unique()
        print(f'  Count: {len(unique)}')
        print(f'  Stocks: {list(unique[:20])}...')

    # Save detailed results
    output_dir = os.path.join(r'e:\量化系统\workspace\outputs')
    os.makedirs(output_dir, exist_ok=True)
    result.report.to_csv(os.path.join(output_dir, 'local_report.csv'))
    result.trades.to_csv(
        os.path.join(output_dir, 'local_trades.csv'), index=False
    )
    result.order_log.to_csv(
        os.path.join(output_dir, 'local_orders.csv'), index=False
    )
    result.daily_holdings.to_csv(
        os.path.join(output_dir, 'local_holdings.csv'), index=False
    )
    print(f'\nResults saved to {output_dir}/')
    print('=' * 70)


if __name__ == '__main__':
    main()
