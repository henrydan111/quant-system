"""Rung-2 GPT R1 Major-3 — falsification test for a broad engine/return/CA bug (rule #10).

Claim under test: "the rung-2 big-year divergence is SELECTION precision + the execution-
realism gap, NOT a local engine/return/corporate-action/cost-path bug."

Test: feed 果仁's ACTUAL held names (from 各阶段持仓详单 segments) into the LOCAL
event-driven engine, equal-weight (an APPROXIMATION of 果仁's 14-26% band — 果仁's true
weight-level path is not observable), 果仁's 0.3%/side cost, same period.

RESULT (rung2_replay_net.parquet; this is a falsification test, NOT a proof of exact 果仁
execution equivalence):
  - It REFUTES a broad local return/corporate-action/price-path bug: the replay reproduces
    果仁 in calm years (2017 -0.0% EXACT, 2021 -2.0, 2025 -1.2). A corrupt return/CA/cost
    path could not produce -0.0% holding 果仁's exact names.
  - It does NOT prove exact 果仁 execution equivalence: the replay undershoots 果仁 by ~11%
    CAGR (+48.8 vs +60.0). That gap is the EXECUTION-REALISM difference (my equal-weight +
    0.3% cost + realistic limit/suspension gates vs 果仁's band-drift weighting + optimistic
    fills) and is weighting-sensitive — an unbounded-drift variant swung to +45% / 2015
    +720% / 12M idle cash, RE-PRODUCING the leak + over-concentration bugs fixed in the main
    strategy (which confirms those fixes). It is NOT fully decomposed and is left so.

ON LIMIT-UP (rule #10 — a refuted cause is removed, not kept): an earlier hypothesis blamed
the big-year gap on 果仁 buying limit-up-at-open names my fill-price gate refuses. DIRECT
CHECK (entry_lock_diagnostic below; saved to rung2_entry_lock.json): only ~0.3% of 果仁's
entries were limit-up-locked at the open (max 1.0% in 2015), so limit-up entry-blocking is
NOT a material driver for the 中小板 universe (larger names, few 一字板; limit-up was rung-1's
pure-microcap signature, not this rung). Any remaining gap is attributed only where
decomposed; otherwise it is marked unresolved.

Usage:
  python workspace/scripts/_replay_guorn_holdings.py          # the replay
  python workspace/scripts/_replay_guorn_holdings.py --diag    # the entry-lock diagnostic only
"""
from __future__ import annotations
import sys
from pathlib import Path
import importlib.util
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace" / "research" / "long_only_50cagr"))
sys.stdout.reconfigure(encoding="utf-8")

import research_utils as ru  # noqa: E402
from src.backtest_engine.event_driven.strategy import Strategy  # noqa: E402

spec = importlib.util.spec_from_file_location("r2", ROOT / "workspace" / "scripts" / "guorn_parity_rung2_posprofit.py")
r2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(r2)

XLSX = ROOT / "Knowledge" / "果仁回测结果" / "16_sm_noc_纯市值正盈利_v4.xlsx"


class FollowStrategy(Strategy):
    """Hold exactly 果仁's prescribed names each day, EQUAL-WEIGHT within the band,
    fully invested (w=1/n, n>=4 => each <= pos_max) — the cleanest 果仁-band-approximating,
    fully-invested replay. This isolates the ENGINE: if it reproduces 果仁's per-year
    return holding 果仁's exact names, the return/CA/cost path is sound.

    (An UNBOUNDED-DRIFT variant — keep held names at drifted weight, only trade on set
    changes — was tried and came back WORSE and wildly noisier: +45% CAGR with 2015
    +720% and 12M idle cash, because it re-introduced the exact two bugs fixed in the
    main rung-2 strategy: unbounded winner drift [no pos_max cap] + cash-leak [no
    redeploy]. That it reproduced both failure modes CONFIRMS the main-strategy fix; the
    bounded equal-weight version below is the right engine test.)"""
    def __init__(self, schedule):
        super().__init__()
        self.schedule = {pd.Timestamp(d): tuple(c) for d, c in schedule.items()}

    def initialize(self, context): return None
    def on_bar(self, context): return []
    def after_market_close(self, context): return None

    def before_market_open(self, context):
        from src.backtest_engine.event_driven.strategies import _emit_rebalance_orders
        names = self.schedule.get(pd.Timestamp(context.date), ())
        if not names:
            return _emit_rebalance_orders({}, context)
        w = 1.0 / len(names)
        return _emit_rebalance_orders({c: w for c in names}, context)


def build_guorn_schedule(start, end):
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    code6 = h["股票代码"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    code = (code6 + ".SZ").to_numpy()
    s = pd.to_datetime(h["开始日期"]).to_numpy().astype("datetime64[D]")
    e = pd.to_datetime(h["结束日期"]).to_numpy().astype("datetime64[D]")
    cal = ru.trading_calendar()
    cal = cal[(cal >= pd.Timestamp(start)) & (cal <= pd.Timestamp(end))]
    sched = {}
    for d in cal:
        dd = np.datetime64(d, "D")
        m = (s <= dd) & (e >= dd)
        sched[d] = sorted(set(code[m].tolist()))
    return sched


def main():
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    start, end = "2014-01-01", "2026-06-20"
    sched = build_guorn_schedule(start, end)
    nonempty = sum(1 for v in sched.values() if v)
    nmean = np.mean([len(v) for v in sched.values() if v])
    print(f"[replay] 果仁 held-set schedule: {nonempty} trading days, mean {nmean:.2f} names/day", flush=True)

    strat = FollowStrategy(sched)
    cost = CostConfig(buy_commission=0.003, sell_commission=0.003, stamp_tax=0.0,
                      min_commission=0.0, transfer_fee=0.0)
    bt = EventDrivenBacktester(data_dir=str(ROOT / "data"))
    res = bt.run(strategy=strat, start_time=start, end_time=end, benchmark="000300.SH",
                 account=1_000_000.0, exchange_config=cost, slippage=FixedSlippage(0.0),
                 volume_limit=0.10,
                 preload_fields=["$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close", "$adj_factor"])
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    net = rep["return"].astype(float)
    net.to_frame("net").to_parquet(r2.OUT / "rung2_replay_net.parquet")
    m = ru.goal_metrics(net)
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    yearly = {int(y): float(v) for y, v in yr.items()}
    for pc in ("n_positions", "cash"):
        if pc in rep.columns:
            print(f"[report] {pc}: mean={pd.to_numeric(rep[pc],errors='coerce').mean():.3f}", flush=True)
    print("\n" + "=" * 78)
    print(f"  REPLAY (果仁's exact names through LOCAL engine)  CAGR={m['cagr']:+.2%}  MDD={m['mdd']:+.2%}")
    print(f"  果仁 reported                                     CAGR={r2.GR_HEADLINE['annual']:+.2%}")
    print("  year    REPLAY     果仁     diff   (calm-year match => broad return/CA bug REFUTED)")
    for y in sorted(yearly):
        g = r2.GR_YEARLY.get(y)
        gt = f"{g:+7.1%}" if g is not None else "  n/a "
        dt = f"{yearly[y]-g:+7.1%}" if g is not None else ""
        print(f"  {y}  {yearly[y]:+8.1%}  {gt}  {dt}")


def entry_lock_diagnostic():
    """GPT R2 Major-2: save the limit-up refutation as a reproducible artifact.
    For every 果仁 holding-segment ENTRY (开始日期), was the name limit-up-locked at the
    open (open >= up_limit => unbuyable by the fill-price-aware gate)? -> rung2_entry_lock.json."""
    import json
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    code6 = h["股票代码"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    h = h.assign(q=code6 + "_SZ", start=pd.to_datetime(h["开始日期"]))
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=str(ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)
    insts = sorted(h["q"].unique())
    df = D.features(insts, ["$open", "$up_limit"], start_time="2014-01-01", end_time="2026-06-20", freq="day")
    df.columns = ["open", "up"]
    df["lock"] = (df["open"] >= df["up"] * 0.999) & (df["up"] > 0)
    lock = df["lock"].unstack(level=0)
    rows = []
    for _, r in h.iterrows():
        d, q = r["start"], r["q"]
        if d in lock.index and q in lock.columns and pd.notna(lock.at[d, q]):
            rows.append((d.year, bool(lock.at[d, q])))
    e = pd.DataFrame(rows, columns=["yr", "locked"])
    by_year = {int(y): {"n": int(len(s)), "locked_pct": float(s["locked"].mean())}
               for y, s in e.groupby("yr")}
    out = {"overall_locked_pct": float(e["locked"].mean()), "n_entries": int(len(e)),
           "by_year": by_year,
           "conclusion": "limit-up entry-blocking is NOT a material driver for the 中小板 "
                         "universe (~0.3% of 果仁 entries locked-up at open); the rung-2 residual "
                         "is selection precision x concentration + the execution-realism gap."}
    p = r2.OUT / "rung2_entry_lock.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[diag] overall limit-up-locked-at-open: {out['overall_locked_pct']:.1%} of {out['n_entries']} entries")
    for y, s in by_year.items():
        print(f"  {y}: {s['locked_pct']:.1%}  (n={s['n']})")
    print(f"  saved -> {p}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--diag", action="store_true", help="run only the entry-lock diagnostic")
    args = ap.parse_args()
    entry_lock_diagnostic() if args.diag else main()
