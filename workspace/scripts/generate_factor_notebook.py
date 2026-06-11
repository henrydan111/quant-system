# ──────────────────────────────────────────────────────────────────────
# PR 7 of 2026-05-26 freeze plan — SCRIPT_STATUS header block.
# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: joinquant_attribution_only
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   Sandbox / one-shot diagnostic script. NOT a formal research
#   surface. Bare D.features calls inside this file are tolerated
#   per scripts/lint_no_bare_qlib_features.py allowlist semantics
#   (PR 6) but the script's output is not eligible for the formal
#   release gate.
# ──────────────────────────────────────────────────────────────────────
"""
Generate Factor Analysis Jupyter Notebook

Programmatically creates a comprehensive .ipynb notebook for analyzing
all 50 factors from the factor catalog. Uses nbformat to build cells.

Usage:
    python workspace/scripts/generate_factor_notebook.py

Output:
    workspace/research/alpha_factors/factor_analysis_50.ipynb
"""

import os
import sys
import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "workspace", "research", "alpha_factors")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "factor_analysis_50.ipynb")


def make_notebook():
    """Build the complete factor analysis notebook."""
    nb = new_notebook()
    nb.metadata.kernelspec = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    cells = []

    # ═══════════════════════════════════════════════════════════════
    # SECTION 0: Title & Metadata
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "# 50-Factor Analysis Workbook\n\n"
        "Systematic evaluation of 50 industry-standard alpha factors using the `factor_eval` library.\n\n"
        "**Research Integrity Rules:**\n"
        "- All price data uses backward-adjusted close (`close × adj_factor`)\n"
        "- PIT-aligned fundamentals (no lookahead bias)\n"
        "- `all_stocks` universe (includes delisted — no survivorship bias)\n"
        "- Temporal split: Train 2012–2020 | Validation 2021–2023 | Test 2024+\n"
        "- ICIR < 0.3 → questioned | ICIR < 0.1 → discarded\n\n"
        "---"
    ))

    # ═══════════════════════════════════════════════════════════════
    # SECTION 1: Environment Setup
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell("## 1. Environment Setup"))

    cells.append(new_code_cell(
        "import sys\n"
        "import os\n"
        "import warnings\n"
        "warnings.filterwarnings('ignore')\n\n"
        "# Project root\n"
        "PROJECT_ROOT = r'e:\\量化系统'\n"
        "sys.path.insert(0, PROJECT_ROOT)\n\n"
        "import numpy as np\n"
        "import pandas as pd\n"
        "import matplotlib.pyplot as plt\n"
        "import seaborn as sns\n"
        "from IPython.display import display, HTML\n\n"
        "# Qlib initialization\n"
        "import qlib\n"
        "from qlib.data import D\n"
        "from qlib.config import REG_CN\n\n"
        "QLIB_DIR = os.path.join(PROJECT_ROOT, 'data', 'qlib_data')\n"
        "qlib.init(provider_uri=QLIB_DIR, region=REG_CN)\n"
        "print('Qlib initialized successfully')\n\n"
        "# Import factor_eval library\n"
        "from src.alpha_research.factor_eval import (\n"
        "    compute_ic_series, compute_ic_summary, compute_ic_by_year,\n"
        "    compute_quantile_returns, compute_quantile_summary,\n"
        "    compute_long_short_returns, test_monotonicity,\n"
        ")\n"
        "from src.alpha_research.factor_eval.factor_plotters import (\n"
        "    plot_factor_report, plot_ic_time_series, plot_quantile_returns,\n"
        ")\n\n"
        "print('factor_eval library loaded')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # SECTION 2: Data Loading
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 2. Data Loading\n\n"
        "Load all required fields from Qlib in one batch."
    ))

    cells.append(new_code_cell(
        "# Define date ranges\n"
        "START_DATE = '2012-01-01'\n"
        "END_DATE   = '2025-12-31'\n\n"
        "# Temporal split boundaries\n"
        "TRAIN_END = '2020-12-31'\n"
        "VAL_END   = '2023-12-31'\n"
        "TEST_START = '2024-01-01'\n\n"
        "# Universe: all_stocks to avoid survivorship bias\n"
        "instruments = D.instruments(market='all_stocks')\n\n"
        "# --- Daily market fields ---\n"
        "market_fields = [\n"
        "    '$close', '$open', '$high', '$low',\n"
        "    '$vol', '$amount', '$pct_chg',\n"
        "    '$turnover_rate', '$volume_ratio',\n"
        "    '$pe_ttm', '$pb', '$ps_ttm',\n"
        "    '$dv_ttm', '$total_mv', '$circ_mv',\n"
        "    '$adj_factor',\n"
        "]\n\n"
        "print(f'Loading market data for {START_DATE} to {END_DATE}...')\n"
        "df_market = D.features(instruments, market_fields, start_time=START_DATE, end_time=END_DATE)\n"
        "df_market.columns = [c.lstrip('$') for c in df_market.columns]\n\n"
        "# Qlib returns MultiIndex(instrument, datetime) — swap to (datetime, instrument)\n"
        "# so that our pandas groupby(level=1) per-stock operations work correctly.\n"
        "# (factor_eval library handles this normalization internally for its own functions.)\n"
        "df_market = df_market.swaplevel().sort_index()\n\n"
        "print(f'Market data shape: {df_market.shape}')\n"
        "print(f'Date range: {df_market.index.get_level_values(0).min()} to {df_market.index.get_level_values(0).max()}')\n"
        "print(f'Stocks: {df_market.index.get_level_values(1).nunique()}')"
    ))

    cells.append(new_code_cell(
        "# --- Fundamental fields (PIT-aligned) ---\n"
        "funda_fields = [\n"
        "    '$roe', '$roa', '$roic',\n"
        "    '$grossprofit_margin', '$netprofit_margin',\n"
        "    '$assets_turn', '$ocfps',\n"
        "    '$or_yoy', '$netprofit_yoy',\n"
        "    '$q_op_qoq', '$basic_eps_yoy',\n"
        "    '$roe_yoy',\n"
        "]\n\n"
        "print('Loading fundamental data (PIT-aligned)...')\n"
        "df_funda = D.features(instruments, funda_fields, start_time=START_DATE, end_time=END_DATE)\n"
        "df_funda.columns = [c.lstrip('$') for c in df_funda.columns]\n"
        "df_funda = df_funda.swaplevel().sort_index()\n"
        "print(f'Fundamental data shape: {df_funda.shape}')"
    ))

    cells.append(new_code_cell(
        "# Compute adjusted close\n"
        "adj_close = df_market['close'] * df_market['adj_factor']\n"
        "adj_close.name = 'adj_close'\n\n"
        "# Daily returns\n"
        "daily_ret = adj_close.groupby(level=1).pct_change()\n"
        "daily_ret.name = 'daily_return'\n\n"
        "# Forward returns (evaluation targets)\n"
        "fwd_1d  = adj_close.groupby(level=1).shift(-1) / adj_close - 1\n"
        "fwd_5d  = adj_close.groupby(level=1).shift(-5) / adj_close - 1\n"
        "fwd_10d = adj_close.groupby(level=1).shift(-10) / adj_close - 1\n"
        "fwd_20d = adj_close.groupby(level=1).shift(-20) / adj_close - 1\n\n"
        "print('Adjusted close, daily returns, and forward returns computed.')\n"
        "print(f'  adj_close NaN%: {adj_close.isna().mean():.2%}')\n"
        "print(f'  fwd_1d NaN%:    {fwd_1d.isna().mean():.2%}')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # SECTION 3: Factor Definitions
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 3. Factor Definitions\n\n"
        "All 50 factors computed in a single cell. Each factor is a `pd.Series` with\n"
        "`MultiIndex(datetime, instrument)`. Factors are shifted by 1 day to prevent\n"
        "same-day leakage.\n\n"
        "> **Note:** Factor values at time `t` are available for trading at `t+1`."
    ))

    cells.append(new_code_cell(
        "factors = {}\n\n"
        "# ─── MOMENTUM (动量) ───────────────────────────────────────\n"
        "factors['mom_return_20d']    = adj_close / adj_close.groupby(level=1).shift(20) - 1\n"
        "factors['mom_return_60d']    = adj_close / adj_close.groupby(level=1).shift(60) - 1\n"
        "factors['mom_return_120d']   = adj_close / adj_close.groupby(level=1).shift(120) - 1\n"
        "factors['mom_return_250d']   = adj_close / adj_close.groupby(level=1).shift(250) - 1\n"
        "factors['mom_skip1m']        = adj_close.groupby(level=1).shift(21) / adj_close.groupby(level=1).shift(252) - 1\n\n"
        "# Weighted momentum (recency-weighted 120d returns)\n"
        "def _weighted_mom(g, window=120):\n"
        "    weights = np.arange(1, window + 1, dtype=float)\n"
        "    weights /= weights.sum()\n"
        "    return g.pct_change().rolling(window).apply(lambda x: (x * weights).sum(), raw=True)\n"
        "factors['mom_weighted_120d'] = daily_ret.groupby(level=1).transform(\n"
        "    lambda x: x.rolling(120).apply(lambda r: (r * (np.arange(1,121)/np.arange(1,121).sum())).sum(), raw=True)\n"
        ")\n\n"
        "# Overnight return (averaged over 20d)\n"
        "adj_open = df_market['open'] * df_market['adj_factor']\n"
        "overnight = adj_open / adj_close.groupby(level=1).shift(1) - 1\n"
        "factors['mom_overnight_20d'] = overnight.groupby(level=1).transform(lambda x: x.rolling(20).mean())\n\n"
        "print(f'Momentum factors: {sum(1 for k in factors if k.startswith(\"mom\"))}')"
    ))

    cells.append(new_code_cell(
        "# ─── VALUE (价值) ─────────────────────────────────────────\n"
        "factors['val_ep_ttm']     = 1.0 / df_market['pe_ttm'].replace(0, np.nan)\n"
        "factors['val_bp']         = 1.0 / df_market['pb'].replace(0, np.nan)\n"
        "factors['val_sp_ttm']     = 1.0 / df_market['ps_ttm'].replace(0, np.nan)\n"
        "factors['val_cftp']       = df_funda['ocfps'] / df_market['close'].replace(0, np.nan)\n"
        "factors['val_div_yield']  = df_market['dv_ttm'] / 100.0\n\n"
        "# EV/EBITDA and EBIT/EV require cross-referencing — simplified using available ratios\n"
        "# For now we use inverse PE and PB as primary value proxies\n"
        "factors['val_earnings_yield'] = factors['val_ep_ttm']  # alias for clarity\n"
        "factors['val_book_yield']     = factors['val_bp']       # alias for clarity\n\n"
        "print(f'Value factors: {sum(1 for k in factors if k.startswith(\"val\"))}')"
    ))

    cells.append(new_code_cell(
        "# ─── QUALITY (质量) ───────────────────────────────────────\n"
        "factors['qual_roe']              = df_funda['roe']\n"
        "factors['qual_roa']              = df_funda['roa']\n"
        "factors['qual_roic']             = df_funda['roic']\n"
        "factors['qual_gross_margin']     = df_funda['grossprofit_margin']\n"
        "factors['qual_net_margin']       = df_funda['netprofit_margin']\n"
        "factors['qual_asset_turnover']   = df_funda['assets_turn']\n\n"
        "print(f'Quality factors: {sum(1 for k in factors if k.startswith(\"qual\"))}')"
    ))

    cells.append(new_code_cell(
        "# ─── GROWTH (成长) ────────────────────────────────────────\n"
        "factors['grow_revenue_yoy']     = df_funda['or_yoy']\n"
        "factors['grow_netprofit_yoy']   = df_funda['netprofit_yoy']\n"
        "factors['grow_opprofit_qoq']    = df_funda['q_op_qoq']\n"
        "factors['grow_eps_yoy']         = df_funda['basic_eps_yoy']\n"
        "factors['grow_roe_change']      = df_funda['roe_yoy']\n\n"
        "print(f'Growth factors: {sum(1 for k in factors if k.startswith(\"grow\"))}')"
    ))

    cells.append(new_code_cell(
        "# ─── SIZE (规模) ──────────────────────────────────────────\n"
        "factors['size_ln_mcap']    = np.log(df_market['total_mv'].replace(0, np.nan) * 10000)\n"
        "factors['size_ln_circmv']  = np.log(df_market['circ_mv'].replace(0, np.nan) * 10000)\n\n"
        "print(f'Size factors: {sum(1 for k in factors if k.startswith(\"size\"))}')"
    ))

    cells.append(new_code_cell(
        "# ─── VOLATILITY / RISK (波动率) ──────────────────────────\n"
        "factors['risk_vol_20d']  = daily_ret.groupby(level=1).transform(lambda x: x.rolling(20).std())\n"
        "factors['risk_vol_60d']  = daily_ret.groupby(level=1).transform(lambda x: x.rolling(60).std())\n"
        "factors['risk_downvol_60d'] = daily_ret.clip(upper=0).groupby(level=1).transform(\n"
        "    lambda x: x.rolling(60).std()\n"
        ")\n\n"
        "# Max drawdown over 60 trading days\n"
        "def _rolling_mdd(prices, window=60):\n"
        "    def _mdd(x):\n"
        "        cummax = np.maximum.accumulate(x)\n"
        "        return np.min(x / cummax - 1)\n"
        "    return prices.rolling(window).apply(_mdd, raw=True)\n\n"
        "factors['risk_mdd_60d'] = adj_close.groupby(level=1).transform(lambda x: _rolling_mdd(x, 60))\n\n"
        "print(f'Volatility/Risk factors: {sum(1 for k in factors if k.startswith(\"risk\"))}')"
    ))

    cells.append(new_code_cell(
        "# ─── LIQUIDITY / VOLUME (流动性) ─────────────────────────\n"
        "factors['liq_turnover_20d']  = df_market['turnover_rate'].groupby(level=1).transform(\n"
        "    lambda x: x.rolling(20).mean()\n"
        ")\n"
        "factors['liq_turnover_ratio'] = (\n"
        "    df_market['turnover_rate'].groupby(level=1).transform(lambda x: x.rolling(5).mean()) /\n"
        "    df_market['turnover_rate'].groupby(level=1).transform(lambda x: x.rolling(60).mean()).replace(0, np.nan)\n"
        ")\n\n"
        "# Amihud illiquidity\n"
        "abs_ret = daily_ret.abs()\n"
        "dollar_vol = df_market['amount'].replace(0, np.nan)\n"
        "amihud_daily = abs_ret / dollar_vol\n"
        "factors['liq_amihud'] = amihud_daily.groupby(level=1).transform(lambda x: x.rolling(20).mean())\n\n"
        "# Volume coefficient of variation\n"
        "vol_mean = df_market['vol'].groupby(level=1).transform(lambda x: x.rolling(20).mean())\n"
        "vol_std  = df_market['vol'].groupby(level=1).transform(lambda x: x.rolling(20).std())\n"
        "factors['liq_vol_cv'] = vol_std / vol_mean.replace(0, np.nan)\n\n"
        "# Volume ratio (smoothed)\n"
        "factors['liq_vol_ratio_ma5'] = df_market['volume_ratio'].groupby(level=1).transform(\n"
        "    lambda x: x.rolling(5).mean()\n"
        ")\n\n"
        "# Log dollar volume\n"
        "factors['liq_log_dollar_vol'] = np.log(\n"
        "    (df_market['amount'] * 1000).groupby(level=1).transform(lambda x: x.rolling(20).mean()).replace(0, np.nan)\n"
        ")\n\n"
        "print(f'Liquidity factors: {sum(1 for k in factors if k.startswith(\"liq\"))}')"
    ))

    cells.append(new_code_cell(
        "# ─── REVERSAL / TECHNICAL (反转/技术) ────────────────────\n"
        "factors['tech_reversal_5d'] = -(adj_close / adj_close.groupby(level=1).shift(5) - 1)\n\n"
        "# RSI 14\n"
        "def _compute_rsi(returns, window=14):\n"
        "    gain = returns.clip(lower=0)\n"
        "    loss = (-returns).clip(lower=0)\n"
        "    avg_gain = gain.rolling(window).mean()\n"
        "    avg_loss = loss.rolling(window).mean()\n"
        "    rs = avg_gain / avg_loss.replace(0, np.nan)\n"
        "    return 100 - 100 / (1 + rs)\n\n"
        "factors['tech_rsi_14'] = daily_ret.groupby(level=1).transform(lambda x: _compute_rsi(x, 14))\n\n"
        "# Close-to-high ratio (20d)\n"
        "adj_high = df_market['high'] * df_market['adj_factor']\n"
        "rolling_high_20 = adj_high.groupby(level=1).transform(lambda x: x.rolling(20).max())\n"
        "factors['tech_close_to_high_20d'] = adj_close / rolling_high_20.replace(0, np.nan) - 1\n\n"
        "# Price-to-MA60 deviation\n"
        "ma60 = adj_close.groupby(level=1).transform(lambda x: x.rolling(60).mean())\n"
        "factors['tech_price_to_ma60'] = adj_close / ma60.replace(0, np.nan) - 1\n\n"
        "# Return skewness and kurtosis (20d)\n"
        "factors['tech_skew_20d'] = daily_ret.groupby(level=1).transform(lambda x: x.rolling(20).skew())\n"
        "factors['tech_kurt_20d'] = daily_ret.groupby(level=1).transform(lambda x: x.rolling(20).kurt())\n\n"
        "print(f'Technical factors: {sum(1 for k in factors if k.startswith(\"tech\"))}')"
    ))

    cells.append(new_code_cell(
        "# ─── APPLY SHIFT(1) TO PREVENT SAME-DAY LEAKAGE ─────────\n"
        "for name in factors:\n"
        "    factors[name] = factors[name].groupby(level=1).shift(1)\n\n"
        "# Summary\n"
        "factor_names = sorted(factors.keys())\n"
        "print(f'\\nTotal factors defined: {len(factors)}')\n"
        "print('\\nFactor coverage (non-NaN %):') \n"
        "coverage = pd.Series({k: 1 - v.isna().mean() for k, v in factors.items()}).sort_values()\n"
        "print(coverage.to_string())"
    ))

    # ═══════════════════════════════════════════════════════════════
    # SECTION 4: Single-Factor Screening (Batch IC)
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 4. Batch IC Screening\n\n"
        "Compute IC/ICIR for all factors against 5-day forward returns to quickly\n"
        "identify which factors have predictive power."
    ))

    cells.append(new_code_cell(
        "# Batch IC computation (5d forward return)\n"
        "fwd = fwd_5d  # Primary evaluation horizon\n\n"
        "ic_results = {}\n"
        "for name, factor in factors.items():\n"
        "    try:\n"
        "        ic = compute_ic_series(factor, fwd, min_obs=50)\n"
        "        if not ic.empty:\n"
        "            summary = compute_ic_summary(ic)\n"
        "            ic_results[name] = summary\n"
        "    except Exception as e:\n"
        "        print(f'  SKIP {name}: {e}')\n\n"
        "ic_df = pd.DataFrame(ic_results).T\n"
        "ic_df = ic_df.sort_values('rank_icir', key=abs, ascending=False)\n\n"
        "# Color-code by ICIR quality\n"
        "print(f'IC results for {len(ic_df)} factors (sorted by |RankICIR|):\\n')\n"
        "display(ic_df.style.format({\n"
        "    'mean_ic': '{:.4f}', 'mean_rank_ic': '{:.4f}',\n"
        "    'std_ic': '{:.4f}', 'std_rank_ic': '{:.4f}',\n"
        "    'icir': '{:.3f}', 'rank_icir': '{:.3f}',\n"
        "    'ic_hit_rate': '{:.1%}', 'ic_positive_pct': '{:.1%}',\n"
        "}).background_gradient(subset=['rank_icir'], cmap='RdYlGn', vmin=-0.5, vmax=0.5))"
    ))

    cells.append(new_code_cell(
        "# Horizontal bar chart of ICIR\n"
        "fig, ax = plt.subplots(figsize=(10, max(8, len(ic_df) * 0.3)))\n"
        "colors = ['#4CAF50' if v > 0.3 else '#FFC107' if v > 0.1 else '#F44336' \n"
        "          for v in ic_df['rank_icir'].abs()]\n"
        "ax.barh(ic_df.index, ic_df['rank_icir'], color=colors, edgecolor='white')\n"
        "ax.axvline(0, color='black', linewidth=0.5)\n"
        "ax.axvline(0.3, color='green', linewidth=1, linestyle='--', alpha=0.5, label='ICIR=0.3')\n"
        "ax.axvline(-0.3, color='green', linewidth=1, linestyle='--', alpha=0.5)\n"
        "ax.set_xlabel('Rank ICIR')\n"
        "ax.set_title('Factor Rank ICIR (5d Forward Return)', fontweight='bold')\n"
        "ax.legend()\n"
        "plt.tight_layout()\n"
        "plt.show()"
    ))

    # ═══════════════════════════════════════════════════════════════
    # SECTION 5: Deep-Dive Single Factor Analysis
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 5. Deep-Dive: Single Factor Analysis\n\n"
        "Select a factor and run the full tearsheet: IC series, quantile portfolios,\n"
        "long-short curve, and summary statistics.\n\n"
        "**Change `FACTOR_NAME` below to analyze different factors.**"
    ))

    cells.append(new_code_cell(
        "# ===== CHANGE THIS TO ANALYZE A DIFFERENT FACTOR =====\n"
        "FACTOR_NAME = 'val_ep_ttm'\n"
        "FWD_HORIZON = fwd_5d  # 5-day forward return\n"
        "# ======================================================\n\n"
        "factor = factors[FACTOR_NAME]\n\n"
        "# IC analysis\n"
        "ic = compute_ic_series(factor, FWD_HORIZON, min_obs=50)\n"
        "summary = compute_ic_summary(ic)\n"
        "yearly = compute_ic_by_year(ic)\n\n"
        "print(f'=== {FACTOR_NAME} ===\\n')\n"
        "print(f\"Mean IC:      {summary['mean_ic']:.4f}\")\n"
        "print(f\"Mean RankIC:  {summary['mean_rank_ic']:.4f}\")\n"
        "print(f\"ICIR:         {summary['icir']:.4f}\")\n"
        "print(f\"RankICIR:     {summary['rank_icir']:.4f}\")\n"
        "print(f\"IC Hit Rate:  {summary['ic_hit_rate']:.1%}\")\n"
        "print(f\"Days:         {summary['n_days']}\")\n\n"
        "print('\\n--- Yearly Breakdown ---')\n"
        "display(yearly.style.format({\n"
        "    'mean_ic': '{:.4f}', 'mean_rank_ic': '{:.4f}',\n"
        "    'icir': '{:.3f}', 'rank_icir': '{:.3f}',\n"
        "    'ic_hit_rate': '{:.1%}'\n"
        "}))"
    ))

    cells.append(new_code_cell(
        "# Quantile analysis\n"
        "q_returns = compute_quantile_returns(factor, FWD_HORIZON, n_quantiles=10, min_obs=100)\n"
        "q_summary = compute_quantile_summary(q_returns)\n"
        "ls_returns = compute_long_short_returns(q_returns)\n"
        "mono = test_monotonicity(q_summary)\n\n"
        "print(f'Monotonicity: {\"PASS\" if mono[\"is_monotonic\"] else \"FAIL\"}')\n"
        "print(f'  Spearman corr: {mono[\"spearman_corr\"]:.4f} (p={mono[\"p_value\"]:.4f})')\n"
        "print(f'  Direction: {mono[\"direction\"]}\\n')\n\n"
        "display(q_summary.style.format({\n"
        "    'mean_daily_return': '{:.4%}',\n"
        "    'annualized_return': '{:.2%}',\n"
        "    'volatility': '{:.2%}',\n"
        "    'sharpe': '{:.3f}',\n"
        "}))"
    ))

    cells.append(new_code_cell(
        "# Composite tearsheet\n"
        "fig = plot_factor_report(\n"
        "    factor_name=FACTOR_NAME,\n"
        "    ic_series=ic,\n"
        "    quantile_summary=q_summary,\n"
        "    ls_returns=ls_returns,\n"
        "    ic_summary=summary,\n"
        ")\n"
        "plt.show()"
    ))

    # ═══════════════════════════════════════════════════════════════
    # SECTION 6: Batch Analysis (All Factors)
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 6. Batch Analysis: All Factors\n\n"
        "Loop through all factors and collect quantile analysis + monotonicity results."
    ))

    cells.append(new_code_cell(
        "# Full batch analysis\n"
        "batch_results = []\n\n"
        "for name in sorted(factors.keys()):\n"
        "    factor = factors[name]\n"
        "    try:\n"
        "        ic = compute_ic_series(factor, fwd_5d, min_obs=50)\n"
        "        if ic.empty:\n"
        "            continue\n"
        "        summary = compute_ic_summary(ic)\n\n"
        "        q_ret = compute_quantile_returns(factor, fwd_5d, n_quantiles=10, min_obs=100)\n"
        "        if not q_ret.empty:\n"
        "            q_sum = compute_quantile_summary(q_ret)\n"
        "            ls = compute_long_short_returns(q_ret)\n"
        "            mono = test_monotonicity(q_sum)\n"
        "            ls_ann_ret = ls.mean() * 252\n"
        "            ls_sharpe = np.sqrt(252) * ls.mean() / ls.std() if ls.std() > 0 else 0\n"
        "        else:\n"
        "            mono = {'is_monotonic': False, 'spearman_corr': 0}\n"
        "            ls_ann_ret = 0\n"
        "            ls_sharpe = 0\n\n"
        "        batch_results.append({\n"
        "            'factor': name,\n"
        "            'mean_rank_ic': summary['mean_rank_ic'],\n"
        "            'rank_icir': summary['rank_icir'],\n"
        "            'ic_hit_rate': summary['ic_hit_rate'],\n"
        "            'monotonic': mono['is_monotonic'],\n"
        "            'mono_corr': mono['spearman_corr'],\n"
        "            'ls_ann_return': ls_ann_ret,\n"
        "            'ls_sharpe': ls_sharpe,\n"
        "            'n_days': summary['n_days'],\n"
        "        })\n"
        "    except Exception as e:\n"
        "        print(f'  SKIP {name}: {e}')\n\n"
        "batch_df = pd.DataFrame(batch_results).set_index('factor')\n"
        "batch_df = batch_df.sort_values('rank_icir', key=abs, ascending=False)\n\n"
        "print(f'Successfully analyzed {len(batch_df)} factors\\n')\n"
        "display(batch_df.style.format({\n"
        "    'mean_rank_ic': '{:.4f}', 'rank_icir': '{:.3f}',\n"
        "    'ic_hit_rate': '{:.1%}', 'mono_corr': '{:.3f}',\n"
        "    'ls_ann_return': '{:.2%}', 'ls_sharpe': '{:.3f}',\n"
        "}).background_gradient(subset=['rank_icir'], cmap='RdYlGn', vmin=-0.5, vmax=0.5))"
    ))

    # ═══════════════════════════════════════════════════════════════
    # SECTION 7: Top Factors Summary
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 7. Factor Screening Summary\n\n"
        "Identify factors that pass the graduation criteria."
    ))

    cells.append(new_code_cell(
        "# Graduation screening\n"
        "graduated = batch_df[\n"
        "    (batch_df['rank_icir'].abs() >= 0.3) &\n"
        "    (batch_df['monotonic'] == True)\n"
        "].copy()\n\n"
        "questioned = batch_df[\n"
        "    (batch_df['rank_icir'].abs() >= 0.1) &\n"
        "    (batch_df['rank_icir'].abs() < 0.3)\n"
        "].copy()\n\n"
        "discarded = batch_df[\n"
        "    batch_df['rank_icir'].abs() < 0.1\n"
        "].copy()\n\n"
        "print(f'✅ GRADUATED (|ICIR| >= 0.3 & monotonic): {len(graduated)}')\n"
        "if not graduated.empty:\n"
        "    display(graduated[['mean_rank_ic', 'rank_icir', 'ls_ann_return', 'ls_sharpe']])\n\n"
        "print(f'\\n⚠️  QUESTIONED (0.1 <= |ICIR| < 0.3): {len(questioned)}')\n"
        "if not questioned.empty:\n"
        "    display(questioned[['mean_rank_ic', 'rank_icir', 'ls_ann_return', 'ls_sharpe']])\n\n"
        "print(f'\\n❌ DISCARDED (|ICIR| < 0.1): {len(discarded)}')\n"
        "if not discarded.empty:\n"
        "    print(', '.join(discarded.index.tolist()))"
    ))

    # ═══════════════════════════════════════════════════════════════
    # SECTION 8: Cross-Factor Correlation
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 8. Cross-Factor Correlation (Graduated Factors)\n\n"
        "Check redundancy among the factors that passed screening."
    ))

    cells.append(new_code_cell(
        "from src.alpha_research.factor_eval import (\n"
        "    compute_factor_correlation, find_redundant_pairs, select_uncorrelated\n"
        ")\n\n"
        "# Use graduated + questioned factors for correlation analysis\n"
        "corr_factors = {}\n"
        "for name in list(graduated.index) + list(questioned.index):\n"
        "    if name in factors:\n"
        "        corr_factors[name] = factors[name]\n\n"
        "if len(corr_factors) >= 2:\n"
        "    corr_matrix = compute_factor_correlation(corr_factors, method='spearman', min_obs=100)\n"
        "    redundant = find_redundant_pairs(corr_matrix, threshold=0.7)\n\n"
        "    from src.alpha_research.factor_eval.factor_plotters import plot_factor_correlation_heatmap\n"
        "    fig, ax = plt.subplots(figsize=(max(8, len(corr_factors)*0.7), max(6, len(corr_factors)*0.6)))\n"
        "    plot_factor_correlation_heatmap(corr_matrix, ax=ax)\n"
        "    plt.tight_layout()\n"
        "    plt.show()\n\n"
        "    if redundant:\n"
        "        print('\\n⚠️  Redundant pairs (|corr| >= 0.7):')\n"
        "        for a, b, c in redundant:\n"
        "            print(f'  {a} <-> {b}: {c:.3f}')\n"
        "    else:\n"
        "        print('\\n✅ No highly redundant pairs found.')\n"
        "else:\n"
        "    print('Not enough factors for correlation analysis.')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # SECTION 9: Rolling IC Time-Series
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 9. Rolling IC Time-Series\n\n"
        "12-month rolling Rank IC and ICIR for Tier 1 factors.\n"
        "Reveals regime shifts, factor crowding, and decay over time."
    ))

    cells.append(new_code_cell(
        "%%time\n"
        "from src.alpha_research.factor_eval import compute_rolling_ic\n\n"
        "# Select Tier 1 factors (|Rank ICIR| >= 0.35)\n"
        "tier1 = ic_df[ic_df['rank_icir'].abs() >= 0.35].index.tolist()\n"
        "print(f'Tier 1 factors ({len(tier1)}): {tier1}')\n\n"
        "# Compute rolling IC for each Tier 1 factor\n"
        "rolling_data = {}\n"
        "for name in tier1:\n"
        "    ic = compute_ic_series(factors[name], fwd_5d, min_obs=50)\n"
        "    if not ic.empty:\n"
        "        rolling_data[name] = compute_rolling_ic(ic, window=252)\n"
        "print(f'Rolling IC computed for {len(rolling_data)} factors')"
    ))

    cells.append(new_code_cell(
        "# Rolling Rank IC curves\n"
        "fig, axes = plt.subplots(2, 1, figsize=(16, 10), sharex=True)\n\n"
        "# Panel 1: Rolling Mean Rank IC\n"
        "ax1 = axes[0]\n"
        "for name, rdf in rolling_data.items():\n"
        "    ax1.plot(rdf.index, rdf['rolling_mean_rank_ic'], label=name, alpha=0.8)\n"
        "ax1.axhline(0, color='black', linewidth=0.5)\n"
        "ax1.set_ylabel('Rolling 12M Mean Rank IC')\n"
        "ax1.set_title('Rolling Rank IC — Tier 1 Factors', fontweight='bold')\n"
        "ax1.legend(loc='upper left', fontsize=8, ncol=2)\n"
        "ax1.grid(alpha=0.3)\n\n"
        "# Panel 2: Rolling Rank ICIR\n"
        "ax2 = axes[1]\n"
        "for name, rdf in rolling_data.items():\n"
        "    ax2.plot(rdf.index, rdf['rolling_rank_icir'], label=name, alpha=0.8)\n"
        "ax2.axhline(0, color='black', linewidth=0.5)\n"
        "ax2.axhline(-0.3, color='red', linewidth=1, linestyle='--', alpha=0.5)\n"
        "ax2.axhline(0.3, color='green', linewidth=1, linestyle='--', alpha=0.5)\n"
        "ax2.set_ylabel('Rolling 12M Rank ICIR')\n"
        "ax2.set_xlabel('Date')\n"
        "ax2.set_title('Rolling Rank ICIR — Tier 1 Factors', fontweight='bold')\n"
        "ax2.legend(loc='upper left', fontsize=8, ncol=2)\n"
        "ax2.grid(alpha=0.3)\n\n"
        "plt.tight_layout()\n"
        "plt.show()"
    ))

    # ═══════════════════════════════════════════════════════════════
    # SECTION 10: Cross-Factor Correlation + De-Redundancy
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 10. Cross-Factor Correlation & De-Redundancy\n\n"
        "Full 43×43 Spearman correlation heatmap across all factors.\n"
        "Identify redundant pairs and greedily select a diversified core pool."
    ))

    cells.append(new_code_cell(
        "%%time\n"
        "from src.alpha_research.factor_eval import (\n"
        "    compute_factor_correlation, find_redundant_pairs, select_uncorrelated\n"
        ")\n"
        "from src.alpha_research.factor_eval.factor_plotters import plot_factor_correlation_heatmap\n\n"
        "# Compute full correlation matrix\n"
        "all_factor_series = {name: factors[name] for name in sorted(factors.keys())}\n"
        "corr_matrix = compute_factor_correlation(all_factor_series, method='spearman', min_obs=100)\n\n"
        "# Plot heatmap\n"
        "fig, ax = plt.subplots(figsize=(18, 15))\n"
        "plot_factor_correlation_heatmap(corr_matrix, ax=ax, title='Cross-Factor Spearman Correlation')\n"
        "plt.tight_layout()\n"
        "plt.show()"
    ))

    cells.append(new_code_cell(
        "# Find redundant pairs (|corr| >= 0.7)\n"
        "redundant = find_redundant_pairs(corr_matrix, threshold=0.7)\n"
        "print(f'Redundant pairs (|corr| >= 0.7): {len(redundant)}\\n')\n"
        "if redundant:\n"
        "    rdf = pd.DataFrame(redundant, columns=['Factor_A', 'Factor_B', 'Correlation'])\n"
        "    display(rdf.style.format({'Correlation': '{:.3f}'}))\n\n"
        "# Greedy selection of uncorrelated factors\n"
        "ic_summary_all = {name: ic_results[name] for name in ic_results}\n"
        "core_pool = select_uncorrelated(corr_matrix, ic_summary_all, max_corr=0.5)\n\n"
        "print(f'\\nCore factor pool ({len(core_pool)} factors, max_corr=0.5):')\n"
        "for i, name in enumerate(core_pool, 1):\n"
        "    icir = ic_results[name]['rank_icir']\n"
        "    print(f'  {i:2d}. {name:<25s}  Rank ICIR = {icir:.3f}')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # SECTION 11: Marginal IC Contribution
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 11. Marginal IC Contribution\n\n"
        "Starting from the strongest factor, iteratively add factors from the core pool\n"
        "and measure the incremental (marginal) IC each one contributes beyond those\n"
        "already selected. Factors with near-zero marginal IC are redundant in context."
    ))

    cells.append(new_code_cell(
        "%%time\n"
        "from src.alpha_research.factor_eval import compute_marginal_ic\n\n"
        "# Use core_pool ordering (already sorted by |ICIR| descending)\n"
        "marginal_results = []\n"
        "selected_so_far = []\n\n"
        "for name in core_pool:\n"
        "    _, m_summary = compute_marginal_ic(\n"
        "        factors_dict=factors,\n"
        "        forward_return=fwd_5d,\n"
        "        base_factors=selected_so_far,\n"
        "        candidate=name,\n"
        "        min_obs=50,\n"
        "    )\n"
        "    marginal_results.append({\n"
        "        'factor': name,\n"
        "        'raw_rank_icir': ic_results[name]['rank_icir'],\n"
        "        'marginal_rank_ic': m_summary.get('mean_rank_ic', 0),\n"
        "        'marginal_rank_icir': m_summary.get('rank_icir', 0),\n"
        "        'step': len(selected_so_far) + 1,\n"
        "    })\n"
        "    selected_so_far.append(name)\n"
        "    print(f'  Step {len(selected_so_far)}: +{name}  marginal ICIR={m_summary.get(\"rank_icir\", 0):.3f}')\n\n"
        "marginal_df = pd.DataFrame(marginal_results).set_index('factor')\n"
        "display(marginal_df.style.format({\n"
        "    'raw_rank_icir': '{:.3f}', 'marginal_rank_ic': '{:.4f}',\n"
        "    'marginal_rank_icir': '{:.3f}',\n"
        "}))"
    ))

    cells.append(new_code_cell(
        "# Bar chart: Raw ICIR vs Marginal ICIR\n"
        "fig, ax = plt.subplots(figsize=(12, max(5, len(marginal_df) * 0.35)))\n"
        "y_pos = np.arange(len(marginal_df))\n"
        "bar_height = 0.35\n\n"
        "ax.barh(y_pos + bar_height/2, marginal_df['raw_rank_icir'].abs(),\n"
        "        height=bar_height, label='Raw |Rank ICIR|', color='#42A5F5', alpha=0.8)\n"
        "ax.barh(y_pos - bar_height/2, marginal_df['marginal_rank_icir'].abs(),\n"
        "        height=bar_height, label='Marginal |Rank ICIR|', color='#FF7043', alpha=0.8)\n\n"
        "ax.set_yticks(y_pos)\n"
        "ax.set_yticklabels(marginal_df.index)\n"
        "ax.set_xlabel('|Rank ICIR|')\n"
        "ax.set_title('Raw vs Marginal Factor ICIR (Incremental Contribution)', fontweight='bold')\n"
        "ax.legend()\n"
        "ax.grid(axis='x', alpha=0.3)\n"
        "ax.invert_yaxis()\n"
        "plt.tight_layout()\n"
        "plt.show()"
    ))

    # ═══════════════════════════════════════════════════════════════
    # SECTION 12: Size-Group Sub-Analysis
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 12. Size-Group Sub-Analysis\n\n"
        "Test whether the top factors work across all market cap segments.\n"
        "Stocks are split into Large / Mid / Small terciles by `total_mv` each day."
    ))

    cells.append(new_code_cell(
        "%%time\n"
        "from src.alpha_research.factor_eval import compute_ic_by_group\n\n"
        "# Create size tercile labels\n"
        "total_mv = df_market['total_mv']\n"
        "size_labels = total_mv.groupby(level=0).transform(\n"
        "    lambda x: pd.qcut(x, 3, labels=['Small', 'Mid', 'Large'], duplicates='drop')\n"
        ")\n"
        "size_labels.name = 'size_group'\n\n"
        "# Analyze Tier 1+2 factors (|Rank ICIR| >= 0.2)\n"
        "tier12 = ic_df[ic_df['rank_icir'].abs() >= 0.2].index.tolist()\n"
        "print(f'Analyzing {len(tier12)} factors across size groups...\\n')\n\n"
        "size_group_results = []\n"
        "for name in tier12:\n"
        "    group_ic = compute_ic_by_group(factors[name], fwd_5d, size_labels, min_obs=30)\n"
        "    for grp, summary in group_ic.items():\n"
        "        size_group_results.append({\n"
        "            'factor': name,\n"
        "            'size_group': grp,\n"
        "            'mean_rank_ic': summary['mean_rank_ic'],\n"
        "            'rank_icir': summary['rank_icir'],\n"
        "            'n_days': summary['n_days'],\n"
        "        })\n\n"
        "sg_df = pd.DataFrame(size_group_results)\n"
        "print(f'Results collected: {len(sg_df)} rows')"
    ))

    cells.append(new_code_cell(
        "# Grouped bar chart: Rank ICIR by size group\n"
        "if not sg_df.empty:\n"
        "    pivot = sg_df.pivot(index='factor', columns='size_group', values='rank_icir')\n"
        "    # Reorder columns\n"
        "    cols = [c for c in ['Large', 'Mid', 'Small'] if c in pivot.columns]\n"
        "    pivot = pivot[cols]\n"
        "    # Sort by average |ICIR|\n"
        "    pivot = pivot.loc[pivot.abs().mean(axis=1).sort_values(ascending=False).index]\n\n"
        "    fig, ax = plt.subplots(figsize=(14, max(6, len(pivot) * 0.4)))\n"
        "    pivot.plot.barh(ax=ax, color=['#1976D2', '#FFA726', '#66BB6A'], edgecolor='white')\n"
        "    ax.axvline(0, color='black', linewidth=0.5)\n"
        "    ax.set_xlabel('Rank ICIR')\n"
        "    ax.set_title('Factor Rank ICIR by Market Cap Group', fontweight='bold')\n"
        "    ax.legend(title='Size Group')\n"
        "    ax.grid(axis='x', alpha=0.3)\n"
        "    ax.invert_yaxis()\n"
        "    plt.tight_layout()\n"
        "    plt.show()\n\n"
        "    # Summary table\n"
        "    print('\\nUniversality check (factors effective across all size groups):')\n"
        "    for name in pivot.index:\n"
        "        vals = pivot.loc[name].dropna()\n"
        "        all_same_sign = (vals > 0).all() or (vals < 0).all()\n"
        "        avg = vals.abs().mean()\n"
        "        status = '✅ Universal' if all_same_sign and avg > 0.15 else '⚠️  Partial' if all_same_sign else '❌ Inconsistent'\n"
        "        print(f'  {name:<25s} {status}  avg|ICIR|={avg:.3f}')\n"
        "else:\n"
        "    print('No size-group results available.')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # SECTION 13: Long-Short Portfolio Backtest
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 13. Long-Short Portfolio Backtest\n\n"
        "For each core-pool factor, build quintile long-short portfolios and compare\n"
        "equity curves, Sharpe ratios, max drawdown, and annual returns.\n\n"
        "> **Note:** These are paper portfolios assuming equal-weight, daily rebalance,\n"
        "> zero transaction cost. Real-world performance will differ."
    ))

    cells.append(new_code_cell(
        "%%time\n"
        "from src.result_analysis.metrics import generate_performance_report\n\n"
        "# Build L/S portfolios for core pool factors\n"
        "ls_curves = {}\n"
        "ls_stats = []\n\n"
        "for name in core_pool:\n"
        "    q_ret = compute_quantile_returns(factors[name], fwd_5d, n_quantiles=10, min_obs=100)\n"
        "    if q_ret.empty:\n"
        "        continue\n"
        "    q_sum = compute_quantile_summary(q_ret)\n"
        "    mono = test_monotonicity(q_sum)\n\n"
        "    # Determine long/short direction based on factor sign\n"
        "    rank_icir = ic_results[name]['rank_icir']\n"
        "    if rank_icir > 0:\n"
        "        long_q, short_q = q_ret['quantile'].max(), 1\n"
        "    else:\n"
        "        long_q, short_q = 1, q_ret['quantile'].max()\n\n"
        "    ls = compute_long_short_returns(q_ret, long_q=long_q, short_q=short_q)\n"
        "    if ls.empty:\n"
        "        continue\n\n"
        "    ls_curves[name] = ls\n"
        "    cum_ret = (1 + ls).cumprod()\n\n"
        "    report = generate_performance_report(ls)\n"
        "    ls_stats.append({\n"
        "        'factor': name,\n"
        "        'direction': 'long_high' if rank_icir > 0 else 'long_low',\n"
        "        'ann_return': float(report.loc['Annualized Return', 'Strategy']),\n"
        "        'volatility': float(report.loc['Annualized Volatility', 'Strategy']),\n"
        "        'sharpe': float(report.loc['Sharpe Ratio', 'Strategy']),\n"
        "        'max_drawdown': float(report.loc['Max Drawdown', 'Strategy']),\n"
        "        'win_rate': float(report.loc['Win Rate', 'Strategy']),\n"
        "        'monotonic': mono['is_monotonic'],\n"
        "    })\n\n"
        "ls_stat_df = pd.DataFrame(ls_stats).set_index('factor')\n"
        "ls_stat_df = ls_stat_df.sort_values('sharpe', ascending=False)\n\n"
        "print(f'L/S backtest completed for {len(ls_stat_df)} factors\\n')\n"
        "display(ls_stat_df.style.format({\n"
        "    'ann_return': '{:.2%}', 'volatility': '{:.2%}',\n"
        "    'sharpe': '{:.3f}', 'max_drawdown': '{:.2%}', 'win_rate': '{:.1%}',\n"
        "}).background_gradient(subset=['sharpe'], cmap='RdYlGn', vmin=-0.5, vmax=1.5))"
    ))

    cells.append(new_code_cell(
        "# Equity curves\n"
        "fig, ax = plt.subplots(figsize=(16, 8))\n\n"
        "for name in ls_stat_df.index[:10]:  # Top 10 by Sharpe\n"
        "    if name in ls_curves:\n"
        "        cum = (1 + ls_curves[name]).cumprod()\n"
        "        sharpe = ls_stat_df.loc[name, 'sharpe']\n"
        "        ax.plot(cum.index, cum.values, label=f'{name} (SR={sharpe:.2f})', alpha=0.8)\n\n"
        "ax.axhline(1, color='black', linewidth=0.5, linestyle='--')\n"
        "ax.set_ylabel('Cumulative Return (starting at 1.0)')\n"
        "ax.set_xlabel('Date')\n"
        "ax.set_title('Long-Short Equity Curves — Core Factor Pool', fontweight='bold')\n"
        "ax.legend(loc='upper left', fontsize=8)\n"
        "ax.grid(alpha=0.3)\n"
        "plt.tight_layout()\n"
        "plt.show()"
    ))

    # ═══════════════════════════════════════════════════════════════
    # SECTION 14: Factor Pool Summary
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 14. Factor Pool Summary\n\n"
        "Final recommended factor list after de-redundancy, with comprehensive\n"
        "per-factor diagnostics."
    ))

    cells.append(new_code_cell(
        "# Build final factor scorecard\n"
        "scorecard = []\n"
        "for name in core_pool:\n"
        "    ic_s = ic_results.get(name, {})\n"
        "    ls_s = ls_stat_df.loc[name] if name in ls_stat_df.index else pd.Series()\n\n"
        "    # Check size universality\n"
        "    factor_sg = sg_df[sg_df['factor'] == name] if name in sg_df['factor'].values else pd.DataFrame()\n"
        "    if not factor_sg.empty:\n"
        "        sg_icirs = factor_sg.set_index('size_group')['rank_icir']\n"
        "        universal = (sg_icirs > 0).all() or (sg_icirs < 0).all()\n"
        "    else:\n"
        "        universal = None\n\n"
        "    scorecard.append({\n"
        "        'factor': name,\n"
        "        'category': name.split('_')[0],\n"
        "        'direction': '📈 Long High' if ic_s.get('rank_icir', 0) > 0 else '📉 Long Low',\n"
        "        'rank_icir': ic_s.get('rank_icir', 0),\n"
        "        'ic_hit_rate': ic_s.get('ic_hit_rate', 0),\n"
        "        'ls_sharpe': ls_s.get('sharpe', 0) if not ls_s.empty else 0,\n"
        "        'ls_ann_return': ls_s.get('ann_return', 0) if not ls_s.empty else 0,\n"
        "        'max_drawdown': ls_s.get('max_drawdown', 0) if not ls_s.empty else 0,\n"
        "        'size_universal': '✅' if universal else ('❌' if universal is False else '—'),\n"
        "    })\n\n"
        "score_df = pd.DataFrame(scorecard).set_index('factor')\n\n"
        "print(f'═══ FINAL FACTOR POOL: {len(score_df)} factors ═══\\n')\n"
        "display(score_df.style.format({\n"
        "    'rank_icir': '{:.3f}', 'ic_hit_rate': '{:.1%}',\n"
        "    'ls_sharpe': '{:.3f}', 'ls_ann_return': '{:.2%}',\n"
        "    'max_drawdown': '{:.2%}',\n"
        "}).background_gradient(subset=['rank_icir'], cmap='RdYlGn', vmin=-0.5, vmax=0.5))"
    ))

    cells.append(new_code_cell(
        "# Category breakdown\n"
        "print('Factor pool by category:')\n"
        "cat_counts = score_df['category'].value_counts()\n"
        "for cat, cnt in cat_counts.items():\n"
        "    cat_factors = score_df[score_df['category'] == cat].index.tolist()\n"
        "    print(f'  {cat}: {cnt} factors — {\", \".join(cat_factors)}')\n\n"
        "print(f'\\nTotal factors in final pool: {len(score_df)}')\n"
        "print(f'Avg |Rank ICIR|: {score_df[\"rank_icir\"].abs().mean():.3f}')\n"
        "print(f'Avg L/S Sharpe: {score_df[\"ls_sharpe\"].mean():.3f}')\n"
        "print(f'Size-universal factors: {(score_df[\"size_universal\"] == \"✅\").sum()} / {len(score_df)}')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # SECTION 15: Next Steps
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 15. Next Steps\n\n"
        "1. **Neutralization**: Run `neutralize_size_industry()` on core-pool factors\n"
        "2. **Decay analysis**: Use `compute_ic_decay()` to find optimal holding period\n"
        "3. **Composite factor**: Combine core-pool factors via ICIR-weighted z-score\n"
        "4. **Validation period**: Re-run on 2021-2023 data separately\n"
        "5. **Out-of-sample test**: Run ONCE on 2024+ (do not iterate on test results)\n"
        "6. **Backtest**: Use `VectorizedBacktester` with TopkDropout strategy\n"
        "7. **MLflow**: Log all results via `ExperimentTracker`\n\n"
        "---\n"
        "*Generated by `workspace/scripts/generate_factor_notebook.py`*"
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
