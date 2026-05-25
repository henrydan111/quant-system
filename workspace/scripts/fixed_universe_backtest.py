"""
Fixed-Universe Validation: Pure Engine Comparison

Uses a PRE-DEFINED list of 10 stocks to eliminate ALL filter differences.
Both local and JQ versions trade the EXACT same stocks.

Strategy:
    - Fixed universe: 10 large/mid-cap main-board stocks
    - Rebalance every 5 trading days
    - Buy top 4 by prev-day close price ascending (cheapest)
    - Equal weight, fill at open
    - No stop-loss, skip yesterday limit-up stocks

This isolates:
    1. Fill price accuracy (open price next day)
    2. Cost computation (commission + stamp tax)
    3. Lot-size rounding
    4. T+1 enforcement
    5. Limit-up/down blocking
"""

import sys, os, logging
sys.path.insert(0, r'e:\量化系统')

import pandas as pd
import numpy as np
from src.backtest_engine.event_driven import (
    EventDrivenBacktester, Strategy, Order, BacktestContext,
    CostConfig, NoSlippage,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger('src.backtest_engine.event_driven').setLevel(logging.WARNING)

DATA_DIR = r'e:\量化系统\data'

# Fixed universe: 10 well-known main-board stocks
# Chosen for: stable trading, no ST issues, no suspension risk, diverse prices
UNIVERSE = [
    '600519.SH',  # 贵州茅台 (high price, will test lot-size with big value)
    '000858.SZ',  # 五粮液
    '000001.SZ',  # 平安银行
    '601318.SH',  # 中国平安
    '600036.SH',  # 招商银行
    '000002.SZ',  # 万科A
    '000568.SZ',  # 泸州老窖
    '601888.SH',  # 中国中免
    '600276.SH',  # 恒瑞医药
    '000651.SZ',  # 格力电器
]


class FixedUniverseRotation(Strategy):
    """Buy cheapest 4 from fixed 10-stock universe, rebalance weekly."""

    def initialize(self, context):
        self.g.stock_num = 4
        self.g.rebalance_interval = 5
        self.g.yesterday_hl_list = []
        logger.info('Fixed universe: %s', UNIVERSE)

    def before_market_open(self, context):
        orders = []
        date = context.date
        day_idx = context.trading_day_index

        # Track yesterday's limit-up
        prev_date = context.feeder.get_prev_trading_day(date)
        if len(context.prev_day_data) > 0 and prev_date is not None:
            prev_idx = context.prev_day_data.set_index('ts_code')
            self.g.yesterday_hl_list = [
                c for c in context.portfolio.positions
                if c in prev_idx.index
                and context.exchange.is_limit_up(prev_idx.loc[c], c, prev_date)
            ]
        else:
            self.g.yesterday_hl_list = []

        if day_idx % self.g.rebalance_interval != 0:
            return orders
        if len(context.prev_day_data) == 0:
            return orders

        # Get prices for universe stocks from prev day
        prev_idx = context.prev_day_data.set_index('ts_code')
        avail = []
        for code in UNIVERSE:
            if code not in prev_idx.index:
                continue
            row = prev_idx.loc[code]
            # Check tradable
            if pd.isna(row.get('vol', 0)) or row.get('vol', 0) == 0:
                continue
            avail.append((code, row['close']))

        # Sort by close price ascending → buy cheapest 4
        avail.sort(key=lambda x: x[1])
        target = [c for c, _ in avail[:self.g.stock_num]]

        current_holds = set(context.portfolio.positions.keys())
        sell_list = [c for c in current_holds
                     if c not in target and c not in self.g.yesterday_hl_list]
        buy_list = [c for c in target if c not in current_holds]

        if sell_list or buy_list:
            logger.info('[%s] Day %d: target=%s, sell=%s, buy=%s',
                        date.strftime('%Y-%m-%d'), day_idx, target,
                        sell_list, buy_list)

        for code in sell_list:
            orders.append(Order(code, 'sell', reason='rebalance'))

        if buy_list:
            prices = dict(zip(context.prev_day_data['ts_code'],
                              context.prev_day_data['close']))
            total_val = context.portfolio.total_value(prices)
            per_stock = total_val / self.g.stock_num
            for code in buy_list:
                orders.append(Order(code, 'buy', target_value=per_stock,
                                    reason='rebalance'))

        return orders


def main():
    print('=' * 70)
    print('Fixed-Universe Validation: 10 Stocks, Buy Cheapest 4')
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
        strategy=FixedUniverseRotation(),
        start_time='2024-01-02',
        end_time='2024-12-31',
        benchmark='000852.SH',
        account=100_000,
        exchange_config=cost_config,
        slippage=NoSlippage(),
        volume_limit=0.25,
    )

    print('\n--- First 20 Trades ---')
    fills = result.trades
    if len(fills) > 0:
        print(fills[['date', 'code', 'direction', 'shares', 'price',
                      'value', 'cost']].head(20).to_string())

    print('\n--- Performance ---')
    s = result.summary
    for k, v in s.items():
        if isinstance(v, float):
            print(f'  {k}: {v:.6f}')
        else:
            print(f'  {k}: {v}')

    print(f'\n--- Trades: {len(fills)} ({len(fills[fills["direction"]=="buy"])} buys, {len(fills[fills["direction"]=="sell"])} sells) ---')

    blocked = result.order_log[result.order_log['status'] == 'BLOCKED']
    print(f'--- Blocked: {len(blocked)} ---')
    if len(blocked) > 0:
        print(blocked[['date', 'code', 'direction', 'detail']].to_string())

    # Save
    output_dir = r'e:\量化系统\workspace\outputs'
    os.makedirs(output_dir, exist_ok=True)
    result.report.to_csv(os.path.join(output_dir, 'fixed_report.csv'))
    result.trades.to_csv(os.path.join(output_dir, 'fixed_trades.csv'), index=False)
    print(f'\nSaved to {output_dir}/')


if __name__ == '__main__':
    main()
