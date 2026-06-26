"""Decisive engine-vs-selection test for #1 (rung-2 replay method): feed 果仁's EXACT daily held names
through MY EventDrivenBacktester (equal-weight, daily, 0.2%/side). If the replay ≈ 果仁 -> engine sound,
the #1 gap is selection; if the replay UNDERSHOOTS 果仁 -> execution-realism gap (turnover cost + limit-up
fills 果仁 takes but the realistic engine can't + winner rotation). Isolates execution from selection."""
import sys
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
XLSX = ROOT / "Knowledge" / "果仁回测结果" / "01_sm_01_成长动量.xlsx"
GR = dict(annual=0.5721, sharpe=1.68, mdd=0.4787, vol=0.3168)


def _qc_dot(code):
    s = str(code).split(".")[0].zfill(6)
    return s + (".SH" if s[0] in "69" else ".SZ")


def _read_guorn_yearly():
    df = pd.read_excel(XLSX, sheet_name="年度收益统计", header=0)
    out = {}
    for _, r in df.iterrows():
        try:
            y = int(str(r.iloc[0])[:4])
        except Exception:
            continue
        v = pd.to_numeric(r.iloc[1], errors="coerce")
        if pd.notna(v):
            out[y] = float(v) / (100.0 if abs(v) > 3 else 1.0)
    return out


def main(start="2014-01-01", end="2026-02-27"):
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单", header=0)
    h["开始日期"] = pd.to_datetime(h["开始日期"])
    h = h[(h["开始日期"] >= pd.Timestamp(start)) & (h["开始日期"] <= pd.Timestamp(end))]
    h["dot"] = h["股票代码"].map(_qc_dot)
    sched = {pd.Timestamp(d): sorted(set(grp["dot"])) for d, grp in h.groupby("开始日期")}
    avg_n = np.mean([len(v) for v in sched.values()])
    print(f"[replay] {len(sched)} days, avg {avg_n:.1f} 果仁 held names; EW daily, 0.2%/side", flush=True)

    strat = EqualWeightScheduleStrategy(sched, n=40)        # EW to ALL 果仁 held names that day
    cost = CostConfig(buy_commission=0.002, sell_commission=0.002, stamp_tax=0.0, min_commission=0.0, transfer_fee=0.0)
    bt = EventDrivenBacktester(data_dir=str(ROOT / "data"))
    res = bt.run(strategy=strat, start_time=start, end_time=end, benchmark="000300.SH", account=1_000_000.0,
                 exchange_config=cost, slippage=FixedSlippage(0.0), volume_limit=0.10,
                 preload_fields=["$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close", "$adj_factor"])
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    net = rep["return"].astype(float)
    net.to_frame("net").to_parquet(OUT / "verify01_replay_net.parquet")
    m = ru.goal_metrics(net); m["sharpe_rf4"] = ru.sharpe(net, rf=0.04)
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    gy = _read_guorn_yearly()
    print("\n" + "=" * 70)
    print("  #1 REPLAY (果仁's exact names through MY engine, EW 0.2%) vs 果仁")
    print(f"  REPLAY annual≈{m['cagr']:+.2%}  Sharpe(rf4%)={m['sharpe_rf4']:.2f}  MDD={m['mdd']:+.2%}  vol={m['ann_vol']:.2%}")
    print(f"  果仁   annual={GR['annual']:+.2%}  Sharpe={GR['sharpe']:.2f}  MDD={-GR['mdd']:+.2%}  vol={GR['vol']:.2%}")
    print("  year    REPLAY    果仁     diff")
    for y in sorted(yr.index):
        g = gy.get(int(y)); gtxt = f"{g:+7.1%}" if g is not None else "   n/a "
        print(f"  {int(y)}   {yr[y]:+8.1%}  {gtxt}  {(f'{yr[y]-g:+7.1%}') if g is not None else ''}")
    print("\n  INTERP: replay≈果仁 => engine sound, #1 gap is selection. replay<<果仁 => execution-realism gap.")


if __name__ == "__main__":
    main()
