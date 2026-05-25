import sys
import os
import pandas as pd
from datetime import datetime

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))
sys.path.insert(0, os.path.join(project_root, 'src'))

from data_infra.storage import StorageManager

def test_storage():
    print("Testing StorageManager...")
    
    # 1. Create fake data
    output_root = os.path.join(project_root, 'workspace', 'outputs', 'storage_smoke')
    test_dir = os.path.join(output_root, 'test_raw')
    out_dir = os.path.join(output_root, 'test_qlib')
    
    sm = StorageManager(data_root=test_dir)
    
    df1 = pd.DataFrame({
        'ts_code': ['000001.SZ', '000002.SZ'],
        'trade_date': ['20240101', '20240101'],
        'open': [10.0, 20.0],
        'high': [10.5, 20.5],
        'low': [9.5, 19.5],
        'close': [10.2, 20.1],
        'vol': [1000, 2000],
        'amount': [10200, 40200],
        'adj_factor': [1.5, 2.0]
    })
    
    df2 = pd.DataFrame({
        'ts_code': ['000001.SZ', '000002.SZ'],
        'trade_date': ['20240102', '20240102'],
        'open': [10.2, 20.1],
        'high': [11.0, 21.0],
        'low': [10.0, 19.8],
        'close': [10.8, 20.9],
        'vol': [1500, 2500],
        'amount': [15500, 52000],
        'adj_factor': [1.5, 2.0]
    })
    
    # Insert fake data
    sm.insert_daily_data(df1)
    sm.insert_daily_data(df2)
    print(f"Fake data inserted. Parquets created in {test_dir}")
    
    # Export to Qlib
    print("Starting export_to_qlib (mode=all)...")
    sm.export_to_qlib(dest_dir=out_dir, mode='all')
    print("Export complete.")
    
    # Verify
    features_dir = os.path.join(out_dir, "features", "sh000001")
    if os.path.exists(features_dir):
        print(f"Success! Features generated at {features_dir}")
        print("Files:", os.listdir(features_dir)[:3])
    else:
        print(f"Failure. Features dir not found: {features_dir}")

if __name__ == "__main__":
    test_storage()
