"""Independent confirmation (Test A'): forecast-LEVEL parity, no realized-actual in the loop.

Compares the as-of-date Tushare report_rc consensus earnings-yield (consensus FY1 EPS /
raw close, report_date+1 anchor) against JoinQuant's genuinely-PIT
`predicted_earnings_to_price_ratio` (朝阳永续) from jq_consensus_canary_SNAP1.csv.

If the as-of-D Tushare consensus reproduces the as-of-D JQ PIT consensus LEVEL, the
report_date+1 anchor reconstructs the genuine point-in-time consensus directly (no
dependence on a realized-actual denominator). Complements the error-parity test.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from data_infra.pit_backend import strictly_next_open_trade_day  # noqa: E402

RC_DIR = PROJECT_ROOT / "data" / "analyst" / "report_rc"
DAILY_DIR = PROJECT_ROOT / "data" / "market" / "daily"
TRADE_CAL = PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet"
SNAP = PROJECT_ROOT / "聚宽回测明细" / "jq_consensus_canary_SNAP1.csv"
MAX_AGE_DAYS = 400
JQ2TS = {".XSHG": ".SH", ".XSHE": ".SZ"}


def jq_to_ts(code):
    for k, v in JQ2TS.items():
        if code.endswith(k):
            return code.replace(k, v)
    return code


def raw_close(ts_code, asof: pd.Timestamp) -> float:
    f = DAILY_DIR / str(asof.year) / f"daily_{asof.strftime('%Y%m%d')}.parquet"
    if not f.exists():
        return np.nan
    df = pd.read_parquet(f, columns=["ts_code", "close"])
    row = df[df["ts_code"] == ts_code]
    return float(row["close"].iloc[0]) if len(row) else np.nan


def main():
    jq = pd.read_csv(SNAP)
    jq = jq[jq["factor"] == "predicted_earnings_to_price_ratio"].copy()
    jq["ts_code"] = jq["code"].map(jq_to_ts)
    jq["asof"] = pd.to_datetime(jq["asof"])
    stocks = sorted(jq["ts_code"].unique())

    cols = ["ts_code", "report_date", "org_name", "author_name", "quarter", "eps"]
    frames = [pd.read_parquet(RC_DIR / f"report_rc_{y}.parquet", columns=cols) for y in range(2013, 2022)]
    rc = pd.concat(frames, ignore_index=True)
    rc = rc[rc["ts_code"].isin(stocks)].copy()
    rc["report_date"] = pd.to_datetime(rc["report_date"], format="%Y%m%d", errors="coerce")
    rc["eps"] = pd.to_numeric(rc["eps"], errors="coerce")
    rc = rc.dropna(subset=["report_date"])
    cal = pd.read_parquet(TRADE_CAL)
    open_cal = pd.DatetimeIndex(
        pd.to_datetime(cal.loc[cal["is_open"] == 1, "cal_date"], format="%Y%m%d")).sort_values()
    rc["effective_date"] = strictly_next_open_trade_day(rc["report_date"], open_cal)
    rc["org_author"] = rc["org_name"].astype(str) + "|" + rc["author_name"].astype(str)
    rc = rc.sort_values("report_date")

    rows = []
    for r in jq.itertuples(index=False):
        asof, ts, fy = r.asof, r.ts_code, r.asof.year
        lo = asof - pd.Timedelta(days=MAX_AGE_DAYS)
        vis = rc[(rc["ts_code"] == ts) & (rc["effective_date"] <= asof)
                 & (rc["report_date"] >= lo) & (rc["quarter"].astype(str) == f"{fy}Q4")].dropna(subset=["eps"])
        latest = vis.drop_duplicates(subset=["org_author"], keep="last")
        cons_eps = float(latest["eps"].mean()) if len(latest) else np.nan
        px = raw_close(ts, asof)
        ts_ep = cons_eps / px if (cons_eps == cons_eps and px == px and px > 0) else np.nan
        rows.append({"asof": asof.date(), "ts_code": ts, "jq_ep": float(r.value),
                     "ts_ep": ts_ep, "cons_eps": cons_eps, "close": px, "n": len(latest)})
    res = pd.DataFrame(rows)
    paired = res.dropna(subset=["jq_ep", "ts_ep"])
    print(res.to_string(index=False))
    if len(paired) >= 3:
        print(f"\nPearson  corr(jq_ep, ts_ep) = {paired['jq_ep'].corr(paired['ts_ep']):+.3f}")
        print(f"Spearman corr               = {paired['jq_ep'].corr(paired['ts_ep'], method='spearman'):+.3f}")
        print(f"mean |jq_ep - ts_ep|        = {(paired['jq_ep'] - paired['ts_ep']).abs().mean():.4f}")
        print(f"mean ratio ts_ep/jq_ep      = {(paired['ts_ep']/paired['jq_ep']).mean():.3f}")


if __name__ == "__main__":
    main()
