"""Diagnose #4 sm_GARP_illiq's low (9.7%) selection overlap: is it omission-driven or a construction bug?

Checks, on a monthly sample of 果仁's actual #4 holdings (各阶段持仓详单):
  (1) UNIVERSE — what fraction of 果仁's held names fall in my universe (main+中小板+创业板, excl 科创板/北证)?
      A low fraction ⇒ universe mis-spec (e.g. 果仁 holds 科创板).
  (2) ILLIQ(5) DIRECTION — the percentile of 果仁's held names' ILLIQ(5) in my pre-ILLIQ eligible set.
      If 果仁 holds predominantly HIGH-ILLIQ names (>0.65), my "keep most-liquid 0-65%" filter is BACKWARDS
      (the book name "illiq" suggests it TARGETS illiquidity) → it excludes exactly 果仁's picks.
  (3) COMPOSITE percentile of 果仁's held names in my full composite (do my factors at least RANK them high?).

NON-FORMAL diagnostic. Run: venv/Scripts/python.exe workspace/scripts/_diag04_overlap.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace" / "research" / "long_only_50cagr"))
sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")
import research_utils as ru                                              # noqa: E402
from guorn_verify_04_garp import (_load, composite_row, LISTED_BOUNDS, WEIGHTS, TOTAL_W,  # noqa: E402
                                  MAIN4_PREFIXES, BUILD_PREFIXES)

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
XLSX = ROOT / "Knowledge" / "果仁回测结果" / "09_sm_GARP_illiq.xlsx"


def _qc(code):
    s = str(code).split(".")[0].zfill(6)
    return s + ("_SH" if s[0] in "69" else "_SZ")


def main():
    f, ind, e = _load(WEIGHTS)
    close_raw, illiq5 = e["close_raw"], e["illiq5"]
    insts = close_raw.columns
    grid = close_raw.index

    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单", header=0)
    h["开始日期"] = pd.to_datetime(h["开始日期"]); h["qc"] = h["股票代码"].map(_qc)
    g_by_date = {d: list(grp["qc"]) for d, grp in h.groupby("开始日期")}
    # monthly sample
    all_dates = sorted(g_by_date)
    sample = []
    seen = set()
    for d in all_dates:
        k = (d.year, d.month)
        if k not in seen:
            seen.add(k); sample.append(d)

    in_build, in_main4, illiq_pcts, comp_pcts, n_held = 0, 0, [], [], 0
    sci_count = 0
    for d in sample:
        held = g_by_date[d]
        n_held += len(held)
        for c in held:
            pre = c.split("_")[0][:3]
            if pre in BUILD_PREFIXES:
                in_build += 1
            if pre in MAIN4_PREFIXES:
                in_main4 += 1
            if pre in ("688", "689"):
                sci_count += 1
        pos = grid.searchsorted(pd.Timestamp(d))
        if pos == 0:
            continue
        pday = grid[pos - 1]
        # pre-ILLIQ eligible set = main4 ∩ priced≥2 ∩ listed (mirror the schedule, minus ILLIQ + ST for speed)
        cr = close_raw.loc[pday]
        elig = [c for c in insts if c.split("_")[0][:3] in MAIN4_PREFIXES
                and pd.notna(cr.get(c)) and cr.get(c) >= 2.0
                and LISTED_BOUNDS.get(c.upper()) is not None
                and LISTED_BOUNDS[c.upper()][0] <= pday <= LISTED_BOUNDS[c.upper()][1]]
        elig = pd.Index(elig)
        il = illiq5.loc[pday].reindex(elig)
        il_pct = il.rank(pct=True)                      # ascending: small ILLIQ (liquid) -> low pct
        comp = composite_row(f, ind, pday, elig, WEIGHTS, TOTAL_W)
        comp_pct = comp.rank(pct=True)                  # high comp -> high pct (my "best")
        for c in held:
            if c in il_pct.index and pd.notna(il_pct[c]):
                illiq_pcts.append(float(il_pct[c]))
            if c in comp_pct.index and pd.notna(comp_pct[c]):
                comp_pcts.append(float(comp_pct[c]))

    print(f"=== #4 diagnosis on {len(sample)} monthly 果仁 holding-dates, {n_held} held-name rows ===\n")
    print(f"(1) UNIVERSE: 果仁 holds in my BUILD universe (main+中小+创业+科创) = {in_build/n_held:.1%}")
    print(f"             in my #4 MASK universe (main+中小+创业, EXCL 科创板)   = {in_main4/n_held:.1%}")
    print(f"             科创板 (688/689) held by 果仁                          = {sci_count/n_held:.1%}")
    print(f"             ⇒ if 科创板 frac is large, my exclusion is WRONG for #4\n")
    ip = np.array(illiq_pcts)
    print(f"(2) ILLIQ(5) percentile of 果仁's held names (ascending: 0=most liquid, 1=most illiquid):")
    print(f"      n={len(ip)}  mean={ip.mean():.3f}  median={np.median(ip):.3f}  "
          f"frac>0.65={np.mean(ip>0.65):.1%}  frac<0.35={np.mean(ip<0.35):.1%}")
    print(f"      ⇒ mean≫0.5 / frac>0.65 high ⇒ 果仁 holds ILLIQUID names ⇒ keep 0-65% should be DESCENDING")
    print(f"      ⇒ mean≈low ⇒ 果仁 holds liquid names ⇒ my ascending 'keep most-liquid 65%' is correct\n")
    cp = np.array(comp_pcts)
    print(f"(3) MY COMPOSITE percentile of 果仁's held names (1=my top):")
    print(f"      n={len(cp)}  mean={cp.mean():.3f}  median={np.median(cp):.3f}  "
          f"frac>0.9={np.mean(cp>0.9):.1%}  frac>0.8={np.mean(cp>0.8):.1%}")
    print(f"      ⇒ mean≫0.5 ⇒ composite agrees directionally (gap = fine-ordering/omission); "
          f"mean≈0.5 ⇒ construction problem")


if __name__ == "__main__":
    main()
