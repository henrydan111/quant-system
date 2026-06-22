"""Rung-2 PIT validation: does the LOCAL provider PIT income-statement serving
reproduce 果仁's per-holding 净利润(单季) values? (the crux rung-2 validates).

果仁's 各阶段持仓详单 carries 净利润(万) for every held name as-of each rebalance.
We read the local provider's PIT single-quarter net profit AS-OF the same rebalance
day via the Qlib provider (the materialized `$..._sq_q0` bins the factor library
consumes — PIT-anchored on effective_date by the backend builder), and compare.
Tests BOTH candidate fields to settle which 果仁's plain "净利润(单季)" maps to:
  $n_income_sq_q0          (总净利润单季, incl. minority)
  $n_income_attr_p_sq_q0   (归母净利润单季)

Throwaway validation utility (sandbox; reads the already-PIT-materialized provider
field as-of the date — no hand-rolled alignment).
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

XLSX = ROOT / "Knowledge" / "果仁回测结果" / "16_sm_noc_纯市值正盈利_v4.xlsx"
FIELDS = ["$n_income_sq_q0", "$n_income_attr_p_sq_q0"]


def main():
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    code6 = h["股票代码"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    h = h.assign(qlib=code6 + "_SZ",                       # 002/003 all SZSE
                 date=pd.to_datetime(h["开始日期"]),
                 np_wan=pd.to_numeric(h["净利润(万)"], errors="coerce")).dropna(subset=["np_wan"])

    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)
    insts = sorted(h["qlib"].unique())
    lo, hi = h["date"].min().strftime("%Y-%m-%d"), h["date"].max().strftime("%Y-%m-%d")
    print(f"[validate] {len(h)} holding-rows | {len(insts)} names | {lo}..{hi}", flush=True)
    df = D.features(insts, FIELDS, start_time=lo, end_time=hi, freq="day")
    df.columns = [c.replace("$", "") for c in FIELDS]

    for field in df.columns:
        wide = df[field].unstack(level=0)        # (instrument, datetime) -> datetime x instrument
        wide = wide.sort_index()
        recs = []
        for dt, sub in h.groupby("date"):
            if dt not in wide.index:
                # snap to the as-of trading day <= dt
                pos = wide.index.searchsorted(dt, side="right") - 1
                if pos < 0:
                    continue
                row = wide.iloc[pos]
            else:
                row = wide.loc[dt]
            for q, gnp in zip(sub["qlib"], sub["np_wan"]):
                local = row.get(q, np.nan)
                recs.append((gnp, local))
        cmp = pd.DataFrame(recs, columns=["guorn_wan", "local_raw"]).dropna()
        if cmp.empty:
            print(f"\n{field}: NO overlap"); continue
        # unit probe: ratio local_raw / (果仁 万) — ~1e4 => provider in 元, ~1 => 万
        ratio = (cmp["local_raw"] / cmp["guorn_wan"].replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).dropna()
        scale = 1e4 if ratio.median() > 100 else 1.0
        local_wan = cmp["local_raw"] / scale
        denom = cmp["guorn_wan"].abs().clip(lower=1.0)
        relerr = (local_wan - cmp["guorn_wan"]).abs() / denom
        print(f"\n=== {field} ===   (median local/果仁 ratio={ratio.median():.1f} -> scale={scale:g}: provider in {'元' if scale>1 else '万'})")
        print(f"  matched: {len(cmp)}/{len(h)} ({len(cmp)/len(h):.1%}) | median rel-err {relerr.median():.4f} | mean {relerr.mean():.4f}")
        for thr in (0.001, 0.01, 0.05, 0.10):
            print(f"  within {thr:>5.1%}: {(relerr <= thr).mean():.1%}")
        for g, l in zip(cmp["guorn_wan"].head(6), local_wan.head(6)):
            print(f"    果仁={g:>14.2f}  local={l:>14.2f}  relerr={abs(l-g)/max(abs(g),1):.4f}")


if __name__ == "__main__":
    main()
