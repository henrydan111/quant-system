"""Phase-C coverage audit: profit_dedt (扣非净利润) single-quarter DERIVABILITY by board.

The vendor `q_dtprofit` reports the single-quarter 扣非 DIRECTLY (served ~99.7%). Our PIT-correct
derivation needs TWO consecutive visible cumulatives (`profit_dedt[Q] - profit_dedt[Q-1]`), so it
carries a structural coverage gap = the PIT-correctness cost. This audit confirms the gap is
non-random (weaker on BJ/STAR/young listings) -> justifies `coverage_tier=sub` for the factor
`qual_dtprofit_to_profit_q`. NON-FORMAL diagnostic.

Also re-states the denominator verdict (empirical, _phasec denominator probe): the vendor
q_dtprofit_to_profit uses 归母净利润 (n_income_attr_p), NOT consolidated n_income, NOT total_profit
(归母 reconstructs the vendor ratio to 0.000 pct-pts / 99.2% within 0.5pts).
"""
from __future__ import annotations
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import pyarrow.dataset as ds
from pathlib import Path

ROOT = Path("E:/量化系统")


def board_of(code: str) -> str:
    c = code.split("_")[0] if "_" in code else code.split(".")[0]
    if c.startswith("688"):
        return "科创板 STAR"
    if c.startswith("300") or c.startswith("301"):
        return "创业板 ChiNext"
    if c.startswith(("8", "4", "920")):
        return "北交所 BSE"
    if c.startswith(("600", "601", "603", "605", "000", "001", "002", "003")):
        return "主板 Main"
    return "其他 Other"


def main():
    t = ds.dataset(str(ROOT / "data/pit_ledger/indicators")).to_table(
        columns=["qlib_code", "end_date", "profit_dedt"]).to_pandas()
    t["end_date"] = pd.to_datetime(t["end_date"].astype(str), errors="coerce")
    t = t.dropna(subset=["end_date"])
    # standard fiscal-quarter ends only (the materializer prefilter)
    m = t["end_date"].dt.month
    d = t["end_date"].dt.day
    std = (((m == 3) & (d == 31)) | ((m == 6) & (d == 30)) | ((m == 9) & (d == 30)) | ((m == 12) & (d == 31)))
    t = t.loc[std].copy()
    t["q"] = t["end_date"].dt.month.map({3: "Q1", 6: "H1", 9: "Q3", 12: "FY"})
    t["fy"] = t["end_date"].dt.year
    t["board"] = t["qlib_code"].map(board_of)

    print("=== single-quarter DERIVABILITY by board (firm-year level; needs this + prior cumulative) ===")
    rows = []
    for board, g in t.groupby("board"):
        piv = g.pivot_table(index=["qlib_code", "fy"], columns="q", values="profit_dedt", aggfunc="last")
        for c in ["Q1", "H1", "Q3", "FY"]:
            if c not in piv:
                piv[c] = np.nan
        n = len(piv)
        if n == 0:
            continue
        q1 = piv["Q1"].notna().mean()
        q2 = (piv["H1"].notna() & piv["Q1"].notna()).mean()
        q3 = (piv["Q3"].notna() & piv["H1"].notna()).mean()
        q4 = (piv["FY"].notna() & piv["Q3"].notna()).mean()
        rows.append((board, n, q1, q2, q3, q4, np.mean([q1, q2, q3, q4])))
    rep = pd.DataFrame(rows, columns=["board", "firm_years", "Q1=cum", "Q2", "Q3", "Q4", "mean"]).sort_values("mean", ascending=False)
    for c in ["Q1=cum", "Q2", "Q3", "Q4", "mean"]:
        rep[c] = (100 * rep[c]).round(1)
    print(rep.to_string(index=False))

    # young-listing proxy: derivability by fiscal year (newer cohorts = thinner history)
    print("\n=== Q4 derivability (FY & Q3 both visible) by fiscal year — young-cohort thinning ===")
    yr = []
    for fy, g in t[t["fy"] >= 2016].groupby("fy"):
        piv = g.pivot_table(index="qlib_code", columns="q", values="profit_dedt", aggfunc="last")
        for c in ["Q3", "FY"]:
            if c not in piv:
                piv[c] = np.nan
        yr.append((int(fy), len(piv), round(100 * (piv["FY"].notna() & piv["Q3"].notna()).mean(), 1)))
    print(pd.DataFrame(yr, columns=["fy", "n_stocks", "Q4_derivable%"]).to_string(index=False))


if __name__ == "__main__":
    main()
