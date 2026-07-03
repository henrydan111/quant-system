"""果仁 deployed-20 verification — strategy #17: 成长_高波@周期 (nn=48, xlsx 48).

SCRIPT_STATUS: Class-B parity diagnostic (2026-07-03). THIN harness on the #16 machinery (same universe:
main+中小+创业板 incl ST, verify01_cache grid/insts; verify16_cache report_rc/ATO/行业 frames REUSED).

Recipe (deployed_20_recipes.md #17): filters = 历史贝塔 排名%区间 0%-30% (keep TOP 30% high-beta;
fix-1 semantics: 区间 0-X% keeps rank-pct ≤ X in 从大到小 order) · 公式(%(预期净利润1年,REF(预期净利润1年,60)))
排名%区间 0%-50% (top half by 60d consensus-upgrade momentum; np_fy1 vendor-approx, pre-2022 backfill
documented) · 未来20日新增流通股<1% [OMITTED]. Rankings (9, Σw=9; 8/9 kept — 净利润−预期净利润Q OMITTED,
no quarterly consensus): orgchg · forecast(alive-window) · rating_up · AssetTurnoverDiffPY(caliber A,
registry #13) · 行业净利润增长/环比 · 行业N日涨幅(20) · CoreProfitQGr%PY (fix-11 0-fill, built here).
Trade: Model II 调仓周期=5 (xlsx grid), 09:35, 5-15% band (~10 holds, max 20), 备选5, sell 排名≥20,
涨停不卖+选股日停牌, no exits. 果仁 +29.46% / −65.50.
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

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
CACHE01 = OUT / "verify01_cache"
CACHE16 = OUT / "verify16_cache"
CACHE = OUT / "verify17_cache"
CACHE.mkdir(parents=True, exist_ok=True)
SCHED = OUT / "verify17_schedule.json"
XLSX = ROOT / "Knowledge" / "果仁回测结果" / "48_成长_高波@周期.xlsx"

WEIGHTS = {"orgchg": (1, +1), "forecast": (1, +1), "rating_up": (1, +1), "ato_diff": (1, +1),
           "ind_np_yoy": (1, +1), "ind_np_qoq": (1, +1), "ind_ret20": (1, +1),
           "CoreProfitQGr": (1, +1)}      # 净利润−预期净利润Q w1 OMITTED → 8/9
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
    fields = (["$report_rc__np_fy1", "$adj_factor", "$close"]
              + [f"${b}_sq_q{i}" for b in ("revenue", "oper_cost", "admin_exp", "sell_exp", "fin_exp",
                                           "biz_tax_surchg") for i in (0, 4)])
    P = {}
    for k in range(0, len(fields), 5):
        batch = fields[k:k + 5]
        df = D.features(insts, batch, start_time=str(grid[0].date()), end_time=str(grid[-1].date()), freq="day")
        for c in batch:
            P[c.replace("$", "")] = (df[c].unstack(level=0).sort_index().reindex(grid)
                                     .reindex(columns=insts))
        print(f"[b17] {min(k+5, len(fields))}/{len(fields)}", flush=True)
        del df
    EPS = 1e-9
    safe = lambda n, d: (n / d.where(d.abs() > EPS)).replace([np.inf, -np.inf], np.nan)  # noqa: E731
    zc = lambda fr: fr.fillna(0.0)  # noqa: E731
    ff = lambda n: P[n].ffill()  # noqa: E731
    npf = ff("report_rc__np_fy1")
    safe(npf, npf.shift(60)).astype("float32").to_parquet(CACHE / "e_npf_chg60.parquet")
    core = lambda qq: (ff(f"revenue_sq_q{qq}") - zc(ff(f"oper_cost_sq_q{qq}"))  # noqa: E731
                       - (zc(ff(f"admin_exp_sq_q{qq}")) + zc(ff(f"sell_exp_sq_q{qq}"))
                          + zc(ff(f"fin_exp_sq_q{qq}"))) - zc(ff(f"biz_tax_surchg_sq_q{qq}")))
    c0, c4 = core(0), core(4)
    safe(c0 - c4, c4.abs()).astype("float32").to_parquet(CACHE / "f_CoreProfitQGr.parquet")
    # 历史贝塔: 250d slope of stock simple returns on 000300 simple returns (v7-validated caliber)
    adjc = (P["close"] * P["adj_factor"]).ffill()
    r = adjc.pct_change(fill_method=None)
    idxdf = D.features(["000300_SH"], ["$close"], start_time=str(grid[0].date()),
                       end_time=str(grid[-1].date()), freq="day")
    x = (idxdf.reset_index(level=0, drop=True)["$close"].sort_index().reindex(grid)
         .pct_change(fill_method=None))
    n, minp = 250, 200
    valid = r.notna() & x.notna().values[:, None]
    xm = pd.DataFrame(np.where(valid, np.broadcast_to(x.values[:, None], r.shape), np.nan),
                      index=r.index, columns=r.columns)
    rm = r.where(valid)
    cnt = valid.rolling(n, min_periods=1).sum()
    sx = xm.rolling(n, min_periods=minp).sum()
    sy = rm.rolling(n, min_periods=minp).sum()
    sxy = (rm * xm).rolling(n, min_periods=minp).sum()
    sxx = (xm ** 2).rolling(n, min_periods=minp).sum()
    cov = sxy - sx * sy / cnt
    var = sxx - sx ** 2 / cnt
    listed_days = adjc.notna().cumsum()
    beta = (cov / var.where(var.abs() > 1e-12)).where((cnt >= minp) & (listed_days >= n))
    beta.astype("float32").to_parquet(CACHE / "e_beta.parquet")
    print("[b17] saved npf_chg60 / CoreProfitQGr(0fill) / beta", flush=True)


def _load():
    cols = pd.read_parquet(CACHE01 / "e_close_raw.parquet").columns
    rd = lambda base, p: pd.read_parquet(base / p).reindex(columns=cols)  # noqa: E731
    f = {"orgchg": rd(CACHE16, "f_orgchg.parquet"), "forecast": rd(CACHE01, "f_forecast_v2.parquet"),
         "rating_up": rd(CACHE16, "f_rating_up.parquet"), "ato_diff": rd(CACHE16, "f_ato_diff_a.parquet"),
         "ind_np_yoy": rd(CACHE16, "f_ind_np_yoy.parquet"), "ind_np_qoq": rd(CACHE16, "f_ind_np_qoq.parquet"),
         "ind_ret20": rd(CACHE16, "f_ind_ret20.parquet"), "CoreProfitQGr": rd(CACHE, "f_CoreProfitQGr.parquet")}
    e = {"close_raw": rd(CACHE01, "e_close_raw.parquet"), "beta": rd(CACHE, "e_beta.parquet"),
         "npf_chg60": rd(CACHE, "e_npf_chg60.parquet")}
    return f, e


def build_schedule(end="2026-02-27", headroom=25):
    f, e = _load()
    close = e["close_raw"]
    grid = close.index
    insts = close.columns
    bounds = v7._bounds()
    rebal = rebalance_grid(end)
    pmap = v7._pdays(rebal, grid)
    # NOTE: #16's ind_* frames exist only on #16's 20d pdays -> for #17's 5d grid use as-of rows (v7._row)
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
        rank_base = listed & cr.notna()                                 # 包含ST
        keep = rank_base.copy()
        bpct = e["beta"].loc[pday].where(rank_base).rank(pct=True, ascending=False)
        keep &= (bpct <= 0.30).fillna(False)                            # 历史贝塔 区间 0-30% = TOP 30% beta
        npct = v7._row(e["npf_chg60"], pday).where(rank_base).rank(pct=True, ascending=False)
        keep &= (npct <= 0.50).fillna(False)                            # consensus-upgrade top half
        elig = keep[keep].index
        if len(elig) < 20:
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
    print(f"[sched17] {sum(1 for v in sched.values() if v)}/{len(rebal)} non-empty", flush=True)


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
        t = pd.read_excel(XLSX, sheet_name="调仓详情")
        t["d"] = pd.to_datetime(t["开始日期"], errors="coerce")
        for _, r in t.iterrows():
            if pd.notna(r["d"]) and r["d"] <= pd.Timestamp(end) and int(r["股票只数"]) == 0:
                sched.setdefault(str(r["d"].date()), [])
        strat = v7.ModelIDivLowVolStrategy(sched, max_holds=99, weights_mode="explicit")
        net_name, label = "verify17_replay_net.parquet", "REPLAY(果仁持仓+权重)"
    else:
        sched = {pd.Timestamp(k): v for k, v in json.loads(SCHED.read_text(encoding="utf-8")).items()}
        strat = ModelIIPosProfitStrategy(sched, buy_rank=20, sell_rank=20, target_n=10, pos_max=0.15,
                                         max_holds=20, use_exits=False, rebuy_cooldown=0)
        net_name, label = "verify17_net.parquet", "LOCAL selection (8/9w)"
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
    print(f"  #17 成长_高波@周期 [{label}]  CAGR={m['cagr']:+.2%}  MDD={m['mdd']:+.2%}  (果仁 +29.46% / −65.50)")
    for y in sorted(yr.index):
        g = gy.get(int(y))
        gt = f"{g:+8.1%}" if g is not None else "   n/a "
        dt = f"{float(yr[y]) - g:+7.1%}" if g is not None else ""
        print(f"  {int(y)}   {float(yr[y]):+8.1%}  {gt}  {dt}")
    json.dump({"cagr": m["cagr"], "mdd": m["mdd"], "yearly": {int(k): float(v) for k, v in yr.items()},
               "guorn_yearly": gy, "replay": replay},
              open(OUT / ("verify17_replay_result.json" if replay else "verify17_result.json"),
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
    print("\n=== #17 tracking ===")
    print(df[["in10", "in20"]].mean().round(3).to_string())
    print(df.groupby("year")[["in10", "in20"]].mean().round(3).to_string())


def main():
    ap = argparse.ArgumentParser()
    for flag in ("build", "schedule", "run", "replay", "compare"):
        ap.add_argument(f"--{flag}", action="store_true")
    ap.add_argument("--end", default="2026-02-27")
    a = ap.parse_args()
    if a.build:
        build()
    if a.schedule:
        build_schedule(a.end)
    if a.run:
        run(end=a.end)
    if a.replay:
        run(end=a.end, replay=True)
    if a.compare:
        compare(a.end)


if __name__ == "__main__":
    main()
