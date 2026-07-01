"""果仁 #59 Comp_Core_Quality — holding-level factor parity (Phase B of the strategy harness).

Validates the 9/12 reproducible ranking factors + the 扣非PE filter against 果仁's displayed
per-holding values (the 各阶段持仓详单 sheet shows every factor value). Method = rung-4/5
(read provider fields for held codes, compute AS-OF the holding date = the served value,
scale-detect, compare). For semantically-uncertain factors (应收账款周转率, 扣非PE, HAVG) it
tests several candidate formulas and reports which matches 果仁.

Excluded by design: slots 7,8 STDEVQ(.,12) (need 12q depth, provider has q0..q4) + slot 10
中性ROE (irreducible neutralization, inert anyway). NON-FORMAL parity diagnostic.
Saves workspace/outputs/guorn_parity/guorn59_factor_parity.json.
"""
from __future__ import annotations
import json, sys, glob
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")
OUT = ROOT / "workspace" / "outputs" / "guorn_parity"


def _books_with(colsub):
    for f in sorted(glob.glob(str(ROOT / "Knowledge/果仁回测结果/*.xlsx"))):
        try:
            cols = pd.read_excel(f, sheet_name="各阶段持仓详单", nrows=0).columns.tolist()
        except Exception:
            continue
        if "股票代码" not in [str(c) for c in cols]:
            continue
        for c in cols:
            if colsub == str(c):
                yield f, c
                break


def _load_guorn(colsub):
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
    df = D.features(insts, fields, start_time="2012-06-01", end_time="2026-06-20", freq="day")
    df.columns = [c.replace("$", "") for c in fields]
    wides = {c: df[c].unstack(level=0).sort_index() for c in df.columns}
    recs = []
    for _, r in g.iterrows():
        q, d = r["q"], r["date"]
        vals, ok = {}, True
        for c, w in wides.items():
            if q not in w.columns:
                ok = False; break
            s = w[q]; pos = s.index.searchsorted(d, side="right") - 1
            vals[c] = s.iat[pos] if pos >= 0 else np.nan
        if not ok:
            continue
        try:
            loc = compute(vals)
        except Exception:
            loc = np.nan
        recs.append((r["gf"], loc))
    cmp = pd.DataFrame(recs, columns=["gf", "loc"]).dropna()
    if cmp.empty:
        return {"factor": name, "status": "no_overlap", "n_guorn": int(len(g))}
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


def ttm(v, base):
    xs = [v[f"{base}_sq_q{i}"] for i in range(4)]
    return np.nan if any(pd.isna(x) for x in xs) else sum(xs)


def avgq(v, base, n=4):
    xs = [v[f"{base}_q{i}"] for i in range(n)]
    return np.nan if any(pd.isna(x) for x in xs) else sum(xs) / n


def coreprofit_q0(v):
    keys = ["revenue_sq_q0", "oper_cost_sq_q0", "admin_exp_sq_q0", "sell_exp_sq_q0",
            "fin_exp_sq_q0", "biz_tax_surchg_sq_q0"]
    if any(pd.isna(v[k]) for k in keys):
        return np.nan
    return (v["revenue_sq_q0"] - v["oper_cost_sq_q0"] - (v["admin_exp_sq_q0"] + v["sell_exp_sq_q0"]
            + v["fin_exp_sq_q0"]) - v["biz_tax_surchg_sq_q0"])


def main():
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data/qlib_data"), region=REG_CN, kernels=1)

    CF = [f"$n_cashflow_act_sq_q{i}" for i in range(4)]
    NI = [f"$n_income_sq_q{i}" for i in range(4)]
    REV = [f"$revenue_sq_q{i}" for i in range(4)]
    COST = [f"$oper_cost_sq_q{i}" for i in range(4)]
    RD = [f"$rd_exp_sq_q{i}" for i in range(4)]
    TA = [f"$total_assets_q{i}" for i in range(4)]

    factors = [
        # ── re-confirm the rung-4 validated ones on #59's holdings ──
        ("OPCFNPDiff%NP", "OPCFNPDiff%NP", CF + NI,
         lambda v: (ttm(v, "n_cashflow_act") - ttm(v, "n_income")) / ttm(v, "n_income")
         if ttm(v, "n_income") else np.nan),
        ("GrossProfit%AssetsQ", "GrossProfit%AssetsQ",
         ["$revenue_sq_q0", "$oper_cost_sq_q0", "$total_assets_q0"],
         lambda v: (v["revenue_sq_q0"] - v["oper_cost_sq_q0"]) / v["total_assets_q0"]
         if v["total_assets_q0"] else np.nan),
        # ── new #59 factors ──
        ("RoeCoreQ", "RoeCoreQ",
         REV + COST + ["$admin_exp_sq_q0", "$sell_exp_sq_q0", "$fin_exp_sq_q0",
                       "$biz_tax_surchg_sq_q0", "$total_hldr_eqy_exc_min_int_q0"],
         lambda v: (coreprofit_q0(v) / v["total_hldr_eqy_exc_min_int_q0"])
         if v["total_hldr_eqy_exc_min_int_q0"] else np.nan),
        ("RnDTTM%营业收入TTM", "RnDTTM%营业收入TTM", RD + REV,
         lambda v: ttm(v, "rd_exp") / ttm(v, "revenue") if ttm(v, "revenue") else np.nan),
        ("RND%Assets", "RND%Assets", RD + TA,
         lambda v: ttm(v, "rd_exp") / avgq(v, "total_assets") if avgq(v, "total_assets") else np.nan),
        ("销售毛利率Q-销售毛利率", "公式(销售毛利率Q-销售毛利率)", REV + COST,
         lambda v: ((v["revenue_sq_q0"] - v["oper_cost_sq_q0"]) / v["revenue_sq_q0"]
                    - (ttm(v, "revenue") - ttm(v, "oper_cost")) / ttm(v, "revenue"))
         if (v["revenue_sq_q0"] and ttm(v, "revenue")) else np.nan),
        # ── HAVG semantics test: is HAVG(OPCFNPDiff%NP,1) == OPCFNPDiff%NP? ──
        ("HAVG(OPCFNPDiff,1)=identity?", "公式(HAVG(OPCFNPDIFF%NP,1))", CF + NI,
         lambda v: (ttm(v, "n_cashflow_act") - ttm(v, "n_income")) / ttm(v, "n_income")
         if ttm(v, "n_income") else np.nan),
        # ── 应收账款周转率 variants ──
        ("应收账款周转率 [TTMrev/AR_q0]", "应收账款周转率", REV + ["$accounts_receiv_q0"],
         lambda v: ttm(v, "revenue") / v["accounts_receiv_q0"] if v["accounts_receiv_q0"] else np.nan),
        ("应收账款周转率 [TTMrev/avg(AR_q0,AR_q4)]", "应收账款周转率",
         REV + ["$accounts_receiv_q0", "$accounts_receiv_q4"],
         lambda v: ttm(v, "revenue") / ((v["accounts_receiv_q0"] + v["accounts_receiv_q4"]) / 2)
         if (v["accounts_receiv_q0"] and v["accounts_receiv_q4"]) else np.nan),
        # ── 扣非市盈率 (filter) variants ──
        ("扣非PE [mv/(dtp_ratio*NPttm)]", "扣非市盈率",
         ["$total_mv", "$dtprofit_to_profit"] + NI,
         lambda v: v["total_mv"] / (v["dtprofit_to_profit"] * ttm(v, "n_income"))
         if (v["dtprofit_to_profit"] and ttm(v, "n_income")) else np.nan),
        ("扣非PE [mv/(dtp_ratio_q0*NPttm)]", "扣非市盈率",
         ["$total_mv", "$dtprofit_to_profit_q0"] + NI,
         lambda v: v["total_mv"] / (v["dtprofit_to_profit_q0"] * ttm(v, "n_income"))
         if (v["dtprofit_to_profit_q0"] and ttm(v, "n_income")) else np.nan),
    ]
    results = []
    for name, col, fields, compute in factors:
        try:
            res = run_factor(D, name, col, fields, compute)
        except Exception as e:
            res = {"factor": name, "status": "error", "err": str(e)[:200]}
        results.append(res)
        print(json.dumps(res, ensure_ascii=False))
    OUT.joinpath("guorn59_factor_parity.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nwrote guorn59_factor_parity.json")


if __name__ == "__main__":
    main()
