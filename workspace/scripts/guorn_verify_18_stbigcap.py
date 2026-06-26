"""果仁 deployed-20 verification — strategy #18: ST_大市值_v3 (nn=53). P5 PROOF for the report_rc data unlock.

The CLEANEST book that exercises the newly-materialized $report_rc__n_active_orgs (评级机构数): its ONLY
new-data dependency is 评级机构数; the other 5 factors are all validated. 果仁 = trusted benchmark.

Recipe (deployed_20_recipes.md #18):
  universe : 仅有ST (ONLY ST stocks) + 包含科创板 (incl 688), 过滤停牌
  filters(1): N日涨幅(250) 排名%区间 0%-75% (drop the top-25% 250d-momentum)
  rankings(6, equal-weight w1, all 从大到小 = bigger-better):
    总市值 ↑ + 营业收入(单季) ↑ + CoreProfitQ ↑ + 评级机构数 ↑ + 业绩预告净利润QGr%PYQ_v1 ↑ + REF(股东数,4)/股东数-1 ↑
  trade model : 模型II daily, 09:35 open, 个股仓位 14–26% (理想20% → ~5 holds, max ~7), 备选5, sell 排名≥8,
    距上次卖出≥8 (rebuy cooldown), 涨停不卖 (hold_on_limit_up). cost 0.2%/side, total return.

NEW FIELD: 评级机构数 = $report_rc__n_active_orgs (Tushare report_rc, in-place published 2026-06-27,
QUARANTINE — NON-FORMAL parity read OK; sandbox stage warns-not-fails). VENDOR-APPROXIMATE vs 果仁 朝阳永续.
Mapping: 总市值=$total_mv, 营收单季=$revenue_sq_q0, CoreProfitQ=rev−cost−(admin+sell+fin)−biztax _sq (rung-5
penny), 业绩预告=$forecast__np_q_yoy (rung-3), 股东数=$holder_num (rung-5; REF(,4) depth per recipe).

OMITTED (documented): the recipe's price exits (买入后涨幅≥120% TP / 跌幅≥18% SL / 最高点跌幅≥18% trail) —
per the rung-2 finding 果仁's exits barely bind (winners exit via RANK) + are PIT-incompatible pre-open
(prev-close eval vs 果仁's 09:35 same-day); use_exits=False is the faithful baseline. NON-FORMAL parity.
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

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
CACHE = OUT / "verify18_cache"
CACHE.mkdir(parents=True, exist_ok=True)
SCHED = OUT / "verify18_schedule.json"
PROVIDER_URI = str(ROOT / "data" / "qlib_data")
PREFIXES = ("600", "601", "603", "605", "000", "001", "002", "003", "300", "301", "688", "689")  # +科创板
XLSX = ROOT / "Knowledge" / "果仁回测结果" / "53_ST_大市值_v3.xlsx"
GR = dict(annual=0.5546, sharpe=2.00, mdd=0.4351, vol=0.2575, excess=0.4631)

# 6 equal-weight terms; dir: +1 = 从大到小 (bigger better). ALL +1 for #18.
WEIGHTS = {"mktcap": (1, +1), "revenue": (1, +1), "coreprofit": (1, +1),
           "n_orgs": (1, +1), "forecast": (1, +1), "holder_chg": (1, +1)}
TOTAL_W = sum(w for w, _ in WEIGHTS.values())

_Q = lambda b, qs: [f"${b}_sq_q{i}" for i in qs]                          # noqa: E731
FIELDS = sorted(set(
    ["$total_mv", "$close", "$adj_factor", "$report_rc__n_active_orgs", "$forecast__np_q_yoy",
     "$holder_num_q0", "$holder_num_q4"]
    + _Q("revenue", (0,)) + _Q("oper_cost", (0,)) + _Q("admin_exp", (0,)) + _Q("sell_exp", (0,))
    + _Q("fin_exp", (0,)) + _Q("biz_tax_surchg", (0,))
))


def _load_bounds() -> dict:
    p = ROOT / "data" / "qlib_data" / "instruments" / "all_stocks.txt"
    df = pd.read_csv(p, sep="\t", header=None, names=["code", "start", "end"], dtype=str)
    return {str(r.code).upper(): (pd.Timestamp(r.start), pd.Timestamp(r.end)) for r in df.itertuples(index=False)}


BOUNDS = _load_bounds()


def _in_universe(c: str) -> bool:
    return c.split("_")[0][:3] in PREFIXES


def build(start: str, end: str):
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=PROVIDER_URI, region=REG_CN, kernels=1)
    allinsts = D.list_instruments(D.instruments("all"), start_time=start, end_time=end, as_list=True)
    insts = sorted(c for c in allinsts if _in_universe(c))
    print(f"[build] {len(insts)} 沪深+科创 insts; pulling {len(FIELDS)} fields {start}..{end}", flush=True)
    fetch_start = (pd.Timestamp(start) - pd.Timedelta(days=420)).strftime("%Y-%m-%d")
    P = {}
    for k in range(0, len(FIELDS), 6):
        batch = FIELDS[k:k + 6]
        df = D.features(insts, batch, start_time=fetch_start, end_time=end, freq="day")
        for col in batch:
            P[col.replace("$", "")] = df[col].unstack(level=0).sort_index()
        print(f"[build]   {min(k + 6, len(FIELDS))}/{len(FIELDS)}", flush=True)
        del df
    idx = P["close"].index
    EPS = 1e-9

    def safe(num, den):
        return (num / den.where(den.abs() > EPS)).replace([np.inf, -np.inf], np.nan)

    def ff(name):
        return P[name].reindex(idx).ffill()

    factors = {}
    factors["mktcap"] = ff("total_mv")
    factors["revenue"] = ff("revenue_sq_q0")
    factors["coreprofit"] = (ff("revenue_sq_q0") - ff("oper_cost_sq_q0")
                             - (ff("admin_exp_sq_q0") + ff("sell_exp_sq_q0") + ff("fin_exp_sq_q0"))
                             - ff("biz_tax_surchg_sq_q0"))
    factors["n_orgs"] = ff("report_rc__n_active_orgs")              # daily-carried level; read at pday = Ref(,1) lag
    factors["forecast"] = ff("forecast__np_q_yoy")
    factors["holder_chg"] = safe(ff("holder_num_q4"), ff("holder_num_q0")) - 1.0   # REF(股东数,4)/股东数−1

    adjc = P["close"] * P["adj_factor"]
    elig = {"close_raw": P["close"], "ret250": safe(adjc, adjc.shift(250)) - 1.0}

    for name, fr in factors.items():
        fr.reindex(idx).astype("float32").to_parquet(CACHE / f"f_{name}.parquet")
    for name, fr in elig.items():
        fr.reindex(idx).astype("float32").to_parquet(CACHE / f"e_{name}.parquet")
    (CACHE / "meta.json").write_text(json.dumps({"start": start, "end": end, "n": len(insts)}), encoding="utf-8")
    print("[build] factor coverage:", {n: round(float(fr.reindex(idx).notna().mean().mean()), 3) for n, fr in factors.items()}, flush=True)
    print(f"[build] cached -> {CACHE}", flush=True)


def _load():
    f = {n: pd.read_parquet(CACHE / f"f_{n}.parquet") for n in WEIGHTS}
    e = {n: pd.read_parquet(CACHE / f"e_{n}.parquet") for n in ("close_raw", "ret250")}
    return f, e


def _composite_row(f, pday, elig_idx):
    """果仁-exact 综合排名分 = Σ(排名分 × w); 排名分 = (N−rank+1)/N×100, NaN→bottom. All 全部-scope here."""
    N = len(elig_idx)
    parts = []
    for name, (w, d) in WEIGHTS.items():
        row = f[name].loc[pday].reindex(elig_idx)
        asc = (d < 0)
        rnk = row.rank(method="min", ascending=asc, na_option="bottom")
        parts.append((N - rnk + 1) / N * 100.0 * w)
    return pd.concat(parts, axis=1).sum(axis=1) / (100.0 * TOTAL_W)


def build_schedule(start, end, headroom=12):   # headroom ≥ sell_rank(8) so the band is resolvable
    f, e = _load()
    cal = ru.trading_calendar()
    cal = cal[(cal >= pd.Timestamp(start)) & (cal <= pd.Timestamp(end))]
    close_raw = e["close_raw"]; ret250 = e["ret250"]
    insts = close_raw.columns
    grid = close_raw.index
    sched, members = {}, {}
    for d in cal:
        d = pd.Timestamp(d)
        pos = grid.searchsorted(d)
        if pos == 0:
            sched[d] = []; continue
        pday = grid[pos - 1]
        st = ru.st_codes_on(d)                                       # the ST set on d (果仁: 仅有ST)
        cr = close_raw.loc[pday]
        keep = cr.notna() & (cr >= 2.0)                             # 过滤停牌 + 收盘价≥2
        keep &= pd.Series([c.upper() in st for c in insts], index=insts)   # ONLY ST stocks
        keep &= pd.Series([(BOUNDS.get(c.upper()) is not None and BOUNDS[c.upper()][0] <= pday <= BOUNDS[c.upper()][1]) for c in insts], index=insts)
        r250 = ret250.loc[pday]
        keep &= (r250.rank(pct=True) <= 0.75) | r250.isna()         # N日涨幅250 rank≤75% (keep NaN = young)
        elig = keep[keep].index
        if len(elig) < headroom:
            sched[d] = []; continue
        comp = _composite_row(f, pday, elig).dropna()
        top = comp.sort_values(ascending=False).head(headroom)
        sched[d] = [str(c).upper().replace("_", ".") for c in top.index]
        members[d] = set(list(top.index)[:5])
    keys = sorted(members)
    churn = [len(members[keys[i]] - members[keys[i - 1]]) / max(len(members[keys[i]]), 1)
             for i in range(1, len(keys)) if members[keys[i]]]
    SCHED.write_text(json.dumps({str(k.date()): v for k, v in sched.items()}, ensure_ascii=False), encoding="utf-8")
    ne = sum(1 for v in sched.values() if v)
    print(f"[sched] {ne}/{len(cal)} non-empty; mean top5 churn/day={np.mean(churn) if churn else float('nan'):.3f}; saved", flush=True)


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
            out[y] = float(v)   # decimals (3.4035=+340%)
    return out


def run(start, end):
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    sched = {pd.Timestamp(k): v for k, v in json.loads(SCHED.read_text(encoding="utf-8")).items()}
    strat = ModelIIPosProfitStrategy(sched, buy_rank=5, sell_rank=8, target_n=5, pos_max=0.26,
                                     max_holds=7, use_exits=False, rebuy_cooldown=8)
    cost = CostConfig(buy_commission=0.002, sell_commission=0.002, stamp_tax=0.0, min_commission=0.0, transfer_fee=0.0)
    bt = EventDrivenBacktester(data_dir=str(ROOT / "data"))
    res = bt.run(strategy=strat, start_time=start, end_time=end, benchmark="000300.SH", account=1_000_000.0,
                 exchange_config=cost, slippage=FixedSlippage(0.0), volume_limit=0.10, hold_on_limit_up=True,
                 preload_fields=["$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close", "$adj_factor",
                                 "$up_limit", "$down_limit"])
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    net = rep["return"].astype(float)
    net.to_frame("net").to_parquet(OUT / "verify18_net.parquet")
    m = ru.goal_metrics(net); m["sharpe_rf4"] = ru.sharpe(net, rf=0.04)
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    yearly = {int(y): float(v) for y, v in yr.items()}
    gy = _read_guorn_yearly()
    print("\n" + "=" * 74)
    print("  #18 ST_大市值_v3 — LOCAL vs 果仁 (daily model-II, 0.2%/side; P5 report_rc 评级机构数 proof)")
    print(f"  LOCAL  annual≈{m['cagr']:+.2%}  Sharpe(rf4%)={m['sharpe_rf4']:.2f}  MDD={m['mdd']:+.2%}  vol={m['ann_vol']:.2%}")
    print(f"  果仁   annual={GR['annual']:+.2%}  Sharpe={GR['sharpe']:.2f}  MDD={-GR['mdd']:+.2%}  vol={GR['vol']:.2%}")
    print("  year     LOCAL      果仁     diff")
    for y in sorted(yearly):
        g = gy.get(y); gtxt = f"{g:+8.1%}" if g is not None else "   n/a  "
        print(f"  {y}   {yearly[y]:+8.1%}  {gtxt}  {(f'{yearly[y]-g:+7.1%}') if g is not None else ''}")
    (OUT / "verify18_result.json").write_text(json.dumps(
        dict(local=m, local_yearly=yearly, guoren=GR, guoren_yearly=gy, start=start, end=end,
             new_field="$report_rc__n_active_orgs (评级机构数)",
             omitted=["price exits TP120/SL18/trail18 (rung-2: barely bind + pre-open-incompatible)"]),
        indent=2, default=str), encoding="utf-8")
    print("\nNON-FORMAL PARITY ARTIFACT — P5 proof the published report_rc 评级机构数 reproduces a book; NOT sealed/deployable.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--schedule", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--start", default="2014-01-01")
    ap.add_argument("--end", default="2026-02-27")
    args = ap.parse_args()
    if args.build:
        build(args.start, args.end)
    if args.schedule:
        build_schedule(args.start, args.end)
    if args.run:
        run(args.start, args.end)


if __name__ == "__main__":
    main()
