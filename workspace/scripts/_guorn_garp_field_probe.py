"""One-shot provider field-availability probe for the GARP/R&D books (#4/#15/#5).

The field_status.yaml registry lists only FORMALLY-promoted fields, but these NON-FORMAL parity
harnesses read the provider directly via D.features — which may carry more single-quarter depth than is
registered (e.g. #1's CoreProfitQGr already uses admin/sell/fin/biz_tax at q4, none registered past q0).
This probe measures the ACTUAL non-null coverage of every candidate field at every depth I need, so the
keep/omit decisions for the 3 books rest on data, not the registry list (CLAUDE.md rule #10).

Run: venv/Scripts/python.exe workspace/scripts/_guorn_garp_field_probe.py
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

PROVIDER_URI = str(ROOT / "data" / "qlib_data")
# representative: main / 中小板 / 创业板 / 科创板 / 北证-excluded liquid names
STOCKS = ["000001_SZ", "600519_SH", "002415_SZ", "300750_SZ", "688981_SH", "300059_SZ"]
START, END = "2022-06-01", "2024-12-31"

# candidate fields grouped by the factor that needs them
CANDIDATES = {
    "revenue depth":   [f"$revenue_sq_q{q}" for q in range(8)],
    "oper_cost depth": [f"$oper_cost_sq_q{q}" for q in range(8)],
    "admin_exp depth": [f"$admin_exp_sq_q{q}" for q in (0, 1, 2, 3, 4)],
    "sell_exp depth":  [f"$sell_exp_sq_q{q}" for q in (0, 1, 2, 3, 4)],
    "fin_exp depth":   [f"$fin_exp_sq_q{q}" for q in (0, 1, 2, 3, 4)],
    "biz_tax depth":   [f"$biz_tax_surchg_sq_q{q}" for q in (0, 1, 2, 3, 4)],
    "income_tax":      [f"$income_tax_sq_q{q}" for q in (0, 1, 2, 3, 4)] + [f"$income_tax_exp_sq_q{q}" for q in (0, 4)],
    "n_income_attr_p": [f"$n_income_attr_p_sq_q{q}" for q in range(5)],
    "profit_dedt":     [f"$profit_dedt_sq_q{q}" for q in range(5)],
    "rd_exp depth":    [f"$rd_exp_sq_q{q}" for q in range(8)],
    "total_assets":    [f"$total_assets_q{q}" for q in (0, 1, 2, 3, 4)],
    "equity exc_min":  [f"$total_hldr_eqy_exc_min_int_q{q}" for q in (0, 1, 2, 3, 4)],
    "ebitda / ebit":   ["$ebitda_sq_q0", "$ebitda_q0", "$ebit_sq_q0", "$ebit_sq_q1", "$ebit_sq_q2", "$ebit_sq_q3"],
    "EV":              ["$ev", "$ev_ttm", "$enterprise_value"],
    "D&A single-q":    ["$depr_fa_coga_dpba_sq_q0", "$amort_intang_assets_sq_q0", "$recp_disp_fiolta_sq_q0",
                        "$depr_fa_coga_dpba_cum_q0", "$amort_intang_assets_cum_q0"],
    "cashflow act":    [f"$n_cashflow_act_sq_q{q}" for q in range(4)],
    "capex single-q":  [f"$c_pay_acq_const_fiolta_sq_q{q}" for q in range(4)],
    "valuation/mv":    ["$total_mv", "$circ_mv", "$dv_ttm", "$pe_ttm", "$amount", "$adj_factor",
                        "$limit_status", "$forecast__np_q_yoy", "$total_liab_q0"],
}


def main():
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=PROVIDER_URI, region=REG_CN, kernels=1)
    print(f"probe {len(STOCKS)} stocks {START}..{END}\n", flush=True)
    for group, fields in CANDIDATES.items():
        print(f"--- {group} ---", flush=True)
        for f in fields:
            try:
                df = D.features(STOCKS, [f], start_time=START, end_time=END, freq="day")
                col = df.iloc[:, 0]
                cov = col.notna().mean()
                # per-stock presence (any non-null)
                per = col.groupby(level=0).apply(lambda s: s.notna().any())
                nstk = int(per.sum())
                print(f"  {f:42} cov={cov:5.1%}  stocks_with_data={nstk}/{len(STOCKS)}", flush=True)
            except Exception as e:
                msg = str(e).splitlines()[0][:70]
                print(f"  {f:42} MISSING ({msg})", flush=True)
        print(flush=True)


if __name__ == "__main__":
    main()
