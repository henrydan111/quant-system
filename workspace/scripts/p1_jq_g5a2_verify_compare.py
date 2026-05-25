"""Compare the JoinQuant verification run (9:30 open fill) against local v11/v13/v18.

JQ-verify CSV columns (gbk): 时间, 基准收益, 策略收益(cum %), 当日盈亏, 当日开仓,
当日平仓, ???, 回撤(%). The 策略收益 column is cumulative percent return.

Builds a daily NAV from 策略收益, computes per-year compounded returns, and
compares to local v11 (equal-weight) and v18 (no-trim) to attribute the gap."""

import pandas as pd
import numpy as np
from pathlib import Path

P = Path(r"E:/量化系统")

# --- JQ verify ---
jqv = pd.read_csv(P / "Knowledge/聚宽回测数据/result_1 (1).csv", encoding="gbk")
jqv.columns = ["time", "bench_cum_pct", "strat_cum_pct", "daily_pnl", "daily_open", "daily_close", "col6", "drawdown_pct"]
jqv["date"] = pd.to_datetime(jqv["time"]).dt.normalize()
jqv["nav"] = 1.0 + jqv["strat_cum_pct"] / 100.0   # cum return % → NAV (start 1.0)
jqv = jqv[["date", "nav"]].rename(columns={"nav": "nav_jqverify"})

# --- local runs ---
def load_local(path):
    df = pd.read_csv(path)
    cal = pd.read_parquet(P / "data/reference/trade_cal.parquet")
    cal["cal_date"] = pd.to_datetime(cal["cal_date"], format="%Y%m%d", errors="coerce")
    cal = cal[(cal["is_open"] == 1) & (cal["cal_date"] >= "2014-01-01") & (cal["cal_date"] <= "2026-02-27")]
    cal = cal.sort_values("cal_date").reset_index(drop=True)
    df["date"] = cal["cal_date"].iloc[:len(df)].values
    df["nav"] = (1 + df["return"]).cumprod()
    return df[["date", "return", "nav"]]

v11 = load_local(P / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v11_topk100_run/event_driven_report.csv")
v18_path = P / "workspace/research/alpha_mining/p1_jq_g5a2_mimic_v18_no_trim_run/event_driven_report.csv"

df = jqv.merge(v11[["date", "return", "nav"]].rename(columns={"return": "ret_v11", "nav": "nav_v11"}), on="date", how="inner")
if v18_path.exists():
    v18 = load_local(v18_path)
    df = df.merge(v18[["date", "return", "nav"]].rename(columns={"return": "ret_v18", "nav": "nav_v18"}), on="date", how="left")

# Normalize NAVs to first trade date
df = df[df["date"] >= "2014-02-07"].reset_index(drop=True)
df["nav_jqverify"] = df["nav_jqverify"] / df["nav_jqverify"].iloc[0]
df["nav_v11"] = (1 + df["ret_v11"]).cumprod()
if "ret_v18" in df.columns:
    df["nav_v18"] = (1 + df["ret_v18"].fillna(0)).cumprod()
df["year"] = df["date"].dt.year

n_yr = len(df) / 242
def cagr(nav_col):
    return (df[nav_col].iloc[-1]) ** (1 / n_yr) - 1

print("=" * 80)
print(f"JQ-verify (9:30 open) final NAV: {df['nav_jqverify'].iloc[-1]:.2f}  CAGR {cagr('nav_jqverify')*100:.2f}%")
print(f"v11 (equal-weight)      final NAV: {df['nav_v11'].iloc[-1]:.2f}  CAGR {cagr('nav_v11')*100:.2f}%")
if "nav_v18" in df.columns:
    print(f"v18 (no-trim)           final NAV: {df['nav_v18'].iloc[-1]:.2f}  CAGR {cagr('nav_v18')*100:.2f}%")
print("=" * 80)

# Per-year
print()
print("Per-year compounded returns:")
hdr = f"{'year':<6} {'jqverify':>10} {'v11':>10}"
if "nav_v18" in df.columns:
    hdr += f" {'v18':>10} {'v18-jqv':>10}"
print(hdr)
for yr, g in df.groupby("year"):
    jqv_y = g["nav_jqverify"].iloc[-1] / g["nav_jqverify"].iloc[0] - 1
    v11_y = (1 + g["ret_v11"]).prod() - 1
    line = f"{yr:<6} {jqv_y*100:>+9.2f}% {v11_y*100:>+9.2f}%"
    if "ret_v18" in df.columns:
        v18_y = (1 + g["ret_v18"].fillna(0)).prod() - 1
        line += f" {v18_y*100:>+9.2f}% {(v18_y-jqv_y)*100:>+9.2f}pp"
    print(line)
