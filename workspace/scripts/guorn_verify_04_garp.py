"""果仁 deployed-20 verification — strategy #4: sm_GARP_illiq (nn=9, xlsx 09).

Fourth GREEN deployed book. 果仁 = trusted benchmark; the LOCAL construction layer is under test.
GARP (growth-at-a-reasonable-price) micro/small-cap book on 沪深 main+中小板+创业板 (− ST − 科创板 − 北证),
filtered to the more-liquid 65% by ILLIQ(5). The build universe additionally INCLUDES 科创板 (688/689) so the
GARP factor frames can be REUSED verbatim by #15 (成长_双创_GARP@周期, the same factor base on the 双创 universe);
#4's Layer-2 mask drops 科创板, #15's keeps only 创业板+科创板.

Recipe (deployed_20_recipes.md #4): 23 ranking terms (weights non-uniform; 2 terms w=2). The book is HEAVY on
irreducible/depth-unavailable factors — 12 of 23 weight-units (48%) are OMITTED with documentation, leaving the
faithful reproducible GARP core (13/25 weight). EVERY omission was decided from a PROVIDER FIELD PROBE
(_guorn_garp_field_probe.py), not the registry list (CLAUDE.md rule #10):

  KEEP (11 terms, Σw=13) — all rung-1..5 validated mappings:
    SalesQGr%PY w1            = (rev_sq0−rev_sq4)/|rev_sq0|                         (rung-4 penny-exact)
    营收单季环比−营收单季同比 w1  = (rev_sq0−rev_sq1)/|rev_sq1| − (rev_sq0−rev_sq4)/|rev_sq4|  (果仁 builtin QoQ−YoY)
    CoreProfitQGr%PY w2       = (core_q0−core_q4)/|core_q4|, core=rev−cost−(adm+sell+fin)−biztax (rung-5 penny)
    所得税费用QGr%PY w1        = (it_sq0−it_sq4)/|it_sq0|                            (income_tax_sq, probe 100%)
    RnDQGR%PY w1              = (rd_sq0−rd_sq4)/rd_sq4                              (rung-5, 0.63% med)
    ROETTMDiffPQ w2          = TTM-ROE(q0)−TTM-ROE(q1) = ΔQoQ Σni_attr_p/equity     (#1 mapping)
    EpsExclXorQGr%PY w1       = (profit_dedt_sq0−profit_dedt_sq4)/|profit_dedt_sq4| (#1 mapping)
    营业收入(单季)/总市值 w1 行业内 = rev_sq0/total_mv  (sales-yield, 一级行业内)
    GrossProfit%AssetsQ w1    = (rev_sq0−cost_sq0)/total_assets_q0                  (rung-4 penny-exact)
    总市值 w1 ↓small          = $total_mv  (全部)
    业绩预告净利润QGr%PYQ_v1 w1 ↑ = $forecast__np_q_yoy  (rung-3; NOTE dir=从大到小 here, unlike #1's 从小到大)

  OMIT (12 terms, Σw=12) — measured-impossible, documented:
    3 中性化 (BP筹资市值比调整, 标准化中性化MI(RNDQP), 中性化(EPCOREPROFITQ,总市值)) — HNeutralize regression, irreducible
    业绩快报归母净利QGr%PY — 快报 (express) not materialized
    波动率_季度指标(CoreProfitQGr%PY,12) — StdevQ over 12 quarters; provider single-q depth = q0..q4 only (probe)
    EBITDAQ%EV + (rev−cost)/EV — NO EV field in provider (probe: $ev/$ev_ttm/$enterprise_value all absent);
                                 EBITDAQ also needs D&A single-q (probe 0% — semi-annual disclosure cadence)
    FCFQ_重算Gr%PYQ + FCFQ%总市值 — FCFQ needs D&A single-q (0%) + 处置FIOLTA单季 (absent)
    营收增长−营收3年复合增长, CoreProfitQGr%PQ−CoreProfitTTMGr%PY, CoreProfitTTMGr%PY−%3Y — TTM-YoY/3yr need
                                 single-q depth q4..q7 (= ≥8 quarters); provider has only q0..q4 (probe)

  trade model : 模型II daily, 09:31≈open fill, 个股仓位 7–13% (理想10% → ~10 holds, max ~14), 备选买入=5,
                sell 排名≥20, buy 调仓日非跌停 (engine limit gate), 不卖 涨停 (hold_on_limit_up) + 选股日停牌.
                NO 价格 exits, NO rebuy-cooldown. cost 0.2%/side, total return.
  filter      : ILLIQ(5) rank 0–65% (keep the more-liquid 65%) + 退市风险(≈price≥2+ST) + 上市天数>30. [未来流通股 skip]

LAYER DISCIPLINE (§8.1): factor VALUES are computed on the full build universe (Layer-1, universe-agnostic);
the cross-sectional RANK + ILLIQ-65% gate + 科创板-exclusion happen inside the eligible set at schedule time
(Layer-2/3). Industry frame for the 一级行业内 sales-yield term = the canonical PIT-safe resolver
build_industry_series_asof (NEVER the all-NaN $sw2021_l1 field — 2026-06-26 #1/#2/#6 bug).

NON-FORMAL parity artifact (metadata-stamped). Reuses ModelIIPosProfitStrategy + the 成长-cluster cache pattern.
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
CACHE = OUT / "verify04_cache"                       # shared with #15 (双创 GARP@周期)
CACHE.mkdir(parents=True, exist_ok=True)
SCHED = OUT / "verify04_schedule.json"
PROVIDER_URI = str(ROOT / "data" / "qlib_data")
# build on main+中小板+创业板+科创板 (so #15 can reuse); #4 masks 科创板 OUT at schedule time
from guorn_universe import in_guorn_universe  # noqa: E402  (board_of()-based; build=incl 科创板, #4 mask=excl 科创板)
XLSX = ROOT / "Knowledge" / "果仁回测结果" / "09_sm_GARP_illiq.xlsx"
GR = dict(annual=0.4959, sharpe=1.54, mdd=0.4245, vol=0.296, excess=0.1052)

# term -> (weight, dir, scope): dir +1=从大到小 (larger better), -1=从小到大; scope "all"=全部, "ind"=一级行业内
WEIGHTS = {
    "SalesQGr":           (1, +1, "all"),
    "revQoQ_minus_YoY":   (1, +1, "all"),
    "CoreProfitQGr":      (2, +1, "all"),
    "incometaxQGr":       (1, +1, "all"),
    "RnDQGR":             (1, +1, "all"),
    "ROETTMDiff":         (2, +1, "all"),
    "EpsExclXorGr":       (1, +1, "all"),
    "salesyield":         (1, +1, "ind"),   # 营业收入(单季)/总市值, 一级行业内
    "GrossProfitAssetsQ": (1, +1, "all"),
    "mktcap":             (1, -1, "all"),   # 总市值, 从小到大, 全部
    "forecast":           (1, +1, "all"),   # 业绩预告净利润QGr%PYQ_v1, 从大到小
}
TOTAL_W = sum(w for w, _, _ in WEIGHTS.values())   # = 13 (order-preserving divisor)
OMITTED = [
    "BP筹资市值比调整 / 标准化中性化MI(RNDQP) / 中性化(EPCOREPROFITQ,总市值) — 3× HNeutralize 中性化 (irreducible)",
    "业绩快报归母净利QGr%PY — 快报 (express) not materialized",
    "波动率_季度指标(CoreProfitQGr%PY,12) — StdevQ over 12q; provider single-q depth = q0..q4 only",
    "EBITDAQ%EV + (rev−cost)/EV — NO EV field in provider; EBITDAQ also needs D&A single-q (0%)",
    "FCFQ_重算Gr%PYQ + FCFQ%总市值 — FCFQ needs D&A single-q (0%) + 处置FIOLTA (absent)",
    "营收增长−3年复合 / CoreProfitQGr%PQ−TTMGr%PY / CoreProfitTTMGr%PY−%3Y — TTM-YoY/3yr need q4..q7 depth",
]

_Q = lambda b, qs: [f"${b}_sq_q{i}" for i in qs]                          # noqa: E731
FIELDS = sorted(set(
    ["$total_mv", "$close", "$open", "$high", "$low", "$pre_close", "$amount",
     "$adj_factor", "$limit_status", "$forecast__np_q_yoy", "$total_assets_q0"]
    + _Q("revenue", (0, 1, 4)) + _Q("oper_cost", (0, 4)) + _Q("admin_exp", (0, 4)) + _Q("sell_exp", (0, 4))
    + _Q("fin_exp", (0, 4)) + _Q("biz_tax_surchg", (0, 4)) + _Q("income_tax", (0, 4))
    + _Q("rd_exp", (0, 4)) + _Q("profit_dedt", (0, 4)) + _Q("n_income_attr_p", (0, 1, 2, 3, 4))
    + ["$total_hldr_eqy_exc_min_int_q0", "$total_hldr_eqy_exc_min_int_q1"]
))


def _load_listed_bounds() -> dict:
    p = ROOT / "data" / "qlib_data" / "instruments" / "all_stocks.txt"
    df = pd.read_csv(p, sep="\t", header=None, names=["code", "start", "end"], dtype=str)
    return {str(r.code).upper(): (pd.Timestamp(r.start), pd.Timestamp(r.end)) for r in df.itertuples(index=False)}


LISTED_BOUNDS = _load_listed_bounds()


def _in_build(c: str) -> bool:
    return in_guorn_universe(c, include_star=True)               # broad cache: incl 科创板 (so #15 双创 reuses it)


def build(start: str, end: str):
    """Pull fields on the broad build universe, compute the 11 GARP factor frames + the industry frame
    (build_industry_series_asof) + eligibility frames (close, ILLIQ(5)), cache (datetime x inst)."""
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    from src.data_infra.provider_metadata import build_industry_series_asof
    qlib.init(provider_uri=PROVIDER_URI, region=REG_CN, kernels=1)
    allinsts = D.list_instruments(D.instruments("all"), start_time=start, end_time=end, as_list=True)
    insts = sorted(c for c in allinsts if _in_build(c))
    print(f"[build] {len(insts)} build-universe insts; pulling {len(FIELDS)} fields {start}..{end}", flush=True)
    fetch_start = (pd.Timestamp(start) - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
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

    def core(q):
        return (ff(f"revenue_sq_q{q}") - ff(f"oper_cost_sq_q{q}")
                - (ff(f"admin_exp_sq_q{q}") + ff(f"sell_exp_sq_q{q}") + ff(f"fin_exp_sq_q{q}"))
                - ff(f"biz_tax_surchg_sq_q{q}"))

    rev0, rev1, rev4 = ff("revenue_sq_q0"), ff("revenue_sq_q1"), ff("revenue_sq_q4")
    cost0 = ff("oper_cost_sq_q0")
    core0, core4 = core(0), core(4)
    it0, it4 = ff("income_tax_sq_q0"), ff("income_tax_sq_q4")
    rd0, rd4 = ff("rd_exp_sq_q0"), ff("rd_exp_sq_q4")
    pd0, pd4 = ff("profit_dedt_sq_q0"), ff("profit_dedt_sq_q4")
    ni = {q: ff(f"n_income_attr_p_sq_q{q}") for q in range(5)}
    tmv = P["total_mv"].reindex(idx).ffill()

    factors = {}
    factors["SalesQGr"] = safe(rev0 - rev4, rev0.abs())
    factors["revQoQ_minus_YoY"] = safe(rev0 - rev1, rev1.abs()) - safe(rev0 - rev4, rev4.abs())
    factors["CoreProfitQGr"] = safe(core0 - core4, core4.abs())
    factors["incometaxQGr"] = safe(it0 - it4, it0.abs())
    factors["RnDQGR"] = safe(rd0 - rd4, rd4)                              # recipe: /refq(rd,4) (no abs)
    roe0 = safe(ni[0] + ni[1] + ni[2] + ni[3], ff("total_hldr_eqy_exc_min_int_q0"))
    roe1 = safe(ni[1] + ni[2] + ni[3] + ni[4], ff("total_hldr_eqy_exc_min_int_q1"))
    factors["ROETTMDiff"] = roe0 - roe1
    factors["EpsExclXorGr"] = safe(pd0 - pd4, pd4.abs())
    factors["salesyield"] = safe(rev0, tmv)                              # 营收单季/总市值 (一级行业内 at rank time)
    factors["GrossProfitAssetsQ"] = safe(rev0 - cost0, ff("total_assets_q0"))
    factors["mktcap"] = tmv
    factors["forecast"] = ff("forecast__np_q_yoy")

    # --- industry frame (申万L1 as-of each day) via the canonical PIT-safe resolver ---
    print("[build] resolving SW2021 L1 industry as-of each grid day ...", flush=True)
    frames = []
    for yr, sub in P["close"].groupby(idx.year):
        mi = pd.MultiIndex.from_product([sub.index, insts], names=["datetime", "instrument"])
        ser = build_industry_series_asof(mi, level="L1")
        frames.append(ser.unstack(level="instrument").reindex(columns=insts))
        print(f"    {yr}: cov={frames[-1].notna().mean().mean():.3f}", flush=True)
    industry = pd.concat(frames).sort_index().reindex(idx).reindex(columns=insts)

    # --- eligibility: ILLIQ(5) = MA(振幅/成交额(亿),5) for the 0-65% liquidity filter ---
    amplitude = safe(P["high"] - P["low"], P["pre_close"])
    amt_yi = P["amount"] / 1e5
    illiq5 = safe(amplitude, amt_yi).rolling(5, min_periods=3).mean()
    elig = {"close_raw": P["close"], "illiq5": illiq5}

    for name, fr in factors.items():
        fr.reindex(idx).astype("float32").to_parquet(CACHE / f"f_{name}.parquet")
    industry.astype("str").to_parquet(CACHE / "industry.parquet")
    for name, fr in elig.items():
        fr.reindex(idx).astype("float32").to_parquet(CACHE / f"e_{name}.parquet")
    (CACHE / "meta.json").write_text(json.dumps({"start": start, "end": end, "n_insts": len(insts)}), encoding="utf-8")
    print("[build] factor coverage (frac non-NaN over the grid):", flush=True)
    for name, fr in factors.items():
        print(f"    {name:20} cov={fr.reindex(idx).notna().mean().mean():.3f}", flush=True)
    print(f"[build] cached -> {CACHE}", flush=True)


def _load(weights):
    f = {n: pd.read_parquet(CACHE / f"f_{n}.parquet") for n in weights}
    ind = pd.read_parquet(CACHE / "industry.parquet")
    e = {n: pd.read_parquet(CACHE / f"e_{n}.parquet") for n in ("close_raw", "illiq5")}
    return f, ind, e


def composite_row(f, ind, pday, elig_idx, weights, total_w):
    """果仁-EXACT composite (果仁筛选与排名功能 §3.1.4): per factor 排名分 = (N−rank+1)/N×100 (NaN→bottom),
    综合 = Σ(排名分×weight). scope 'ind' ranks WITHIN 申万L1 (排名分 over the group); else cross-sectional."""
    indrow = ind.loc[pday].reindex(elig_idx)
    N = len(elig_idx)
    parts = []
    for name, (w, d, scope) in weights.items():
        row = f[name].loc[pday].reindex(elig_idx)
        asc = (d < 0)
        if scope == "ind":
            rnk = row.groupby(indrow).rank(method="min", ascending=asc, na_option="bottom")
            gN = indrow.map(indrow.value_counts())
            score = (gN - rnk + 1) / gN * 100.0
        else:
            rnk = row.rank(method="min", ascending=asc, na_option="bottom")
            score = (N - rnk + 1) / N * 100.0
        parts.append(score * w)
    return pd.concat(parts, axis=1).sum(axis=1) / (100.0 * total_w)


def build_schedule(start, end, headroom=25):
    f, ind, e = _load(WEIGHTS)
    cal = ru.trading_calendar()
    cal = cal[(cal >= pd.Timestamp(start)) & (cal <= pd.Timestamp(end))]
    close_raw, illiq5 = e["close_raw"], e["illiq5"]
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
        # #4 universe = main+中小板+创业板 (EXCLUDE 科创板/北证) + 上市天数>30 (calendar) + not-ST + listed
        ok = []
        for c in insts:
            b = LISTED_BOUNDS.get(c.upper())
            ok.append(in_guorn_universe(c) and c.upper() not in st                      # #4 = 排除科创板
                      and b is not None and b[0] <= pday <= b[1] and (pday - b[0]).days > 30)
        keep &= pd.Series(ok, index=insts)
        # ILLIQ(5) 排名%区间 0%-65% is DESCENDING (0% = MOST illiquid): the book "sm_GARP_illiq" TARGETS
        # illiquidity. PROVEN: 果仁's #4 holds sit at ILLIQ-ascending-pct mean 0.68, frac<0.35 ~1.2%
        # (_diag04_overlap.py) — it keeps the MOST-illiquid 65% (drops the most-liquid 35%). An ascending
        # "keep most-liquid 65%" filter excluded 55% of 果仁's actual picks (overlap 9.7% -> see re-run).
        elig0 = keep[keep].index
        il = illiq5.loc[pday].reindex(elig0)
        keep_illiq = il.rank(pct=True, ascending=False, na_option="bottom") <= 0.65
        elig_names = keep_illiq[keep_illiq].index
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
    print(f"[sched] {nonempty}/{len(cal)} non-empty; mean top10 churn/day={np.mean(churn) if churn else float('nan'):.3f}; saved", flush=True)


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
            out[y] = float(v)   # 果仁 年度收益统计 stores DECIMALS; never /100
    return out


def run(start, end):
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    sched = {pd.Timestamp(k): v for k, v in json.loads(SCHED.read_text(encoding="utf-8")).items()}
    # #4 模型II: 个股仓位 7–13% (~10 holds, max ~14), sell 排名≥20, 备选买入=5, exits OFF, no cooldown.
    strat = ModelIIPosProfitStrategy(sched, buy_rank=5, sell_rank=20, target_n=10, pos_max=0.13,
                                     max_holds=14, use_exits=False, rebuy_cooldown=0)
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
    net.to_frame("net").to_parquet(OUT / "verify04_net.parquet")
    m = ru.goal_metrics(net); m["sharpe_rf4"] = ru.sharpe(net, rf=0.04)
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    yearly = {int(y): float(v) for y, v in yr.items()}
    gy = _read_guorn_yearly()
    print("\n" + "=" * 74)
    print("  #4 sm_GARP_illiq — LOCAL vs 果仁 (daily model-II, 0.2%/side; 12/23 weight-units OMITTED)")
    print(f"  LOCAL  annual≈{m['cagr']:+.2%}  Sharpe(rf4%)={m['sharpe_rf4']:.2f}  MDD={m['mdd']:+.2%}  vol={m['ann_vol']:.2%}")
    print(f"  果仁   annual={GR['annual']:+.2%}  Sharpe={GR['sharpe']:.2f}  MDD={-GR['mdd']:+.2%}  vol={GR['vol']:.2%}")
    print("  year     LOCAL      果仁     diff")
    for y in sorted(yearly):
        g = gy.get(y); gtxt = f"{g:+7.1%}" if g is not None else "   n/a "
        print(f"  {y}   {yearly[y]:+8.1%}  {gtxt}  {(f'{yearly[y]-g:+7.1%}') if g is not None else ''}")
    (OUT / "verify04_result.json").write_text(json.dumps(
        dict(local=m, local_yearly=yearly, guoren=GR, guoren_yearly=gy, start=start, end=end,
             kept_terms=list(WEIGHTS), kept_weight=TOTAL_W, total_recipe_weight=25, omitted=OMITTED),
        indent=2, default=str), encoding="utf-8")
    print("\nNON-FORMAL PARITY ARTIFACT — validates #4 construction vs 果仁; NOT sealed/deployable.")


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
