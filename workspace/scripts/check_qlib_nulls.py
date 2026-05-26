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
import qlib
from qlib.data import D
import warnings
import pandas as pd
import numpy as np
import os

warnings.filterwarnings('ignore')

def main():
    print("Initialize Qlib...")
    qlib.init(provider_uri='E:/量化系统/data/qlib_data')

    print("Fetching universe and features...")
    # Get instruments and features
    instruments = 'all_stocks'
    
    # D.list_features() returns what features exist
    features_list = [f for f in D.list_features() if f is not None]
    print(f"Total Features found: {len(features_list)}")
    
    all_summary = []
    
    batch_size = 5
    for i in range(0, len(features_list), batch_size):
        batch = features_list[i:i+batch_size]
        print(f"Evaluating batch {i//batch_size + 1}: {batch}")
        
        try:
            # Query default features for all_stocks over all available dates
            df = D.features(instruments, batch, freq='day')
            
            for feature in batch:
                if feature in df.columns:
                    col_data = df[feature]
                    total_points = len(col_data)
                    null_points = col_data.isna().sum()
                    null_ratio = null_points / total_points if total_points > 0 else 1.0
                    
                    all_summary.append({
                        'Feature': feature,
                        'Total Data Points': total_points,
                        'Null Points': null_points,
                        'Null Ratio': round(null_ratio, 4)
                    })
        except Exception as e:
            print(f"Error querying batch {batch}: {e}")

    if not all_summary:
        print("No features processed successfully.")
        return

    report_df = pd.DataFrame(all_summary)
    report_df = report_df.sort_values(by='Null Ratio', ascending=False)
    
    os.makedirs('workspace/outputs', exist_ok=True)
    report_path = 'E:/量化系统/workspace/outputs/qlib_null_validation.csv'
    report_df.to_csv(report_path, index=False)
    
    print(f"\nReport saved to: {report_path}")
    print("\nTop 10 features with most nulls:")
    print(report_df.head(10).to_string(index=False))

    null_free = len(report_df[report_df['Null Ratio'] == 0])
    print(f"\n{null_free}/{len(report_df)} features have no missing values across available stock dates.")

if __name__ == '__main__':
    main()
