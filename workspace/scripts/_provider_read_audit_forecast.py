"""Rung-3 FINAL registration gate (GPT R2 M1): the full-market PROVIDER-READ audit.

Reads $forecast__np_q_yoy back THROUGH Qlib from the full-market staged provider (the
publish candidate) — NOT recomputed from raw ledgers — and proves:
  1. it reproduces 果仁 at full scope (all held codes across the 5 forecast books that are
     built), provider-read;
  2. coverage by year from the served field (non-null stock count on each year-end);
  3. the NaN-before-computable behaviour is present (a non-trivial NaN fraction, consistent
     with the forecast-before-income transition windows).
Saves rung3_forecast_provider_read_audit.json.

Usage: python workspace/scripts/_provider_read_audit_forecast.py [build_dir]
       (defaults to the most-recent data/qlib_builds/* staged provider)
"""
from __future__ import annotations
import glob
import json
import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")
OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
BOOKS = ["01_sm_01_成长动量", "07_sm_大制造GARP_v3", "10_sm_双创研发强度_v1",
         "48_成长_高波@周期", "53_ST_大市值_v3"]


def main():
    build = sys.argv[1] if len(sys.argv) > 1 else sorted(
        glob.glob(str(ROOT / "data/qlib_builds/*/")), key=os.path.getmtime)[-1]
    prov = os.path.join(build, "provider")
    built = sorted(os.path.basename(p).upper() for p in glob.glob(os.path.join(prov, "features", "*"))
                   if os.path.exists(os.path.join(p, "forecast__np_q_yoy.day.bin")))
    print(f"[provider-read] build={build}  built stocks with forecast__np_q_yoy = {len(built)}", flush=True)

    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=prov, region=REG_CN, kernels=1)

    # --- 1. 果仁 reproduction (provider-read) across all built held codes ---
    df = D.features(built, ["$forecast__np_q_yoy"], start_time="2013-06-01", end_time="2026-06-20", freq="day")
    df.columns = ["f"]
    wide = df["f"].unstack(level=0).sort_index()
    rows = []
    for b in BOOKS:
        p = ROOT / "Knowledge" / "果仁回测结果" / f"{b}.xlsx"
        if not p.exists():
            continue
        g = pd.read_excel(p, sheet_name="各阶段持仓详单")
        col = next((c for c in g.columns if "业绩预告净利润QGr" in str(c)), None)
        if col is None:
            continue
        c6 = g["股票代码"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
        g = g.assign(q=c6 + np.where(c6.str[0].isin(["6", "9"]), "_SH", "_SZ"),
                     date=pd.to_datetime(g["开始日期"]), gf=pd.to_numeric(g[col], errors="coerce")).dropna(subset=["gf"])
        g = g[g["q"].isin(wide.columns)]
        for _, r in g.iterrows():
            s = wide[r["q"]]; s = s[s.index <= r["date"]]
            loc = s.dropna().iloc[-1] if s.notna().any() else np.nan
            if pd.notna(loc):
                rows.append((r["gf"], loc))
    cmp = pd.DataFrame(rows, columns=["guorn", "prov"])
    rel = (cmp["prov"] - cmp["guorn"]).abs() / cmp["guorn"].abs().clip(lower=0.05)

    # --- 2. coverage by year (non-null served stocks on each year-end) ---
    cov = {}
    for yr in range(2014, 2027):
        dts = wide.index[wide.index <= pd.Timestamp(yr, 12, 31)]
        if len(dts) == 0:
            continue
        row = wide.loc[dts[-1]]
        cov[yr] = int(row.notna().sum())

    # --- 3. NaN fraction over the served panel (the transition-window NaNs + pre-coverage) ---
    served = wide.notna()
    nonnull_frac = float(served.values.mean())

    audit = {
        "build_dir": build, "built_stocks_with_field": len(built),
        "guorn_provider_read": {
            "n_holdings_matched": int(len(cmp)),
            "median_relerr": float(rel.median()), "within_1pct": float((rel <= 0.01).mean()),
            "within_5pct": float((rel <= 0.05).mean()),
            "sign_match": float((np.sign(cmp["prov"]) == np.sign(cmp["guorn"])).mean()),
        },
        "coverage_nonnull_stocks_by_yearend": cov,
        "served_panel_nonnull_fraction": nonnull_frac,
    }
    OUT.joinpath("rung3_forecast_provider_read_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
