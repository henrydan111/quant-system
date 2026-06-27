"""THOROUGH gap decomposition for the GARP/R&D cluster (#4/#15/#5): split LOCAL−果仁 into
EXECUTION vs SELECTION vs CONSTRUCTION via the campaign's replay method (rung-2 / #1).

Four legs, identical engine/cost/fill_mode/hold_on_limit_up/volume_limit — only NAMES + WEIGHTING differ:
  R_guorn  = 果仁's reported return (xlsx 年度收益统计, corrected float decimals)
  R_replay = 果仁's EXACT daily held names (各阶段持仓详单) through MY engine, equal-weight
  R_myew   = MY schedule top-N names, equal-weight (same engine)
  R_mine   = MY actual model-II result (verifyNN_result.json)

Decomposition (additive on CAGR, log-consistent enough for attribution):
  EXECUTION    = R_guorn  − R_replay   (果仁 holds the SAME names but fills them optimistically: 一字 limit-up
                                        buys my fill-price-aware gate refuses + no volume cap + better prices)
  SELECTION    = R_replay − R_myew     (果仁's name choice vs mine, at identical EW execution = the omission cost)
  CONSTRUCTION = R_myew   − R_mine      (EW vs my model-II band/cooldown/exits)

If R_replay ≈ R_guorn ⇒ engine/data/execution SOUND, gap is SELECTION. If R_replay ≪ R_guorn ⇒ EXECUTION
(fill optimism) dominates. Per-year tables localize WHERE each leg's gap concentrates (bull vs calm).

Usage:
  _guorn_gap_decompose.py --book 04 --leg replay   # run one leg (background-friendly)
  _guorn_gap_decompose.py --book 04 --leg myew
  _guorn_gap_decompose.py --book 04 --report        # print the 4-way decomposition from saved nets
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace" / "research" / "long_only_50cagr"))
sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")
import research_utils as ru                                            # noqa: E402
from guorn_parity_rung6_quality59 import EqualWeightScheduleStrategy   # noqa: E402

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
BOOKS = {
    "04": dict(xlsx="09_sm_GARP_illiq.xlsx", sched="verify04_schedule.json", result="verify04_result.json",
               topn=10, fill="open_close", label="#4 sm_GARP_illiq"),
    "15": dict(xlsx="44_成长_双创_GARP@周期_v2.xlsx", sched="verify15_schedule.json", result="verify15_result.json",
               topn=10, fill="jq_daily_avg", label="#15 成长_双创_GARP@周期"),
    "05": dict(xlsx="10_sm_双创研发强度_v1.xlsx", sched="verify05_schedule.json", result="verify05_result.json",
               topn=5, fill="open_close", label="#5 sm_双创研发强度"),
}


def _qc_dot(code):
    s = str(code).split(".")[0].zfill(6)
    return s + (".SH" if s[0] in "69" else ".SZ")


def _guorn_yearly(xlsx):
    df = pd.read_excel(ROOT / "Knowledge" / "果仁回测结果" / xlsx, sheet_name="年度收益统计", header=0)
    out = {}
    for _, r in df.iterrows():
        try:
            y = int(str(r.iloc[0])[:4])
        except Exception:
            continue
        v = pd.to_numeric(r.iloc[1], errors="coerce")
        if pd.notna(v):
            out[y] = float(v)   # CORRECTED: 果仁 stores DECIMALS, never /100
    return out


def _replay_sched(xlsx, start, end):
    h = pd.read_excel(ROOT / "Knowledge" / "果仁回测结果" / xlsx, sheet_name="各阶段持仓详单", header=0)
    h["开始日期"] = pd.to_datetime(h["开始日期"])
    h = h[(h["开始日期"] >= pd.Timestamp(start)) & (h["开始日期"] <= pd.Timestamp(end))]
    h["dot"] = h["股票代码"].map(_qc_dot)
    return {pd.Timestamp(d): sorted(set(grp["dot"])) for d, grp in h.groupby("开始日期")}


def _run(strat, fill, start, end):
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    cost = CostConfig(buy_commission=0.002, sell_commission=0.002, stamp_tax=0.0, min_commission=0.0, transfer_fee=0.0)
    bt = EventDrivenBacktester(data_dir=str(ROOT / "data"))
    res = bt.run(strategy=strat, start_time=start, end_time=end, benchmark="000300.SH", account=1_000_000.0,
                 exchange_config=cost, slippage=FixedSlippage(0.0), volume_limit=0.10, hold_on_limit_up=True,
                 fill_mode=fill,
                 preload_fields=["$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close", "$adj_factor",
                                 "$up_limit", "$down_limit"])
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    return rep["return"].astype(float)


def run_leg(book, leg, start, end):
    cfg = BOOKS[book]
    if leg == "replay":
        sched = _replay_sched(cfg["xlsx"], start, end)
        strat = EqualWeightScheduleStrategy(sched, n=40)
        avg_n = np.mean([len(v) for v in sched.values()])
        print(f"[{book}/replay] {len(sched)} days, avg {avg_n:.1f} 果仁 names; EW; fill={cfg['fill']}", flush=True)
    else:
        raw = json.loads((OUT / cfg["sched"]).read_text(encoding="utf-8"))
        sched = {pd.Timestamp(k): v[:cfg["topn"]] for k, v in raw.items() if v}
        strat = EqualWeightScheduleStrategy(sched, n=cfg["topn"])
        print(f"[{book}/myew] {len(sched)} days, my top{cfg['topn']} EW; fill={cfg['fill']}", flush=True)
    net = _run(strat, cfg["fill"], start, end)
    net.to_frame("net").to_parquet(OUT / f"verify{book}_{leg}_net.parquet")
    m = ru.goal_metrics(net)
    print(f"[{book}/{leg}] CAGR={m['cagr']:+.2%}  MDD={m['mdd']:+.2%}  vol={m['ann_vol']:.2%} -> saved", flush=True)


def _yr(net):
    net.index = pd.to_datetime(net.index)
    return net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)


def report(book):
    cfg = BOOKS[book]
    gy = _guorn_yearly(cfg["xlsx"])
    res = json.loads((OUT / cfg["result"]).read_text(encoding="utf-8"))
    mine_cagr = res["local"]["cagr"]
    mine_yr = {int(k): v for k, v in res["local_yearly"].items()}
    rep_net = pd.read_parquet(OUT / f"verify{book}_replay_net.parquet")["net"]
    myew_net = pd.read_parquet(OUT / f"verify{book}_myew_net.parquet")["net"]
    rep_m = ru.goal_metrics(rep_net); myew_m = ru.goal_metrics(myew_net)
    rep_yr, myew_yr = _yr(rep_net), _yr(myew_net)

    # geometric full-period CAGR for 果仁 (compound the yearly decimals over the comparable window)
    yrs = sorted(set(gy) & set(mine_yr))
    g_comp = np.prod([1 + gy[y] for y in yrs]) ** (1 / len(yrs)) - 1
    rep_comp = np.prod([1 + rep_yr.get(y, 0) for y in yrs]) ** (1 / len(yrs)) - 1
    myew_comp = np.prod([1 + myew_yr.get(y, 0) for y in yrs]) ** (1 / len(yrs)) - 1
    mine_comp = np.prod([1 + mine_yr.get(y, 0) for y in yrs]) ** (1 / len(yrs)) - 1

    print("\n" + "=" * 86)
    print(f"  {cfg['label']} — GAP DECOMPOSITION (replay method; {len(yrs)}y {yrs[0]}-{yrs[-1]}, geo-CAGR over common yrs)")
    print(f"  R_guorn  (果仁 reported)            = {g_comp:+.2%}")
    print(f"  R_replay (果仁 names, MY engine EW) = {rep_comp:+.2%}   [MDD {rep_m['mdd']:+.1%} vol {rep_m['ann_vol']:.1%}]")
    print(f"  R_myew   (MY names, EW)            = {myew_comp:+.2%}   [MDD {myew_m['mdd']:+.1%} vol {myew_m['ann_vol']:.1%}]")
    print(f"  R_mine   (MY model-II)             = {mine_comp:+.2%}")
    print(f"  -----------------------------------------------------------------")
    print(f"  EXECUTION    (guorn − replay)      = {g_comp - rep_comp:+.2%}   <- 果仁 fill optimism on SAME names")
    print(f"  SELECTION    (replay − myew)       = {rep_comp - myew_comp:+.2%}   <- 果仁 names vs mine (omission cost)")
    print(f"  CONSTRUCTION (myew − mine)         = {myew_comp - mine_comp:+.2%}   <- EW vs my model-II band")
    print(f"  total gap    (guorn − mine)        = {g_comp - mine_comp:+.2%}")
    verdict = "SELECTION-dominated" if (rep_comp - myew_comp) > (g_comp - rep_comp) else "EXECUTION-dominated"
    print(f"  ⇒ {verdict}  (replay {'≈' if abs(g_comp-rep_comp)<0.05 else '≪'} guorn: engine "
          f"{'SOUND' if abs(g_comp-rep_comp)<0.05 else 'shows execution gap'})")
    print("\n  year   R_guorn  R_replay  R_myew   R_mine | EXEC(g−rep) SEL(rep−my)")
    for y in yrs:
        g = gy[y]; rp = rep_yr.get(y, np.nan); mw = myew_yr.get(y, np.nan); mn = mine_yr.get(y, np.nan)
        print(f"  {y}  {g:+7.1%}  {rp:+7.1%}  {mw:+7.1%}  {mn:+7.1%} |  {g-rp:+7.1%}   {rp-mw:+7.1%}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", choices=sorted(BOOKS), required=True)
    ap.add_argument("--leg", choices=["replay", "myew"])
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--start", default="2014-01-01")
    ap.add_argument("--end", default="2026-02-27")
    args = ap.parse_args()
    if args.leg:
        run_leg(args.book, args.leg, args.start, args.end)
    if args.report:
        report(args.book)


if __name__ == "__main__":
    main()
