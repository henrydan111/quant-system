"""End-to-end PIT pipeline harness using a tiny isolated mock database."""

from __future__ import annotations

import os
import shutil
import sys

import pandas as pd
import qlib
from qlib.data import D


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from data_infra.pipeline.build_qlib_backend import build_unified_qlib
from data_infra.storage import StorageManager


def test_pipeline_e2e() -> None:
    """Verify next-trading-day PIT visibility on a tiny mock dataset."""
    print("--- 1. Setting up isolated mock database ---")
    output_root = os.path.join(PROJECT_ROOT, "workspace", "outputs", "pipeline_e2e_harness")
    test_data_root = os.path.join(output_root, "data_test_mock")
    test_qlib_dir = os.path.join(test_data_root, "qlib_data")

    if os.path.exists(test_data_root):
        shutil.rmtree(test_data_root)

    os.makedirs(test_data_root, exist_ok=True)
    os.makedirs(test_qlib_dir, exist_ok=True)

    os.makedirs(os.path.join(test_data_root, "reference"), exist_ok=True)
    cal_dates = pd.date_range("2024-01-01", "2024-01-14", freq="B")
    cal_df = pd.DataFrame({"cal_date": cal_dates.strftime("%Y%m%d"), "is_open": 1})
    cal_df.to_parquet(os.path.join(test_data_root, "reference", "trade_cal.parquet"), index=False)

    storage = StorageManager(data_root=test_data_root)

    print("--- 2. Injecting mock daily prices ---")
    price_df = pd.DataFrame(
        {
            "ts_code": "000001.SZ",
            "trade_date": cal_dates.strftime("%Y%m%d"),
            "open": 10,
            "high": 12,
            "low": 9,
            "close": 11,
            "vol": 1000,
            "amount": 11000,
        }
    )
    storage.insert_daily_data(price_df)

    print("--- 3. Injecting mock fundamentals (announcement on Jan 5) ---")
    income_df = pd.DataFrame(
        {
            "ts_code": ["000001.SZ"],
            "ann_date": ["20240105"],
            "end_date": ["20231231"],
            "total_revenue": [1000.0],
            "n_income": [100.0],
        }
    )
    storage.insert_fundamental_data(income_df, "income")

    fina_df = pd.DataFrame(
        {
            "ts_code": ["000001.SZ"],
            "ann_date": ["20240105"],
            "end_date": ["20231231"],
            "roe": [15.5],
            "roa": [5.5],
            "gross_margin": [30.0],
        }
    )
    storage.insert_fundamental_data(fina_df, "indicators")

    print("--- 4. Executing staged compiler ---")
    build_unified_qlib(test_data_root, test_qlib_dir)

    print("--- 5. Asserting PIT-safe Qlib queries ---")
    qlib.init(provider_uri=test_qlib_dir, region="cn", kernels=1)
    df = D.features(["000001_SZ"], ["$close", "$roe"], start_time="2024-01-01", end_time="2024-01-10")

    print("\n[RESULT TABLE]")
    print(df)
    print("\n[EVALUATION]")

    roe_01_05 = df.loc[("000001_SZ", pd.Timestamp("2024-01-05")), "$roe"]
    roe_01_08 = df.loc[("000001_SZ", pd.Timestamp("2024-01-08")), "$roe"]

    if pd.isna(roe_01_05) and roe_01_08 == 15.5:
        print("[SUCCESS]: PIT forward shift prevented same-day lookahead bias.")
        print("[SUCCESS]: Ticker format schema built and fetched via 000001_SZ.")
    else:
        print(f"[FAILED]: Lookahead bounds broken. ROE Jan 5: {roe_01_05} | ROE Jan 8: {roe_01_08}")


if __name__ == "__main__":
    test_pipeline_e2e()
