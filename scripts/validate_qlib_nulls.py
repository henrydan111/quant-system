"""
Qlib Database Integrity Validation: Null/NaN Check (Parallel)

Scans all stock feature .bin files in data/qlib_data/features/ and reports
any features containing NaN values. Uses multiprocessing for speed.

Qlib binary format: each .bin file is a flat array of float32 values.
NaN in float32 represents missing/null data.
"""
import os
import sys
import json
import numpy as np
from collections import defaultdict
from datetime import datetime
from multiprocessing import Pool, cpu_count

# --- Configuration ---
QLIB_FEATURES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  'data', 'qlib_data', 'features')
CALENDAR_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                              'data', 'qlib_data', 'calendars', 'day.txt')
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')


def load_calendar(cal_path):
    """Load trading calendar dates."""
    dates = []
    with open(cal_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                dates.append(line)
    return dates


def scan_stock(stock_dir):
    """Scan all .bin files for a single stock directory.

    Args:
        stock_dir: Name of the stock subdirectory.

    Returns:
        Dict with stock-level and feature-level NaN statistics.
    """
    stock_path = os.path.join(QLIB_FEATURES_DIR, stock_dir)
    bin_files = sorted([
        f for f in os.listdir(stock_path) if f.endswith('.day.bin')
    ])

    stock_nan_count = 0
    stock_total_values = 0
    feature_results = []  # (feature_name, num_values, nan_count)

    for bf in bin_files:
        feature_name = bf.replace('.day.bin', '')
        filepath = os.path.join(stock_path, bf)
        data = np.fromfile(filepath, dtype='<f')
        nan_count = int(np.isnan(data).sum())
        num_values = len(data)

        stock_nan_count += nan_count
        stock_total_values += num_values
        feature_results.append((feature_name, num_values, nan_count))

    return {
        'stock': stock_dir,
        'total_nans': stock_nan_count,
        'total_values': stock_total_values,
        'total_features': len(bin_files),
        'feature_results': feature_results
    }


def main():
    """Run the full Qlib NaN validation scan with multiprocessing."""
    start_time = datetime.now()
    print("=" * 80)
    print("  Qlib Database Integrity Validation - NaN/Null Check")
    print(f"  Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print(flush=True)

    # Load calendar
    calendar = load_calendar(CALENDAR_FILE)
    print(f"Calendar: {len(calendar)} trading days "
          f"({calendar[0]} -> {calendar[-1]})")

    # Enumerate stock directories
    stock_dirs = sorted([
        d for d in os.listdir(QLIB_FEATURES_DIR)
        if os.path.isdir(os.path.join(QLIB_FEATURES_DIR, d))
    ])
    total_stocks = len(stock_dirs)
    num_workers = min(cpu_count(), 8)
    print(f"Stocks: {total_stocks} | Workers: {num_workers}")
    print(flush=True)

    # --- Parallel scan ---
    results = []
    with Pool(processes=num_workers) as pool:
        for i, result in enumerate(pool.imap_unordered(scan_stock, stock_dirs,
                                                        chunksize=50)):
            results.append(result)
            done = len(results)
            if done % 500 == 0 or done == total_stocks:
                elapsed_so_far = (datetime.now() - start_time).total_seconds()
                print(f"  Progress: {done}/{total_stocks} "
                      f"({done/total_stocks*100:.1f}%) - "
                      f"{elapsed_so_far:.0f}s", flush=True)

    elapsed = (datetime.now() - start_time).total_seconds()

    # --- Aggregate ---
    feature_stats = defaultdict(lambda: {
        'total_stocks': 0, 'stocks_with_nans': 0,
        'total_values': 0, 'total_nans': 0,
        'worst_stock': None, 'worst_nan_pct': 0.0
    })

    stocks_with_issues = []
    stocks_clean = 0
    total_files_scanned = 0
    total_nans_global = 0
    total_values_global = 0

    for r in results:
        n_files = r['total_features']
        total_files_scanned += n_files
        total_nans_global += r['total_nans']
        total_values_global += r['total_values']

        features_with_nans_count = 0
        for feat_name, num_values, nan_count in r['feature_results']:
            fs = feature_stats[feat_name]
            fs['total_stocks'] += 1
            fs['total_values'] += num_values
            fs['total_nans'] += nan_count
            if nan_count > 0:
                features_with_nans_count += 1
                fs['stocks_with_nans'] += 1
                pct = (nan_count / num_values * 100) if num_values > 0 else 0
                if pct > fs['worst_nan_pct']:
                    fs['worst_nan_pct'] = pct
                    fs['worst_stock'] = r['stock']

        if r['total_nans'] > 0:
            stocks_with_issues.append({
                'stock': r['stock'],
                'total_nans': r['total_nans'],
                'total_values': r['total_values'],
                'nan_pct': (r['total_nans'] / r['total_values'] * 100
                            if r['total_values'] > 0 else 0),
                'features_with_nans': features_with_nans_count,
                'total_features': n_files
            })
        else:
            stocks_clean += 1

    # ------------------------------------------------------------------ #
    #  REPORT
    # ------------------------------------------------------------------ #
    global_nan_pct = ((total_nans_global / total_values_global * 100)
                      if total_values_global > 0 else 0)

    print()
    print("=" * 80)
    print("  VALIDATION REPORT")
    print("=" * 80)
    print()

    print("## Executive Summary")
    print(f"  Scan Duration:        {elapsed:.1f} seconds")
    print(f"  Stocks Scanned:       {total_stocks}")
    print(f"  Files Scanned:        {total_files_scanned:,}")
    print(f"  Total Values Checked: {total_values_global:,}")
    print(f"  Total NaN Values:     {total_nans_global:,}")
    print(f"  Global NaN Rate:      {global_nan_pct:.4f}%")
    print(f"  Stocks Clean (0 NaN): {stocks_clean}")
    print(f"  Stocks with NaNs:     {len(stocks_with_issues)}")
    print()

    if not stocks_with_issues:
        print("  PASS: DATABASE IS FULLY CLEAN - No null values found.")
        _save_json(start_time, elapsed, total_stocks, total_files_scanned,
                   total_values_global, total_nans_global, global_nan_pct,
                   stocks_clean, [], [])
        return

    # Feature-level summary
    features_with_nans = {k: v for k, v in feature_stats.items()
                          if v['total_nans'] > 0}
    features_sorted = sorted(features_with_nans.items(),
                              key=lambda x: x[1]['total_nans'], reverse=True)

    print(f"## Feature-Level Summary "
          f"({len(features_sorted)} features with NaN values)")
    print(f"  {'Feature':<42} {'StocksNaN':>10} {'TotalNaN':>12} "
          f"{'NaN%':>7} {'WorstStock':<18} {'Worst%':>7}")
    print(f"  {'-'*40}  {'-'*10} {'-'*12} "
          f"{'-'*7} {'-'*18} {'-'*7}")
    for feat_name, fs in features_sorted:
        nan_pct = ((fs['total_nans'] / fs['total_values'] * 100)
                   if fs['total_values'] > 0 else 0)
        ws = fs['worst_stock'] or 'N/A'
        wp = fs['worst_nan_pct']
        print(f"  {feat_name:<42} {fs['stocks_with_nans']:>10} "
              f"{fs['total_nans']:>12,} {nan_pct:>6.2f}% "
              f"{ws:<18} {wp:>6.1f}%")
    print()

    # Category breakdown
    market_features = {
        'open', 'high', 'low', 'close', 'pre_close', 'change', 'pct_chg',
        'vol', 'volume', 'amount', 'turnover_rate', 'turnover_rate_f',
        'volume_ratio', 'pe', 'pe_ttm', 'pb', 'ps', 'ps_ttm',
        'dv_ratio', 'dv_ttm', 'total_share', 'float_share', 'free_share',
        'total_mv', 'circ_mv', 'adj_factor', 'factor'
    }

    mkt_nan_feats = [f for f in features_sorted if f[0] in market_features]
    funda_nan_feats = [f for f in features_sorted
                       if f[0] not in market_features]

    print("## Category Breakdown")
    print(f"  Market/Daily features with NaN:       {len(mkt_nan_feats)}")
    print(f"  Fundamental/Other features with NaN:  {len(funda_nan_feats)}")
    print()

    if mkt_nan_feats:
        print("  ### Market Features with NaN:")
        for feat_name, fs in mkt_nan_feats:
            nan_pct = ((fs['total_nans'] / fs['total_values'] * 100)
                       if fs['total_values'] > 0 else 0)
            print(f"    - {feat_name}: {fs['stocks_with_nans']} stocks, "
                  f"{fs['total_nans']:,} NaNs ({nan_pct:.2f}%)")
        print()

    # Top 50 worst stocks
    stocks_sorted = sorted(stocks_with_issues,
                            key=lambda x: x['nan_pct'], reverse=True)
    top_n = min(50, len(stocks_sorted))
    print(f"## Top {top_n} Stocks by NaN Rate")
    print(f"  {'Stock':<18} {'NaN Values':>12} {'Total Values':>14} "
          f"{'NaN%':>7} {'FeatNaN':>8}/{'Total':>6}")
    print(f"  {'-'*16}  {'-'*12} {'-'*14} "
          f"{'-'*7} {'-'*8} {'-'*6}")
    for s in stocks_sorted[:top_n]:
        print(f"  {s['stock']:<18} {s['total_nans']:>12,} "
              f"{s['total_values']:>14,} {s['nan_pct']:>6.2f}% "
              f"{s['features_with_nans']:>8}/{s['total_features']:>5}")
    print()

    # Distribution
    print(f"## NaN Rate Distribution Across All {total_stocks} Stocks")
    ranges = [
        ('0% (clean)',  lambda p: p == 0),
        ('0-10%',       lambda p: 0 < p <= 10),
        ('10-25%',      lambda p: 10 < p <= 25),
        ('25-50%',      lambda p: 25 < p <= 50),
        ('50-75%',      lambda p: 50 < p <= 75),
        ('75-90%',      lambda p: 75 < p <= 90),
        ('90-100%',     lambda p: 90 < p <= 100),
    ]

    all_pcts = ([0.0] * stocks_clean
                + [s['nan_pct'] for s in stocks_with_issues])

    for name, cond in ranges:
        count = sum(1 for p in all_pcts if cond(p))
        bar_len = int(count / total_stocks * 50)
        bar = '#' * bar_len
        print(f"  {name:<15} {count:>6} stocks "
              f"({count/total_stocks*100:>5.1f}%)  {bar}")
    print()

    _save_json(start_time, elapsed, total_stocks, total_files_scanned,
               total_values_global, total_nans_global, global_nan_pct,
               stocks_clean, features_sorted, stocks_sorted)


def _save_json(start_time, elapsed, total_stocks, total_files,
               total_values, total_nans, nan_pct,
               stocks_clean, features_sorted, stocks_sorted):
    """Persist a JSON summary to logs/."""
    report = {
        'scan_timestamp': start_time.isoformat(),
        'duration_seconds': round(elapsed, 1),
        'total_stocks': total_stocks,
        'total_files': total_files,
        'total_values': total_values,
        'total_nans': total_nans,
        'global_nan_rate_pct': round(nan_pct, 4),
        'stocks_clean': stocks_clean,
        'stocks_with_issues': total_stocks - stocks_clean,
        'features_with_nans_count': len(features_sorted),
        'top10_worst_features': [
            {
                'feature': f[0],
                'total_nans': f[1]['total_nans'],
                'stocks_affected': f[1]['stocks_with_nans'],
                'nan_pct': round(
                    f[1]['total_nans'] / f[1]['total_values'] * 100, 2
                ) if f[1]['total_values'] > 0 else 0
            }
            for f in features_sorted[:10]
        ],
        'top10_worst_stocks': [
            {
                'stock': s['stock'],
                'nan_pct': round(s['nan_pct'], 2),
                'total_nans': s['total_nans'],
                'features_with_nans': s['features_with_nans']
            }
            for s in stocks_sorted[:10]
        ]
    }
    os.makedirs(LOG_DIR, exist_ok=True)
    report_path = os.path.join(LOG_DIR, 'qlib_null_validation.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"  JSON summary saved to: {report_path}")
    print()
    print("=" * 80)
    print("  Validation Complete")
    print("=" * 80)


if __name__ == '__main__':
    main()
