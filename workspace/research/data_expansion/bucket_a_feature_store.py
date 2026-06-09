"""Bucket A PIT feature store (ML-ready) — all 8 new-data endpoints → one panel.

Assembles a point-in-time-correct feature matrix MultiIndex(datetime, instrument[qlib])
from every Bucket A dataset, on a monthly as-of grid, with forward-return labels. SANDBOX
research artifact (no Qlib-provider / field-registry governance — that is only for formal
standalone factors); PIT-correctness is still enforced via the canonical visibility anchor.

PIT anchor: every feature is visible only from `strictly_next_open_trade_day(disclosure_date)`.
  report_rc            -> next_open(report_date)                 [validated: eps_diffusion strong]
  express              -> next_open(ann_date)
  disclosure_date      -> next_open(ann_date) / forward pre_date
  fina_mainbz          -> next_open(end_date + 120d)  (no ann_date in schema; conservative lag)
  repurchase           -> next_open(ann_date)
  pledge_stat          -> next_open(end_date + 7d)    (weekly stat date; conservative lag)
  top10_floatholders   -> next_open(ann_date)
  fina_audit           -> next_open(ann_date)

Output: workspace/outputs/feature_store/bucket_a_features_monthly.parquet + manifest.json
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT)); sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(HERE.parent))

from data_infra.pit_backend import strictly_next_open_trade_day  # noqa: E402
from report_rc_consensus import load_report_rc, build_consensus_panel  # noqa: E402
from report_rc_consensus_v2 import build_consensus_panel_v2  # noqa: E402

DATA = PROJECT_ROOT / "data"
OUT = PROJECT_ROOT / "workspace" / "outputs" / "feature_store"


def open_cal():
    cal = pd.read_parquet(DATA / "reference" / "trade_cal.parquet")
    return pd.DatetimeIndex(pd.to_datetime(cal.loc[cal["is_open"] == 1, "cal_date"],
                                           format="%Y%m%d")).sort_values()


def month_ends(y0, y1, cal):
    od = cal[(cal.year >= y0) & (cal.year <= y1)]
    return sorted(pd.Series(od).groupby(od.to_period("M")).max().tolist())


def _read_years(subdir, pattern_years):
    frames = []
    for f in sorted((DATA / subdir).glob("*.parquet")):
        frames.append(pd.read_parquet(f))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def latest_visible(df, asof_dates, eff_col, value_cols, agg=None):
    """For each as-of date, the latest visible row per stock (effective<=asof)."""
    df = df[df[eff_col].notna()].sort_values(eff_col)
    out = []
    for asof in asof_dates:
        vis = df[df[eff_col] <= asof]
        if vis.empty:
            continue
        latest = vis.drop_duplicates(subset=["ts_code"], keep="last")
        rows = latest[["ts_code"] + value_cols].copy()
        if agg:
            rows = agg(vis, latest, asof)
        rows["datetime"] = asof
        out.append(rows)
    if not out:
        return pd.DataFrame()
    return pd.concat(out, ignore_index=True).set_index(["datetime", "ts_code"])


# ---- per-dataset extractors -------------------------------------------------
def f_report_rc(asof, cal):
    rc = load_report_rc(years=range(2010, 2027))
    v1 = build_consensus_panel(asof, rc=rc)[
        ["n_analysts", "rating_score", "eps_fy1", "eps_dispersion", "rating_revision", "eps_revision"]]
    v2 = build_consensus_panel_v2(asof, rc=rc)[["eps_diffusion", "rating_diffusion"]]
    df = v1.join(v2, how="outer")
    return df.add_prefix("rc_")


def f_express(asof, cal):
    df = _read_years("fundamentals/express", None)
    if df.empty:
        return pd.DataFrame()
    df["ann"] = pd.to_datetime(df["ann_date"], format="%Y%m%d", errors="coerce")
    df["eff"] = strictly_next_open_trade_day(df["ann"], cal)
    for c in ["yoy_net_profit", "diluted_roe"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    out = latest_visible(df, asof, "eff", ["yoy_net_profit", "diluted_roe"])
    return out.rename(columns={"yoy_net_profit": "exp_npy_yoy", "diluted_roe": "exp_roe"})


def f_repurchase(asof, cal):
    df = _read_years("corporate/repurchase", None)
    if df.empty:
        return pd.DataFrame()
    df["ann"] = pd.to_datetime(df["ann_date"], format="%Y%m%d", errors="coerce")
    df["eff"] = strictly_next_open_trade_day(df["ann"], cal)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df[df["eff"].notna()].sort_values("eff")
    out = []
    for a in asof:
        win = df[(df["eff"] <= a) & (df["eff"] >= a - pd.Timedelta(days=180))]
        if win.empty:
            continue
        g = win.groupby("ts_code").agg(repo_amount_180d=("amount", "sum"),
                                       repo_events_180d=("amount", "size"))
        g["repo_active"] = 1.0
        g["datetime"] = a
        out.append(g.reset_index())
    return pd.concat(out, ignore_index=True).set_index(["datetime", "ts_code"]) if out else pd.DataFrame()


def f_pledge(asof, cal):
    df = _read_years("corporate/pledge_stat", None)
    if df.empty:
        return pd.DataFrame()
    df["end"] = pd.to_datetime(df["end_date"], format="%Y%m%d", errors="coerce") + pd.Timedelta(days=7)
    df["eff"] = strictly_next_open_trade_day(df["end"], cal)
    df["pledge_ratio"] = pd.to_numeric(df["pledge_ratio"], errors="coerce")
    return latest_visible(df, asof, "eff", ["pledge_ratio"]).add_prefix("pledge_")


def f_top10(asof, cal):
    df = _read_years("corporate/top10_floatholders", None)
    if df.empty:
        return pd.DataFrame()
    df["ann"] = pd.to_datetime(df["ann_date"], format="%Y%m%d", errors="coerce")
    df["eff"] = strictly_next_open_trade_day(df["ann"], cal)
    df["hold_ratio"] = pd.to_numeric(df["hold_ratio"], errors="coerce")
    df["hold_change"] = pd.to_numeric(df["hold_change"], errors="coerce")
    df = df[df["eff"].notna()].sort_values("eff")
    out = []
    for a in asof:
        vis = df[df["eff"] <= a]
        if vis.empty:
            continue
        # latest period per stock = max eff; aggregate its 10 holders
        latest_eff = vis.groupby("ts_code")["eff"].transform("max")
        cur = vis[vis["eff"] == latest_eff]
        g = cur.groupby("ts_code").agg(float_top10_share=("hold_ratio", "sum"),
                                       float_hold_change=("hold_change", "sum"))
        g["datetime"] = a
        out.append(g.reset_index())
    return pd.concat(out, ignore_index=True).set_index(["datetime", "ts_code"]) if out else pd.DataFrame()


def f_audit(asof, cal):
    df = _read_years("fundamentals/fina_audit", None)
    if df.empty:
        return pd.DataFrame()
    df["ann"] = pd.to_datetime(df["ann_date"], format="%Y%m%d", errors="coerce")
    df["eff"] = strictly_next_open_trade_day(df["ann"], cal)
    std = df["audit_result"].astype(str).str.contains("标准无保留", na=False)
    df["audit_nonstandard"] = (~std).astype(float)
    return latest_visible(df, asof, "eff", ["audit_nonstandard"])


def f_mainbz(asof, cal):
    df = _read_years("fundamentals/fina_mainbz", None)
    if df.empty:
        return pd.DataFrame()
    df["end"] = pd.to_datetime(df["end_date"], format="%Y%m%d", errors="coerce") + pd.Timedelta(days=120)
    df["eff"] = strictly_next_open_trade_day(df["end"], cal)
    df["bz_sales"] = pd.to_numeric(df["bz_sales"], errors="coerce")
    df = df[df["eff"].notna() & (df["bz_sales"] > 0)].sort_values("eff")
    out = []
    for a in asof:
        vis = df[df["eff"] <= a]
        if vis.empty:
            continue
        latest_eff = vis.groupby("ts_code")["eff"].transform("max")
        cur = vis[vis["eff"] == latest_eff]
        def hhi(s):
            w = s / s.sum()
            return float((w ** 2).sum())
        g = cur.groupby("ts_code")["bz_sales"].agg(mainbz_hhi=hhi, mainbz_n_seg="size")
        g["datetime"] = a
        out.append(g.reset_index())
    return pd.concat(out, ignore_index=True).set_index(["datetime", "ts_code"]) if out else pd.DataFrame()


def f_disclosure(asof, cal):
    df = _read_years("fundamentals/disclosure_date", None)
    if df.empty:
        return pd.DataFrame()
    df["ann"] = pd.to_datetime(df["ann_date"], format="%Y%m%d", errors="coerce")
    df["eff"] = strictly_next_open_trade_day(df["ann"], cal)
    df["pre"] = pd.to_datetime(df["pre_date"], format="%Y%m%d", errors="coerce")
    df = df[df["eff"].notna()].sort_values("eff")
    out = []
    for a in asof:
        vis = df[df["eff"] <= a].drop_duplicates(subset=["ts_code"], keep="last")
        upcoming = vis[vis["pre"] >= a]
        if upcoming.empty:
            continue
        g = pd.DataFrame({"ts_code": upcoming["ts_code"].values,
                          "disc_days_to_report": (upcoming["pre"] - a).dt.days.clip(0, 200).values})
        g["datetime"] = a
        out.append(g)
    return pd.concat(out, ignore_index=True).set_index(["datetime", "ts_code"]) if out else pd.DataFrame()


EXTRACTORS = {"report_rc": f_report_rc, "express": f_express, "disclosure": f_disclosure,
              "repurchase": f_repurchase, "pledge": f_pledge, "top10": f_top10,
              "audit": f_audit, "mainbz": f_mainbz}


def build(y0=2014, y1=2020):
    cal = open_cal()
    asof = month_ends(y0, y1, cal)
    panels, manifest = [], {}
    for name, fn in EXTRACTORS.items():
        p = fn(asof, cal)
        if p is None or p.empty:
            print(f"  {name}: EMPTY"); continue
        panels.append(p)
        manifest[name] = {"features": list(p.columns), "rows": int(len(p)),
                          "coverage_per_feature_pct": {c: round(p[c].notna().mean() * 100, 1)
                                                       for c in p.columns}}
        print(f"  {name}: {p.shape} cols={list(p.columns)}")
    feat = pd.concat(panels, axis=1).sort_index()
    feat.index = feat.index.set_names(["datetime", "ts_code"])
    return feat, asof, manifest


LABEL_HORIZONS = [5, 20, 60]


def add_labels_qlib(feat, asof):
    """Convert ts_code->qlib instrument and join forward-return labels (the ML targets)."""
    from alpha_research.factor_library.operators import compute_factors
    fq = feat.reset_index()
    fq["instrument"] = fq["ts_code"].str.replace(".", "_", regex=False)
    fq = fq.drop(columns="ts_code").set_index(["datetime", "instrument"]).sort_index()
    _, fwd = compute_factors({"px": "$close"}, "2014-01-01", "2021-06-01",
                             horizons=LABEL_HORIZONS, stage="is_only")
    asof_set = set(pd.to_datetime(asof))
    fwd = fwd[fwd.index.get_level_values(0).isin(asof_set)]
    for h in LABEL_HORIZONS:
        fq[f"label_fwd_{h}d"] = fwd[f"fwd_{h}d"].reindex(fq.index)
    return fq


if __name__ == "__main__":
    feat, asof, manifest = build(2014, 2020)
    print(f"\nUNIFIED feature panel: {feat.shape}  ({feat.index.get_level_values(1).nunique()} stocks)")
    ml = add_labels_qlib(feat, asof)
    feat_cols = [c for c in ml.columns if not c.startswith("label_")]
    label_cols = [c for c in ml.columns if c.startswith("label_")]
    print("feature + label coverage (%):")
    print((ml.notna().mean() * 100).round(1).to_string())

    OUT.mkdir(parents=True, exist_ok=True)
    ml.reset_index().to_parquet(OUT / "bucket_a_ml_monthly.parquet", index=False)
    manifest["_meta"] = {
        "grid": "monthly month-end, IS 2014-2020 (OOS 2021-2026 NOT included)",
        "index": "(datetime, instrument[qlib_format])",
        "rows": int(len(ml)), "n_features": len(feat_cols), "features": feat_cols,
        "labels": label_cols, "label_def": "fwd_Hd = forward H-trading-day return from close",
        "pit": "every feature visible only from strictly_next_open_trade_day(disclosure_date)",
        "status": "SANDBOX ML feature store — NOT formal Qlib fields / not registry-governed",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT/'bucket_a_ml_monthly.parquet'}  ({len(feat_cols)} features + {len(label_cols)} labels)")
