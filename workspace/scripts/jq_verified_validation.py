"""
JoinQuant Verified-Factor Validation Strategy

INSTRUCTIONS:
1. Copy this entire code to JoinQuant (聚宽) strategy editor
2. Set backtest parameters:
   - Start: 2024-01-02
   - End: 2024-12-31
   - Initial cash: ¥200,000
   - Frequency: Daily (每天)
3. Run the backtest
4. Copy summary metrics + download transaction CSV

Strategy uses ONLY factors verified identical between Tushare/Qlib and JQ:
    1. Market Cap      (✅ 100% exact match) — smaller = better
    2. Turnover Rate   (✅ 100% exact match) — lower = better
    3. 20d Return      (✅ 96.4% match)      — lower = better (reversal)

Universe:    CSI 300, main board only
Hold:        Top 6 stocks
Rebalance:   Every 10 trading days at OPEN
Costs:       Commission 万3.5, stamp 0.05%, min ¥5, no slippage
"""

from jqdata import *
import numpy as np
import pandas as pd


def initialize(context):
    """Initialize strategy — mirrors local VerifiedFactorStrategy."""
    set_option('avoid_future_data', True)
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)

    set_slippage(FixedSlippage(0))

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

    Uses ONLY verified-identical factors:
    1. Size:     Market cap (lower = better) → data verified 100% match
    2. Turnover: Turnover rate (lower = better) → data verified 100% match
    3. Reversal: 20d return (lower = better) → data verified 96.4% match

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

    # Get valuation data — market cap and turnover (both verified ✅)
    q = query(
        valuation.code,
        valuation.market_cap,          # 总市值 (亿元) — ✅ exact match
        valuation.turnover_ratio,      # 换手率 (%)   — ✅ exact match
    ).filter(
        valuation.code.in_(filtered),
    )
    val_df = get_fundamentals(q)

    if val_df.empty:
        return []

    valid_stocks = list(val_df.code)

    # Get 20-day returns (verified ✅ 96.4% match)
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
    for _, row in val_df.iterrows():
        code = row['code']
        market_cap = row['market_cap']
        turnover = row['turnover_ratio']

        if pd.isna(market_cap) or market_cap <= 0:
            continue
        if pd.isna(turnover):
            continue

        # 20d momentum
        stock_prices = price_df[price_df['code'] == code]['close'].values
        mom_20d = np.nan
        if len(stock_prices) >= 21:
            if stock_prices[0] > 0:
                mom_20d = stock_prices[-1] / stock_prices[0] - 1

        records.append({
            'code': code,
            'market_cap': market_cap,
            'turnover': turnover,
            'mom_20d': mom_20d,
        })

    if not records:
        return []

    df = pd.DataFrame(records)

    # Composite score — matches local exactly
    # Lower market cap = better → 1 - rank
    df['v_size'] = 1 - df['market_cap'].rank(pct=True)

    # Lower turnover = better → 1 - rank
    df['v_turn'] = 1 - df['turnover'].rank(pct=True)

    # Lower momentum = better (reversal) → 1 - rank
    if df['mom_20d'].notna().sum() > 5:
        df['v_mom'] = 1 - df['mom_20d'].rank(pct=True)
    else:
        df['v_mom'] = 0.5

    # Equal weight composite (3 factors)
    df['composite'] = (df['v_size'] + df['v_turn'] + df['v_mom']) / 3
    df = df.sort_values('composite', ascending=False)

    # Log top stocks
    for _, r in df.head(g.stock_num).iterrows():
        log.info('  %-15s Turn=%.2f Mom=%.3f MV=%.0f亿 Score=%.3f'
                 % (r['code'], r['turnover'],
                    r['mom_20d'] if not np.isnan(r['mom_20d']) else 0,
                    r['market_cap'], r['composite']))

    return list(df.head(g.stock_num * 2)['code'])


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
        if s in context.portfolio.positions:
            target.append(s)
            continue
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
