"""果仁 parity rung-4 REVERSE-ENGINEERING: nail the ambiguous factors to penny-exact.

Uses 果仁's EXACT published formulas
(workspace/research/idea_sourcing/guorn/indicator_reference_auto.md):
  BP                 = 归属母公司股东权益合计/总市值
                       → total_hldr_eqy_EXC_min_int (parent-only), NOT inc_min_int (total)
  市盈率              = built-in PE  → try $pe (static) vs $pe_ttm (trailing)
  250日涨幅          = 后复权收盘价/REF(后复权收盘价,250)-1   (ratio ⇒ adj-convention-invariant)
  N日乖离率(120)     = (收盘价-MA(收盘价,120))/MA(收盘价,120)  → raw vs 后复权 close
  ILLIQ(5)           = Amihud  → MA(|ret|/amt,5) variants (ret raw vs adj; div-then-MA vs MA-ratio)
  股价振幅%成交额10日 = MA((高-低)/前收/当日成交额,10)         (already penny-exact; re-confirm + fix sign)

For each factor, try candidate formulas/fields and report which is penny-exact.
Prints sample rows for the still-ambiguous ones so the residual is diagnosable, not guessed.
NON-FORMAL diagnostic. Writes rung4_reverse_engineer.json.
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


def _load_guorn(colsub):
    """All (qlib_code, date, guorn_value) across books showing the EXACT column `colsub`."""
    rows = []
    for f in sorted(glob.glob(str(ROOT / "Knowledge/果仁回测结果/*.xlsx"))):
        try:
            cols = pd.read_excel(f, sheet_name="各阶段持仓详单", nrows=0).columns.tolist()
        except Exception:
            continue
        names = [str(c) for c in cols]
        if colsub not in names or "股票代码" not in names:
            continue
        g = pd.read_excel(f, sheet_name="各阶段持仓详单")
        c6 = g["股票代码"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
        q = c6 + np.where(c6.str[0].isin(["6", "9"]), "_SH", "_SZ")
        d = pd.to_datetime(g["开始日期"]); v = pd.to_numeric(g[colsub], errors="coerce")
        for a, b, c in zip(q, d, v):
            if pd.notna(c):
                rows.append((a, b, c))
    return pd.DataFrame(rows, columns=["q", "date", "gf"]).dropna()


def _parity(g, getter, n_sample=0):
    """Compare guorn value to getter(q, date) across all holdings. Power-of-10 scale-detect."""
    recs = []
    for _, r in g.iterrows():
        v = getter(r["q"], r["date"])
        if v is not None and np.isfinite(v):
            recs.append((r["q"], r["date"], r["gf"], float(v)))
    cmp = pd.DataFrame(recs, columns=["q", "date", "gf", "loc"]).dropna()
    if cmp.empty:
        return {"n": 0}, cmp
    ratio = (cmp["loc"] / cmp["gf"].replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).abs().dropna()
    med = ratio.median()
    scale = 10.0 ** round(float(np.log10(med))) if (np.isfinite(med) and med > 0) else 1.0
    locs = cmp["loc"] / scale
    rel = (locs - cmp["gf"]).abs() / cmp["gf"].abs().clip(lower=0.05)
    stats = {"n": int(len(cmp)), "scale": scale,
             "median_relerr": round(float(rel.median()), 6),
             "within_1pct": round(float((rel <= 0.01).mean()), 4),
             "within_5pct": round(float((rel <= 0.05).mean()), 4),
             "sign_match": round(float((np.sign(locs) == np.sign(cmp["gf"])).mean()), 4)}
    samp = cmp.assign(loc_scaled=locs, relerr=rel).head(n_sample) if n_sample else cmp.iloc[:0]
    return stats, samp


def _point_getter(wides, expr):
    """As-of getter for point fields: expr(vals_dict) over latest trading day <= date."""
    def getter(q, d):
        vals = {}
        for c, w in wides.items():
            if q not in w.columns:
                return None
            s = w[q]; pos = s.index.searchsorted(d, side="right") - 1
            vals[c] = s.iat[pos] if pos >= 0 else np.nan
        try:
            return expr(vals)
        except Exception:
            return None
    return getter


def _roll_getter(panel, lag):
    idx = panel.index
    def getter(q, d):
        if q not in panel.columns:
            return None
        pos = idx.searchsorted(d, side="right") - 1 - lag
        if pos < 0:
            return None
        return panel.iat[pos, panel.columns.get_loc(q)]
    return getter


def main():
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data/qlib_data"), region=REG_CN, kernels=1)
    results = {}

    # ── field-availability probe ──────────────────────────────────────────────
    probe_codes = ["000001_SZ", "600519_SH", "300750_SZ"]
    for fld in ["$total_hldr_eqy_exc_min_int_q0", "$total_hldr_eqy_inc_min_int_q0", "$pe", "$pe_ttm"]:
        try:
            t = D.features(probe_codes, [fld], start_time="2024-01-01", end_time="2024-12-31", freq="day")
            ok = t[fld].notna().any()
        except Exception as e:
            ok = f"ERR:{type(e).__name__}"
        print(f"[probe] {fld:38s} -> {ok}", flush=True)
        results.setdefault("_probe", {})[fld] = str(ok)

    # ── BP: parent-equity (exc) vs total (inc) ────────────────────────────────
    gBP = _load_guorn("BP")
    print(f"\n[BP] {len(gBP)} guorn holdings", flush=True)
    if not gBP.empty:
        insts = sorted(gBP["q"].unique())
        for tag, eqfield in [("exc_min_int", "$total_hldr_eqy_exc_min_int_q0"),
                             ("inc_min_int", "$total_hldr_eqy_inc_min_int_q0")]:
            try:
                df = D.features(insts, [eqfield, "$total_mv"], start_time="2013-06-01",
                                end_time="2026-06-20", freq="day")
                df.columns = ["eq", "mv"]
                wides = {c: df[c].unstack(level=0).sort_index() for c in df.columns}
                g = _point_getter(wides, lambda v: v["eq"] / v["mv"] if v["mv"] else np.nan)
                st, _ = _parity(gBP, g)
                print(f"[BP] {tag:12s} -> {json.dumps(st, ensure_ascii=False)}", flush=True)
                results.setdefault("BP", {})[tag] = st
            except Exception as e:
                print(f"[BP] {tag:12s} -> ERR {e}", flush=True)
                results.setdefault("BP", {})[tag] = f"ERR:{e}"

    # ── 市盈率: $pe (static) vs $pe_ttm (trailing) ─────────────────────────────
    gPE = _load_guorn("市盈率")
    print(f"\n[市盈率] {len(gPE)} guorn holdings", flush=True)
    if not gPE.empty:
        insts = sorted(gPE["q"].unique())
        df = D.features(insts, ["$pe", "$pe_ttm"], start_time="2013-06-01", end_time="2026-06-20", freq="day")
        df.columns = ["pe", "pe_ttm"]
        wides = {c: df[c].unstack(level=0).sort_index() for c in df.columns}
        for tag, key in [("pe_static", "pe"), ("pe_ttm", "pe_ttm")]:
            g = _point_getter({key: wides[key]}, lambda v, k=key: v[k])
            st, _ = _parity(gPE, g)
            print(f"[市盈率] {tag:10s} -> {json.dumps(st, ensure_ascii=False)}", flush=True)
            results.setdefault("市盈率", {})[tag] = st

    # ── price/volume rolling factors ──────────────────────────────────────────
    pv_factors = ["250日涨幅", "N日乖离率(120)", "ILLIQ(5)", "股价振幅%当日成交额10日"]
    gmap = {n: _load_guorn(n) for n in pv_factors}
    insts = sorted(set().union(*[set(g["q"]) for g in gmap.values() if not g.empty]))
    print(f"\n[pricevol] {len(insts)} held codes", flush=True)
    df = D.features(insts, ["$open", "$close", "$high", "$low", "$vol", "$amount", "$adj_factor"],
                    start_time="2011-06-01", end_time="2026-06-20", freq="day")
    df.columns = ["open", "close", "high", "low", "vol", "amount", "adj"]
    close = df["close"].unstack(level=0).sort_index()
    adjc = (df["close"] * df["adj"]).unstack(level=0).sort_index()
    high = df["high"].unstack(level=0).sort_index()
    low = df["low"].unstack(level=0).sort_index()
    amt = df["amount"].unstack(level=0).sort_index()
    vol = df["vol"].unstack(level=0).sort_index()

    # candidate panels per factor
    candidates = {
        "250日涨幅": {
            "adj_ratio": adjc / adjc.shift(250) - 1.0,
            "raw_ratio": close / close.shift(250) - 1.0,
        },
        "N日乖离率(120)": {
            "raw_close": (close - close.rolling(120).mean()) / close.rolling(120).mean(),
            "adj_close": (adjc - adjc.rolling(120).mean()) / adjc.rolling(120).mean(),
        },
        "ILLIQ(5)": {
            "adjret_div_amt": (adjc.pct_change().abs() / amt).rolling(5).mean(),
            "rawret_div_amt": (close.pct_change().abs() / amt).rolling(5).mean(),
            "ratio_of_MAs": adjc.pct_change().abs().rolling(5).mean() / amt.rolling(5).mean(),
            "adjret_div_vol": (adjc.pct_change().abs() / vol).rolling(5).mean(),
        },
        "股价振幅%当日成交额10日": {
            "amp_div_amt": (((high - low) / close.shift(1)) / amt).rolling(10).mean(),
        },
    }
    for name in pv_factors:
        g = gmap[name]
        if g.empty:
            continue
        print(f"\n[{name}] {len(g)} guorn holdings", flush=True)
        best = None
        for tag, panel in candidates[name].items():
            for lag in (0, 1):
                st, samp = _parity(g, _roll_getter(panel, lag), n_sample=6)
                if st.get("n", 0) == 0:
                    continue
                line = {**st, "variant": tag, "lag": lag}
                print(f"  {tag:16s} lag{lag} -> med_relerr={st['median_relerr']} "
                      f"w1%={st['within_1pct']} w5%={st['within_5pct']} sign={st['sign_match']} n={st['n']}",
                      flush=True)
                if best is None or st["median_relerr"] < best["median_relerr"]:
                    best = line
                    best_samp = samp
        results.setdefault("pricevol", {})[name] = best
        if best is not None:
            print(f"  BEST: {best['variant']} lag{best['lag']} med_relerr={best['median_relerr']}", flush=True)
            print("  samples (q, date, gf, loc_scaled, relerr):", flush=True)
            for _, s in best_samp.iterrows():
                print(f"    {s['q']} {str(s['date'])[:10]} gf={s['gf']:.6g} "
                      f"loc={s['loc_scaled']:.6g} rel={s['relerr']:.4g}", flush=True)

    OUT.joinpath("rung4_reverse_engineer.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n[done] wrote rung4_reverse_engineer.json", flush=True)


if __name__ == "__main__":
    main()
