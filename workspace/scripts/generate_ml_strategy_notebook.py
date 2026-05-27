#!/usr/bin/env python
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
Generate ML Multi-Factor Strategy Notebook.

Creates a Jupyter notebook that:
  1. Loads market data from Qlib
  2. Engineers ~60 alpha factors (price-volume, fundamental, technical)
  3. Constructs walk-forward train/valid/test splits
  4. Trains LightGBM models per fold with early stopping
  5. Analyzes feature importance
  6. Assembles OOS predictions
  7. Backtests with VectorizedBacktester
  8. Compares ML vs linear baseline vs CSI300
  9. Logs to MLflow (optional)

Usage:
    python workspace/scripts/generate_ml_strategy_notebook.py

Output:
    workspace/research/alpha_factors/ml_strategy.ipynb
"""
import os
import nbformat


def new_code_cell(source: str) -> nbformat.NotebookNode:
    """Create a code cell."""
    return nbformat.v4.new_code_cell(source=source)


def new_markdown_cell(source: str) -> nbformat.NotebookNode:
    """Create a markdown cell."""
    return nbformat.v4.new_markdown_cell(source=source)


def build_notebook() -> nbformat.NotebookNode:
    """Build the complete ML strategy notebook."""
    nb = nbformat.v4.new_notebook()
    nb.metadata.kernelspec = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    cells = nb.cells

    # ═══════════════════════════════════════════════════════════════
    # §0: TITLE
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "# ML Multi-Factor Strategy (LightGBM)\n\n"
        "Machine learning approach to multi-factor stock selection:\n"
        "- **Features**: ~60 engineered alpha factors from 350+ Qlib fields\n"
        "- **Model**: LightGBM with walk-forward validation\n"
        "- **Backtest**: TopkDropout(50) with CSI300 benchmark\n\n"
        "This notebook replaces the linear ICIR-weighted composite with a "
        "non-linear model that captures factor interactions."
    ))

    # ═══════════════════════════════════════════════════════════════
    # §1: SETUP & DATA LOADING
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 1. Setup & Data Loading"
    ))

    cells.append(new_code_cell(
        "import os, sys, yaml, warnings\n"
        "import numpy as np\n"
        "import pandas as pd\n"
        "import matplotlib.pyplot as plt\n"
        "import seaborn as sns\n\n"
        "warnings.filterwarnings('ignore', category=FutureWarning)\n"
        "warnings.filterwarnings('ignore', category=UserWarning)\n"
        "pd.set_option('display.max_columns', 30)\n"
        "pd.set_option('display.float_format', '{:.4f}'.format)\n\n"
        "# ─── Project setup ───\n"
        "PROJECT_ROOT = os.path.abspath(os.path.join(os.getcwd(), '..', '..', '..'))\n"
        "if PROJECT_ROOT not in sys.path:\n"
        "    sys.path.insert(0, PROJECT_ROOT)\n"
        "print(f'Project root: {PROJECT_ROOT}')\n\n"
        "with open(os.path.join(PROJECT_ROOT, 'config.yaml'), 'r', encoding='utf-8') as f:\n"
        "    config = yaml.safe_load(f)\n"
        "QLIB_DIR = os.path.join(PROJECT_ROOT, config['storage']['qlib_data_dir'])\n"
        "print(f'Qlib dir: {QLIB_DIR}')"
    ))

    cells.append(new_code_cell(
        "import qlib\n"
        "from qlib.data import D\n"
        "from qlib.config import REG_CN\n\n"
        "qlib.init(provider_uri=QLIB_DIR, region=REG_CN)\n"
        "print('Qlib initialized')\n\n"
        "# ─── Date ranges ───\n"
        "FULL_START = '2012-01-01'\n"
        "FULL_END   = '2025-12-31'\n"
        "TRAIN_YEARS = 3   # rolling train window\n"
        "VALID_YEARS = 1   # validation window\n"
        "TEST_YEARS  = 1   # test / OOS window\n"
        "FWD_DAYS    = 20   # forward return horizon (label)\n\n"
        "print(f'Data range: {FULL_START} → {FULL_END}')\n"
        "print(f'Walk-forward: {TRAIN_YEARS}yr train / {VALID_YEARS}yr valid / {TEST_YEARS}yr test')\n"
        "print(f'Label: {FWD_DAYS}-day forward return')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §2: FEATURE ENGINEERING
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 2. Feature Engineering\n\n"
        "We engineer ~60 features from Qlib's raw fields using Qlib expression operators.\n"
        "Categories:\n"
        "- **Price-Volume** (25): momentum, volatility, volume patterns, turnover\n"
        "- **Fundamental** (20): valuation, profitability, leverage, growth\n"
        "- **Technical** (10): mean-reversion signals, price position indicators\n"
        "- **Cross-sectional** (5): rank-normalized features"
    ))

    cells.append(new_code_cell(
        "%%time\n"
        "# ─── Define feature expressions ───\n"
        "# Qlib expression format: $field for raw, operators for derived\n\n"
        "FEATURES = {}\n\n"
        "# ── Price-Volume (25 features) ──────────────────────────\n"
        "# Momentum at multiple horizons\n"
        "for d in [5, 10, 20, 60, 120]:\n"
        "    FEATURES[f'mom_{d}d'] = f'Ref($close,1)/$close - 1'  if d == 1 else f'Ref($close,1)/Ref($close,{d}) - 1'\n\n"
        "# Volatility\n"
        "for d in [5, 10, 20, 60]:\n"
        "    FEATURES[f'vol_{d}d'] = f'Std($close/Ref($close,1)-1, {d})'\n\n"
        "# Volume patterns\n"
        "FEATURES['vol_ratio_5_20'] = 'Mean($vol, 5) / (Mean($vol, 20) + 1e-8)'\n"
        "FEATURES['vol_ratio_5_60'] = 'Mean($vol, 5) / (Mean($vol, 60) + 1e-8)'\n"
        "FEATURES['amt_ratio_5_20'] = 'Mean($amount, 5) / (Mean($amount, 20) + 1e-8)'\n\n"
        "# Turnover\n"
        "FEATURES['turnover_5d'] = 'Mean($turnover_rate, 5)'\n"
        "FEATURES['turnover_20d'] = 'Mean($turnover_rate, 20)'\n"
        "FEATURES['turnover_ratio'] = 'Mean($turnover_rate, 5) / (Mean($turnover_rate, 20) + 1e-8)'\n\n"
        "# Price position\n"
        "FEATURES['high_low_range_20'] = '($high - $low) / ($close + 1e-8)'\n"
        "FEATURES['close_to_high_20'] = '$close / (Max($high, 20) + 1e-8)'\n"
        "FEATURES['close_to_low_20'] = '$close / (Min($low, 20) + 1e-8)'\n\n"
        "# Overnight return\n"
        "FEATURES['overnight_ret_20'] = 'Mean($open/Ref($close,1)-1, 20)'\n\n"
        "# VWAP deviation\n"
        "FEATURES['vwap_dev_5'] = 'Mean($close - $amount/($vol+1e-8), 5)'\n\n"
        "# ── Fundamental (20 features) ──────────────────────────\n"
        "# Valuation\n"
        "FEATURES['pe_ttm'] = '$pe_ttm'\n"
        "FEATURES['pb'] = '$pb'\n"
        "FEATURES['ps_ttm'] = '$ps_ttm'\n"
        "FEATURES['dv_ttm'] = '$dv_ttm'  # dividend yield\n"
        "FEATURES['ep_ttm'] = '1 / ($pe_ttm + 1e-8)'  # earnings yield\n\n"
        "# Profitability\n"
        "FEATURES['roe'] = '$roe'\n"
        "FEATURES['roa'] = '$roa'\n"
        "FEATURES['gross_margin'] = '$grossprofit_margin'\n"
        "FEATURES['net_margin'] = '$netprofit_margin'\n"
        "FEATURES['roic'] = '$roic'\n\n"
        "# Leverage & Liquidity\n"
        "FEATURES['debt_to_assets'] = '$debt_to_assets'\n"
        "FEATURES['current_ratio'] = '$current_ratio'\n"
        "FEATURES['quick_ratio'] = '$quick_ratio'\n"
        "FEATURES['ocf_to_debt'] = '$ocf_to_debt'\n\n"
        "# Growth (YoY)\n"
        "FEATURES['netprofit_yoy'] = '$netprofit_yoy'\n"
        "FEATURES['revenue_yoy'] = '$or_yoy'\n"
        "FEATURES['eps_yoy'] = '$basic_eps_yoy'\n"
        "FEATURES['equity_yoy'] = '$eqt_yoy'\n"
        "FEATURES['ocf_yoy'] = '$ocf_yoy'\n"
        "FEATURES['assets_yoy'] = '$assets_yoy'\n\n"
        "# ── Technical (10 features) ────────────────────────────\n"
        "# Reversal\n"
        "FEATURES['reversal_5d'] = '-1 * (Ref($close,1)/$close - 1)'\n"
        "FEATURES['reversal_20d'] = '-1 * (Ref($close,1)/Ref($close,20) - 1)'\n\n"
        "# Bollinger band position\n"
        "FEATURES['bb_position_20'] = '($close - Mean($close, 20)) / (Std($close, 20) + 1e-8)'\n\n"
        "# Rolling skewness & kurtosis (via return)\n"
        "FEATURES['ret_skew_20'] = 'Skew($close/Ref($close,1)-1, 20)'\n"
        "FEATURES['ret_kurt_20'] = 'Kurt($close/Ref($close,1)-1, 20)'\n\n"
        "# Max drawdown lookback\n"
        "FEATURES['max_dd_20'] = '($close - Max($close, 20)) / (Max($close, 20) + 1e-8)'\n"
        "FEATURES['max_dd_60'] = '($close - Max($close, 60)) / (Max($close, 60) + 1e-8)'\n\n"
        "# Volume-price divergence\n"
        "FEATURES['vol_price_corr_10'] = 'Corr($close, $vol, 10)'\n"
        "FEATURES['vol_price_corr_20'] = 'Corr($close, $vol, 20)'\n\n"
        "# Amihud illiquidity\n"
        "FEATURES['amihud_20'] = 'Mean(Abs($close/Ref($close,1)-1)/($amount+1e-8), 20)'\n\n"
        "# ── Cross-sectional (5 features) ───────────────────────\n"
        "# Log transforms for heavy-tailed fields\n"
        "FEATURES['log_total_mv'] = 'Log($total_mv + 1)'\n"
        "FEATURES['log_circ_mv'] = 'Log($circ_mv + 1)'\n"
        "FEATURES['log_amount_20'] = 'Log(Mean($amount, 20) + 1)'\n"
        "FEATURES['log_vol_20'] = 'Log(Mean($vol, 20) + 1)'\n"
        "FEATURES['volume_ratio_20'] = '$volume_ratio'\n\n"
        "print(f'Total features defined: {len(FEATURES)}')\n"
        "for cat, prefix in [('Price-Volume', ['mom_', 'vol_', 'amt_', 'turnover', 'high_', 'close_to', 'overnight', 'vwap']),\n"
        "                     ('Fundamental', ['pe_', 'pb', 'ps_', 'dv_', 'ep_', 'roe', 'roa', 'gross', 'net_', 'roic', 'debt', 'current', 'quick', 'ocf_to', 'netprofit_y', 'revenue_y', 'eps_y', 'equity_y', 'ocf_y', 'assets_y']),\n"
        "                     ('Technical', ['reversal', 'bb_', 'ret_skew', 'ret_kurt', 'max_dd', 'vol_price', 'amihud']),\n"
        "                     ('Cross-sectional', ['log_', 'volume_ratio'])]:\n"
        "    n = sum(1 for k in FEATURES if any(k.startswith(p) for p in prefix))\n"
        "    print(f'  {cat}: {n}')"
    ))

    cells.append(new_code_cell(
        "%%time\n"
        "# ─── Load features from Qlib ───\n"
        "instruments = D.instruments(market='all_stocks')\n\n"
        "# Build expression list for D.features()\n"
        "feature_exprs = list(FEATURES.values())\n"
        "feature_names = list(FEATURES.keys())\n\n"
        "df_raw = D.features(\n"
        "    instruments, feature_exprs,\n"
        "    start_time=FULL_START, end_time=FULL_END,\n"
        ")\n\n"
        "# Rename columns to feature names\n"
        "df_raw.columns = feature_names\n\n"
        "# Swap to (datetime, instrument) convention\n"
        "df_raw = df_raw.swaplevel().sort_index()\n\n"
        "print(f'Raw feature matrix: {df_raw.shape}')\n"
        "print(f'Date range: {df_raw.index.get_level_values(0).min()} → {df_raw.index.get_level_values(0).max()}')\n"
        "print(f'Stocks: {df_raw.index.get_level_values(1).nunique()}')\n\n"
        "# Coverage check\n"
        "coverage = (1 - df_raw.isna().mean()).sort_values()\n"
        "print(f'\\nFeature coverage (non-NaN rate):')\n"
        "print(coverage.head(10).to_string())  # worst coverage\n"
        "print(f'  ...')\n"
        "print(f'  Median coverage: {coverage.median():.1%}')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §3: LABEL CONSTRUCTION
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 3. Label Construction\n\n"
        "Forward N-day return as prediction target. Winsorized to reduce outlier influence."
    ))

    cells.append(new_code_cell(
        "%%time\n"
        "# ─── Construct forward return label ───\n"
        "close = D.features(instruments, ['$close'],\n"
        "                   start_time=FULL_START, end_time=FULL_END)\n"
        "close = close.swaplevel().sort_index()\n"
        "close.columns = ['close']\n\n"
        "# Forward return\n"
        "label = close.groupby(level=1)['close'].pct_change(FWD_DAYS).shift(-FWD_DAYS)\n"
        "label.name = 'label'\n\n"
        "# Winsorize at 1% / 99%\n"
        "lower = label.quantile(0.01)\n"
        "upper = label.quantile(0.99)\n"
        "label = label.clip(lower, upper)\n\n"
        "print(f'Label ({FWD_DAYS}d forward return):')\n"
        "print(f'  Shape: {label.shape}')\n"
        "print(f'  Mean: {label.mean():.4f}, Std: {label.std():.4f}')\n"
        "print(f'  Range: [{lower:.4f}, {upper:.4f}] (after winsorization)')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §4: WALK-FORWARD SPLIT
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 4. Walk-Forward Split\n\n"
        "Rolling window: 3yr train → 1yr valid → 1yr test, rolling forward by 1 year.\n"
        "No data leakage between folds."
    ))

    cells.append(new_code_cell(
        "# ─── Merge features + label ───\n"
        "df_full = df_raw.join(label, how='inner').dropna(subset=['label'])\n\n"
        "# Drop rows with >50% missing features\n"
        "feature_cols = list(FEATURES.keys())\n"
        "missing_rate = df_full[feature_cols].isna().mean(axis=1)\n"
        "df_full = df_full[missing_rate <= 0.5].copy()\n\n"
        "# Fill remaining NaN with cross-sectional median\n"
        "def fill_cs_median(group):\n"
        "    return group.fillna(group.median())\n\n"
        "df_full[feature_cols] = df_full.groupby(level=0, group_keys=False)[feature_cols].apply(fill_cs_median)\n"
        "# Any remaining NaN (all stocks missing) → fill 0\n"
        "df_full[feature_cols] = df_full[feature_cols].fillna(0)\n\n"
        "print(f'Clean dataset: {df_full.shape}')\n"
        "print(f'NaN remaining: {df_full[feature_cols].isna().sum().sum()}')"
    ))

    cells.append(new_code_cell(
        "# ─── Build walk-forward folds ───\n"
        "dates = df_full.index.get_level_values(0).unique().sort_values()\n"
        "years = dates.year.unique().sort_values()\n"
        "print(f'Available years: {years.tolist()}')\n\n"
        "folds = []\n"
        "first_year = years[0]\n"
        "total_window = TRAIN_YEARS + VALID_YEARS + TEST_YEARS\n\n"
        "for start_year in range(first_year, years[-1] - total_window + 2):\n"
        "    train_start = f'{start_year}-01-01'\n"
        "    train_end   = f'{start_year + TRAIN_YEARS - 1}-12-31'\n"
        "    valid_start = f'{start_year + TRAIN_YEARS}-01-01'\n"
        "    valid_end   = f'{start_year + TRAIN_YEARS + VALID_YEARS - 1}-12-31'\n"
        "    test_start  = f'{start_year + TRAIN_YEARS + VALID_YEARS}-01-01'\n"
        "    test_end    = f'{start_year + TRAIN_YEARS + VALID_YEARS + TEST_YEARS - 1}-12-31'\n"
        "    \n"
        "    # Check we have data for all periods\n"
        "    train_dates = dates[(dates >= train_start) & (dates <= train_end)]\n"
        "    valid_dates = dates[(dates >= valid_start) & (dates <= valid_end)]\n"
        "    test_dates  = dates[(dates >= test_start) & (dates <= test_end)]\n"
        "    \n"
        "    if len(train_dates) > 100 and len(valid_dates) > 50 and len(test_dates) > 50:\n"
        "        folds.append({\n"
        "            'fold': len(folds) + 1,\n"
        "            'train': (train_start, train_end),\n"
        "            'valid': (valid_start, valid_end),\n"
        "            'test':  (test_start, test_end),\n"
        "            'train_days': len(train_dates),\n"
        "            'valid_days': len(valid_dates),\n"
        "            'test_days':  len(test_dates),\n"
        "        })\n\n"
        "print(f'Walk-forward folds: {len(folds)}\\n')\n"
        "fold_df = pd.DataFrame(folds)\n"
        "fold_df['train_range'] = fold_df['train'].apply(lambda x: f'{x[0]} → {x[1]}')\n"
        "fold_df['valid_range'] = fold_df['valid'].apply(lambda x: f'{x[0]} → {x[1]}')\n"
        "fold_df['test_range']  = fold_df['test'].apply(lambda x: f'{x[0]} → {x[1]}')\n"
        "display(fold_df[['fold', 'train_range', 'valid_range', 'test_range', 'train_days', 'valid_days', 'test_days']])"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §5: MODEL TRAINING
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 5. LightGBM Walk-Forward Training\n\n"
        "Train one LightGBM per fold. Early stopping on validation MSE.\n"
        "Collect OOS predictions and per-fold metrics."
    ))

    cells.append(new_code_cell(
        "%%time\n"
        "from src.alpha_research.model_zoo import LightGBMModel\n"
        "from src.alpha_research.factor_eval import compute_ic_series, compute_ic_summary\n\n"
        "# ─── Training loop ───\n"
        "all_predictions = []  # OOS predictions per fold\n"
        "fold_metrics = []     # per-fold IC/ICIR\n"
        "fold_importances = [] # feature importance per fold\n\n"
        "for fold_info in folds:\n"
        "    fold_id = fold_info['fold']\n"
        "    tr_s, tr_e = fold_info['train']\n"
        "    va_s, va_e = fold_info['valid']\n"
        "    te_s, te_e = fold_info['test']\n"
        "    \n"
        "    print(f'\\n{\"=\"*60}')\n"
        "    print(f'Fold {fold_id}: Train [{tr_s},{tr_e}] | Valid [{va_s},{va_e}] | Test [{te_s},{te_e}]')\n"
        "    print(f'{\"=\"*60}')\n"
        "    \n"
        "    # Slice data\n"
        "    idx = df_full.index.get_level_values(0)\n"
        "    mask_train = (idx >= tr_s) & (idx <= tr_e)\n"
        "    mask_valid = (idx >= va_s) & (idx <= va_e)\n"
        "    mask_test  = (idx >= te_s) & (idx <= te_e)\n"
        "    \n"
        "    X_train = df_full.loc[mask_train, feature_cols]\n"
        "    y_train = df_full.loc[mask_train, 'label']\n"
        "    X_valid = df_full.loc[mask_valid, feature_cols]\n"
        "    y_valid = df_full.loc[mask_valid, 'label']\n"
        "    X_test  = df_full.loc[mask_test, feature_cols]\n"
        "    y_test  = df_full.loc[mask_test, 'label']\n"
        "    \n"
        "    print(f'  Samples: train={len(X_train)}, valid={len(X_valid)}, test={len(X_test)}')\n"
        "    \n"
        "    # Train\n"
        "    model = LightGBMModel(\n"
        "        num_leaves=128,\n"
        "        max_depth=8,\n"
        "        learning_rate=0.05,\n"
        "        feature_fraction=0.8,\n"
        "        bagging_fraction=0.8,\n"
        "        bagging_freq=5,\n"
        "        lambda_l1=0.1,\n"
        "        lambda_l2=1.0,\n"
        "        min_data_in_leaf=200,\n"
        "    )\n"
        "    model.fit(X_train, y_train, X_valid, y_valid,\n"
        "              num_boost_round=1000, early_stopping_rounds=50)\n"
        "    \n"
        "    # OOS predictions\n"
        "    pred_test = model.predict(X_test)\n"
        "    all_predictions.append(pred_test)\n"
        "    \n"
        "    # Feature importance\n"
        "    fi = model.feature_importance('gain')\n"
        "    fi.name = f'fold_{fold_id}'\n"
        "    fold_importances.append(fi)\n"
        "    \n"
        "    # OOS IC\n"
        "    try:\n"
        "        ic_series = compute_ic_series(pred_test, y_test)\n"
        "        ic_summary = compute_ic_summary(ic_series)\n"
        "        print(f'  OOS RankIC: {ic_summary[\"mean_rank_ic\"]:.4f}, ICIR: {ic_summary[\"rank_icir\"]:.4f}')\n"
        "        fold_metrics.append({\n"
        "            'fold': fold_id,\n"
        "            'test_period': f'{te_s}_{te_e}',\n"
        "            'rank_ic': ic_summary['mean_rank_ic'],\n"
        "            'rank_icir': ic_summary['rank_icir'],\n"
        "            'ic_hit_rate': ic_summary.get('ic_hit_rate', 0),\n"
        "            'best_iteration': model.model.best_iteration,\n"
        "        })\n"
        "    except Exception as e:\n"
        "        print(f'  IC computation failed: {e}')\n"
        "        fold_metrics.append({'fold': fold_id, 'test_period': f'{te_s}_{te_e}',\n"
        "                            'rank_ic': np.nan, 'rank_icir': np.nan})\n\n"
        "print(f'\\n{\"=\"*60}')\n"
        "print('Walk-forward training complete!')\n"
        "print(f'Total OOS predictions: {sum(len(p) for p in all_predictions)}')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §6: FEATURE IMPORTANCE
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 6. Feature Importance Analysis"
    ))

    cells.append(new_code_cell(
        "# ─── Per-fold metrics ───\n"
        "metrics_df = pd.DataFrame(fold_metrics)\n"
        "print('=== Per-Fold OOS Performance ===')\n"
        "display(metrics_df)\n\n"
        "print(f'\\nAverage OOS Rank IC:   {metrics_df[\"rank_ic\"].mean():.4f}')\n"
        "print(f'Average OOS Rank ICIR: {metrics_df[\"rank_icir\"].mean():.4f}')"
    ))

    cells.append(new_code_cell(
        "# ─── Feature importance (averaged across folds) ───\n"
        "fi_all = pd.concat(fold_importances, axis=1)\n"
        "fi_mean = fi_all.mean(axis=1).sort_values(ascending=False)\n"
        "fi_std = fi_all.std(axis=1).reindex(fi_mean.index)\n\n"
        "fig, axes = plt.subplots(1, 2, figsize=(18, 8))\n\n"
        "# Top-20 features\n"
        "ax1 = axes[0]\n"
        "top20 = fi_mean.head(20)\n"
        "colors = ['#1976D2' if std/mean < 0.5 else '#FFB74D' \n"
        "          for mean, std in zip(top20.values, fi_std.head(20).values)]\n"
        "ax1.barh(range(len(top20)), top20.values[::-1], color=colors[::-1])\n"
        "ax1.set_yticks(range(len(top20)))\n"
        "ax1.set_yticklabels(top20.index[::-1], fontsize=10)\n"
        "ax1.set_xlabel('Mean Gain Importance')\n"
        "ax1.set_title('Top-20 Features (blue=stable, orange=variable)', fontweight='bold')\n\n"
        "# Cumulative importance\n"
        "ax2 = axes[1]\n"
        "cum_imp = (fi_mean / fi_mean.sum()).cumsum()\n"
        "ax2.plot(range(len(cum_imp)), cum_imp.values, 'o-', markersize=3, color='#1976D2')\n"
        "ax2.axhline(0.8, color='red', linestyle='--', alpha=0.5, label='80% threshold')\n"
        "n_80 = (cum_imp <= 0.8).sum() + 1\n"
        "ax2.axvline(n_80, color='red', linestyle='--', alpha=0.5)\n"
        "ax2.set_xlabel('Number of Features')\n"
        "ax2.set_ylabel('Cumulative Importance')\n"
        "ax2.set_title(f'Cumulative Importance ({n_80} features capture 80%)', fontweight='bold')\n"
        "ax2.legend()\n\n"
        "plt.tight_layout()\n"
        "plt.show()"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §7: OOS PREDICTION ASSEMBLY
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 7. Out-of-Sample Prediction Assembly"
    ))

    cells.append(new_code_cell(
        "# ─── Concatenate OOS predictions ───\n"
        "oos_pred = pd.concat(all_predictions)\n\n"
        "# Remove duplicates (overlapping fold boundaries)\n"
        "oos_pred = oos_pred[~oos_pred.index.duplicated(keep='last')]\n"
        "oos_pred = oos_pred.sort_index()\n"
        "oos_pred.name = 'score'\n\n"
        "print(f'OOS Prediction Series:')\n"
        "print(f'  Shape: {oos_pred.shape}')\n"
        "print(f'  Date range: {oos_pred.index.get_level_values(0).min()} → {oos_pred.index.get_level_values(0).max()}')\n"
        "print(f'  Unique dates: {oos_pred.index.get_level_values(0).nunique()}')\n"
        "print(f'  Stocks/day: {len(oos_pred) / oos_pred.index.get_level_values(0).nunique():.0f}')\n\n"
        "# OOS IC over the full period\n"
        "label_aligned = label.reindex(oos_pred.index)\n"
        "oos_ic = compute_ic_series(oos_pred, label_aligned)\n"
        "oos_summary = compute_ic_summary(oos_ic)\n\n"
        "print(f'\\n=== Full OOS IC Summary ===')\n"
        "for k, v in oos_summary.items():\n"
        "    if isinstance(v, float):\n"
        "        print(f'  {k}: {v:.4f}')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §8: BACKTEST
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 8. Backtest: ML vs Linear vs CSI300"
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
        "# ─── Run ML backtest ───\n"
        "oos_start = str(oos_pred.index.get_level_values(0).min().date())\n"
        "oos_end   = str(oos_pred.index.get_level_values(0).max().date())\n\n"
        "print(f'OOS backtest period: {oos_start} → {oos_end}')\n\n"
        "result_ml = bt.run(\n"
        "    predictions=oos_pred,\n"
        "    start_time=oos_start,\n"
        "    end_time=oos_end,\n"
        "    topk=50,\n"
        "    n_drop=5,\n"
        "    benchmark='000300_SH',\n"
        ")\n\n"
        "print('\\n=== ML Strategy Backtest Summary ===')\n"
        "print(result_ml)"
    ))

    cells.append(new_code_cell(
        "# ─── Equity curve + Drawdown ───\n"
        "if result_ml.report is not None:\n"
        "    report = result_ml.report\n"
        "    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True)\n\n"
        "    # Panel 1: Cumulative returns\n"
        "    cum_ret = (1 + report['return']).cumprod()\n"
        "    cum_bench = (1 + report['bench']).cumprod()\n"
        "    axes[0].plot(cum_ret.index, cum_ret.values, label='ML Strategy', linewidth=1.5, color='#1976D2')\n"
        "    axes[0].plot(cum_bench.index, cum_bench.values, label='CSI 300', linewidth=1.5, alpha=0.7, color='#757575')\n"
        "    axes[0].set_ylabel('Cumulative Return')\n"
        "    axes[0].set_title('ML Multi-Factor Strategy vs CSI 300', fontweight='bold', fontsize=14)\n"
        "    axes[0].legend()\n"
        "    axes[0].grid(alpha=0.3)\n\n"
        "    # Panel 2: Excess return\n"
        "    excess = report['return'] - report['bench']\n"
        "    cum_excess = (1 + excess).cumprod()\n"
        "    axes[1].plot(cum_excess.index, cum_excess.values, color='green', linewidth=1.5)\n"
        "    axes[1].axhline(1, color='black', linewidth=0.5, linestyle='--')\n"
        "    axes[1].set_ylabel('Cumulative Excess Return')\n"
        "    axes[1].set_title('Excess Return vs CSI 300', fontweight='bold')\n"
        "    axes[1].grid(alpha=0.3)\n\n"
        "    # Panel 3: Drawdown\n"
        "    peak = cum_ret.expanding().max()\n"
        "    dd = (cum_ret - peak) / peak\n"
        "    axes[2].fill_between(dd.index, dd.values, 0, color='red', alpha=0.3)\n"
        "    axes[2].set_ylabel('Drawdown')\n"
        "    axes[2].set_title('Strategy Drawdown', fontweight='bold')\n"
        "    axes[2].grid(alpha=0.3)\n\n"
        "    plt.tight_layout()\n"
        "    plt.show()"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §9: MLFLOW LOGGING (optional)
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## 9. Experiment Logging (MLflow)\n\n"
        "Log model parameters, per-fold metrics, and feature importance."
    ))

    cells.append(new_code_cell(
        "# ─── MLflow logging (optional — skip if MLflow server not running) ───\n"
        "LOG_TO_MLFLOW = False  # Set True if MLflow is running\n\n"
        "if LOG_TO_MLFLOW:\n"
        "    from src.alpha_research.mlflow_tracker import ExperimentTracker\n"
        "    tracker = ExperimentTracker(config_path=os.path.join(PROJECT_ROOT, 'config.yaml'))\n"
        "    tracker.start_run(run_name='ml_lgb_walkforward')\n\n"
        "    # Params\n"
        "    tracker.log_params({\n"
        "        'model': 'LightGBM',\n"
        "        'n_features': len(feature_cols),\n"
        "        'fwd_days': FWD_DAYS,\n"
        "        'train_years': TRAIN_YEARS,\n"
        "        'valid_years': VALID_YEARS,\n"
        "        'test_years': TEST_YEARS,\n"
        "        'n_folds': len(folds),\n"
        "        'topk': 50,\n"
        "        'n_drop': 5,\n"
        "    })\n\n"
        "    # OOS metrics\n"
        "    tracker.log_metrics({\n"
        "        'oos_rank_ic': oos_summary.get('mean_rank_ic', 0),\n"
        "        'oos_rank_icir': oos_summary.get('rank_icir', 0),\n"
        "        **{k: v for k, v in result_ml.summary.items() if isinstance(v, (int, float))},\n"
        "    })\n\n"
        "    tracker.end_run()\n"
        "    print('Logged to MLflow')\n"
        "else:\n"
        "    print('MLflow logging skipped (set LOG_TO_MLFLOW = True to enable)')"
    ))

    # ═══════════════════════════════════════════════════════════════
    # §10: CONCLUSION
    # ═══════════════════════════════════════════════════════════════
    cells.append(new_markdown_cell(
        "## Summary\n\n"
        "| Aspect | Detail |\n"
        "|--------|--------|\n"
        "| Model | LightGBM (gradient boosting) |\n"
        "| Features | ~60 engineered alpha factors |\n"
        "| Validation | Walk-forward (3yr/1yr/1yr) |\n"
        "| Strategy | TopkDropout(50), daily rebalance |\n"
        "| Benchmark | CSI 300 (000300_SH) |\n\n"
        "### Next Steps\n"
        "1. **Hyperparameter tuning** — Optuna/Hyperopt search over LightGBM params\n"
        "2. **Feature selection** — Drop features below importance threshold\n"
        "3. **Ensemble** — Combine LightGBM + XGBoost + linear for diversity\n"
        "4. **Rebalance frequency** — Test weekly/monthly instead of daily\n"
        "5. **Risk overlay** — Add drawdown control and position sizing"
    ))

    return nb


def main():
    """Generate the ML strategy notebook."""
    nb = build_notebook()
    output_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "research", "alpha_factors",
    )
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "ml_strategy.ipynb")
    with open(output_path, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)
    print(f"Notebook generated: {os.path.abspath(output_path)}")
    print(f"  Cells: {len(nb.cells)}")
    code_cells = sum(1 for c in nb.cells if c.cell_type == "code")
    md_cells = sum(1 for c in nb.cells if c.cell_type == "markdown")
    print(f"  Code cells: {code_cells}")
    print(f"  Markdown cells: {md_cells}")


if __name__ == "__main__":
    main()
