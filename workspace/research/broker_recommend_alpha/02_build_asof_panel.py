"""Build the PIT-correct as-of monthly panel for the 券商金股 mother signal.

Input : data/analyst/broker_recommend/*.parquet (via raw_combined.parquet)
        data/reference/trade_cal.parquet
Output: workspace/outputs/broker_recommend_alpha/panel_asof.parquet

PIT visibility anchor (CRITICAL): month M's list is populated by Tushare within
its first 1-3 calendar days, and there is NO per-row disclosure date. So month
M's picks become tradable at the OPEN of the first trading day on/after the
**4th calendar day** of month M (primary anchor `entry_d4`). We also compute a
day-1 anchor (`entry_d1` = first trading day of month M) purely as a SENSITIVITY
leg — the d1-vs-d4 gap measures how much "edge" sits in the first 1-3 days
(announcement-drift / crowding), and d1 is mildly optimistic re the update lag.

Each month's holding period runs from its own anchor (inclusive) to the next
month's anchor (exclusive) — a clean ~1-month, no-overlap monthly rebalance.

Signal columns per (month, stock):
  - n_brokers      : distinct brokers picking it that month (raw conviction)
  - conv_rank_pct  : within-month percentile rank of n_brokers (cross-month
                     counts are NOT comparable — broker coverage swings 10-44/mo)
  - is_member      : 1 (membership is the primary signal; 81% are single-broker)
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_COMBINED = PROJECT_ROOT / "workspace" / "outputs" / "broker_recommend_alpha" / "raw_combined.parquet"
TRADE_CAL = PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet"
OUT_DIR = PROJECT_ROOT / "workspace" / "outputs" / "broker_recommend_alpha"


def _open_days() -> np.ndarray:
    cal = pd.read_parquet(TRADE_CAL)
    cal = cal[cal["is_open"] == 1]
    days = pd.to_datetime(cal["cal_date"].astype(str), format="%Y%m%d").sort_values().to_numpy()
    return days


def _first_trading_on_or_after(open_days: np.ndarray, target: np.datetime64) -> pd.Timestamp | None:
    idx = int(np.searchsorted(open_days, target, side="left"))
    if idx >= len(open_days):
        return None
    return pd.Timestamp(open_days[idx])


def main() -> int:
    df = pd.read_parquet(RAW_COMBINED)
    df["month"] = df["month"].astype(str)
    open_days = _open_days()

    # conviction per (month, ts_code)
    conv = (
        df.groupby(["month", "ts_code"])
        .agg(n_brokers=("broker", "nunique"), name=("name", "first"))
        .reset_index()
    )

    # within-month percentile rank of conviction (higher brokers -> higher rank)
    conv["conv_rank_pct"] = conv.groupby("month")["n_brokers"].rank(pct=True, method="average")
    conv["is_member"] = 1

    # anchors per month
    anchors = []
    for month in sorted(conv["month"].unique()):
        y, m = int(month[:4]), int(month[4:6])
        a4 = _first_trading_on_or_after(open_days, np.datetime64(datetime(y, m, 4)))
        a1 = _first_trading_on_or_after(open_days, np.datetime64(datetime(y, m, 1)))
        anchors.append({"month": month, "entry_d4": a4, "entry_d1": a1})
    anchors = pd.DataFrame(anchors)

    panel = conv.merge(anchors, on="month", how="left")
    panel["qlib_code"] = panel["ts_code"].str.replace(".", "_", regex=False)

    # holding window end = next month's entry anchor (exclusive)
    anchors_sorted = anchors.sort_values("month").reset_index(drop=True)
    anchors_sorted["exit_d4"] = anchors_sorted["entry_d4"].shift(-1)
    anchors_sorted["exit_d1"] = anchors_sorted["entry_d1"].shift(-1)
    panel = panel.merge(anchors_sorted[["month", "exit_d4", "exit_d1"]], on="month", how="left")

    panel = panel[
        ["month", "ts_code", "qlib_code", "name", "n_brokers", "conv_rank_pct",
         "is_member", "entry_d1", "entry_d4", "exit_d1", "exit_d4"]
    ].sort_values(["month", "n_brokers"], ascending=[True, False])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(OUT_DIR / "panel_asof.parquet", index=False)

    # diagnostics
    print(f"panel rows={len(panel)}  months={panel['month'].nunique()}  stocks={panel['ts_code'].nunique()}")
    print(f"last month with a forward window (exit_d4 not NaT): "
          f"{panel.loc[panel['exit_d4'].notna(),'month'].max()}  "
          f"(last month {panel['month'].max()} has no forward month yet)")
    chk = anchors_sorted.copy()
    chk["entry_d1"] = chk["entry_d1"].dt.strftime("%Y-%m-%d")
    chk["entry_d4"] = chk["entry_d4"].dt.strftime("%Y-%m-%d")
    print("\nfirst 6 + last 6 month anchors (entry_d1 / entry_d4):")
    print(chk[["month", "entry_d1", "entry_d4"]].head(6).to_string(index=False))
    print(chk[["month", "entry_d1", "entry_d4"]].tail(6).to_string(index=False))
    nm = panel.groupby("month").size()
    print(f"\nnames per month: min={nm.min()} median={nm.median():.0f} max={nm.max()}")
    print(f"wrote -> {OUT_DIR / 'panel_asof.parquet'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
