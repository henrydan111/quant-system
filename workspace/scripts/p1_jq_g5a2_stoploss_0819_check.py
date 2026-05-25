"""Verify the 2015-08-19 market_stoploss trigger: was it borderline?

v18 fired stoploss on 08-19 based on 08-18's mean(close/open) over the 中小综
universe ≤ 0.94. JQ-verify did NOT fire (stayed invested). Compute our mean
with both conventions (drop-suspended vs suspended=1.0) and see how close to
0.94 it is. Also check whether JQ would re-enter while v18 stayed in cash by
counting tradeable (non-suspended, non-limit) 002/003 stocks on each day."""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

P = Path(r"E:/量化系统")
sys.path.insert(0, str(P))

import qlib
from qlib.data import D
qlib.init(provider_uri=str(P / "data/qlib_data"), kernels=1)

# JQ PIT universe membership
jq_pit = pd.read_csv(P / "Knowledge/zxz_399101_pit_membership_tuesdays.csv")
jq_pit["date"] = pd.to_datetime(jq_pit["date"]).dt.normalize()
jq_pit["ts_code"] = jq_pit["ts_code"].str.replace(".XSHE", ".SZ").str.replace(".XSHG", ".SH")

def nearest_tue(d):
    tu = sorted(jq_pit["date"].unique())
    valid = [t for t in tu if t <= d]
    return valid[-1] if valid else tu[0]

# Check the trigger dates: prev-day mean(close/open) for v18 stoploss on 08-19,
# plus surrounding Tuesdays where v18 stayed cash (08-25, 09-01, 09-08).
check_pairs = [
    ("2015-08-19", "2015-08-18"),  # v18 fired (uses 08-18 data)
    ("2015-08-25", "2015-08-24"),  # Tuesday; Black Monday 08-24 data
    ("2015-09-01", "2015-08-31"),
    ("2015-09-08", "2015-09-07"),
    ("2015-09-15", "2015-09-14"),  # v18 re-entered here
]

all_codes_set = set(jq_pit["ts_code"])
all_codes_qlib = sorted(c.replace(".", "_") for c in all_codes_set)
df = D.features(all_codes_qlib, ["$open", "$close", "$up_limit", "$down_limit"],
                start_time="2015-08-10", end_time="2015-09-20", freq="day")
df.columns = ["open", "close", "up_limit", "down_limit"]
df = df.reset_index()
df["date"] = pd.to_datetime(df["datetime"]).dt.normalize()
df["ts_code"] = df["instrument"].str.upper().str.replace("_", ".")

print("Market-stoploss trigger check (threshold 0.94):")
print(f"{'fire_date':<12} {'prev_date':<12} {'n_universe':>10} {'n_trading':>10} {'n_susp':>8} "
      f"{'mean_drop':>10} {'mean_fill1':>11} {'fire_drop?':>11} {'fire_fill1?':>12}")
for fire_d, prev_d in check_pairs:
    fire_ts = pd.Timestamp(fire_d); prev_ts = pd.Timestamp(prev_d)
    uni = set(jq_pit[jq_pit["date"] == nearest_tue(fire_ts)]["ts_code"])
    slice_ = df[df["date"] == prev_ts]
    slice_ = slice_[slice_["ts_code"].isin(uni)]
    valid = slice_[(slice_["open"] > 0) & slice_["close"].notna() & slice_["open"].notna()]
    n_uni = len(uni); n_trading = len(valid); n_susp = n_uni - n_trading
    if n_trading < 50:
        print(f"{fire_d:<12} {prev_d:<12} insufficient")
        continue
    ratio_trading = (valid["close"] / valid["open"]).mean()
    ratio_fill1 = (ratio_trading * n_trading + 1.0 * n_susp) / n_uni
    print(f"{fire_d:<12} {prev_d:<12} {n_uni:>10} {n_trading:>10} {n_susp:>8} "
          f"{ratio_trading:>10.4f} {ratio_fill1:>11.4f} "
          f"{'FIRE' if ratio_trading<=0.94 else 'no':>11} {'FIRE' if ratio_fill1<=0.94 else 'no':>12}")

# Count tradeable candidates each day 08-19 to 09-15 (can v18 even re-enter?)
print()
print("Tradeable 002/003 count per day (open valid, not limit-up, not limit-down) — re-entry capacity:")
print(f"{'date':<12} {'n_universe':>10} {'n_tradeable':>12} {'n_suspended':>12}")
for d in pd.date_range("2015-08-18", "2015-09-16"):
    d = pd.Timestamp(d).normalize()
    slice_ = df[df["date"] == d]
    if slice_.empty:
        continue
    uni = set(jq_pit[jq_pit["date"] == nearest_tue(d)]["ts_code"])
    slice_ = slice_[slice_["ts_code"].isin(uni)]
    tradeable = slice_[(slice_["open"] > 0) & slice_["open"].notna()
                       & (slice_["open"] < slice_["up_limit"] - 1e-4)
                       & (slice_["open"] > slice_["down_limit"] + 1e-4)]
    n_susp = len(uni) - len(slice_[slice_["open"].notna() & (slice_["open"] > 0)])
    print(f"{d.date()!s:<12} {len(uni):>10} {len(tradeable):>12} {n_susp:>12}")
