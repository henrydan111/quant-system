"""Rebuild ``st_stocks.txt`` from local raw reference data.

This wrapper keeps the historical script name, but it no longer fetches raw
data directly from Tushare. Routine raw refreshes should happen through the
main pipeline; this script only rebuilds the derived Qlib instrument file.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from data_infra.provider_metadata import build_st_universe, write_instruments_readme


log_dir = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler(
            os.path.join(log_dir, "build_st_universe.log"),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild st_stocks.txt from local reference data")
    parser.add_argument("--data-root", type=str, default=os.path.join(PROJECT_ROOT, "data"))
    parser.add_argument(
        "--output-path",
        type=str,
        default=None,
        help="Override output path (default: data/qlib_data/instruments/st_stocks.txt)",
    )
    parser.add_argument("--skip-readme", action="store_true", help="Do not refresh the instruments README")
    args = parser.parse_args()

    data_root = args.data_root
    output_path = args.output_path or os.path.join(data_root, "qlib_data", "instruments", "st_stocks.txt")
    instruments_dir = os.path.dirname(output_path)

    trade_cal_path = os.path.join(data_root, "reference", "trade_cal.parquet")
    stock_st_path = os.path.join(data_root, "reference", "stock_st_daily.parquet")
    namechange_path = os.path.join(data_root, "reference", "namechange.parquet")

    for required_path in (trade_cal_path, stock_st_path, namechange_path):
        if not os.path.exists(required_path):
            raise FileNotFoundError(f"Required input missing: {required_path}")

    trade_cal = pd.read_parquet(trade_cal_path)
    open_calendar = pd.DatetimeIndex(pd.to_datetime(trade_cal.loc[trade_cal["is_open"] == 1, "cal_date"]))
    build_st_universe(
        stock_st_daily=pd.read_parquet(stock_st_path),
        namechange=pd.read_parquet(namechange_path),
        trading_calendar=open_calendar,
        output_path=output_path,
    )
    if not args.skip_readme:
        write_instruments_readme(instruments_dir)
    logger.info("ST universe rebuilt at %s", output_path)


if __name__ == "__main__":
    main()
