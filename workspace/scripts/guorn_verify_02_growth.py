"""果仁 deployed-20 verification — strategy #2: sm_01_成长_v1 (nn=5).

Second of the 成长 cluster. 果仁 = trusted benchmark; the LOCAL construction layer is under test.

Recipe (deployed_20_recipes.md #2): the universe + 8 eligibility filters are BYTE-IDENTICAL to #1
(全部股票 − ST − 科创板, 过滤停牌; 收盘价≥2 · 上市>20 · 5d&20d 成交额>0.05亿 · 真实负债资产率 & 乖离率120
rank≥10%). rankings(7):
  总市值 w2 一级行业内 ↓small  +  总市值 w3 全部 ↓small        (market-cap dominates, 5/10)
  CoreProfitQGr%PY w1 ↑   EpsExclXorQGr%PY w1 ↑   ROETTMDiffPQ w1 ↑
  股价振幅%成交额10日(ILLIQ) w1 ↑   业绩快报归母净利QGr%PY w1 ↑
So #2 = #1 with the 2 overnight-mom + 1 业绩预告 terms REPLACED by ONE 业绩快报(express) term.

GAP — 业绩快报 (express earnings flash) is NOT materialized (absent from the provider; mapping-doc §7).
The express factor (w=1 of 10) is therefore OMITTED → the composite is the faithful 6-term core (weight
9 of 10). Documented approximation; its impact is measured against 果仁 below. NOT proxied by #1's 业绩预告
$forecast__np_q_yoy — a distinct event (express ≻ forecast in precision; substitution would be unvalidated).

Trade model (= #1, identical recipe trade_model): 模型II daily, 09:35 open fill, 个股仓位 7–13% (~10 holds,
max 15), 备选 20, sell 排名≥25, 涨停不卖 (engine hold_on_limit_up), 退市风险 sell ≈ price<2 + ST, no timing.
Cost 千分之二 (0.2%/side, 果仁 default), total return (EventDriven credits dividends, §3.3).

REUSE: #2's 6 ranking factors ⊂ #1's 9 → this reads #1's validated factor cache (verify01_cache,
recomputation-free) and drives the SAME validated build_schedule / _composite_row (guorn_verify_01_growth,
module globals overridden to the 6-term WEIGHTS). NON-FORMAL parity artifact; not sealed/deployable.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np  # noqa: F401  (parity with #1 import surface)
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace" / "research" / "long_only_50cagr"))
sys.path.insert(0, str(ROOT / "workspace" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")

import research_utils as ru                                          # noqa: E402
import guorn_verify_01_growth as g1                                  # noqa: E402  (reuse validated machinery)
from guorn_parity_rung2_posprofit import ModelIIPosProfitStrategy    # noqa: E402

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
CACHE_01 = OUT / "verify01_cache"          # REUSE #1's frames (the 6 shared factors ⊂ #1's 9)
SCHED_02 = OUT / "verify02_schedule.json"
XLSX = ROOT / "Knowledge" / "果仁回测结果" / "05_sm_01_成长_v1.xlsx"
GR = dict(annual=0.5820, sharpe=1.58, mdd=0.5004, vol=0.3438, excess=0.1688)

# #2 composite = 6 faithful terms (express OMITTED). term -> (weight, dir): +1 = 从大到小 (larger better),
# -1 = 从小到大 (smaller better). market-cap dominates (5/9 of the consumed weight), as in #1.
WEIGHTS = {"mktcap_ind": (2, -1), "mktcap_x": (3, -1), "CoreProfitQGr": (1, +1),
           "EpsExclXorGr": (1, +1), "ROETTMDiff": (1, +1), "ILLIQ": (1, +1)}
TOTAL_W = sum(w for w, _ in WEIGHTS.values())   # = 9 (order-preserving divisor only; selection-invariant)


def schedule(start, end):
    """Override #1's globals to the 6-term composite + reuse its cache, then run the VALIDATED scheduler."""
    if not (CACHE_01 / "f_mktcap_x.parquet").exists():
        raise SystemExit("verify01_cache missing — run guorn_verify_01_growth.py --build first.")
    g1.WEIGHTS = WEIGHTS
    g1.TOTAL_W = TOTAL_W
    g1.CACHE = CACHE_01            # reuse #1's frames (identical universe/fields/range)
    g1.SCHED = SCHED_02
    g1.build_schedule(start, end, headroom=30)   # headroom≥25 so the sell-band (rank≥25) is resolvable


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
            out[y] = float(v)   # 果仁 年度收益统计 stores DECIMALS (0.8445=84%, 3.4035=340%); never /100
    return out


def run(start, end):
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    sched = {pd.Timestamp(k): v for k, v in json.loads(SCHED_02.read_text(encoding="utf-8")).items()}
    # #2 交易模型 = #1's (identical recipe): 模型II, 理想持仓 10 / 最大持仓 15, 卖出排名≥25, 备选20 全池, exits OFF.
    strat = ModelIIPosProfitStrategy(sched, buy_rank=20, sell_rank=25, target_n=10, pos_max=0.13,
                                     max_holds=15, use_exits=False, rebuy_cooldown=0)
    cost = CostConfig(buy_commission=0.002, sell_commission=0.002, stamp_tax=0.0, min_commission=0.0, transfer_fee=0.0)
    bt = EventDrivenBacktester(data_dir=str(ROOT / "data"))
    res = bt.run(strategy=strat, start_time=start, end_time=end, benchmark="000300.SH", account=1_000_000.0,
                 exchange_config=cost, slippage=FixedSlippage(0.0), volume_limit=0.10,
                 hold_on_limit_up=True,   # 果仁 不卖条件: 调仓日交易时涨停 (hold limit-up winners)
                 preload_fields=["$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close", "$adj_factor",
                                 "$up_limit", "$down_limit"])
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    net = rep["return"].astype(float)
    net.to_frame("net").to_parquet(OUT / "verify02_net.parquet")
    m = ru.goal_metrics(net); m["sharpe_rf4"] = ru.sharpe(net, rf=0.04)
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    yearly = {int(y): float(v) for y, v in yr.items()}
    gy = _read_guorn_yearly()
    print("\n" + "=" * 74)
    print("  #2 sm_01_成长_v1 — LOCAL vs 果仁 (daily model-II, 0.2%/side; 业绩快报 OMITTED)")
    print(f"  LOCAL  annual≈{m['cagr']:+.2%}  Sharpe(rf4%)={m['sharpe_rf4']:.2f}  MDD={m['mdd']:+.2%}  vol={m['ann_vol']:.2%}")
    print(f"  果仁   annual={GR['annual']:+.2%}  Sharpe={GR['sharpe']:.2f}  MDD={-GR['mdd']:+.2%}  vol={GR['vol']:.2%}")
    print("  year     LOCAL      果仁     diff")
    for y in sorted(yearly):
        g = gy.get(y); gtxt = f"{g:+7.1%}" if g is not None else "   n/a "
        print(f"  {y}   {yearly[y]:+8.1%}  {gtxt}  {(f'{yearly[y]-g:+7.1%}') if g is not None else ''}")
    (OUT / "verify02_result.json").write_text(json.dumps(
        dict(local=m, local_yearly=yearly, guoren=GR, guoren_yearly=gy, start=start, end=end,
             omitted=["业绩快报归母净利QGr%PY (express, not materialized)"]), indent=2, default=str), encoding="utf-8")
    print("\nNON-FORMAL PARITY ARTIFACT — validates #2 construction vs 果仁; NOT sealed/deployable.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--schedule", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--start", default="2014-01-01")
    ap.add_argument("--end", default="2026-02-27")
    args = ap.parse_args()
    if args.schedule:
        schedule(args.start, args.end)
    if args.run:
        run(args.start, args.end)


if __name__ == "__main__":
    main()
