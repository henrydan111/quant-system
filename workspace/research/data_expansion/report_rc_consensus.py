"""PIT-correct analyst-consensus panel from raw report_rc (Wave-1A foundation).

Turns the raw per-(stock × analyst × forecast-quarter) report_rc rows into a
point-in-time consensus panel keyed by (as-of trading day, ts_code). Reusable by
the Wave-1A pilot AND the eventual normalize→PIT→provider ingestion.

PIT contract (cross-review Q-D1):
  * visibility anchor  = strictly_next_open_trade_day(report_date)  [canonical, pit_backend]
  * a forecast is visible at as-of T iff effective_date <= T
  * forecast-age expiry: drop forecasts whose report_date < T - MAX_AGE_DAYS
  * one vote per analyst = latest report per (ts_code, org_name, author_name)

Consensus features per (T, ts_code):
  n_analysts, rating_score (ordinal mean), eps_fy1 (current-FY annual EPS consensus),
  eps_dispersion (cross-analyst std / |mean|), rating_revision_{lag}, eps_revision_{lag}.

NOT a canonical function yet — propose adding a src/system.md §0 row if the pilot passes.
Sandbox only; report_rc is unregistered.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from data_infra.pit_backend import strictly_next_open_trade_day  # noqa: E402

RC_DIR = PROJECT_ROOT / "data" / "analyst" / "report_rc"
TRADE_CAL = PROJECT_ROOT / "data" / "reference" / "trade_cal.parquet"

MAX_AGE_DAYS = 400          # forecast-age expiry (a year + reporting slack)
DEFAULT_REVISION_LAG = 90   # consensus revision window (days)

RATING_MAP = {
    "strong buy": 2, "强烈推荐": 2, "强推": 2, "buy": 1, "买入": 1, "overweight": 1,
    "outperform": 1, "增持": 1, "推荐": 1, "add": 1, "accumulate": 1, "优于大市": 1,
    "审慎增持": 1, "谨慎增持": 1,
    "hold": 0, "neutral": 0, "中性": 0, "持有": 0, "market perform": 0, "谨慎推荐": 0,
    "equal-weight": 0, "equalweight": 0, "观望": 0, "in-line": 0,
    "reduce": -1, "underweight": -1, "sell": -1, "减持": -1, "卖出": -1, "回避": -1,
    "underperform": -1, "弱于大市": -1,
}


def _rating_score(s):
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return np.nan
    return RATING_MAP.get(str(s).strip().lower(), np.nan)


def load_report_rc(years=range(2010, 2027)) -> pd.DataFrame:
    """Load raw report_rc, parse dates, compute the PIT visibility anchor once."""
    cols = ["ts_code", "report_date", "org_name", "author_name", "quarter", "eps", "rating", "tp"]
    frames = []
    for y in years:
        f = RC_DIR / f"report_rc_{y}.parquet"
        if f.exists():
            frames.append(pd.read_parquet(f, columns=cols))
    df = pd.concat(frames, ignore_index=True)
    df["report_date"] = pd.to_datetime(df["report_date"], format="%Y%m%d", errors="coerce")
    df = df[df["report_date"].notna()].copy()
    df["eps"] = pd.to_numeric(df["eps"], errors="coerce")
    df["tp"] = pd.to_numeric(df["tp"], errors="coerce")
    df["rscore"] = df["rating"].map(_rating_score)

    cal = pd.read_parquet(TRADE_CAL)
    open_cal = pd.DatetimeIndex(
        pd.to_datetime(cal.loc[cal["is_open"] == 1, "cal_date"], format="%Y%m%d")).sort_values()
    df["effective_date"] = strictly_next_open_trade_day(df["report_date"], open_cal)
    df = df[df["effective_date"].notna()].copy()
    df["org_author"] = df["org_name"].astype(str) + "|" + df["author_name"].astype(str)
    return df.sort_values("report_date").reset_index(drop=True)


def _consensus_at(rc: pd.DataFrame, asof: pd.Timestamp, fy1_quarter: str) -> pd.DataFrame:
    """Per-stock consensus visible at `asof` (effective_date<=asof, age-expired, 1 vote/analyst)."""
    lo = asof - pd.Timedelta(days=MAX_AGE_DAYS)
    vis = rc[(rc["effective_date"] <= asof) & (rc["report_date"] >= lo)]
    if vis.empty:
        return pd.DataFrame()
    # latest report per analyst (already sorted by report_date ascending → keep='last')
    latest = vis.drop_duplicates(subset=["ts_code", "org_author"], keep="last")
    rate = latest.groupby("ts_code").agg(
        n_analysts=("org_author", "nunique"),
        rating_score=("rscore", "mean"),
    )
    # FY1 annual EPS consensus: latest per analyst among the fy1 quarter rows
    fy = vis[vis["quarter"].astype(str) == fy1_quarter]
    fy_latest = fy.drop_duplicates(subset=["ts_code", "org_author"], keep="last")
    eps = fy_latest.groupby("ts_code")["eps"].agg(eps_fy1="mean", eps_fy1_std="std", eps_n="count")
    return rate.join(eps, how="left")


def build_consensus_panel(asof_dates, revision_lag=DEFAULT_REVISION_LAG, rc=None) -> pd.DataFrame:
    """Long panel MultiIndex(datetime, ts_code) of consensus features over `asof_dates`."""
    if rc is None:
        rc = load_report_rc()
    out = []
    for asof in pd.to_datetime(sorted(asof_dates)):
        fy1 = f"{asof.year}Q4"                         # current fiscal-year annual target
        now = _consensus_at(rc, asof, fy1)
        if now.empty:
            continue
        prev = _consensus_at(rc, asof - pd.Timedelta(days=revision_lag), fy1)
        df = now.copy()
        if not prev.empty:
            df["rating_revision"] = df["rating_score"] - prev["rating_score"].reindex(df.index)
            denom = prev["eps_fy1"].reindex(df.index).abs() + 1e-6
            df["eps_revision"] = (df["eps_fy1"] - prev["eps_fy1"].reindex(df.index)) / denom
        else:
            df["rating_revision"] = np.nan
            df["eps_revision"] = np.nan
        df["eps_dispersion"] = df["eps_fy1_std"] / (df["eps_fy1"].abs() + 1e-6)
        df["datetime"] = asof
        out.append(df.reset_index())
    panel = pd.concat(out, ignore_index=True)
    panel = panel.rename(columns={"index": "ts_code"})
    return panel.set_index(["datetime", "ts_code"]).sort_index()


FEATURES = ["n_analysts", "rating_score", "eps_fy1", "eps_dispersion",
            "rating_revision", "eps_revision"]


if __name__ == "__main__":
    # quick smoke: build on 3 IS dates, print coverage + sanity
    rc = load_report_rc()
    print(f"loaded report_rc: {len(rc):,} rows, {rc['ts_code'].nunique()} stocks, "
          f"rating mapped {rc['rscore'].notna().mean()*100:.0f}%, "
          f"effective>report all: {(rc['effective_date']>rc['report_date']).all()}")
    panel = build_consensus_panel(["2016-06-30", "2018-06-29", "2019-12-31"], rc=rc)
    print("\npanel shape:", panel.shape)
    for d, sub in panel.groupby(level=0):
        print(f"\n{d.date()}  stocks={len(sub)}  "
              f"n_analysts med={sub['n_analysts'].median():.0f}  "
              f"rating_score mean={sub['rating_score'].mean():.2f}  "
              f"eps_fy1 cov={sub['eps_fy1'].notna().mean()*100:.0f}%  "
              f"eps_rev cov={sub['eps_revision'].notna().mean()*100:.0f}%")
    print("\nfeature null% overall:")
    print((panel[FEATURES].isna().mean()*100).round(1).to_string())
