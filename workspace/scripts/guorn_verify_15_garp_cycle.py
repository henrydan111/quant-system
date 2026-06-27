"""果仁 deployed-20 verification — strategy #15: 成长_双创_GARP@周期_v2 (nn=44, xlsx 44).

The SAME GARP factor base as #4 (sm_GARP_illiq) on the 双创 universe (创业板 + 科创板) — the textbook
"#4 on 双创" book. 果仁 = trusted benchmark; the LOCAL construction layer is under test. Reuses #4's
verify04_cache verbatim (the build universe already includes 科创板 for exactly this reuse — like #6 reused #1).

Recipe (deployed_20_recipes.md #15): 22 ranking terms. Identical to #4's GARP set EXCEPT it drops 总市值 and
FCFQ%总市值 and adds BP带壳 (壳价值 — irreducible). So the KEEP set = #4's 11 minus 总市值 = 10 terms (Σw=12);
the OMIT set is #4's 11 (3 中性化, 快报, 12q-StdevQ, EBITDAQ%EV, gross÷EV, FCFQ growth, 3 TTM-YoY/3yr) PLUS
BP带壳 → 12 OMIT (Σw=12). KEEP = 12/24 weight. Every omission is the SAME measured-impossible reason as #4
(provider single-q depth q0..q4, no EV field, D&A single-q 0%, 中性化/壳/快报 irreducible) — see #4 docstring +
_guorn_garp_field_probe.py.

  filter      : 退市风险(≈price≥2+ST) + 上市天数>20. [未来20日新增流通股<1% skip — PIT lockup, no clean feed]
                (NO ILLIQ filter — that is #4-only.)
  trade model : 模型II daily, 调仓价格=日均成交价 → engine fill_mode='jq_daily_avg' (§3.3 — gates on all_day_lock).
                个股仓位 7–13% (~10 holds, max ~14), 备选买入=5, sell 排名≥20, 不卖 涨停 (hold_on_limit_up)+选股日停牌.
                PRICE EXITS (买入后涨幅≥100% TP / 跌幅≥18% SL / 最高点跌幅≥18% trail) + buy 距上次卖出≥10 cooldown.
                cost 0.2%/side, total return.

⚠ CAVEAT (rung-2 GPT note, documented): the price exits are evaluated PRE-OPEN on prev-day close (the
ModelIIPosProfitStrategy approximation), so they OVER-fire vs 果仁's same-day 09:35/日均 evaluation; a faithful
exit belongs in the engine fill-step (future work). 果仁's exits empirically rarely bind (rung-2). 实时选股=未勾选
on #15 → 果仁 ranks on the prev close (our pday rank is already prev-day → consistent).

LAYER DISCIPLINE (§8.1): factor frames are #4's full-build-universe (universe-agnostic Layer-1); the 双创
restriction is a Layer-2 selection mask. NON-FORMAL parity artifact (metadata-stamped).
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

import research_utils as ru                                              # noqa: E402
from guorn_parity_rung2_posprofit import ModelIIPosProfitStrategy        # noqa: E402
from guorn_verify_04_garp import _load, composite_row, LISTED_BOUNDS, CACHE  # noqa: E402  (reuse #4 cache+composite)

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
SCHED = OUT / "verify15_schedule.json"
SHUANGCHUANG = ("300", "301", "688", "689")          # 双创 = 创业板 + 科创板
XLSX = ROOT / "Knowledge" / "果仁回测结果" / "44_成长_双创_GARP@周期_v2.xlsx"
GR = dict(annual=0.4339, sharpe=1.13, mdd=0.4655, vol=0.3492, excess=0.3064)

# #15 KEEP = #4 WEIGHTS minus 'mktcap' (#15 has no 总市值 term). dir/scope identical to #4.
WEIGHTS = {
    "SalesQGr":           (1, +1, "all"),
    "revQoQ_minus_YoY":   (1, +1, "all"),
    "CoreProfitQGr":      (2, +1, "all"),
    "incometaxQGr":       (1, +1, "all"),
    "RnDQGR":             (1, +1, "all"),
    "ROETTMDiff":         (2, +1, "all"),
    "EpsExclXorGr":       (1, +1, "all"),
    "salesyield":         (1, +1, "ind"),
    "GrossProfitAssetsQ": (1, +1, "all"),
    "forecast":           (1, +1, "all"),
}
TOTAL_W = sum(w for w, _, _ in WEIGHTS.values())   # = 12
OMITTED = [
    "BP带壳 — 壳价值 (AH-premium regression), irreducible",
    "BP筹资市值比调整 / 标准化中性化MI(RNDQP) / 中性化(EPCOREPROFITQ,总市值) — 3× HNeutralize 中性化",
    "业绩快报归母净利QGr%PY — 快报 (express) not materialized",
    "波动率_季度指标(CoreProfitQGr%PY,12) — 12q StdevQ; provider single-q depth = q0..q4 only",
    "EBITDAQ%EV + (rev−cost)/EV — NO EV field; EBITDAQ also needs D&A single-q (0%)",
    "FCFQ_重算Gr%PYQ — FCFQ needs D&A single-q (0%) + 处置FIOLTA (absent)",
    "营收增长−3年复合 / CoreProfitQGr%PQ−TTMGr%PY / CoreProfitTTMGr%PY−%3Y — TTM-YoY/3yr need q4..q7 depth",
]


def build_schedule(start, end, headroom=25):
    f, ind, e = _load(WEIGHTS)
    cal = ru.trading_calendar()
    cal = cal[(cal >= pd.Timestamp(start)) & (cal <= pd.Timestamp(end))]
    close_raw = e["close_raw"]
    insts = close_raw.columns
    grid = close_raw.index
    sched, members = {}, {}
    for d in cal:
        d = pd.Timestamp(d)
        pos = grid.searchsorted(d)
        if pos == 0:
            sched[d] = []; continue
        pday = grid[pos - 1]
        st = ru.st_codes_on(d)
        cr = close_raw.loc[pday]
        keep = pd.Series(True, index=insts)
        keep &= cr.notna() & (cr >= 2.0)                                 # 过滤停牌 + 退市风险 atom 收盘价≥2
        ok = []                                                          # 双创 universe + 上市>20 + not-ST + listed
        for c in insts:
            b = LISTED_BOUNDS.get(c.upper())
            ok.append(c.split("_")[0][:3] in SHUANGCHUANG and c.upper() not in st
                      and b is not None and b[0] <= pday <= b[1] and (pday - b[0]).days > 20)
        keep &= pd.Series(ok, index=insts)
        elig_names = keep[keep].index
        if len(elig_names) < headroom:
            sched[d] = []; continue
        comp = composite_row(f, ind, pday, elig_names, WEIGHTS, TOTAL_W).dropna()
        top = comp.sort_values(ascending=False).head(headroom)
        sched[d] = [str(c).upper().replace("_", ".") for c in top.index]
        members[d] = set(list(top.index)[:10])
    keys = sorted(members)
    churn = [len(members[keys[i]] - members[keys[i - 1]]) / max(len(members[keys[i]]), 1)
             for i in range(1, len(keys)) if members[keys[i]]]
    SCHED.write_text(json.dumps({str(k.date()): v for k, v in sched.items()}, ensure_ascii=False), encoding="utf-8")
    nonempty = sum(1 for v in sched.values() if v)
    print(f"[sched15] {nonempty}/{len(cal)} non-empty; mean top10 churn/day={np.mean(churn) if churn else float('nan'):.3f}; saved", flush=True)


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
            out[y] = float(v)   # decimals; never /100
    return out


def run(start, end, use_exits=False):
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    sched = {pd.Timestamp(k): v for k, v in json.loads(SCHED.read_text(encoding="utf-8")).items()}
    # #15 模型II: 个股仓位 7–13% (~10 holds), sell 排名≥20, 备选=5, 距上次卖出≥10 cooldown.
    # PRICE EXITS DEFAULT OFF = the FAITHFUL baseline (rung-2 finding): 果仁's 买入后涨幅≥100%/跌幅≥18%/
    # 最高点跌幅≥18% exits empirically rarely bind (rung-2: frac hit ≈ 0.000), but our pre-open prev-close
    # APPROXIMATION over-fires (exits-ON: 2015 +132% vs 果仁 +358% [−226pp], MDD −71%, trail=283/sl=42 churn).
    # The faithful exit belongs in the engine fill-step (same-day 09:35/日均 eval); pre-open it whipsaws.
    # Exits-ON is recorded as the documented OVER-FIRING variant (verify15_result_exits.json).
    strat = ModelIIPosProfitStrategy(sched, buy_rank=5, sell_rank=20, target_n=10, pos_max=0.13,
                                     max_holds=14, use_exits=use_exits, tp=1.00, sl=0.18, trail=0.18, rebuy_cooldown=10)
    cost = CostConfig(buy_commission=0.002, sell_commission=0.002, stamp_tax=0.0, min_commission=0.0, transfer_fee=0.0)
    bt = EventDrivenBacktester(data_dir=str(ROOT / "data"))
    res = bt.run(strategy=strat, start_time=start, end_time=end, benchmark="000300.SH", account=1_000_000.0,
                 exchange_config=cost, slippage=FixedSlippage(0.0), volume_limit=0.10, hold_on_limit_up=True,
                 fill_mode="jq_daily_avg",   # 果仁 调仓价格=日均成交价 (§3.3)
                 preload_fields=["$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close", "$adj_factor",
                                 "$up_limit", "$down_limit"])
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    net = rep["return"].astype(float)
    # exits-off (faithful baseline) is the PRIMARY artifact (verify15_net/result.json); exits-on = _exits variant
    tag = "" if not use_exits else "_exits"
    net.to_frame("net").to_parquet(OUT / f"verify15_net{tag}.parquet")
    m = ru.goal_metrics(net); m["sharpe_rf4"] = ru.sharpe(net, rf=0.04)
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    yearly = {int(y): float(v) for y, v in yr.items()}
    gy = _read_guorn_yearly()
    sr = strat.sell_reasons
    print("\n" + "=" * 74)
    print(f"  #15 成长_双创_GARP@周期_v2 — LOCAL vs 果仁 (daily model-II, 日均成交价, 0.2%/side; 12/24 weight OMITTED; "
          f"exits={'ON (over-firing variant)' if use_exits else 'OFF (faithful baseline)'})")
    print(f"  LOCAL  annual≈{m['cagr']:+.2%}  Sharpe(rf4%)={m['sharpe_rf4']:.2f}  MDD={m['mdd']:+.2%}  vol={m['ann_vol']:.2%}")
    print(f"  果仁   annual={GR['annual']:+.2%}  Sharpe={GR['sharpe']:.2f}  MDD={-GR['mdd']:+.2%}  vol={GR['vol']:.2%}")
    print(f"  sells: {sr}")
    print("  year     LOCAL      果仁     diff")
    for y in sorted(yearly):
        g = gy.get(y); gtxt = f"{g:+7.1%}" if g is not None else "   n/a "
        print(f"  {y}   {yearly[y]:+8.1%}  {gtxt}  {(f'{yearly[y]-g:+7.1%}') if g is not None else ''}")
    (OUT / f"verify15_result{tag}.json").write_text(json.dumps(
        dict(local=m, local_yearly=yearly, guoren=GR, guoren_yearly=gy, start=start, end=end, use_exits=use_exits,
             kept_terms=list(WEIGHTS), kept_weight=TOTAL_W, total_recipe_weight=24, omitted=OMITTED,
             sell_reasons=sr), indent=2, default=str), encoding="utf-8")
    print("\nNON-FORMAL PARITY ARTIFACT — validates #15 construction vs 果仁; NOT sealed/deployable.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--schedule", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--exits", default="off", choices=["on", "off"])   # off = faithful baseline (rung-2)
    ap.add_argument("--start", default="2014-01-01")
    ap.add_argument("--end", default="2026-02-27")
    args = ap.parse_args()
    if args.schedule:
        build_schedule(args.start, args.end)
    if args.run:
        run(args.start, args.end, use_exits=(args.exits == "on"))


if __name__ == "__main__":
    main()
