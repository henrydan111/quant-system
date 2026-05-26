# ──────────────────────────────────────────────────────────────────────
# PR 7 of 2026-05-26 freeze plan — SCRIPT_STATUS header block.
# script_status: formal_candidate
# formal_research_allowed: true
# deployment_target: joinquant_daily
# execution_profile: joinquant_daily_sim
# requires_provider_manifest: true
# requires_preload_strict: true
# pr2_audit_class: B
# notes: |
#   Uses QlibDataFeeder directly. Must call
#   feeder.preload_features(..., strict=True) for engine-required
#   fields before any get_features call. See
#   src/backtest_engine/event_driven/constants.py::ENGINE_REQUIRED_FIELDS.
# ──────────────────────────────────────────────────────────────────────
"""
Local Data Dump — matches jq_data_verify.py output format.
Dumps PE_TTM, market_cap, close, volume, 20d momentum for CSI300 main-board stocks
on the same 3 sample dates for comparison with JQ data.
"""
import sys
import os
sys.path.insert(0, r'e:\量化系统')

import pandas as pd
import numpy as np

SAMPLE_DATES = ['2023-12-29', '2024-04-30', '2024-09-30']
DATA_DIR = r'e:\量化系统\data'
OUTPUT_PATH = os.path.join(r'e:\量化系统\workspace\outputs', 'local_factor_dump.csv')

if __name__ == '__main__':
    from src.backtest_engine.event_driven.data_feeder import QlibDataFeeder

    feeder = QlibDataFeeder(data_dir=DATA_DIR)

    # Preload all features for the entire range
    fields = ['$open', '$close', '$high', '$low', '$vol', '$pre_close',
              '$pe_ttm', '$pb', '$total_mv', '$turnover_rate']
    feeder.preload_features('all', fields, '2023-12-01', '2024-10-05')

    all_records = []

    for sample_date in SAMPLE_DATES:
        # Get CSI300 constituents
        dt = pd.Timestamp(sample_date)
        csi300 = feeder.get_index_constituents('csi300', dt)

        # Filter: main board only
        main_board = [
            s for s in csi300
            if s[:3] not in ('300', '301', '688', '689')
            and s[0] not in ('8', '4', '9')
        ]

        # Get features for this date
        df = feeder.get_features(main_board, fields, sample_date, sample_date)
        if df.empty:
            print(f"WARNING: no data for {sample_date}")
            continue

        df = df.reset_index()
        df = df.rename(columns={'instrument': 'code'})
        if 'datetime' in df.columns:
            df = df.drop(columns=['datetime'])

        # Get 20d history for momentum
        dt_20d_ago = feeder.get_prev_trading_day(dt)
        for i in range(19):
            dt_20d_ago = feeder.get_prev_trading_day(dt_20d_ago)

        hist_df = feeder.get_features(main_board, ['$close'], 
                                       dt_20d_ago.strftime('%Y-%m-%d'),
                                       sample_date)
        mom_dict = {}
        if not hist_df.empty:
            hist_df = hist_df.reset_index()
            for code in main_board:
                stock_hist = hist_df[hist_df['instrument'] == code]['$close'].values
                if len(stock_hist) >= 21 and stock_hist[0] > 0:
                    mom_dict[code] = stock_hist[-1] / stock_hist[0] - 1

        for _, row in df.iterrows():
            code = row['code']
            # Convert total_mv from 万元 to 亿元
            mv_yi = row.get('$total_mv', np.nan) / 10000 if not pd.isna(row.get('$total_mv', np.nan)) else np.nan

            all_records.append({
                'date': sample_date,
                'code': code,
                'close': round(row.get('$close', np.nan), 4) if not pd.isna(row.get('$close', np.nan)) else np.nan,
                'open': round(row.get('$open', np.nan), 4) if not pd.isna(row.get('$open', np.nan)) else np.nan,
                'high': round(row.get('$high', np.nan), 4) if not pd.isna(row.get('$high', np.nan)) else np.nan,
                'low': round(row.get('$low', np.nan), 4) if not pd.isna(row.get('$low', np.nan)) else np.nan,
                'pre_close': round(row.get('$pre_close', np.nan), 4) if not pd.isna(row.get('$pre_close', np.nan)) else np.nan,
                'volume': row.get('$vol', np.nan),
                'pe_ttm': round(row.get('$pe_ttm', np.nan), 4) if not pd.isna(row.get('$pe_ttm', np.nan)) else np.nan,
                'market_cap_yi': round(mv_yi, 4) if not pd.isna(mv_yi) else np.nan,
                'pb': round(row.get('$pb', np.nan), 4) if not pd.isna(row.get('$pb', np.nan)) else np.nan,
                'turnover': round(row.get('$turnover_rate', np.nan), 4) if not pd.isna(row.get('$turnover_rate', np.nan)) else np.nan,
                'mom_20d': round(mom_dict.get(code, np.nan), 6),
            })

    result_df = pd.DataFrame(all_records)
    print(f"Total rows: {len(result_df)}")
    print(f"Dates: {sorted(result_df['date'].unique())}")
    print(f"Stocks per date: {result_df.groupby('date').size().to_dict()}")
    print()
    print("Sample (first 5 per date):")
    print(result_df.groupby('date').head(5).to_string(index=False))

    result_df.to_csv(OUTPUT_PATH, index=False)
    print(f"\n✅ Saved to {OUTPUT_PATH}")
