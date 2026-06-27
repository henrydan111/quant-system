"""果仁 deployed-20 verification — strategy #5: sm_双创研发强度_v1 (nn=10, xlsx 10).

GREEN deployed book — R&D-intensity small-cap on the 双创 universe (创业板 + 科创板). 果仁 = trusted benchmark;
the LOCAL construction layer is under test. This is the HEAVIEST-omission GREEN book: 9 of 16 ranking
weight-units (incl. the w=2 namesake R&D-growth term) are OMITTED, leaving a 7/16-weight reproducible core.
Every omission is decided from the provider field probe (_guorn_garp_field_probe.py), not assumed (rule #10):

  KEEP (7 terms, Σw=7):
    总市值 w1 ↓small        = $total_mv (全部)
    股价振幅%当日成交额10日 w1 = MA(((high−low)/pre_close)/(amount/1e5), 10)   (ILLIQ-10d, rung-4)
    RND%Assets w1          = TTM(rd)/AvgQ(资产总计,4) = Σrd_sq_q0..3 / mean(total_assets_q0..3)  (rung-6 penny)
    研发销售比率 w1         = TTM(rd)/TTM(营收) = Σrd_sq_q0..3 / Σrev_sq_q0..3   (= #6's rndsales)
    RoeQ w1                = ifnull(扣非净利润单季, 净利润单季)/资产总计单季 = profit_dedt_sq0(↛n_income_sq0)/total_assets_q0
    ROETTMDiffPQ w1        = TTM-ROE(q0)−TTM-ROE(q1)                          (#1 mapping)
    业绩预告净利润QGr%PYQ_v1 w1 = $forecast__np_q_yoy                          (rung-3)

  OMIT (8 terms, Σw=9) — measured-impossible / quarantine / irreducible:
    RnDTTMGr%PY w2 — (TTM(rd,0)−TTM(rd,4))/|TTM(rd,4)| needs rd_sq q4..q7 (≥8 quarters); provider depth = q0..q4
                     (probe). The w=2 NAMESAKE R&D-GROWTH term — the single largest omission for this book.
    评级调高家数 w1 — report_rc rating_up: NEW quarantine consensus data, owned by a parallel session — DO NOT USE.
    10日融资偿还金额 w1 — margin repayment $rzche: QUARANTINE (CLAUDE.md §3.4 — only repayment fields blocked).
    机构持股比例 w1 / 管理层持股比例 w1 — institution / management holding %: not materialized.
    财报预约公布天数 w1 — 预约披露 disclosure-schedule calendar: not ingested (not a validated data path).
    未来60日新增流通股数 w1 — future-shares: reproducing with realized shares = LOOKAHEAD (skip, like 未来20日…).
    BP带壳01 w1 — 壳价值 (AH-premium regression): irreducible.

  filter      : 退市风险(≈price≥2+ST) + 交易天数>5 + 5日&20日成交额>0.05亿 + 20日换手率 rank≤99% (drop top-1% turnover).
                [重大违规 skip — irreducible.]
  trade model : 模型II daily, 09:35≈open fill, 个股仓位 14–26% (理想20% → ~5 holds, max ~7), 备选买入=5,
                sell 排名≥20, 不卖 涨停 (hold_on_limit_up) + 选股日停牌. NO price exits, NO cooldown.
                cost 0.2%/side, total return.

⚠ Expect a LARGER residual than the 成长 cluster: the kept core is 总市值 + R&D-LEVEL (RND%Assets / 研发销售比率)
+ quality (RoeQ / ROETTMDiff) + forecast — faithfully the "研发强度" theme, but the dominant R&D-GROWTH driver
(RnDTTMGr%PY, w=2) and the rating/holding factors are gone, so the selection overlap is a floor, not a ceiling.
LAYER DISCIPLINE (§8.1): all 7 terms are scope=全部 (no 一级行业内 → no industry frame). NON-FORMAL artifact.
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
CACHE = OUT / "verify05_cache"
CACHE.mkdir(parents=True, exist_ok=True)
SCHED = OUT / "verify05_schedule.json"
PROVIDER_URI = str(ROOT / "data" / "qlib_data")
from guorn_universe import in_guorn_universe, SHUANGCHUANG  # noqa: E402  (board_of()-based 双创=创业板+科创板)
XLSX = ROOT / "Knowledge" / "果仁回测结果" / "10_sm_双创研发强度_v1.xlsx"
GR = dict(annual=0.6267, sharpe=1.54, mdd=0.6095, vol=0.3805, excess=0.2019)

# term -> (weight, dir): +1 从大到小, -1 从小到大. ALL scope=全部.
WEIGHTS = {"mktcap": (1, -1), "illiq10": (1, +1), "rnd_assets": (1, +1), "rndsales": (1, +1),
           "roeq": (1, +1), "ROETTMDiff": (1, +1), "forecast": (1, +1)}
TOTAL_W = sum(w for w, _ in WEIGHTS.values())   # = 7
OMITTED = [
    "RnDTTMGr%PY (w=2, namesake R&D-growth) — (TTM(rd,0)−TTM(rd,4))/|TTM(rd,4)| needs rd_sq q4..q7; depth = q0..q4",
    "评级调高家数 — report_rc rating_up: NEW quarantine consensus data (parallel session) — DO NOT USE",
    "10日融资偿还金额 — margin repayment $rzche: QUARANTINE",
    "机构持股比例 / 管理层持股比例 — institution / management holding %: not materialized",
    "财报预约公布天数 — 预约披露 disclosure-schedule calendar: not ingested",
    "未来60日新增流通股数 — future-shares: realized shares = lookahead (skip)",
    "BP带壳01 — 壳价值 (AH-premium regression): irreducible",
]

_Q = lambda b, qs: [f"${b}_sq_q{i}" for i in qs]                          # noqa: E731
FIELDS = sorted(set(
    ["$total_mv", "$circ_mv", "$close", "$open", "$high", "$low", "$pre_close", "$amount",
     "$adj_factor", "$limit_status", "$forecast__np_q_yoy"]
    + _Q("revenue", (0, 1, 2, 3)) + _Q("rd_exp", (0, 1, 2, 3)) + _Q("n_income", (0,)) + _Q("profit_dedt", (0,))
    + _Q("n_income_attr_p", (0, 1, 2, 3, 4))
    + ["$total_assets_q0", "$total_assets_q1", "$total_assets_q2", "$total_assets_q3",
       "$total_hldr_eqy_exc_min_int_q0", "$total_hldr_eqy_exc_min_int_q1"]
))


def _load_listed_bounds() -> dict:
    p = ROOT / "data" / "qlib_data" / "instruments" / "all_stocks.txt"
    df = pd.read_csv(p, sep="\t", header=None, names=["code", "start", "end"], dtype=str)
    return {str(r.code).upper(): (pd.Timestamp(r.start), pd.Timestamp(r.end)) for r in df.itertuples(index=False)}


LISTED_BOUNDS = _load_listed_bounds()


def _in_universe(c: str) -> bool:
    return in_guorn_universe(c, boards=SHUANGCHUANG)             # 双创 = 创业板 + 科创板 (chinext + star)


def build(start: str, end: str):
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=PROVIDER_URI, region=REG_CN, kernels=1)
    allinsts = D.list_instruments(D.instruments("all"), start_time=start, end_time=end, as_list=True)
    insts = sorted(c for c in allinsts if _in_universe(c))
    print(f"[build05] {len(insts)} 双创 insts; pulling {len(FIELDS)} fields {start}..{end}", flush=True)
    fetch_start = (pd.Timestamp(start) - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    P = {}
    for k in range(0, len(FIELDS), 6):
        batch = FIELDS[k:k + 6]
        df = D.features(insts, batch, start_time=fetch_start, end_time=end, freq="day")
        for col in batch:
            P[col.replace("$", "")] = df[col].unstack(level=0).sort_index()
        print(f"[build05]   {min(k + 6, len(FIELDS))}/{len(FIELDS)}", flush=True)
        del df
    idx = P["close"].index
    EPS = 1e-9

    def safe(num, den):
        return (num / den.where(den.abs() > EPS)).replace([np.inf, -np.inf], np.nan)

    def ff(name):
        return P[name].reindex(idx).ffill()

    ttm_rd = sum(ff(f"rd_exp_sq_q{q}") for q in range(4))
    ttm_rev = sum(ff(f"revenue_sq_q{q}") for q in range(4))
    avg_assets = sum(ff(f"total_assets_q{q}") for q in range(4)) / 4.0
    ni = {q: ff(f"n_income_attr_p_sq_q{q}") for q in range(5)}

    factors = {}
    factors["mktcap"] = P["total_mv"].reindex(idx).ffill()
    amplitude = safe(P["high"] - P["low"], P["pre_close"])
    amt_yi = P["amount"] / 1e5
    factors["illiq10"] = safe(amplitude, amt_yi).rolling(10, min_periods=5).mean()
    factors["rnd_assets"] = safe(ttm_rd, avg_assets)                     # RND%Assets = TTM(rd)/AvgQ(assets,4)
    factors["rndsales"] = safe(ttm_rd, ttm_rev)                          # 研发销售比率 = TTM(rd)/TTM(rev)
    factors["roeq"] = safe(ff("profit_dedt_sq_q0").fillna(ff("n_income_sq_q0")), ff("total_assets_q0"))
    roe0 = safe(ni[0] + ni[1] + ni[2] + ni[3], ff("total_hldr_eqy_exc_min_int_q0"))
    roe1 = safe(ni[1] + ni[2] + ni[3] + ni[4], ff("total_hldr_eqy_exc_min_int_q1"))
    factors["ROETTMDiff"] = roe0 - roe1
    factors["forecast"] = ff("forecast__np_q_yoy")

    # eligibility: turnover20 (换手率 ~ amount/circ_mv), amount, close
    turn = safe(P["amount"], P["circ_mv"])
    elig = {"close_raw": P["close"], "amt": P["amount"], "turn20": turn.rolling(20, min_periods=5).mean()}

    for name, fr in factors.items():
        fr.reindex(idx).astype("float32").to_parquet(CACHE / f"f_{name}.parquet")
    for name, fr in elig.items():
        fr.reindex(idx).astype("float32").to_parquet(CACHE / f"e_{name}.parquet")
    (CACHE / "meta.json").write_text(json.dumps({"start": start, "end": end, "n_insts": len(insts)}), encoding="utf-8")
    print("[build05] factor coverage (frac non-NaN over the grid):", flush=True)
    for name, fr in factors.items():
        print(f"    {name:14} cov={fr.reindex(idx).notna().mean().mean():.3f}", flush=True)
    print(f"[build05] cached -> {CACHE}", flush=True)


def _load():
    f = {n: pd.read_parquet(CACHE / f"f_{n}.parquet") for n in WEIGHTS}
    e = {n: pd.read_parquet(CACHE / f"e_{n}.parquet") for n in ("close_raw", "amt", "turn20")}
    return f, e


def _composite_row(f, pday, elig_idx):
    """果仁-exact composite (§3.1.4), all scope=全部: 排名分=(N−rank+1)/N×100 (NaN→bottom), 综合=Σ(排名分×w)."""
    N = len(elig_idx)
    parts = []
    for name, (w, d) in WEIGHTS.items():
        row = f[name].loc[pday].reindex(elig_idx)
        rnk = row.rank(method="min", ascending=(d < 0), na_option="bottom")
        parts.append((N - rnk + 1) / N * 100.0 * w)
    return pd.concat(parts, axis=1).sum(axis=1) / (100.0 * TOTAL_W)


def build_schedule(start, end, headroom=20):   # headroom>=20 so sell-band (rank≥20) is resolvable
    f, e = _load()
    cal = ru.trading_calendar()
    cal = cal[(cal >= pd.Timestamp(start)) & (cal <= pd.Timestamp(end))]
    close_raw, amt, turn20 = e["close_raw"], e["amt"], e["turn20"]
    amt5 = amt.rolling(5, min_periods=1).mean(); amt20 = amt.rolling(20, min_periods=1).mean()
    hist = close_raw.notna().rolling(10, min_periods=1).sum()
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
        keep &= (amt5.loc[pday] > 5000.0) & (amt20.loc[pday] > 5000.0)   # 5日&20日成交额>0.05亿
        keep &= hist.loc[pday] >= 5                                      # 交易天数>5 (proxy)
        ok = []
        for c in insts:
            b = LISTED_BOUNDS.get(c.upper())
            ok.append(c.upper() not in st and b is not None and b[0] <= pday <= b[1])
        keep &= pd.Series(ok, index=insts)
        # 20日换手率 排名%最小 99%: drop the top-1% most-active names (rank within the kept set)
        elig0 = keep[keep].index
        tr = turn20.loc[pday].reindex(elig0)
        keep_turn = tr.rank(pct=True, na_option="top") <= 0.99
        elig_names = keep_turn[keep_turn].index
        if len(elig_names) < headroom:
            sched[d] = []; continue
        comp = _composite_row(f, pday, elig_names).dropna()
        top = comp.sort_values(ascending=False).head(headroom)
        sched[d] = [str(c).upper().replace("_", ".") for c in top.index]
        members[d] = set(list(top.index)[:5])
    keys = sorted(members)
    churn = [len(members[keys[i]] - members[keys[i - 1]]) / max(len(members[keys[i]]), 1)
             for i in range(1, len(keys)) if members[keys[i]]]
    SCHED.write_text(json.dumps({str(k.date()): v for k, v in sched.items()}, ensure_ascii=False), encoding="utf-8")
    nonempty = sum(1 for v in sched.values() if v)
    print(f"[sched05] {nonempty}/{len(cal)} non-empty; mean top5 churn/day={np.mean(churn) if churn else float('nan'):.3f}; saved", flush=True)


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


def run(start, end):
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    sched = {pd.Timestamp(k): v for k, v in json.loads(SCHED.read_text(encoding="utf-8")).items()}
    # #5 模型II: 个股仓位 14–26% (理想20% → ~5 holds, max ~7), sell 排名≥20, 备选=5, exits OFF, no cooldown.
    strat = ModelIIPosProfitStrategy(sched, buy_rank=5, sell_rank=20, target_n=5, pos_max=0.26,
                                     max_holds=7, use_exits=False, rebuy_cooldown=0)
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
    net.to_frame("net").to_parquet(OUT / "verify05_net.parquet")
    m = ru.goal_metrics(net); m["sharpe_rf4"] = ru.sharpe(net, rf=0.04)
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    yearly = {int(y): float(v) for y, v in yr.items()}
    gy = _read_guorn_yearly()
    print("\n" + "=" * 74)
    print("  #5 sm_双创研发强度_v1 — LOCAL vs 果仁 (daily model-II, 0.2%/side; 9/16 weight OMITTED incl w=2 RnDTTMGr)")
    print(f"  LOCAL  annual≈{m['cagr']:+.2%}  Sharpe(rf4%)={m['sharpe_rf4']:.2f}  MDD={m['mdd']:+.2%}  vol={m['ann_vol']:.2%}")
    print(f"  果仁   annual={GR['annual']:+.2%}  Sharpe={GR['sharpe']:.2f}  MDD={-GR['mdd']:+.2%}  vol={GR['vol']:.2%}")
    print("  year     LOCAL      果仁     diff")
    for y in sorted(yearly):
        g = gy.get(y); gtxt = f"{g:+7.1%}" if g is not None else "   n/a "
        print(f"  {y}   {yearly[y]:+8.1%}  {gtxt}  {(f'{yearly[y]-g:+7.1%}') if g is not None else ''}")
    (OUT / "verify05_result.json").write_text(json.dumps(
        dict(local=m, local_yearly=yearly, guoren=GR, guoren_yearly=gy, start=start, end=end,
             kept_terms=list(WEIGHTS), kept_weight=TOTAL_W, total_recipe_weight=16, omitted=OMITTED),
        indent=2, default=str), encoding="utf-8")
    print("\nNON-FORMAL PARITY ARTIFACT — validates #5 construction vs 果仁; NOT sealed/deployable.")


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
