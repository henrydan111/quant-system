"""
JoinQuant Small-Cap Strategy (小市值排除3个bug版) — Local Recreation

Recreates the JoinQuant strategy from:
  https://www.joinquant.com/post/47933
  https://www.joinquant.com/post/47791

Core logic:
  1. Universe: CSI 1000 (中证1000) constituents
  2. Filter: Main-board only, market cap 10–100亿, positive profit, revenue > 1亿,
     listed > 375 days, price ≤ 50, exclude ST/paused/delisted
  3. Signal: Rank by market cap ascending (smallest = most desirable)
  4. Hold: Top 4 smallest stocks, ~weekly rebalance

Adapted from JoinQuant's event-driven framework to the local Qlib 4-layer pipeline.
Intraday features (stop-loss, limit-up monitoring) are omitted.

Usage:
    python smallcap_jq_strategy.py
"""

import os
import sys
import logging
import warnings
import numpy as np
import pandas as pd

# Project root
PROJECT_ROOT = r'e:\量化系统'
sys.path.insert(0, PROJECT_ROOT)

# Suppress noisy warnings
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=UserWarning)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════

# --- Date range ---
START_DATE = '2015-01-01'
END_DATE = '2026-02-26'         # 1 day before last calendar date to avoid Qlib boundary error

# --- Strategy parameters ---
STRATEGY_TYPE = 'topk_dropout'
TOP_K = 4           # Hold 4 stocks (same as JQ g.stock_num)
N_DROP = 4           # Full rotation allowed
HOLD_THRESH = 5      # ~weekly holding (5 trading days ≈ 1 week)
ONLY_TRADABLE = False
FORBID_LIMIT = True

# --- Universe & benchmark ---
SUB_UNIVERSE = 'csi1000'        # CSI 1000 index constituents
BENCHMARK = '000852_SH'         # CSI 1000 index (000852.SH in Tushare → 000852_SH in Qlib)

# --- Capital ---
ACCOUNT = 100_000               # ¥100,000 (match JoinQuant)

# --- Exchange parameters ---
DEAL_PRICE = 'open'
# Main board ±10% limit
LIMIT_THRESH = ('Ge($pct_chg, 9.5)', 'Le($pct_chg, -9.5)')
# JoinQuant costs: open_commission=3.5/10000, close_commission=3.5/10000, close_tax=0.001
OPEN_COST = 0.00035             # Buy: 0.035% commission
CLOSE_COST = 0.00135            # Sell: 0.035% commission + 0.1% stamp tax
MIN_COST = 5                    # Minimum ¥5 per trade

# --- Filter thresholds (from JQ strategy) ---
MIN_MV_YI = 10        # 最小市值 10亿
MAX_MV_YI = 100       # 最大市值 100亿
MAX_PRICE = 50         # 股票单价上限
MIN_LISTING_DAYS = 375 # 次新股过滤 (上市天数)
MIN_REVENUE = 1e8      # 最小营业收入 1亿元

# Convert market cap from 亿 to Tushare's 万元 units
MIN_MV_WAN = MIN_MV_YI * 10000   # 10亿 = 100,000万
MAX_MV_WAN = MAX_MV_YI * 10000   # 100亿 = 1,000,000万

# --- Qlib paths ---
QLIB_DIR = os.path.join(PROJECT_ROOT, 'data', 'qlib_data')
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'config.yaml')


def load_stock_reference():
    """Load stock reference data for listing dates and ST/name detection.

    Returns:
        DataFrame with columns: ts_code (Qlib format), list_date, name
    """
    ref_path = os.path.join(PROJECT_ROOT, 'data', 'reference', 'stock_basic.parquet')
    ref = pd.read_parquet(ref_path, columns=['ts_code', 'list_date', 'name'])
    # Convert ts_code from Tushare format (000001.SZ) to Qlib format (000001_SZ)
    ref['qlib_code'] = ref['ts_code'].str.replace('.', '_', regex=False)
    ref['list_date'] = pd.to_datetime(ref['list_date'])
    return ref.set_index('qlib_code')


def build_signal():
    """Build the small-cap strategy signal following the 4-layer pipeline.

    Returns:
        pd.Series: Signal with MultiIndex(datetime, instrument), higher = more desirable.
    """
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D

    # Initialize Qlib
    try:
        qlib.init(provider_uri=QLIB_DIR, region=REG_CN)
    except Exception:
        pass  # Already initialized
    logger.info('Qlib initialized.')

    # Load stock reference data
    stock_ref = load_stock_reference()
    logger.info('Loaded stock reference: %d stocks', len(stock_ref))

    # ═══════════════════════════════════════════════════════════
    # LAYER 1: Factor Computation (full market)
    # Index: (instrument, datetime) MultiIndex
    # ═══════════════════════════════════════════════════════════
    logger.info('Layer 1: Loading factors for full market...')
    all_instruments = D.instruments(market='all')
    fields = [
        '$close',
        '$total_mv',           # 总市值 (万元)
        '$n_income',           # 净利润 (元)
        '$n_income_attr_p',    # 归属于母公司所有者的净利润 (元)
        '$total_revenue',      # 营业总收入 (元)
        '$vol',                # 成交量
        '$pct_chg',            # 涨跌幅 (%)
    ]
    df = D.features(all_instruments, fields, start_time=START_DATE, end_time=END_DATE)
    df.columns = ['close', 'total_mv', 'n_income', 'n_income_attr_p', 'total_revenue', 'vol', 'pct_chg']

    logger.info('Layer 1 complete: %d rows, %d unique stocks, %d dates',
                len(df), df.index.get_level_values(0).nunique(),
                df.index.get_level_values(1).nunique())

    # ═══════════════════════════════════════════════════════════
    # LAYER 2: Universe Selection (masks only, no row drops)
    # ═══════════════════════════════════════════════════════════
    logger.info('Layer 2: Building universe masks...')

    # 2a. CSI 1000 membership mask
    csi1000_members = D.features(
        D.instruments(market=SUB_UNIVERSE), ['$close'],
        start_time=START_DATE, end_time=END_DATE
    )
    is_csi1000 = df.index.isin(csi1000_members.index)
    logger.info('  CSI1000 membership: %d / %d rows', is_csi1000.sum(), len(df))

    # 2b. Main-board filter (exclude ChiNext 30x, STAR 68x, 北交所 8x/4x)
    instruments = df.index.get_level_values(0)
    # Extract numeric code prefix
    code_prefix = instruments.str[:2]
    is_mainboard = ~(
        code_prefix.isin(['30', '68']) |
        instruments.str.startswith('8') |
        instruments.str.startswith('4')
    )
    # Also exclude index codes (000001_SH, 000300_SH, etc.)
    is_stock = ~instruments.str.endswith('_SH') | instruments.str[:3].isin(['600', '601', '603', '605'])
    # Actually, let's just exclude known SH indices (000xxx_SH pattern where it's not 6xxxxx)
    is_sh_index = instruments.str.endswith('_SH') & ~instruments.str[:1].isin(['6'])
    is_mainboard = is_mainboard & ~is_sh_index
    logger.info('  Main-board filter: %d / %d rows pass', is_mainboard.sum(), len(df))

    # 2c. ST / delisted / name filter
    # Build set of ST/退市 codes (vectorized, not per-stock loop)
    st_codes = set()
    for code, row in stock_ref.iterrows():
        name = row['name']
        if isinstance(name, str) and ('ST' in name or '退' in name):
            st_codes.add(code)
    is_st_stock = instruments.isin(st_codes)
    not_st = ~is_st_stock
    logger.info('  ST/退市 filter: %d rows flagged as ST (%d unique stocks)',
                is_st_stock.sum(), len(st_codes))

    # 2d. Listing age filter (> 375 days)
    # Create a mapping: instrument -> list_date
    listing_dates = stock_ref['list_date'].to_dict()
    dates = df.index.get_level_values(1)
    # Build a pandas Series (not Index) for listing dates to enable proper timedelta ops
    list_date_arr = pd.array(instruments.map(listing_dates), dtype='datetime64[ns]')
    td = dates - list_date_arr
    # td is a TimedeltaIndex; use .days property directly (no .dt accessor needed)
    listing_age_days = td.days  # NaT → NaN
    is_seasoned = np.where(np.isnan(listing_age_days), False, listing_age_days > MIN_LISTING_DAYS)
    logger.info('  Listing age > %d days: %d / %d rows', MIN_LISTING_DAYS, is_seasoned.sum(), len(df))

    # 2e. Data completeness
    has_data = (
        df['total_mv'].notna() &
        df['n_income'].notna() &
        df['n_income_attr_p'].notna() &
        df['total_revenue'].notna() &
        df['close'].notna()
    )

    # 2f. Fundamental screening (JQ国九条 filters)
    passes_screen = (
        df['total_mv'].between(MIN_MV_WAN, MAX_MV_WAN) &  # 市值 10-100亿
        (df['n_income'] > 0) &                              # 净利润 > 0
        (df['n_income_attr_p'] > 0) &                       # 归属净利润 > 0
        (df['total_revenue'] > MIN_REVENUE) &               # 营业收入 > 1亿
        (df['close'] <= MAX_PRICE)                           # 股价 ≤ 50元
    )

    # Combine all masks
    is_eligible = is_csi1000 & is_mainboard & not_st & is_seasoned & has_data & passes_screen
    is_rankable = is_eligible  # No vol>0 filter (§1.2 Rule 3)

    eligible_per_date = is_eligible.groupby(level=1).sum()
    logger.info('Layer 2 complete: eligible per date — min=%d, max=%d, mean=%.1f',
                eligible_per_date.min(), eligible_per_date.max(), eligible_per_date.mean())

    # ═══════════════════════════════════════════════════════════
    # LAYER 3: Signal Construction
    # Rank by market cap ascending within eligible stocks
    # Smaller cap = higher signal = more desirable for TopkDropout
    # ═══════════════════════════════════════════════════════════
    logger.info('Layer 3: Constructing signal...')

    # Rank market cap: ascending=True means smallest gets rank 1
    # We want smallest cap to have HIGHEST signal value for TopkDropout
    # So use ascending=False in pct rank → largest pct rank = smallest cap
    df.loc[is_rankable, 'signal'] = (
        df[is_rankable].groupby(level=1)['total_mv']
        .rank(pct=True, ascending=False)  # Smallest cap → highest score
    )

    # Forward-fill signal for temporarily missing data within CSI1000 members
    df.loc[is_csi1000, 'signal'] = (
        df.loc[is_csi1000, 'signal'].groupby(level=0).ffill()
    )

    # Extract final signal for CSI1000 members
    final_signal = df.loc[is_csi1000, 'signal'].dropna()
    final_signal = final_signal.swaplevel().sort_index()  # → (datetime, instrument)

    # Validation
    total_eligible_pairs = is_eligible.sum()
    signal_pairs = final_signal.notna().sum()
    coverage = signal_pairs / total_eligible_pairs if total_eligible_pairs > 0 else 0
    logger.info('Layer 3 complete: signal coverage = %.1f%% (%d/%d pairs)',
                coverage * 100, signal_pairs, total_eligible_pairs)

    # Print sample signal stats
    dates_with_signal = final_signal.index.get_level_values(0).unique()
    logger.info('  Signal covers %d trading days', len(dates_with_signal))

    # Sample: show top stocks for a few dates
    for sample_date in dates_with_signal[::500][:5]:
        day_signal = final_signal.loc[sample_date].sort_values(ascending=False)
        top_stocks = day_signal.head(TOP_K)
        logger.info('  %s top-%d: %s', sample_date.strftime('%Y-%m-%d'),
                     TOP_K, list(zip(top_stocks.index, top_stocks.values.round(3))))

    return final_signal


def run_backtest(final_signal):
    """Run the backtest using VectorizedBacktester.

    Args:
        final_signal: Signal Series with MultiIndex(datetime, instrument).

    Returns:
        BacktestResult
    """
    from src.backtest_engine.vectorized import VectorizedBacktester

    bt = VectorizedBacktester(config_path=CONFIG_PATH, qlib_dir=QLIB_DIR)

    logger.info('Running backtest: %s to %s, topk=%d, hold_thresh=%d',
                START_DATE, END_DATE, TOP_K, HOLD_THRESH)

    result = bt.run(
        predictions=final_signal,
        start_time=START_DATE,
        end_time=END_DATE,
        strategy_type=STRATEGY_TYPE,
        topk=TOP_K,
        n_drop=N_DROP,
        hold_thresh=HOLD_THRESH,
        only_tradable=ONLY_TRADABLE,
        forbid_all_trade_at_limit=FORBID_LIMIT,
        benchmark=BENCHMARK,
        account=ACCOUNT,
        exchange_kwargs={
            'freq': 'day',
            'deal_price': DEAL_PRICE,
            'limit_threshold': LIMIT_THRESH,
            'open_cost': OPEN_COST,
            'close_cost': CLOSE_COST,
            'min_cost': MIN_COST,
        },
    )

    return result


def print_results(result):
    """Print comprehensive backtest results and compare to JQ reference."""
    logger.info('=' * 70)
    logger.info('BACKTEST RESULTS')
    logger.info('=' * 70)

    # Summary metrics
    summary = result.summary
    for key, val in summary.items():
        if isinstance(val, float):
            logger.info('  %-30s: %.4f', key, val)
        else:
            logger.info('  %-30s: %s', key, val)

    # Detailed analysis via BacktestReport
    try:
        from src.result_analysis.report import BacktestReport
        report = BacktestReport(result.report, benchmark_col='bench')
        rpt = report.summary()
        logger.info('\n--- BacktestReport Summary ---')
        for key, val in rpt.items():
            if isinstance(val, float):
                logger.info('  %-30s: %.4f', key, val)
            else:
                logger.info('  %-30s: %s', key, val)
    except Exception as e:
        logger.warning('BacktestReport failed: %s', e)

    # Year-by-year returns
    if result.report is not None and not result.report.empty:
        net_returns = result.report['return'] - result.report['cost']
        equity = (1 + net_returns).cumprod()

        logger.info('\n--- Year-by-Year Returns ---')
        yearly = net_returns.groupby(net_returns.index.year)
        for year, returns in yearly:
            ann_ret = (1 + returns).prod() - 1
            logger.info('  %d: %.2f%%', year, ann_ret * 100)

        # Final cumulative return
        total_return = equity.iloc[-1] - 1
        logger.info('\n  Total cumulative return: %.2f%%', total_return * 100)

        # Max drawdown
        drawdown = equity / equity.cummax() - 1
        max_dd = drawdown.min()
        logger.info('  Max drawdown: %.2f%%', max_dd * 100)

    # Comparison to JoinQuant reference
    logger.info('\n--- Comparison to JoinQuant Reference ---')
    logger.info('  JQ 策略收益: 63216.87%%   | ours: %.2f%%', total_return * 100 if 'total_return' in dir() else 0)
    logger.info('  JQ 年化收益: 78.81%%')
    logger.info('  JQ 夏普比率: 2.320')
    logger.info('  JQ 最大回撤: 31.66%%      | ours: %.2f%%', abs(max_dd * 100) if 'max_dd' in dir() else 0)
    logger.info('  JQ 胜率: 0.656')
    logger.info('  NOTE: Differences expected due to missing stop-loss/take-profit logic')


if __name__ == '__main__':
    logger.info('=' * 70)
    logger.info('JoinQuant Small-Cap Strategy — Local Recreation')
    logger.info('=' * 70)

    # Step 1: Build signal
    final_signal = build_signal()

    # Step 2: Run backtest
    result = run_backtest(final_signal)

    # Step 3: Print results
    print_results(result)

    logger.info('Done.')
