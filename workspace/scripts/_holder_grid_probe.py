"""Rung-5 holder-grid (股东数) — determine 果仁's 报告期 convention BEFORE building a materializer.

果仁 factor `REF(股东数,4)/股东数-1` (股东数下降率, 1yr) operates on a QUARTERLY 报告期 series (果仁 uses
REFQ elsewhere; for fundamentals REF spaces by 报告期). Tushare stk_holdernumber is 不定期 (only 58.6% of
end_dates are quarter-ends; 41.4% are voluntary/irregular), so the current disclosure-indexed `$holder_num_qN`
counts DISCLOSURES, not 报告期 → q4 reaches anywhere from ~5 weeks to ~4 years back (rung-5: sign 7.9%, ~8x).

This probe reconstructs the ratio at the holding level vs 果仁's displayed value under THREE conventions and
reports which matches — that decides the materializer design:
  RAW   = current behaviour: ALL disclosures, q4=4 disclosures back   (expect the ~8x failure)
  QEND  = prefilter to end_date==quarter-end, q4=4 报告期 back        (the profit_dedt-style fix)
  ASOF  = quarterly grid, value = latest disclosure with end_date<=quarter-end (incl. irregular), ffilled
All at signal lag 0 and 1 (rung-4 meta-finding: 果仁 displays at T-1). NON-FORMAL diagnostic.
"""
from __future__ import annotations
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")

QE = {(3, 31), (6, 30), (9, 30), (12, 31)}


def _guorn_holder_ratio() -> pd.DataFrame:
    """All (q, date, guorn_ratio) from books displaying the REF(股东数,4)/股东数-1 column."""
    rows = []
    for f in sorted(glob.glob(str(ROOT / "Knowledge/果仁回测结果/*.xlsx"))):
        try:
            names = [str(c) for c in pd.read_excel(f, sheet_name="各阶段持仓详单", nrows=0).columns]
        except Exception:
            continue
        if "股票代码" not in names:
            continue
        col = next((c for c in names if ("股东数" in c) and ("REF" in c.upper()) and ("/股东数-1" in c)), None)
        if col is None:
            continue
        g = pd.read_excel(f, sheet_name="各阶段持仓详单")
        c6 = g["股票代码"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
        q = pd.Series(c6 + np.where(c6.str[0].isin(["6", "9"]), "_SH", "_SZ")).str.lower()
        d = pd.to_datetime(g["开始日期"], errors="coerce")
        v = pd.to_numeric(g[col], errors="coerce")
        sub = pd.DataFrame({"q": q, "date": d, "gf": v}).dropna()
        rows.append(sub)
    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["q", "date", "gf"])
    return out.drop_duplicates()


def _ledger() -> dict[str, pd.DataFrame]:
    df = pd.read_parquet(glob.glob(str(ROOT / "data/pit_ledger/holder_number/holder_number.parquet"))[0])
    df["_ed"] = pd.to_datetime(df["end_date"].astype(str), errors="coerce")  # noqa: unsafe-pit-dates[PIT001] reason: parity diagnostic parsing raw end_date for cadence analysis; no factor/serving, no lookahead
    df["_eff"] = pd.to_datetime(df["effective_date"].astype(str), errors="coerce")  # noqa: unsafe-pit-dates[PIT001] reason: parity diagnostic; effective_date IS the PIT visibility anchor, parsed for as-of comparison
    df = df.dropna(subset=["_ed", "_eff", "holder_num"]).copy()
    df["_isqe"] = [(d.month, d.day) in QE for d in df["_ed"]]
    df["_qcode"] = df["qlib_code"].astype(str).str.lower()
    return {code: g.sort_values("_eff") for code, g in df.groupby("_qcode")}


def _ratio_raw_or_qend(g: pd.DataFrame, d: pd.Timestamp, lag: int, qend_only: bool):
    """q4/q0-1 over disclosures (optionally quarter-end-only), slots = visible disclosures as-of the signal."""
    sub = g[g["_isqe"]] if qend_only else g
    vis = sub[sub["_eff"] <= d]
    if lag:
        # drop the most-recent `lag` disclosures (signal shown at T-1 = exclude same-day-visible newest)
        vis = vis.iloc[:-lag] if len(vis) > lag else vis.iloc[:0]
    # dedup to one row per 报告期 (latest eff) so duplicates/revisions of the same end_date don't shift slots
    vis = vis.drop_duplicates(subset="_ed", keep="last")
    if len(vis) < 5:
        return np.nan
    q0 = vis["holder_num"].iloc[-1]
    q4 = vis["holder_num"].iloc[-5]
    return q4 / q0 - 1.0 if q0 else np.nan


def _ratio_asof(g: pd.DataFrame, d: pd.Timestamp, lag: int):
    """Quarterly 报告期 grid; grid value(T)=latest disclosure (any end_date) with _ed<=T; REF(,4) on the grid."""
    vis = g[g["_eff"] <= d]
    if lag:
        vis = vis.iloc[:-lag] if len(vis) > lag else vis.iloc[:0]
    if vis.empty:
        return np.nan
    # latest visible 报告期 quarter-end = the quarter-end of the most-recent disclosure's _ed (floor to QE)
    last_ed = vis["_ed"].max()
    # build the quarter-end grid up to last_ed
    grid = pd.date_range(end=last_ed, periods=8, freq="QE")
    s = vis.sort_values("_ed").drop_duplicates(subset="_ed", keep="last").set_index("_ed")["holder_num"]
    vals = s.reindex(s.index.union(grid)).sort_index().ffill().reindex(grid)
    if vals.isna().any() or len(vals) < 5:
        return np.nan
    q0 = vals.iloc[-1]
    q4 = vals.iloc[-5]
    return q4 / q0 - 1.0 if q0 else np.nan


def _score(g: pd.DataFrame, fn) -> dict:
    recs = []
    for r in g.itertuples():
        loc = fn(r)
        if np.isfinite(loc):
            recs.append((r.gf, loc))
    cmp = pd.DataFrame(recs, columns=["gf", "loc"]).dropna()
    if len(cmp) < 50:
        return {"n": len(cmp), "note": "too few"}
    rel = (cmp["loc"] - cmp["gf"]).abs() / cmp["gf"].abs().clip(lower=0.02)
    return {"n": int(len(cmp)),
            "median_relerr": round(float(rel.median()), 4),
            "within_5pct": round(float((rel <= 0.05).mean()), 4),
            "within_10pct": round(float((rel <= 0.10).mean()), 4),
            "sign_match": round(float((np.sign(cmp["loc"]) == np.sign(cmp["gf"])).mean()), 4)}


def main():
    g = _guorn_holder_ratio()
    print(f"果仁 holdings with REF(股东数,4)/股东数-1: {len(g)} rows, {g['q'].nunique()} stocks")
    led = _ledger()
    g = g[g["q"].isin(led)].reset_index(drop=True)
    print(f"  with ledger coverage: {len(g)} rows  (果仁 gf==0: {(g['gf']==0).mean():.3f})\n")

    # 果仁 is 92.6% zero (REF returns current when <4 报告期 history). The meaningful test is the
    # NON-ZERO subset: where 果仁 computed a real change, does the reconstruction match?
    g_nz = g[g["gf"] != 0].reset_index(drop=True)
    print(f"=== NON-ZERO 果仁 subset: {len(g_nz)} rows ===")
    for lag in (0, 1):
        for label, fn in [
            ("RAW", lambda r, lag=lag: _ratio_raw_or_qend(led[r.q], r.date, lag, qend_only=False)),
            ("QEND", lambda r, lag=lag: _ratio_raw_or_qend(led[r.q], r.date, lag, qend_only=True)),
            ("ASOF", lambda r, lag=lag: _ratio_asof(led[r.q], r.date, lag)),
        ]:
            print(f"  lag={lag} {label:6s}", _score(g_nz, fn))
    # REF-depth sweep on the non-zero subset: which disclosure-spacing matches 果仁's magnitude?
    def ratio_depth(g, d, lag, depth):
        vis = g[g["_eff"] <= d]
        if lag:
            vis = vis.iloc[:-lag] if len(vis) > lag else vis.iloc[:0]
        vis = vis.drop_duplicates(subset="_ed", keep="last")
        if len(vis) < depth + 1:
            return np.nan
        q0 = vis["holder_num"].iloc[-1]
        qd = vis["holder_num"].iloc[-1 - depth]
        return qd / q0 - 1.0 if q0 else np.nan
    print("\n=== REF-depth sweep (RAW disclosures, lag=0), non-zero subset ===")
    for depth in (1, 2, 3, 4, 6, 8):
        print(f"  depth={depth}", _score(g_nz, lambda r, depth=depth: ratio_depth(led[r.q], r.date, 0, depth)))

    # disclosure-recency split: WHY 果仁 is ~92% zero — it's a DISCLOSURE-EVENT convention (non-zero only
    # just after a new 股东数 disclosure). zero rows sit far from a disclosure; non-zero rows right after one.
    print("\n=== disclosure-recency split (median days since last visible disclosure) ===")

    def _days_since(q, d):
        e = led.get(q)
        if e is None:
            return np.nan
        eff = e["_eff"].values
        pos = int(np.searchsorted(eff, np.datetime64(d), side="right"))
        return (np.datetime64(d) - eff[pos - 1]) / np.timedelta64(1, "D") if pos > 0 else np.nan

    g2 = g.assign(_gap=[_days_since(r.q, r.date) for r in g.itertuples()])
    for lab, sub in [("果仁 gf==0", g2[g2["gf"] == 0]), ("果仁 gf!=0", g2[g2["gf"] != 0])]:
        print(f"  {lab}: n={len(sub)} median_days_since_disclosure={sub['_gap'].median():.0f}")

    print("\n=== FULL set (incl. 果仁 zeros) ===")
    for lag in (0, 1):
        for label, fn in [
            ("RAW (all disclosures)", lambda r, lag=lag: _ratio_raw_or_qend(led[r.q], r.date, lag, qend_only=False)),
            ("QEND (quarter-end only)", lambda r, lag=lag: _ratio_raw_or_qend(led[r.q], r.date, lag, qend_only=True)),
            ("ASOF (quarterly grid ffill)", lambda r, lag=lag: _ratio_asof(led[r.q], r.date, lag)),
        ]:
            print(f"lag={lag}  {label:30s}", _score(g, fn))
        print()


if __name__ == "__main__":
    main()
