"""
Generate Small-Cap Strategy Jupyter Notebook

Creates a simple strategy notebook that:
  - Filters universe: market cap 1–10B, single-quarter net profit > 0, excl. STAR board
  - Buys the 5 stocks with the lowest total market cap
  - Equal-weights each position (20% each)
  - Rebalances every 5 trading days
  - Backtests from 2010-01-01 to 2025-12-31 via VectorizedBacktester

Usage:
    python workspace/scripts/generate_smallcap_notebook.py

Output:
    workspace/research/alpha_factors/smallcap_strategy.ipynb
"""

import os
import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "workspace", "research", "alpha_factors")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "smallcap_strategy.ipynb")


def make_notebook():
    """Build the small-cap strategy notebook."""
    nb = new_notebook()
    nb.metadata.kernelspec = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    cells = []

    # ═══════════════════════════════════════════════════════════════
    # TITLE
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "# Small-Cap Strategy: Buy Lowest Market Cap\n\n"
        "A simple rules-based strategy:\n"
        "- **Universe filter**: Market cap 1–10B CNY, single-quarter net profit > 0, excl. 科创板\n"
        "- **Signal**: Total market cap (lowest = best)\n"
        "- **Portfolio**: Hold 5 stocks, equal-weighted (20% each)\n"
        "- **Rebalance**: Every 5 trading days\n"
        "- **Backtest**: 2010-01-01 → 2025-12-31\n"
        "- **Engine**: Qlib `VectorizedBacktester` (TopkDropout, A-share costs)\n\n"
        "---"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §1: ENVIRONMENT
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell("## 1. Environment & Data Loading"))

    cells.append(new_code_cell(
        "import sys\n"
        "import os\n"
        "import warnings\n"
        "warnings.filterwarnings('ignore')\n\n"
        "PROJECT_ROOT = r'e:\\量化系统'\n"
        "sys.path.insert(0, PROJECT_ROOT)\n\n"
        "import numpy as np\n"
        "import pandas as pd\n"
        "import matplotlib.pyplot as plt\n"
        "import matplotlib.dates as mdates\n\n"
        "# Qlib initialization\n"
        "import qlib\n"
        "from qlib.data import D\n"
        "from qlib.config import REG_CN\n\n"
        "QLIB_DIR = os.path.join(PROJECT_ROOT, 'data', 'qlib_data')\n"
        "qlib.init(provider_uri=QLIB_DIR, region=REG_CN)\n"
        "print('Qlib initialized')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §2: PARAMETERS & DATA
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell("## 2. Parameters & Data Loading"))

    cells.append(new_code_cell(
        "# ─── Strategy Parameters ─────────────────────────────────\n"
        "START_DATE = '2010-01-01'\n"
        "END_DATE   = '2025-12-31'\n"
        "TOP_K      = 5          # Number of stocks to hold\n"
        "REBAL_DAYS = 5          # Rebalance every N trading days\n\n"
        "# Universe filters\n"
        "# total_mv is in 万元 (10k CNY): 1B CNY = 100,000 万元, 10B CNY = 1,000,000 万元\n"
        "MV_MIN = 100_000        # 1 billion CNY (10亿)\n"
        "MV_MAX = 1_000_000      # 10 billion CNY (100亿)\n\n"
        "# Transaction costs (A-share)\n"
        "BUY_COST  = 0.0005      # 0.05% commission\n"
        "SELL_COST = 0.0015      # 0.15% commission + stamp tax\n\n"
        "# ─── Load from Qlib ──────────────────────────────────────\n"
        "instruments = D.instruments(market='all_stocks')\n\n"
        "fields = [\n"
        "    '$close',           # Close price\n"
        "    '$total_mv',        # Total market cap (万元)\n"
        "    '$n_income_attr_p', # Net profit attrib. to parent (PIT-aligned)\n"
        "    '$adj_factor',      # Adjustment factor\n"
        "    '$vol',             # Volume\n"
        "]\n\n"
        "print('Loading market data...')\n"
        "df = D.features(instruments, fields, start_time=START_DATE, end_time=END_DATE)\n"
        "df.columns = ['close', 'total_mv', 'net_profit', 'adj_factor', 'vol']\n\n"
        "# Qlib returns MultiIndex(instrument, datetime)\n"
        "print(f'Raw data shape: {df.shape}')\n"
        "print(f'Date range: {df.index.get_level_values(1).min()} – '\n"
        "      f'{df.index.get_level_values(1).max()}')\n"
        "print(f'Stocks: {df.index.get_level_values(0).nunique()}')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §3: UNIVERSE FILTERING
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 3. Universe Filtering\n\n"
        "Apply the following filters each day:\n"
        "1. **Exclude 科创板**: Remove 688xxx stocks (STAR Market, ±20% limits)\n"
        "2. **Market cap**: 1B ≤ total_mv ≤ 10B CNY\n"
        "3. **Single-quarter net profit**: > 0 (latest quarter profitable)\n"
        "4. **Tradable**: Volume > 0 (not suspended)"
    ))

    cells.append(new_code_cell(
        "# ─── Compute single-quarter net profit ────────────────────\n"
        "# n_income_attr_p is cumulative YTD (PIT-aligned, forward-filled).\n"
        "# To derive single-quarter profit:\n"
        "#   1. Detect 'change points' where the value changes (new report announced)\n"
        "#   2. At each change point, if value dropped significantly → Q1 report\n"
        "#      (new fiscal year), so single_q = new value itself\n"
        "#   3. Otherwise, single_q = new_value - old_value\n"
        "#   4. Forward-fill until next change point\n\n"
        "cumulative_np = df['net_profit'].copy()\n\n"
        "# Previous value (per stock) — detects when cumulative value changes\n"
        "prev_val = cumulative_np.groupby(level=0).shift(1)\n"
        "changed = (cumulative_np != prev_val) & prev_val.notna()\n\n"
        "# Compute raw diff\n"
        "raw_diff = cumulative_np - prev_val\n\n"
        "# Detect Q1 reports: cumulative dropped significantly (new fiscal year)\n"
        "# Q1 cumulative << previous Q3/Q4 cumulative → diff is very negative\n"
        "# Heuristic: if new value < old value * 0.5, it's likely Q1\n"
        "is_q1 = changed & (cumulative_np < prev_val * 0.5)\n\n"
        "# Single-quarter profit at change points\n"
        "single_q = pd.Series(np.nan, index=cumulative_np.index)\n"
        "single_q[changed & ~is_q1] = raw_diff[changed & ~is_q1]  # Normal: diff\n"
        "single_q[is_q1] = cumulative_np[is_q1]                   # Q1: use value directly\n\n"
        "# Forward-fill within each stock\n"
        "df['single_q_profit'] = single_q.groupby(level=0).ffill()\n\n"
        "print('Single-quarter net profit computed')\n"
        "print(f'  Change points detected: {changed.sum():,}')\n"
        "print(f'  Q1 reports detected: {is_q1.sum():,}')\n"
        "print(f'  Coverage: {df[\"single_q_profit\"].notna().mean():.1%}')"
    ))

    cells.append(new_code_cell(
        "# ─── Apply universe filters ──────────────────────────────\n"
        "print('Before filtering:', df.shape)\n\n"
        "# Drop rows missing key fields\n"
        "df = df.dropna(subset=['total_mv', 'close', 'adj_factor'])\n"
        "print(f'After dropping NaN: {df.shape}')\n\n"
        "# Filter: exclude 科创板 (STAR Market, 688xxx)\n"
        "star_mask = df.index.get_level_values(0).str.startswith('688')\n"
        "df_no_star = df[~star_mask].copy()\n"
        "print(f'Excl. 科创板 (688xxx): {df_no_star.shape}')\n\n"
        "# Filter: tradable (volume > 0)\n"
        "df_tradable = df_no_star[df_no_star['vol'] > 0].copy()\n"
        "print(f'Tradable (vol > 0): {df_tradable.shape}')\n\n"
        "# Filter: market cap between 1B and 10B\n"
        "mv_mask = (df_tradable['total_mv'] >= MV_MIN) & (df_tradable['total_mv'] <= MV_MAX)\n"
        "df_filtered = df_tradable[mv_mask].copy()\n"
        "print(f'Market cap 1-10B: {df_filtered.shape}')\n\n"
        "# Filter: single-quarter net profit > 0\n"
        "profit_mask = df_filtered['single_q_profit'] > 0\n"
        "df_filtered = df_filtered[profit_mask].copy()\n"
        "print(f'Single-Q net profit > 0: {df_filtered.shape}')\n\n"
        "# Summary\n"
        "print(f'\\nFiltered universe stats:')\n"
        "print(f'  Date range: {df_filtered.index.get_level_values(1).min()} – '\n"
        "      f'{df_filtered.index.get_level_values(1).max()}')\n"
        "print(f'  Unique stocks: {df_filtered.index.get_level_values(0).nunique()}')\n\n"
        "# Stocks per day\n"
        "stocks_per_day = df_filtered.groupby(level=1).size()\n"
        "print(f'  Stocks per day: min={stocks_per_day.min()}, '\n"
        "      f'median={stocks_per_day.median():.0f}, max={stocks_per_day.max()}')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §4: MANUAL BACKTEST (Simple Replace-All)
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 4. Backtest: Simple Replace-All (with Limit Handling)\n\n"
        "On every rebalance day:\n"
        "1. Rank all eligible stocks by `total_mv` (ascending)\n"
        "2. **Sell everything** currently held (except limit-down stocks — can't sell)\n"
        "3. **Buy bottom 5** that are NOT at limit-up; skip to next candidate if limit-up\n"
        "4. Hold for 5 trading days, then repeat\n\n"
        "Limit detection: daily return ≥ 9.5% → limit-up (can't buy), ≤ -9.5% → limit-down (can't sell).\n\n"
        "Transaction costs: buy 0.05%, sell 0.15% (applied on turnover fraction)."
    ))

    cells.append(new_code_cell(
        "# ─── Prepare adjusted returns ────────────────────────────\n"
        "# Need returns for ALL stocks (not just filtered), since we hold stocks\n"
        "# between rebalances even if they temporarily leave the universe\n"
        "df['adj_close'] = df['close'] * df['adj_factor']\n"
        "df['daily_ret'] = df.groupby(level=0)['adj_close'].pct_change()\n\n"
        "# ─── Detect limit-up / limit-down ────────────────────────\n"
        "# A-shares: ±10% for main board, ±20% for 创业板/科创板\n"
        "# We already excluded 科创板. Use 9.5% threshold (conservative).\n"
        "LIMIT_THRESHOLD = 0.095\n"
        "df['is_limit_up'] = df['daily_ret'] >= LIMIT_THRESHOLD\n"
        "df['is_limit_down'] = df['daily_ret'] <= -LIMIT_THRESHOLD\n\n"
        "limit_up_count = df['is_limit_up'].sum()\n"
        "limit_down_count = df['is_limit_down'].sum()\n"
        "print(f'Limit-up days detected: {limit_up_count:,}')\n"
        "print(f'Limit-down days detected: {limit_down_count:,}')\n\n"
        "# ─── Trading calendar ────────────────────────────────────\n"
        "all_dates = df_filtered.index.get_level_values(1).unique().sort_values()\n"
        "print(f'Trading days: {len(all_dates)}')\n\n"
        "# Rebalance dates: every REBAL_DAYS trading days\n"
        "rebal_dates_list = all_dates[::REBAL_DAYS].tolist()\n"
        "rebal_dates_set = set(rebal_dates_list)\n"
        "print(f'Rebalance dates: {len(rebal_dates_list)}')\n\n"
        "# ─── Select stocks on each rebalance date ───────────────\n"
        "# Rank by total_mv ascending. On each rebalance:\n"
        "# - Skip stocks that are limit-up today (can't buy)\n"
        "# - Fall through to next-ranked candidate\n"
        "# - Keep \"BACKUP_DEPTH\" candidates to ensure enough non-limit stocks\n"
        "BACKUP_DEPTH = 20  # look at top-20 to find 5 buyable stocks\n\n"
        "holdings = {}       # {date: [list of stock codes actually bought]}\n"
        "limit_skips = 0     # count how many times we had to skip a stock\n\n"
        "for dt in rebal_dates_list:\n"
        "    mask = df_filtered.index.get_level_values(1) == dt\n"
        "    cs = df_filtered.loc[mask, 'total_mv'].droplevel(1).dropna()\n"
        "    if len(cs) < TOP_K:\n"
        "        continue\n\n"
        "    # Rank candidates by market cap (ascending = smallest first)\n"
        "    candidates = cs.nsmallest(min(BACKUP_DEPTH, len(cs)))\n\n"
        "    # Filter out limit-up stocks (can't buy at close)\n"
        "    selected = []\n"
        "    for stk in candidates.index:\n"
        "        try:\n"
        "            if df.loc[(stk, dt), 'is_limit_up']:\n"
        "                limit_skips += 1\n"
        "                continue  # Skip: stock is at limit-up\n"
        "        except KeyError:\n"
        "            continue\n"
        "        selected.append(stk)\n"
        "        if len(selected) >= TOP_K:\n"
        "            break\n\n"
        "    if selected:\n"
        "        holdings[dt] = selected\n\n"
        "print(f'Rebalance events with valid holdings: {len(holdings)}')\n"
        "print(f'Total limit-up skips: {limit_skips:,}')\n"
        "for i, (dt, stocks) in enumerate(list(holdings.items())[:3]):\n"
        "    print(f'  {dt.strftime(\"%Y-%m-%d\")}: {stocks}')"
    ))

    cells.append(new_code_cell(
        "%%time\n"
        "# ─── Simulate portfolio returns (with limit handling) ─────\n"
        "# Rules:\n"
        "#   - On rebalance: sell current holdings (skip limit-down, carry over)\n"
        "#   - Buy new selections (already filtered for limit-up above)\n"
        "#   - Equal-weight the actually-held stocks\n"
        "portfolio_returns = []\n"
        "current_stocks = []\n"
        "prev_stocks = []\n"
        "limit_down_holds = 0  # count stocks forced to hold due to limit-down\n\n"
        "for dt in all_dates:\n"
        "    # Check if rebalance day\n"
        "    if dt in holdings:\n"
        "        new_targets = holdings[dt]\n"
        "        prev_stocks = current_stocks.copy()\n\n"
        "        # Check which current holdings are at limit-down (can't sell)\n"
        "        forced_holds = []\n"
        "        for stk in current_stocks:\n"
        "            try:\n"
        "                if df.loc[(stk, dt), 'is_limit_down']:\n"
        "                    forced_holds.append(stk)\n"
        "                    limit_down_holds += 1\n"
        "            except KeyError:\n"
        "                pass\n\n"
        "        # New portfolio = forced holds + new targets (dedup, cap at TOP_K)\n"
        "        current_stocks = list(dict.fromkeys(\n"
        "            forced_holds + [s for s in new_targets if s not in forced_holds]\n"
        "        ))[:TOP_K + len(forced_holds)]  # may exceed TOP_K slightly\n\n"
        "    if not current_stocks:\n"
        "        continue\n\n"
        "    # Get daily returns for held stocks\n"
        "    day_rets = []\n"
        "    for stk in current_stocks:\n"
        "        try:\n"
        "            ret = df.loc[(stk, dt), 'daily_ret']\n"
        "            if np.isfinite(ret):\n"
        "                day_rets.append(ret)\n"
        "        except KeyError:\n"
        "            pass  # stock not traded this day (suspended)\n\n"
        "    if not day_rets:\n"
        "        portfolio_returns.append({'date': dt, 'ret_gross': 0.0, 'cost': 0.0})\n"
        "        continue\n\n"
        "    # Equal-weighted return (gross)\n"
        "    ret_gross = np.mean(day_rets)\n\n"
        "    # Transaction cost on rebalance day\n"
        "    cost = 0.0\n"
        "    if dt in holdings:\n"
        "        if prev_stocks:\n"
        "            sold = set(prev_stocks) - set(current_stocks)\n"
        "            bought = set(current_stocks) - set(prev_stocks)\n"
        "            # Turnover: fraction of portfolio that changed\n"
        "            n_pos = max(len(current_stocks), len(prev_stocks), 1)\n"
        "            turnover = (len(sold) + len(bought)) / (2 * n_pos)\n"
        "            cost = turnover * (BUY_COST + SELL_COST)\n"
        "        else:\n"
        "            # First buy: full portfolio cost\n"
        "            cost = BUY_COST\n\n"
        "    portfolio_returns.append({\n"
        "        'date': dt,\n"
        "        'ret_gross': ret_gross,\n"
        "        'cost': cost,\n"
        "    })\n\n"
        "port_df = pd.DataFrame(portfolio_returns).set_index('date')\n"
        "port_df['ret_net'] = port_df['ret_gross'] - port_df['cost']\n\n"
        "print(f'Portfolio return series: {len(port_df)} days')\n"
        "print(f'Date range: {port_df.index.min()} – {port_df.index.max()}')\n"
        "print(f'Total rebalance cost: {port_df[\"cost\"].sum():.4%}')\n"
        "print(f'Limit-down forced holds: {limit_down_holds:,}')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §5: LOAD CSI300 BENCHMARK
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell("## 5. Load CSI 300 Benchmark"))

    cells.append(new_code_cell(
        "# Load CSI 300 from Qlib\n"
        "import glob\n\n"
        "# Try Qlib features first\n"
        "bench_raw = D.features(['000300_SH'], ['$close'], start_time=START_DATE, end_time=END_DATE)\n\n"
        "if not bench_raw.empty:\n"
        "    bench_close = bench_raw.droplevel(0)['$close']\n"
        "    bench_daily_ret = bench_close.pct_change().dropna()\n"
        "    print(f'CSI300 from Qlib: {len(bench_daily_ret)} days')\n"
        "else:\n"
        "    # Fallback: load from index parquet files\n"
        "    index_path = os.path.join(PROJECT_ROOT, 'data', 'market', 'index_daily')\n"
        "    if os.path.exists(index_path):\n"
        "        idx_files = sorted(glob.glob(os.path.join(index_path, '*.parquet')))\n"
        "        idx_all = pd.concat([pd.read_parquet(f) for f in idx_files], ignore_index=True)\n"
        "        csi300 = idx_all[idx_all['ts_code'] == '000300.SH'].copy()\n"
        "        csi300['trade_date'] = pd.to_datetime(csi300['trade_date'], format='%Y%m%d')\n"
        "        csi300 = csi300.set_index('trade_date').sort_index()\n"
        "        bench_daily_ret = csi300['pct_chg'] / 100\n"
        "        print(f'CSI300 from parquet: {len(bench_daily_ret)} days')\n"
        "    else:\n"
        "        bench_daily_ret = None\n"
        "        print('No CSI300 benchmark data found')\n\n"
        "# Align dates\n"
        "net_ret = port_df['ret_net']\n"
        "if bench_daily_ret is not None:\n"
        "    common_dates = port_df.index.intersection(bench_daily_ret.index)\n"
        "    bench_ret = bench_daily_ret.loc[common_dates]\n"
        "    net_ret_aligned = net_ret.loc[common_dates]\n"
        "    print(f'Aligned trading days: {len(common_dates)}')\n"
        "else:\n"
        "    bench_ret = pd.Series(0.0, index=net_ret.index)\n"
        "    net_ret_aligned = net_ret\n"
        "    common_dates = net_ret.index"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §6: BACKTEST REPORT
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 6. Performance Report\n\n"
        "Using `BacktestReport` for standardized analysis with interactive Plotly charts."
    ))

    cells.append(new_code_cell(
        "from src.result_analysis import BacktestReport\n\n"
        "report = BacktestReport(\n"
        "    net_ret_aligned, bench_ret,\n"
        "    name='Small-Cap 1-10B (Simple Replace-All)',\n"
        "    risk_free_rate=0.02,\n"
        ")\n"
        "report.summary()"
    ))

    cells.append(new_code_cell(
        "# ─── 果仁-Style Trading Analysis ─────────────────────────\n"
        "report.trading_analysis(\n"
        "    holdings=holdings,\n"
        "    df=df,\n"
        "    buy_cost=BUY_COST,\n"
        "    sell_cost=SELL_COST,\n"
        ")"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §7: INTERACTIVE DASHBOARD
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 7. Equity Curve & Drawdown\n\n"
        "Interactive dashboard — hover for values, drag to zoom."
    ))

    cells.append(new_code_cell("report.plot()"))

    # ═══════════════════════════════════════════════════════════════
    # §8: YEARLY RETURNS
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell("## 8. Yearly Returns Breakdown"))

    cells.append(new_code_cell("report.yearly()"))

    # ═══════════════════════════════════════════════════════════════
    # §8b: MONTHLY HEATMAP
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 8b. Monthly Returns Heatmap\n\n"
        "Year × Month return calendar. Green = positive, red = negative."
    ))

    cells.append(new_code_cell("report.monthly_heatmap()"))

    # ═══════════════════════════════════════════════════════════════
    # §8c: ROLLING METRICS
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 8c. Rolling Metrics (1-Year Window)\n\n"
        "Rolling Sharpe, volatility, and compounded return."
    ))

    cells.append(new_code_cell("report.rolling(window=252)"))

    # ═══════════════════════════════════════════════════════════════
    # §8d: RETURN DISTRIBUTION
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell("## 8d. Daily Return Distribution"))

    cells.append(new_code_cell("report.distribution()"))

    # ═══════════════════════════════════════════════════════════════
    # §8e: QLIB BACKTEST (Model II / TopkDropout)
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "---\n\n"
        "## 8e. Qlib Backtest (Model II — TopkDropout)\n\n"
        "For comparison with the manual replace-all above, run the same strategy\n"
        "through Qlib's `VectorizedBacktester` with `TopkDropout`.\n\n"
        "**Key difference**: TopkDropout only sells stocks that *drop out* of the top-K,\n"
        "rather than replacing the entire portfolio. This matches 果仁's Model II.\n\n"
        "Signal = `-total_mv` (lower cap = higher score), forward-filled between\n"
        "rebalance dates so Qlib doesn't trade between rebalances."
    ))

    cells.append(new_code_cell(
        "# ─── Build signal for Qlib (rebalance dates only) ────────\n"
        "# Signal only exists on rebalance dates (every REBAL_DAYS days).\n"
        "# Between rebalances: Qlib gets None → no trades → positions held.\n"
        "# On rebalance: fresh scores from current universe → clean ranking.\n"
        "# This eliminates ghost holdings from stale forward-filled scores.\n"
        "#\n"
        "# Signal = -total_mv (lower cap = higher score = better rank)\n\n"
        "signal_parts = []\n"
        "for dt in rebal_dates_list:\n"
        "    mask = df_filtered.index.get_level_values(1) == dt\n"
        "    cs = df_filtered.loc[mask, 'total_mv'].droplevel(1).dropna()\n"
        "    if cs.empty:\n"
        "        continue\n"
        "    scores = -cs  # lower cap = higher (less negative) score\n"
        "    scores_df = scores.to_frame('score')\n"
        "    scores_df['datetime'] = dt\n"
        "    scores_df.index.name = 'instrument'\n"
        "    signal_parts.append(scores_df.reset_index())\n\n"
        "# NO forward-fill — signal only exists on rebalance dates\n"
        "signal_df = pd.concat(signal_parts, ignore_index=True)\n"
        "signal_df = signal_df.set_index(['datetime', 'instrument']).sort_index()\n"
        "signal_series = signal_df['score']\n\n"
        "print(f'Signal entries: {len(signal_series):,}')\n"
        "print(f'Rebalance dates with signal: '\n"
        "      f'{signal_series.index.get_level_values(0).nunique()}')\n"
        "print(f'Date range: {signal_series.index.get_level_values(0).min()} – '\n"
        "      f'{signal_series.index.get_level_values(0).max()}')\n"
        "print(f'Stocks per rebalance (median): '\n"
        "      f'{signal_series.groupby(level=0).count().median():.0f}')"
    ))

    cells.append(new_code_cell(
        "%%time\n"
        "from src.backtest_engine.vectorized import VectorizedBacktester, _DEFAULT_EXCHANGE_KWARGS\n\n"
        "# Diagnostic: confirm correct limit_threshold\n"
        "print(f'limit_threshold: {_DEFAULT_EXCHANGE_KWARGS[\"limit_threshold\"]}')\n\n"
        "bt = VectorizedBacktester(\n"
        "    config_path=os.path.join(PROJECT_ROOT, 'config.yaml'),\n"
        "    qlib_dir=QLIB_DIR,\n"
        ")\n\n"
        "qlib_result = bt.run(\n"
        "    predictions=signal_series,\n"
        "    start_time=START_DATE,\n"
        "    end_time=END_DATE,\n"
        "    topk=TOP_K,\n"
        "    n_drop=TOP_K,\n"
        "    hold_thresh=1,                # rebalance spacing handled by signal gaps\n"
        "    benchmark='000300_SH',\n"
        ")\n\n"
        "print('Qlib backtest complete')"
    ))

    # Diagnostic cell to investigate flat line
    cells.append(new_code_cell(
        "# ─── Diagnostic: Qlib positions & returns ────────────────\n"
        "rpt = qlib_result.report\n"
        "print('Report columns:', rpt.columns.tolist())\n"
        "print(f'Report shape: {rpt.shape}')\n"
        "print(f'Date range: {rpt.index.min()} to {rpt.index.max()}')\n\n"
        "# Find when returns go near-zero\n"
        "yearly_avg = rpt.groupby(rpt.index.year).agg({\n"
        "    'return': 'mean',\n"
        "    'cost': 'mean',\n"
        "    'bench': 'mean',\n"
        "    'turnover': 'mean' if 'turnover' in rpt.columns else 'count',\n"
        "})\n"
        "print('\\nYearly average daily metrics:')\n"
        "display(yearly_avg)\n\n"
        "# Check positions\n"
        "if qlib_result.positions is not None:\n"
        "    pos = qlib_result.positions\n"
        "    # positions is a dict {date: Position}\n"
        "    pos_dates = sorted(pos.keys())\n"
        "    print(f'\\nPositions tracked: {len(pos_dates)} dates')\n"
        "    print(f'First: {pos_dates[0]}, Last: {pos_dates[-1]}')\n\n"
        "    # Check a few dates\n"
        "    for check_year in [2015, 2020, 2023, 2024, 2025]:\n"
        "        year_dates = [d for d in pos_dates if d.year == check_year]\n"
        "        if year_dates:\n"
        "            mid = year_dates[len(year_dates)//2]\n"
        "            p = pos[mid]\n"
        "            if hasattr(p, 'get_stock_list'):\n"
        "                stocks = p.get_stock_list()\n"
        "                cash_pct = p.get_cash() / p.calculate_value() if p.calculate_value() > 0 else 1.0\n"
        "                print(f'  {mid.date()}: {len(stocks)} stocks, cash={cash_pct:.1%}')\n"
        "            elif isinstance(p, dict):\n"
        "                stock_count = len([k for k in p if k != 'cash'])\n"
        "                total = sum(v for v in p.values())\n"
        "                cash_pct = p.get('cash', 0) / total if total > 0 else 1.0\n"
        "                print(f'  {mid.date()}: {stock_count} stocks, cash={cash_pct:.1%}')\n"
        "else:\n"
        "    print('No positions data available')"
    ))

    cells.append(new_code_cell(
        "# Extract Qlib returns and build report\n"
        "qlib_report = qlib_result.report\n"
        "qlib_net_ret = qlib_report['return'] - qlib_report['cost']\n"
        "qlib_bench_ret = qlib_report['bench']\n\n"
        "report_qlib = BacktestReport(\n"
        "    qlib_net_ret, qlib_bench_ret,\n"
        "    name='Small-Cap 1-10B (Qlib TopkDropout)',\n"
        "    risk_free_rate=0.02,\n"
        ")\n"
        "report_qlib.summary()"
    ))

    cells.append(new_code_cell(
        "# ─── 果仁-Style Trading Analysis (Qlib) ─────────────────\n"
        "# Build holdings dict from Qlib positions for trading stats\n"
        "qlib_holdings = {}\n"
        "if qlib_result.positions is not None:\n"
        "    for dt, pos in qlib_result.positions.items():\n"
        "        if hasattr(pos, 'get_stock_list'):\n"
        "            stocks = pos.get_stock_list()\n"
        "        elif isinstance(pos, dict):\n"
        "            stocks = [k for k in pos if k != 'cash']\n"
        "        else:\n"
        "            stocks = []\n"
        "        if stocks:\n"
        "            qlib_holdings[dt] = stocks\n\n"
        "if qlib_holdings:\n"
        "    report_qlib.trading_analysis(\n"
        "        holdings=qlib_holdings,\n"
        "        df=df,\n"
        "        report_df=qlib_result.report,\n"
        "        buy_cost=BUY_COST,\n"
        "        sell_cost=SELL_COST,\n"
        "    )\n"
        "else:\n"
        "    print('No Qlib positions available for trading analysis')"
    ))

    cells.append(new_code_cell("report_qlib.plot()"))

    cells.append(new_code_cell("report_qlib.yearly()"))

    # ═══════════════════════════════════════════════════════════════
    # §9: UNIVERSE STATS
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell("## 9. Universe & Holdings Analysis"))

    cells.append(new_code_cell(
        "# Universe size over time\n"
        "fig, ax = plt.subplots(figsize=(14, 4))\n"
        "stocks_per_day.plot(ax=ax, color='#7E57C2', linewidth=0.8)\n"
        "ax.set_ylabel('Eligible Stocks')\n"
        "ax.set_title('Filtered Universe Size Over Time (1-10B, NP>0, Tradable)',\n"
        "             fontweight='bold')\n"
        "ax.grid(alpha=0.3)\n"
        "plt.tight_layout()\n"
        "plt.show()\n\n"
        "# Market cap distribution of held stocks\n"
        "print('\\nMarket cap of held stocks (from Qlib positions):')\n"
        "print(f'  Universe filter: {MV_MIN:,} – {MV_MAX:,} 万元')\n"
        "print(f'  = {MV_MIN/10000:.0f}亿 – {MV_MAX/10000:.0f}亿 CNY')\n"
        "print(f'  = {MV_MIN*10000/1e9:.1f}B – {MV_MAX*10000/1e9:.1f}B CNY')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## Summary\n\n"
        "| Parameter | Value |\n"
        "|-----------|-------|\n"
        "| Signal | Lowest total market cap |\n"
        "| Universe filter | Market cap 1–10B, single-Q net profit > 0, excl. 科创板 |\n"
        "| Stocks held | 5 |\n"
        "| Weighting | Equal (20% each) |\n"
        "| Rebalance frequency | Every 5 trading days |\n"
        "| Transaction costs | Buy 0.05% + Sell 0.15% (A-share) |\n"
        "| Backtest period | 2010-01-01 → 2025-12-31 |\n"
        "| Engine | Manual replace-all (matches 果仁 Model I) |\n\n"
        "### Caveats\n"
        "- **Survivorship bias**: Mitigated by `all_stocks` universe (includes delisted)\n"
        "- **Market impact**: Not modeled — small-cap stocks have wider spreads\n"
        "- **Limit-up/down**: Qlib enforces 9.5% limit threshold\n"
        "- **Net profit filter**: PIT-aligned, single-quarter derived from cumulative YTD\n"
        "- **Q1 detection**: Heuristic (new value < 50% of previous) — may misclassify edge cases\n\n"
        "---\n"
        "*Generated by `workspace/scripts/generate_smallcap_notebook.py`*"
    ))

    nb.cells = cells
    return nb


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    nb = make_notebook()
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)
    print(f"Notebook generated: {OUTPUT_PATH}")
    print(f"  Cells: {len(nb.cells)}")
    print(f"  Code cells: {sum(1 for c in nb.cells if c.cell_type == 'code')}")
    print(f"  Markdown cells: {sum(1 for c in nb.cells if c.cell_type == 'markdown')}")
