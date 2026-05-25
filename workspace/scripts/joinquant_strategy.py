"""
JoinQuant Version — Small-Cap Weekly Rotation (Cross-Platform Validation)

INSTRUCTIONS:
1. Copy this entire code to JoinQuant (聚宽) strategy editor
2. Set backtest parameters:
   - Start: 2024-01-02
   - End: 2024-12-31
   - Initial cash: ¥100,000
   - Frequency: Daily (每天)
3. Run the backtest
4. Compare results with local backtest output

This strategy is a SIMPLIFIED version designed for exact cross-platform
comparison. The rules are identical to the local SmallCapRotation:

Rules:
    1. Universe: All A-shares, main board only (not ChiNext/STAR/BSE)
    2. Filter: Not ST, not suspended, not limit-up
    3. Filter: IPO > 375 calendar days
    4. Filter: Close price <= 50
    5. Filter: Market cap 10亿-100亿
    6. Sort: Market cap ascending
    7. Hold: 4 stocks, equal weight
    8. Rebalance: Every 5 trading days at OPEN
    9. Skip selling yesterday's limit-up stocks
   10. Costs: commission=万3.5, stamp_tax=0.1% (built-in), min=¥5
   11. No slippage (for comparison)

Expected Results (from local backtest):
    - Total Return: ~28.8%
    - Max Drawdown: ~46.9%
    - Sharpe: ~0.79
    - Total trades: 62
    - Unique stocks: 11
"""

from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
from datetime import timedelta


def initialize(context):
    """Initialize strategy parameters and scheduled jobs."""
    # Prevent future data
    set_option('avoid_future_data', True)
    
    # Benchmark: 中证1000
    set_benchmark('000852.XSHG')
    
    # Use real prices
    set_option('use_real_price', True)
    
    # NO slippage for exact comparison
    set_slippage(FixedSlippage(0))
    
    # Costs: commission=万3.5, stamp=0.1%, min=¥5
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.001,          # 0.1% stamp tax (sell only)
            open_commission=3.5/10000, # 万3.5 buy
            close_commission=3.5/10000,# 万3.5 sell
            close_today_commission=0,
            min_commission=5,
        ),
        type='stock',
    )
    
    # Log levels
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')
    
    # Strategy parameters
    g.stock_num = 4           # Number of stocks to hold
    g.min_mv = 10             # Min market cap in 亿
    g.max_mv = 100            # Max market cap in 亿
    g.highest = 50            # Max stock price
    g.rebalance_interval = 5  # Rebalance every N trading days
    g.day_count = 0           # Trading day counter
    g.yesterday_HL_list = []  # Yesterday's limit-up stocks
    
    # Schedule daily preparation and rebalance
    run_daily(prepare_stock_list, '9:05')
    run_daily(weekly_adjustment, '9:30')


def prepare_stock_list(context):
    """Track yesterday's limit-up stocks in held positions."""
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


def get_stock_list(context):
    """Generate ranked candidate list using query API.
    
    Filters:
    - Main board (exclude ChiNext 300/301, STAR 688/689, BSE)
    - Not ST, not suspended
    - Market cap 10-100亿
    - Close price <= 50
    - IPO > 375 days
    - Not limit-up
    
    Returns:
        List of stock codes sorted by market cap ascending.
    """
    # Start with all A-shares, filtered to main board
    all_stocks = list(get_all_securities(['stock']).index)
    
    # Filter to main board (000/001/002/003/600/601/603 prefixes)
    main_board = [
        s for s in all_stocks
        if s[:3] in ('000', '001', '002', '003', '600', '601', '603')
    ]
    
    # Apply standard filters
    initial_list = filter_stocks(context, main_board)
    
    # Query fundamentals
    q = query(
        valuation.code,
        valuation.market_cap,
    ).filter(
        valuation.code.in_(initial_list),
        valuation.market_cap.between(g.min_mv, g.max_mv),
    ).order_by(
        valuation.market_cap.asc()
    ).limit(
        g.stock_num * 3
    )
    
    df = get_fundamentals(q)
    final_list = list(df.code)
    
    # Filter by price
    if final_list:
        last_prices = history(
            1, unit='1d', field='close', security_list=final_list
        )
        final_list = [
            s for s in final_list
            if s in context.portfolio.positions
            or last_prices[s][-1] <= g.highest
        ]
    
    return final_list


def filter_stocks(context, stock_list):
    """Filter for suspension, ST, delisting, limit, IPO.
    
    Matches local backtester's filter logic exactly.
    """
    current_data = get_current_data()
    last_prices = history(
        1, unit='1m', field='close', security_list=stock_list
    )
    
    filtered = []
    for stock in stock_list:
        # Skip suspended
        if current_data[stock].paused:
            continue
        # Skip ST
        if current_data[stock].is_st:
            continue
        # Skip delisted
        if '退' in current_data[stock].name:
            continue
        # Skip limit-up (can't buy, unless already held)
        if not (stock in context.portfolio.positions
                or last_prices[stock][-1] < current_data[stock].high_limit):
            continue
        # Skip IPO < 375 days
        start_date = get_security_info(stock).start_date
        if context.previous_date - start_date < timedelta(days=375):
            continue
        filtered.append(stock)
    
    return filtered


def weekly_adjustment(context):
    """Rebalance every g.rebalance_interval trading days."""
    g.day_count += 1
    
    # Only rebalance on scheduled days (day 1, 6, 11, 16, ...)
    if (g.day_count - 1) % g.rebalance_interval != 0:
        return
    
    # Get target list
    target_list = get_stock_list(context)[:g.stock_num]
    log.info('Day %d | Target: %s' % (g.day_count, str(target_list)))
    
    current_holds = set(context.portfolio.positions.keys())
    
    # Determine sells (skip yesterday limit-up stocks)
    sell_list = [
        s for s in current_holds
        if s not in target_list
        and s not in g.yesterday_HL_list
    ]
    
    # Determine buys
    buy_list = [s for s in target_list if s not in current_holds]
    
    log.info('Sell: %s | Buy: %s | HL: %s'
             % (str(sell_list), str(buy_list), str(g.yesterday_HL_list)))
    
    # Execute sells first
    for stock in sell_list:
        if stock in context.portfolio.positions:
            order_target_value(stock, 0)
            log.info('SELL %s' % stock)
    
    # Execute buys with equal weight
    if buy_list:
        # Equal weight across all target positions
        per_stock = context.portfolio.total_value / g.stock_num
        for stock in buy_list:
            order_target_value(stock, per_stock)
            log.info('BUY %s target=%.2f' % (stock, per_stock))
    
    # Log portfolio
    log.info(
        'Portfolio: cash=%.2f, value=%.2f, positions=%d'
        % (context.portfolio.cash,
           context.portfolio.total_value,
           len(context.portfolio.positions))
    )
