import os
import pandas as pd
import logging
import glob
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import Manager

logger = logging.getLogger(__name__)

class DataAuditor:
    def __init__(self, data_root=None):
        if data_root is not None:
            self.data_root = data_root
        else:
            # Resolve from config.yaml relative to project root
            import yaml
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            config_path = os.path.join(project_root, 'config.yaml')
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            self.data_root = os.path.normpath(
                os.path.join(project_root, config['storage']['data_root'])
            )
        self.market_daily_dir = os.path.join(self.data_root, 'market', 'daily')
        self.ref_dir = os.path.join(self.data_root, 'reference')
        
    def _load_reference_data(self):
        """Load stock_basic and trade_cal to know expectations."""
        try:
            stock_basic = pd.read_parquet(os.path.join(self.ref_dir, "stock_basic.parquet"))
            trade_cal = pd.read_parquet(os.path.join(self.ref_dir, "trade_cal.parquet"))
            # convert dates for easier comparison
            trade_cal['cal_date'] = pd.to_datetime(trade_cal['cal_date']).dt.strftime('%Y%m%d')
            stock_basic['list_date'] = pd.to_datetime(stock_basic['list_date'], errors='coerce').dt.strftime('%Y%m%d')
            stock_basic['delist_date'] = pd.to_datetime(stock_basic['delist_date'], errors='coerce').dt.strftime('%Y%m%d')
            return stock_basic, trade_cal
        except Exception as e:
            logger.error(f"Failed to load reference data: {e}")
            return None, None

    def _get_expected_symbols_for_date(self, stock_basic: pd.DataFrame, target_date_str: str) -> set:
        """Find symbols that should have traded on target_date_str."""
        # Condition: list_date <= target_date AND (delist_date is null OR delist_date >= target_date)
        mask_listed = stock_basic['list_date'] <= target_date_str
        
        # handle nan in delist_date
        mask_not_delisted = (stock_basic['delist_date'].isna()) | (stock_basic['delist_date'] >= target_date_str)
        
        valid_stocks = stock_basic[mask_listed & mask_not_delisted]
        return set(valid_stocks['ts_code'])

    def audit_daily_files(self, start_date=None, end_date=None, check_nulls=True):
        """
        Scan through data/market/daily Parquet files.
        Returns a dictionary or list summarizing anomalies.
        """
        stock_basic, trade_cal = self._load_reference_data()
        if stock_basic is None or trade_cal is None:
            return {"error": "Missing Reference Data"}
            
        # Filter trade calendar
        valid_days = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist()
        if start_date:
            valid_days = [d for d in valid_days if d >= start_date]
        if end_date:
            valid_days = [d for d in valid_days if d <= end_date]
            
        all_daily_files = glob.glob(os.path.join(self.market_daily_dir, "*", "daily_*.parquet"))
        
        # Map date to file path
        date_file_map = {}
        for f in all_daily_files:
            basename = os.path.basename(f)
            # expected naming: daily_YYYYMMDD.parquet
            date_str = basename.replace("daily_", "").replace(".parquet", "")
            date_file_map[date_str] = f

        report = {
            "missing_dates": [],
            "anomalies": [] # list of dicts: {"date": x, "type": "Missing Stocks", "details": ...}
        }
        
        logger.info(f"Auditing {len(valid_days)} trading days...")
        
        for t_date in valid_days:
            if t_date not in date_file_map:
                report["missing_dates"].append(t_date)
                continue
                
            file_path = date_file_map[t_date]
            try:
                # Load parquet
                df = pd.read_parquet(file_path)
                found_symbols = set(df['ts_code'])
                expected_symbols = self._get_expected_symbols_for_date(stock_basic, t_date)
                
                # Check 1: Missing expectations
                missing_symbols = list(expected_symbols - found_symbols)
                
                # We expect some to be suspended, suspend_d is better checked, but for simplicity:
                # Flag if missing ratio > 15% (which indicates an API failure, not just suspensions)
                if expected_symbols:
                    missing_ratio = len(missing_symbols) / len(expected_symbols)
                    if missing_ratio > 0.15:
                        report["anomalies"].append({
                            "date": t_date,
                            "type": "High Missing Ratio",
                            "message": f"Missing {len(missing_symbols)} stocks ({missing_ratio:.1%} out of {len(expected_symbols)})"
                        })
                
                # Check 2: Nulls in core fields
                if check_nulls:
                    critical_cols = ['open', 'high', 'low', 'close', 'vol']
                    null_counts = df[critical_cols].isnull().sum()
                    if null_counts.sum() > 0:
                        report["anomalies"].append({
                            "date": t_date,
                            "type": "Null Values Found",
                            "message": null_counts.to_dict()
                        })
                        
            except Exception as e:
                report["anomalies"].append({
                    "date": t_date,
                    "type": "File Read Error",
                    "message": str(e)
                })
                
        return report
