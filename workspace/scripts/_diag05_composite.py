"""Confirm #5's lower overlap (21.4% top-10) is OMISSION-driven, not a construction bug: where does my
#5 composite rank 果仁's actual held names? (rule #10 — same check that cleared #4.) High percentile ⇒ the
kept R&D/quality factors agree with 果仁; the gap is the omitted w=2 RnDTTMGr%PY + rating/holding terms.

Run: venv/Scripts/python.exe workspace/scripts/_diag05_composite.py
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
import research_utils as ru                                              # noqa: E402
from guorn_verify_05_rnd import _load, _composite_row, LISTED_BOUNDS, SHUANGCHUANG  # noqa: E402

XLSX = ROOT / "Knowledge" / "果仁回测结果" / "10_sm_双创研发强度_v1.xlsx"


def _qc(code):
    s = str(code).split(".")[0].zfill(6)
    return s + ("_SH" if s[0] in "69" else "_SZ")


def main():
    f, e = _load()
    close_raw = e["close_raw"]
    insts = close_raw.columns
    grid = close_raw.index
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单", header=0)
    h["开始日期"] = pd.to_datetime(h["开始日期"]); h["qc"] = h["股票代码"].map(_qc)
    g_by_date = {d: list(grp["qc"]) for d, grp in h.groupby("开始日期")}
    sample, seen = [], set()
    for d in sorted(g_by_date):
        k = (d.year, d.month)
        if k not in seen:
            seen.add(k); sample.append(d)

    in_uni, n_held, comp_pcts = 0, 0, []
    for d in sample:
        held = g_by_date[d]; n_held += len(held)
        for c in held:
            if c.split("_")[0][:3] in SHUANGCHUANG:
                in_uni += 1
        pos = grid.searchsorted(pd.Timestamp(d))
        if pos == 0:
            continue
        pday = grid[pos - 1]
        cr = close_raw.loc[pday]
        elig = [c for c in insts if c.split("_")[0][:3] in SHUANGCHUANG
                and pd.notna(cr.get(c)) and cr.get(c) >= 2.0
                and LISTED_BOUNDS.get(c.upper()) is not None
                and LISTED_BOUNDS[c.upper()][0] <= pday <= LISTED_BOUNDS[c.upper()][1]]
        elig = pd.Index(elig)
        comp = _composite_row(f, pday, elig)
        cpct = comp.rank(pct=True)
        for c in held:
            if c in cpct.index and pd.notna(cpct[c]):
                comp_pcts.append(float(cpct[c]))
    cp = np.array(comp_pcts)
    print(f"=== #5 diagnosis on {len(sample)} monthly 果仁 dates, {n_held} held-rows ===")
    print(f"UNIVERSE: 果仁 holds in 双创 (300/301/688/689) = {in_uni/n_held:.1%}")
    print(f"MY #5 COMPOSITE percentile of 果仁's held names: n={len(cp)} mean={cp.mean():.3f} "
          f"median={np.median(cp):.3f} frac>0.9={np.mean(cp>0.9):.1%} frac>0.8={np.mean(cp>0.8):.1%}")
    print("⇒ mean≫0.5 ⇒ composite faithful (gap = omitted w=2 RnDTTMGr + rating/holding); mean≈0.5 ⇒ bug")


if __name__ == "__main__":
    main()
