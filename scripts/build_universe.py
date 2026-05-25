"""Rebuild provider universe sidecars from observed raw data."""

from __future__ import annotations

import os
import sys

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from data_infra.provider_metadata import (
    build_all_stocks_universe,
    build_index_universes,
    build_st_universe,
    write_instruments_readme,
)


def main() -> None:
    data_root = os.path.join(PROJECT_ROOT, "data")
    qlib_dir = os.path.join(data_root, "qlib_data")
    instruments_dir = os.path.join(qlib_dir, "instruments")
    metadata_dir = os.path.join(qlib_dir, "metadata")

    stock_basic = pd.read_parquet(os.path.join(data_root, "reference", "stock_basic.parquet"))
    daily_files = sorted(
        os.path.join(root, name)
        for root, _, files in os.walk(os.path.join(data_root, "market", "daily"))
        for name in files
        if name.endswith(".parquet")
    )
    price_ranges = pd.concat(
        [
            pd.read_parquet(path, columns=["ts_code", "trade_date"])
            for path in daily_files
        ],
        ignore_index=True,
    )
    price_ranges["trade_date"] = pd.to_datetime(price_ranges["trade_date"], errors="coerce")
    price_ranges = (
        price_ranges.groupby("ts_code")["trade_date"]
        .agg(price_start="min", price_end="max")
        .reset_index()
    )
    price_ranges["qlib_code"] = price_ranges["ts_code"].str.replace(".", "_", regex=False).str.upper()

    build_all_stocks_universe(stock_basic, price_ranges, instruments_dir, metadata_dir)

    index_weights_dir = os.path.join(data_root, "universe", "index_weights")
    index_files = sorted(
        os.path.join(index_weights_dir, name)
        for name in os.listdir(index_weights_dir)
        if name.endswith(".parquet")
    )
    if index_files:
        weights = pd.concat([pd.read_parquet(path) for path in index_files], ignore_index=True)
        build_index_universes(weights, instruments_dir)

    trade_cal = pd.read_parquet(os.path.join(data_root, "reference", "trade_cal.parquet"))
    open_calendar = pd.DatetimeIndex(pd.to_datetime(trade_cal.loc[trade_cal["is_open"] == 1, "cal_date"]))
    build_st_universe(
        stock_st_daily=pd.read_parquet(os.path.join(data_root, "reference", "stock_st_daily.parquet")),
        namechange=pd.read_parquet(os.path.join(data_root, "reference", "namechange.parquet")),
        trading_calendar=open_calendar,
        output_path=os.path.join(instruments_dir, "st_stocks.txt"),
    )
    write_instruments_readme(instruments_dir)


if __name__ == "__main__":
    main()
