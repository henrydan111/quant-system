"""Diagnostic: what do suspended-stock rows actually look like on 2015-06-29 in our Qlib data?"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(r"E:/量化系统")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import qlib
from qlib.data import D

qlib.init(provider_uri=str(PROJECT_ROOT / "data/qlib_data"), kernels=1)

# Sanity 1: pick 5 known 002 stocks and dump 06-29 row
sb = pd.read_parquet(PROJECT_ROOT / "data/reference/stock_basic.parquet")
sb = sb[sb["ts_code"].str.startswith("002")]
codes = sorted({c.replace(".", "_") for c in sb["ts_code"].iloc[:1000]})

df = D.features(codes, ["$open", "$close", "$vol"],
                start_time="2015-06-25", end_time="2015-07-02", freq="day")
df.columns = ["open", "close", "vol"]
df = df.reset_index()
df["date"] = pd.to_datetime(df["datetime"]).dt.normalize()
slice_ = df[df["date"] == pd.Timestamp("2015-06-29")]

print(f"Total 002 rows on 2015-06-29: {len(slice_)}")
print(f"Rows with open NaN: {slice_['open'].isna().sum()}")
print(f"Rows with open == 0: {(slice_['open'] == 0).sum()}")
print(f"Rows with vol NaN: {slice_['vol'].isna().sum()}")
print(f"Rows with vol == 0: {(slice_['vol'] == 0).sum()}")
print(f"Rows with vol > 0: {(slice_['vol'] > 0).sum()}")
print(f"Rows with close < 0.99 * open (down >1%): {((slice_['close'] / slice_['open']) < 0.99).sum()}")
print(f"Rows with close == open (close/open == 1.0): {(slice_['close'] == slice_['open']).sum()}")
print()
print("Sample rows where close == open:")
print(slice_[slice_["close"] == slice_["open"]][["instrument", "open", "close", "vol"]].head(20))

# Check the suspension_ranges.parquet — official suspension table
susp_path = PROJECT_ROOT / "data/market/suspension/suspension_ranges.parquet"
if susp_path.exists():
    susp = pd.read_parquet(susp_path)
    print()
    print(f"\nSuspension table cols: {susp.columns.tolist()}")
    print(susp.head())
    # Filter to 06-29
    susp["start"] = pd.to_datetime(susp.get("suspend_start_date", susp.get("start_date", susp.iloc[:, 1])))
    susp["end"] = pd.to_datetime(susp.get("suspend_end_date", susp.get("end_date", susp.iloc[:, 2])))
    susp_0629 = susp[(susp["start"] <= "2015-06-29") & ((susp["end"].isna()) | (susp["end"] >= "2015-06-29"))]
    print(f"\nSuspended on 2015-06-29 per official table: {len(susp_0629)} rows")
    print(susp_0629.head(20))
else:
    print(f"\nNo suspension table at {susp_path}")
