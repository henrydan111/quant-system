"""果仁 dividend-yield CALIBER — the announcement-date (declared) TTM dividend, NOT Tushare's ex-date dv_ttm.

WHY THIS EXISTS
---------------
果仁's `股息率TTM` (and every dividend-derived factor: DivGrPY%, Div%NetIncY2, 近三年分红之和, …) is built on
the DECLARED dividend stream, dated by ANNOUNCEMENT. Tushare's `daily_basic.$dv_ttm` is built on the REALIZED
(ex-date) dividend stream. The two diverge exactly at the high-yield tail — the SELECTION zone — so using
`$dv_ttm` to reproduce a 果仁 dividend book is a silent caliber error (we mis-diagnosed it as "irreducible
vendor data" on 2026-06-27 before pinning the caliber on 2026-06-28).

THE CALIBER (validated 2025-12-31 cross-section, n=2186, median |rel-err| 0.52% on 果仁's own price,
top-5/10 selection overlap 100%, Spearman 0.992; on local close median 1.3%, top-5 100%, top-20 90%):

  股息率TTM = Σ  cash_div_tax   ÷   close
             over dividend events whose EARLIEST announcement (预案 ann_date) ∈ (signal − 365d, signal]

  • cash_div_tax  = 每股股利 **PRE-tax** (税前). NOT cash_div (税后). Confirmed by the 0.5% full-universe match.
  • one value per (ts_code, end_date) fiscal event, using the MOST-FINALIZED amount KNOWN by `signal`
    (proc priority 实施 > 股东大会通过 > 预案) — this avoids the spurious 预案 "annual total" rows
    (e.g. 002271 FY2024 carries a 1.850 预案 row alongside the real 0.925 per-event rows; max() double-counts).
  • window anchor = the EARLIEST ann_date of the event (the 预案/board-proposal date — when it became public),
    restricted to ann_date ≤ signal (PIT: never count a dividend announced after the signal date).
  • denominator = RAW close on the signal date (果仁 收盘价 ≈ Tushare raw $close; NOT adjusted).

CONTRAST WITH $dv_ttm (why it diverges at the tail):
  • 果仁 INCLUDES dividends ANNOUNCED-but-not-yet-ex   (600329: 2.450 announced 2025-10-31, ex 2026-02-12 →
    counted at 2025-12-31; $dv_ttm misses it → 2.77% vs 果仁 8.18%).
  • 果仁 EXCLUDES dividends that went ex in the trailing 12m but were ANNOUNCED >12m ago
    (603167: 0.220 announced 2024-12-13, ex 2025-01-21 → $dv_ttm counts it → 10.97% vs 果仁 8.48%).

This is NOT a PIT-loader path — it reads the corporate-actions ledger directly for parity diagnostics only.
NON-FORMAL 果仁-parity tooling. For any FORMAL factor, materialize through the ledger/provider (see CLAUDE.md §6).
"""
from __future__ import annotations
import glob
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DIV_GLOB = str(ROOT / "data" / "corporate" / "dividends" / "dividends_*.parquet")
_PROC_PRIORITY = {"实施": 3, "股东大会通过": 2, "预案": 1}


def _decode_gbk(s) -> str:
    """div_proc is GBK bytes mis-read as latin-1 on this Windows checkout; recover the Chinese."""
    try:
        return str(s).encode("latin-1").decode("gbk")
    except Exception:
        return str(s)


def declared_dividend_ttm(signal_date: str, *, pretax: bool = True, window_days: int = 365) -> pd.Series:
    """果仁-caliber trailing dividend PER SHARE: Σ declared cash dividend over the trailing `window_days`,
    anchored by ANNOUNCEMENT (预案) date, PIT-clamped to ann_date ≤ signal. Returns a Series indexed by
    6-digit code (e.g. '600329'). Divide by the raw close to get 股息率TTM (as a fraction; ×100 for %)."""
    sig = pd.Timestamp(signal_date)
    start = sig - pd.Timedelta(days=window_days)
    amount_col = "cash_div_tax" if pretax else "cash_div"

    frames = [pd.read_parquet(f) for f in glob.glob(DIV_GLOB)]
    d = pd.concat(frames, ignore_index=True)
    d["proc"] = d["div_proc"].map(_decode_gbk)
    d["ann"] = pd.to_datetime(d["ann_date"], format="%Y%m%d", errors="coerce")
    d = d[(d[amount_col].fillna(0) > 0) & (d["ann"].notna()) & (d["ann"] <= sig)].copy()  # PIT
    d["prio"] = d["proc"].map(_PROC_PRIORITY).fillna(0)

    # one row per (ts_code, end_date): most-finalized amount known by signal; window = earliest announcement
    ev = (d.sort_values("prio")
            .groupby(["ts_code", "end_date"])
            .agg(dps=(amount_col, "last"), win=("ann", "min"))
            .reset_index())
    ev = ev[(ev["win"] > start) & (ev["win"] <= sig)]
    out = ev.groupby("ts_code")["dps"].sum()
    out.index = [c.split(".")[0] for c in out.index]
    return out.rename("declared_div_ttm")


def dividend_yield_ttm(signal_date: str, close_by_code6: pd.Series, *, pretax: bool = True) -> pd.Series:
    """果仁-caliber 股息率TTM as a FRACTION (×100 for %), given a Series of raw close indexed by 6-digit code."""
    dps = declared_dividend_ttm(signal_date, pretax=pretax)
    return (dps.reindex(close_by_code6.index) / close_by_code6).rename("dv_ttm_guorn")


def _declared_events(signal_date: str, *, pretax: bool = True, drop_stale_plans: bool = True,
                     stale_days: int = 240) -> pd.DataFrame:
    """Shared event kernel for the REPORT-PERIOD (分红总金额) calibers: one row per (code6, end_date) at the
    most-finalized amount KNOWN by `signal` (实施 > 股东大会通过 > 预案), PIT ann_date ≤ signal.

    ⚠ STALE-预案 rule (2026-07-01, pinned via 正丹股份 300641): Tushare keeps SUPERSEDED plan rows — 正丹's FY2024
    interim was 预案'd at end_date 20240630 (0.4, ann 2024-08) then re-dated and IMPLEMENTED at end_date 20240930
    (0.4). Summing both double-counts (my 1.10 vs 果仁 0.70 → DivAGrPY% 54 vs 34). 果仁 does NOT count such
    phantoms, but DOES count recently-declared not-yet-implemented dividends (same as 股息率TTM's 600329 case).
    So: drop an event whose best state is still not 实施 AND whose latest announcement is older than `stale_days`
    (~8 months) before signal — old enough that a genuine plan would have implemented. Validated: fixes DivAGrPY%
    top-5 to 100% while leaving DivOP%'s declared-pending recent quarters intact (top-5 stays 100%)."""
    sig = pd.Timestamp(signal_date)
    amount_col = "cash_div_tax" if pretax else "cash_div"
    frames = [pd.read_parquet(f) for f in glob.glob(DIV_GLOB)]
    d = pd.concat(frames, ignore_index=True)
    d["proc"] = d["div_proc"].map(_decode_gbk)
    d["ann"] = pd.to_datetime(d["ann_date"], format="%Y%m%d", errors="coerce")
    d = d[(d[amount_col].fillna(0) > 0) & (d["ann"].notna()) & (d["ann"] <= sig)].copy()  # PIT
    d["prio"] = d["proc"].map(_PROC_PRIORITY).fillna(0)
    d["c6"] = d["ts_code"].str.split(".").str[0]
    ev = (d.sort_values(["prio", "ann"])
            .groupby(["c6", "end_date"])
            .agg(dps=(amount_col, "last"), best=("proc", "last"), last_ann=("ann", "max"))
            .reset_index())
    if drop_stale_plans:
        stale = (ev["best"] != "实施") & (ev["last_ann"] < sig - pd.Timedelta(days=stale_days))
        ev = ev[~stale]
    ev["ed"] = ev["end_date"].astype(str)  # noqa: unsafe-pit-dates[PIT001] reason: end_date is a fiscal-period LABEL here; visibility already PIT-gated by the ann<=sig filter above
    ev["fy"] = ev["ed"].str[:4].astype(int)
    return ev


def declared_dividend_by_quarter(signal_date: str, *, pretax: bool = True,
                                 drop_stale_plans: bool = True) -> pd.DataFrame:
    """Per-fiscal-QUARTER declared dividend PER SHARE (for 果仁's `sumq(分红总金额, N, M)`). Returns a DataFrame
    indexed by 6-digit code, columns = fiscal-period end_date string (e.g. '20241231').

    ⚠ CALIBER (2026-07-01, pinned via 建发股份 decomposition): 果仁's `分红总金额` is a 季报指标 attributed to the
    dividend's REPORT PERIOD (`end_date`), and `sumq(分红总金额,4,0)` sums the last 4 FISCAL QUARTERS. This is NOT
    the same as the ann-date trailing-365-day window (`declared_dividend_ttm`, which is the 股息率TTM caliber): a
    2024-interim dividend (end_date 2024Q3, announced 2025-01) is INSIDE a 365-day ann-window but OUTSIDE the last-4
    fiscal quarters {2024Q4,2025Q1,Q2,Q3}. Use THIS (report-period) for 分红总金额 sumq/annual factors
    (DivOP%/DivGrPY%/…); use `declared_dividend_ttm` only for 股息率TTM. (建发: ann-window 0.7 vs report-period 0.3.)
    Stale-预案 phantoms are dropped by default (see `_declared_events`)."""
    ev = _declared_events(signal_date, pretax=pretax, drop_stale_plans=drop_stale_plans)
    return ev.groupby(["c6", "ed"])["dps"].sum().unstack("ed")


def declared_dividend_by_fy(signal_date: str, *, pretax: bool = True,
                            drop_stale_plans: bool = True) -> pd.DataFrame:
    """Per-FISCAL-YEAR declared dividend PER SHARE (for 果仁's `annual(分红总金额, k)`). Returns a DataFrame indexed
    by 6-digit code, columns = fiscal_year int (from end_date), values = that FY's total declared dividend/share
    (interim+final summed; NaN if none). As-of a signal in year Y with only quarterly reports out, `annual(分红,0)`
    = FY(Y-1) (最近年报 convention — e.g. FY2024 as-of 2025-12-31). Stale-预案 phantoms dropped by default
    (正丹股份: FY2024 1.10→0.70, the 果仁 value — see `_declared_events`)."""
    ev = _declared_events(signal_date, pretax=pretax, drop_stale_plans=drop_stale_plans)
    return ev.groupby(["c6", "fy"])["dps"].sum().unstack("fy")


if __name__ == "__main__":  # quick self-check against the 2025-12-31 export
    import sys
    sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
    dps = declared_dividend_ttm("2025-12-31")
    print(f"declared-dividend TTM (2025-12-31): {len(dps)} stocks with a trailing declared dividend")
    print("  sample:", {k: round(v, 3) for k, v in dps.sort_values(ascending=False).head(5).items()})
