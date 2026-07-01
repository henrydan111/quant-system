"""Self-review gap-closer: confirm the EXISTING PROVIDER fields $holder_num_q0/$holder_num_q1 (read via
Qlib D.features, the factor-library path) reproduce 果仁's 股东数下降率 on the non-zero subset — NOT just
the raw ledger (the rung-3 provider-read-vs-raw lesson). If provider q1/q0-1 matches ~0.24% like the
ledger probe, the "no materializer, existing fields suffice" claim is airtight. NON-FORMAL diagnostic.
"""
from __future__ import annotations
import glob
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")


def col_match(c: str) -> bool:
    return ("股东数" in c) and ("REF" in c.upper()) and ("/股东数-1" in c)


def guorn_rows() -> pd.DataFrame:
    rows = []
    for f in sorted(glob.glob(str(ROOT / "Knowledge/果仁回测结果/*.xlsx"))):
        try:
            names = [str(c) for c in pd.read_excel(f, sheet_name="各阶段持仓详单", nrows=0).columns]
        except Exception:
            continue
        if "股票代码" not in names:
            continue
        col = next((c for c in names if col_match(c)), None)
        if col is None:
            continue
        g = pd.read_excel(f, sheet_name="各阶段持仓详单")
        c6 = g["股票代码"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
        q = pd.Series(c6 + np.where(c6.str[0].isin(["6", "9"]), "_SH", "_SZ")).str.lower()
        rows.append(pd.DataFrame({"q": q, "date": pd.to_datetime(g["开始日期"], errors="coerce"),
                                  "gf": pd.to_numeric(g[col], errors="coerce")}).dropna())
    return pd.concat(rows, ignore_index=True).drop_duplicates()


def main():
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data/qlib_data"), region=REG_CN, kernels=1)

    g = guorn_rows()
    insts = sorted(g["q"].unique())
    df = D.features(insts, ["$holder_num_q0", "$holder_num_q1"],
                    start_time="2012-06-01", end_time="2026-06-20", freq="day")
    df.columns = ["q0", "q1"]
    w0 = df["q0"].unstack(level=0).sort_index()
    w1 = df["q1"].unstack(level=0).sort_index()

    def recon(q, d, lag):
        if q not in w0.columns:
            return np.nan
        s0, s1 = w0[q], w1[q]
        pos = s0.index.searchsorted(d, side="right") - 1 - lag
        if pos < 0:
            return np.nan
        a, b = s0.iat[pos], s1.iat[pos]
        return b / a - 1.0 if (np.isfinite(a) and np.isfinite(b) and a) else np.nan

    g_nz = g[g["gf"] != 0].reset_index(drop=True)
    print(f"PROVIDER-READ check: 果仁 non-zero subset n={len(g_nz)} (provider $holder_num_q1/$holder_num_q0 - 1)")
    for lag in (0, 1):
        recs = [(r.gf, recon(r.q, r.date, lag)) for r in g_nz.itertuples()]
        cmp = pd.DataFrame(recs, columns=["gf", "loc"]).dropna()
        cmp = cmp[np.isfinite(cmp["loc"])]
        rel = (cmp["loc"] - cmp["gf"]).abs() / cmp["gf"].abs().clip(lower=0.02)
        print(f"  lag={lag}: n={len(cmp)} median_relerr={rel.median():.4f} "
              f"within_5pct={(rel<=0.05).mean():.4f} within_10pct={(rel<=0.10).mean():.4f} "
              f"sign_match={(np.sign(cmp['loc'])==np.sign(cmp['gf'])).mean():.4f}")


if __name__ == "__main__":
    main()
