"""果仁 parity rung-4 batch 3: price/volume ROLLING factor parity vs 果仁.

These need rolling windows (not point reads). Read daily OHLC/amount/adj for the held
codes, compute each rolling factor as a (datetime x code) panel, look up AS-OF the holding
date (and prev day — empirically settle which 果仁 uses), compare to 果仁's displayed value.
Auto-detects display scale. NON-FORMAL. Appends to rung4_field_parity.json (separate file).

⚠ SUPERSEDED for the exact formulas — the reverse-engineering (2026-06-23) corrected these:
  · 果仁 displays factors at the SIGNAL date (T-1), not the buy date → use lag 1.
  · ILLIQ(5) numerator is 股价振幅 (high-low)/prev_close, NOT |1日涨幅| (the aichat doc was wrong);
    denom 成交额(亿元)=amount(千元)/1e5; avg-of-ratios. → see _rung4_decompose.py / _illiq_bp_final.py.
  · 股价振幅%成交额10日 is UN-VALIDATABLE: 果仁 displays 0.00 (true value ~2e-6 rounds to 0 at 2-dec).
  · 250日涨幅/乖离率 residual is the N-day lookback window-membership counting (NOT data/复权/corp-action;
    proven in _rung4_momentum_diag.py). The close data itself is validated via 总市值.
"""
from __future__ import annotations
import json
import sys
import glob
import os
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace" / "research" / "long_only_50cagr"))
sys.stdout.reconfigure(encoding="utf-8")
OUT = ROOT / "workspace" / "outputs" / "guorn_parity"


def _load_guorn(colsub):
    rows = []
    for f in sorted(glob.glob(str(ROOT / "Knowledge/果仁回测结果/*.xlsx"))):
        try:
            cols = pd.read_excel(f, sheet_name="各阶段持仓详单", nrows=0).columns.tolist()
        except Exception:
            continue
        names = [str(c) for c in cols]
        if colsub not in names or "股票代码" not in names:  # skip fund/multi-asset books (基金代码)
            continue
        g = pd.read_excel(f, sheet_name="各阶段持仓详单")
        c6 = g["股票代码"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
        q = c6 + np.where(c6.str[0].isin(["6", "9"]), "_SH", "_SZ")
        d = pd.to_datetime(g["开始日期"]); v = pd.to_numeric(g[colsub], errors="coerce")
        for a, b, c in zip(q, d, v):
            if pd.notna(c):
                rows.append((a, b, c))
    return pd.DataFrame(rows, columns=["q", "date", "gf"]).dropna()


def _asof_compare(panel, g, lag):
    idx = panel.index
    recs = []
    for _, r in g.iterrows():
        q, d = r["q"], r["date"]
        if q not in panel.columns:
            continue
        pos = idx.searchsorted(d, side="right") - 1 - lag
        if pos < 0:
            continue
        v = panel.iat[pos, panel.columns.get_loc(q)]
        if pd.notna(v):
            recs.append((r["gf"], float(v)))
    cmp = pd.DataFrame(recs, columns=["gf", "loc"]).dropna()
    if cmp.empty:
        return None
    ratio = (cmp["loc"] / cmp["gf"].replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).abs().dropna()
    med = ratio.median() if len(ratio) else np.nan
    scale = 10.0 ** round(float(np.log10(med))) if (np.isfinite(med) and med > 0) else 1.0
    locs = cmp["loc"] / scale
    rel = (locs - cmp["gf"]).abs() / cmp["gf"].abs().clip(lower=0.05)
    return {"n": int(len(cmp)), "scale": scale, "median_relerr": round(float(rel.median()), 6),
            "within_1pct": round(float((rel <= 0.01).mean()), 4),
            "sign_match": round(float((np.sign(locs) == np.sign(cmp["gf"])).mean()), 4)}


def main():
    factors = ["250日涨幅", "N日乖离率(120)", "ILLIQ(5)", "股价振幅%当日成交额10日"]
    gmap = {name: _load_guorn(name) for name in factors}
    insts = sorted(set().union(*[set(g["q"]) for g in gmap.values() if not g.empty]))
    print(f"[pricevol] {len(insts)} held codes across {sum(1 for g in gmap.values() if not g.empty)} factors", flush=True)

    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data/qlib_data"), region=REG_CN, kernels=1)
    df = D.features(insts, ["$open", "$close", "$high", "$low", "$amount", "$adj_factor"],
                    start_time="2012-06-01", end_time="2026-06-20", freq="day")
    df.columns = ["open", "close", "high", "low", "amount", "adj"]
    close = df["close"].unstack(level=0).sort_index()
    adjc = (df["close"] * df["adj"]).unstack(level=0).sort_index()
    high = df["high"].unstack(level=0).sort_index()
    low = df["low"].unstack(level=0).sort_index()
    amt = df["amount"].unstack(level=0).sort_index()

    panels = {
        "250日涨幅": adjc / adjc.shift(250) - 1.0,
        "N日乖离率(120)": (close - close.rolling(120).mean()) / close.rolling(120).mean(),
        "ILLIQ(5)": (adjc.pct_change().abs() / amt).rolling(5).mean(),
        "股价振幅%当日成交额10日": (((high - low) / close.shift(1)) / amt).rolling(10).mean(),
    }
    results = []
    for name in factors:
        g = gmap[name]
        if g.empty or name not in panels:
            results.append({"factor": name, "status": "skip"}); continue
        best = None
        for lag in (0, 1):  # empirically settle whether 果仁 displays as-of d or d-1
            r = _asof_compare(panels[name], g, lag)
            if r and (best is None or r["within_1pct"] > best["within_1pct"]):
                best = {**r, "lag": lag}
        out = {"factor": name, "status": "ok", "n_guorn": int(len(g)), **(best or {})}
        results.append(out)
        print(json.dumps(out, ensure_ascii=False), flush=True)
    OUT.joinpath("rung4_pricevol_parity.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
