"""Direct test of Mech E: did v13 see different market_cap values than JQ
for the stocks they disagreed on?

For each (Tuesday, disputed pick) pair from the v13-vs-JQ audit, pull
Ref($total_mv, 1) (Monday's total_mv) from our Qlib data. We don't have
JoinQuant's valuation.market_cap locally, but we can check:

  (a) What ranks v13 assigned to only-JQ picks vs only-v13 picks
  (b) If v13's ranking puts only-v13 picks SMALLER than only-JQ picks,
      and JQ went the opposite way, then JQ saw different market_cap values."""

import pandas as pd
import sys
from pathlib import Path

P = Path(r"E:/量化系统")
sys.path.insert(0, str(P))

import qlib
from qlib.data import D
qlib.init(provider_uri=str(P / "data/qlib_data"), kernels=1)

# Disputed picks per sample date (from v13_vs_jq_picks_audit_v2.py)
disputed = {
    pd.Timestamp("2015-07-28"): {
        "only_v13": ["002213.SZ", "002607.SZ", "002634.SZ"],
        "only_jq":  ["002058.SZ", "002125.SZ", "002193.SZ", "002560.SZ", "002723.SZ"],
    },
    pd.Timestamp("2017-08-01"): {
        "only_v13": ["002758.SZ"],
        "only_jq":  [],   # all of JQ matched v13
    },
    pd.Timestamp("2019-08-06"): {
        "only_v13": [],
        "only_jq":  ["002188.SZ"],   # 1 only-JQ
    },
    pd.Timestamp("2021-08-03"): {
        "only_v13": [],
        "only_jq":  ["002058.SZ", "002193.SZ", "002633.SZ"],   # 3 only-JQ
    },
    pd.Timestamp("2022-08-02"): {
        "only_v13": ["002207.SZ", "002211.SZ"],
        "only_jq":  ["002188.SZ", "002193.SZ", "002633.SZ", "002848.SZ", "002862.SZ"],
    },
    pd.Timestamp("2024-07-30"): {
        "only_v13": [],
        "only_jq":  ["002188.SZ", "002499.SZ", "002633.SZ"],
    },
    pd.Timestamp("2025-07-29"): {
        "only_v13": [],
        "only_jq":  ["002058.SZ", "002193.SZ", "002211.SZ", "002633.SZ", "002848.SZ", "002862.SZ"],
    },
}

def get_prev_date(d: pd.Timestamp) -> pd.Timestamp:
    cal = pd.read_parquet(P / "data/reference/trade_cal.parquet")
    cal["cal_date"] = pd.to_datetime(cal["cal_date"], format="%Y%m%d", errors="coerce")
    cal = cal[cal["is_open"] == 1].sort_values("cal_date").reset_index(drop=True)
    pri = cal[cal["cal_date"] < d]
    return pd.Timestamp(pri.iloc[-1]["cal_date"]) if not pri.empty else d - pd.Timedelta(days=1)

for d, disputes in disputed.items():
    prev = get_prev_date(d)
    all_codes = sorted({c.replace(".", "_") for c in disputes["only_v13"] + disputes["only_jq"]})
    if not all_codes:
        continue
    df = D.features(all_codes, ["$total_mv"], start_time=prev.strftime("%Y-%m-%d"), end_time=prev.strftime("%Y-%m-%d"), freq="day")
    df.columns = ["total_mv"]
    df = df.reset_index()
    df["ts_code"] = df["instrument"].str.upper().str.replace("_", ".")
    print(f"\n=== {d.date()} | prev_date = {prev.date()} (data used at Tuesday 10:30) ===")
    print(f"{'group':<10} {'code':<12} {'total_mv (万元)':>20}")
    for c in disputes["only_v13"]:
        row = df[df["ts_code"] == c]
        if not row.empty:
            print(f"{'only_v13':<10} {c:<12} {row.iloc[0]['total_mv']:>20,.0f}")
        else:
            print(f"{'only_v13':<10} {c:<12} {'(missing)':>20}")
    for c in disputes["only_jq"]:
        row = df[df["ts_code"] == c]
        if not row.empty:
            print(f"{'only_jq':<10} {c:<12} {row.iloc[0]['total_mv']:>20,.0f}")
        else:
            print(f"{'only_jq':<10} {c:<12} {'(missing)':>20}")
