"""Composite-fidelity diag for #1: where do 果仁's held names sit in MY composite ranking, and how well
does my composite agree with 果仁's exported 总排名分? Sampled days (every 5th) for speed. Reuses the
harness cache + _composite_row. High percentile (>0.9) + high corr => composite broadly faithful (gap =
top-N noise); mid percentile / low corr => composite structurally off (which factor/weight to fix)."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace" / "research" / "long_only_50cagr"))
sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")
import research_utils as ru  # noqa: E402
import guorn_verify_01_growth as H  # noqa: E402  (reuse _load / _composite_row / LISTED_BOUNDS / _in_universe)

XLSX = ROOT / "Knowledge" / "果仁回测结果" / "01_sm_01_成长动量.xlsx"


def _qc(code):
    s = str(code).split(".")[0].zfill(6)
    return s + ("_SH" if s[0] in "69" else "_SZ")


def main():
    f, ind, e = H._load()
    close_raw, amt = e["close_raw"], e["amt"]
    amt5 = amt.rolling(5, min_periods=1).mean(); amt20 = amt.rolling(20, min_periods=1).mean()
    hist = close_raw.notna().rolling(20, min_periods=1).sum()
    insts = close_raw.columns
    grid = close_raw.index

    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单", header=0)
    h["开始日期"] = pd.to_datetime(h["开始日期"]); h["qc"] = h["股票代码"].map(_qc)
    h["score"] = pd.to_numeric(h["总排名分"], errors="coerce")
    g_by_date = {d: grp for d, grp in h.groupby("开始日期")}
    g_dates = sorted(g_by_date)

    pctls, score_pairs, n = [], [], 0
    for d in g_dates[::5]:                                    # sample every 5th 果仁 rebalance day
        d = pd.Timestamp(d)
        pos = grid.searchsorted(d)
        if pos == 0:
            continue
        pday = grid[pos - 1]
        st = ru.st_codes_on(d)
        cr = close_raw.loc[pday]
        keep = cr.notna() & (cr >= 2.0) & (amt5.loc[pday] > 5000.0) & (amt20.loc[pday] > 5000.0) & (hist.loc[pday] >= 20)
        keep &= pd.Series([(H.LISTED_BOUNDS.get(c.upper()) is not None
                            and H.LISTED_BOUNDS[c.upper()][0] <= pday <= H.LISTED_BOUNDS[c.upper()][1]) for c in insts], index=insts)
        keep &= pd.Series([c.upper() not in st for c in insts], index=insts)
        keep &= e["debt_assets"].loc[pday].rank(pct=True) >= 0.10
        keep &= e["bias120"].loc[pday].rank(pct=True) >= 0.10
        elig = keep[keep].index
        if len(elig) < 50:
            continue
        comp = H._composite_row(f, ind, pday, elig).dropna()
        if comp.empty:
            continue
        comp_pct = comp.rank(pct=True)                        # my composite percentile (1.0 = my top pick)
        grp = g_by_date[d.normalize()] if d.normalize() in g_by_date else g_by_date[d]
        for _, r in grp.iterrows():
            qc = r["qc"]
            if qc in comp_pct.index:
                pctls.append(comp_pct[qc]); n += 1
                if pd.notna(r["score"]):
                    score_pairs.append((comp[qc], r["score"]))
    ar = np.array(pctls)
    print(f"=== #1 composite fidelity ({n} 果仁 held-name instances, sampled) ===")
    print(f"  果仁 held names' percentile in MY composite: median={np.median(ar):.3f} mean={ar.mean():.3f}")
    print(f"    frac in my top-10%: {np.mean(ar >= 0.90):.1%}   top-20%: {np.mean(ar >= 0.80):.1%}   "
          f"below my median: {np.mean(ar < 0.50):.1%}")
    if score_pairs:
        a = np.array(score_pairs)
        from scipy.stats import spearmanr
        rho = spearmanr(a[:, 0], a[:, 1]).correlation
        print(f"  corr(my composite, 果仁 总排名分) over held names: Spearman={rho:.3f}  (n={len(a)})")
    print("\n  INTERP: pctl>0.9 + high corr => composite faithful (gap=top-N noise). "
          "mid pctl / low corr => composite structurally off.")


if __name__ == "__main__":
    main()
