"""v12 (no survivor) - v11 (survivor) per-stock attribution.

v12 added back ~80 stocks that delisted between 2014 and 2024 to the eligible
universe. We compute:
  1. Which delisted names did v12 ACTUALLY buy that v11 did NOT?
  2. For each, what was its return contribution per year?
  3. Aggregate by year — confirm 2014/2015 wins came from same names that hurt 2020/2022/2023

This identifies the exact names JQ's index-reconstitution-aware universe would
INCLUDE (helping 2014/2015) OR EXCLUDE (sparing 2020+ damage)."""

import pandas as pd
from pathlib import Path

P = Path(r"E:/量化系统")
v11 = pd.read_csv(P / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v11_topk100_run/event_driven_trades.csv",
                  parse_dates=["date"])
v12 = pd.read_csv(P / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v12_no_survivor_run/event_driven_trades.csv",
                  parse_dates=["date"])

# 1. Identify "v12-only" stocks (in v12 but not v11) across the full window
v11_codes = set(v11[v11["direction"] == "buy"]["code"])
v12_codes = set(v12[v12["direction"] == "buy"]["code"])
only_v12 = v12_codes - v11_codes
only_v11 = v11_codes - v12_codes
common = v11_codes & v12_codes

print(f"v11 unique buy stocks (all years): {len(v11_codes)}")
print(f"v12 unique buy stocks (all years): {len(v12_codes)}")
print(f"Common: {len(common)}")
print(f"Only-v11 (excluded from v12 — never picked because universe wider): {len(only_v11)}")
print(f"Only-v12 (added by removing survivor): {len(only_v12)}")

# 2. For only-v12 names, get listing/delist status
sb = pd.read_parquet(P / "data/reference/stock_basic.parquet")
sb["list_date"] = pd.to_datetime(sb["list_date"], format="%Y%m%d", errors="coerce")
sb["delist_date"] = pd.to_datetime(sb["delist_date"], format="%Y%m%d", errors="coerce")

only_v12_info = []
for c in only_v12:
    ts_c = c
    row = sb[sb["ts_code"] == ts_c]
    if not row.empty:
        r = row.iloc[0]
        only_v12_info.append({
            "code": c,
            "name": r["name"],
            "list_date": r["list_date"].date() if pd.notna(r["list_date"]) else None,
            "delist_date": r["delist_date"].date() if pd.notna(r["delist_date"]) else None,
        })
ov12 = pd.DataFrame(only_v12_info)
ov12["delisted_before_2024"] = ov12["delist_date"].apply(
    lambda d: d is not None and d < pd.Timestamp("2024-01-01").date()
)
print()
print(f"Of {len(ov12)} only-v12 names: {ov12['delisted_before_2024'].sum()} delisted before 2024-01-01")

# 3. v12 trades stats by year for only-v12 stocks
v12_buys = v12[v12["direction"] == "buy"].copy()
v12_only_buys = v12_buys[v12_buys["code"].isin(only_v12)].copy()
v12_only_buys["year"] = v12_only_buys["date"].dt.year
print()
print("v12-only-stock buy counts by year:")
print(v12_only_buys.groupby("year").size().to_string())

# 4. For each only-v12 stock, compute its IN-TRADE return contribution
# Match each buy with the subsequent sell from the same code
v12_sells = v12[v12["direction"] == "sell"].copy().sort_values("date")
v12_buys_sorted = v12_only_buys.sort_values("date").copy()

# Simple approach: pair each buy with the next sell of the same code
contributions = []
for code in only_v12:
    cb = v12_buys_sorted[v12_buys_sorted["code"] == code].sort_values("date").reset_index(drop=True)
    cs = v12_sells[v12_sells["code"] == code].sort_values("date").reset_index(drop=True)
    bi, si = 0, 0
    while bi < len(cb) and si < len(cs):
        bd = cb.iloc[bi]
        # find next sell after this buy
        sd_idx = cs[cs["date"] >= bd["date"]].index
        if len(sd_idx) == 0:
            break
        sd = cs.loc[sd_idx[0]]
        b_price = bd["price"]
        s_price = sd["price"]
        if pd.notna(b_price) and b_price > 0 and pd.notna(s_price):
            ret_pct = (s_price - b_price) / b_price
            value_in = bd["value"]
            pl = value_in * ret_pct  # CNY profit/loss
            contributions.append({
                "code": code,
                "year": bd["date"].year,
                "buy_date": bd["date"].date(),
                "sell_date": sd["date"].date(),
                "ret_pct": ret_pct,
                "pl_yuan": pl,
            })
        bi += 1
        si = sd_idx[0] + 1

cdf = pd.DataFrame(contributions)
if not cdf.empty:
    print()
    print("v12-only-stock P/L by year (sum, CNY):")
    pl_by_year = cdf.groupby("year")["pl_yuan"].sum().sort_index()
    for yr, pl in pl_by_year.items():
        print(f"  {yr}: CNY{pl:>15,.0f}")
    print()
    print("Top 20 BEST v12-only stocks by total P/L (CNY):")
    top_pl = cdf.groupby("code")["pl_yuan"].sum().sort_values(ascending=False)
    for c, pl in top_pl.head(20).items():
        name = sb[sb["ts_code"] == c]["name"].iloc[0] if not sb[sb["ts_code"] == c].empty else "?"
        delist = sb[sb["ts_code"] == c]["delist_date"].iloc[0] if not sb[sb["ts_code"] == c].empty else None
        delist_str = delist.date() if pd.notna(delist) else "active"
        n_trades = (cdf["code"] == c).sum()
        print(f"  {c}  {name:<12}  delist={delist_str}  trades={n_trades:>3}  total_pl=CNY{pl:>12,.0f}")
    print()
    print("Top 20 WORST v12-only stocks by total P/L (CNY):")
    for c, pl in top_pl.tail(20).items():
        name = sb[sb["ts_code"] == c]["name"].iloc[0] if not sb[sb["ts_code"] == c].empty else "?"
        delist = sb[sb["ts_code"] == c]["delist_date"].iloc[0] if not sb[sb["ts_code"] == c].empty else None
        delist_str = delist.date() if pd.notna(delist) else "active"
        n_trades = (cdf["code"] == c).sum()
        print(f"  {c}  {name:<12}  delist={delist_str}  trades={n_trades:>3}  total_pl=CNY{pl:>12,.0f}")
