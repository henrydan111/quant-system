"""果仁 deployed-20 verification — strategy #12: value_创业板sm_v1 (nn=24, xlsx 24).

SCRIPT_STATUS: Class-B parity diagnostic (2026-07-03). THIN harness — all 9 ranking terms already exist as
verify04_cache frames (the #4 upgrade arc): EBITDAQ%EV(行业内) · 营收单季/总市值(行业内) · gp_ev(行业内) ·
GrossProfit%AssetsQ · bpfin · FCFQ%总市值 · mi_rndqp[EXCLUDED — broken semantics, sp −0.18 → 8/9 weight] ·
ep_core_neut(行业内) · 总市值(从小到大). Universe: 创业板 ONLY − ST − 停牌 (board_of=='chinext'). NO filters.
Trade: Model II daily 09:35, 5-15% band (~10 holds, max 20), 备选5, sell 排名≥20, PRICE EXITS
(tp100%/sl18%/trail18%) + rebuy cooldown 10, 涨停不卖+选股日停牌. 果仁 +41.75% / −43.11.
NON-FORMAL parity artifact.
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
import guorn_verify_07_divlowvol as v7                                   # noqa: E402
from guorn_universe import in_guorn_universe                             # noqa: E402

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
CACHE04 = OUT / "verify04_cache"
SCHED = OUT / "verify12_schedule.json"
XLSX = ROOT / "Knowledge" / "果仁回测结果" / "24_value_创业板sm_v1.xlsx"

# term -> (weight, dir, scope); frames all from verify04_cache
WEIGHTS = {"ebitda_ev": (1, +1, "ind"), "salesyield": (1, +1, "ind"), "gp_ev": (1, +1, "ind"),
           "GrossProfitAssetsQ": (1, +1, "all"), "bpfin": (1, +1, "all"), "fcf_mv": (1, +1, "all"),
           "ep_core_neut": (1, +1, "ind"), "mktcap": (1, -1, "all")}     # mi_rndqp w1 EXCLUDED -> 8/9
TOTAL_W = sum(w for w, _, _ in WEIGHTS.values())


def _load():
    cols = pd.read_parquet(CACHE04 / "e_close_raw.parquet").columns
    rd = lambda p: pd.read_parquet(CACHE04 / p).reindex(columns=cols)  # noqa: E731
    f = {n: rd(f"f_{n}.parquet") for n in WEIGHTS}
    ind = rd("industry.parquet").replace({"nan": np.nan, "None": np.nan})
    e = {"close_raw": rd("e_close_raw.parquet")}
    return f, ind, e


def build_schedule(start="2014-01-01", end="2026-02-27", headroom=25):
    f, ind, e = _load()
    cal = ru.trading_calendar()
    cal = cal[(cal >= pd.Timestamp(start)) & (cal <= pd.Timestamp(end))]
    close = e["close_raw"]
    grid = close.index
    insts = close.columns
    bounds = v7._bounds()
    chinext = pd.Series([in_guorn_universe(c, boards=("chinext",)) for c in insts], index=insts)
    sched = {}
    for d in cal:
        d = pd.Timestamp(d)
        pos = grid.searchsorted(d)
        if pos == 0:
            sched[d] = []
            continue
        pday = grid[pos - 1]
        st = ru.st_codes_on(d)
        cr = close.loc[pday]
        listed = pd.Series([(bounds.get(str(c).upper()) is not None
                             and bounds[str(c).upper()][0] <= pday <= bounds[str(c).upper()][1])
                            for c in insts], index=insts)
        keep = chinext & listed & cr.notna()
        keep &= pd.Series([str(c).upper() not in st for c in insts], index=insts)
        elig = keep[keep].index
        if len(elig) < headroom:
            sched[d] = []
            continue
        indrow = ind.loc[pday].reindex(elig)
        N = len(elig)
        parts = []
        for name, (w, di, scope) in WEIGHTS.items():
            row = v7._row(f[name], pday).reindex(elig)
            asc = di < 0
            if scope == "ind":
                rnk = row.groupby(indrow).rank(method="min", ascending=asc, na_option="bottom")
                gN = indrow.map(indrow.value_counts())
                score = (gN - rnk + 1) / gN * 100.0
            else:
                rnk = row.rank(method="min", ascending=asc, na_option="bottom")
                score = (N - rnk + 1) / N * 100.0
            parts.append(score * w)
        comp = pd.concat(parts, axis=1).sum(axis=1) / (100.0 * TOTAL_W)
        top = comp.sort_values(ascending=False).head(headroom)
        sched[d] = [str(c).upper().replace("_", ".") for c in top.index]
    SCHED.write_text(json.dumps({str(k.date()): v for k, v in sched.items()}, ensure_ascii=False),
                     encoding="utf-8")
    print(f"[sched12] {sum(1 for v in sched.values() if v)}/{len(cal)} non-empty", flush=True)


def run(start="2014-01-02", end="2026-02-27", replay=False):
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    if replay:
        h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
        h["start"] = pd.to_datetime(h["开始日期"], errors="coerce")
        h["code"] = h["股票代码"].astype(str).str.zfill(6)
        h = h[h["start"].notna() & (h["start"] <= pd.Timestamp(end))]
        sched = {}
        for d, grp in h.groupby("start"):
            rows = []
            for _, r in grp.iterrows():
                w = pd.to_numeric(r.get("本期起始仓位"), errors="coerce")
                if pd.notna(w) and w > 0:
                    c = r["code"]
                    rows.append([f"{c}.{'SH' if c[0] == '6' else 'SZ'}", float(w)])
            sched[str(d.date())] = rows
        strat = v7.ModelIDivLowVolStrategy(sched, max_holds=99, weights_mode="explicit")
        net_name, label = "verify12_replay_net.parquet", "REPLAY(果仁持仓+权重)"
    else:
        sched = {pd.Timestamp(k): v for k, v in json.loads(SCHED.read_text(encoding="utf-8")).items()}
        strat = ModelIIPosProfitStrategy(sched, buy_rank=20, sell_rank=20, target_n=10, pos_max=0.15,
                                         max_holds=20, use_exits=True, tp=1.00, sl=0.18, trail=0.18,
                                         rebuy_cooldown=10)
        net_name, label = "verify12_net.parquet", "LOCAL selection (8/9w)"
    cost = CostConfig(buy_commission=0.002, sell_commission=0.002, stamp_tax=0.0, min_commission=0.0,
                      transfer_fee=0.0)
    bt = EventDrivenBacktester(data_dir=str(ROOT / "data"))
    res = bt.run(strategy=strat, start_time=start, end_time=end, benchmark="000300.SH", account=1_000_000.0,
                 exchange_config=cost, slippage=FixedSlippage(0.0), volume_limit=0.10, hold_on_limit_up=True,
                 preload_fields=["$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close",
                                 "$adj_factor", "$up_limit", "$down_limit"])
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    net = rep["return"].astype(float)
    net.to_frame("net").to_parquet(OUT / net_name)
    m = ru.goal_metrics(net)
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    gdf = pd.read_excel(XLSX, sheet_name="年度收益统计", header=0)
    gy = {}
    for _, r in gdf.iterrows():
        try:
            y = int(str(r.iloc[0])[:4])
        except Exception:
            continue
        v = pd.to_numeric(r.iloc[1], errors="coerce")
        if pd.notna(v):
            gy[y] = float(v)
    print("\n" + "=" * 72)
    print(f"  #12 value_创业板sm_v1 [{label}]  CAGR={m['cagr']:+.2%}  MDD={m['mdd']:+.2%}  "
          f"(果仁 +41.75% / −43.11)")
    for y in sorted(yr.index):
        g = gy.get(int(y))
        gt = f"{g:+8.1%}" if g is not None else "   n/a "
        dt = f"{float(yr[y]) - g:+7.1%}" if g is not None else ""
        print(f"  {int(y)}   {float(yr[y]):+8.1%}  {gt}  {dt}")
    json.dump({"cagr": m["cagr"], "mdd": m["mdd"], "yearly": {int(k): float(v) for k, v in yr.items()},
               "guorn_yearly": gy, "replay": replay},
              open(OUT / ("verify12_replay_result.json" if replay else "verify12_result.json"),
                   "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def compare(end="2026-02-27"):
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    h["start"] = pd.to_datetime(h["开始日期"], errors="coerce")
    h["code"] = h["股票代码"].astype(str).str.zfill(6)
    h = h[h["start"].notna() & (h["start"] <= pd.Timestamp(end))]
    s = {pd.Timestamp(k): v for k, v in json.loads(SCHED.read_text(encoding="utf-8")).items()}
    code6 = lambda c: str(c).split("_")[0].split(".")[0].zfill(6)  # noqa: E731
    rows = []
    for d, grp in h.groupby("start"):
        lst = s.get(d)
        if lst is None:
            continue
        held = set(grp["code"])
        order = {code6(c): i + 1 for i, c in enumerate(lst)}
        rks = [order.get(c, 999) for c in held]
        rows.append(dict(date=d, in10=float(np.mean([r <= 10 for r in rks])),
                         in20=float(np.mean([r <= 20 for r in rks]))))
    df = pd.DataFrame(rows)
    df["year"] = df["date"].dt.year
    print("\n=== #12 tracking ===")
    print(df[["in10", "in20"]].mean().round(3).to_string())
    print(df.groupby("year")[["in10", "in20"]].mean().round(3).to_string())


def main():
    ap = argparse.ArgumentParser()
    for flag in ("schedule", "run", "replay", "compare"):
        ap.add_argument(f"--{flag}", action="store_true")
    ap.add_argument("--end", default="2026-02-27")
    a = ap.parse_args()
    if a.schedule:
        build_schedule(end=a.end)
    if a.run:
        run(end=a.end)
    if a.replay:
        run(end=a.end, replay=True)
    if a.compare:
        compare(a.end)


if __name__ == "__main__":
    main()
