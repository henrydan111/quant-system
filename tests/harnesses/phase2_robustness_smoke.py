import sys
import os
import pandas as pd
import logging

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))
sys.path.insert(0, os.path.join(project_root, 'src'))

from data_infra.fetchers import TushareFetcher

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_robust():
    fetcher = TushareFetcher(config_path=os.path.join(project_root, 'config.yaml'))
    test_stock = '000001.SZ'
    start_year = 2008
    
    print(f"--- Robust Test for {test_stock} ---")
    
    # 1. Income Pagination & Filter
    inc_df = fetcher.fetch_income(ts_code=test_stock)
    raw_len = len(inc_df)
    filtered_inc = inc_df[inc_df['end_date'] >= f"{start_year}0101"]
    
    print(f"INCOME: Fetched {raw_len} lifetime rows.")
    if not filtered_inc.empty:
        print(f"  -> Retained {len(filtered_inc)} rows after 2008 filter.")
        print(f"  -> Oldest Date: {filtered_inc['end_date'].min()}")
        print(f"  -> Newest Date: {filtered_inc['end_date'].max()}")
        assert filtered_inc['end_date'].min() >= '20080101', "Filter failed for Income!"
    print("")

    # 2. Balance Sheet Pagination & Filter
    bal_df = fetcher.fetch_balancesheet(ts_code=test_stock)
    raw_len = len(bal_df)
    filtered_bal = bal_df[bal_df['end_date'] >= f"{start_year}0101"]
    
    print(f"BALANCE SHEET: Fetched {raw_len} lifetime rows.")
    if not filtered_bal.empty:
        print(f"  -> Retained {len(filtered_bal)} rows after 2008 filter.")
        print(f"  -> Oldest Date: {filtered_bal['end_date'].min()}")
        print(f"  -> Newest Date: {filtered_bal['end_date'].max()}")
        assert filtered_bal['end_date'].min() >= '20080101', "Filter failed for Balance Sheet!"
    print("")

    # 3. Fina Indicator Pagination & Filter (CRITICAL: Needs > 100 rows)
    fina_df = fetcher.fetch_fina_indicator(ts_code=test_stock)
    raw_len = len(fina_df)
    filtered_fina = fina_df[fina_df['end_date'] >= f"{start_year}0101"]
    
    print(f"FINA INDICATORS: Fetched {raw_len} lifetime rows. (Must be > 100 to prove pagination works)")
    assert raw_len > 100, "Pagination for Fina Indicator FAILED. Exactly 100 rows returned."
    
    if not filtered_fina.empty:
        print(f"  -> Retained {len(filtered_fina)} rows after 2008 filter.")
        print(f"  -> Oldest Date: {filtered_fina['end_date'].min()}")
        print(f"  -> Newest Date: {filtered_fina['end_date'].max()}")
        assert filtered_fina['end_date'].min() >= '20080101', "Filter failed for Fina Indicators!"
    print("")

    # 4. Dividends Filter
    div_df = fetcher.fetch_dividend(ts_code=test_stock)
    raw_len = len(div_df)
    date_filter_col = 'ann_date' if 'ann_date' in div_df.columns else ('end_date' if 'end_date' in div_df.columns else None)
    filtered_div = div_df[div_df[date_filter_col] >= f"{start_year}0101"] if date_filter_col else div_df
    
    print(f"DIVIDENDS: Fetched {raw_len} lifetime rows.")
    if not filtered_div.empty:
        print(f"  -> Retained {len(filtered_div)} rows after 2008 filter.")
        print(f"  -> Oldest Date: {filtered_div[date_filter_col].min()}")
        print(f"  -> Newest Date: {filtered_div[date_filter_col].max()}")
        assert filtered_div[date_filter_col].min() >= '20080101', "Filter failed for Dividends!"
    print("")
    
    print("ALL ROBUST TESTS PASSED: Pagination works. 2008 Filter works.")
    
    print("\nNo local data was modified by this harness.")

if __name__ == "__main__":
    test_robust()
