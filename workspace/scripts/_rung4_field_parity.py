"""果仁 parity rung-4: holding-level field/factor parity sweep.

Validates every REPRODUCIBLE 果仁-displayed factor against the local provider, at the
holding level (the rung-2/rung-3 method, generalized). For each factor: read the provider
fields for the held codes, compute the factor AS-OF the holding date (latest trading day
<= date, the served value), and compare to 果仁's displayed value across every book that
shows it. Auto-detects the display scale (果仁 shows 百分数/ratio).

Batch 1 = income/balance/cashflow statement factors (beyond rung-2's net profit).
NON-FORMAL parity diagnostic. Saves rung4_field_parity.json.
"""
from __future__ import annotations
import json
import sys
import glob
import os
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")
OUT = ROOT / "workspace" / "outputs" / "guorn_parity"


def _books_with(colsub):
    """Yield (book_path, exact_col) for books whose holdings show a column containing colsub."""
    for f in sorted(glob.glob(str(ROOT / "Knowledge/果仁回测结果/*.xlsx"))):
        try:
            import openpyxl  # noqa
            cols = pd.read_excel(f, sheet_name="各阶段持仓详单", nrows=0).columns.tolist()
        except Exception:
            continue
        names = [str(c) for c in cols]
        if "股票代码" not in names:  # skip fund/multi-asset books (基金代码)
            continue
        for c in cols:
            if colsub == str(c):
                yield f, c
                break


def _load_guorn(colsub):
    """All (qlib_code, date, guorn_value) across books showing the exact column `colsub`."""
    rows = []
    for f, col in _books_with(colsub):
        g = pd.read_excel(f, sheet_name="各阶段持仓详单")
        c6 = g["股票代码"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
        q = c6 + np.where(c6.str[0].isin(["6", "9"]), "_SH", "_SZ")
        d = pd.to_datetime(g["开始日期"])
        v = pd.to_numeric(g[col], errors="coerce")
        for a, b, c in zip(q, d, v):
            if pd.notna(c):
                rows.append((a, b, c))
    return pd.DataFrame(rows, columns=["q", "date", "gf"]).dropna()


def run_factor(D, name, colsub, fields, compute):
    g = _load_guorn(colsub)
    if g.empty:
        return {"factor": name, "status": "no_guorn_column"}
    insts = sorted(g["q"].unique())
    df = D.features(insts, fields, start_time="2013-06-01", end_time="2026-06-20", freq="day")
    df.columns = [c.replace("$", "") for c in fields]
    # per-instrument as-of panels
    wides = {c: df[c].unstack(level=0).sort_index() for c in df.columns}
    recs = []
    for _, r in g.iterrows():
        q, d = r["q"], r["date"]
        vals = {}
        ok = True
        for c, w in wides.items():
            if q not in w.columns:
                ok = False; break
            s = w[q]; pos = s.index.searchsorted(d, side="right") - 1
            vals[c] = s.iat[pos] if pos >= 0 else np.nan
        if not ok:
            continue
        loc = compute(vals)
        recs.append((r["gf"], loc))
    cmp = pd.DataFrame(recs, columns=["gf", "loc"]).dropna()
    if cmp.empty:
        return {"factor": name, "status": "no_overlap", "n_guorn": int(len(g))}
    # scale-detect: correct any POWER-OF-10 unit mismatch (% display, 元 vs 万元, etc.);
    # rounds the median(|loc/gf|) to the nearest power of 10 (a 2x would NOT be scaled away).
    ratio = (cmp["loc"] / cmp["gf"].replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).abs().dropna()
    med = ratio.median()
    scale = 10.0 ** round(float(np.log10(med))) if (med is not None and np.isfinite(med) and med > 0) else 1.0
    locs = cmp["loc"] / scale
    rel = (locs - cmp["gf"]).abs() / cmp["gf"].abs().clip(lower=0.05)
    return {
        "factor": name, "status": "ok", "n_guorn": int(len(g)), "n_matched": int(len(cmp)),
        "scale_applied": scale, "median_relerr": round(float(rel.median()), 6),
        "within_1pct": round(float((rel <= 0.01).mean()), 4),
        "within_5pct": round(float((rel <= 0.05).mean()), 4),
        "sign_match": round(float((np.sign(locs) == np.sign(cmp["gf"])).mean()), 4),
    }


def main():
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data/qlib_data"), region=REG_CN, kernels=1)

    def ttm(v, base):  # sum of 4 single-quarter slots q0..q3
        xs = [v[f"{base}_sq_q{i}"] for i in range(4)]
        return np.nan if any(pd.isna(x) for x in xs) else sum(xs)

    factors = [
        ("GrossProfit%AssetsQ", "GrossProfit%AssetsQ",
         ["$revenue_sq_q0", "$oper_cost_sq_q0", "$total_assets_q0"],
         lambda v: (v["revenue_sq_q0"] - v["oper_cost_sq_q0"]) / v["total_assets_q0"]
         if v["total_assets_q0"] else np.nan),
        ("SalesQGr%PY", "SalesQGr%PY",
         ["$revenue_sq_q0", "$revenue_sq_q4"],
         lambda v: (v["revenue_sq_q0"] - v["revenue_sq_q4"]) / abs(v["revenue_sq_q0"])
         if v["revenue_sq_q0"] else np.nan),
        ("负债资产率", "负债资产率",
         ["$total_liab_q0", "$total_assets_q0"],
         lambda v: v["total_liab_q0"] / v["total_assets_q0"] if v["total_assets_q0"] else np.nan),
        ("OPCFNPDiff%NP", "OPCFNPDiff%NP",
         [f"$n_cashflow_act_sq_q{i}" for i in range(4)] + [f"$n_income_sq_q{i}" for i in range(4)],
         lambda v: ((ttm(v, "n_cashflow_act") - ttm(v, "n_income")) / ttm(v, "n_income"))
         if ttm(v, "n_income") else np.nan),
        # ── valuation (point) ──
        # BP = 归属母公司股东权益合计/总市值 — PARENT-only equity (exc_min_int), reverse-engineered
        # 2026-06-23 vs 果仁's published formula. inc_min_int (total) is WRONG (5.9% vs 0.66%).
        # Residual = 总市值 signal-date timing (果仁 shows T-1) + 总市值 2-dec display rounding.
        ("BP", "BP",
         ["$total_hldr_eqy_exc_min_int_q0", "$total_mv"],
         lambda v: v["total_hldr_eqy_exc_min_int_q0"] / v["total_mv"] if v["total_mv"] else np.nan),
        ("市盈率", "市盈率",  # validate the provider $pe_ttm field directly
         ["$pe_ttm"], lambda v: v["pe_ttm"]),
    ]
    results = []
    for name, col, fields, compute in factors:
        res = run_factor(D, name, col, fields, compute)
        results.append(res)
        print(json.dumps(res, ensure_ascii=False))
    OUT.joinpath("rung4_field_parity.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
