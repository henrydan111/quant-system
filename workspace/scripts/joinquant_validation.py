"""
JoinQuant Validation — Fixed-Universe Cheapest-4 Rotation

INSTRUCTIONS:
1. Copy this entire code to JoinQuant (聚宽) strategy editor
2. Set backtest parameters:
   - Start: 2024-06-03
   - End: 2024-12-31
   - Initial cash: ¥100,000
   - Frequency: Daily (每天)
3. Run the backtest
4. Copy the FULL LOG output and summary metrics
5. Compare with local backtest results

Strategy (identical to local run_validation_backtest.py):
    Universe:    10 fixed large-cap stocks (main board only)
    Ranking:     Previous-day close price ascending
    Hold:        Cheapest 4 stocks, equal weight
    Rebalance:   Every 5 trading days at OPEN
    Skip sell:   Yesterday's limit-up stocks
    Costs:       Commission 万3.5, stamp 0.05%, min ¥5
    Slippage:    None (FixedSlippage(0))
"""

from jqdata import *
import pandas as pd
from datetime import timedelta


# Fixed universe — SAME 10 stocks as local version (JQ format)
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
    """Initialize strategy — matches local FixedUniverseStrategy.initialize()."""
    set_option('avoid_future_data', True)
    set_benchmark('000852.XSHG')     # CSI 1000
    set_option('use_real_price', True)

    # NO slippage
    set_slippage(FixedSlippage(0))

    # Costs: commission 万3.5, stamp 0.05%, min ¥5
    # Note: JQ applies stamp tax only on sells automatically
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.0005,              # 0.05% stamp tax (post 2023-08-28)
            open_commission=3.5/10000,     # 万3.5 buy
            close_commission=3.5/10000,    # 万3.5 sell
            close_today_commission=0,
            min_commission=5,
        ),
        type='stock',
    )

    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')

    # Strategy state (matches local self.g)
    g.stock_num = 4
    g.rebalance_interval = 5
    g.day_count = 0
    g.yesterday_HL_list = []

    # Schedule: prepare at 9:05, trade at 9:30 (fills at OPEN)
    run_daily(prepare_stock_list, '9:05')
    run_daily(weekly_adjustment, '9:30')


def prepare_stock_list(context):
    """Track yesterday's limit-up stocks (matches local logic)."""
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
    """Rebalance every 5 trading days (matches local before_market_open)."""
    g.day_count += 1

    # Log HL list if any
    if g.yesterday_HL_list:
        log.info('Day %d [%s] HL stocks: %s'
                 % (g.day_count, str(context.current_dt.date()),
                    str(g.yesterday_HL_list)))

    # Only rebalance on scheduled days (day 1, 6, 11, ...)
    if (g.day_count - 1) % g.rebalance_interval != 0:
        return

    # Get prev-day close for universe
    current_data = get_current_data()
    last_prices = history(1, unit='1d', field='close', security_list=UNIVERSE)

    avail = []
    for stock in UNIVERSE:
        # Skip suspended
        if current_data[stock].paused:
            continue
        price = last_prices[stock][-1]
        avail.append((stock, price))

    # Sort by close ascending → cheapest first
    avail.sort(key=lambda x: x[1])
    target = [s for s, _ in avail[:g.stock_num]]

    current_holds = set(context.portfolio.positions.keys())

    # Sell: not in target, not yesterday's limit-up
    sell_list = [
        s for s in current_holds
        if s not in target and s not in g.yesterday_HL_list
    ]
    # Buy: in target, not already held
    buy_list = [s for s in target if s not in current_holds]

    log.info('Day %d [%s] REBALANCE | Avail: %s'
             % (g.day_count, str(context.current_dt.date()),
                [(s, round(p, 2)) for s, p in avail]))
    log.info('  Target: %s | Sell: %s | Buy: %s | HL: %s'
             % (target, sell_list, buy_list, g.yesterday_HL_list))

    # Execute sells first
    for stock in sell_list:
        if stock in context.portfolio.positions:
            pos = context.portfolio.positions[stock]
            log.info('  SELL %s: %d shares @ open' % (stock, pos.total_amount))
            order_target_value(stock, 0)

    # Execute buys — equal weight
    if buy_list:
        per_stock = context.portfolio.total_value / g.stock_num
        for stock in buy_list:
            log.info('  BUY %s: target_value=%.2f @ open' % (stock, per_stock))
            order_target_value(stock, per_stock)

    # Log portfolio state
    log.info('  Portfolio: cash=%.2f, value=%.2f, positions=%d'
             % (context.portfolio.cash,
                context.portfolio.total_value,
                len(context.portfolio.positions)))
