"""Check whether v9's top-12 picks on 2024-02-06 were at limit-down,
which would explain why JQ's filter_limitdown_stock excluded them and JQ picked higher-ranked names."""

import pandas as pd
import sys
from pathlib import Path

P = Path(r"E:/量化系统")
sys.path.insert(0, str(P))

import qlib
from qlib.data import D
qlib.init(provider_uri=str(P / "data/qlib_data"), kernels=1)

TEST_DATE = pd.Timestamp("2024-02-06")
V9_TOP12 = [
    "002633.SZ", "002856.SZ", "002193.SZ", "002652.SZ", "002848.SZ",
    "002211.SZ", "002719.SZ", "002188.SZ", "002629.SZ", "002058.SZ",
    "002591.SZ", "002207.SZ",
]
JQ_PICKS = [
    "002144.SZ", "002205.SZ", "002209.SZ", "002767.SZ", "002780.SZ",
    "002809.SZ", "002820.SZ", "002890.SZ", "003001.SZ", "003008.SZ",
    "003017.SZ", "003023.SZ",
]

codes_qlib = sorted({c.replace(".", "_") for c in V9_TOP12 + JQ_PICKS})
df = D.features(codes_qlib,
                ["$open", "$close", "$high", "$low", "$up_limit", "$down_limit", "$pre_close", "$vol"],
                start_time="2024-02-05", end_time="2024-02-07", freq="day")
df.columns = ["open", "close", "high", "low", "up_limit", "down_limit", "pre_close", "vol"]
df = df.reset_index()
df["date"] = pd.to_datetime(df["datetime"]).dt.normalize()
df["ts_code"] = df["instrument"].str.upper().str.replace("_", ".")

print("=" * 110)
print(f"v9 top-12 picks on {TEST_DATE.date()} — were they at limit-down?")
print("=" * 110)
print(f"{'code':<12} {'open':>7} {'high':>7} {'low':>7} {'close':>7} "
      f"{'up_lim':>8} {'down_lim':>9} {'pre_cl':>7} "
      f"{'close==down?':>14} {'open==down?':>13} {'low==down?':>13}")
print("-" * 110)
day = df[df["date"] == TEST_DATE]
for c in V9_TOP12:
    row = day[day["ts_code"] == c]
    if row.empty:
        print(f"{c:<12} (missing)")
        continue
    r = row.iloc[0]
    cl_at_dl = abs(r["close"] - r["down_limit"]) < 0.005
    open_at_dl = abs(r["open"] - r["down_limit"]) < 0.005
    low_at_dl = abs(r["low"] - r["down_limit"]) < 0.005
    print(f"{c:<12} {r['open']:>7.2f} {r['high']:>7.2f} {r['low']:>7.2f} {r['close']:>7.2f} "
          f"{r['up_limit']:>8.2f} {r['down_limit']:>9.2f} {r['pre_close']:>7.2f} "
          f"{'YES' if cl_at_dl else '':>14} {'YES' if open_at_dl else '':>13} {'YES' if low_at_dl else '':>13}")

print()
print("=" * 110)
print(f"JQ's picks on {TEST_DATE.date()} — for comparison")
print("=" * 110)
print(f"{'code':<12} {'open':>7} {'high':>7} {'low':>7} {'close':>7} "
      f"{'up_lim':>8} {'down_lim':>9} {'pre_cl':>7}")
print("-" * 90)
for c in JQ_PICKS:
    row = day[day["ts_code"] == c]
    if row.empty:
        print(f"{c:<12} (missing)")
        continue
    r = row.iloc[0]
    print(f"{c:<12} {r['open']:>7.2f} {r['high']:>7.2f} {r['low']:>7.2f} {r['close']:>7.2f} "
          f"{r['up_limit']:>8.2f} {r['down_limit']:>9.2f} {r['pre_close']:>7.2f}")

# Summary: how many of v9's top 12 had low==down_limit (touched limit-down intraday)?
v9_low_at_dl = 0
v9_close_at_dl = 0
for c in V9_TOP12:
    row = day[day["ts_code"] == c]
    if row.empty:
        continue
    r = row.iloc[0]
    if abs(r["low"] - r["down_limit"]) < 0.01:
        v9_low_at_dl += 1
    if abs(r["close"] - r["down_limit"]) < 0.01:
        v9_close_at_dl += 1

jq_low_at_dl = 0
jq_close_at_dl = 0
for c in JQ_PICKS:
    row = day[day["ts_code"] == c]
    if row.empty:
        continue
    r = row.iloc[0]
    if abs(r["low"] - r["down_limit"]) < 0.01:
        jq_low_at_dl += 1
    if abs(r["close"] - r["down_limit"]) < 0.01:
        jq_close_at_dl += 1

print()
print("=" * 110)
print(f"Summary for {TEST_DATE.date()}:")
print(f"  v9 top-12 picks: {v9_low_at_dl}/12 touched limit-down intraday, {v9_close_at_dl}/12 closed at limit-down")
print(f"  JQ actual picks: {jq_low_at_dl}/12 touched limit-down intraday, {jq_close_at_dl}/12 closed at limit-down")
print("=" * 110)
