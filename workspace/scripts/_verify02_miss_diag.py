"""#2 sm_01_成长_v1 — SELECTION-miss diagnosis (NON-FORMAL parity diagnostic).

SCRIPT_STATUS: Class-B diagnostic (kept). The replay proved the engine path sound and the entire local-run
gap = SELECTION. This drills the misses: for each 果仁 holding-period start in the problem years, classify
each 果仁-held name against the LOCAL pipeline —
  OK          : in local composite top-25 (the sell band)
  RANK-MISS   : eligible but ranked >25 — then WHICH factor term drags it, and do our factor VALUES match
                果仁's own xlsx per-holding factor columns (value mismatch ⇒ data/PIT issue; match ⇒
                composite/tie-break/universe issue)?
  SCREEN-MISS : excluded by an eligibility screen — WHICH screen.
Mirrors guorn_verify_01_growth's build_schedule screens + _composite_row exactly (v1 canonical construction).
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace" / "research" / "long_only_50cagr"))
sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")

import research_utils as ru                                          # noqa: E402
import guorn_verify_01_growth as g1                                  # noqa: E402

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
XLSX = ROOT / "Knowledge" / "果仁回测结果" / "05_sm_01_成长_v1.xlsx"

WEIGHTS = {"mktcap_ind": (2, -1), "mktcap_x": (3, -1), "CoreProfitQGr": (1, +1),
           "EpsExclXorGr": (1, +1), "ROETTMDiff": (1, +1), "ILLIQ": (1, +1)}
YEARS = (2015, 2018, 2023)

# 果仁 xlsx per-holding factor column -> (our frame name, transform ours -> 果仁 unit)
XCOLS = {"CoreProfitQGr%PY": ("CoreProfitQGr", lambda v: v),
         "EpsExclXorQGr%PY": ("EpsExclXorGr", lambda v: v),
         "ROETTMDiffPQ": ("ROETTMDiff", lambda v: v),
         "总市值(亿)": ("mktcap_x", lambda v: v / 1e4)}


def main():
    g1.WEIGHTS = WEIGHTS
    g1.TOTAL_W = sum(w for w, _ in WEIGHTS.values())
    f, ind, e = g1._load()
    grid = e["close_raw"].index
    insts = e["close_raw"].columns
    inst_of = {}
    for c in insts:
        inst_of[str(c).split("_")[0]] = c

    amt5 = e["amt"].rolling(5, min_periods=1).mean()
    amt20 = e["amt"].rolling(20, min_periods=1).mean()
    hist = e["close_raw"].notna().rolling(20, min_periods=1).sum()
    bounds = g1.LISTED_BOUNDS

    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    h["c6"] = h["股票代码"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    h["start"] = pd.to_datetime(h["开始日期"], errors="coerce")
    h = h[h["start"].notna()]
    h["year"] = h["start"].dt.year
    h = h[h["year"].isin(YEARS)]

    rows = []
    for d, grp in h.groupby("start"):
        pos = grid.searchsorted(pd.Timestamp(d))
        if pos == 0 or pos >= len(grid) + 1:
            continue
        pday = grid[pos - 1]
        st = ru.st_codes_on(pd.Timestamp(d))
        cr = e["close_raw"].loc[pday]
        keep = pd.Series(True, index=insts)
        scr = {}
        scr["suspended/price<2"] = cr.notna() & (cr >= 2.0)
        scr["amt5"] = amt5.loc[pday] > 5000.0
        scr["amt20"] = amt20.loc[pday] > 5000.0
        scr["hist20"] = hist.loc[pday] >= 20
        listed = pd.Series([(bounds.get(str(c).upper()) is not None
                             and bounds[str(c).upper()][0] <= pday <= bounds[str(c).upper()][1]) for c in insts],
                           index=insts)
        scr["listed"] = listed
        scr["ST"] = pd.Series([str(c).upper() not in st for c in insts], index=insts)
        da = e["debt_assets"].loc[pday]
        bz = e["bias120"].loc[pday]
        scr["debt10%"] = da.rank(pct=True) >= 0.10
        scr["bias10%"] = bz.rank(pct=True) >= 0.10
        for m in scr.values():
            keep &= m.fillna(False) if m.dtype == object else m
        elig = keep[keep].index

        # per-factor scores on the eligible set (mirror _composite_row)
        indrow = ind.loc[pday].reindex(elig)
        N = len(elig)
        term_scores = {}
        comp = pd.Series(0.0, index=elig)
        for name, (w, dd) in WEIGHTS.items():
            row = f[name].loc[pday].reindex(elig)
            asc = (dd < 0)
            if name == "mktcap_ind":
                rnk = row.groupby(indrow).rank(method="min", ascending=asc, na_option="bottom")
                gN = indrow.map(indrow.value_counts())
                score = (gN - rnk + 1) / gN * 100.0
            else:
                rnk = row.rank(method="min", ascending=asc, na_option="bottom")
                score = (N - rnk + 1) / N * 100.0
            term_scores[name] = score
            comp = comp.add(score * w, fill_value=0.0)
        order = comp.sort_values(ascending=False)
        rank_of = pd.Series(np.arange(1, len(order) + 1), index=order.index)

        for _, r in grp.iterrows():
            c6 = r["c6"]
            inst = inst_of.get(c6)
            rec = dict(year=int(r["year"]), date=pd.Timestamp(d), code=c6, name=r.get("股票名"))
            if inst is None:
                rec.update(cls="NO-INST", detail="not in provider universe")
                rows.append(rec); continue
            if inst not in set(elig):
                fails = [k for k, m in scr.items() if not bool(pd.Series(m).get(inst, False))]
                rec.update(cls="SCREEN-MISS", detail=",".join(fails) or "?")
                rows.append(rec); continue
            rk = int(rank_of.get(inst, 10 ** 6))
            rec["rank"] = rk
            if rk <= 25:
                rec.update(cls="OK", detail="")
            else:
                drags = {n: float(term_scores[n].get(inst, np.nan)) for n in WEIGHTS}
                worst = min(drags, key=lambda k: drags[k] if np.isfinite(drags[k]) else 1e9)
                rec.update(cls="RANK-MISS", detail=f"worst={worst}({drags[worst]:.0f})")
                for n, v in drags.items():
                    rec[f"s_{n}"] = v
                for xc, (fn, tf) in XCOLS.items():
                    gv = pd.to_numeric(r.get(xc), errors="coerce")
                    ours = tf(float(f[fn].loc[pday].get(inst, np.nan)))
                    rec[f"g_{fn}"] = float(gv) if pd.notna(gv) else np.nan
                    rec[f"o_{fn}"] = ours
            rows.append(rec)

    df = pd.DataFrame(rows)
    df.to_parquet(OUT / "verify02_missdiag.parquet")
    print("=" * 84)
    for y in YEARS:
        sub = df[df.year == y]
        n = len(sub)
        cls = sub["cls"].value_counts()
        print(f"\n### {y}: held-name-periods={n}  " + "  ".join(f"{k}={v}({v/n*100:.0f}%)" for k, v in cls.items()))
        sm = sub[sub.cls == "SCREEN-MISS"]
        if len(sm):
            from collections import Counter
            cc = Counter()
            for dt in sm["detail"]:
                for t in str(dt).split(","):
                    cc[t] += 1
            print("   screen-miss by screen:", dict(cc.most_common(6)))
        rm = sub[sub.cls == "RANK-MISS"]
        if len(rm):
            from collections import Counter
            wc = Counter(str(x).split("=")[1].split("(")[0] for x in rm["detail"])
            print("   rank-miss worst-term:", dict(wc.most_common(6)))
            print(f"   rank-miss median rank: {rm['rank'].median():.0f}  p90: {rm['rank'].quantile(.9):.0f}")
            # factor-value agreement on rank-misses (ours vs 果仁 xlsx)
            for xc, (fn, _) in XCOLS.items():
                gv = rm[f"g_{fn}"]; ov = rm[f"o_{fn}"]
                m = pd.concat([gv, ov], axis=1).dropna()
                if len(m) < 5:
                    continue
                rele = (m.iloc[:, 1] - m.iloc[:, 0]).abs() / m.iloc[:, 0].abs().replace(0, np.nan)
                sgn = (np.sign(m.iloc[:, 0]) == np.sign(m.iloc[:, 1])).mean() * 100
                print(f"   value-agreement {fn:14} n={len(m)}  med|rel|={np.nanmedian(rele)*100:6.1f}%  sign={sgn:.0f}%")


if __name__ == "__main__":
    main()
