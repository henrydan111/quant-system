"""#59 Phase-B refinement: resolve RoeCoreQ equity-base + the exact 应收账款周转率 formula.

From the 果仁 docs (indicator_reference_auto.md):
  应收账款周转率 = TTM(营收) / (AvgQ(应收账款,4) + AvgQ(应收票据,4) - AvgQ(预收账款,4))
  ROE family uses AvgQ(权益,4,1) (averaged, offset-1 equity), not quarter-end.
Reuses the run_factor machinery from _guorn59_factor_parity.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")
from _guorn59_factor_parity import run_factor, ttm, coreprofit_q0  # noqa


def avg_slots(v, base, idxs):
    xs = [v[f"{base}_q{i}"] for i in idxs]
    return np.nan if any(pd.isna(x) for x in xs) else sum(xs) / len(idxs)


def main():
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data/qlib_data"), region=REG_CN, kernels=1)

    REV = [f"$revenue_sq_q{i}" for i in range(4)]
    COST = [f"$oper_cost_sq_q{i}" for i in range(4)]
    EQ = [f"$total_hldr_eqy_exc_min_int_q{i}" for i in range(5)]
    CORE = REV + COST + ["$admin_exp_sq_q0", "$sell_exp_sq_q0", "$fin_exp_sq_q0", "$biz_tax_surchg_sq_q0"]
    AR = [f"$accounts_receiv_q{i}" for i in range(4)]
    NR = [f"$notes_receiv_q{i}" for i in range(4)]
    ADV = [f"$adv_receipts_q{i}" for i in range(4)]

    def roe(eq_idxs):
        return lambda v: (coreprofit_q0(v) / avg_slots(v, "total_hldr_eqy_exc_min_int", eq_idxs)) \
            if avg_slots(v, "total_hldr_eqy_exc_min_int", eq_idxs) else np.nan

    factors = [
        ("RoeCoreQ /eq_q0(end,base)", "RoeCoreQ", CORE + EQ, roe([0])),
        ("RoeCoreQ /eq_q1(begin)", "RoeCoreQ", CORE + EQ, roe([1])),
        ("RoeCoreQ /avg(q0,q1)", "RoeCoreQ", CORE + EQ, roe([0, 1])),
        ("RoeCoreQ /AvgQ(4,0)=q0..3", "RoeCoreQ", CORE + EQ, roe([0, 1, 2, 3])),
        ("RoeCoreQ /AvgQ(4,1)=q1..4", "RoeCoreQ", CORE + EQ, roe([1, 2, 3, 4])),
        ("应收账款周转率 EXACT[TTMrev/(avg4AR+avg4NR-avg4ADV)]", "应收账款周转率",
         REV + AR + NR + ADV,
         lambda v: ttm(v, "revenue") / (avg_slots(v, "accounts_receiv", range(4))
                                        + avg_slots(v, "notes_receiv", range(4))
                                        - avg_slots(v, "adv_receipts", range(4)))
         if (ttm(v, "revenue") is not None and
             avg_slots(v, "accounts_receiv", range(4)) is not None and
             (avg_slots(v, "accounts_receiv", range(4)) + avg_slots(v, "notes_receiv", range(4))
              - avg_slots(v, "adv_receipts", range(4)))) else np.nan),
        ("应收账款周转率 [TTMrev/avg4(AR only)]", "应收账款周转率", REV + AR,
         lambda v: ttm(v, "revenue") / avg_slots(v, "accounts_receiv", range(4))
         if avg_slots(v, "accounts_receiv", range(4)) else np.nan),
    ]
    results = []
    for name, col, fields, compute in factors:
        try:
            res = run_factor(D, name, col, fields, compute)
        except Exception as e:
            res = {"factor": name, "status": "error", "err": str(e)[:200]}
        results.append(res)
        print(json.dumps(res, ensure_ascii=False))
    (ROOT / "workspace/outputs/guorn_parity/guorn59_refine.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
