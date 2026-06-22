"""Is the rank discrepancy a 市值 DATA bug or a filter/universe difference?
For 果仁-held names that rank >11 in mine, compare 果仁's recorded 总市值/流通市值
(亿, from 各阶段持仓详单) vs my panel's total_mv/circ_mv on the same date."""
import sys
from pathlib import Path
import pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
import guorn_parity_rung1_purecap as G  # noqa: E402

h = pd.read_excel(ROOT / "Knowledge" / "果仁回测结果" / "11_sm_纯市值01.xlsx",
                  sheet_name="各阶段持仓详单", header=0)
h.columns = [str(c).strip() for c in h.columns]
h["code"] = h["股票代码"].astype(str).str.extract(r"(\d{6})")[0]
h["start"] = pd.to_datetime(h["开始日期"])
h = h.dropna(subset=["code"])

panel = pd.read_parquet(G.PANEL)
tmv = panel["total_mv"].unstack(level=0)   # datetime x instrument (万元)
cmv = panel["circ_mv"].unstack(level=0)
amt = panel["amount"].unstack(level=0)
cal_idx = tmv.index


def q(code6, date):
    # find the qlib instrument col matching the 6-digit code
    for suf in ("_SZ", "_SH"):
        c = code6 + suf
        if c in tmv.columns:
            pos = cal_idx.searchsorted(pd.Timestamp(date))
            pday = cal_idx[pos - 1]
            return (tmv.loc[pday, c], cmv.loc[pday, c], amt.loc[pday, c], c)
    return (None, None, None, "NOT_IN_PANEL")


for d in ["2015-07-02", "2015-01-05", "2015-11-02"]:
    rows = h[h["start"] == pd.Timestamp(d)]
    print(f"\n=== {d}  ({len(rows)} 果仁 holdings) — 果仁 市值(亿) vs mine(亿) ===")
    for _, r in rows.iterrows():
        g_tmv, g_cmv = r.get("总市值(亿)"), r.get("流通市值(亿)")
        m_tmv, m_cmv, m_amt, col = q(r["code"], d)
        mt = f"{m_tmv/1e4:.2f}" if m_tmv == m_tmv and m_tmv is not None else "NaN"
        mc = f"{m_cmv/1e4:.2f}" if m_cmv == m_cmv and m_cmv is not None else "NaN"
        amt_y = f"{m_amt/1e5:.3f}亿" if m_amt == m_amt and m_amt is not None else "NaN"
        print(f"  {r['code']} {str(r['股票名'])[:6]:6} 果仁 tmv={g_tmv}/cmv={g_cmv}  "
              f"| mine tmv={mt}/cmv={mc} amt5d? raw_amt={amt_y}  [{col}]")
