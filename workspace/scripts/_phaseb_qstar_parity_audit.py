"""Phase-B value-parity audit (GPT REVISE-PLAN M1/M2): empirically validate each corrected q_*
mapping against the vendor q_* bin (materialized-but-inert), per the OFFICIAL Tushare fina_indicator
definitions (doc 79). A mapping is a "replacement" ONLY if it passes parity; else it's a local
factor, not vendor-equivalent. Compare on the daily-overlap (both carried from the same report).
NON-FORMAL diagnostic.
"""
from __future__ import annotations
import sys, warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path("E:/量化系统")
sys.stdout.reconfigure(encoding="utf-8")

# corrected candidate mappings: vendor q_* (official def) -> local expr over existing _sq
# expr is a python lambda over a dict of field arrays (per stock, aligned daily).
MAPS = [
    ("q_sales_yoy", "营业收入同比单季", ["revenue_sq_q0", "revenue_sq_q4"],
     lambda v: (v["revenue_sq_q0"] - v["revenue_sq_q4"]) / np.abs(v["revenue_sq_q4"])),
    ("q_gr_yoy", "营业总收入同比单季", ["total_revenue_sq_q0", "total_revenue_sq_q4"],
     lambda v: (v["total_revenue_sq_q0"] - v["total_revenue_sq_q4"]) / np.abs(v["total_revenue_sq_q4"])),
    ("q_profit_yoy", "净利润同比单季 (n_income TOTAL)", ["n_income_sq_q0", "n_income_sq_q4"],
     lambda v: (v["n_income_sq_q0"] - v["n_income_sq_q4"]) / np.abs(v["n_income_sq_q4"])),
    ("q_netprofit_yoy", "归母净利润同比单季", ["n_income_attr_p_sq_q0", "n_income_attr_p_sq_q4"],
     lambda v: (v["n_income_attr_p_sq_q0"] - v["n_income_attr_p_sq_q4"]) / np.abs(v["n_income_attr_p_sq_q4"])),
    ("q_gsprofit_margin", "销售毛利率单季", ["revenue_sq_q0", "oper_cost_sq_q0"],
     lambda v: (v["revenue_sq_q0"] - v["oper_cost_sq_q0"]) / v["revenue_sq_q0"]),
    ("q_netprofit_margin", "销售净利率单季 (n_income/revenue)", ["n_income_sq_q0", "revenue_sq_q0"],
     lambda v: v["n_income_sq_q0"] / v["revenue_sq_q0"]),
    ("q_op_to_gr", "营业利润/营业总收入单季", ["operate_profit_sq_q0", "total_revenue_sq_q0"],
     lambda v: v["operate_profit_sq_q0"] / v["total_revenue_sq_q0"]),
    ("q_profit_to_gr", "净利润/营业总收入单季", ["n_income_sq_q0", "total_revenue_sq_q0"],
     lambda v: v["n_income_sq_q0"] / v["total_revenue_sq_q0"]),
    ("q_adminexp_to_gr", "管理费用/营业总收入单季", ["admin_exp_sq_q0", "total_revenue_sq_q0"],
     lambda v: v["admin_exp_sq_q0"] / v["total_revenue_sq_q0"]),
    ("q_finaexp_to_gr", "财务费用/营业总收入单季", ["fin_exp_sq_q0", "total_revenue_sq_q0"],
     lambda v: v["fin_exp_sq_q0"] / v["total_revenue_sq_q0"]),
    ("q_opincome", "经营活动净收益单季 (total_rev−total_cogs)", ["total_revenue_sq_q0", "total_cogs_sq_q0"],
     lambda v: v["total_revenue_sq_q0"] - v["total_cogs_sq_q0"]),
    ("q_opincome_to_ebt", "经营活动净收益/利润总额单季", ["total_revenue_sq_q0", "total_cogs_sq_q0", "total_profit_sq_q0"],
     lambda v: (v["total_revenue_sq_q0"] - v["total_cogs_sq_q0"]) / v["total_profit_sq_q0"]),
    ("q_ocf_to_or", "经营现金流/经营活动净收益单季", ["n_cashflow_act_sq_q0", "total_revenue_sq_q0", "total_cogs_sq_q0"],
     lambda v: v["n_cashflow_act_sq_q0"] / (v["total_revenue_sq_q0"] - v["total_cogs_sq_q0"])),
    ("q_salescash_to_or", "销售收现/营业收入单季", ["c_fr_sale_sg_sq_q0", "revenue_sq_q0"],
     lambda v: v["c_fr_sale_sg_sq_q0"] / v["revenue_sq_q0"]),
    ("q_eps", "EPS单季 (归母/total_share — approx)", ["n_income_attr_p_sq_q0", "total_share"],
     lambda v: v["n_income_attr_p_sq_q0"] / v["total_share"]),
    ("q_investincome", "价值变动净收益单季 (test invest_income — expect MISMATCH)", ["invest_income_sq_q0"],
     lambda v: v["invest_income_sq_q0"]),
]


def main():
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data/qlib_data"), region=REG_CN, kernels=1)
    import os
    feat = ROOT / "data/qlib_data/features"
    alldirs = [d for d in os.listdir(feat) if len(d) == 9 and d[6] == "_"]
    samp = alldirs[:: max(1, len(alldirs) // 150)][:150]

    print(f"{'q_* (vendor)':22s} {'def':40s} {'n':>7s} {'scale':>7s} {'med_rel':>8s} {'w1%':>6s} {'sign':>6s}  verdict")
    for vendor, desc, fields, fn in MAPS:
        need = sorted(set(fields + [f"q_{vendor[2:]}_q0" if False else f"{vendor}_q0"]))
        cols = [f"${f}" for f in fields] + [f"${vendor}_q0"]
        try:
            df = D.features(samp, cols, start_time="2014-01-01", end_time="2024-12-31", freq="day")
        except Exception as e:
            print(f"{vendor:22s} READ-ERR {e}"); continue
        df.columns = fields + ["vendor"]
        # per-row local expr
        vd = {f: df[f].to_numpy(float) for f in fields}
        with np.errstate(all="ignore"):
            loc = fn(vd)
        ven = df["vendor"].to_numpy(float)
        m = np.isfinite(loc) & np.isfinite(ven) & (ven != 0)
        if m.sum() < 100:
            print(f"{vendor:22s} {desc:40s} too-few n={int(m.sum())}"); continue
        ratio = np.abs(loc[m] / ven[m])
        med = np.median(ratio)
        scale = 10.0 ** round(float(np.log10(med))) if (np.isfinite(med) and med > 0) else 1.0
        locs = loc / scale
        rel = np.abs(locs[m] - ven[m]) / np.clip(np.abs(ven[m]), 1e-6, None)
        medrel = float(np.median(rel)); w1 = float((rel <= 0.01).mean())
        sign = float((np.sign(locs[m]) == np.sign(ven[m])).mean())
        verdict = "MATCH" if (medrel < 0.01 and w1 > 0.8) else ("approx" if w1 > 0.5 else "MISMATCH")
        print(f"{vendor:22s} {desc:40s} {int(m.sum()):7d} {scale:7.0f} {medrel:8.4f} {w1:6.3f} {sign:6.3f}  {verdict}")


if __name__ == "__main__":
    main()
