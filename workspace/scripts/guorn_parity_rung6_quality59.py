"""果仁 PARITY ladder — rung 6 / strategy-harness object #1: Comp_Core_Quality (nn=59).

The FIRST formal StrategyCandidate is a faithful reproduction of a real deployed 果仁 book,
validated against its xlsx ground truth BEFORE it is formalized/sealed. 果仁 = TRUSTED
BENCHMARK; the LOCAL strategy-construction layer is UNDER TEST.

#59 recipe (verbatim, guorn_strategies_master.json nn=59; universe + trade model PROVEN from
the 各阶段持仓详单, see GUORN_HARNESS_59_PLAN.md):
  universe : 全部股票 − ST − 科创板 (PROVEN = 沪深 main + 中小板 + 创业板; 0 北证 / 0 科创 ever), 过滤停牌
  filter   : 扣非市盈率 ∈ (0, 60)
  ranking  : 12 equal-weight slots; OPCFNPDiff%NP listed TWICE (recipe-faithful 2× weight)
  model    : Model I, hold 20, equal weight, rebalance every 5 trading days at CLOSE, 备选 5, no timing
  cost     : 果仁 platform default 0.2%/side, no stamp/过户费, no slippage ; TOTAL return (EventDriven)

Factor parity (rung-6 holding-level sweep, _guorn59_factor_parity.py / _guorn59_refine.py; ledger §1b):
  6 penny-exact + RoeCoreQ rank-faithful + HAVG(x,1)=申万L1 industry mean + 扣非PE via $dtprofit_to_profit×NPttm.
  OMITTED: STDEVQ(RoeCoreQ,12)+STDEVQ(SalesQGr%PY,12) (need 12q depth) + 中性ROE (irreducible+inert).

Execution: the REAL local EventDrivenBacktester (src/backtest_engine/event_driven/) — NOT a temporary
engine. Strategy = a thin Strategy subclass; signal = offline D.features composite (four-layer pipeline).
All ranks/filters AS-OF prev trading day (T−1, 果仁 signal date) → PIT-safe. Engine OPEN fill vs 果仁
CLOSE fill = execution-timing approximation (does NOT change WHICH names are picked).

Pipeline (cache once, iterate selection/diagnosis cheaply):
  --build           pull D.features + compute 9 factor frames + 扣非PE -> CACHE (slow, ~4min)
  --select          composite + eligibility + top-20 schedule from CACHE (fast); --rank-eligible toggles
  --diag            WHY 果仁's held names miss my top-20 (filter / coverage / ranked-low) from CACHE (fast)
  --check-overlap   my top-20 ∩ 果仁 / 果仁 (the factor-fidelity arbiter)
  --run             EventDrivenBacktester + 果仁 cost; diff vs 59_Comp_Core_Quality.xlsx
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workspace" / "research" / "long_only_50cagr"))
sys.stdout.reconfigure(encoding="utf-8")

import research_utils as ru                                   # noqa: E402
from src.backtest_engine.event_driven.strategy import Strategy  # noqa: E402

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
CACHE = OUT / "rung6_cache"
CACHE.mkdir(parents=True, exist_ok=True)
SCHED = OUT / "rung6_schedule.json"
PROVIDER_URI = str(ROOT / "data" / "qlib_data")   # overridable via --provider-dir (staged deep-slot build)
REBAL_EVERY = 5
TOP_N = 20
MAIN_PREFIXES = ("600", "601", "603", "605", "000", "001", "002", "003", "300", "301")

GR_HEADLINE = dict(annual=0.2256, sharpe=0.69, mdd=0.4086, vol=0.2671, info_ratio=0.92,
                   beta=0.94, alpha=0.1644, excess=0.1535, benchmark_annual=0.0625)

_SQ4 = lambda b: [f"${b}_sq_q{i}" for i in range(4)]          # noqa: E731
_Q4 = lambda b: [f"${b}_q{i}" for i in range(4)]              # noqa: E731
# Deep slots (require the slot_depth=16 staged provider): SalesQGr(t)=(rev[t]-rev[t+4]) for t=0..11
# needs revenue q0..q15; RoeCoreQ(t) needs CoreProfit components + equity q0..q11.
FIELDS = sorted(set(
    _SQ4("n_cashflow_act") + _SQ4("n_income")
    + [f"$revenue_sq_q{i}" for i in range(16)]
    + [f"$oper_cost_sq_q{i}" for i in range(12)]
    + [f"$admin_exp_sq_q{i}" for i in range(12)]
    + [f"$sell_exp_sq_q{i}" for i in range(12)]
    + [f"$fin_exp_sq_q{i}" for i in range(12)]
    + [f"$biz_tax_surchg_sq_q{i}" for i in range(12)]
    + [f"$total_hldr_eqy_exc_min_int_q{i}" for i in range(12)]
    + _SQ4("rd_exp") + _Q4("total_assets") + _Q4("accounts_receiv") + _Q4("notes_receiv") + _Q4("adv_receipts")
    + ["$total_mv", "$dtprofit_to_profit", "$sw2021_l1", "$close"]
))
# the 11 reproducible 果仁 slots (only inert 中性ROE omitted): 9 level/flow + 2 real STDEVQ(.,12) stability.
FACTOR_ORDER = ["RnDTTM%营收", "OPCFNPDiff%NP_a", "销售毛利率Q-销售毛利率", "RoeCoreQ",
                "GrossProfit%AssetsQ", "RND%Assets", "应收账款周转率", "OPCFNPDiff%NP_b",
                "HAVG(OPCFNPDiff,1)=indMean", "STDEVQ(RoeCoreQ,12)=stab", "STDEVQ(SalesQGr,12)=stab"]
DIRECTIONS = {"STDEVQ(RoeCoreQ,12)=stab": -1, "STDEVQ(SalesQGr,12)=stab": -1}  # lower std = more stable = better


def _load_listed_bounds() -> dict:
    p = ROOT / "data" / "qlib_data" / "instruments" / "all_stocks.txt"
    df = pd.read_csv(p, sep="\t", header=None, names=["code", "start", "end"], dtype=str)
    return {str(r.code).upper(): (pd.Timestamp(r.start), pd.Timestamp(r.end))
            for r in df.itertuples(index=False)}


LISTED_BOUNDS = _load_listed_bounds()


def _in_universe(qlib_code: str) -> bool:
    return qlib_code.split("_")[0][:3] in MAIN_PREFIXES


def _rebal_dates(start, end):
    cal = ru.trading_calendar()
    cal = cal[(cal >= pd.Timestamp(start)) & (cal <= pd.Timestamp(end))]
    return cal[::REBAL_EVERY], cal


def build(start, end):
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    print(f"[build] provider_uri={PROVIDER_URI}", flush=True)
    qlib.init(provider_uri=PROVIDER_URI, region=REG_CN, kernels=1)

    rebal, cal = _rebal_dates(start, end)
    pos = cal.searchsorted(rebal)
    pdays = pd.DatetimeIndex([cal[p - 1] if p > 0 else cal[0] for p in pos])
    keep = pos > 0
    rebal, pdays = rebal[keep], pdays[keep]
    print(f"[build] {len(rebal)} rebalances  {rebal[0].date()}..{rebal[-1].date()}", flush=True)

    allinsts = D.list_instruments(D.instruments("all"), start_time=start, end_time=end, as_list=True)
    insts = sorted(c for c in allinsts if _in_universe(c))
    print(f"[build] {len(insts)} 沪深 instruments; pulling {len(FIELDS)} fields", flush=True)

    fetch_start = (pd.Timestamp(start) - pd.Timedelta(days=900)).strftime("%Y-%m-%d")
    panels: dict = {}
    for k in range(0, len(FIELDS), 5):
        batch = FIELDS[k:k + 5]
        df = D.features(insts, batch, start_time=fetch_start, end_time=end, freq="day")
        for col in batch:
            name = col.replace("$", "")
            wide = df[col].unstack(level=0).sort_index()
            panels[name] = (wide.ffill().reindex(pdays), wide.reindex(pdays))
        print(f"[build]   fields {min(k + 5, len(FIELDS))}/{len(FIELDS)}", flush=True)
        del df

    def P(name):
        return panels[name][0]

    def ttm(b):
        return sum(P(f"{b}_sq_q{i}") for i in range(4))

    def avg4(b):
        return sum(P(f"{b}_q{i}") for i in range(4)) / 4.0

    EPS = 1e-9
    def safe(num, den):
        return (num / den.where(den.abs() > EPS)).replace([np.inf, -np.inf], np.nan)

    ni_ttm, rev_ttm, cost_ttm = ttm("n_income"), ttm("revenue"), ttm("oper_cost")
    coreprofit = (P("revenue_sq_q0") - P("oper_cost_sq_q0")
                  - (P("admin_exp_sq_q0") + P("sell_exp_sq_q0") + P("fin_exp_sq_q0"))
                  - P("biz_tax_surchg_sq_q0"))
    opcf = safe(ttm("n_cashflow_act") - ni_ttm, ni_ttm)
    factors = {
        "RnDTTM%营收": safe(ttm("rd_exp"), rev_ttm),
        "OPCFNPDiff%NP_a": opcf,
        "销售毛利率Q-销售毛利率": (safe(P("revenue_sq_q0") - P("oper_cost_sq_q0"), P("revenue_sq_q0"))
                              - safe(rev_ttm - cost_ttm, rev_ttm)),
        "RoeCoreQ": safe(coreprofit, P("total_hldr_eqy_exc_min_int_q0")),
        "GrossProfit%AssetsQ": safe(P("revenue_sq_q0") - P("oper_cost_sq_q0"), P("total_assets_q0")),
        "RND%Assets": safe(ttm("rd_exp"), avg4("total_assets")),
        "应收账款周转率": safe(rev_ttm, avg4("accounts_receiv") + avg4("notes_receiv") - avg4("adv_receipts")),
        "OPCFNPDiff%NP_b": opcf,
    }
    ind = P("sw2021_l1")
    opcf_ind = pd.DataFrame(index=opcf.index, columns=opcf.columns, dtype=float)
    for d in opcf.index:
        opcf_ind.loc[d] = opcf.loc[d].groupby(ind.loc[d]).transform("mean")
    factors["HAVG(OPCFNPDiff,1)=indMean"] = opcf_ind

    # --- the 2 real STDEVQ(.,12) stability factors (need the slot_depth=16 staged provider) ---
    def _rolling_std(frames, min_count):
        stk = np.stack([f.reindex(index=opcf.index, columns=opcf.columns).values for f in frames])
        cnt = np.sum(~np.isnan(stk), axis=0)
        with np.errstate(invalid="ignore"):
            sd = np.nanstd(stk, axis=0)
        sd[cnt < min_count] = np.nan
        return pd.DataFrame(sd, index=opcf.index, columns=opcf.columns)

    # STDEVQ(SalesQGr%PY,12): SalesQGr(t)=(rev[t]-rev[t+4])/|rev[t]|, t=0..11 (rev q0..q15)
    sqgr = [safe(P(f"revenue_sq_q{t}") - P(f"revenue_sq_q{t+4}"), P(f"revenue_sq_q{t}").abs()) for t in range(12)]
    factors["STDEVQ(SalesQGr,12)=stab"] = _rolling_std(sqgr, min_count=8)

    # STDEVQ(RoeCoreQ,12): RoeCoreQ(t)=CoreProfit(t)/equity(t), t=0..11 (components + equity q0..q11)
    roeq = []
    for t in range(12):
        cp = (P(f"revenue_sq_q{t}") - P(f"oper_cost_sq_q{t}")
              - (P(f"admin_exp_sq_q{t}") + P(f"sell_exp_sq_q{t}") + P(f"fin_exp_sq_q{t}"))
              - P(f"biz_tax_surchg_sq_q{t}"))
        roeq.append(safe(cp, P(f"total_hldr_eqy_exc_min_int_q{t}")))
    factors["STDEVQ(RoeCoreQ,12)=stab"] = _rolling_std(roeq, min_count=8)

    dtp = P("dtprofit_to_profit")
    dtp_med = float(np.nanmedian(np.abs(dtp.values)))
    dtp_frac = dtp / 100.0 if dtp_med > 5 else dtp
    pe = safe(P("total_mv") * 1e4, dtp_frac * ni_ttm)
    print(f"[build] dtprofit median|.|={dtp_med:.2f}->{'pct/100' if dtp_med>5 else 'ratio'}; "
          f"扣非PE med(0..200)={float(np.nanmedian(pe.values[(pe.values>0)&(pe.values<200)])):.1f}", flush=True)

    # ---- cache everything diag/select needs ----
    for i, name in enumerate(FACTOR_ORDER):
        factors[name].astype("float32").to_parquet(CACHE / f"f{i}.parquet")
    pe.astype("float32").to_parquet(CACHE / "pe.parquet")
    panels["close"][1].notna().to_parquet(CACHE / "rawclose_notna.parquet")
    meta = {"rebal": [str(d.date()) for d in rebal], "pdays": [str(d.date()) for d in pdays],
            "factor_order": FACTOR_ORDER, "start": start, "end": end}
    (CACHE / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[build] cached {len(FACTOR_ORDER)} factor frames + pe + rawclose to {CACHE}", flush=True)


def build_stability(provider_dir):
    """Compute ONLY the 2 STDEVQ(.,12) stability factors from a deep-slot (slot_depth>=16) staged
    provider (income+balancesheet datasets suffice) and add them to the existing 9-factor cache as
    f9/f10 + bump meta to 11. The 9 live factors (f0..f8, incl. HAVG which needs sw2021_l1) are reused
    from the live-provider cache — decoupling avoids the staged provider's missing reference panel."""
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    print(f"[stab] provider={provider_dir}", flush=True)
    qlib.init(provider_uri=provider_dir, region=REG_CN, kernels=1)
    meta = json.loads((CACHE / "meta.json").read_text(encoding="utf-8"))
    f0 = pd.read_parquet(CACHE / "f0.parquet")
    insts, idx = list(f0.columns), f0.index            # same universe + pday index as the 9-factor cache
    fields = ([f"$revenue_sq_q{i}" for i in range(16)]
              + [f"$oper_cost_sq_q{i}" for i in range(12)]
              + [f"$admin_exp_sq_q{i}" for i in range(12)]
              + [f"$sell_exp_sq_q{i}" for i in range(12)]
              + [f"$fin_exp_sq_q{i}" for i in range(12)]
              + [f"$biz_tax_surchg_sq_q{i}" for i in range(12)]
              + [f"$total_hldr_eqy_exc_min_int_q{i}" for i in range(12)])
    fetch_start = (idx.min() - pd.Timedelta(days=900)).strftime("%Y-%m-%d")
    fetch_end = idx.max().strftime("%Y-%m-%d")
    panels = {}
    for k in range(0, len(fields), 6):
        batch = fields[k:k + 6]
        df = D.features(insts, batch, start_time=fetch_start, end_time=fetch_end, freq="day")
        for col in batch:
            panels[col.replace("$", "")] = df[col].unstack(level=0).sort_index().ffill().reindex(idx)
        print(f"[stab] fields {min(k + 6, len(fields))}/{len(fields)}", flush=True)
        del df
    EPS = 1e-9
    def P(n):
        return panels[n].reindex(columns=insts)
    def safe(num, den):
        return (num / den.where(den.abs() > EPS)).replace([np.inf, -np.inf], np.nan)
    def rstd(frames, mc):
        stk = np.stack([f.values for f in frames])
        cnt = np.sum(~np.isnan(stk), axis=0)
        with np.errstate(invalid="ignore"):
            sd = np.nanstd(stk, axis=0)
        sd[cnt < mc] = np.nan
        return pd.DataFrame(sd, index=idx, columns=insts)

    sqgr = [safe(P(f"revenue_sq_q{t}") - P(f"revenue_sq_q{t+4}"), P(f"revenue_sq_q{t}").abs()) for t in range(12)]
    sales_stab = rstd(sqgr, 8)
    roeq = []
    for t in range(12):
        cp = (P(f"revenue_sq_q{t}") - P(f"oper_cost_sq_q{t}")
              - (P(f"admin_exp_sq_q{t}") + P(f"sell_exp_sq_q{t}") + P(f"fin_exp_sq_q{t}"))
              - P(f"biz_tax_surchg_sq_q{t}"))
        roeq.append(safe(cp, P(f"total_hldr_eqy_exc_min_int_q{t}")))
    roe_stab = rstd(roeq, 8)
    roe_stab.astype("float32").to_parquet(CACHE / "f9.parquet")    # FACTOR_ORDER[9] = STDEVQ(RoeCoreQ,12)
    sales_stab.astype("float32").to_parquet(CACHE / "f10.parquet")  # FACTOR_ORDER[10] = STDEVQ(SalesQGr,12)
    meta["factor_order"] = FACTOR_ORDER
    (CACHE / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[stab] f9 RoeCoreQ-stab nonNaN={roe_stab.notna().mean().mean():.3f} | "
          f"f10 SalesGr-stab nonNaN={sales_stab.notna().mean().mean():.3f} | meta -> {len(FACTOR_ORDER)} factors",
          flush=True)


def _load_cache():
    meta = json.loads((CACHE / "meta.json").read_text(encoding="utf-8"))
    factors = {name: pd.read_parquet(CACHE / f"f{i}.parquet") for i, name in enumerate(meta["factor_order"])}
    pe = pd.read_parquet(CACHE / "pe.parquet")
    rawnotna = pd.read_parquet(CACHE / "rawclose_notna.parquet")
    rebal = pd.DatetimeIndex(pd.to_datetime(meta["rebal"]))
    pdays = pd.DatetimeIndex(pd.to_datetime(meta["pdays"]))
    return factors, pe, rawnotna, rebal, pdays


def _composite(factors, present_min, eligible_mask=None, drop=(), nan_policy="skip"):
    """Equal-weight average of per-factor cross-sectional pct-ranks (direction-aware via DIRECTIONS:
    +1=从大到小 ascending rank, -1=从小到大 inverted). `nan_policy`: 'skip' = NaN-skipping mean (a name
    missing a factor is averaged over its present factors); 'worst' = NaN→0 percentile (a missing factor
    is treated as the WORST value, e.g. no-R&D firm gets R&D-rank 0) — the 果仁-faithful hypothesis.
    `drop` = factor names to exclude. Always-NaN factors (e.g. dead stability slot) are dropped."""
    items = [(n, f) for n, f in factors.items() if n not in drop and bool(f.notna().any().any())]
    if eligible_mask is not None:
        items = [(n, f.where(eligible_mask)) for n, f in items]
    pcts = []
    for n, f in items:
        p = f.rank(axis=1, pct=True, ascending=(DIRECTIONS.get(n, 1) == 1))
        if nan_policy == "worst":
            p = p.fillna(0.0)            # missing factor -> worst rank (penalize); ineligible masked later
        pcts.append(p)
    comp = pd.concat(pcts).groupby(level=0).mean()
    present = sum(f.notna().astype(int) for _, f in items)
    return comp.where(present >= present_min)


def _eligibility(pe, rawnotna, rebal, pdays):
    """(pdays x inst) bool: 0<扣非PE<60 & not suspended & not ST(on rebal d) & listed(on pday)."""
    elig = (pe > 0) & (pe < 60) & rawnotna
    insts = pe.columns
    listed = {}
    for d, pday in zip(rebal, pdays):
        st = ru.st_codes_on(d)
        ok = np.array([(c.upper() not in st) and
                       (LISTED_BOUNDS.get(c.upper()) is not None
                        and LISTED_BOUNDS[c.upper()][0] <= pday <= LISTED_BOUNDS[c.upper()][1])
                       for c in insts])
        listed[pday] = pd.Series(ok, index=insts)
    listed = pd.DataFrame(listed).T.reindex(pdays)
    return elig & listed


def select(present_min=6, rank_eligible=True, save=True, drop=(), nan_policy="skip"):
    factors, pe, rawnotna, rebal, pdays = _load_cache()
    elig = _eligibility(pe, rawnotna, rebal, pdays)
    comp = _composite(factors, present_min, eligible_mask=elig if rank_eligible else None,
                      drop=drop, nan_policy=nan_policy)
    comp = comp.where(elig)
    schedule = {}
    for d, pday in zip(rebal, pdays):
        row = comp.loc[pday].dropna()
        top = row.sort_values(ascending=False).head(TOP_N)
        schedule[str(d.date())] = [c.upper().replace("_", ".") for c in top.index]
    if save:
        SCHED.write_text(json.dumps(schedule, ensure_ascii=False, indent=1), encoding="utf-8")
        sizes = [len(v) for v in schedule.values() if v]
        print(f"[select] present_min={present_min} rank_eligible={rank_eligible}: "
              f"{sum(1 for v in schedule.values() if v)}/{len(schedule)} non-empty, mean {np.mean(sizes):.1f}; saved", flush=True)
    return schedule


def _guorn_by_date():
    h = pd.read_parquet(OUT / "holdings_59.parquet")
    h["start"] = pd.to_datetime(h["start"])
    out = {}
    for d, grp in h.groupby("start"):
        codes = grp["code"].astype(str).str.zfill(6)
        q = codes + np.where(codes.str[0].isin(["6", "9"]), "_SH", "_SZ")
        out[pd.Timestamp(d).normalize()] = set(q)
    return out


def diag(present_min=6, rank_eligible=True, drop=(), nan_policy="skip"):
    """WHY do 果仁's held names miss my top-20? Categorize each held name."""
    factors, pe, rawnotna, rebal, pdays = _load_cache()
    elig = _eligibility(pe, rawnotna, rebal, pdays)
    comp = _composite(factors, present_min, eligible_mask=elig if rank_eligible else None,
                      drop=drop, nan_policy=nan_policy).where(elig)
    g_by_date = _guorn_by_date()
    g_dates = pd.DatetimeIndex(sorted(g_by_date))
    insts = set(pe.columns)
    cats = {"in_top20": 0, "eligible_ranked_low": 0, "filtered_pe": 0, "filtered_suspend": 0,
            "filtered_st_or_delist": 0, "low_coverage_NaN": 0, "not_in_my_universe": 0}
    pctls, n_g = [], 0
    for d, pday in zip(rebal, pdays):
        posj = g_dates.searchsorted(d)
        cand = [g_dates[j] for j in (posj - 1, posj) if 0 <= j < len(g_dates) and abs((g_dates[j] - d).days) <= 4]
        if not cand:
            continue
        gd = min(cand, key=lambda c: abs((c - d).days))
        gset = g_by_date[gd]
        row = comp.loc[pday]
        elig_row = elig.loc[pday]
        top20 = set(row.dropna().sort_values(ascending=False).head(TOP_N).index)
        elig_vals = row.dropna()
        for g in gset:
            n_g += 1
            if g not in insts:
                cats["not_in_my_universe"] += 1; continue
            if g in top20:
                cats["in_top20"] += 1
                pctls.append(1.0); continue
            if bool(elig_row.get(g, False)) and pd.notna(row.get(g, np.nan)):
                cats["eligible_ranked_low"] += 1
                pctls.append(float((elig_vals < row[g]).mean()))
            elif not bool(elig_row.get(g, False)):
                if not bool(rawnotna.loc[pday].get(g, False)):
                    cats["filtered_suspend"] += 1
                elif not (0 < (pe.loc[pday].get(g, np.nan) if pd.notna(pe.loc[pday].get(g, np.nan)) else -1) < 60):
                    cats["filtered_pe"] += 1
                else:
                    cats["filtered_st_or_delist"] += 1
            else:
                cats["low_coverage_NaN"] += 1
    print(f"=== #59 diag (present_min={present_min}, rank_eligible={rank_eligible}) — {n_g} 果仁 held-name-instances ===")
    for k, v in cats.items():
        print(f"  {k:24} {v:6}  ({v/max(n_g,1):.1%})")
    if pctls:
        ar = np.array(pctls)
        print(f"  果仁-names' percentile in MY ranking: median={np.median(ar):.3f} mean={ar.mean():.3f} "
              f"(1.0=top). frac in top-20={np.mean(ar==1.0):.1%}")


def check_overlap():
    sched = json.loads(SCHED.read_text(encoding="utf-8"))
    g_by_date = _guorn_by_date()
    g_dates = pd.DatetimeIndex(sorted(g_by_date))
    rows = []
    for ds, mine in sched.items():
        if not mine:
            continue
        d = pd.Timestamp(ds)
        posj = g_dates.searchsorted(d)
        cand = [g_dates[j] for j in (posj - 1, posj) if 0 <= j < len(g_dates) and abs((g_dates[j] - d).days) <= 4]
        if not cand:
            continue
        gd = min(cand, key=lambda c: abs((c - d).days))
        gset = g_by_date[gd]
        mset = {c.replace(".", "_") for c in mine}
        rows.append((d.year, len(mset & gset), len(gset), len(mset)))
    df = pd.DataFrame(rows, columns=["yr", "inter", "n_guorn", "n_mine"])
    by = df.groupby("yr").agg(periods=("inter", "size"), overlap=("inter", "sum"), guorn=("n_guorn", "sum"))
    by["pct"] = (by["overlap"] / by["guorn"]).round(3)
    tot = df["inter"].sum() / df["n_guorn"].sum()
    print("=== #59 holdings overlap (my top-20 ∩ 果仁 / 果仁) ===")
    print(by.to_string())
    print(f"\nOVERALL overlap = {tot:.1%}  ({len(df)} periods)")
    return tot


class EqualWeightScheduleStrategy(Strategy):
    def __init__(self, schedule, n=TOP_N):
        super().__init__()
        self.schedule = {pd.Timestamp(d): list(c) for d, c in schedule.items()}
        self.n = int(n)

    def initialize(self, context):
        return None

    def on_bar(self, context):
        return []

    def after_market_close(self, context):
        return None

    def before_market_open(self, context):
        from src.backtest_engine.event_driven.strategies import _emit_rebalance_orders
        names = self.schedule.get(pd.Timestamp(context.date))
        if not names:
            return []
        names = names[:self.n]
        return _emit_rebalance_orders({c: 1.0 / len(names) for c in names}, context)


def _read_guorn_yearly():
    df = pd.read_excel(ROOT / "Knowledge/果仁回测结果/59_Comp_Core_Quality.xlsx", sheet_name=3, header=0)
    out = {}
    for _, r in df.iterrows():
        try:
            y = int(str(r.iloc[0])[:4])
        except Exception:
            continue
        v = pd.to_numeric(r.iloc[1], errors="coerce")
        if pd.notna(v):
            out[y] = float(v) / (100.0 if abs(v) > 3 else 1.0)
    return out


def run(start, end):
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    sched = json.loads(SCHED.read_text(encoding="utf-8"))
    strat = EqualWeightScheduleStrategy(sched)
    cost = CostConfig(buy_commission=0.002, sell_commission=0.002, stamp_tax=0.0,
                      min_commission=0.0, transfer_fee=0.0)
    bt = EventDrivenBacktester(data_dir=str(ROOT / "data"))
    res = bt.run(strategy=strat, start_time=start, end_time=end, benchmark="000300.SH",
                 account=1_000_000.0, exchange_config=cost, slippage=FixedSlippage(0.0),
                 volume_limit=0.10,
                 preload_fields=["$open", "$close", "$high", "$low", "$vol", "$amount",
                                 "$pre_close", "$adj_factor"])
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    net = rep["return"].astype(float)
    net.to_frame("net").to_parquet(OUT / "rung6_net.parquet")
    m = ru.goal_metrics(net)
    m["sharpe_rf4"] = ru.sharpe(net, rf=0.04)
    yr = net.groupby(net.index.year).apply(lambda r: (1 + r).prod() - 1)
    yearly = {int(y): float(v) for y, v in yr.items()}
    gy = _read_guorn_yearly()
    print("\n" + "=" * 70)
    print(f"  LOCAL annual≈{m['cagr']:+.2%} Sharpe(rf4%)={m['sharpe_rf4']:.2f} MDD={m['mdd']:+.2%} vol={m['ann_vol']:.2%}")
    print(f"  果仁  annual={GR_HEADLINE['annual']:+.2%} Sharpe={GR_HEADLINE['sharpe']:.2f} "
          f"MDD={-GR_HEADLINE['mdd']:+.2%} vol={GR_HEADLINE['vol']:.2%} (beta {GR_HEADLINE['beta']})")
    print("  year     LOCAL      果仁     diff")
    for y in sorted(yearly):
        g = gy.get(y)
        gtxt = f"{g:+7.1%}" if g is not None else "   n/a "
        dtxt = f"{yearly[y]-g:+7.1%}" if g is not None else ""
        print(f"  {y}   {yearly[y]:+8.1%}  {gtxt}  {dtxt}")
    out = dict(local=m, local_yearly=yearly, guoren_headline=GR_HEADLINE, guoren_yearly=gy,
               start=start, end=end, top_n=TOP_N, rebal_every=REBAL_EVERY)
    (OUT / "rung6_result.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print("\nNON-FORMAL PARITY ARTIFACT — validates the strategy-construction layer vs 果仁; NOT sealed/deployable.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--build-stability", action="store_true", help="add the 2 STDEVQ(.,12) factors from a deep-slot provider")
    ap.add_argument("--select", action="store_true")
    ap.add_argument("--diag", action="store_true")
    ap.add_argument("--check-overlap", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--present-min", type=int, default=6)
    ap.add_argument("--rank-eligible", default="off", choices=["on", "off"])
    ap.add_argument("--drop-stab", action="store_true", help="exclude the stability factor (9-factor ablation)")
    ap.add_argument("--nan-policy", default="skip", choices=["skip", "worst"])
    ap.add_argument("--provider-dir", default=None, help="override qlib provider (staged deep-slot build)")
    ap.add_argument("--start", default="2014-01-01")
    ap.add_argument("--end", default="2026-06-20")
    args = ap.parse_args()
    if args.provider_dir:
        global PROVIDER_URI
        PROVIDER_URI = args.provider_dir
    re_ = (args.rank_eligible == "on")
    drop = {"STDEVQ(RoeCoreQ,12)=stab", "STDEVQ(SalesQGr,12)=stab"} if args.drop_stab else set()
    if args.build:
        build(args.start, args.end)
    if args.build_stability:
        build_stability(args.provider_dir or PROVIDER_URI)
    if args.select:
        select(present_min=args.present_min, rank_eligible=re_, drop=drop, nan_policy=args.nan_policy)
    if args.diag:
        diag(present_min=args.present_min, rank_eligible=re_, drop=drop, nan_policy=args.nan_policy)
    if args.check_overlap:
        check_overlap()
    if args.run:
        run(args.start, args.end)


if __name__ == "__main__":
    main()
