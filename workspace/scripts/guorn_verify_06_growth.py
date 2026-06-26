"""果仁 deployed-20 verification — strategy #6: sm_01_成长高贝塔@TMT_v1 (nn=6).

Third of the 成长 cluster (TMT-restricted, high-beta variant). 果仁 = trusted benchmark; LOCAL under test.

Recipe (deployed_20_recipes.md #6):
  universe : TMT (申万L1 ∈ {传媒,电子,计算机,通信}) ∩ 沪深 main+创业板 (− 科创板/688 − ST), 过滤停牌
  filters(6): 退市风险=0 (≈price≥2+ST) · 5d&20d 成交额>0.05亿 · 上市>20 · [skip 重大违规] · 乖离率60 rank≥10%
              (NOTE vs #1: NO 真实负债资产率 filter; 乖离率60 not 120)
  rankings(10): 总市值 w2 一级行业内 ↓ + 总市值 w3 全部 ↓ + CoreProfitQGr%PY w1 ↑ + EpsExclXorQGr%PY w1 ↑
              + ROETTMDiffPQ w1 ↑ + 股价振幅%成交额10日(ILLIQ) w1 ↑ + 贝塔N日(000001,250) w1 ↑
              + 预期营收2年复合增长 w1 ↑ + 研发销售比率 w1 ↑ + 业绩快报归母净利QGr%PY w1 ↑
  trade model : 模型II daily, 09:35 open, 个股仓位 7.5–22.5% (理想15% → ~7 holds, max ~13), 备选20,
              sell 排名≥15, 涨停不卖 (hold_on_limit_up), no timing. cost 0.2%/side, total return.

GAPS — 2 of 11 weight OMITTED: 预期营收2年复合增长 (analyst CONSENSUS, irreducible per mapping-doc §5) and
业绩快报归母净利QGr%PY (express, not materialized §7). The composite is the faithful 8-term core (weight 9/11).

NEW factors (both reproducible, computed here): 贝塔N日(000001,250) = rolling-250d slope of stock daily
return on 上证综指(000001.SH) return = Cov/Var (index from data/market/index/index_000001.SH.parquet);
研发销售比率 = TTM(研发费用)/TTM(营业收入) = Σ$rd_exp_sq_q0..3 / Σ$revenue_sq_q0..3.

LAYER DISCIPLINE (§8.1): the 6 shared factors are #1's FULL-MARKET frames (verify01_cache, universe-agnostic
Layer-1) reused as-is; the TMT restriction is a Layer-2 SELECTION mask (industry frame = the 2026-06-26
FIXED build_industry_series_asof SW2021 L1). NON-FORMAL parity artifact; not sealed/deployable.
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

import research_utils as ru                                          # noqa: E402
from guorn_parity_rung2_posprofit import ModelIIPosProfitStrategy    # noqa: E402

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
CACHE_01 = OUT / "verify01_cache"          # reuse #1's 6 shared full-market factor frames + industry + elig base
CACHE_06 = OUT / "verify06_cache"          # #6 extras: beta, rndsales, bias60
CACHE_06.mkdir(parents=True, exist_ok=True)
SCHED_06 = OUT / "verify06_schedule.json"
PROVIDER_URI = str(ROOT / "data" / "qlib_data")
INDEX_000001 = ROOT / "data" / "market" / "index" / "index_000001.SH.parquet"
MAIN_PREFIXES = ("600", "601", "603", "605", "000", "001", "002", "003", "300", "301")
TMT_L1 = {"801760.SI", "801080.SI", "801750.SI", "801770.SI"}        # 传媒/电子/计算机/通信 (SW2021)
XLSX = ROOT / "Knowledge" / "果仁回测结果" / "06_sm_01_成长高贝塔@TMT_v1.xlsx"
GR = dict(annual=0.6032, sharpe=1.44, mdd=0.5188, vol=0.392, excess=0.1845)

# 8 faithful terms (预期营收 + express OMITTED). term -> (weight, dir): +1 从大到小, -1 从小到大.
WEIGHTS = {"mktcap_ind": (2, -1), "mktcap_x": (3, -1), "CoreProfitQGr": (1, +1), "EpsExclXorGr": (1, +1),
           "ROETTMDiff": (1, +1), "ILLIQ": (1, +1), "beta": (1, +1), "rndsales": (1, +1)}
TOTAL_W = sum(w for w, _ in WEIGHTS.values())   # = 9 (order-preserving divisor; selection-invariant)
SHARED = ["mktcap_ind", "mktcap_x", "CoreProfitQGr", "EpsExclXorGr", "ROETTMDiff", "ILLIQ"]   # from #1 cache
_Q = lambda b, qs: [f"${b}_sq_q{i}" for i in qs]                      # noqa: E731


def _in_universe(c: str) -> bool:
    return c.split("_")[0][:3] in MAIN_PREFIXES


def build_extras(start: str, end: str):
    """Compute the 3 #6-only frames (beta vs 上证, rndsales TTM, bias60) on the full 沪深 grid; cache."""
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=PROVIDER_URI, region=REG_CN, kernels=1)
    close = pd.read_parquet(CACHE_01 / "e_close_raw.parquet")
    insts = sorted(c for c in close.columns if _in_universe(c))
    fields = ["$close", "$adj_factor"] + _Q("revenue", (0, 1, 2, 3)) + _Q("rd_exp", (0, 1, 2, 3))
    fetch_start = (pd.Timestamp(start) - pd.Timedelta(days=520)).strftime("%Y-%m-%d")   # 250d beta warmup
    print(f"[build06] {len(insts)} TMT-candidate insts; pulling {len(fields)} fields {fetch_start}..{end}", flush=True)
    P = {}
    for k in range(0, len(fields), 6):
        batch = fields[k:k + 6]
        df = D.features(insts, batch, start_time=fetch_start, end_time=end, freq="day")
        for col in batch:
            P[col.replace("$", "")] = df[col].unstack(level=0).sort_index()
        print(f"[build06]   {min(k + 6, len(fields))}/{len(fields)}", flush=True)
        del df
    idx = P["close"].index
    EPS = 1e-9

    def safe(num, den):
        return (num / den.where(den.abs() > EPS)).replace([np.inf, -np.inf], np.nan)

    def ff(name):
        return P[name].reindex(idx).ffill()

    # --- 研发销售比率 = TTM(研发费用)/TTM(营业收入) ---
    ttm_rd = sum(ff(f"rd_exp_sq_q{q}") for q in range(4))
    ttm_rev = sum(ff(f"revenue_sq_q{q}") for q in range(4))
    rndsales = safe(ttm_rd, ttm_rev)

    # --- 贝塔N日(000001,250) = rolling-250d Cov(stock_ret, idx_ret)/Var(idx_ret) ---
    adjc = P["close"] * P["adj_factor"]
    y = adjc.pct_change()                                            # stock daily return (后复权)
    iraw = pd.read_parquet(INDEX_000001)                            # cols: ts_code, trade_date(int), close, ...
    iclose = pd.Series(pd.to_numeric(iraw["close"], errors="coerce").values,
                       index=pd.to_datetime(iraw["trade_date"].astype(str))).sort_index()
    x = iclose.pct_change().reindex(idx)                             # 上证综指 1日涨幅 aligned to grid
    N = 250
    Ey = y.rolling(N, min_periods=120).mean()
    Ex = x.rolling(N, min_periods=120).mean()
    Exy = y.mul(x, axis=0).rolling(N, min_periods=120).mean()
    cov = Exy.sub(Ey.mul(Ex, axis=0))
    varx = (x * x).rolling(N, min_periods=120).mean() - Ex ** 2
    beta = cov.div(varx, axis=0).replace([np.inf, -np.inf], np.nan)

    # --- 乖离率60 (lag 1, like #1's bias120 but 60d) ---
    ma60 = adjc.rolling(60, min_periods=30).mean()
    bias60 = safe(adjc - ma60, ma60)

    for name, fr in {"beta": beta, "rndsales": rndsales, "bias60": bias60}.items():
        fr.reindex(idx).astype("float32").to_parquet(CACHE_06 / f"f_{name}.parquet")
        print(f"    {name:10} cov={fr.reindex(idx).notna().mean().mean():.3f}", flush=True)
    print(f"[build06] cached -> {CACHE_06}", flush=True)


def _load():
    f = {n: pd.read_parquet(CACHE_01 / f"f_{n}.parquet") for n in SHARED}
    f["beta"] = pd.read_parquet(CACHE_06 / "f_beta.parquet")
    f["rndsales"] = pd.read_parquet(CACHE_06 / "f_rndsales.parquet")
    ind = pd.read_parquet(CACHE_01 / "industry.parquet")
    e = {n: pd.read_parquet(CACHE_01 / f"e_{n}.parquet") for n in ("close_raw", "amt")}
    e["bias60"] = pd.read_parquet(CACHE_06 / "f_bias60.parquet")
    return f, ind, e


def _composite_row(f, ind, pday, elig_idx):
    """果仁-exact composite (§3.1.4): 排名分 = (N−rank+1)/N×100, NaN→bottom; 综合 = Σ(排名分×w).
    mktcap_ind ranks WITHIN 申万L1 (over the TMT-eligible set's industries)."""
    indrow = ind.loc[pday].reindex(elig_idx)
    N = len(elig_idx)
    parts = []
    for name, (w, d) in WEIGHTS.items():
        row = f[name].loc[pday].reindex(elig_idx)
        asc = (d < 0)
        if name == "mktcap_ind":
            rnk = row.groupby(indrow).rank(method="min", ascending=asc, na_option="bottom")
            gN = indrow.map(indrow.value_counts())
            score = (gN - rnk + 1) / gN * 100.0
        else:
            rnk = row.rank(method="min", ascending=asc, na_option="bottom")
            score = (N - rnk + 1) / N * 100.0
        parts.append(score * w)
    return pd.concat(parts, axis=1).sum(axis=1) / (100.0 * TOTAL_W)


def schedule(start, end, headroom=20):
    if not (CACHE_06 / "f_beta.parquet").exists():
        raise SystemExit("verify06_cache missing — run --build first.")
    f, ind, e = _load()
    cal = ru.trading_calendar()
    cal = cal[(cal >= pd.Timestamp(start)) & (cal <= pd.Timestamp(end))]
    close_raw, amt = e["close_raw"], e["amt"]
    amt5 = amt.rolling(5, min_periods=1).mean(); amt20 = amt.rolling(20, min_periods=1).mean()
    hist = close_raw.notna().rolling(20, min_periods=1).sum()
    insts = close_raw.columns
    # TMT membership at pday via the (now fixed) industry frame
    sched, members = {}, {}
    grid = close_raw.index
    LB = {str(r.code).upper(): (pd.Timestamp(r.start), pd.Timestamp(r.end)) for r in
          pd.read_csv(ROOT / "data" / "qlib_data" / "instruments" / "all_stocks.txt", sep="\t", header=None,
                      names=["code", "start", "end"], dtype=str).itertuples(index=False)}
    for d in cal:
        d = pd.Timestamp(d)
        pos = grid.searchsorted(d)
        if pos == 0:
            sched[d] = []; continue
        pday = grid[pos - 1]
        st = ru.st_codes_on(d)
        cr = close_raw.loc[pday]
        indrow = ind.loc[pday]
        keep = pd.Series(True, index=insts)
        keep &= cr.notna() & (cr >= 2.0)                              # 过滤停牌 + 收盘价≥2
        keep &= (amt5.loc[pday] > 5000.0) & (amt20.loc[pday] > 5000.0)    # 5d/20d 成交额>0.05亿
        keep &= hist.loc[pday] >= 20                                  # 上市>20 (proxy)
        keep &= pd.Series([indrow.get(c) in TMT_L1 for c in insts], index=insts)   # TMT industry mask
        keep &= pd.Series([(LB.get(c.upper()) is not None and LB[c.upper()][0] <= pday <= LB[c.upper()][1]) for c in insts], index=insts)
        keep &= pd.Series([c.upper() not in st for c in insts], index=insts)
        keep &= e["bias60"].loc[pday].rank(pct=True) >= 0.10          # 乖离率60 rank≥10%
        elig_names = keep[keep].index
        if len(elig_names) < headroom:
            sched[d] = []; continue
        comp = _composite_row(f, ind, pday, elig_names).dropna()
        top = comp.sort_values(ascending=False).head(headroom)
        sched[d] = [str(c).upper().replace("_", ".") for c in top.index]
        members[d] = set(list(top.index)[:7])
    keys = sorted(members)
    churn = [len(members[keys[i]] - members[keys[i - 1]]) / max(len(members[keys[i]]), 1)
             for i in range(1, len(keys)) if members[keys[i]]]
    SCHED_06.write_text(json.dumps({str(k.date()): v for k, v in sched.items()}, ensure_ascii=False), encoding="utf-8")
    nonempty = sum(1 for v in sched.values() if v)
    print(f"[sched06] {nonempty}/{len(cal)} non-empty; mean top7 churn/day={np.mean(churn) if churn else float('nan'):.3f}; saved", flush=True)


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
    sched = {pd.Timestamp(k): v for k, v in json.loads(SCHED_06.read_text(encoding="utf-8")).items()}
    # #6 交易模型: 模型II, 个股仓位 7.5–22.5% (理想15% → ~7 holds, max ~13), sell 排名≥15, 备选20, exits OFF.
    strat = ModelIIPosProfitStrategy(sched, buy_rank=20, sell_rank=15, target_n=7, pos_max=0.225,
                                     max_holds=13, use_exits=False, rebuy_cooldown=0)
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
    net.to_frame("net").to_parquet(OUT / "verify06_net.parquet")
    m = ru.goal_metrics(net); m["sharpe_rf4"] = ru.sharpe(net, rf=0.04)
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    yearly = {int(y): float(v) for y, v in yr.items()}
    gy = _read_guorn_yearly()
    print("\n" + "=" * 74)
    print("  #6 sm_01_成长高贝塔@TMT_v1 — LOCAL vs 果仁 (daily model-II, 0.2%/side; 预期营收+快报 OMITTED)")
    print(f"  LOCAL  annual≈{m['cagr']:+.2%}  Sharpe(rf4%)={m['sharpe_rf4']:.2f}  MDD={m['mdd']:+.2%}  vol={m['ann_vol']:.2%}")
    print(f"  果仁   annual={GR['annual']:+.2%}  Sharpe={GR['sharpe']:.2f}  MDD={-GR['mdd']:+.2%}  vol={GR['vol']:.2%}")
    print("  year     LOCAL      果仁     diff")
    for y in sorted(yearly):
        g = gy.get(y); gtxt = f"{g:+7.1%}" if g is not None else "   n/a "
        print(f"  {y}   {yearly[y]:+8.1%}  {gtxt}  {(f'{yearly[y]-g:+7.1%}') if g is not None else ''}")
    (OUT / "verify06_result.json").write_text(json.dumps(
        dict(local=m, local_yearly=yearly, guoren=GR, guoren_yearly=gy, start=start, end=end,
             omitted=["预期营收2年复合增长 (consensus)", "业绩快报归母净利QGr%PY (express)"]), indent=2, default=str), encoding="utf-8")
    print("\nNON-FORMAL PARITY ARTIFACT — validates #6 construction vs 果仁; NOT sealed/deployable.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--schedule", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--start", default="2014-01-01")
    ap.add_argument("--end", default="2026-02-27")
    args = ap.parse_args()
    if args.build:
        build_extras(args.start, args.end)
    if args.schedule:
        schedule(args.start, args.end)
    if args.run:
        run(args.start, args.end)


if __name__ == "__main__":
    main()
