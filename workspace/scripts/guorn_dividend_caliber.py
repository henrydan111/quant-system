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


if __name__ == "__main__":  # quick self-check against the 2025-12-31 export
    import sys
    sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
    dps = declared_dividend_ttm("2025-12-31")
    print(f"declared-dividend TTM (2025-12-31): {len(dps)} stocks with a trailing declared dividend")
    print("  sample:", {k: round(v, 3) for k, v in dps.sort_values(ascending=False).head(5).items()})
