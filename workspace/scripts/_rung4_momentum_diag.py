"""果仁 parity rung-4: decisive diagnosis of the 250日涨幅 / 乖离率 long-window residual.

250日涨幅 = adjc[t]/adjc[t-250]-1 is 复权-base-INVARIANT (后复权-present and 前复权-as-of give the
identical ratio; raw is far worse) — so the residual is NOT a 复权-convention choice. Two candidates
remain: (a) the WINDOW count (果仁's "250日" ≠ exactly 250 trading days), (b) date-specific adj_factor
differences on corporate-action dates (Tushare vs 果仁 复权 factor).

Decisive tests:
  1. WINDOW SWEEP — N in {244..255}: if a clean N collapses the residual, it's a window-count issue.
  2. CORP-ACTION SPLIT — subset where adj[t]==adj[t-N] (no corp action in window) vs changed:
     if the no-corp-action subset is penny-exact, the residual IS adj_factor on corp-action dates.
Same split for 乖离率 (no corp action in the 120d window).
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


def _pos(idx, d, lag):
    return idx.searchsorted(d, side="right") - 1 - lag


def main():
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data/qlib_data"), region=REG_CN, kernels=1)
    results = {}

    # ── 250日涨幅 ──────────────────────────────────────────────────────────────
    g = _load_simple("250日涨幅")
    insts = sorted(g["q"].unique())
    print(f"[250日涨幅] {len(g)} holdings / {len(insts)} codes", flush=True)
    df = D.features(insts, ["$close", "$adj_factor"], start_time="2011-06-01",
                    end_time="2026-06-20", freq="day")
    df.columns = ["close", "adj"]
    adjc = (df["close"] * df["adj"]).unstack(level=0).sort_index()
    adjf = df["adj"].unstack(level=0).sort_index()
    idx = adjc.index

    # window sweep at lag 0 and 1
    print("  WINDOW SWEEP (median_relerr):", flush=True)
    for N in (240, 244, 245, 248, 250, 252, 255, 260):
        ratio_panel = adjc / adjc.shift(N) - 1.0
        line = {}
        for lag in (0, 1):
            loc, gf = [], []
            for r in g.itertuples():
                if r.q not in ratio_panel.columns:
                    continue
                p = _pos(idx, r.date, lag)
                if p < 0:
                    continue
                v = ratio_panel.iat[p, ratio_panel.columns.get_loc(r.q)]
                if np.isfinite(v):
                    loc.append(v); gf.append(r.gf)
            loc, gf = np.array(loc), np.array(gf)
            rel = np.abs(loc - gf) / np.clip(np.abs(gf), 0.02, None)
            line[f"lag{lag}"] = round(float(np.median(rel)), 5)
        print(f"    N={N}: {line}", flush=True)
        results.setdefault("250_window_sweep", {})[f"N{N}"] = line

    # corp-action split at N=250, lag0
    N, lag = 250, 0
    ratio_panel = adjc / adjc.shift(N) - 1.0
    rows = []
    for r in g.itertuples():
        if r.q not in ratio_panel.columns:
            continue
        p = _pos(idx, r.date, lag)
        if p < N:
            continue
        v = ratio_panel.iat[p, ratio_panel.columns.get_loc(r.q)]
        af_t = adjf.iat[p, adjf.columns.get_loc(r.q)]
        af_0 = adjf.iat[p - N, adjf.columns.get_loc(r.q)]
        if np.isfinite(v) and np.isfinite(af_t) and np.isfinite(af_0):
            rows.append((r.gf, v, abs(af_t / af_0 - 1.0) < 1e-6))
    arr = pd.DataFrame(rows, columns=["gf", "loc", "no_ca"])
    for sub, label in [(arr[arr.no_ca], "no_corp_action"), (arr[~arr.no_ca], "corp_action")]:
        if len(sub):
            rel = (sub["loc"] - sub["gf"]).abs() / sub["gf"].abs().clip(lower=0.02)
            st = {"n": len(sub), "median_relerr": round(float(rel.median()), 5),
                  "within_1pct": round(float((rel <= 0.01).mean()), 4),
                  "within_5pct": round(float((rel <= 0.05).mean()), 4)}
            print(f"  [250] {label:16s} -> {json.dumps(st)}", flush=True)
            results.setdefault("250_corp_split", {})[label] = st

    # ── 乖离率(120) corp-action split (adj close, lag1) ────────────────────────
    g2 = _load_simple("N日乖离率(120)")
    insts2 = sorted(g2["q"].unique())
    print(f"\n[乖离率120] {len(g2)} holdings / {len(insts2)} codes", flush=True)
    df2 = D.features(insts2, ["$close", "$adj_factor"], start_time="2011-06-01",
                     end_time="2026-06-20", freq="day")
    df2.columns = ["close", "adj"]
    adjc2 = (df2["close"] * df2["adj"]).unstack(level=0).sort_index()
    adjf2 = df2["adj"].unstack(level=0).sort_index()
    bias = (adjc2 - adjc2.rolling(120).mean()) / adjc2.rolling(120).mean()
    idx2 = adjc2.index
    rows = []
    lag = 1
    for r in g2.itertuples():
        if r.q not in bias.columns:
            continue
        p = _pos(idx2, r.date, lag)
        if p < 120:
            continue
        v = bias.iat[p, bias.columns.get_loc(r.q)]
        af_t = adjf2.iat[p, adjf2.columns.get_loc(r.q)]
        af_0 = adjf2.iat[p - 120, adjf2.columns.get_loc(r.q)]
        if np.isfinite(v) and np.isfinite(af_t) and np.isfinite(af_0):
            rows.append((r.gf, v, abs(af_t / af_0 - 1.0) < 1e-6))
    arr2 = pd.DataFrame(rows, columns=["gf", "loc", "no_ca"])
    for sub, label in [(arr2[arr2.no_ca], "no_corp_action"), (arr2[~arr2.no_ca], "corp_action")]:
        if len(sub):
            rel = (sub["loc"] - sub["gf"]).abs() / sub["gf"].abs().clip(lower=0.02)
            st = {"n": len(sub), "median_relerr": round(float(rel.median()), 5),
                  "within_1pct": round(float((rel <= 0.01).mean()), 4),
                  "within_5pct": round(float((rel <= 0.05).mean()), 4)}
            print(f"  [乖离率] {label:16s} -> {json.dumps(st)}", flush=True)
            results.setdefault("bias_corp_split", {})[label] = st

    OUT.joinpath("rung4_momentum_diag.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n[done]", flush=True)


if __name__ == "__main__":
    main()
