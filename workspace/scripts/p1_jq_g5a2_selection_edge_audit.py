# ──────────────────────────────────────────────────────────────────────
# PR 7 of 2026-05-26 freeze plan — SCRIPT_STATUS header block.
# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: joinquant_attribution_only
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   Sandbox / one-shot diagnostic script. NOT a formal research
#   surface. Bare D.features calls inside this file are tolerated
#   per scripts/lint_no_bare_qlib_features.py allowlist semantics
#   (PR 6) but the script's output is not eligible for the formal
#   release gate.
# ──────────────────────────────────────────────────────────────────────
"""Why did v13 pick stocks 002213/002607/002634 instead of JQ's
002058/002125/002193/002560/002723 on 2015-07-28?

For each disputed pick:
  1. Was it in JQ's PIT 中小综 universe on that date? (Tuesday snapshot)
  2. What was its total_mv vs other picks?
  3. Was it locked at open (limit-up or limit-down)?
  4. Was it ST or suspended on that date?
  5. Was it in our local universe at all (data presence)?

Identifies the EXACT filter or selection step that diverges."""

import pandas as pd
from pathlib import Path
import sys

P = Path(r"E:/量化系统")
sys.path.insert(0, str(P))

import qlib
from qlib.data import D
qlib.init(provider_uri=str(P / "data/qlib_data"), kernels=1)

TEST_DATE = pd.Timestamp("2015-07-28")
PREV_DATE = pd.Timestamp("2015-07-27")

# 1. Load JQ PIT universe on TEST_DATE
jq_pit = pd.read_csv(P / "Knowledge/zxz_399101_pit_membership_tuesdays.csv")
jq_pit["date"] = pd.to_datetime(jq_pit["date"]).dt.normalize()
jq_pit["ts_code"] = jq_pit["ts_code"].str.replace(".XSHE", ".SZ").str.replace(".XSHG", ".SH")
jq_universe = set(jq_pit[jq_pit["date"] == TEST_DATE]["ts_code"])
print(f"JQ PIT universe on {TEST_DATE.date()}: {len(jq_universe)} stocks")

# 2. Load all v13's universe metadata
sb = pd.read_parquet(P / "data/reference/stock_basic.parquet")
sb["list_date"] = pd.to_datetime(sb["list_date"], format="%Y%m%d", errors="coerce")
sb["delist_date"] = pd.to_datetime(sb["delist_date"], format="%Y%m%d", errors="coerce")

# 3. Apply v13's filters: 375d listing + delist
list_cutoff = TEST_DATE - pd.Timedelta(days=375)
v13_eligible = sb[
    (sb["ts_code"].isin(jq_universe))
    & (sb["list_date"] <= list_cutoff)
    & ((sb["delist_date"].isna()) | (sb["delist_date"] > TEST_DATE))
].copy()
print(f"v13 eligible after 375d + delist filters: {len(v13_eligible)} stocks")

# 4. ST exclusion
st = []
for line in (P / "data/qlib_data/instruments/st_stocks.txt").read_text(encoding="utf-8").splitlines():
    parts = line.strip().split("\t")
    if len(parts) < 3:
        continue
    st.append({
        "ts_code": parts[0].replace("_", ".").upper(),
        "start": pd.to_datetime(parts[1], format="%Y-%m-%d", errors="coerce"),
        "end": pd.to_datetime(parts[2], format="%Y-%m-%d", errors="coerce"),
    })
st = pd.DataFrame(st)
st_today = st[
    (st["start"].notna()) & (st["start"] <= TEST_DATE) & ((st["end"].isna()) | (st["end"] > TEST_DATE))
]
v13_eligible = v13_eligible[~v13_eligible["ts_code"].isin(set(st_today["ts_code"]))]
print(f"v13 eligible after ST exclusion: {len(v13_eligible)} stocks")

# 5. Load OHLC + total_mv for these stocks on PREV_DATE and TEST_DATE
codes_qlib = sorted(v13_eligible["ts_code"].str.replace(".", "_"))
df = D.features(codes_qlib, ["Ref($total_mv, 1)", "$open", "$close", "$up_limit", "$down_limit", "$pre_close", "$vol"],
                start_time=TEST_DATE.strftime("%Y-%m-%d"), end_time=TEST_DATE.strftime("%Y-%m-%d"), freq="day")
df.columns = ["total_mv_lag1", "open", "close", "up_limit", "down_limit", "pre_close", "vol"]
df = df.reset_index()
df["ts_code"] = df["instrument"].str.replace("_", ".")
print(f"Features loaded: {len(df)} rows")

# 6. Rank by total_mv_lag1 ascending — v13's selection order
df_valid = df.dropna(subset=["total_mv_lag1"]).sort_values("total_mv_lag1").reset_index(drop=True)
df_valid["rank"] = range(1, len(df_valid) + 1)
print(f"With valid total_mv_lag1: {len(df_valid)} stocks")

# 7. Apply v13's runtime at-open filter
EPS = 1e-4
def is_tradeable(r):
    if r["open"] is None or pd.isna(r["open"]):
        return False
    if r["up_limit"] is not None and r["open"] >= r["up_limit"] - EPS:
        return False
    if r["down_limit"] is not None and r["open"] <= r["down_limit"] + EPS:
        return False
    return True
df_valid["tradeable"] = df_valid.apply(is_tradeable, axis=1)

# 8. v13's top picks = top 100 then first 12 tradeable
top100 = df_valid.head(100)
v13_picks = top100[top100["tradeable"]].head(12)
print(f"\nv13's top 12 (smallest market_cap, tradeable at open) on {TEST_DATE.date()}:")
print(v13_picks[["rank", "ts_code", "total_mv_lag1", "open", "close", "up_limit", "down_limit", "tradeable"]].to_string(index=False))

# 9. JQ's actual picks on this date
jq_trades = pd.read_csv(r"C:/Users/henry/Desktop/聚宽回测系统/strategies/G5_韶华纯净小市值/variants/G5_A2_stocknum12/g5_G5_A2_stocknum12_trades.csv", parse_dates=["time"])
jq_trades["date"] = jq_trades["time"].dt.normalize()
jq_trades["ts_code"] = jq_trades["security"].str.replace(".XSHE", ".SZ").str.replace(".XSHG", ".SH")
jq_buys_today = jq_trades[(jq_trades["date"] == TEST_DATE) & (jq_trades["action"] == "open")]
jq_picks_today = set(jq_buys_today["ts_code"])
print(f"\nJQ's actual buys on {TEST_DATE.date()}: {jq_picks_today}")

# 10. For each JQ-only pick, show its v13 ranking and tradeability
only_jq = jq_picks_today - set(v13_picks["ts_code"])
print(f"\nOnly-JQ picks (v13 missed): {len(only_jq)}")
for c in sorted(only_jq):
    row = df_valid[df_valid["ts_code"] == c]
    if row.empty:
        print(f"  {c}: NOT IN v13 ELIGIBLE UNIVERSE (375d/ST/delist filter)")
        sb_row = sb[sb["ts_code"] == c]
        if not sb_row.empty:
            r = sb_row.iloc[0]
            print(f"       list_date={r['list_date'].date() if pd.notna(r['list_date']) else None} "
                  f"delist_date={r['delist_date'].date() if pd.notna(r['delist_date']) else None}")
        else:
            print(f"       NOT IN our stock_basic")
    else:
        r = row.iloc[0]
        in_jq_universe = c in jq_universe
        print(f"  {c}: v13_rank=#{int(r['rank'])} of {len(df_valid)}  "
              f"total_mv_lag1={r['total_mv_lag1']:,.0f}  open={r['open']:.2f}  "
              f"down_limit={r['down_limit']:.2f}  tradeable={r['tradeable']}  in_jq_pit={in_jq_universe}")

# Also show v13-only picks (JQ didn't pick)
print()
only_v13 = set(v13_picks["ts_code"]) - jq_picks_today
print(f"Only-v13 picks (JQ avoided): {len(only_v13)}")
for c in sorted(only_v13):
    row = df_valid[df_valid["ts_code"] == c]
    r = row.iloc[0]
    in_jq_universe = c in jq_universe
    print(f"  {c}: v13_rank=#{int(r['rank'])}  total_mv_lag1={r['total_mv_lag1']:,.0f}  "
          f"open={r['open']:.2f}  in_jq_pit={in_jq_universe}")
