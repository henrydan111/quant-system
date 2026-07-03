"""果仁 deployed-20 verification — strategy #16: 成长_隔夜动量@周期 (nn=45, xlsx 45).

SCRIPT_STATUS: Class-B parity diagnostic (2026-07-03). 果仁 = trusted benchmark; LOCAL under test.

Recipe (deployed_20_recipes.md #16): universe 板块=全部 EXCL 科创/BSE, **包含ST**, 过滤停牌; NO screens
except 未来20日新增流通股<1% [OMITTED — the only screen]. Rankings (10 terms, Σw=13):
  onmom250−20 w3 + onmom120−20 w2  = the #1-validated v2 frames (min_periods=1, 涨停-day zeroed) — REUSED
  公式(%(评级机构数,REF(评级机构数,60))) w1 = $report_rc__n_active_orgs / its value 60 td ago (rank-faithful class)
  业绩预告净利润QGr%PYQ_v1 w1     = verify01 f_forecast_v2 (ALIVE-WINDOW masked) — REUSED
  公式((净利润−预期净利润Q)/|·|) w1 = quarterly CONSENSUS surprise — OMITTED (预期净利润Q not available;
                                     report_rc carries FY consensus only) → 12/13 weight kept
  评级调高家数 w1                  = $report_rc__rating_up
  AssetTurnoverDiffPY w1          = ATO(0)−ATO(4); UNLOCK_8Q pre-registered calibers A (4q-avg assets) vs
                                     B (begin+end/2, needs q8) — BOTH built, xlsx truth column decides
  行业净利润增长/环比 w1+w1        = SW-L1 member-aggregate Σni_sq growth (YoY / QoQ), broadcast to members
  行业N日涨幅(20) w1              = cap-weighted L1 20d adjusted return, broadcast
Trade model: Model II, 调仓周期=20 (xlsx 调仓详情 grid, 152 periods), 09:35≈open, 个股仓位 5-15%
(~10 holds, max 20), 备选5, sell 排名≥20, 涨停不卖+选股日停牌, no exits. Cost 0.2%/side.

REUSES verify01_cache (same universe: main+中小+创业板 incl ST, 4826 insts, grid 2012-11..2026-02-27):
e_close_raw / f_onmom250_v2 / f_onmom120_v2 / f_forecast_v2 / industry (hot-fixed L1 as-of).
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
import guorn_verify_07_divlowvol as v7                                   # noqa: E402  (_pdays/_bounds/_row + replay strategy)

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
CACHE01 = OUT / "verify01_cache"
CACHE = OUT / "verify16_cache"
CACHE.mkdir(parents=True, exist_ok=True)
SCHED = OUT / "verify16_schedule.json"
XLSX = ROOT / "Knowledge" / "果仁回测结果" / "45_成长_隔夜动量@周期.xlsx"
GR = dict(annual=0.2776, sharpe=0.81, mdd=0.5397)

WEIGHTS = {"onmom250": (3, +1), "onmom120": (2, +1), "orgchg": (1, +1), "forecast": (1, +1),
           "rating_up": (1, +1), "ato_diff": (1, +1), "ind_np_yoy": (1, +1), "ind_np_qoq": (1, +1),
           "ind_ret20": (1, +1)}          # npq_surprise w1 OMITTED (quarterly consensus) → 12/13 kept
TOTAL_W = sum(w for w, _ in WEIGHTS.values())


def _qlib_init():
    import qlib
    from qlib.config import REG_CN
    qlib.init(provider_uri=str(ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)


def rebalance_grid(cal_max="2026-02-27"):
    t = pd.read_excel(XLSX, sheet_name="调仓详情")
    d = pd.to_datetime(t["开始日期"], errors="coerce").dropna().sort_values().unique()
    return [pd.Timestamp(x) for x in d if pd.Timestamp(x) <= pd.Timestamp(cal_max)]


def build():
    from qlib.data import D
    _qlib_init()
    close = pd.read_parquet(CACHE01 / "e_close_raw.parquet")
    grid = close.index
    insts = list(close.columns)
    q = lambda b, qs: [f"${b}{i}" for i in qs]  # noqa: E731
    fields = (["$report_rc__n_active_orgs", "$report_rc__rating_up", "$total_mv", "$adj_factor", "$close"]
              + q("revenue_sq_q", range(8)) + ["$total_assets_q0", "$total_assets_q1", "$total_assets_q2",
                                               "$total_assets_q3", "$total_assets_q4", "$total_assets_q5",
                                               "$total_assets_q6", "$total_assets_q7", "$total_assets_q8"]
              + ["$n_income_sq_q0", "$n_income_sq_q1", "$n_income_sq_q4"])
    P = {}
    for k in range(0, len(fields), 5):
        batch = fields[k:k + 5]
        df = D.features(insts, batch, start_time=str(grid[0].date()), end_time=str(grid[-1].date()), freq="day")
        for c in batch:
            P[c.replace("$", "")] = (df[c].unstack(level=0).sort_index().reindex(grid)
                                     .reindex(columns=insts))
        print(f"[b16] {min(k+5, len(fields))}/{len(fields)}", flush=True)
        del df
    EPS = 1e-9
    safe = lambda n, d: (n / d.where(d.abs() > EPS)).replace([np.inf, -np.inf], np.nan)  # noqa: E731
    ff = lambda n: P[n].ffill()  # noqa: E731

    orgs = ff("report_rc__n_active_orgs")
    safe(orgs, orgs.shift(60)).astype("float32").to_parquet(CACHE / "f_orgchg.parquet")
    ff("report_rc__rating_up").astype("float32").to_parquet(CACHE / "f_rating_up.parquet")

    rev = {i: ff(f"revenue_sq_q{i}") for i in range(8)}
    ta = {i: ff(f"total_assets_q{i}") for i in range(9)}
    ttm0 = rev[0] + rev[1] + rev[2] + rev[3]
    ttm4 = rev[4] + rev[5] + rev[6] + rev[7]
    avgA0 = (ta[0] + ta[1] + ta[2] + ta[3]) / 4.0
    avgA4 = (ta[4] + ta[5] + ta[6] + ta[7]) / 4.0
    (safe(ttm0, avgA0) - safe(ttm4, avgA4)).astype("float32").to_parquet(CACHE / "f_ato_diff_a.parquet")
    beA0 = (ta[0] + ta[4]) / 2.0
    beA4 = (ta[4] + ta[8]) / 2.0
    (safe(ttm0, beA0) - safe(ttm4, beA4)).astype("float32").to_parquet(CACHE / "f_ato_diff_b.parquet")

    # --- industry aggregates (SW L1 as-of from the hot-fixed verify01 industry frame) ---
    ind = pd.read_parquet(CACHE01 / "industry.parquet").reindex(columns=insts) \
        .replace({"nan": np.nan, "None": np.nan})
    ni0, ni1, ni4 = ff("n_income_sq_q0"), ff("n_income_sq_q1"), ff("n_income_sq_q4")
    tmv = ff("total_mv")
    adjc = (P["close"] * P["adj_factor"])
    ret20 = adjc.ffill() / adjc.ffill().shift(20) - 1

    def ind_agg_broadcast(val: pd.DataFrame, weight: pd.DataFrame | None = None) -> pd.DataFrame:
        out = pd.DataFrame(np.nan, index=grid, columns=val.columns)
        for pday in grid:
            g = ind.loc[pday] if pday in ind.index else None
            if g is None or g.notna().sum() == 0:
                continue
            v = val.loc[pday]
            if weight is None:
                s = v.groupby(g).sum(min_count=3)
                out.loc[pday] = g.map(s).values
            else:
                w = weight.loc[pday]
                num = (v * w).groupby(g).sum(min_count=3)
                den = w.where(v.notna()).groupby(g).sum(min_count=3)
                out.loc[pday] = g.map(num / den.where(den > 0)).values
        return out

    # limit the expensive per-day loop to REBALANCE pdays only (the schedule reads pday rows)
    rebal = rebalance_grid()
    pmap = v7._pdays(rebal, grid)
    pdays = pd.DatetimeIndex(sorted(set(pmap.values())))
    sub = lambda fr: fr.loc[fr.index.isin(pdays)]  # noqa: E731
    ind_p = ind.loc[ind.index.isin(pdays)]

    def agg_on_pdays(val, weight=None):
        out = pd.DataFrame(np.nan, index=pdays, columns=val.columns)
        for pday in pdays:
            g = ind_p.loc[pday]
            v = val.loc[pday]
            if weight is None:
                s = v.groupby(g).sum(min_count=3)
                out.loc[pday] = g.map(s).values
            else:
                w = weight.loc[pday]
                num = (v * w).groupby(g).sum(min_count=3)
                den = w.where(v.notna()).groupby(g).sum(min_count=3)
                out.loc[pday] = g.map(num / den.where(den > 0)).values
        return out

    s0, s1, s4 = agg_on_pdays(ni0), agg_on_pdays(ni1), agg_on_pdays(ni4)
    safe(s0 - s4, s4.abs()).astype("float32").to_parquet(CACHE / "f_ind_np_yoy.parquet")
    safe(s0 - s1, s1.abs()).astype("float32").to_parquet(CACHE / "f_ind_np_qoq.parquet")
    agg_on_pdays(ret20, weight=tmv).astype("float32").to_parquet(CACHE / "f_ind_ret20.parquet")
    print("[b16] saved orgchg / rating_up / ato_diff_a+b / ind_np_yoy / ind_np_qoq / ind_ret20", flush=True)


def _load(ato="a"):
    cols = pd.read_parquet(CACHE01 / "e_close_raw.parquet").columns
    rd01 = lambda p: pd.read_parquet(CACHE01 / p).reindex(columns=cols)  # noqa: E731
    rd16 = lambda p: pd.read_parquet(CACHE / p).reindex(columns=cols)  # noqa: E731
    f = {"onmom250": rd01("f_onmom250_v2.parquet"), "onmom120": rd01("f_onmom120_v2.parquet"),
         "forecast": rd01("f_forecast_v2.parquet"), "orgchg": rd16("f_orgchg.parquet"),
         "rating_up": rd16("f_rating_up.parquet"), "ato_diff": rd16(f"f_ato_diff_{ato}.parquet"),
         "ind_np_yoy": rd16("f_ind_np_yoy.parquet"), "ind_np_qoq": rd16("f_ind_np_qoq.parquet"),
         "ind_ret20": rd16("f_ind_ret20.parquet")}
    e = {"close_raw": rd01("e_close_raw.parquet")}
    return f, e


def build_schedule(end="2026-02-27", headroom=25, ato="a"):
    f, e = _load(ato)
    close = e["close_raw"]
    grid = close.index
    insts = close.columns
    bounds = v7._bounds()
    rebal = rebalance_grid(end)
    pmap = v7._pdays(rebal, grid)
    sched = {}
    for d in rebal:
        pday = pmap.get(pd.Timestamp(d))
        if pday is None:
            sched[pd.Timestamp(d)] = []
            continue
        cr = close.loc[pday]
        listed = pd.Series([(bounds.get(str(c).upper()) is not None
                             and bounds[str(c).upper()][0] <= pday <= bounds[str(c).upper()][1])
                            for c in insts], index=insts)
        keep = listed & cr.notna()                    # 包含ST (no ST mask); 过滤停牌 via notna
        elig = keep[keep].index
        if len(elig) < headroom:
            sched[pd.Timestamp(d)] = []
            continue
        N = len(elig)
        parts = []
        for name, (w, di) in WEIGHTS.items():
            row = v7._row(f[name], pday).reindex(elig)
            rnk = row.rank(method="min", ascending=(di < 0), na_option="bottom")
            parts.append((N - rnk + 1) / N * 100.0 * w)
        comp = pd.concat(parts, axis=1).sum(axis=1) / (100.0 * TOTAL_W)
        top = comp.sort_values(ascending=False).head(headroom)
        sched[pd.Timestamp(d)] = [str(c).upper().replace("_", ".") for c in top.index]
    SCHED.write_text(json.dumps({str(k.date()): v for k, v in sched.items()}, ensure_ascii=False),
                     encoding="utf-8")
    print(f"[sched16-{ato}] {sum(1 for v in sched.values() if v)}/{len(rebal)} non-empty", flush=True)


XLSX_COLS = {
    "onmom250": "公式(SUM(IF(当日涨停标记=1,0,LOG(后复权开盘价/REF(后复权收盘价,1))),250)-SUM(IF(当日涨停标记=1,0,LOG(后复权开盘价/REF(后复权收盘价,1))),20))",
    "onmom120": "公式(SUM(IF(当日涨停标记=1,0,LOG(后复权开盘价/REF(后复权收盘价,1))),120)-SUM(IF(当日涨停标记=1,0,LOG(后复权开盘价/REF(后复权收盘价,1))),20))",
    "orgchg": "公式(%(评级机构数,REF(评级机构数,60)))",
    "forecast": "业绩预告净利润QGr%PYQ_v1",
    "rating_up": "评级调高家数",
    "ato_diff_a": "AssetTurnoverDiffPY", "ato_diff_b": "AssetTurnoverDiffPY",
    "ind_np_yoy": "行业净利润增长", "ind_np_qoq": "行业净利润环比增长", "ind_ret20": "行业N日涨幅(20)"}


def factor_parity(end="2026-02-27"):
    cols = pd.read_parquet(CACHE01 / "e_close_raw.parquet").columns
    frames = {}
    for k in XLSX_COLS:
        base = CACHE01 if k in ("onmom250", "onmom120", "forecast") else CACHE
        name = {"onmom250": "f_onmom250_v2", "onmom120": "f_onmom120_v2", "forecast": "f_forecast_v2"} \
            .get(k, f"f_{k}")
        p = base / f"{name}.parquet"
        if p.exists():
            frames[k] = pd.read_parquet(p).reindex(columns=cols)
    h = pd.read_excel(XLSX, sheet_name="各阶段持仓详单")
    h["start"] = pd.to_datetime(h["开始日期"], errors="coerce")
    h = h[h["start"].notna() & (h["start"] <= pd.Timestamp(end))].copy()
    h["code"] = h["股票代码"].astype(str).str.zfill(6)
    grid = pd.read_parquet(CACHE01 / "e_close_raw.parquet").index
    up = {str(c).split("_")[0]: c for c in cols}
    recs = {k: [] for k in frames}
    for d, grp in h.groupby("start"):
        pos = grid.searchsorted(pd.Timestamp(d))
        if pos == 0:
            continue
        pday = grid[pos - 1]
        for _, r in grp.iterrows():
            inst = up.get(r["code"])
            if inst is None:
                continue
            for k, fr in frames.items():
                gv = pd.to_numeric(r.get(XLSX_COLS[k]), errors="coerce")
                lv = v7._row(fr, pday).get(inst, np.nan)
                if pd.notna(gv) and pd.notna(lv):
                    recs[k].append((float(gv), float(lv)))
    print(f"\n=== #16 per-factor value agreement vs xlsx (held names) ===")
    for k, pairs in recs.items():
        if not pairs:
            print(f"  {k:12} NO DATA")
            continue
        a = pd.DataFrame(pairs, columns=["g", "l"])
        rel = ((a["l"] - a["g"]).abs() / a["g"].abs().clip(lower=1e-9)).median()
        sign = (np.sign(a["l"]) == np.sign(a["g"])).mean()
        sp = a["g"].corr(a["l"], method="spearman")
        print(f"  {k:12} n={len(a):6d}  medRel={rel:8.4f}  sign={sign:.3f}  sp={sp:+.3f}")


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
        net_name, label = "verify16_replay_net.parquet", "REPLAY(果仁持仓+权重)"
    else:
        sched = {pd.Timestamp(k): v for k, v in json.loads(SCHED.read_text(encoding="utf-8")).items()}
        strat = ModelIIPosProfitStrategy(sched, buy_rank=20, sell_rank=20, target_n=10, pos_max=0.15,
                                         max_holds=20, use_exits=False, rebuy_cooldown=0)
        net_name, label = "verify16_net.parquet", "LOCAL selection (12/13w)"
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
    print(f"  #16 成长_隔夜动量@周期 [{label}]  CAGR={m['cagr']:+.2%}  MDD={m['mdd']:+.2%}  "
          f"(果仁 +27.76% / −53.97)")
    for y in sorted(yr.index):
        g = gy.get(int(y))
        gt = f"{g:+8.1%}" if g is not None else "   n/a "
        dt = f"{float(yr[y]) - g:+7.1%}" if g is not None else ""
        print(f"  {int(y)}   {float(yr[y]):+8.1%}  {gt}  {dt}")
    json.dump({"cagr": m["cagr"], "mdd": m["mdd"], "yearly": {int(k): float(v) for k, v in yr.items()},
               "guorn_yearly": gy, "replay": replay},
              open(OUT / ("verify16_replay_result.json" if replay else "verify16_result.json"),
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
        my_book = [code6(c) for c in lst[:10]]
        prec = float(np.mean([c in held for c in my_book])) if my_book else np.nan
        rows.append(dict(date=d, in10=float(np.mean([r <= 10 for r in rks])),
                         in20=float(np.mean([r <= 20 for r in rks])), precision=prec))
    df = pd.DataFrame(rows)
    df["year"] = df["date"].dt.year
    print("\n=== #16 tracking ===")
    print(df[["in10", "in20", "precision"]].mean().round(3).to_string())
    print(df.groupby("year")[["in10", "in20", "precision"]].mean().round(3).to_string())


def main():
    ap = argparse.ArgumentParser()
    for flag in ("build", "schedule", "factor-parity", "run", "replay", "compare"):
        ap.add_argument(f"--{flag}", action="store_true")
    ap.add_argument("--end", default="2026-02-27")
    ap.add_argument("--ato", default="a", choices=("a", "b"))
    a = ap.parse_args()
    if a.build:
        build()
    if a.schedule:
        build_schedule(a.end, ato=a.ato)
    if a.factor_parity:
        factor_parity(a.end)
    if a.run:
        run(end=a.end)
    if a.replay:
        run(end=a.end, replay=True)
    if a.compare:
        compare(a.end)


if __name__ == "__main__":
    main()
