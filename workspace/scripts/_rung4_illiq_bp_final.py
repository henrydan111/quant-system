"""果仁 parity rung-4 FINAL: nail ILLIQ averaging convention + confirm BP at signal-date lag.

ILLIQ: numerator confirmed = 股价振幅 (high-low)/prev_close, denom = 成交额(亿元). Remaining gf/mine
       ~0.86 → test average-of-ratios MA(振幅/amt,5) vs ratio-of-averages MA(振幅,5)/MA(amt,5),
       and the 5-day mean of amt as the denominator. At signal-date lag (1).
BP   : exc_min_int_q0 / total_mv — re-test at lag0 vs lag1 (果仁 shows signal-date T-1) to confirm
       the residual collapses to ~display precision (penny-exact given 总市值 2-dec display).
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


def _asof(panel, q, d, lag):
    if q not in panel.columns:
        return np.nan
    idx = panel.index
    pos = idx.searchsorted(d, side="right") - 1 - lag
    return panel.iat[pos, panel.columns.get_loc(q)] if pos >= 0 else np.nan


def _eval(panel, g, lag, floor):
    loc = np.array([_asof(panel, r.q, r.date, lag) for r in g.itertuples()], float)
    gf = g["gf"].values.astype(float)
    m = np.isfinite(loc) & np.isfinite(gf) & (gf != 0)
    rel = np.abs(loc[m] - gf[m]) / np.clip(np.abs(gf[m]), floor, None)
    ratio = gf[m] / loc[m]
    return {"n": int(m.sum()), "median_relerr": round(float(np.median(rel)), 6),
            "within_0.1pct": round(float((rel <= 0.001).mean()), 4),
            "within_1pct": round(float((rel <= 0.01).mean()), 4),
            "within_5pct": round(float((rel <= 0.05).mean()), 4),
            "ratio_med": round(float(np.median(ratio)), 4),
            "ratio_p25": round(float(np.percentile(ratio, 25)), 4),
            "ratio_p75": round(float(np.percentile(ratio, 75)), 4)}


def main():
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data/qlib_data"), region=REG_CN, kernels=1)
    results = {}

    # ── ILLIQ averaging-convention sweep (振幅 numerator) ──────────────────────
    gI = _load_simple("ILLIQ(5)")
    print(f"[ILLIQ] {len(gI)} holdings", flush=True)
    insts = sorted(gI["q"].unique())
    df = D.features(insts, ["$close", "$high", "$low", "$amount"],
                    start_time="2011-06-01", end_time="2026-06-20", freq="day")
    df.columns = ["close", "high", "low", "amount"]
    close = df["close"].unstack(level=0).sort_index()
    high = df["high"].unstack(level=0).sort_index()
    low = df["low"].unstack(level=0).sort_index()
    amt_yi = df["amount"].unstack(level=0).sort_index() / 1e5     # 千元 → 亿元
    amp = (high - low) / close.shift(1)
    variants = {
        "avg_of_ratios":  (amp / amt_yi).rolling(5).mean(),               # MA(振幅/amt,5)
        "ratio_of_avgs":  amp.rolling(5).mean() / amt_yi.rolling(5).mean(),  # MA(振幅,5)/MA(amt,5)
        "amp_over_avgamt": amp / amt_yi.rolling(5).mean(),                # 振幅 / 5日均成交额亿
    }
    for tag, panel in variants.items():
        st = _eval(panel, gI, lag=1, floor=0.01)
        print(f"[ILLIQ] {tag:16s} lag1 -> med={st['median_relerr']} w0.1%={st['within_0.1pct']} "
              f"w1%={st['within_1pct']} w5%={st['within_5pct']} | gf/mine "
              f"med={st['ratio_med']} ({st['ratio_p25']}-{st['ratio_p75']})", flush=True)
        results.setdefault("ILLIQ", {})[tag] = st

    # ── BP at signal-date lag (exc_min_int parent equity) ─────────────────────
    gBP = _load_simple("BP")
    print(f"\n[BP] {len(gBP)} holdings", flush=True)
    insts = sorted(gBP["q"].unique())
    df = D.features(insts, ["$total_hldr_eqy_exc_min_int_q0", "$total_mv"],
                    start_time="2013-06-01", end_time="2026-06-20", freq="day")
    df.columns = ["eq", "mv"]
    eq_w = df["eq"].unstack(level=0).sort_index()
    mv_w = df["mv"].unstack(level=0).sort_index()
    for lag in (0, 1):
        # equity is slow-moving (q0 snapshot); only the 总市值 denom needs the signal-date lag.
        loc = []
        for r in gBP.itertuples():
            e = _asof(eq_w, r.q, r.date, lag)
            m = _asof(mv_w, r.q, r.date, lag)
            loc.append(e / m if (np.isfinite(e) and np.isfinite(m) and m) else np.nan)
        loc = np.array(loc, float); gf = gBP["gf"].values.astype(float)
        mm = np.isfinite(loc) & np.isfinite(gf) & (gf != 0)
        # BP scale: equity(元)/total_mv(万元) → 1e4 unit; correct it
        ratio = (loc[mm] / gf[mm])
        scale = 10.0 ** round(float(np.log10(np.median(np.abs(ratio)))))
        locs = loc / scale
        rel = np.abs(locs[mm] - gf[mm]) / np.clip(np.abs(gf[mm]), 0.01, None)
        st = {"n": int(mm.sum()), "scale": scale, "median_relerr": round(float(np.median(rel)), 6),
              "within_0.1pct": round(float((rel <= 0.001).mean()), 4),
              "within_1pct": round(float((rel <= 0.01).mean()), 4),
              "within_5pct": round(float((rel <= 0.05).mean()), 4)}
        print(f"[BP] exc_min_int lag{lag} -> {json.dumps(st)}", flush=True)
        results.setdefault("BP", {})[f"lag{lag}"] = st

    OUT.joinpath("rung4_illiq_bp_final.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n[done]", flush=True)


if __name__ == "__main__":
    main()
