# SCRIPT_STATUS: ACTIVE — 果仁 #9 重股息 → cross-style Pareto-optimization book (IS 2014-2020 DESIGN; OOS SEALED)
"""Optimize 果仁 deployed book #9 (value_红利低波_重股息) into a Pareto-superior cross-style book.

BENCHMARK = 果仁's OWN deployed selection, run through OUR engine (same-engine REPLAY, the fair bar):
  #9 REPLAY  CAGR +33.34% / MDD -33.9% / Sharpe ~1.27 (果仁 published +33.25% / -32.95% / 1.27).
GOAL = a book that PARETO-DOMINATES it: CAGR >= bar AND MDD <= bar AND Sharpe >= bar (>=1 strict, no
  regression) — measured at the DEPLOYED-BOOK level (event-driven, 1x total return), NOT factor LS-decile.

LOCKED deployment envelope (identical to #9 — only the SIGNAL changes; §ledger deployed_20 #9):
  universe   : in_guorn_universe (主板+创业板, EXCL STAR/BSE) ∧ _is_ashare_stock, listed, ¬ST, close>=2
  trade model: Model-I, 5d rebalance on 果仁's OWN 606-period grid, ~open fill, TOP-10, w ∝ sqrt(circ_mv)
  cost/exec  : 0.2%/side, slippage 0, volume_limit 0.10, hold_on_limit_up, benchmark 000300.SH
  window     : book history 2014-01-02 .. 2026-02-27  →  IS 2014..2020 (design) / OOS 2021..2026 (SEALED)

THE THREE PARETO LEVERS (user-chosen 2026-07-04):
  (1) 多风格分散 — cross-style pool (guorn quality/growth + catalog value/momentum/low-vol/liquidity/reversal)
  (2) 市值/行业中性化 — per-date residualize each factor vs log(circ_mv) [+ SW-L1 industry] over the BROAD
      ESTU then mask to eligible (transform-then-mask, memory project_matrix_residual_decoupling)
  (3) 权重优化 — equal-z vs IS-IC-weighted composite (IS-IC used for DIRECTION and optional magnitude)

PIT: every catalog factor is Ref(...,1) wrapped → the optimized book is FORMAL-quality / deployable
  (the benchmark REPLAY is 果仁's real holdings, no factor lag involved — the comparison is honest).
NON-FORMAL parity tooling for the IS design search; the OOS spend is a GATED one-shot (see --run --oos).

Reuses: guorn_verify_09_divheavy (universe cache, rebalance grid, dividend screens),
        guorn_verify_07_divlowvol (Model-I strategy, _pdays/_bounds/_row/_sw_asof/_cgb_series),
        research_utils (goal_metrics), factor_library.operators.compute_factors (the cross-style pool).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "workspace" / "research" / "long_only_50cagr"),
          str(ROOT / "workspace" / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.stdout.reconfigure(encoding="utf-8")

import research_utils as ru                                   # noqa: E402
import guorn_verify_07_divlowvol as v7                        # noqa: E402  (Model-I, _pdays/_bounds/_row/_sw_asof/_cgb)
import guorn_verify_09_divheavy as v9                         # noqa: E402  (universe cache, grid, dividend screens)
from guorn_universe import in_guorn_universe                  # noqa: E402
from guorn_beta import _is_ashare_stock                       # noqa: E402

OUT = ROOT / "workspace" / "outputs" / "guorn_parity"
V9C = OUT / "verify09_cache"                                  # reuse #9's built universe / circ_mv / dividend frames
CACHE = OUT / "optimize09_cache"
CACHE.mkdir(parents=True, exist_ok=True)
PANEL = CACHE / "factor_panel"                                # one parquet per factor (date × code) + fwd
PANEL.mkdir(parents=True, exist_ok=True)
QLIB = str(ROOT / "data" / "qlib_data")

IS_START, IS_END = "2014-01-02", "2020-12-31"
OOS_START, OOS_END = "2021-01-01", "2026-02-27"
PANEL_START = "2012-06-01"                                    # 250d+ lookback buffer before IS_START
BAR = dict(cagr=0.3325, mdd=-0.3295, sharpe=1.27)             # 果仁 published #9 (== REPLAY within noise)

# ── cross-style pool: factor -> style bucket. Direction is IS-IC-signed at build (not hard-coded). ──
POOL = {
    "grn_core_profit_qgr": "quality",   "grn_roe_ttm_diff_q": "quality",
    "grn_ato_diff_py": "quality",       "qual_gross_profitability": "quality",
    "val_bp": "value",                  "val_ep_ttm": "value",             "grn_gp_ev": "value",
    "grn_onmom_250_20": "momentum",     "mom_skip1m_252d": "momentum",
    "risk_vol_20d": "lowvol",
    "liq_amihud_20d": "liquidity",      "liq_zero_ret_days_10d": "liquidity",
    "rev_return_5d": "reversal",
}

POOL_NOMOM = [f for f in POOL if f != "mom_skip1m_252d"]        # drop the IS-dead 12M momentum (IC ~0)
# DEPLOYABLE pools — drop the "fast/gappy" factors whose close-to-close edge dies under open-fill:
#   grn_onmom_250_20 (overnight return — the move happens when you can't trade),
#   rev_return_5d (5d reversal — churns + bounce names gap to limit-up), mom_skip1m_252d (IS-dead).
POOL_SLOW = [f for f in POOL if f not in ("grn_onmom_250_20", "rev_return_5d", "mom_skip1m_252d")]
POOL_CORE = ["grn_core_profit_qgr", "grn_roe_ttm_diff_q", "grn_ato_diff_py", "qual_gross_profitability",
             "val_bp", "val_ep_ttm", "grn_gp_ev", "risk_vol_20d"]   # value+quality+lowvol only (slowest)

# named design variants (elig ∈ keep9|div_anchor|full ; weight ∈ eq|ic ; neut ∈ size|size_ind|none)
VARIANTS = {
    # round 1 — span eligibility × weight × neutralization
    "v0_keep9_eq_size":   dict(elig="keep9",      weight="eq", neut="size",     pool=list(POOL)),
    "v1_div_eq_size":     dict(elig="div_anchor", weight="eq", neut="size",     pool=list(POOL)),
    "v2_full_eq_size":    dict(elig="full",       weight="eq", neut="size",     pool=list(POOL)),
    "v3_div_ic_size":     dict(elig="div_anchor", weight="ic", neut="size",     pool=list(POOL)),
    "v4_div_eq_sizeind":  dict(elig="div_anchor", weight="eq", neut="size_ind", pool=list(POOL)),
    # round 2 — un-neutralized CAGR ceiling (keeps small-cap/illiq return) + dead-momentum dropped
    "v5_full_eq_none":    dict(elig="full",       weight="eq", neut="none",     pool=POOL_NOMOM),
    "v6_div_eq_none":     dict(elig="div_anchor", weight="eq", neut="none",     pool=POOL_NOMOM),
    "v7_full_ic_size":    dict(elig="full",       weight="ic", neut="size",     pool=POOL_NOMOM),
    "v8_div_ic_none":     dict(elig="div_anchor", weight="ic", neut="none",     pool=POOL_NOMOM),
    # round 3 — DIVERSIFY (harvest the +0.071 IC / monotonic decile at more holdings) + industry-neutral
    "v9_full_eq_sind_k20":  dict(elig="full",       weight="eq", neut="size_ind", pool=POOL_NOMOM, topk=20),
    "v10_full_eq_sind_k30": dict(elig="full",       weight="eq", neut="size_ind", pool=POOL_NOMOM, topk=30),
    "v11_full_eq_size_k30": dict(elig="full",       weight="eq", neut="size",     pool=POOL_NOMOM, topk=30),
    "v12_div_eq_sind_k30":  dict(elig="div_anchor", weight="eq", neut="size_ind", pool=POOL_NOMOM, topk=30),
    # round 4 — DEPLOYABLE slow pools (drop onmom/reversal): does the paper→backtest gap collapse?
    "s1_slow_sind_k20":   dict(elig="full", weight="eq", neut="size_ind", pool=POOL_SLOW, topk=20),
    "s2_slow_sind_k30":   dict(elig="full", weight="eq", neut="size_ind", pool=POOL_SLOW, topk=30),
    "s3_core_sind_k30":   dict(elig="full", weight="eq", neut="size_ind", pool=POOL_CORE, topk=30),
    "s4_slow_sind_k20_eqw": dict(elig="full", weight="eq", neut="size_ind", pool=POOL_SLOW, topk=20, wmode="equal"),
}


# ================================================================ factor panel (compute + cache) ====
def _universe_cols():
    return list(pd.read_parquet(V9C / "e_close_raw.parquet").columns)


def build_panel(start=PANEL_START, end=IS_END, smoke=False):
    """compute_factors over the pool (+ fwd 5/20d) via the sanctioned windowed door; cache one
    date×code parquet per factor. OOS is NOT computed here (end defaults to IS_END). A --smoke run
    computes on 2014-H1 only and asserts 0 native-compute crash (the 门1 cross-dataset-broadcast gate)."""
    from src.alpha_research.factor_library import operators as op
    from src.alpha_research.factor_library.catalog import get_factor_catalog
    cat = get_factor_catalog(include_new_data=True)
    sub = {f: cat[f] for f in POOL}
    if smoke:
        start, end = "2014-01-02", "2014-06-30"
    print(f"[panel] compute {len(sub)} factors + fwd(5,20) {start}..{end} (all_stocks, kernels=1)", flush=True)
    panel, fwd = op.compute_factors(catalog=sub, start_date=start, end_date=end, horizons=[5, 20],
                                    qlib_dir=QLIB, kernels=1, stage="is_only")
    # compute_factors → MultiIndex(datetime, instrument); merge factors + fwd, access by named level
    both = panel.join(fwd) if fwd is not None and len(fwd) else panel
    cols = _universe_cols()
    for f in list(POOL) + ["fwd_5d", "fwd_20d"]:
        if f not in both.columns:
            print(f"[panel]   !! {f} MISSING from compute output", flush=True)
            continue
        wide = both[f].unstack("instrument").sort_index().reindex(columns=cols)
        nz = float(wide.notna().mean().mean())
        if smoke:
            print(f"[smoke]   {f:26} coverage={nz:.3f}  (0 crash ✓)", flush=True)
        else:
            wide.astype("float32").to_parquet(PANEL / f"{f}.parquet")
    print(f"[panel] {'SMOKE ok — no build_panel crash' if smoke else f'cached -> {PANEL}'}", flush=True)


def _load_factor(f):
    return pd.read_parquet(PANEL / f"{f}.parquet")


# ================================================================ IS-IC orientation ================
def build_is_ic():
    """Per-factor IS rank-IC vs fwd_5d over IS rebalance dates (fwd clamped inside IS). Gives the
    signal DIRECTION (sign) and optional IC magnitude (ic-weight). IS-only look — OOS validates."""
    cols = _universe_cols()
    fwd = _load_factor("fwd_5d")
    rebal = [d for d in v9.rebalance_grid(IS_END) if pd.Timestamp(IS_START) <= d <= pd.Timestamp("2020-12-24")]
    ic = {}
    for f in POOL:
        fr = _load_factor(f)
        vals = []
        for d in rebal:
            if d not in fr.index or d not in fwd.index:
                continue
            a, b = fr.loc[d], fwd.loc[d]
            m = a.notna() & b.notna()
            if m.sum() < 100:
                continue
            vals.append(a[m].rank().corr(b[m].rank()))
        ic[f] = float(np.nanmean(vals)) if vals else np.nan
    (CACHE / "is_ic.json").write_text(json.dumps(ic, indent=1), encoding="utf-8")
    print("[is-ic] IS rank-IC (fwd_5d), signed direction:", flush=True)
    for f, v in sorted(ic.items(), key=lambda kv: -abs(kv[1])):
        print(f"  {f:26} IC={v:+.4f}  style={POOL[f]}", flush=True)
    return ic


# ================================================================ neutralize + composite ============
def _sw_l1(pdays, cols):
    """SW-2021 L1 industry name as-of each pday (for industry neutralization). Column probed from the
    members parquet (l1_name / industry_name variants handled)."""
    m = pd.read_parquet(v7.SWM)
    lvl = next((c for c in ("l1_name", "sw_l1", "industry_l1", "l1") if c in m.columns), None)
    if lvl is None:
        raise SystemExit(f"SW members parquet has no L1 name column; cols={list(m.columns)}")
    return v7._sw_asof(lvl, pdays, cols)


def _neutralize(fval, logmv, ind, broad, mode):
    """Residualize fval vs [1, logmv (+ industry dummies)] over broad; winsorize-then-neutralize; return
    a broad-scoped z-score (NaN off-broad). transform-then-mask (memory project_matrix_residual_decoupling)."""
    x = fval.where(broad)
    lo, hi = x.quantile(0.01), x.quantile(0.99)
    x = x.clip(lo, hi)
    if mode == "none":                                          # winsorize + z only (no residualization)
        z = (x - x.mean()) / (x.std(ddof=0) or 1.0)
        return z.where(broad)
    ok = x.notna() & logmv.notna()
    if ok.sum() < 30:
        return pd.Series(np.nan, index=fval.index)
    cols_df = {"logmv": logmv[ok]}
    if mode == "size_ind":
        d = pd.get_dummies(ind[ok].astype("object").fillna("NA"), prefix="ind", drop_first=True)
        for c in d.columns:
            cols_df[c] = d[c].astype(float)
    X = pd.DataFrame(cols_df, index=x.index[ok])
    X.insert(0, "const", 1.0)
    y = x[ok].astype(float)
    beta, *_ = np.linalg.lstsq(X.values, y.values, rcond=None)
    resid = y - X.values @ beta
    z = (resid - resid.mean()) / (resid.std(ddof=0) or 1.0)
    return z.reindex(fval.index)


def _elig_frames(mode, cols):
    """Preload the eligibility frames ONCE (hoisted out of the per-date loop)."""
    if mode == "full":
        return {}
    rd = lambda n: pd.read_parquet(V9C / f"{n}.parquet").reindex(columns=cols)  # noqa: E731
    if mode == "div_anchor":
        return {"contdiv3": rd("f_contdiv3")}
    fr = {n.replace("f_", ""): rd(n) for n in ("f_contdiv3", "f_divop", "f_payout3ok", "f_div3y", "f_dyttm")}
    fr["idxflag"] = rd("e_idxflag")
    fr["cgb_ma60"] = v7._cgb_series().rolling(60).mean()
    return fr


def _elig_mask(mode, fr, d, pday, cols):
    """Eligibility boolean over `cols` for a rebalance date (frames preloaded via _elig_frames)."""
    if mode == "full":
        return pd.Series(True, index=cols)
    if mode == "div_anchor":
        return v7._row(fr["contdiv3"], pday).fillna(0).astype(bool)
    keep = pd.Series(True, index=cols)                          # keep9: #9's 8 dividend/macro screens
    keep &= v7._row(fr["contdiv3"], pday).fillna(0).astype(bool)
    dop = v7._row(fr["divop"], pday)
    keep &= ((dop >= 0.10) & (dop <= 2.00)).fillna(False)
    cma60 = fr["cgb_ma60"]
    cpos = cma60.index.searchsorted(pd.Timestamp(d), side="right")
    cma = float(cma60.iloc[cpos - 1]) if cpos > 0 else np.nan
    keep &= ((v7._row(fr["dyttm"], pday) - cma) > 0.02).fillna(False)
    keep &= v7._row(fr["payout3ok"], pday).fillna(0).astype(bool)
    keep &= (v7._row(fr["div3y"], pday) > 5e7).fillna(False)
    keep &= v7._row(fr["idxflag"], pday).fillna(0).astype(int) == 0
    return keep


def build_signal(variant):
    cfg = VARIANTS[variant]
    pool = cfg["pool"]
    ic = json.loads((CACHE / "is_ic.json").read_text())
    sign = {f: (1.0 if ic.get(f, 0) >= 0 else -1.0) for f in pool}
    wmag = {f: (abs(ic.get(f, 0.0)) if cfg["weight"] == "ic" else 1.0) for f in pool}
    cols = _universe_cols()
    close = pd.read_parquet(V9C / "e_close_raw.parquet")
    circ = pd.read_parquet(V9C / "e_circ_mv.parquet").reindex(columns=cols)
    grid = close.index
    bounds = v7._bounds()
    rebal = [d for d in v9.rebalance_grid(IS_END) if pd.Timestamp(IS_START) <= d <= pd.Timestamp(IS_END)]
    pmap = v7._pdays(rebal, grid)
    frames = {f: _load_factor(f) for f in pool}
    need_ind = cfg["neut"] == "size_ind"
    ind_asof = _sw_l1([pmap[d] for d in rebal if d in pmap], cols) if need_ind else None
    efr = _elig_frames(cfg["elig"], cols)

    sched, n_elig = {}, []
    for d in rebal:
        pday = pmap.get(d)
        if pday is None:
            sched[str(d.date())] = []
            continue
        cr = close.loc[pday]
        st = ru.st_codes_on(d)
        listed = pd.Series([(bounds.get(str(c).upper()) is not None
                             and bounds[str(c).upper()][0] <= pday <= bounds[str(c).upper()][1])
                            for c in cols], index=cols)
        not_st = pd.Series([str(c).upper() not in st for c in cols], index=cols)
        broad = listed & cr.notna() & not_st & (cr >= 2.0).fillna(False)
        if broad.sum() < 30:
            sched[str(d.date())] = []
            continue
        logmv = np.log(circ.loc[pday].where(circ.loc[pday] > 0))
        ind = ind_asof.loc[pday] if (need_ind and pday in ind_asof.index) else pd.Series("NA", index=cols)
        comp = pd.Series(0.0, index=cols)
        wsum = pd.Series(0.0, index=cols)
        for f in pool:
            fr = frames[f]
            fval = (fr.loc[d] if d in fr.index else v7._row(fr, d)).reindex(cols)
            z = _neutralize(fval, logmv, ind, broad, cfg["neut"]) * sign[f]
            add = z * wmag[f]
            comp = comp.add(add.fillna(0.0), fill_value=0.0)
            wsum = wsum.add(add.notna().astype(float) * wmag[f], fill_value=0.0)
        comp = (comp / wsum.where(wsum > 0)).where(broad)          # mean of available oriented z
        elig = broad & _elig_mask(cfg["elig"], efr, d, pday, cols)
        comp = comp.where(elig)
        n = int(comp.notna().sum())
        n_elig.append(n)
        top = comp.sort_values(ascending=False).head(cfg.get("topk", 10))
        wmode = cfg.get("wmode", "sqrt_mv")
        if wmode == "signal":                                  # conviction: explicit positive weights ∝ comp
            sc = comp.reindex(top.index); sc = sc - sc.min() + 1e-6
            wval = sc / sc.sum()
        elif wmode == "equal":                                 # 1.0 basis → sqrt(1)=equal after normalize
            wval = pd.Series(1.0, index=top.index)
        else:                                                  # sqrt_mv (#9 default): circ_mv basis
            wval = circ.loc[pday].reindex(top.index)
        sched[str(d.date())] = [[str(c).upper().replace("_", "."), float(wval.get(c, np.nan))]
                                for c in top.index if pd.notna(wval.get(c)) and wval.get(c) > 0]
    (CACHE / f"sched_{variant}.json").write_text(json.dumps(sched, ensure_ascii=False), encoding="utf-8")
    ne = pd.Series(n_elig)
    print(f"[signal {variant}] {sum(1 for v in sched.values() if v)}/{len(rebal)} non-empty; "
          f"elig p10/med/p90 = {ne.quantile(.1):.0f}/{ne.median():.0f}/{ne.quantile(.9):.0f}", flush=True)


# ================================================================ engine run (IS default; OOS gated) =
def run(variant, window="is", spend_oos=False):
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    if window == "oos" and not spend_oos:
        raise SystemExit("REFUSED: --window oos is the one-shot sealed spend. Pass --i-am-spending-oos "
                         "AND have GPT design sign-off + user go (§13). IS design uses --window is.")
    start, end = (IS_START, IS_END) if window == "is" else \
                 (OOS_START, OOS_END) if window == "oos" else (IS_START, OOS_END)
    sched = json.loads((CACHE / f"sched_{variant}.json").read_text(encoding="utf-8"))
    k = VARIANTS[variant].get("topk", 10)
    strat = v7.ModelIDivLowVolStrategy(sched, max_holds=k, reserve=k)     # sqrt(circ_mv) weights
    cost = CostConfig(buy_commission=0.002, sell_commission=0.002, stamp_tax=0.0,
                      min_commission=0.0, transfer_fee=0.0)
    bt = EventDrivenBacktester(data_dir=str(ROOT / "data"))
    res = bt.run(strategy=strat, start_time=start, end_time=end, benchmark="000300.SH",
                 account=1_000_000.0, exchange_config=cost, slippage=FixedSlippage(0.0),
                 volume_limit=0.10, hold_on_limit_up=True,
                 preload_fields=["$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close",
                                 "$adj_factor", "$up_limit", "$down_limit"])
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    net = rep["return"].astype(float)
    net.to_frame("net").to_parquet(CACHE / f"net_{variant}_{window}.parquet")
    print(f"[run {variant} {window}] saved net ({len(net)} days {start}..{end})", flush=True)


# ================================================================ metrics + Pareto verdict ==========
def _turnover(variant):
    sched = json.loads((CACHE / f"sched_{variant}.json").read_text(encoding="utf-8"))
    keys = sorted(sched)
    prev, tos = None, []
    for k in keys:
        cur = {str(x[0]) for x in sched[k]} if sched[k] else set()
        if prev is not None and (prev or cur):
            tos.append(len(prev ^ cur) / (2 * max(len(prev | cur), 1)))
        prev = cur
    return float(np.mean(tos)) if tos else np.nan


def _metrics(net, label, turnover=np.nan):
    m = ru.goal_metrics(net)
    m["calmar"] = m["cagr"] / abs(m["mdd"]) if m["mdd"] else np.nan
    m["turnover"] = turnover
    print(f"  {label:22} CAGR={m['cagr']:+.2%}  MDD={m['mdd']:+.2%}  Sharpe={m['sharpe']:.2f}  "
          f"Calmar={m['calmar']:.2f}  vol={m['ann_vol']:.1%}  turn={turnover:.2f}", flush=True)
    return m


def benchmark():
    """Segment the #9 REPLAY (果仁 holdings × our engine) into IS/OOS — the same-engine Pareto bar."""
    print("\n=== #9 benchmark (same-engine) — the Pareto bar ===", flush=True)
    out = {}
    for tag, fn in (("REPLAY", "verify09_replay_net.parquet"), ("LOCAL(faithful)", "verify09_net.parquet")):
        p = OUT / fn
        if not p.exists():
            print(f"  {tag:22} MISSING {fn}", flush=True)
            continue
        net = pd.read_parquet(p)["net"]
        net.index = pd.to_datetime(net.index)
        out[tag] = {"IS": _metrics(net[IS_START:IS_END], f"{tag} IS"),
                    "OOS": _metrics(net[OOS_START:OOS_END], f"{tag} OOS"),
                    "full": _metrics(net, f"{tag} full")}
    (CACHE / "benchmark.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"  Pareto bar (IS, REPLAY): CAGR>={BAR['cagr']:.2%}  MDD<={BAR['mdd']:.2%}  Sharpe>={BAR['sharpe']}",
          flush=True)


def diag(variant):
    """Signal-quality autopsy: the COMPOSITE's IS rank-IC (5d/20d), decile-mean fwd_20d monotonicity,
    and the top-10's median size percentile — isolates 'weak signal / top-10 concentration' from a
    construction bug BEFORE blaming execution."""
    cfg = VARIANTS[variant]
    pool = cfg["pool"]
    ic = json.loads((CACHE / "is_ic.json").read_text())
    sign = {f: (1.0 if ic.get(f, 0) >= 0 else -1.0) for f in pool}
    wmag = {f: (abs(ic.get(f, 0.0)) if cfg["weight"] == "ic" else 1.0) for f in pool}
    cols = _universe_cols()
    close = pd.read_parquet(V9C / "e_close_raw.parquet")
    circ = pd.read_parquet(V9C / "e_circ_mv.parquet").reindex(columns=cols)
    fwd5, fwd20 = _load_factor("fwd_5d"), _load_factor("fwd_20d")
    grid = close.index
    bounds = v7._bounds()
    rebal = [d for d in v9.rebalance_grid("2020-12-24") if pd.Timestamp(IS_START) <= d]
    pmap = v7._pdays(rebal, grid)
    frames = {f: _load_factor(f) for f in pool}
    efr = _elig_frames(cfg["elig"], cols)
    ind_asof = _sw_l1([pmap[d] for d in rebal if d in pmap], cols) if cfg["neut"] == "size_ind" else None
    ic5, ic20, dec_rows, top_sz = [], [], [], []
    for d in rebal:
        pday = pmap.get(d)
        if pday is None or d not in fwd5.index:
            continue
        cr = close.loc[pday]
        st = ru.st_codes_on(d)
        listed = pd.Series([(bounds.get(str(c).upper()) is not None
                             and bounds[str(c).upper()][0] <= pday <= bounds[str(c).upper()][1])
                            for c in cols], index=cols)
        not_st = pd.Series([str(c).upper() not in st for c in cols], index=cols)
        broad = listed & cr.notna() & not_st & (cr >= 2.0).fillna(False)
        if broad.sum() < 30:
            continue
        logmv = np.log(circ.loc[pday].where(circ.loc[pday] > 0))
        ind = ind_asof.loc[pday] if (ind_asof is not None and pday in ind_asof.index) else pd.Series("NA", index=cols)
        comp = pd.Series(0.0, index=cols); wsum = pd.Series(0.0, index=cols)
        for f in pool:
            fval = (frames[f].loc[d] if d in frames[f].index else v7._row(frames[f], d)).reindex(cols)
            z = _neutralize(fval, logmv, ind, broad, cfg["neut"]) * sign[f]
            add = z * wmag[f]
            comp = comp.add(add.fillna(0.0), fill_value=0.0)
            wsum = wsum.add(add.notna().astype(float) * wmag[f], fill_value=0.0)
        comp = (comp / wsum.where(wsum > 0)).where(broad)
        comp = comp.where(broad & _elig_mask(cfg["elig"], efr, d, pday, cols))
        f5, f20 = fwd5.loc[d], fwd20.loc[d]
        m = comp.notna() & f5.notna()
        if m.sum() < 30:
            continue
        ic5.append(comp[m].rank().corr(f5[m].rank()))
        m20 = comp.notna() & f20.notna()
        ic20.append(comp[m20].rank().corr(f20[m20].rank()))
        # decile-mean fwd_20d (10 = top composite)
        try:
            q = pd.qcut(comp[m20], 10, labels=False, duplicates="drop")
            dec_rows.append(f20[m20].groupby(q).mean())
        except Exception:
            pass
        top = comp.sort_values(ascending=False).head(10).index
        szpct = circ.loc[pday].rank(pct=True).reindex(top)
        top_sz.append(float(szpct.median()))
    dec = pd.concat(dec_rows, axis=1).mean(axis=1) if dec_rows else pd.Series(dtype=float)
    print(f"\n=== diag {variant} (IS composite quality) ===", flush=True)
    print(f"  composite rank-IC: 5d={np.nanmean(ic5):+.4f}  20d={np.nanmean(ic20):+.4f}  (n={len(ic5)} dates)",
          flush=True)
    print(f"  top-10 median size-percentile = {np.nanmean(top_sz):.2f}  (1.0=largest; <0.3 => microcap tilt)",
          flush=True)
    if len(dec):
        print("  decile-mean fwd_20d (0=bottom composite, 9=top):", flush=True)
        print("   " + "  ".join(f"{i}:{v:+.3f}" for i, v in dec.items()), flush=True)
        print(f"  top-bottom decile spread (fwd_20d) = {dec.iloc[-1] - dec.iloc[0]:+.4f}", flush=True)


def _composite_series(cfg, cols, close, circ, frames, efr, ind_asof, bounds, rebal, pmap):
    """Yield (d, pday, comp, broad) for each rebalance date — shared by diag/ksweep."""
    ic = json.loads((CACHE / "is_ic.json").read_text())
    pool = cfg["pool"]
    sign = {f: (1.0 if ic.get(f, 0) >= 0 else -1.0) for f in pool}
    wmag = {f: (abs(ic.get(f, 0.0)) if cfg["weight"] == "ic" else 1.0) for f in pool}
    for d in rebal:
        pday = pmap.get(d)
        if pday is None:
            continue
        cr = close.loc[pday]
        st = ru.st_codes_on(d)
        listed = pd.Series([(bounds.get(str(c).upper()) is not None
                             and bounds[str(c).upper()][0] <= pday <= bounds[str(c).upper()][1])
                            for c in cols], index=cols)
        not_st = pd.Series([str(c).upper() not in st for c in cols], index=cols)
        broad = listed & cr.notna() & not_st & (cr >= 2.0).fillna(False)
        if broad.sum() < 30:
            continue
        logmv = np.log(circ.loc[pday].where(circ.loc[pday] > 0))
        ind = ind_asof.loc[pday] if (ind_asof is not None and pday in ind_asof.index) else pd.Series("NA", index=cols)
        comp = pd.Series(0.0, index=cols); wsum = pd.Series(0.0, index=cols)
        for f in pool:
            fval = (frames[f].loc[d] if d in frames[f].index else v7._row(frames[f], d)).reindex(cols)
            z = _neutralize(fval, logmv, ind, broad, cfg["neut"]) * sign[f]
            add = z * wmag[f]
            comp = comp.add(add.fillna(0.0), fill_value=0.0)
            wsum = wsum.add(add.notna().astype(float) * wmag[f], fill_value=0.0)
        comp = (comp / wsum.where(wsum > 0)).where(broad & _elig_mask(cfg["elig"], efr, d, pday, cols))
        yield d, pday, comp, broad


def ksweep(variant, ks=(10, 15, 20, 30, 50, 100)):
    """GROSS paper-portfolio frontier vs holdings-count K: equal-weight top-K, chain realized fwd_5d
    (no costs/slippage/limits). Fast upper-bound preview — finds the optimal K before backtesting.
    Net ≈ gross − ~6%/yr turnover drag."""
    cfg = VARIANTS[variant]
    cols = _universe_cols()
    close = pd.read_parquet(V9C / "e_close_raw.parquet")
    circ = pd.read_parquet(V9C / "e_circ_mv.parquet").reindex(columns=cols)
    fwd5 = _load_factor("fwd_5d")
    grid = close.index
    bounds = v7._bounds()
    rebal = [d for d in v9.rebalance_grid(IS_END) if pd.Timestamp(IS_START) <= d <= pd.Timestamp(IS_END)]
    pmap = v7._pdays(rebal, grid)
    frames = {f: _load_factor(f) for f in cfg["pool"]}
    efr = _elig_frames(cfg["elig"], cols)
    ind_asof = _sw_l1([pmap[d] for d in rebal if d in pmap], cols) if cfg["neut"] == "size_ind" else None
    rets = {k: {} for k in ks}
    for d, pday, comp, broad in _composite_series(cfg, cols, close, circ, frames, efr, ind_asof,
                                                  bounds, rebal, pmap):
        if d not in fwd5.index:
            continue
        f5 = fwd5.loc[d]
        ranked = comp.dropna().sort_values(ascending=False)
        for k in ks:
            top = ranked.head(k).index
            r = f5.reindex(top).dropna()
            if len(r):
                rets[k][d] = float(r.mean())            # equal-weight gross 5d return
    print(f"\n=== ksweep {variant} — GROSS paper top-K (equal-wt, fwd_5d chained, no costs) ===", flush=True)
    print(f"  bar (net) CAGR>={BAR['cagr']:.1%} Sharpe>={BAR['sharpe']} MDD<={BAR['mdd']:.1%}", flush=True)
    for k in ks:
        s = pd.Series(rets[k]).sort_index()
        if len(s) < 20:
            continue
        cagr = (1 + s).prod() ** (252 / (len(s) * 5)) - 1        # 5 trading days per period
        shp = s.mean() / s.std() * np.sqrt(252 / 5) if s.std() else np.nan
        nav = (1 + s).cumprod(); mdd = float((nav / nav.cummax() - 1).min())
        print(f"  K={k:3d}  gross CAGR={cagr:+.1%}  Sharpe={shp:.2f}  MDD={mdd:+.1%}  "
              f"(net CAGR≈{cagr-0.06:+.1%})", flush=True)


# ================================================================ PR2 prototype: risk-aware optimizer =
# Lifts the transfer coefficient (IR = IC·√breadth·TC). Replaces rank→top-K→weight with
# max αᵀw − λ·wᵀΣw s.t. long-only, Σw=1, w≤max_w. Σ = Ledoit-Wolf shrunk trailing covariance.
# Reuses src/portfolio_risk/optimizer.py's formulation (that skeleton hardcodes λ=1; here λ is swept).
def build_returns(start=PANEL_START, end=IS_END):
    """Adjusted daily-return panel (date×code) — the covariance input. One qlib read; OOS not touched."""
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    qlib.init(provider_uri=QLIB, region=REG_CN, kernels=1)
    cols = _universe_cols()
    print(f"[returns] read $close·$adj_factor {start}..{end} ({len(cols)} insts)", flush=True)
    df = D.features(cols, ["$close", "$adj_factor"], start_time=start, end_time=end, freq="day")
    adj = (df["$close"] * df["$adj_factor"]).unstack(level=0).sort_index().reindex(columns=cols)
    ret = adj.pct_change()
    ret.astype("float32").to_parquet(CACHE / "returns.parquet")
    print(f"[returns] cached {ret.shape} -> {CACHE / 'returns.parquet'}", flush=True)


def _shrink_cov(R):
    """Ledoit-Wolf shrunk covariance from a (T×N) return matrix (finite, full-history columns)."""
    try:
        from sklearn.covariance import LedoitWolf
        return LedoitWolf(assume_centered=False).fit(R).covariance_
    except Exception:
        S = np.cov(R, rowvar=False)
        mu = np.trace(S) / S.shape[0]
        return 0.8 * S + 0.2 * mu * np.eye(S.shape[0])       # shrink to scaled identity


def _optimize_mv(alpha, cov, max_w, lam):
    """Long-only mean-variance: max αᵀw − λ·wᵀΣw  s.t. Σw=1, 0≤w≤max_w. Fail-closed (None) if no solver."""
    import cvxpy as cp
    n = len(alpha)
    w = cp.Variable(n)
    obj = alpha @ w - lam * cp.quad_form(w, cp.psd_wrap(cov))
    cons = [cp.sum(w) == 1, w >= 0, w <= max_w]
    prob = cp.Problem(cp.Maximize(obj), cons)
    for s in ("CLARABEL", "ECOS", "OSQP", "SCS"):
        if s not in set(cp.installed_solvers()):
            continue
        try:
            prob.solve(solver=s)
        except Exception:
            continue
        if prob.status in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE} and w.value is not None:
            x = np.clip(np.asarray(w.value, dtype=float).ravel(), 0, None)
            return x / x.sum() if x.sum() > 0 else None
    return None                                              # fail closed — NO equal-weight fallback (formal)


def build_opt_signal(variant, lam=20.0, ncand=100, max_w=0.10, cov_lb=250):
    """alpha-screen top-ncand (deployable composite) → LW cov on trailing cov_lb returns → MV-optimize →
    explicit-weight schedule. The optimizer decides concentration (via λ) and per-name weight (via Σ)."""
    cfg = VARIANTS[variant]
    cols = _universe_cols()
    close = pd.read_parquet(V9C / "e_close_raw.parquet")
    circ = pd.read_parquet(V9C / "e_circ_mv.parquet").reindex(columns=cols)
    ret = pd.read_parquet(CACHE / "returns.parquet").reindex(columns=cols)
    grid = close.index
    bounds = v7._bounds()
    rebal = [d for d in v9.rebalance_grid(IS_END) if pd.Timestamp(IS_START) <= d <= pd.Timestamp(IS_END)]
    pmap = v7._pdays(rebal, grid)
    frames = {f: _load_factor(f) for f in cfg["pool"]}
    efr = _elig_frames(cfg["elig"], cols)
    ind_asof = _sw_l1([pmap[d] for d in rebal if d in pmap], cols) if cfg["neut"] == "size_ind" else None
    sched, nsel, nfail = {}, [], 0
    for d, pday, comp, broad in _composite_series(cfg, cols, close, circ, frames, efr, ind_asof,
                                                  bounds, rebal, pmap):
        cand = comp.dropna().sort_values(ascending=False).head(ncand)
        rr = ret.loc[:pday].tail(cov_lb)[list(cand.index)].dropna(axis=1, how="any")   # full-history names
        cand = cand[[c for c in cand.index if c in rr.columns]]
        if len(cand) < 10:
            sched[str(d.date())] = []
            continue
        cov = _shrink_cov(rr[list(cand.index)].values) * 252.0                          # annualized Σ
        a = cand.values.astype(float)
        a = (a - a.mean()) / (a.std() or 1.0)                                           # α = z within candidates
        w = _optimize_mv(a, cov, max_w, lam)
        if w is None:
            nfail += 1
            sched[str(d.date())] = []
            continue
        nsel.append(int((w > 1e-4).sum()))
        sched[str(d.date())] = [[str(c).upper().replace("_", "."), float(wi)]
                                for c, wi in zip(cand.index, w) if wi > 1e-4]
    (CACHE / f"sched_{variant}_opt.json").write_text(json.dumps(sched, ensure_ascii=False), encoding="utf-8")
    ns = pd.Series(nsel)
    print(f"[opt {variant} λ={lam} maxw={max_w}] {sum(1 for v in sched.values() if v)}/{len(rebal)} non-empty; "
          f"n_held p10/med/p90 = {ns.quantile(.1):.0f}/{ns.median():.0f}/{ns.quantile(.9):.0f}; "
          f"solver_fail={nfail}", flush=True)


def run_opt(variant, window="is", spend_oos=False, lam=None):
    """Event-driven run of an OPTIMIZED (explicit-weight) schedule."""
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    if window == "oos" and not spend_oos:
        raise SystemExit("REFUSED: --window oos is the one-shot sealed spend (need --i-am-spending-oos + go).")
    start, end = (IS_START, IS_END) if window == "is" else \
                 (OOS_START, OOS_END) if window == "oos" else (IS_START, OOS_END)
    sched = json.loads((CACHE / f"sched_{variant}_opt.json").read_text(encoding="utf-8"))
    strat = v7.ModelIDivLowVolStrategy(sched, max_holds=999, weights_mode="explicit")   # optimized weights
    cost = CostConfig(buy_commission=0.002, sell_commission=0.002, stamp_tax=0.0,
                      min_commission=0.0, transfer_fee=0.0)
    bt = EventDrivenBacktester(data_dir=str(ROOT / "data"))
    res = bt.run(strategy=strat, start_time=start, end_time=end, benchmark="000300.SH",
                 account=1_000_000.0, exchange_config=cost, slippage=FixedSlippage(0.0),
                 volume_limit=0.10, hold_on_limit_up=True,
                 preload_fields=["$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close",
                                 "$adj_factor", "$up_limit", "$down_limit"])
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    net = rep["return"].astype(float)
    net.to_frame("net").to_parquet(CACHE / f"net_{variant}_opt_{window}.parquet")
    to = _turnover_sched(sched)
    tag = f"{variant}_opt λ={lam}" if lam is not None else f"{variant}_opt"
    print(f"\n=== OPTIMIZED {tag} [{window}] vs #9 REPLAY bar ===", flush=True)
    m = _metrics(net, f"{tag} {window}", to)
    bmk = json.loads((CACHE / "benchmark.json").read_text())["REPLAY"][window.upper()] \
        if (CACHE / "benchmark.json").exists() else None
    if bmk:
        _metrics_from(bmk, "REPLAY bar")
        risk_win = (m["sharpe"] >= bmk["sharpe"] and m["mdd"] >= bmk["mdd"])
        print(f"  → ΔCAGR={m['cagr']-bmk['cagr']:+.2%}  ΔMDD={m['mdd']-bmk['mdd']:+.2%}  "
              f"ΔSharpe={m['sharpe']-bmk['sharpe']:+.2f}  "
              f"[{'RISK-ADJ WIN ✅' if risk_win else 'not yet'}]", flush=True)
    return m


def _turnover_sched(sched):
    keys = sorted(sched)
    prev, tos = None, []
    for k in keys:
        cur = {str(x[0]) for x in sched[k]} if sched[k] else set()
        if prev is not None and (prev or cur):
            tos.append(len(prev ^ cur) / (2 * max(len(prev | cur), 1)))
        prev = cur
    return float(np.mean(tos)) if tos else np.nan


def opt_frontier(variant, window="is", lams=(2.0, 10.0, 30.0, 100.0), ncand=100, max_w=0.10):
    """FAIL-FAST CONTROL (build-plan PR2): SAME deployable alpha, optimizer (risk-model MVO) vs naive top-K.
    Sweep λ to trace the risk/return frontier. If the optimizer lifts Sharpe + cuts MDD, the
    transfer-coefficient thesis is EMPIRICALLY confirmed before any heavy investment. IS-only."""
    if not (CACHE / "returns.parquet").exists():
        build_returns()
    rows = []
    for lam in lams:
        build_opt_signal(variant, lam=lam, ncand=ncand, max_w=max_w)
        rows.append((lam, run_opt(variant, window, lam=lam)))
    print("\n" + "=" * 82, flush=True)
    print(f"FAIL-FAST CONTROL — {variant} [{window}]: optimizer (risk-model MVO) vs naive top-K", flush=True)
    print("=" * 82, flush=True)
    bp = CACHE / f"net_{variant}_{window}.parquet"                      # the naive top-K baseline (same alpha)
    if bp.exists():
        bnet = pd.read_parquet(bp)["net"]
        bnet.index = pd.to_datetime(bnet.index)
        _metrics(bnet, f"{variant} TOP-K (naive)")
    for lam, m in rows:
        print(f"  MVO λ={lam:<6g} CAGR={m['cagr']:+.2%}  MDD={m['mdd']:+.2%}  Sharpe={m['sharpe']:.2f}  "
              f"Calmar={m['calmar']:.2f}  vol={m['ann_vol']:.1%}  turn={m['turnover']:.2f}", flush=True)
    if (CACHE / "benchmark.json").exists():
        b = json.loads((CACHE / "benchmark.json").read_text())["REPLAY"][window.upper()]
        print(f"  #9 REPLAY bar CAGR={b['cagr']:+.2%}  MDD={b['mdd']:+.2%}  Sharpe={b['sharpe']:.2f}", flush=True)


def metrics(variant, window="is"):
    p = CACHE / f"net_{variant}_{window}.parquet"
    if not p.exists():
        raise SystemExit(f"no net for {variant} {window} — run first")
    net = pd.read_parquet(p)["net"]
    net.index = pd.to_datetime(net.index)
    to = _turnover(variant)
    print(f"\n=== optimized {variant} [{window}] vs #9 REPLAY bar ===", flush=True)
    m = _metrics(net, f"{variant} {window}", to)
    bmk = json.loads((CACHE / "benchmark.json").read_text())["REPLAY"][window.upper()] \
        if (CACHE / "benchmark.json").exists() else None
    if bmk:
        _metrics_from(bmk, "REPLAY bar")
        dominates = (m["cagr"] >= bmk["cagr"] and m["mdd"] >= bmk["mdd"] and m["sharpe"] >= bmk["sharpe"])
        strict = (m["cagr"] > bmk["cagr"] or m["mdd"] > bmk["mdd"] or m["sharpe"] > bmk["sharpe"])
        verdict = "PARETO-DOMINATES ✅" if (dominates and strict) else "does NOT dominate ✗"
        print(f"  → {verdict}  (ΔCAGR={m['cagr']-bmk['cagr']:+.2%}  ΔMDD={m['mdd']-bmk['mdd']:+.2%}  "
              f"ΔSharpe={m['sharpe']-bmk['sharpe']:+.2f})", flush=True)


def _metrics_from(md, label):
    print(f"  {label:22} CAGR={md['cagr']:+.2%}  MDD={md['mdd']:+.2%}  Sharpe={md['sharpe']:.2f}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="native-compute smoke on 2014-H1 (0-crash gate)")
    ap.add_argument("--panel", action="store_true", help="compute + cache the IS factor panel")
    ap.add_argument("--is-ic", action="store_true", help="build IS rank-IC (direction + magnitude)")
    ap.add_argument("--benchmark", action="store_true", help="segment #9 replay into the IS/OOS bar")
    ap.add_argument("--signal", help="build schedule for a named variant")
    ap.add_argument("--run", help="engine-run a named variant")
    ap.add_argument("--metrics", help="metrics + Pareto verdict for a named variant")
    ap.add_argument("--diag", help="signal-quality autopsy (composite IC/decile/size) for a variant")
    ap.add_argument("--ksweep", help="gross paper-portfolio CAGR/Sharpe/MDD vs holdings-count K")
    ap.add_argument("--window", default="is", choices=("is", "oos", "full"))
    ap.add_argument("--i-am-spending-oos", action="store_true", help="unlock the one-shot OOS spend (GATED)")
    ap.add_argument("--all-variants", action="store_true", help="signal+run+metrics every VARIANT (IS)")
    # PR2 prototype — risk-aware optimizer (lifts the transfer coefficient)
    ap.add_argument("--build-returns", action="store_true", help="cache adjusted daily returns (covariance input)")
    ap.add_argument("--opt", help="build optimized (MVO) explicit-weight schedule for a variant")
    ap.add_argument("--run-opt", help="event-driven run of an optimized schedule")
    ap.add_argument("--opt-frontier", help="FAIL-FAST CONTROL: optimizer vs top-K, sweep λ (a variant)")
    ap.add_argument("--lam", type=float, default=20.0, help="risk-aversion λ in max αᵀw − λ·wᵀΣw")
    ap.add_argument("--ncand", type=int, default=100, help="alpha-screen candidate pool size before optimize")
    ap.add_argument("--maxw", type=float, default=0.10, help="max single-name weight (0.10 → ≥10 names)")
    a = ap.parse_args()
    if a.smoke:
        build_panel(smoke=True)
    if a.panel:
        build_panel()
    if a.is_ic:
        build_is_ic()
    if a.benchmark:
        benchmark()
    if a.signal:
        build_signal(a.signal)
    if a.run:
        run(a.run, a.window, a.i_am_spending_oos)
    if a.metrics:
        metrics(a.metrics, a.window)
    if a.diag:
        diag(a.diag)
    if a.ksweep:
        ksweep(a.ksweep)
    if a.build_returns:
        build_returns()
    if a.opt:
        build_opt_signal(a.opt, lam=a.lam, ncand=a.ncand, max_w=a.maxw)
    if a.run_opt:
        run_opt(a.run_opt, a.window, a.i_am_spending_oos, lam=a.lam)
    if a.opt_frontier:
        opt_frontier(a.opt_frontier, a.window, ncand=a.ncand, max_w=a.maxw)
    if a.all_variants:
        for v in VARIANTS:
            try:
                build_signal(v); run(v, "is"); metrics(v, "is")
            except Exception as exc:
                print(f"[all-variants] {v} FAILED: {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
