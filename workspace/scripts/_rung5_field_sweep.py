"""果仁 parity rung-5: targeted field sweep of the OPEN data paths (holding-level parity).

Validates the data paths NOT yet covered by rungs 1-4, via the 果仁 indicators that exercise them:
  · 股息率TTM         → $dv_ttm                                  (dividend-yield path)
  · RnDQGR%PY         → ($rd_exp_sq_q0-$rd_exp_sq_q4)/$rd_exp_sq_q4   (R&D path; single-quarter YoY)
  · CoreProfitQ       → 营收−营业成本−(管理+销售+财务费用)−营业税金及附加 (single-q)
                        = $revenue_sq_q0 − $oper_cost_sq_q0 − ($admin_exp_sq_q0+$sell_exp_sq_q0
                          +$fin_exp_sq_q0) − $biz_tax_surchg_sq_q0   (EXPENSE-LINE path, all at once)
  · 股东数下降率       → $holder_num_q4/$holder_num_q0 − 1          (holder-count path)

Each tried at signal lag 0 and 1 with power-of-10 scale-detect (per the rung-4 conventions).
NOT covered (recorded as gaps, not run): 折旧摊销/D&A fields NOT materialized (EBITDAQ/FCFQ
unreproducible); share-count already validated via 总市值 (=close×total_share, penny-exact).
NON-FORMAL diagnostic. Writes rung5_field_sweep.json.
"""
from __future__ import annotations
import json
import sys
import glob
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")
OUT = ROOT / "workspace" / "outputs" / "guorn_parity"


def _load(match_fn):
    """All (qlib_code, date, guorn_value) across books whose holdings show a column matching match_fn."""
    rows = []
    for f in sorted(glob.glob(str(ROOT / "Knowledge/果仁回测结果/*.xlsx"))):
        try:
            names = [str(c) for c in pd.read_excel(f, sheet_name="各阶段持仓详单", nrows=0).columns]
        except Exception:
            continue
        if "股票代码" not in names:
            continue
        col = next((c for c in names if match_fn(c)), None)
        if col is None:
            continue
        g = pd.read_excel(f, sheet_name="各阶段持仓详单")
        c6 = g["股票代码"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
        q = c6 + np.where(c6.str[0].isin(["6", "9"]), "_SH", "_SZ")
        d = pd.to_datetime(g["开始日期"]); v = pd.to_numeric(g[col], errors="coerce")
        for a, b, c in zip(q, d, v):
            if pd.notna(c):
                rows.append((a, b, c))
    return pd.DataFrame(rows, columns=["q", "date", "gf"]).dropna()


def _asof(wides, q, d, lag):
    vals = {}
    for c, w in wides.items():
        if q not in w.columns:
            return None
        s = w[q]; pos = s.index.searchsorted(d, side="right") - 1 - lag
        vals[c] = s.iat[pos] if pos >= 0 else np.nan
    return vals


def _run(D, name, match_fn, fields, compute, floor=0.02):
    g = _load(match_fn)
    if g.empty:
        return {"factor": name, "status": "no_guorn_column"}
    insts = sorted(g["q"].unique())
    df = D.features(insts, fields, start_time="2012-06-01", end_time="2026-06-20", freq="day")
    df.columns = [c.replace("$", "") for c in fields]
    wides = {c: df[c].unstack(level=0).sort_index() for c in df.columns}
    best = None
    for lag in (0, 1):
        recs = []
        for r in g.itertuples():
            vals = _asof(wides, r.q, r.date, lag)
            if vals is None:
                continue
            try:
                loc = compute(vals)
            except Exception:
                loc = np.nan
            if np.isfinite(loc):
                recs.append((r.gf, loc))
        cmp = pd.DataFrame(recs, columns=["gf", "loc"]).dropna()
        if cmp.empty:
            continue
        ratio = (cmp["loc"] / cmp["gf"].replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).abs().dropna()
        med = ratio.median()
        scale = 10.0 ** round(float(np.log10(med))) if (np.isfinite(med) and med > 0) else 1.0
        locs = cmp["loc"] / scale
        rel = (locs - cmp["gf"]).abs() / cmp["gf"].abs().clip(lower=floor)
        st = {"n": int(len(cmp)), "lag": lag, "scale": scale,
              "median_relerr": round(float(rel.median()), 6),
              "within_1pct": round(float((rel <= 0.01).mean()), 4),
              "within_5pct": round(float((rel <= 0.05).mean()), 4),
              "sign_match": round(float((np.sign(locs) == np.sign(cmp["gf"])).mean()), 4)}
        if best is None or st["median_relerr"] < best["median_relerr"]:
            best = st
    return {"factor": name, "status": "ok", "n_guorn": int(len(g)), **(best or {})}


def main():
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data/qlib_data"), region=REG_CN, kernels=1)

    factors = [
        ("股息率TTM(dividend)", lambda c: c == "股息率TTM",
         ["$dv_ttm"], lambda v: v["dv_ttm"]),
        ("RnDQGR%PY(R&D)", lambda c: c.upper() == "RNDQGR%PY",
         ["$rd_exp_sq_q0", "$rd_exp_sq_q4"],
         lambda v: (v["rd_exp_sq_q0"] - v["rd_exp_sq_q4"]) / v["rd_exp_sq_q4"] if v["rd_exp_sq_q4"] else np.nan),
        ("CoreProfitQ(expense lines)", lambda c: c == "CoreProfitQ",
         ["$revenue_sq_q0", "$oper_cost_sq_q0", "$admin_exp_sq_q0", "$sell_exp_sq_q0",
          "$fin_exp_sq_q0", "$biz_tax_surchg_sq_q0"],
         lambda v: v["revenue_sq_q0"] - v["oper_cost_sq_q0"]
                   - (v["admin_exp_sq_q0"] + v["sell_exp_sq_q0"] + v["fin_exp_sq_q0"])
                   - v["biz_tax_surchg_sq_q0"]),
        ("股东数下降率(holder count)", lambda c: ("股东数" in c) and ("REF" in c.upper()) and ("/股东数-1" in c),
         ["$holder_num_q0", "$holder_num_q4"],
         lambda v: v["holder_num_q4"] / v["holder_num_q0"] - 1.0 if v["holder_num_q0"] else np.nan),
    ]
    results = []
    for name, match_fn, fields, compute in factors:
        res = _run(D, name, match_fn, fields, compute)
        results.append(res)
        print(json.dumps(res, ensure_ascii=False), flush=True)
    OUT.joinpath("rung5_field_sweep.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n[done]", flush=True)


if __name__ == "__main__":
    main()
