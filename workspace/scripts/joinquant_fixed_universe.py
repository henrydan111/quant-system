"""
JoinQuant Version — Fixed-Universe Validation Strategy

INSTRUCTIONS:
1. Copy this entire code to JoinQuant (聚宽) strategy editor
2. Set backtest parameters:
   - Start: 2024-01-02
   - End: 2024-12-31
   - Initial cash: ¥100,000
   - Frequency: Daily (每天)
3. Run and compare with local results

Strategy:
    - Fixed 10-stock universe (large/mid-cap main board)
    - Buy cheapest 4 by prev-day close price
    - Rebalance every 5 trading days at open
    - Equal weight
    - No stop-loss
    - Skip selling yesterday's limit-up stocks

Costs: commission=万3.5, stamp=0.1%, min=¥5, NO slippage

Expected Local Results:
    - Day 1 buys: 000001.SZ, 000002.SZ, 600036.SH, 000651.SZ
    - Total Return: 26.28%
    - Max Drawdown: 13.35%
    - Sharpe: 1.249
    - Total trades: 16 (10 buys, 6 sells)
"""

from jqdata import *
import pandas as pd
from datetime import timedelta


# Fixed universe — SAME 10 stocks as local version
UNIVERSE = [
    '600519.XSHG',  # 贵州茅台
    '000858.XSHE',  # 五粮液
    '000001.XSHE',  # 平安银行
    '601318.XSHG',  # 中国平安
    '600036.XSHG',  # 招商银行
    '000002.XSHE',  # 万科A
    '000568.XSHE',  # 泸州老窖
    '601888.XSHG',  # 中国中免
    '600276.XSHG',  # 恒瑞医药
    '000651.XSHE',  # 格力电器
]


def initialize(context):
    set_option('avoid_future_data', True)
    set_benchmark('000852.XSHG')
    set_option('use_real_price', True)
    set_slippage(FixedSlippage(0))
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.001,
            open_commission=3.5/10000,
            close_commission=3.5/10000,
            close_today_commission=0,
            min_commission=5,
        ),
        type='stock',
    )
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')

    g.stock_num = 4
    g.rebalance_interval = 5
    g.day_count = 0
    g.yesterday_HL_list = []

    run_daily(prepare_stock_list, '9:05')
    run_daily(weekly_adjustment, '9:30')


def prepare_stock_list(context):
    g.hold_list = list(context.portfolio.positions.keys())
    if g.hold_list:
        df = get_price(
            g.hold_list,
            end_date=context.previous_date,
            frequency='daily',
            fields=['close', 'high_limit'],
            count=1,
            panel=False,
            fill_paused=False,
        )
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)
    else:
        g.yesterday_HL_list = []


def weekly_adjustment(context):
    g.day_count += 1

    if (g.day_count - 1) % g.rebalance_interval != 0:
        return

    # Get prev-day close prices for universe
    current_data = get_current_data()
    last_prices = history(1, unit='1d', field='close', security_list=UNIVERSE)

    avail = []
    for stock in UNIVERSE:
        if current_data[stock].paused:
            continue
        price = last_prices[stock][-1]
        avail.append((stock, price))

    # Sort by close ascending → cheapest 4
    avail.sort(key=lambda x: x[1])
    target = [s for s, _ in avail[:g.stock_num]]

    current_holds = set(context.portfolio.positions.keys())
    sell_list = [s for s in current_holds
                 if s not in target and s not in g.yesterday_HL_list]
    buy_list = [s for s in target if s not in current_holds]

    log.info('Day %d | Target: %s | Sell: %s | Buy: %s | HL: %s'
             % (g.day_count, target, sell_list, buy_list, g.yesterday_HL_list))

    # Sells first
    for stock in sell_list:
        if stock in context.portfolio.positions:
            order_target_value(stock, 0)
            log.info('SELL %s' % stock)

    # Buys — equal weight
    if buy_list:
        per_stock = context.portfolio.total_value / g.stock_num
        for stock in buy_list:
            order_target_value(stock, per_stock)
            log.info('BUY %s target=%.2f' % (stock, per_stock))

    log.info('Portfolio: cash=%.2f, value=%.2f, positions=%d'
             % (context.portfolio.cash,
                context.portfolio.total_value,
                len(context.portfolio.positions)))
