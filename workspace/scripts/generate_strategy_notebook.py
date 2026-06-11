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
Generate Multi-Factor Strategy Jupyter Notebook

Programmatically creates a comprehensive notebook that takes the 8
selected factors from the screening stage and performs:
  §1 Load selected factors
  §2 Neutralization (size + industry)
  §3 IC Decay analysis
  §4 Composite factor construction
  §5 Temporal validation (train / val)
  §6 Out-of-sample test (2024+)
  §7 Backtest with VectorizedBacktester
  §8 MLflow logging

Usage:
    python workspace/scripts/generate_strategy_notebook.py

Output:
    workspace/research/alpha_factors/multi_factor_strategy.ipynb
"""

import os
import sys
import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "workspace", "research", "alpha_factors")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "multi_factor_strategy.ipynb")


def make_notebook():
    """Build the multi-factor strategy notebook."""
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
        "# Multi-Factor Strategy Notebook\n\n"
        "End-to-end pipeline from factor neutralization to Qlib backtest.\n\n"
        "**Selected Factor Pool (8 factors):**\n\n"
        "| Factor | Category | Direction | Raw ICIR | Marginal ICIR | L/S Sharpe |\n"
        "|--------|----------|-----------|----------|---------------|------------|\n"
        "| `liq_vol_cv` | Liquidity | Long Low | −0.628 | −0.628 | 5.72 |\n"
        "| `liq_log_dollar_vol` | Liquidity | Long Low | −0.505 | −0.455 | 4.75 |\n"
        "| `liq_turnover_ratio` | Liquidity | Long Low | −0.354 | −0.234 | 2.51 |\n"
        "| `mom_return_20d` | Momentum | Long Low | −0.367 | −0.220 | 3.20 |\n"
        "| `mom_overnight_20d` | Momentum | Long High | +0.138 | +0.338 | 0.70 |\n"
        "| `tech_reversal_5d` | Technical | Long High | +0.294 | +0.203 | 2.78 |\n"
        "| `tech_skew_20d` | Technical | Long Low | −0.464 | −0.210 | 2.84 |\n"
        "| `val_bp` | Value | Long High | +0.221 | +0.103 | 1.43 |\n\n"
        "**Research Integrity:**\n"
        "- Temporal split: Train 2012–2020 | Validation 2021–2023 | Test 2024+\n"
        "- Test period run ONCE — results logged before any adjustment\n"
        "- Universe: `all_stocks` (includes delisted)\n"
        "- PIT-aligned fundamentals, `shift(1)` leakage guard\n\n"
        "---"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §1: ENVIRONMENT + LOAD SELECTED FACTORS
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
        "import seaborn as sns\n"
        "from IPython.display import display, HTML\n\n"
        "# Qlib initialization\n"
        "import qlib\n"
        "from qlib.data import D\n"
        "from qlib.config import REG_CN\n\n"
        "QLIB_DIR = os.path.join(PROJECT_ROOT, 'data', 'qlib_data')\n"
        "qlib.init(provider_uri=QLIB_DIR, region=REG_CN)\n"
        "print('Qlib initialized')\n\n"
        "# Import factor_eval + backtest\n"
        "from src.alpha_research.factor_eval import (\n"
        "    compute_ic_series, compute_ic_summary, compute_ic_by_year,\n"
        "    compute_quantile_returns, compute_quantile_summary,\n"
        "    compute_long_short_returns, test_monotonicity,\n"
        "    compute_rolling_ic, compute_marginal_ic,\n"
        "    neutralize_size_industry,\n"
        ")\n"
        "from src.alpha_research.factor_eval.decay_analysis import compute_ic_decay, find_optimal_horizon\n"
        "from src.alpha_research.factor_eval.factor_plotters import (\n"
        "    plot_factor_report, plot_ic_decay,\n"
        ")\n"
        "from src.result_analysis.metrics import generate_performance_report\n\n"
        "print('Libraries loaded')"
    ))

    cells.append(new_code_cell(
        "# ─── TEMPORAL SPLIT ────────────────────────────────────\n"
        "TRAIN_START = '2012-01-01'\n"
        "TRAIN_END   = '2020-12-31'\n"
        "VAL_START   = '2021-01-01'\n"
        "VAL_END     = '2023-12-31'\n"
        "TEST_START  = '2024-01-01'\n"
        "TEST_END    = '2025-12-31'\n\n"
        "FULL_START  = TRAIN_START\n"
        "FULL_END    = TEST_END\n\n"
        "# ─── SELECTED FACTORS ──────────────────────────────────\n"
        "SELECTED_FACTORS = [\n"
        "    'liq_vol_cv', 'liq_log_dollar_vol', 'liq_turnover_ratio',\n"
        "    'mom_return_20d', 'mom_overnight_20d',\n"
        "    'tech_reversal_5d', 'tech_skew_20d',\n"
        "    'val_bp',\n"
        "]\n\n"
        "# Factor directions: +1 = long high, -1 = long low\n"
        "FACTOR_DIRECTION = {\n"
        "    'liq_vol_cv': -1, 'liq_log_dollar_vol': -1, 'liq_turnover_ratio': -1,\n"
        "    'mom_return_20d': -1, 'mom_overnight_20d': +1,\n"
        "    'tech_reversal_5d': +1, 'tech_skew_20d': -1,\n"
        "    'val_bp': +1,\n"
        "}\n\n"
        "# Factor ICIR weights (from full-period screening)\n"
        "FACTOR_ICIR = {\n"
        "    'liq_vol_cv': -0.628, 'liq_log_dollar_vol': -0.505,\n"
        "    'liq_turnover_ratio': -0.354,\n"
        "    'mom_return_20d': -0.367, 'mom_overnight_20d': +0.138,\n"
        "    'tech_reversal_5d': +0.294, 'tech_skew_20d': -0.464,\n"
        "    'val_bp': +0.221,\n"
        "}\n\n"
        "print(f'Selected factors: {len(SELECTED_FACTORS)}')\n"
        "print(f'Date range: {FULL_START} → {FULL_END}')\n"
        "print(f'Train: {TRAIN_START}–{TRAIN_END} | Val: {VAL_START}–{VAL_END} | Test: {TEST_START}–{TEST_END}')"
    ))

    cells.append(new_code_cell(
        "# ─── LOAD MARKET DATA ──────────────────────────────────\n"
        "instruments = D.instruments(market='all_stocks')\n\n"
        "market_fields = [\n"
        "    '$close', '$open', '$high', '$low',\n"
        "    '$vol', '$amount', '$pct_chg',\n"
        "    '$turnover_rate', '$volume_ratio',\n"
        "    '$pe_ttm', '$pb', '$ps_ttm',\n"
        "    '$dv_ttm', '$total_mv', '$circ_mv',\n"
        "    '$adj_factor',\n"
        "]\n\n"
        "print(f'Loading market data...')\n"
        "df_market = D.features(instruments, market_fields, start_time=FULL_START, end_time=FULL_END)\n"
        "df_market.columns = [c.lstrip('$') for c in df_market.columns]\n"
        "df_market = df_market.swaplevel().sort_index()\n\n"
        "# Adjusted close & returns\n"
        "adj_close = df_market['close'] * df_market['adj_factor']\n"
        "adj_close.name = 'adj_close'\n"
        "daily_ret = adj_close.groupby(level=1).pct_change()\n"
        "daily_ret.name = 'daily_return'\n\n"
        "# Forward returns\n"
        "fwd_1d  = adj_close.groupby(level=1).shift(-1) / adj_close - 1\n"
        "fwd_5d  = adj_close.groupby(level=1).shift(-5) / adj_close - 1\n"
        "fwd_10d = adj_close.groupby(level=1).shift(-10) / adj_close - 1\n"
        "fwd_20d = adj_close.groupby(level=1).shift(-20) / adj_close - 1\n\n"
        "print(f'Market data: {df_market.shape}')\n"
        "print(f'Date range: {df_market.index.get_level_values(0).min()} – {df_market.index.get_level_values(0).max()}')"
    ))

    cells.append(new_code_cell(
        "# ─── COMPUTE SELECTED FACTORS ──────────────────────────\n"
        "factors = {}\n\n"
        "# Liquidity\n"
        "vol_mean = df_market['vol'].groupby(level=1).transform(lambda x: x.rolling(20).mean())\n"
        "vol_std  = df_market['vol'].groupby(level=1).transform(lambda x: x.rolling(20).std())\n"
        "factors['liq_vol_cv'] = vol_std / vol_mean.replace(0, np.nan)\n\n"
        "factors['liq_log_dollar_vol'] = np.log(\n"
        "    (df_market['amount'] * 1000).groupby(level=1).transform(lambda x: x.rolling(20).mean()).replace(0, np.nan)\n"
        ")\n\n"
        "factors['liq_turnover_ratio'] = (\n"
        "    df_market['turnover_rate'].groupby(level=1).transform(lambda x: x.rolling(5).mean()) /\n"
        "    df_market['turnover_rate'].groupby(level=1).transform(lambda x: x.rolling(60).mean()).replace(0, np.nan)\n"
        ")\n\n"
        "# Momentum\n"
        "factors['mom_return_20d'] = adj_close / adj_close.groupby(level=1).shift(20) - 1\n\n"
        "adj_open = df_market['open'] * df_market['adj_factor']\n"
        "overnight = adj_open / adj_close.groupby(level=1).shift(1) - 1\n"
        "factors['mom_overnight_20d'] = overnight.groupby(level=1).transform(lambda x: x.rolling(20).mean())\n\n"
        "# Technical\n"
        "factors['tech_reversal_5d'] = -(adj_close / adj_close.groupby(level=1).shift(5) - 1)\n\n"
        "factors['tech_skew_20d'] = daily_ret.groupby(level=1).transform(lambda x: x.rolling(20).skew())\n\n"
        "# Value\n"
        "factors['val_bp'] = 1.0 / df_market['pb'].replace(0, np.nan)\n\n"
        "# Apply shift(1) to prevent same-day leakage\n"
        "for name in factors:\n"
        "    factors[name] = factors[name].groupby(level=1).shift(1)\n\n"
        "print(f'Factors computed: {len(factors)}')\n"
        "print('Coverage (non-NaN %):')\n"
        "coverage = pd.Series({k: 1 - v.isna().mean() for k, v in factors.items()}).sort_values()\n"
        "print(coverage.to_string())"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §2: NEUTRALIZATION
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 2. Neutralization (Size + Industry)\n\n"
        "Remove market-cap and Shenwan L1 industry exposures from each factor.\n"
        "Compare raw vs neutralized IC to decide which version to keep."
    ))

    cells.append(new_code_cell(
        "%%time\n"
        "# Load Shenwan L1 industry labels\n"
        "import glob\n\n"
        "# Try known paths (the file may be in a subdirectory)\n"
        "industry_candidates = [\n"
        "    os.path.join(PROJECT_ROOT, 'data', 'universe', 'industry_sw2021', 'industry_sw2021.parquet'),\n"
        "    os.path.join(PROJECT_ROOT, 'data', 'universe', 'industry_sw2021.parquet'),\n"
        "]\n"
        "# Fallback: glob search\n"
        "industry_candidates += glob.glob(os.path.join(PROJECT_ROOT, 'data', '**', '*industry*sw*.parquet'), recursive=True)\n\n"
        "industry_path = None\n"
        "for candidate in industry_candidates:\n"
        "    if os.path.exists(candidate):\n"
        "        industry_path = candidate\n"
        "        break\n\n"
        "if industry_path is None:\n"
        "    raise FileNotFoundError(f'Could not find industry_sw2021.parquet. Searched: {industry_candidates}')\n\n"
        "print(f'Industry file: {industry_path}')\n"
        "df_ind = pd.read_parquet(industry_path)\n"
        "print(f'Industry data shape: {df_ind.shape}')\n"
        "print(f'Columns: {df_ind.columns.tolist()}')\n"
        "print(f'Unique L1 industries: {df_ind[\"industry_name\"].nunique()}')"
    ))

    cells.append(new_code_cell(
        "%%time\n"
        "from src.alpha_research.factor_eval import neutralize_size_industry\n\n"
        "# ─── Tushare→Qlib ts_code converter ───────────────────\n"
        "# Tushare: '000001.SZ' → Qlib: '000001_SZ' (underscore, code first)\n"
        "def _tushare_to_qlib(ts_code):\n"
        "    return ts_code.replace('.', '_')\n\n"
        "# Load stock_basic for industry mapping\n"
        "stock_basic = pd.read_parquet(os.path.join(PROJECT_ROOT, 'data', 'reference', 'stock_basic.parquet'))\n"
        "stock_basic['qlib_code'] = stock_basic['ts_code'].apply(_tushare_to_qlib)\n"
        "industry_map = stock_basic.set_index('qlib_code')['industry'].to_dict()\n\n"
        "# Map to our MultiIndex (level 1 = instrument in Qlib format)\n"
        "industry_labels = df_market.index.get_level_values(1).map(\n"
        "    lambda x: industry_map.get(x, 'Unknown')\n"
        ")\n"
        "industry_series = pd.Series(industry_labels.values, index=df_market.index, name='industry')\n\n"
        "# Market cap for size neutralization\n"
        "market_cap = df_market['total_mv']\n\n"
        "print(f'Industry coverage: {(industry_series != \"Unknown\").mean():.1%}')\n"
        "print(f'Unique industries: {industry_series.nunique()}')\n"
        "print(f'\\nTop 10 industries:')\n"
        "print(industry_series[industry_series != 'Unknown'].value_counts().head(10))"
    ))

    cells.append(new_code_cell(
        "%%time\n"
        "# Neutralize all 8 factors\n"
        "factors_neutral = {}\n"
        "neutral_comparison = []\n\n"
        "for name in SELECTED_FACTORS:\n"
        "    print(f'  Neutralizing {name}...')\n"
        "    try:\n"
        "        factors_neutral[name] = neutralize_size_industry(\n"
        "            factors[name], market_cap, industry_series, min_obs=50\n"
        "        )\n"
        "    except Exception as e:\n"
        "        print(f'    FAILED: {e}')\n"
        "        factors_neutral[name] = factors[name]  # fallback to raw\n\n"
        "    # Compare raw vs neutralized IC\n"
        "    ic_raw = compute_ic_series(factors[name], fwd_5d, min_obs=50)\n"
        "    ic_neu = compute_ic_series(factors_neutral[name], fwd_5d, min_obs=50)\n"
        "    sum_raw = compute_ic_summary(ic_raw) if not ic_raw.empty else {}\n"
        "    sum_neu = compute_ic_summary(ic_neu) if not ic_neu.empty else {}\n\n"
        "    neutral_comparison.append({\n"
        "        'factor': name,\n"
        "        'raw_rank_icir': sum_raw.get('rank_icir', 0),\n"
        "        'neutral_rank_icir': sum_neu.get('rank_icir', 0),\n"
        "        'raw_ic_hit': sum_raw.get('ic_hit_rate', 0),\n"
        "        'neutral_ic_hit': sum_neu.get('ic_hit_rate', 0),\n"
        "    })\n\n"
        "nc_df = pd.DataFrame(neutral_comparison).set_index('factor')\n"
        "nc_df['delta_icir'] = nc_df['neutral_rank_icir'].abs() - nc_df['raw_rank_icir'].abs()\n"
        "nc_df['use_neutral'] = nc_df['delta_icir'] > 0\n\n"
        "print('\\n=== Raw vs Neutralized IC ===')\n"
        "display(nc_df.style.format({\n"
        "    'raw_rank_icir': '{:.3f}', 'neutral_rank_icir': '{:.3f}',\n"
        "    'raw_ic_hit': '{:.1%}', 'neutral_ic_hit': '{:.1%}',\n"
        "    'delta_icir': '{:+.3f}',\n"
        "}))"
    ))

    cells.append(new_code_cell(
        "# Apply best version for each factor\n"
        "factors_best = {}\n"
        "for name in SELECTED_FACTORS:\n"
        "    if nc_df.loc[name, 'use_neutral']:\n"
        "        factors_best[name] = factors_neutral[name]\n"
        "        status = 'NEUTRALIZED'\n"
        "    else:\n"
        "        factors_best[name] = factors[name]\n"
        "        status = 'RAW'\n"
        "    print(f'  {name:<25s} → {status}')\n\n"
        "print(f'\\nUsing neutralized: {nc_df[\"use_neutral\"].sum()} / {len(SELECTED_FACTORS)}')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §3: IC DECAY ANALYSIS
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 3. IC Decay Analysis\n\n"
        "Determine optimal forward-return horizon for each factor.\n"
        "This informs the rebalance frequency for the composite strategy."
    ))

    cells.append(new_code_cell(
        "%%time\n"
        "# Compute IC decay for each factor\n"
        "decay_results = {}\n"
        "optimal_horizons = []\n\n"
        "for name in SELECTED_FACTORS:\n"
        "    print(f'  Decay analysis: {name}...')\n"
        "    decay_df = compute_ic_decay(\n"
        "        factors_best[name], adj_close,\n"
        "        horizons=[1, 2, 3, 5, 10, 20, 40, 60],\n"
        "        min_obs=50,\n"
        "    )\n"
        "    decay_results[name] = decay_df\n"
        "    opt = find_optimal_horizon(decay_df)\n"
        "    optimal_horizons.append({\n"
        "        'factor': name,\n"
        "        'best_horizon_icir': opt['best_horizon_icir'],\n"
        "        'peak_icir': opt['peak_icir'],\n"
        "        'half_life': opt['half_life'],\n"
        "    })\n\n"
        "opt_df = pd.DataFrame(optimal_horizons).set_index('factor')\n"
        "display(opt_df.style.format({'peak_icir': '{:.3f}'}))"
    ))

    cells.append(new_code_cell(
        "# Plot IC decay curves\n"
        "fig, axes = plt.subplots(2, 4, figsize=(20, 8))\n"
        "axes = axes.flatten()\n\n"
        "for i, name in enumerate(SELECTED_FACTORS):\n"
        "    ax = axes[i]\n"
        "    decay = decay_results[name]\n"
        "    ax.bar(range(len(decay)), decay['rank_icir'].values, color='steelblue', alpha=0.7)\n"
        "    ax.set_xticks(range(len(decay)))\n"
        "    ax.set_xticklabels(decay.index, fontsize=8)\n"
        "    ax.set_title(name, fontsize=10, fontweight='bold')\n"
        "    ax.set_ylabel('Rank ICIR')\n"
        "    ax.set_xlabel('Horizon (days)')\n"
        "    ax.axhline(0, color='black', linewidth=0.5)\n"
        "    ax.grid(axis='y', alpha=0.3)\n\n"
        "plt.suptitle('IC Decay by Forward Return Horizon', fontsize=14, fontweight='bold')\n"
        "plt.tight_layout()\n"
        "plt.show()\n\n"
        "# Determine rebalance frequency\n"
        "median_horizon = int(opt_df['best_horizon_icir'].median())\n"
        "print(f'\\nMedian optimal horizon: {median_horizon} days')\n"
        "print(f'Recommended rebalance frequency: every {median_horizon} trading days')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §4: COMPOSITE FACTOR
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 4. Composite Factor Construction\n\n"
        "Combine the 8 factors via ICIR-weighted z-score:\n\n"
        "$$\\text{composite}(t) = \\sum_i \\text{sign}(\\text{ICIR}_i) \\cdot |\\text{ICIR}_i| \\cdot \\text{zscore}(\\text{factor}_i(t))$$\n\n"
        "The sign ensures all factors point in the 'long high = good' direction."
    ))

    cells.append(new_code_cell(
        "%%time\n"
        "# Cross-sectional z-score each factor\n"
        "zscores = {}\n"
        "for name in SELECTED_FACTORS:\n"
        "    f = factors_best[name]\n"
        "    # Per-date z-score (cross-sectional)\n"
        "    z = f.groupby(level=0).transform(lambda x: (x - x.mean()) / x.std())\n"
        "    # Clip outliers\n"
        "    z = z.clip(-3, 3)\n"
        "    zscores[name] = z\n\n"
        "# ICIR-weighted combination\n"
        "composite = pd.Series(0.0, index=factors_best[SELECTED_FACTORS[0]].index)\n"
        "total_weight = 0\n\n"
        "for name in SELECTED_FACTORS:\n"
        "    icir = FACTOR_ICIR[name]\n"
        "    weight = icir  # sign * magnitude, so long_low factors get negative weight → flipped to positive alpha\n"
        "    composite = composite + weight * zscores[name].fillna(0)\n"
        "    total_weight += abs(weight)\n"
        "    print(f'  {name:<25s}  weight = {weight:+.3f}')\n\n"
        "# Normalize\n"
        "composite = composite / total_weight\n"
        "composite.name = 'composite_factor'\n\n"
        "print(f'\\nComposite factor computed. NaN%: {composite.isna().mean():.2%}')"
    ))

    cells.append(new_code_cell(
        "# IC analysis of composite factor (full period)\n"
        "ic_comp = compute_ic_series(composite, fwd_5d, min_obs=50)\n"
        "sum_comp = compute_ic_summary(ic_comp)\n\n"
        "print('=== Composite Factor IC (Full Period) ===')\n"
        "print(f\"  Mean Rank IC:  {sum_comp['mean_rank_ic']:.4f}\")\n"
        "print(f\"  Rank ICIR:     {sum_comp['rank_icir']:.4f}\")\n"
        "print(f\"  IC Hit Rate:   {sum_comp['ic_hit_rate']:.1%}\")\n"
        "print(f\"  Days:          {sum_comp['n_days']}\")\n\n"
        "# Compare with best single factor\n"
        "print(f'\\nComposite Rank ICIR ({sum_comp[\"rank_icir\"]:.3f}) vs best single factor liq_vol_cv ({FACTOR_ICIR[\"liq_vol_cv\"]:.3f})')\n"
        "improvement = (abs(sum_comp['rank_icir']) - abs(FACTOR_ICIR['liq_vol_cv'])) / abs(FACTOR_ICIR['liq_vol_cv'])\n"
        "print(f'Improvement: {improvement:+.1%}')"
    ))

    cells.append(new_code_cell(
        "# Quantile analysis of composite\n"
        "q_ret = compute_quantile_returns(composite, fwd_5d, n_quantiles=10, min_obs=100)\n"
        "q_sum = compute_quantile_summary(q_ret)\n"
        "ls = compute_long_short_returns(q_ret, long_q=5, short_q=1)\n"
        "mono = test_monotonicity(q_sum)\n\n"
        "print(f'Monotonicity: {\"PASS\" if mono[\"is_monotonic\"] else \"FAIL\"}')\n"
        "print(f'  Spearman corr: {mono[\"spearman_corr\"]:.4f}')\n\n"
        "display(q_sum.style.format({\n"
        "    'mean_daily_return': '{:.4%}',\n"
        "    'annualized_return': '{:.2%}',\n"
        "    'volatility': '{:.2%}',\n"
        "    'sharpe': '{:.3f}',\n"
        "}))\n\n"
        "# L/S performance\n"
        "report = generate_performance_report(ls)\n"
        "print('\\n=== Composite L/S Performance ===')\n"
        "display(report)"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §5: TEMPORAL VALIDATION
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 5. Temporal Validation (Train / Validation)\n\n"
        "Compare factor performance across train (2012–2020) and validation (2021–2023) periods.\n"
        "Factors that degrade significantly in validation may be overfit."
    ))

    cells.append(new_code_cell(
        "%%time\n"
        "# Split IC by period\n"
        "periods = {\n"
        "    'Train (2012-2020)': (TRAIN_START, TRAIN_END),\n"
        "    'Val (2021-2023)': (VAL_START, VAL_END),\n"
        "}\n\n"
        "temporal_results = []\n\n"
        "for period_name, (start, end) in periods.items():\n"
        "    # Filter factors and forward returns to this period\n"
        "    mask = (composite.index.get_level_values(0) >= start) & \\\n"
        "           (composite.index.get_level_values(0) <= end)\n"
        "    comp_period = composite[mask]\n"
        "    fwd_period = fwd_5d[mask]\n\n"
        "    # Composite IC\n"
        "    ic_p = compute_ic_series(comp_period, fwd_period, min_obs=50)\n"
        "    sum_p = compute_ic_summary(ic_p) if not ic_p.empty else {}\n\n"
        "    temporal_results.append({\n"
        "        'period': period_name,\n"
        "        'factor': 'COMPOSITE',\n"
        "        'mean_rank_ic': sum_p.get('mean_rank_ic', 0),\n"
        "        'rank_icir': sum_p.get('rank_icir', 0),\n"
        "        'ic_hit_rate': sum_p.get('ic_hit_rate', 0),\n"
        "        'n_days': sum_p.get('n_days', 0),\n"
        "    })\n\n"
        "    # Individual factors\n"
        "    for name in SELECTED_FACTORS:\n"
        "        f_period = factors_best[name][mask]\n"
        "        ic_f = compute_ic_series(f_period, fwd_period, min_obs=50)\n"
        "        sum_f = compute_ic_summary(ic_f) if not ic_f.empty else {}\n"
        "        temporal_results.append({\n"
        "            'period': period_name,\n"
        "            'factor': name,\n"
        "            'mean_rank_ic': sum_f.get('mean_rank_ic', 0),\n"
        "            'rank_icir': sum_f.get('rank_icir', 0),\n"
        "            'ic_hit_rate': sum_f.get('ic_hit_rate', 0),\n"
        "            'n_days': sum_f.get('n_days', 0),\n"
        "        })\n\n"
        "temporal_df = pd.DataFrame(temporal_results)\n"
        "pivot = temporal_df.pivot(index='factor', columns='period', values='rank_icir')\n"
        "pivot = pivot.reindex(['COMPOSITE'] + SELECTED_FACTORS)\n\n"
        "print('=== Rank ICIR by Period ===')\n"
        "display(pivot.style.format('{:.3f}').background_gradient(cmap='RdYlGn', vmin=-0.5, vmax=0.5))"
    ))

    cells.append(new_code_cell(
        "# Grouped bar chart: Train vs Val ICIR\n"
        "fig, ax = plt.subplots(figsize=(14, 6))\n"
        "pivot.plot.bar(ax=ax, color=['#1976D2', '#FF7043'], edgecolor='white', width=0.7)\n"
        "ax.axhline(0, color='black', linewidth=0.5)\n"
        "ax.axhline(0.3, color='green', linewidth=1, linestyle='--', alpha=0.4, label='ICIR=±0.3')\n"
        "ax.axhline(-0.3, color='green', linewidth=1, linestyle='--', alpha=0.4)\n"
        "ax.set_ylabel('Rank ICIR')\n"
        "ax.set_title('Factor Stability: Train vs Validation Period', fontweight='bold')\n"
        "ax.legend()\n"
        "ax.grid(axis='y', alpha=0.3)\n"
        "plt.xticks(rotation=45, ha='right')\n"
        "plt.tight_layout()\n"
        "plt.show()\n\n"
        "# Validation gate\n"
        "val_icir = pivot.iloc[:, -1]  # validation column\n"
        "comp_val = val_icir.loc['COMPOSITE']\n"
        "print(f'\\nComposite Validation ICIR: {comp_val:.3f}')\n"
        "if abs(comp_val) >= 0.2:\n"
        "    print('✅ PASS — proceed to out-of-sample test')\n"
        "else:\n"
        "    print('⚠️  WARN — validation ICIR < 0.2, consider revising factor pool')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §6: OUT-OF-SAMPLE TEST
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 6. Out-of-Sample Test (2024+)\n\n"
        "> **⚠️ ONE-SHOT TEST** — Run this section ONCE. Do NOT iterate on these results.\n"
        "> Log the result before making any model changes."
    ))

    cells.append(new_code_cell(
        "%%time\n"
        "# OOS IC analysis\n"
        "mask_oos = (composite.index.get_level_values(0) >= TEST_START) & \\\n"
        "           (composite.index.get_level_values(0) <= TEST_END)\n"
        "comp_oos = composite[mask_oos]\n"
        "fwd_oos = fwd_5d[mask_oos]\n\n"
        "ic_oos = compute_ic_series(comp_oos, fwd_oos, min_obs=50)\n"
        "sum_oos = compute_ic_summary(ic_oos) if not ic_oos.empty else {}\n\n"
        "print('╔═══════════════════════════════════════════╗')\n"
        "print('║   OUT-OF-SAMPLE RESULTS (2024+)          ║')\n"
        "print('╠═══════════════════════════════════════════╣')\n"
        "print(f'║  Mean Rank IC:  {sum_oos.get(\"mean_rank_ic\", 0):.4f}              ║')\n"
        "print(f'║  Rank ICIR:     {sum_oos.get(\"rank_icir\", 0):.4f}              ║')\n"
        "print(f'║  IC Hit Rate:   {sum_oos.get(\"ic_hit_rate\", 0):.1%}               ║')\n"
        "print(f'║  N Days:        {sum_oos.get(\"n_days\", 0)}                 ║')\n"
        "print('╚═══════════════════════════════════════════╝')\n\n"
        "# OOS L/S backtest\n"
        "q_oos = compute_quantile_returns(comp_oos, fwd_oos, n_quantiles=10, min_obs=100)\n"
        "if not q_oos.empty:\n"
        "    ls_oos = compute_long_short_returns(q_oos, long_q=5, short_q=1)\n"
        "    report_oos = generate_performance_report(ls_oos)\n"
        "    print('\\n=== OOS L/S Performance ===')\n"
        "    display(report_oos)\n"
        "else:\n"
        "    print('Not enough OOS data for quantile analysis')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §7: BACKTEST WITH VECTORIZED BACKTESTER
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 7. Backtest with VectorizedBacktester\n\n"
        "Full Qlib-integrated backtest with:\n"
        "- TopkDropout strategy (topk=50, n_drop=5)\n"
        "- A-share exchange costs (buy 0.05%, sell 0.15%, min ¥5)\n"
        "- Benchmark: 沪深300 (000300_SH)"
    ))

    cells.append(new_code_cell(
        "from src.backtest_engine.vectorized import VectorizedBacktester\n\n"
        "bt = VectorizedBacktester(\n"
        "    config_path=os.path.join(PROJECT_ROOT, 'config.yaml'),\n"
        "    qlib_dir=QLIB_DIR,\n"
        ")\n"
        "print('Backtester initialized')"
    ))

    cells.append(new_code_cell(
        "%%time\n"
        "# Prepare prediction signal: composite factor needs MultiIndex(datetime, instrument)\n"
        "# VectorizedBacktester expects higher score = better stock\n"
        "signal = composite.copy()\n"
        "signal.name = 'score'\n\n"
        "# Run backtest — full period\n"
        "print('Running full-period backtest...')\n"
        "result_full = bt.run(\n"
        "    predictions=signal,\n"
        "    start_time=TRAIN_START,\n"
        "    end_time=FULL_END,\n"
        "    topk=50,\n"
        "    n_drop=5,\n"
        "    benchmark='000300_SH',  # 沪深300 in Qlib underscore format\n"
        ")\n\n"
        "print('\\n=== Full-Period Backtest Summary ===')\n"
        "print(result_full)"
    ))

    cells.append(new_code_cell(
        "# Plot equity curve & drawdown\n"
        "if hasattr(result_full, 'report') and result_full.report is not None:\n"
        "    report_df = result_full.report\n\n"
        "    fig, axes = plt.subplots(2, 1, figsize=(16, 9), sharex=True)\n\n"
        "    # Panel 1: Cumulative returns\n"
        "    ax1 = axes[0]\n"
        "    cum_ret = (1 + report_df['return']).cumprod()\n"
        "    ax1.plot(cum_ret.index, cum_ret.values, label='Strategy', linewidth=1.5, color='#1976D2')\n"
        "    ax1.set_ylabel('Cumulative Return')\n"
        "    ax1.set_title('Multi-Factor Strategy Equity Curve', fontweight='bold', fontsize=14)\n"
        "    ax1.legend()\n"
        "    ax1.grid(alpha=0.3)\n\n"
        "    # Panel 2: Drawdown\n"
        "    ax2 = axes[1]\n"
        "    peak = cum_ret.expanding().max()\n"
        "    dd = (cum_ret - peak) / peak\n"
        "    ax2.fill_between(dd.index, dd.values, 0, color='red', alpha=0.3)\n"
        "    ax2.set_ylabel('Drawdown')\n"
        "    ax2.set_title('Strategy Drawdown', fontweight='bold')\n"
        "    ax2.grid(alpha=0.3)\n\n"
        "    plt.tight_layout()\n"
        "    plt.show()\n"
        "else:\n"
        "    print('No backtest report available')"
    ))

    cells.append(new_code_cell(
        "%%time\n"
        "# Compare: composite vs best single factor (liq_vol_cv) vs equal-weight\n"
        "# Build equal-weight composite for comparison\n"
        "composite_eq = pd.Series(0.0, index=composite.index)\n"
        "for name in SELECTED_FACTORS:\n"
        "    direction = FACTOR_DIRECTION[name]\n"
        "    composite_eq = composite_eq + direction * zscores[name].fillna(0)\n"
        "composite_eq = composite_eq / len(SELECTED_FACTORS)\n"
        "composite_eq.name = 'score'\n\n"
        "# Best single factor\n"
        "single_best = factors_best['liq_vol_cv'].copy()\n"
        "# Flip sign so higher = better (since direction is -1)\n"
        "single_best = -single_best\n"
        "single_best.name = 'score'\n\n"
        "signals = {\n"
        "    'Composite (ICIR-weighted)': signal,\n"
        "    'Composite (Equal-weighted)': composite_eq,\n"
        "    'Single: liq_vol_cv': single_best,\n"
        "}\n\n"
        "print('Running comparison backtest...')\n"
        "comparison = bt.compare(\n"
        "    signals=signals,\n"
        "    start_time=TRAIN_START,\n"
        "    end_time=FULL_END,\n"
        "    topk=50,\n"
        "    n_drop=5,\n"
        ")\n\n"
        "print('\\n=== Strategy Comparison ===')\n"
        "display(comparison)"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §8: MLFLOW LOGGING
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 8. MLflow Logging\n\n"
        "Log all parameters, metrics, and artifacts to MLflow for reproducibility.\n\n"
        "> **Note:** Requires MLflow server running at the URI in `config.yaml`.\n"
        "> If not available, this section can be skipped — results are printed above."
    ))

    cells.append(new_code_cell(
        "# Log to MLflow (optional — skip if server not running)\n"
        "SKIP_MLFLOW = True  # Set to False when MLflow server is running\n\n"
        "if not SKIP_MLFLOW:\n"
        "    from src.alpha_research.mlflow_tracker import ExperimentTracker\n\n"
        "    tracker = ExperimentTracker(os.path.join(PROJECT_ROOT, 'config.yaml'))\n"
        "    tracker.start_run('multi_factor_8f_v1')\n\n"
        "    # Params\n"
        "    tracker.log_params({\n"
        "        'n_factors': len(SELECTED_FACTORS),\n"
        "        'factors': ','.join(SELECTED_FACTORS),\n"
        "        'combination': 'icir_weighted_zscore',\n"
        "        'universe': 'all_stocks',\n"
        "        'train_period': f'{TRAIN_START}_{TRAIN_END}',\n"
        "        'val_period': f'{VAL_START}_{VAL_END}',\n"
        "        'test_period': f'{TEST_START}_{TEST_END}',\n"
        "        'topk': 50,\n"
        "        'n_drop': 5,\n"
        "    })\n\n"
        "    # Metrics\n"
        "    tracker.log_metrics({\n"
        "        'full_rank_icir': sum_comp['rank_icir'],\n"
        "        'full_ic_hit_rate': sum_comp['ic_hit_rate'],\n"
        "        'oos_rank_icir': sum_oos.get('rank_icir', 0),\n"
        "    })\n\n"
        "    # Add backtest metrics if available\n"
        "    if hasattr(result_full, 'summary'):\n"
        "        s = result_full.summary()\n"
        "        tracker.log_metrics({\n"
        "            'bt_sharpe': s.get('sharpe', 0),\n"
        "            'bt_ann_return': s.get('annualized_return', 0),\n"
        "            'bt_max_drawdown': s.get('max_drawdown', 0),\n"
        "            'bt_turnover': s.get('turnover', 0),\n"
        "        })\n\n"
        "    tracker.end_run()\n"
        "    print('Results logged to MLflow ✅')\n"
        "else:\n"
        "    print('MLflow logging skipped (SKIP_MLFLOW=True)')\n"
        "    print('Set SKIP_MLFLOW=False when MLflow server is running')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # CONCLUSION
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## Summary\n\n"
        "| Stage | Key Metric | Value |\n"
        "|-------|-----------|-------|\n"
        "| Factor Pool | Factors selected | 8 (3 liq, 2 mom, 2 tech, 1 val) |\n"
        "| Composite | Full-period Rank ICIR | See §4 |\n"
        "| Validation | 2021-2023 Rank ICIR | See §5 |\n"
        "| OOS Test | 2024+ Rank ICIR | See §6 |\n"
        "| Backtest | Sharpe vs 沪深300 | See §7 |\n\n"
        "### Next Steps\n"
        "1. **Optimize rebalance frequency** based on IC decay results\n"
        "2. **Position sizing**: Replace equal-weight with risk-parity or min-variance\n"
        "3. **Transaction cost sensitivity**: Vary cost assumptions, measure net Sharpe\n"
        "4. **Walk-forward validation**: Rolling 2-year train + 1-year test windows\n"
        "5. **Live signal generation**: Pipeline from raw data → composite factor → trade list\n\n"
        "---\n"
        "*Generated by `workspace/scripts/generate_strategy_notebook.py`*"
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
