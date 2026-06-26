"""果仁 deployed-20 verification — strategy #1: sm_01_成长动量 (nn=1).

First of the 6 GREEN deployed books. 果仁 = trusted benchmark; the LOCAL construction layer is under test.
Recipe (deployed_20_recipes.md #1 + execution spec):
  universe : 全部股票 − ST − 科创板 (= 沪深 main+中小板+创业板, MAIN_PREFIXES; rung-1 ground-truth), 过滤停牌
  eligibility: 收盘价≥2 · 上市>20 · 5d&20d 成交额>0.05亿 · 负债资产率 & 乖离率120 rank≥10% · [skip 重大违规/未来流通股]
  signal (9 weighted rank terms, /12):
    总市值  w2 一级行业内 ↓small  +  总市值 w3 全部 ↓small        (market-cap dominates, 5/12)
    CoreProfitQGr%PY w1 ↑   EpsExclXorQGr%PY w1 ↑   ROETTMDiffPQ w1 ↑
    股价振幅%成交额10日(ILLIQ) w1 ↑   o/n-mom 250−20 & 120−20 (excl 涨停) w1 each ↑   业绩预告QGr w1 ↓
  trade model : 模型II, 调仓周期=1 (DAILY), 09:35≈open, 个股仓位 7–13% (~10 holds), 备选 20, no timing
  cost : 千分之二 (0.2%/side, 果仁 default — WORKING ASSUMPTION; confirm via return-match), total return

Factor mapping (rung 1-5 validated base; deployed_20_VERIFICATION_TRACKER.md):
  总市值=$total_mv ✓ · CoreProfitQ=rev−cost−(admin+sell+fin)−biztax _sq (rung-5 penny) ·
  EpsExclXorQ≈$profit_dedt_sq/shares (Phase-C; shares-stable-YoY proxy) · ROETTMDiff=ΔQoQ TTM-ROE ·
  ILLIQ=MA(振幅/成交额,10) (rung-4) · o/n-mom=LOG(adjopen/Ref(adjclose,1)) excl $limit_status==1 ·
  业绩预告=$forecast__np_q_yoy (rung-3). The 2 ⚠ (EpsExclXor shares-basis, ROETTM ROE-field) are
  documented choices validated via the holdings/return match (rung-4 method).

NON-FORMAL parity artifact. Reuses the rung-2 daily model-II engine (ModelIIPosProfitStrategy, no exits / no
cooldown for #1) + rung-6 factor-cache pattern.
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
from guorn_parity_rung2_posprofit import ModelIIPosProfitStrategy        # noqa: E402  (reuse daily model-II)

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
CACHE = OUT / "verify01_cache"
CACHE.mkdir(parents=True, exist_ok=True)
SCHED = OUT / "verify01_schedule.json"
PROVIDER_URI = str(ROOT / "data" / "qlib_data")
MAIN_PREFIXES = ("600", "601", "603", "605", "000", "001", "002", "003", "300", "301")
XLSX = ROOT / "Knowledge" / "果仁回测结果" / "01_sm_01_成长动量.xlsx"
GR = dict(annual=0.5721, sharpe=1.68, mdd=0.4787, vol=0.3168, bench_annual=0.3535, excess=0.1615)

# composite term -> (weight, direction): +1 = 从大到小 (larger better), -1 = 从小到大 (smaller better)
WEIGHTS = {"mktcap_ind": (2, -1), "mktcap_x": (3, -1), "CoreProfitQGr": (1, +1),
           "EpsExclXorGr": (1, +1), "ROETTMDiff": (1, +1), "ILLIQ": (1, +1),
           "onmom250": (1, +1), "onmom120": (1, +1), "forecast": (1, -1)}
TOTAL_W = sum(w for w, _ in WEIGHTS.values())

_Q = lambda b, qs: [f"${b}_sq_q{i}" for i in qs]                          # noqa: E731
FIELDS = sorted(set(
    ["$total_mv", "$sw2021_l1", "$close", "$open", "$high", "$low", "$pre_close", "$amount",
     "$adj_factor", "$limit_status", "$forecast__np_q_yoy", "$total_liab_q0", "$total_assets_q0"]
    + _Q("revenue", (0, 4)) + _Q("oper_cost", (0, 4)) + _Q("admin_exp", (0, 4)) + _Q("sell_exp", (0, 4))
    + _Q("fin_exp", (0, 4)) + _Q("biz_tax_surchg", (0, 4)) + _Q("profit_dedt", (0, 4))
    + _Q("n_income_attr_p", (0, 1, 2, 3, 4))
    + ["$total_hldr_eqy_exc_min_int_q0", "$total_hldr_eqy_exc_min_int_q1"]
))


def _load_listed_bounds() -> dict:
    p = ROOT / "data" / "qlib_data" / "instruments" / "all_stocks.txt"
    df = pd.read_csv(p, sep="\t", header=None, names=["code", "start", "end"], dtype=str)
    return {str(r.code).upper(): (pd.Timestamp(r.start), pd.Timestamp(r.end)) for r in df.itertuples(index=False)}


LISTED_BOUNDS = _load_listed_bounds()


def _in_universe(c: str) -> bool:
    return c.split("_")[0][:3] in MAIN_PREFIXES


def build(start: str, end: str):
    """Pull fields, compute the 9 daily factor frames + eligibility frames, cache (datetime x inst)."""
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=PROVIDER_URI, region=REG_CN, kernels=1)
    allinsts = D.list_instruments(D.instruments("all"), start_time=start, end_time=end, as_list=True)
    insts = sorted(c for c in allinsts if _in_universe(c))
    print(f"[build] {len(insts)} 沪深 insts; pulling {len(FIELDS)} fields {start}..{end}", flush=True)
    fetch_start = (pd.Timestamp(start) - pd.Timedelta(days=400)).strftime("%Y-%m-%d")  # warmup for rolling/TTM
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

    def ff(name):                                       # fundamentals: forward-fill across the daily grid
        return P[name].reindex(idx).ffill()

    # --- fundamentals (ffill daily) ---
    def core(q):
        return (ff(f"revenue_sq_q{q}") - ff(f"oper_cost_sq_q{q}")
                - (ff(f"admin_exp_sq_q{q}") + ff(f"sell_exp_sq_q{q}") + ff(f"fin_exp_sq_q{q}"))
                - ff(f"biz_tax_surchg_sq_q{q}"))
    core0, core4 = core(0), core(4)
    factors = {}
    factors["CoreProfitQGr"] = safe(core0 - core4, core4.abs())
    factors["EpsExclXorGr"] = safe(ff("profit_dedt_sq_q0") - ff("profit_dedt_sq_q4"), ff("profit_dedt_sq_q4").abs())
    ni = {q: ff(f"n_income_attr_p_sq_q{q}") for q in range(5)}
    roe0 = safe(ni[0] + ni[1] + ni[2] + ni[3], ff("total_hldr_eqy_exc_min_int_q0"))   # TTM ROE as-of q0
    roe1 = safe(ni[1] + ni[2] + ni[3] + ni[4], ff("total_hldr_eqy_exc_min_int_q1"))   # TTM ROE as-of q1
    factors["ROETTMDiff"] = roe0 - roe1
    factors["forecast"] = ff("forecast__np_q_yoy")
    factors["mktcap_x"] = P["total_mv"].reindex(idx).ffill()
    factors["mktcap_ind"] = factors["mktcap_x"]                       # same values; industry-grouped at rank time
    industry = P["sw2021_l1"].reindex(idx).ffill()

    # --- price/volume (daily, raw + adjusted) ---
    high, low, pre = P["high"], P["low"], P["pre_close"]
    amplitude = safe(high - low, pre)                                # 股价振幅 = (high−low)/pre_close (rung-4)
    amt_yi = P["amount"] / 1e5                                       # 当日成交额 in 亿 (amount is 千元)
    factors["ILLIQ"] = safe(amplitude, amt_yi).rolling(10, min_periods=5).mean()
    adjf = P["adj_factor"]
    adjc = P["close"] * adjf
    adjo = P["open"] * adjf
    onret = np.log(safe(adjo, adjc.shift(1)))                        # LOG(后复权开盘/REF(后复权收盘,1))
    lim = P["limit_status"].reindex_like(onret)
    onret = onret.where(lim != 1, 0.0)                              # excl 当日涨停 (limit_status==1)
    s20 = onret.rolling(20, min_periods=10).sum()
    factors["onmom250"] = onret.rolling(250, min_periods=120).sum() - s20
    factors["onmom120"] = onret.rolling(120, min_periods=60).sum() - s20

    # --- eligibility frames ---
    close_raw = P["close"]
    elig = {
        "close_raw": close_raw, "amt": P["amount"],
        "debt_assets": safe(ff("total_liab_q0"), ff("total_assets_q0")),
        "bias120": safe(adjc - adjc.rolling(120, min_periods=60).mean(), adjc.rolling(120, min_periods=60).mean()),
    }

    for name, fr in factors.items():
        fr.reindex(idx).astype("float32").to_parquet(CACHE / f"f_{name}.parquet")
    industry.astype("str").to_parquet(CACHE / "industry.parquet")
    for name, fr in elig.items():
        fr.reindex(idx).astype("float32").to_parquet(CACHE / f"e_{name}.parquet")
    (CACHE / "meta.json").write_text(json.dumps({"start": start, "end": end, "n_insts": len(insts)}), encoding="utf-8")
    print("[build] factor coverage (frac non-NaN over the grid):", flush=True)
    for name, fr in factors.items():
        print(f"    {name:14} cov={fr.reindex(idx).notna().mean().mean():.3f}", flush=True)
    print(f"[build] cached -> {CACHE}", flush=True)


def _load():
    f = {n: pd.read_parquet(CACHE / f"f_{n}.parquet") for n in WEIGHTS}
    ind = pd.read_parquet(CACHE / "industry.parquet")
    e = {n: pd.read_parquet(CACHE / f"e_{n}.parquet") for n in ("close_raw", "amt", "debt_assets", "bias120")}
    return f, ind, e


def _composite_row(f, ind, pday, elig_idx):
    """果仁-EXACT composite (果仁筛选与排名功能 doc §3.1.4): per factor, 排名分 = (N − 排名 + 1)/N × 100 where
    排名 is the 1-based rank in the factor's preferred direction; **a NaN factor → ranked LAST → lowest 排名分**
    (NOT skipped — this was the bug; 果仁 penalizes空值 to the worst rank). 综合排名分 = Σ(排名分 × weight).
    Ranked WITHIN the eligible set (果仁's 选股域); 市值 industry-term ranks WITHIN 申万L1 (排名分 over the group)."""
    indrow = ind.loc[pday].reindex(elig_idx)
    N = len(elig_idx)
    parts = []
    for name, (w, d) in WEIGHTS.items():
        row = f[name].loc[pday].reindex(elig_idx)
        asc = (d < 0)  # +1 从大到小 → largest=rank1 (ascending=False); −1 从小到大 → smallest=rank1 (ascending=True)
        if name == "mktcap_ind":
            rnk = row.groupby(indrow).rank(method="min", ascending=asc, na_option="bottom")
            gN = indrow.map(indrow.value_counts())
            score = (gN - rnk + 1) / gN * 100.0
        else:
            rnk = row.rank(method="min", ascending=asc, na_option="bottom")
            score = (N - rnk + 1) / N * 100.0
        parts.append(score * w)
    # 综合排名分 = Σ(排名分 × weight); /(100*TOTAL_W) is order-preserving (keeps composite in ~[0,1]).
    return pd.concat(parts, axis=1).sum(axis=1) / (100.0 * TOTAL_W)


def build_schedule(start, end, headroom=30):   # headroom>=25 so the sell-band (rank≥25) is resolvable
    f, ind, e = _load()
    cal = ru.trading_calendar()
    cal = cal[(cal >= pd.Timestamp(start)) & (cal <= pd.Timestamp(end))]
    close_raw, amt = e["close_raw"], e["amt"]
    amt5 = amt.rolling(5, min_periods=1).mean(); amt20 = amt.rolling(20, min_periods=1).mean()
    hist = close_raw.notna().rolling(20, min_periods=1).sum()
    insts = close_raw.columns
    sched, members = {}, {}
    grid = close_raw.index
    for d in cal:
        d = pd.Timestamp(d)
        pos = grid.searchsorted(d)
        if pos == 0:
            sched[d] = []; continue
        pday = grid[pos - 1]                                          # market data as-of prev day (09:35 fill, no lookahead)
        st = ru.st_codes_on(d)
        # eligibility on pday
        cr = close_raw.loc[pday]
        keep = pd.Series(True, index=insts)
        keep &= cr.notna() & (cr >= 2.0)                            # 过滤停牌 + 收盘价≥2
        keep &= (amt5.loc[pday] > 5000.0) & (amt20.loc[pday] > 5000.0)   # 5d/20d 成交额>0.05亿
        keep &= hist.loc[pday] >= 20                                # 上市天数>20 (proxy)
        listed = pd.Series([(LISTED_BOUNDS.get(c.upper()) is not None
                             and LISTED_BOUNDS[c.upper()][0] <= pday <= LISTED_BOUNDS[c.upper()][1]) for c in insts], index=insts)
        keep &= listed
        keep &= pd.Series([c.upper() not in st for c in insts], index=insts)
        # rank-band screens: 负债资产率 & 乖离率120 keep pct≥10% (drop the bottom-10% tail)
        da = e["debt_assets"].loc[pday]; bz = e["bias120"].loc[pday]
        keep &= da.rank(pct=True) >= 0.10
        keep &= bz.rank(pct=True) >= 0.10
        elig_names = keep[keep].index
        if len(elig_names) < headroom:
            sched[d] = []; continue
        comp = _composite_row(f, ind, pday, elig_names).dropna()
        top = comp.sort_values(ascending=False).head(headroom)
        sched[d] = [str(c).upper().replace("_", ".") for c in top.index]
        members[d] = set(list(top.index)[:10])
    keys = sorted(members)
    churn = [len(members[keys[i]] - members[keys[i - 1]]) / max(len(members[keys[i]]), 1)
             for i in range(1, len(keys)) if members[keys[i]]]
    SCHED.write_text(json.dumps({str(k.date()): v for k, v in sched.items()}, ensure_ascii=False), encoding="utf-8")
    nonempty = sum(1 for v in sched.values() if v)
    print(f"[sched] {nonempty}/{len(cal)} non-empty; mean top10 churn/day={np.mean(churn) if churn else float('nan'):.3f}; saved", flush=True)
    return sched


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
    sched = {pd.Timestamp(k): v for k, v in json.loads(SCHED.read_text(encoding="utf-8")).items()}
    # EXACT #1 交易模型 (screenshot): 模型II, 理想持仓 10 / 最大持仓 15, 卖出排名≥25, 新买无 rank≤10 限制
    # (买入候选=备选20 全池), 止盈/止损/回撤/持有天数/同行业/距上次卖出 全 OFF, 调仓日非跌停=engine limit gate.
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
    net.to_frame("net").to_parquet(OUT / "verify01_net.parquet")
    m = ru.goal_metrics(net); m["sharpe_rf4"] = ru.sharpe(net, rf=0.04)
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    yearly = {int(y): float(v) for y, v in yr.items()}
    gy = _read_guorn_yearly()
    print("\n" + "=" * 74)
    print(f"  #1 sm_01_成长动量 — LOCAL vs 果仁 (daily model-II, 0.2%/side)")
    print(f"  LOCAL  annual≈{m['cagr']:+.2%}  Sharpe(rf4%)={m['sharpe_rf4']:.2f}  MDD={m['mdd']:+.2%}  vol={m['ann_vol']:.2%}")
    print(f"  果仁   annual={GR['annual']:+.2%}  Sharpe={GR['sharpe']:.2f}  MDD={-GR['mdd']:+.2%}  vol={GR['vol']:.2%}")
    print("  year     LOCAL      果仁     diff")
    for y in sorted(yearly):
        g = gy.get(y); gtxt = f"{g:+7.1%}" if g is not None else "   n/a "
        print(f"  {y}   {yearly[y]:+8.1%}  {gtxt}  {(f'{yearly[y]-g:+7.1%}') if g is not None else ''}")
    (OUT / "verify01_result.json").write_text(json.dumps(
        dict(local=m, local_yearly=yearly, guoren=GR, guoren_yearly=gy, start=start, end=end), indent=2, default=str), encoding="utf-8")
    print("\nNON-FORMAL PARITY ARTIFACT — validates #1 construction vs 果仁; NOT sealed/deployable.")


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
