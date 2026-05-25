"""
JoinQuant Multi-Factor PIT Validation Strategy

INSTRUCTIONS:
1. Copy this entire code to JoinQuant (聚宽) strategy editor
2. Set backtest parameters:
   - Start: 2024-01-02
   - End: 2024-12-31
   - Initial cash: ¥200,000
   - Frequency: Daily (每天)
3. Run the backtest
4. Copy FULL LOG and summary metrics back

Strategy (mirrors local run_multifactor_validation.py):
    Universe:    CSI 300, main board, market cap > 50亿, PE > 0
    Factors:     PE_TTM (value), raw quarterly revenue, 20d reversal, market cap
    Composite:   Equal-weight percentile rank
    Hold:        Top 6 stocks
    Rebalance:   Every 10 trading days at OPEN
    Costs:       Commission 万3.5, stamp 0.05%, min ¥5, no slippage

PIT Test Focus:
    PE_TTM and revenue_q use quarterly financial data which has delayed
    announcements. Both platforms should apply PIT-correct data (using
    announcement date, not report end_date). If our local data has PIT
    issues, the stock rankings will diverge significantly from JQ.
"""

from jqdata import *
import numpy as np
import pandas as pd
from datetime import timedelta


def initialize(context):
    """Initialize strategy — matches local MultiFactorStrategy."""
    set_option('avoid_future_data', True)
    set_benchmark('000300.XSHG')     # CSI 300
    set_option('use_real_price', True)

    # NO slippage
    set_slippage(FixedSlippage(0))

    # Costs: commission 万3.5, stamp 0.05%, min ¥5
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.0005,
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

    g.stock_num = 6
    g.rebalance_interval = 10
    g.day_count = 0
    g.yesterday_HL_list = []

    run_daily(prepare_stock_list, '9:05')
    run_daily(rebalance, '9:30')


def prepare_stock_list(context):
    """Track yesterday's limit-up stocks."""
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


def get_candidates(context):
    """Build factor-ranked candidate list from CSI 300.

    Matches local factor construction exactly:
    1. Value:    PE_TTM (lower = better)
    2. Revenue:  Single-quarter revenue (higher = better) — matches local $revenue_q
    3. Reversal: 20d return (lower = better)
    4. Size:     Market cap (lower = better)

    Returns:
        list of stock codes sorted by composite score descending.
    """
    # Get CSI 300 constituents
    csi300 = get_index_stocks('000300.XSHG', date=context.previous_date)

    # Filter: main board only (exclude 300/301 ChiNext, 688/689 STAR)
    main_board = [
        s for s in csi300
        if s[:3] not in ('300', '301', '688', '689')
        and s[0] not in ('8', '4', '9')
    ]

    # Filter: not ST, not paused
    current_data = get_current_data()
    filtered = []
    for s in main_board:
        if current_data[s].paused:
            continue
        if current_data[s].is_st:
            continue
        if '退' in current_data[s].name:
            continue
        filtered.append(s)

    if not filtered:
        return []

    # Get fundamentals (PIT-correct via JQ's get_fundamentals)
    q = query(
        valuation.code,
        valuation.market_cap,          # 总市值 (亿元)
        valuation.pe_ratio,            # PE TTM
    ).filter(
        valuation.code.in_(filtered),
        valuation.market_cap >= 50,    # > 50亿
        valuation.pe_ratio > 0,        # Profitable (PE > 0)
    )
    fund_df = get_fundamentals(q)

    if fund_df.empty:
        return []

    valid_stocks = list(fund_df.code)

    # ─── Single-Quarter Revenue (matches local $revenue_q) ───────────
    # JQ's income.operating_revenue is cumulative YTD.
    # Our local $revenue_q is single-quarter revenue from Tushare.
    # To match: single_q = current_cumulative - prev_quarter_cumulative
    # For Q1 reports, single_q = cumulative (since it IS the first quarter)
    #
    # get_fundamentals(date=X) returns the latest PIT-correct financial report.
    # We also need the PREVIOUS quarter's cumulative to compute deduction.
    q_rev = query(
        income.code,
        income.operating_revenue,      # 营业收入 (cumulative YTD)
        income.statDate,               # Report period (e.g. '2024-03-31')
    ).filter(
        income.code.in_(valid_stocks),
    )
    rev_df = get_fundamentals(q_rev)

    # For prev quarter: go back ~95 days to get a reference date in the
    # previous reporting quarter, then query PIT data at that date
    prev_q_date = context.previous_date - timedelta(days=95)
    rev_prev_df = get_fundamentals(q_rev, date=prev_q_date)

    # Build single-quarter revenue dict
    rev_single_q = {}
    for _, row in rev_df.iterrows():
        code = row['code']
        cur_cum = row['operating_revenue']
        stat_date = str(row['statDate']) if row['statDate'] is not None else ''

        if pd.isna(cur_cum):
            continue

        # Determine if this is a Q1 report (cumulative = single quarter)
        is_q1 = stat_date.endswith('-03-31') or stat_date.endswith('0331')

        if is_q1:
            # Q1: cumulative IS single-quarter
            rev_single_q[code] = cur_cum
        else:
            # Q2/Q3/Q4: single_q = current_cumulative - prev_cumulative
            prev_row = rev_prev_df[rev_prev_df['code'] == code]
            if not prev_row.empty:
                prev_cum = prev_row['operating_revenue'].values[0]
                prev_stat = str(prev_row['statDate'].values[0]) if prev_row['statDate'].values[0] is not None else ''
                if not pd.isna(prev_cum) and prev_stat != stat_date:
                    single_q = cur_cum - prev_cum
                    rev_single_q[code] = single_q
                else:
                    # Same report period or NaN — use cumulative as fallback
                    rev_single_q[code] = cur_cum
            else:
                rev_single_q[code] = cur_cum

    # Get 20-day returns
    price_df = get_price(
        valid_stocks,
        end_date=context.previous_date,
        frequency='daily',
        fields=['close'],
        count=21,
        panel=False,
    )

    # Build factor DataFrame
    records = []
    for _, row in fund_df.iterrows():
        code = row['code']
        pe_ttm = row['pe_ratio']
        market_cap = row['market_cap']  # 亿元

        # Single-quarter revenue (matches local $revenue_q)
        revenue_q = rev_single_q.get(code, np.nan)

        # 20d momentum
        stock_prices = price_df[price_df['code'] == code]['close'].values
        mom_20d = np.nan
        if len(stock_prices) >= 21:
            if stock_prices[0] > 0:
                mom_20d = stock_prices[-1] / stock_prices[0] - 1

        # Skip if revenue is missing or <= 0
        if np.isnan(revenue_q) or revenue_q <= 0:
            continue

        records.append({
            'code': code,
            'pe_ttm': pe_ttm,
            'market_cap': market_cap,
            'revenue_q': revenue_q,
            'mom_20d': mom_20d,
        })

    if not records:
        return []

    df = pd.DataFrame(records)

    # Compute composite score (matches local exactly)
    # Lower PE = better → 1 - rank(ascending)
    df['v_pe'] = 1 - df['pe_ttm'].rank(pct=True)

    # Higher revenue = better → rank(ascending) directly
    df['v_rev'] = df['revenue_q'].rank(pct=True)

    # Lower momentum = better (reversal) → 1 - rank(ascending)
    if df['mom_20d'].notna().sum() > 5:
        df['v_mom'] = 1 - df['mom_20d'].rank(pct=True)
    else:
        df['v_mom'] = 0.5

    # Lower size = better → 1 - rank(ascending)
    df['v_size'] = 1 - df['market_cap'].rank(pct=True)

    # Equal weight composite
    df['composite'] = (df['v_pe'] + df['v_rev'] + df['v_mom'] + df['v_size']) / 4
    df = df.sort_values('composite', ascending=False)

    # Log top stocks
    for _, r in df.head(g.stock_num).iterrows():
        log.info('  %-15s PE=%.1f Rev=%.0f Mom=%.3f MV=%.0f亿 Score=%.3f'
                 % (r['code'], r['pe_ttm'],
                    r['revenue_q'] if not np.isnan(r['revenue_q']) else 0,
                    r['mom_20d'] if not np.isnan(r['mom_20d']) else 0,
                    r['market_cap'], r['composite']))

    return list(df.head(g.stock_num * 2)['code'])  # Return extra for filtering


def rebalance(context):
    """Rebalance every 10 trading days."""
    g.day_count += 1

    if g.yesterday_HL_list:
        log.info('Day %d [%s] HL stocks: %s'
                 % (g.day_count, str(context.current_dt.date()),
                    str(g.yesterday_HL_list)))

    if (g.day_count - 1) % g.rebalance_interval != 0:
        return

    log.info('Day %d [%s] REBALANCE' % (g.day_count, str(context.current_dt.date())))

    # Get ranked candidates
    candidates = get_candidates(context)

    if not candidates:
        log.info('  No candidates, skipping rebalance')
        return

    # Filter limit-up for buys
    current_data = get_current_data()
    target = []
    for s in candidates:
        if len(target) >= g.stock_num:
            break
        # If already held, keep
        if s in context.portfolio.positions:
            target.append(s)
            continue
        # For new buys, skip limit-up
        try:
            last_px = history(1, unit='1m', field='close', security_list=[s])
            if last_px[s][-1] < current_data[s].high_limit:
                target.append(s)
        except:
            target.append(s)

    current_holds = set(context.portfolio.positions.keys())
    sell_list = [s for s in current_holds
                 if s not in target and s not in g.yesterday_HL_list]
    buy_list = [s for s in target if s not in current_holds]

    log.info('  Target: %s' % target[:g.stock_num])
    log.info('  Sell: %s | Buy: %s | HL: %s'
             % (sell_list, buy_list, g.yesterday_HL_list))

    # Sells first
    for stock in sell_list:
        if stock in context.portfolio.positions:
            pos = context.portfolio.positions[stock]
            log.info('  SELL %s: %d shares' % (stock, pos.total_amount))
            order_target_value(stock, 0)

    # Buys — equal weight
    if buy_list:
        per_stock = context.portfolio.total_value / g.stock_num
        for stock in buy_list:
            log.info('  BUY %s: target=%.2f' % (stock, per_stock))
            order_target_value(stock, per_stock)

    log.info('  Portfolio: cash=%.2f, value=%.2f, positions=%d'
             % (context.portfolio.cash,
                context.portfolio.total_value,
                len(context.portfolio.positions)))
