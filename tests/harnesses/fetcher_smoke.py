import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from data_infra.fetchers import TushareFetcher

def test_fetcher():
    config_path = os.path.join(PROJECT_ROOT, 'config.yaml')
    
    fetcher = TushareFetcher(config_path=config_path)
    
    # 1. Test fetching all stocks (L, D, P)
    print("Fetching stock basic...")
    df_stocks = fetcher.fetch_stock_basic()
    print(f"Total stocks fetched: {len(df_stocks)}")
    print(df_stocks.head(3))
    
    # 2. Test fetching index daily
    print("\nFetching index daily (000001.SH) for last 5 days...")
    df_index = fetcher.fetch_index_daily(ts_code='000001.SH', start_date='20240101', end_date='20240108')
    print(f"Index rows fetched: {len(df_index)}")
    print(df_index.head())

if __name__ == "__main__":
    test_fetcher()
