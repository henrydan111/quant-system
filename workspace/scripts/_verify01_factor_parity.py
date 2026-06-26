"""Diagnose the #1 undershoot: validate EACH of my factor computations against 果仁's OWN displayed
factor values in 01_*.xlsx 各阶段持仓详单 (34,466 holdings). 果仁 shows each factor as of the SIGNAL
date T-1 (rung-4 meta-finding), so compare my cached factor at the prev trading day vs 果仁's value.
A high per-factor rel-err / low corr / sign-flip localizes the mapping error driving the selection gap.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace" / "research" / "long_only_50cagr"))
sys.stdout.reconfigure(encoding="utf-8")
import research_utils as ru  # noqa: E402

CACHE = ROOT / "workspace" / "outputs" / "guorn_parity" / "verify01_cache"
XLSX = ROOT / "Knowledge" / "果仁回测结果" / "01_sm_01_成长动量.xlsx"
ON250 = ("公式(SUM(IF(当日涨停标记=1,0,LOG(后复权开盘价/REF(后复权收盘价,1))),250)"
         "-SUM(IF(当日涨停标记=1,0,LOG(后复权开盘价/REF(后复权收盘价,1))),20))")
ON120 = ON250.replace(",250)", ",120)")
COLMAP = {  # my cached frame -> 果仁 displayed column
    "mktcap_x": "总市值(亿)", "CoreProfitQGr": "CoreProfitQGr%PY", "EpsExclXorGr": "EpsExclXorQGr%PY",
    "ROETTMDiff": "ROETTMDiffPQ", "ILLIQ": "股价振幅%当日成交额10日", "onmom250": ON250, "onmom120": ON120,
    "forecast": "公式(业绩预告净利润QGr%PYQ_v1)",
}
ELIGMAP = {"debt_assets": "真实负债资产率", "bias120": "N日乖离率(120)"}
SCALE = {"mktcap_x": 1e-4}  # my $total_mv (万元) -> 果仁 亿


def _qcode(code):
    s = str(code).split(".")[0].zfill(6)
    return s + ("_SH" if s[0] in "69" else "_SZ")


def main():
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单", header=0)
    h["开始日期"] = pd.to_datetime(h["开始日期"])
    h["qc"] = h["股票代码"].map(_qcode)
    cal = ru.trading_calendar()
    # signal date = prev trading day of 开始日期
    pos = cal.searchsorted(h["开始日期"].values)
    h["pday"] = [cal[p - 1] if p > 0 else pd.NaT for p in pos]
    h = h.dropna(subset=["pday"])
    print(f"[parity] {len(h)} holdings, {h['开始日期'].dt.year.min()}..{h['开始日期'].dt.year.max()}", flush=True)

    frames = {**{k: CACHE / f"f_{k}.parquet" for k in COLMAP}, **{k: CACHE / f"e_{k}.parquet" for k in ELIGMAP}}
    allmap = {**COLMAP, **ELIGMAP}

    print(f"\n{'factor':14} {'果仁 col':12} {'n':>6} {'med_relerr':>10} {'sign%':>6} {'corr':>6}  note")
    print("-" * 86)
    for myname, gcol in allmap.items():
        if gcol not in h.columns:
            print(f"{myname:14} MISSING 果仁 col"); continue
        fr = pd.read_parquet(frames[myname])
        # gather mine at (pday, qc)
        sub = h[["pday", "qc", gcol]].dropna()
        sub = sub[sub["qc"].isin(fr.columns)]
        # vectorized lookup
        mine = []
        for pday, grp in sub.groupby("pday"):
            if pday not in fr.index:
                mine.append(pd.Series(np.nan, index=grp.index)); continue
            row = fr.loc[pday]
            mine.append(grp["qc"].map(row).set_axis(grp.index))
        sub = sub.assign(mine=pd.concat(mine))
        sub["mine"] = sub["mine"] * SCALE.get(myname, 1.0)
        sub["theirs"] = pd.to_numeric(sub[gcol], errors="coerce")
        ok = sub.dropna(subset=["mine", "theirs"])
        if ok.empty:
            print(f"{myname:14} {str(gcol)[:12]:12} {0:>6} no overlap"); continue
        rel = (ok["mine"] - ok["theirs"]).abs() / ok["theirs"].abs().clip(lower=1e-6)
        sign = (np.sign(ok["mine"]) == np.sign(ok["theirs"])).mean()
        corr = ok["mine"].corr(ok["theirs"])
        flag = "" if (rel.median() < 0.05 or corr > 0.95) else "  <-- CHECK"
        print(f"{myname:14} {str(gcol)[:12]:12} {len(ok):>6} {rel.median():>10.3f} {sign:>6.1%} {corr:>6.2f}{flag}", flush=True)


if __name__ == "__main__":
    main()
