"""REPLAY decomposition for #2 sm_01_成长_v1 (nn=5, xlsx 05) — 果仁's ACTUAL holdings through the LOCAL engine.

SCRIPT_STATUS: Class-B parity diagnostic (kept). Purpose: split the corrected yearly residual (2015 −86pp,
2018 −30pp, 2023 −41pp, 2025 −42pp vs 果仁) into SELECTION vs EXECUTION/data-path, per the guorn-verification
skill's gap discipline: replay ≈ 果仁 ⇒ local SELECTION is the dominant residual; replay gap ⇒ the
execution/weights/cost/fill/CA path is unlocalized.

Upgrade over the rung-2 template (_replay_guorn_holdings.py): WEIGHT-FAITHFUL — the 各阶段持仓详单 carries
本期起始仓位 (the observed segment start weight), so targets use 果仁's actual weights (renormalized), not the
equal-weight approximation. --weights equal reproduces the template behavior for sensitivity.

Cost = the book's 果仁 default 千分之二 (0.2%/side), slippage 0, open fill (09:35 replica), total return.
NON-FORMAL parity artifact; not sealed/deployable.
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace" / "research" / "long_only_50cagr"))
sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")

import research_utils as ru                                          # noqa: E402
from src.backtest_engine.event_driven.strategies import Strategy     # noqa: E402

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
XLSX = ROOT / "Knowledge" / "果仁回测结果" / "05_sm_01_成长_v1.xlsx"
GR_YEARLY_SHEET = "年度收益统计"


def _code(c6: str) -> str:
    return f"{c6}.SH" if c6.startswith(("6",)) else f"{c6}.SZ"


def build_schedule(start, end, mode="observed"):
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    h["c6"] = h["股票代码"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    h["code"] = h["c6"].map(_code)
    h["s"] = pd.to_datetime(h["开始日期"], errors="coerce")
    h["e"] = pd.to_datetime(h["结束日期"], errors="coerce")
    h["w0"] = pd.to_numeric(h["本期起始仓位"], errors="coerce")
    h = h.dropna(subset=["s", "e"])
    cal = ru.trading_calendar()
    cal = cal[(cal >= pd.Timestamp(start)) & (cal <= pd.Timestamp(end))]
    sv = h["s"].to_numpy().astype("datetime64[D]")
    ev = h["e"].to_numpy().astype("datetime64[D]")
    codes = h["code"].to_numpy()
    w0 = h["w0"].fillna(0.10).to_numpy()
    sched = {}
    for d in cal:
        dd = np.datetime64(d, "D")
        m = (sv <= dd) & (ev >= dd)
        if not m.any():
            sched[d] = {}
            continue
        cs, ws = codes[m], w0[m]
        agg = {}
        for c, w in zip(cs, ws):
            agg[c] = agg.get(c, 0.0) + float(w)
        if mode == "equal" or sum(agg.values()) <= 0:
            n = len(agg)
            sched[d] = {c: 0.98 / n for c in agg}
        else:
            tot = sum(agg.values())
            sched[d] = {c: w / tot * 0.98 for c, w in agg.items()}     # observed weights, renormalized to 98% invested
    return sched


class FollowWeights(Strategy):
    def __init__(self, schedule):
        super().__init__()
        self.schedule = {pd.Timestamp(d): dict(v) for d, v in schedule.items()}

    def initialize(self, context): return None
    def on_bar(self, context): return []
    def after_market_close(self, context): return None

    def before_market_open(self, context):
        from src.backtest_engine.event_driven.strategies import _emit_rebalance_orders
        tgt = self.schedule.get(pd.Timestamp(context.date), {})
        return _emit_rebalance_orders(tgt, context)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2014-01-01")
    ap.add_argument("--end", default="2026-02-27")
    ap.add_argument("--weights", choices=["observed", "equal"], default="observed")
    a = ap.parse_args()

    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    sched = build_schedule(a.start, a.end, a.weights)
    nonempty = sum(1 for v in sched.values() if v)
    nmean = np.mean([len(v) for v in sched.values() if v])
    print(f"[replay05] schedule: {nonempty} days, mean {nmean:.2f} names/day, weights={a.weights}", flush=True)

    strat = FollowWeights(sched)
    cost = CostConfig(buy_commission=0.002, sell_commission=0.002, stamp_tax=0.0,
                      min_commission=0.0, transfer_fee=0.0)
    bt = EventDrivenBacktester(data_dir=str(ROOT / "data"))
    res = bt.run(strategy=strat, start_time=a.start, end_time=a.end, benchmark="000300.SH",
                 account=1_000_000.0, exchange_config=cost, slippage=FixedSlippage(0.0),
                 volume_limit=0.10,
                 preload_fields=["$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close",
                                 "$adj_factor", "$up_limit", "$down_limit"])
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    net = rep["return"].astype(float)
    tag = "obs" if a.weights == "observed" else "eq"
    net.to_frame("net").to_parquet(OUT / f"verify02_replay_{tag}_net.parquet")
    m = ru.goal_metrics(net)
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)

    gdf = pd.read_excel(XLSX, sheet_name=GR_YEARLY_SHEET, header=0)
    gy = {}
    for _, r in gdf.iterrows():
        try:
            y = int(str(r.iloc[0])[:4])
        except Exception:
            continue
        v = pd.to_numeric(r.iloc[1], errors="coerce")
        if pd.notna(v):
            gy[y] = float(v)

    print("\n" + "=" * 78)
    print(f"  #2 REPLAY ({a.weights} weights, 0.2%/side)  CAGR={m['cagr']:+.2%}  MDD={m['mdd']:+.2%}")
    print("  year    REPLAY     果仁      diff    (≈0 ⇒ engine/data path sound; local-run gap ⇒ SELECTION)")
    for y in sorted(yr.index):
        g = gy.get(int(y))
        gt = f"{g:+8.1%}" if g is not None else "   n/a "
        dt = f"{float(yr[y]) - g:+7.1%}" if g is not None else ""
        print(f"  {int(y)}  {float(yr[y]):+8.1%}  {gt}  {dt}")
    for pc in ("n_positions", "cash"):
        if pc in rep.columns:
            print(f"  [report] {pc}: mean={pd.to_numeric(rep[pc], errors='coerce').mean():.2f}")


if __name__ == "__main__":
    main()
