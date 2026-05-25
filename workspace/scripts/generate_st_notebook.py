"""
Generate ST Strategy Jupyter Notebook (v3 — Native Quarterly Features)

Replicates a 果仁-style strategy that:
  - Trades only ST stocks (universe from namechange PIT data)
  - Filters by 250-day return (0%–75% percentile, ranked across ALL stocks)
  - Ranks by total_mv + revenue_q + core_profit_q (descending, equal weight)
  - Holds 5 stocks, daily rebalance, TopkDropout (Model II)
  - Backtests from 2014-01-01 to 2025-12-31 via VectorizedBacktester

Key v2 fix: 250d return is computed from ALL stocks' full price history,
then the percentile filter is applied across all stocks before intersecting
with the ST universe. This matches 果仁's actual logic.

Usage:
    python workspace/scripts/generate_st_notebook.py

Output:
    workspace/research/alpha_factors/st_strategy.ipynb
"""

import os
import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "workspace", "research", "alpha_factors")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "st_strategy.ipynb")


def make_notebook():
    """Build the ST strategy notebook."""
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
        "# ST Strategy: 果仁 Replication (v3)\n\n"
        "**Rules-based strategy trading only ST (Special Treatment) stocks.**\n\n"
        "| Parameter | Value |\n"
        "|-----------|-------|\n"
        "| Universe | ST stocks only (from `namechange` PIT data) |\n"
        "| Screening | 250d return within 0%–75% percentile (ranked vs ALL stocks) |\n"
        "| Ranking factors | 总市值↓, 营业收入(单季)↓, CoreProfitQ↓ |\n"
        "| # Stocks | 6 (equal-weight ≈ 16.7% each) |\n"
        "| Rebalance | Daily |\n"
        "| Sell rule | Rank ≥ 7 (TopkDropout, n_drop=1) |\n"
        "| Deal price | Open (proxy for 09:35) |\n"
        "| Limit handling | Skip limit-up (buy), skip limit-down (sell) |\n"
        "| Market timing | None |\n\n"
        "> **v3**: Single-quarter fundamentals (`$revenue_q`, `$core_profit_q`) now\n"
        "> loaded directly from Tushare's native single-quarter data (report_type=2,3),\n"
        "> PIT-aligned with `f_ann_date`. No fragile Q1 heuristic.\n\n"
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
        "import matplotlib.pyplot as plt\n\n"
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
        "START_DATE = '2016-01-02'\n"
        "END_DATE   = '2025-12-31'\n"
        "TOP_K      = 5          # Hold 5 stocks (20% each, matches 果仁 spec)\n"
        "N_DROP     = 1          # Sell ≤ 1 stock per rebalance (TopkDropout Model II)\n\n"
        "# Screening\n"
        "RETURN_LOOKBACK = 250   # 250 trading days ≈ 1 year\n"
        "RETURN_MAX_PCT  = 0.75  # Keep bottom 75% (filter top 25% momentum)\n\n"
        "# Transaction costs (A-share)\n"
        "BUY_COST  = 0.0005      # 0.05% commission\n"
        "SELL_COST = 0.0015      # 0.15% commission + stamp tax"
    ))

    cells.append(new_markdown_cell(
        "### 2a. Load ALL stocks (for 250d return computation)\n\n"
        "We need the full price history for **all** stocks to compute 250-day returns,\n"
        "since a stock that recently became ST needs its pre-ST price history for the\n"
        "return lookback."
    ))

    cells.append(new_code_cell(
        "# ─── Load close & adj_factor from ALL stocks ──────────────\n"
        "all_instruments = D.instruments(market='all')\n\n"
        "print('Loading close prices for ALL stocks (for 250d return)...')\n"
        "df_all = D.features(\n"
        "    all_instruments,\n"
        "    ['$close', '$adj_factor', '$vol'],\n"
        "    start_time='2012-01-01',  # Need 2 years before START_DATE for 250d lookback\n"
        "    end_time=END_DATE,\n"
        ")\n"
        "df_all.columns = ['close', 'adj_factor', 'vol']\n\n"
        "# Compute adjusted close and 250-day return\n"
        "df_all['adj_close'] = df_all['close'] * df_all['adj_factor']\n"
        "df_all['return_250d'] = df_all.groupby(level=0)['adj_close'].pct_change(RETURN_LOOKBACK)\n\n"
        "print(f'All stocks data shape: {df_all.shape}')\n"
        "print(f'Unique stocks: {df_all.index.get_level_values(0).nunique()}')\n"
        "print(f'250d return coverage: {df_all[\"return_250d\"].notna().mean():.1%}')"
    ))

    cells.append(new_code_cell(
        "# ─── Compute 250d return cross-sectional percentile rank ──\n"
        "# This ranks ACROSS ALL stocks on each day, matching 果仁's logic\n"
        "df_all['ret_pctrank'] = df_all.groupby(level=1)['return_250d'].rank(pct=True)\n\n"
        "# Preview\n"
        "sample_date = df_all.index.get_level_values(1).unique()[-100]\n"
        "day_data = df_all.xs(sample_date, level=1)\n"
        "print(f'On {sample_date.strftime(\"%Y-%m-%d\")}:')\n"
        "print(f'  Stocks with 250d return: {day_data[\"return_250d\"].notna().sum()}')\n"
        "print(f'  75th percentile return: {day_data[\"return_250d\"].quantile(0.75):.2%}')"
    ))

    cells.append(new_markdown_cell(
        "### 2b. Load ST stocks (fundamentals & market data)\n\n"
        "The ST universe provides the *filter* — only trade ST stocks.\n"
        "Single-quarter revenue (`$revenue_q`) is loaded directly from Qlib —\n"
        "pre-computed from Tushare's native report_type=2,3 data with proper PIT alignment."
    ))

    cells.append(new_code_cell(
        "# ─── Load ST stock fundamentals (native single-quarter) ──\n"
        "st_instruments = D.instruments(market='st_stocks')\n\n"
        "st_fields = [\n"
        "    '$close',\n"
        "    '$total_mv',        # Total market cap (万元)\n"
        "    '$revenue_q',       # 营业收入 (single-quarter, from Tushare report_type=2,3)\n"
        "    '$vol',             # Volume\n"
        "    '$pct_chg',         # Daily % change\n"
        "]\n\n"
        "print('Loading ST stock data...')\n"
        "df_st = D.features(st_instruments, st_fields, start_time=START_DATE, end_time=END_DATE)\n"
        "df_st.columns = ['close', 'total_mv', 'revenue_q', 'vol', 'pct_chg']\n\n"
        "print(f'ST data shape: {df_st.shape}')\n"
        "print(f'ST stocks: {df_st.index.get_level_values(0).nunique()}')\n"
        "print(f'Date range: {df_st.index.get_level_values(1).min()} – '\n"
        "      f'{df_st.index.get_level_values(1).max()}')\n"
        "print(f'revenue_q coverage: {df_st[\"revenue_q\"].notna().mean():.1%}')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §3: QUARTERLY DATA VALIDATION
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 3. Quarterly Data Validation\n\n"
        "Single-quarter revenue is pre-computed from Tushare's native data:\n"
        "- `$revenue_q`: single-quarter revenue (report_type=2, PIT-aligned)\n\n"
        "Report type 3 (adjusted) supersedes type 2 based on announcement date."
    ))

    cells.append(new_code_cell(
        "# Quick validation of quarterly data\n"
        "print('Revenue_q stats:')\n"
        "print(df_st['revenue_q'].describe())\n"
        "print(f'\\nrevenue_q non-null: {df_st[\"revenue_q\"].notna().sum():,}')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §4: MERGE 250d RETURN & SCREENING
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 4. Merge 250d Return & Apply Screening\n\n"
        "**Critical step**: Merge the 250d return and its *all-market* percentile rank\n"
        "from the full `all_stocks` dataset onto the ST-only dataset.\n\n"
        "This ensures:\n"
        "- ST stocks use their *full* price history for 250d return (not just ST period)\n"
        "- The percentile filter uses all-market ranking (matching 果仁)"
    ))

    cells.append(new_code_cell(
        "# ─── Merge 250d return from all_stocks onto ST data ──────\n"
        "# The all_stocks data has 250d return for EVERY stock, including\n"
        "# the period before they became ST.\n\n"
        "# Restrict all_stocks data to the backtest period for merging\n"
        "df_all_bt = df_all.loc[\n"
        "    df_all.index.get_level_values(1) >= pd.Timestamp(START_DATE)\n"
        "].copy()\n\n"
        "# Get the 250d return and percentile rank for ST stocks\n"
        "st_stocks_set = set(df_st.index.get_level_values(0).unique())\n"
        "all_stocks_set = set(df_all_bt.index.get_level_values(0).unique())\n"
        "overlap = st_stocks_set & all_stocks_set\n\n"
        "print(f'ST stocks: {len(st_stocks_set)}')\n"
        "print(f'All stocks: {len(all_stocks_set)}')\n"
        "print(f'ST stocks found in all_stocks: {len(overlap)}')\n"
        "print(f'ST stocks MISSING from all_stocks: {len(st_stocks_set - all_stocks_set)}')\n\n"
        "# Extract 250d return data for ST stocks from the all_stocks dataset\n"
        "# This uses the FULL price history for the return calculation\n"
        "df_ret = df_all_bt[['return_250d', 'ret_pctrank']]\n"
        "df_ret_st = df_ret.loc[df_ret.index.get_level_values(0).isin(st_stocks_set)]\n\n"
        "# Merge onto ST frame\n"
        "df_st['return_250d'] = df_ret_st['return_250d']\n"
        "df_st['ret_pctrank'] = df_ret_st['ret_pctrank']\n\n"
        "print(f'\\n250d return coverage in ST data: {df_st[\"return_250d\"].notna().mean():.1%}')\n"
        "print(f'Percentile rank coverage: {df_st[\"ret_pctrank\"].notna().mean():.1%}')"
    ))

    cells.append(new_code_cell(
        "# ─── Apply screening filters ─────────────────────────────\n"
        "print(f'Before filtering: {df_st.shape}')\n\n"
        "# Drop rows missing key fields\n"
        "df_screen = df_st.dropna(subset=['total_mv', 'close', 'return_250d', 'revenue_q']).copy()\n"
        "print(f'After dropping NaN (need 250d return, revenue_q): {df_screen.shape}')\n\n"
        "# Filter: tradable (volume > 0, not suspended)\n"
        "df_screen = df_screen[df_screen['vol'] > 0].copy()\n"
        "print(f'Tradable (vol > 0): {df_screen.shape}')\n\n"
        "# Filter: 250d return within bottom 75% (cross-sectional percentile\n"
        "# ranked ACROSS ALL STOCKS, not just ST)\n"
        "df_screen = df_screen[df_screen['ret_pctrank'] <= RETURN_MAX_PCT].copy()\n"
        "print(f'250d return ≤ 75th pctile (all-market rank): {df_screen.shape}')\n\n"
        "# Summary\n"
        "stocks_per_day = df_screen.groupby(level=1).size()\n"
        "print(f'\\nScreened ST universe stats:')\n"
        "print(f'  Date range: {df_screen.index.get_level_values(1).min()} – '\n"
        "      f'{df_screen.index.get_level_values(1).max()}')\n"
        "print(f'  Unique stocks: {df_screen.index.get_level_values(0).nunique()}')\n"
        "print(f'  Stocks per day: min={stocks_per_day.min()}, '\n"
        "      f'median={stocks_per_day.median():.0f}, max={stocks_per_day.max()}')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §5: RANKING & SIGNAL
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 5. Ranking & Signal Construction\n\n"
        "Two ranking factors (both **descending** — larger = better rank):\n"
        "1. **总市值** (total market cap): larger → higher rank (weight 1)\n"
        "2. **营业收入(单季)**: larger → higher rank (weight 1)\n\n"
        "Composite score = sum of the two percentile ranks (equal weight).\n"
        "Higher composite → more desirable."
    ))

    cells.append(new_code_cell(
        "# ─── Cross-sectional percentile ranking (per day) ────────\n"
        "# Rank within the SCREENED ST UNIVERSE (not all stocks)\n"
        "# ascending=True + pct=True: largest value → highest rank\n\n"
        "df_screen['rank_mv'] = df_screen.groupby(level=1)['total_mv'].rank(\n"
        "    pct=True, ascending=True, na_option='bottom'\n"
        ")\n"
        "df_screen['rank_rev'] = df_screen.groupby(level=1)['revenue_q'].rank(\n"
        "    pct=True, ascending=True, na_option='bottom'\n"
        ")\n\n"
        "# Composite score: equal-weight sum of 2 rank factors\n"
        "df_screen['composite_score'] = (\n"
        "    df_screen['rank_mv'] + df_screen['rank_rev']\n"
        ")\n\n"
        "# Sanity check\n"
        "print('Composite score stats:')\n"
        "print(df_screen['composite_score'].describe())\n"
        "print(f'NaN count: {df_screen[\"composite_score\"].isna().sum()}')"
    ))

    cells.append(new_code_cell(
        "# ─── Preview: top-ranked stocks on a sample date ─────────\n"
        "sample_dates = df_screen.index.get_level_values(1).unique()\n"
        "mid_idx = len(sample_dates) // 2\n"
        "sample_date = sample_dates[mid_idx]\n\n"
        "sample = df_screen.xs(sample_date, level=1).nlargest(10, 'composite_score')\n"
        "print(f'\\nTop-10 stocks on {sample_date.strftime(\"%Y-%m-%d\")}:')\n"
        "display(sample[['total_mv', 'revenue_q',\n"
        "                 'rank_mv', 'rank_rev',\n"
        "                 'composite_score', 'return_250d']].round(4))"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §6: QLIB BACKTEST (TopkDropout / Model II)
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 6. Backtest (Model II — TopkDropout)\n\n"
        "Run through Qlib's `VectorizedBacktester` with `TopkDropout`.\n"
        "TopkDropout only sells stocks that *drop out* of the top-K,\n"
        "matching 果仁's Model II.\n\n"
        "- `topk=5`: hold 5 stocks (20% each, matches 果仁 spec)\n"
        "- `n_drop=1`: sell ≤ 1 stock per rebalance\n"
        "- `hold_thresh=1`: can trade every day\n"
        "- `deal_price=\"open\"`: 09:35 approximation\n"
        "- Sell condition: rank ≥ 6 (drop out of top-5)"
    ))

    cells.append(new_code_cell(
        "# ─── Build signal for Qlib ───────────────────────────────\n"
        "# Signal = composite_score from screened ST universe.\n\n"
        "signal = df_screen['composite_score'].dropna()\n\n"
        "# Reformat to MultiIndex(datetime, instrument) as Qlib expects\n"
        "signal = signal.swaplevel().sort_index()\n"
        "signal.index.names = ['datetime', 'instrument']\n\n"
        "print(f'Signal entries: {len(signal):,}')\n"
        "print(f'Trading days with signal: {signal.index.get_level_values(0).nunique()}')\n"
        "print(f'Stocks per day (median): '\n"
        "      f'{signal.groupby(level=0).count().median():.0f}')"
    ))

    cells.append(new_code_cell(
        "%%time\n"
        "from src.backtest_engine.vectorized import VectorizedBacktester\n\n"
        "# Override deal_price to 'open' (proxy for 09:35)\n"
        "exchange_kwargs = {\n"
        "    'deal_price': 'open',\n"
        "    # ST stocks have ±5% limit (tighter than main board ±10%)\n"
        "    'limit_threshold': ('Ge($pct_chg, 4.5)', 'Le($pct_chg, -4.5)'),\n"
        "}\n\n"
        "bt = VectorizedBacktester(\n"
        "    config_path=os.path.join(PROJECT_ROOT, 'config.yaml'),\n"
        "    qlib_dir=QLIB_DIR,\n"
        ")\n\n"
        "qlib_result = bt.run(\n"
        "    predictions=signal,\n"
        "    start_time=START_DATE,\n"
        "    end_time=END_DATE,\n"
        "    topk=TOP_K,\n"
        "    n_drop=N_DROP,\n"
        "    hold_thresh=1,\n"
        "    benchmark='000001_SH',          # SSE Composite\n"
        "    exchange_kwargs=exchange_kwargs,\n"
        ")\n\n"
        "print('Qlib backtest complete')\n"
        "print(qlib_result)"
    ))

    cells.append(new_code_cell(
        "# ─── Backtest Report ──────────────────────────────────────\n"
        "from src.result_analysis import BacktestReport\n\n"
        "qlib_report = qlib_result.report\n"
        "qlib_net_ret = qlib_report['return'] - qlib_report['cost']\n"
        "qlib_bench_ret = qlib_report['bench']\n\n"
        "report_qlib = BacktestReport(\n"
        "    qlib_net_ret, qlib_bench_ret,\n"
        "    name='ST Strategy (TopkDropout / Model II)',\n"
        "    risk_free_rate=0.02,\n"
        ")\n"
        "report_qlib.summary()"
    ))

    cells.append(new_code_cell(
        "# ─── Trading Analysis ────────────────────────────────────\n"
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
        "        df=df_st,\n"
        "        report_df=qlib_result.report,\n"
        "        buy_cost=BUY_COST,\n"
        "        sell_cost=SELL_COST,\n"
        "    )\n"
        "else:\n"
        "    print('No Qlib positions available for trading analysis')"
    ))

    cells.append(new_code_cell("report_qlib.plot()"))
    cells.append(new_code_cell("report_qlib.yearly()"))
    cells.append(new_code_cell("report_qlib.monthly_heatmap()"))
    cells.append(new_code_cell("report_qlib.rolling(window=252)"))
    cells.append(new_code_cell("report_qlib.distribution()"))

    # ═══════════════════════════════════════════════════════════════
    # §7: VALIDATION vs 果仁
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 7. Validation vs 果仁 Holdings\n\n"
        "Load the 果仁 backtest Excel and compare holdings on sample dates\n"
        "to verify signal correctness."
    ))

    cells.append(new_code_cell(
        "# ─── Load 果仁 holding data ──────────────────────────────\n"
        "guoren_path = os.path.join(PROJECT_ROOT, '果仁回测明细', 'ST Strategy Backtest.xlsx')\n"
        "if os.path.exists(guoren_path):\n"
        "    gr = pd.read_excel(guoren_path, sheet_name='各阶段持仓详单')\n"
        "    print(f'Loaded 果仁 data: {gr.shape[0]} rows')\n\n"
        "    # Normalize codes\n"
        "    def guoren_code_to_qlib(code_int):\n"
        "        code_str = str(code_int).zfill(6)\n"
        "        return f'{code_str}_SH' if code_str.startswith('6') else f'{code_str}_SZ'\n\n"
        "    gr['qlib_code'] = gr['股票代码'].apply(guoren_code_to_qlib)\n"
        "    gr['date'] = pd.to_datetime(gr['开始日期'])\n"
        "else:\n"
        "    gr = None\n"
        "    print(f'果仁 Excel not found at {guoren_path}')"
    ))

    cells.append(new_code_cell(
        "# ─── Compare top-5 on sample dates ───────────────────────\n"
        "if gr is not None:\n"
        "    check_dates = [\n"
        "        pd.Timestamp('2014-01-02'), pd.Timestamp('2015-01-05'),\n"
        "        pd.Timestamp('2018-01-02'), pd.Timestamp('2020-01-02'),\n"
        "        pd.Timestamp('2023-01-03'), pd.Timestamp('2025-06-02'),\n"
        "    ]\n\n"
        "    for dt in check_dates:\n"
        "        gr_day = gr[gr['date'] == dt]\n"
        "        if gr_day.empty:\n"
        "            nearest = gr['date'].unique()\n"
        "            nearest = nearest[nearest >= dt]\n"
        "            if len(nearest) > 0:\n"
        "                dt = pd.Timestamp(nearest[0])\n"
        "                gr_day = gr[gr['date'] == dt]\n"
        "        if gr_day.empty:\n"
        "            continue\n\n"
        "        gr_stocks = set(gr_day['qlib_code'])\n\n"
        "        # Our picks on this date\n"
        "        try:\n"
        "            our_day = df_screen.xs(dt, level=1)\n"
        "            our_top5 = set(our_day.nlargest(TOP_K, 'composite_score').index)\n"
        "        except KeyError:\n"
        "            our_top5 = set()\n\n"
        "        overlap = gr_stocks & our_top5\n\n"
        "        print(f'\\n{dt.date()}: 果仁={len(gr_day)} stocks, '\n"
        "              f'ours={len(our_top5)}, overlap={len(overlap)}')\n"
        "        print(f'  果仁 picks: {sorted(gr_stocks)}')\n"
        "        print(f'  Our picks:  {sorted(our_top5)}')\n"
        "        if overlap:\n"
        "            print(f'  ✓ Match:    {sorted(overlap)}')\n"
        "else:\n"
        "    print('Skipping validation (果仁 data not available)')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §8: UNIVERSE ANALYSIS
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell("## 8. Universe & Holdings Analysis"))

    cells.append(new_code_cell(
        "# ST Universe size over time\n"
        "fig, ax = plt.subplots(figsize=(14, 4))\n"
        "stocks_per_day.plot(ax=ax, color='#E53935', linewidth=0.8)\n"
        "ax.set_ylabel('Screened ST Stocks')\n"
        "ax.set_title('ST Universe Size Over Time (after 250d return filter)',\n"
        "             fontweight='bold')\n"
        "ax.grid(alpha=0.3)\n"
        "plt.tight_layout()\n"
        "plt.show()"
    ))

    # ═══════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## Summary\n\n"
        "| Parameter | Value |\n"
        "|-----------|-------|\n"
        "| Signal | Composite: total_mv↓ + revenue_q↓ + CoreProfitQ↓ |\n"
        "| CoreProfitQ | 营收 - 营业成本 - (管理+销售+财务费用) - 税金及附加 |\n"
        "| Universe | ST stocks only (PIT from namechange data) |\n"
        "| Screen | 250d return 0%–75% percentile (ranked vs ALL stocks) |\n"
        "| Stocks held | 6 |\n"
        "| Weighting | Equal (≈16.7% each) |\n"
        "| Rebalance | Daily (Model II: TopkDropout n_drop=1) |\n"
        "| Deal price | Open (proxy for 09:35) |\n"
        "| Costs | Buy 0.05% + Sell 0.15% |\n"
        "| Backtest period | 2014-01-01 → 2025-12-31 |\n"
        "| Benchmark | SSE Composite (000001_SH) |\n\n"
        "### Key Approximations\n"
        "- **Deal price**: 果仁 09:35 → Qlib uses open price\n"
        "- **Single-quarter**: Native Tushare report_type=2,3 data, PIT-aligned\n"
        "- **ST limit**: ±5% (vs ±10% main board); threshold set to 4.5%\n"
        "- **Model II**: TopkDropout n_drop=1 approximates 果仁's Model II\n"
        "- **Position range**: 14–26% not exactly enforced; equal-weight ≈ 16.7%\n\n"
        "---\n"
        "*Generated by `workspace/scripts/generate_st_notebook.py` (v3)*"
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
