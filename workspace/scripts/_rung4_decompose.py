"""果仁 parity rung-4 DECOMPOSITION + exact ILLIQ.

(1) BP/PE residual decomposition — 果仁 holdings carry a 总市值(亿) column AND 开始价格(前复权).
    The pure-fundamental statement factors were penny-exact; BP/PE carry a market-price
    denominator and show ~1% residual. Decompose it:
      a) my $total_mv (万元) vs 果仁 总市值(亿)×1e4  at lag 0 / 1  → is the price/cap source+day exact?
    If 总市值 matches penny-exact at some lag, the BP residual is the EQUITY PIT-timing; if not,
    it is the price source/day. Either way the ambiguity is localized with data, not guessed.

(2) ILLIQ exact 果仁 formula (guorn_aichat_indicator_defs.md):
      Amihud = MA(|1日涨幅| / 成交额(亿元), 5)   ; 成交额(亿元) = Tushare amount(千元)/1e5
    Recompute with the exact unit; print the RAW (gf/mine) ratio distribution (no scale-detect)
    to see whether the residual is a constant unit factor or a variable formula difference.

NON-FORMAL diagnostic. Writes rung4_decompose.json.
"""
from __future__ import annotations
import json
import sys
import glob
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")
OUT = ROOT / "workspace" / "outputs" / "guorn_parity"


def _find_col(names, *subs):
    for c in names:
        cs = str(c)
        if all(s in cs for s in subs):
            return c
    return None


def _load_books(need_col):
    """Per-holding (q, date, gf, mv_yi, startpx) across books showing exact column `need_col`."""
    rows = []
    for f in sorted(glob.glob(str(ROOT / "Knowledge/果仁回测结果/*.xlsx"))):
        try:
            names = [str(c) for c in pd.read_excel(f, sheet_name="各阶段持仓详单", nrows=0).columns]
        except Exception:
            continue
        if need_col not in names or "股票代码" not in names:
            continue
        g = pd.read_excel(f, sheet_name="各阶段持仓详单")
        mv_c = _find_col(names, "总市值", "亿")     # the 总市值(亿) DISPLAY col, not a factor name w/ 总市值
        px_c = _find_col(names, "开始价格", "复权")
        c6 = g["股票代码"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
        q = c6 + np.where(c6.str[0].isin(["6", "9"]), "_SH", "_SZ")
        d = pd.to_datetime(g["开始日期"])
        gf = pd.to_numeric(g[need_col], errors="coerce")
        mv = pd.to_numeric(g[mv_c], errors="coerce") if mv_c else pd.Series(np.nan, index=g.index)
        px = pd.to_numeric(g[px_c], errors="coerce") if px_c else pd.Series(np.nan, index=g.index)
        for a, b, c, m, p in zip(q, d, gf, mv, px):
            if pd.notna(c):
                rows.append((a, b, c, m, p))
    return pd.DataFrame(rows, columns=["q", "date", "gf", "mv_yi", "startpx"]).dropna(subset=["gf"])


def _asof(panel, q, d, lag):
    if q not in panel.columns:
        return np.nan
    idx = panel.index
    pos = idx.searchsorted(d, side="right") - 1 - lag
    return panel.iat[pos, panel.columns.get_loc(q)] if pos >= 0 else np.nan


def _stats(loc, gf, floor):
    loc, gf = np.asarray(loc, float), np.asarray(gf, float)
    m = np.isfinite(loc) & np.isfinite(gf)
    loc, gf = loc[m], gf[m]
    rel = np.abs(loc - gf) / np.clip(np.abs(gf), floor, None)
    return {"n": int(m.sum()), "median_relerr": round(float(np.median(rel)), 6),
            "within_0.1pct": round(float((rel <= 0.001).mean()), 4),
            "within_1pct": round(float((rel <= 0.01).mean()), 4),
            "within_5pct": round(float((rel <= 0.05).mean()), 4)}


def main():
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data/qlib_data"), region=REG_CN, kernels=1)
    results = {}

    # ── (1) 总市值 decomposition (BP book) ─────────────────────────────────────
    gBP = _load_books("BP")
    gBP = gBP.dropna(subset=["mv_yi"])
    print(f"[总市值] {len(gBP)} BP holdings with a 总市值(亿) column", flush=True)
    if not gBP.empty:
        insts = sorted(gBP["q"].unique())
        df = D.features(insts, ["$total_mv", "$close", "$open", "$adj_factor"],
                        start_time="2013-06-01", end_time="2026-06-20", freq="day")
        df.columns = ["total_mv", "close", "open", "adj"]
        mv_w = df["total_mv"].unstack(level=0).sort_index()    # 万元
        for lag in (0, 1):
            loc = [_asof(mv_w, r.q, r.date, lag) for r in gBP.itertuples()]
            gf_w = gBP["mv_yi"].values * 1e4                    # 亿 → 万元
            st = _stats(loc, gf_w, floor=1.0)
            print(f"[总市值] my $total_mv vs 果仁 总市值  lag{lag} -> {json.dumps(st)}", flush=True)
            results.setdefault("total_mv_decomp", {})[f"lag{lag}"] = st

    # ── (2) ILLIQ exact: MA(|raw ret| / 成交额(亿元), 5) ────────────────────────
    def _load_simple(col):
        rows = []
        for f in sorted(glob.glob(str(ROOT / "Knowledge/果仁回测结果/*.xlsx"))):
            try:
                names = [str(c) for c in pd.read_excel(f, sheet_name="各阶段持仓详单", nrows=0).columns]
            except Exception:
                continue
            if col not in names or "股票代码" not in names:
                continue
            g = pd.read_excel(f, sheet_name="各阶段持仓详单")
            c6 = g["股票代码"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
            q = c6 + np.where(c6.str[0].isin(["6", "9"]), "_SH", "_SZ")
            d = pd.to_datetime(g["开始日期"]); v = pd.to_numeric(g[col], errors="coerce")
            for a, b, c in zip(q, d, v):
                if pd.notna(c):
                    rows.append((a, b, c))
        return pd.DataFrame(rows, columns=["q", "date", "gf"]).dropna()

    gI = _load_simple("ILLIQ(5)")
    print(f"\n[ILLIQ] {len(gI)} holdings", flush=True)
    if not gI.empty:
        insts = sorted(gI["q"].unique())
        df = D.features(insts, ["$close", "$high", "$low", "$amount", "$adj_factor"],
                        start_time="2011-06-01", end_time="2026-06-20", freq="day")
        df.columns = ["close", "high", "low", "amount", "adj"]
        close = df["close"].unstack(level=0).sort_index()
        high = df["high"].unstack(level=0).sort_index()
        low = df["low"].unstack(level=0).sort_index()
        amt_yi = df["amount"].unstack(level=0).sort_index() / 1e5     # 千元 → 亿元
        rawret = close.pct_change(fill_method=None).abs()
        amplitude = (high - low) / close.shift(1)                    # 股价振幅 = (高-低)/前收
        variants = {
            "ret_per_day": (rawret / amt_yi).rolling(5).mean(),       # |1日涨幅|/成交额亿
            "amp_per_day": (amplitude / amt_yi).rolling(5).mean(),    # 股价振幅/成交额亿  ← hypothesis
        }
        for tag, panel in variants.items():
            for lag in (0, 1):
                loc = np.array([_asof(panel, r.q, r.date, lag) for r in gI.itertuples()], float)
                gf = gI["gf"].values
                m = np.isfinite(loc) & np.isfinite(gf) & (gf != 0)
                ratio = gf[m] / loc[m]            # 果仁 / mine, RAW (no scale-detect)
                st = _stats(loc, gf, floor=0.01)
                print(f"[ILLIQ] {tag:14s} lag{lag} -> {json.dumps(st)} | gf/mine "
                      f"median={np.median(ratio):.4g} p25={np.percentile(ratio,25):.4g} "
                      f"p75={np.percentile(ratio,75):.4g}", flush=True)
                results.setdefault("ILLIQ", {})[f"{tag}_lag{lag}"] = {
                    **st, "ratio_median": round(float(np.median(ratio)), 6),
                    "ratio_p25": round(float(np.percentile(ratio, 25)), 6),
                    "ratio_p75": round(float(np.percentile(ratio, 75)), 6)}

    OUT.joinpath("rung4_decompose.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n[done] wrote rung4_decompose.json", flush=True)


if __name__ == "__main__":
    main()
