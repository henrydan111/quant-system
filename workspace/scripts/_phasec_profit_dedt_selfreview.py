"""Phase-C self-review probe: is profit_dedt (扣非净利润, indicators ledger) reported QUARTERLY (so the
single-quarter derivation is viable) or only semi-annually (the D&A trap → single-q NaN)?

Verdict (2026-06-24): profit_dedt is QUARTERLY — Q1 94.0% / H1 96.1% / Q3 94.5% / FY 98.2% non-null.
So profit_dedt[Q] − profit_dedt[Q-1] is genuinely derivable (unlike the cashflow 折旧摊销 case). The
vendor q_dtprofit (served 99.7%, reports the single-q DIRECTLY) is the coverage ceiling; our PIT-correct
derivation (needs two consecutive cumulatives) has a modest coverage gap = the PIT-correctness cost.
NON-FORMAL diagnostic.
"""
from __future__ import annotations
import os, warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import pyarrow.dataset as ds
from pathlib import Path

ROOT = Path("E:/量化系统")


def main():
    t = ds.dataset(str(ROOT / "data/pit_ledger/indicators")).to_table(
        columns=["qlib_code", "end_date", "profit_dedt"]).to_pandas()
    t["end_date"] = pd.to_datetime(t["end_date"].astype(str), errors="coerce")  # noqa: unsafe-pit-dates[PIT001] reason: diagnostic quarterly-coverage self-review — end_date parsed only to bucket by fiscal quarter; no factor/serving, no lookahead
    t = t.dropna(subset=["end_date"])
    t["q"] = t["end_date"].dt.month.map({3: "Q1", 6: "H1", 9: "Q3", 12: "FY"})
    print("=== profit_dedt non-null coverage by fiscal quarter (quarterly vs semi-annual?) ===")
    g = t.groupby("q")["profit_dedt"].agg(n="size", nonnull=lambda s: s.notna().sum())
    g["cov%"] = (100 * g["nonnull"] / g["n"]).round(1)
    print(g.reindex(["Q1", "H1", "Q3", "FY"]).to_string())

    t["fy"] = t["end_date"].dt.year
    piv = t.pivot_table(index=["qlib_code", "fy"], columns="q", values="profit_dedt", aggfunc="last")
    for c in ["Q1", "H1", "Q3", "FY"]:
        if c not in piv:
            piv[c] = np.nan
    print("\n=== single-q DERIVABLE fraction (firm-years; needs this + prior cumulative) ===")
    print(f"  Q1 {piv['Q1'].notna().mean():.3f}  Q2 {(piv['H1'].notna() & piv['Q1'].notna()).mean():.3f}"
          f"  Q3 {(piv['Q3'].notna() & piv['H1'].notna()).mean():.3f}"
          f"  Q4 {(piv['FY'].notna() & piv['Q3'].notna()).mean():.3f}")
    print("  (firm-year denominator includes non-reporting years — report-level derivability ~90-95%)")

    # vendor q_dtprofit served coverage (the direct single-q = the coverage ceiling)
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data/qlib_data"), region=REG_CN, kernels=1)
    feat = ROOT / "data/qlib_data/features"
    samp = [d for d in os.listdir(feat) if len(d) == 9 and d[6] == "_"][::40][:120]
    df = D.features(samp, ["$q_dtprofit_q0", "$n_income_attr_p_sq_q0", "$total_profit_sq_q0"],
                    start_time="2015-01-01", end_time="2024-12-31", freq="day")
    print(f"\nvendor q_dtprofit_q0 served non-nan: {df['$q_dtprofit_q0'].notna().mean():.4f} "
          f"(the direct single-q ceiling); n_income_attr_p_sq_q0 {df['$n_income_attr_p_sq_q0'].notna().mean():.4f}")


if __name__ == "__main__":
    main()
