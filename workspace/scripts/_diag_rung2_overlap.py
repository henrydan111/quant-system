"""Diagnostic: does the rung-2 SELECTION match 果仁's ACTUAL holdings?
Reconstruct 果仁's held set on probe dates (from 各阶段持仓详单 开始/结束日期 segments)
and compare to my schedule's top candidates + my actual backtest holdings. Localizes
whether the 2018 gap is SELECTION (universe/gate/rank) or EXECUTION (exits/model-II).
"""
from __future__ import annotations
import sys
from pathlib import Path
import importlib.util
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace" / "research" / "long_only_50cagr"))
sys.path.insert(0, str(ROOT / "workspace" / "research" / "jq_replication"))
sys.stdout.reconfigure(encoding="utf-8")

spec = importlib.util.spec_from_file_location("r2", ROOT / "workspace" / "scripts" / "guorn_parity_rung2_posprofit.py")
r2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(r2)

XLSX = ROOT / "Knowledge" / "果仁回测结果" / "16_sm_noc_纯市值正盈利_v4.xlsx"


def guorn_held_on(h, d):
    seg = h[(h["start"] <= d) & (h["end"] >= d)]
    return set(seg["code"])


def main():
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    code6 = h["股票代码"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    h = h.assign(code=code6 + ".SZ", start=pd.to_datetime(h["开始日期"]), end=pd.to_datetime(h["结束日期"]))

    panel = pd.read_parquet(r2.PANEL); profit = pd.read_parquet(r2.GATE)
    rebal = r2._rebal_dates("2018-01-01", "2018-12-31", "daily")
    sched, _ = r2.build_schedule(panel, profit, rebal)
    # my actual backtest holdings (from the exits-on smoke run), if present
    myh = None
    p = r2.OUT / "rung2_holdings_exits.parquet"
    if p.exists():
        myh = pd.read_parquet(p)
        print("my-holdings cols:", list(myh.columns)[:8], "shape", myh.shape)

    # probe ~ month-end trading days
    probes = [d for d in sorted(sched) if sched[d]]
    probes = probes[:: max(1, len(probes) // 12)][:12]
    print(f"\n{'date':12} {'果仁N':>5} {'sched_ov':>8} {'in_univ':>7} {'gate_drop':>9}  missing_reasons")
    close_raw = panel["close"].unstack(level=0)
    tmv = panel["total_mv"].unstack(level=0)
    prof = profit.reindex(close_raw.index).ffill()
    for d in probes:
        gset = guorn_held_on(h, d)
        if not gset:
            continue
        mytop = set(sched[d][:8])
        ov = len(gset & mytop)
        # for 果仁 names NOT in my top-8, why?  (universe / gate / rank / data)
        pos = close_raw.index.searchsorted(d) - 1
        pday = close_raw.index[pos]
        reasons = {"not_univ": 0, "no_data": 0, "np<=0": 0, "ranked_lower": 0}
        for c in gset - mytop:
            q = c.replace(".", "_")
            if q.split("_")[0][:3] not in r2.UNIVERSE_PREFIXES:
                reasons["not_univ"] += 1
            elif q not in close_raw.columns or pd.isna(close_raw.at[pday, q]):
                reasons["no_data"] += 1
            elif pd.isna(prof.at[pday, q]) or prof.at[pday, q] <= 0:
                reasons["np<=0"] += 1
            else:
                reasons["ranked_lower"] += 1
        in_univ = sum(1 for c in gset if c.replace(".", "_").split("_")[0][:3] in r2.UNIVERSE_PREFIXES)
        rtxt = " ".join(f"{k}={v}" for k, v in reasons.items() if v)
        print(f"{str(d.date()):12} {len(gset):5} {ov:8} {in_univ:7} {'':9}  {rtxt}")


if __name__ == "__main__":
    main()
