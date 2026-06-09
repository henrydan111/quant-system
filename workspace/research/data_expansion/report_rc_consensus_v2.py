"""Wave-1A v2 — stronger analyst-alpha feature forms (refinement of the NO-GO).

The v1 pilot tested magnitude revisions + levels and found them weak. This builds
the literature's stronger forms, in the SAME PIT-correct framework:

  eps_diffusion   net % of analysts RAISING their FY1 EPS over a trailing window
                  (a sign/breadth index, not a magnitude — outlier-robust)
  rating_diffusion net % of analysts RAISING their rating over the window
  rec_up_net      recommendation-CHANGE EVENT: net (upgrades−downgrades) in the
                  last `event_window` days / n_analysts (the alpha concentrates
                  right after the change; a monthly snapshot of the level misses it)
  tp_consensus    mean sanitized target price (→ target-implied return = tp/close−1
                  computed in the harness, where close is available)

Per-analyst direction = compare each analyst's two most recent forecasts (sorted by
report_date) within the visibility-respecting window. Reuses load_report_rc (PIT anchor).
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
from report_rc_consensus import load_report_rc, MAX_AGE_DAYS  # noqa: E402

REV_WINDOW_DAYS = 120     # an analyst needs time to issue 2 reports
EVENT_WINDOW_DAYS = 60    # "recent" rating-change horizon
TP_MIN, TP_MAX = 0.0, 10000.0


def _pairwise(df: pd.DataFrame, valcol: str) -> pd.DataFrame:
    """Per (ts_code, org_author): latest & second-latest value + latest date + direction."""
    s = df.dropna(subset=[valcol]).sort_values("report_date")
    if s.empty:
        return pd.DataFrame(columns=["dir", "last_date"])
    agg = s.groupby(["ts_code", "org_author"]).agg(
        last=(valcol, "last"),
        prev=(valcol, lambda x: x.iloc[-2] if len(x) >= 2 else np.nan),
        last_date=("report_date", "last"),
    )
    agg["dir"] = np.sign(agg["last"] - agg["prev"])
    return agg.reset_index()


def _diffusion_by_stock(pw: pd.DataFrame, asof, event_window) -> pd.DataFrame:
    """Aggregate per-analyst directions to per-stock breadth + recent-event net."""
    if pw.empty:
        return pd.DataFrame()
    d = pw.copy()
    d["up"] = (d["dir"] > 0).astype(int)
    d["down"] = (d["dir"] < 0).astype(int)
    recent = d["last_date"] >= (asof - pd.Timedelta(days=event_window))
    d["up_r"] = (d["up"] & recent).astype(int)
    d["down_r"] = (d["down"] & recent).astype(int)
    g = d.groupby("ts_code").agg(n_up=("up", "sum"), n_down=("down", "sum"),
                                 up_r=("up_r", "sum"), dn_r=("down_r", "sum"),
                                 n_rev=("dir", "count"))
    denom = (g["n_up"] + g["n_down"]).replace(0, np.nan)
    g["diffusion"] = (g["n_up"] - g["n_down"]) / denom
    g["rec_net"] = g["up_r"] - g["dn_r"]
    return g[["diffusion", "rec_net", "n_rev"]]


def build_consensus_panel_v2(asof_dates, rc=None,
                             rev_window=REV_WINDOW_DAYS, event_window=EVENT_WINDOW_DAYS) -> pd.DataFrame:
    if rc is None:
        rc = load_report_rc()
    out = []
    for asof in pd.to_datetime(sorted(asof_dates)):
        fy1 = f"{asof.year}Q4"
        lo_age = asof - pd.Timedelta(days=MAX_AGE_DAYS)
        lo_rev = asof - pd.Timedelta(days=rev_window)
        vis = rc[(rc["effective_date"] <= asof) & (rc["report_date"] >= lo_age)]
        if vis.empty:
            continue
        vis_rev = vis[vis["report_date"] >= lo_rev]
        n_analysts = vis.groupby("ts_code")["org_author"].nunique().rename("n_analysts")

        # EPS diffusion (fy1 rows)
        eps_pw = _pairwise(vis_rev[vis_rev["quarter"].astype(str) == fy1], "eps")
        eps_d = _diffusion_by_stock(eps_pw, asof, event_window).add_prefix("eps_")
        # Rating diffusion + rec events (one rating per report)
        rat = vis_rev.drop_duplicates(subset=["ts_code", "org_author", "report_date"])
        rat_pw = _pairwise(rat, "rscore")
        rat_d = _diffusion_by_stock(rat_pw, asof, event_window).add_prefix("rat_")
        # target price consensus (latest per analyst, sanitized)
        tpv = vis[(vis["tp"] > TP_MIN) & (vis["tp"] < TP_MAX)]
        tp_latest = tpv.sort_values("report_date").drop_duplicates(
            subset=["ts_code", "org_author"], keep="last")
        tp_c = tp_latest.groupby("ts_code")["tp"].mean().rename("tp_consensus")

        df = pd.concat([n_analysts, eps_d, rat_d, tp_c], axis=1)
        df["rec_up_net"] = (df.get("rat_rec_net", np.nan)) / df["n_analysts"]
        df["datetime"] = asof
        out.append(df.reset_index().rename(columns={"index": "ts_code"}))
    panel = pd.concat(out, ignore_index=True).set_index(["datetime", "ts_code"]).sort_index()
    panel = panel.rename(columns={"eps_diffusion": "eps_diffusion",
                                  "rat_diffusion": "rating_diffusion"})
    return panel


V2_FEATURES = ["eps_diffusion", "rating_diffusion", "rec_up_net", "tp_implied_return"]


if __name__ == "__main__":
    rc = load_report_rc(years=range(2010, 2021))
    p = build_consensus_panel_v2(["2016-06-30", "2018-06-29", "2019-12-31"], rc=rc)
    print("v2 panel shape:", p.shape, "\ncols:", list(p.columns))
    for d, sub in p.groupby(level=0):
        print(f"{d.date()} stocks={len(sub)} "
              f"eps_diff cov={sub['eps_diffusion'].notna().mean()*100:.0f}% "
              f"rat_diff cov={sub['rating_diffusion'].notna().mean()*100:.0f}% "
              f"tp cov={sub['tp_consensus'].notna().mean()*100:.0f}% "
              f"eps_diff mean={sub['eps_diffusion'].mean():.3f}")
