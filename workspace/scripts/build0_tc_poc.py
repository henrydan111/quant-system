# SCRIPT_STATUS: ACTIVE — BUILD-0 PoC: transfer-coefficient (TC) measurement + light-construction test
"""BUILD-0 first empirical task of STRATEGY_DEVELOPMENT_METHODOLOGY_v1.0.

Cheaply, IS-only, test the methodology's central prior BEFORE building the full construction stack:
  (Step 1) MEASURE the transfer coefficient TC = corr(mu/sigma, dw*sigma) of the s3_core book under
           different weight constructions (Grinold-Kahn / Clarke-de-Silva-Thorley Fundamental Law).
  (Step 2) RUN each construction vs equal-weight top-K on net-of-cost IS PnL, on the SAME alpha /
           universe / costs / rebalance envelope (weights are the ONLY thing that differs).
  (Step 3) VERDICT: does the methodology-faithful LIGHT construction beat equal-weight top-K on net
           RISK-ADJUSTED return (Sharpe primary, MDD guard)?  TC is DESCRIPTIVE, never the gate.

Design (controlled experiment): every construction holds the SAME name set (top-30 by the shared
neutralized composite `comp`); they differ ONLY in the weight vector -> isolates the weighting effect.

  eqw     : 1/K                         -- methodology's low-TC baseline (rank -> top-K -> equal weight)
  alpha   : propto sigma * z            -- §S3-LITERAL target_w propto calibrated alpha (=IC*sigma*z);
                                           the METHODOLOGY-FAITHFUL light construction  [PRIMARY]
  sigcomp : propto (comp - min + eps)   -- score-proportional (harness wmode="signal"); propto z, NOT alpha
  invvol  : propto z / sigma            -- risk-scaled / MV-diagonal FORM (its holdings-TC=1 is a TAUTOLOGY)
  sqrtmv  : propto sqrt(circ_mv)        -- #9's OWN weighting (a SIZE tilt, not signal); reuse cross-check

GOVERNANCE / HONESTY (folded from the 4-lens design red-team, 2026-07-11 — see FINDINGS):
  * HEADLINE TC = the FULL-eligible CALIBRATED TC (the Fundamental-Law object entering IR=TC*IC*sqrt(BR)).
    Holdings-only TC is a within-book DIAGNOSTIC (dw sums to ~0.99, not 0) and is TAUTOLOGICAL for any
    signal-proportional weight (invvol propto z/sigma => dw*sigma propto z => corr=1 by construction) —
    it is NEVER used to select a construction and must not be recorded as an "edge".
  * TC is DESCRIPTIVE. Net-of-cost PnL is the SOLE selector. The verdict gate reads Sharpe (primary) +
    MDD (guard), never TC.
  * sigma = TOTAL trailing-60d vol (a PROXY; handoff permits 先粗后精). §S2b's Grinold/MV forms are
    defined on RESIDUAL/idio vol, so alpha/invvol carry a residual beta/size tilt caveat (BUILD-0b fix).
  * The TC benchmark (equal-weight-over-eligible) differs from the PnL benchmark (000300.SH) and the
    reported Sharpe is ABSOLUTE — so no TC number maps to the backtest IR; they are NOT cross-cited.
  * SCOPE: n=1 non-microcap value+quality+low-vol book, ONE IS window (2014-2020, value-favorable). This
    is the well-conditioned case §S3 assigns to the OPTIMIZER, not the micro-tail lane where light
    construction is prescribed — a verdict here does NOT settle the micro-tail lane. Absolute IC/CAGR/
    Sharpe are IS-fitted (sign-orientation on the same window) => optimistic, design-stage, not deployable.

sigma_i = trailing 60d daily-return stdev up to pday (=T-1, PIT-safe; identical convention to the trusted
build_opt_signal covariance input). IS-only (2014-2020); this script has NO OOS path by design.

Reuses guorn_optimize_09 (NO edits): its shared composite generator `_composite_series`, the cached factor
panel / IS-IC / returns, the eligibility frames, and the exact event-driven run envelope. Metrics via
research_utils.goal_metrics. MLflow opt-in via --mlflow (CLAUDE.md 7.6; server best-effort).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "workspace" / "scripts"),
          str(ROOT / "workspace" / "research" / "long_only_50cagr")):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.stdout.reconfigure(encoding="utf-8")

import guorn_optimize_09 as g09          # noqa: E402  (sets sys.path, imports v7/v9/ru; NO edits made here)

log = logging.getLogger("build0")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

VARIANT = "s3_core_sind_k30"             # the #9 deployable-core book (value+quality+low-vol, top-30, non-microcap)
K = g09.VARIANTS[VARIANT].get("topk", 10)
CONSTRUCTIONS = ("eqw", "alpha", "sigcomp", "invvol", "sqrtmv")
SIGNAL_PROP = ("alpha", "sigcomp", "invvol")   # the signal-proportional LIGHT constructions (sqrtmv is a size ref)
PRIMARY, BASELINE = "alpha", "eqw"       # PRIMARY = the §S3-faithful calibrated-alpha light construction
LABELS = {
    "eqw": "equal-weight (low-TC baseline)",
    "alpha": "propto sigma*z  (§S3 calibrated-alpha) [PRIMARY]",
    "sigcomp": "propto comp    (score-proportional; harness wmode=signal)",
    "invvol": "propto z/sigma  (risk-scaled; holdings-TC=1 is a tautology)",
    "sqrtmv": "propto sqrt(mv) (#9 size weighting; reuse cross-check)",
}
SHARPE_MARGIN = 0.10                      # a Sharpe lift below this is within IS noise (bootstrap-checked)
MDD_TOL = 0.02                           # a construction may not worsen MDD by > 2pp to count as a "win"
SIGMA_WIN, SIGMA_MINOBS = 60, 40
CACHE = g09.CACHE
IS_START, IS_END = g09.IS_START, g09.IS_END
TAG = "build0"                           # namespaces every artifact this script writes


# ================================================================ shared preamble (mirror ksweep) ===
def _setup():
    """Assemble the exact inputs `_composite_series` needs (mirrors g09.ksweep / g09.build_signal)."""
    cfg = g09.VARIANTS[VARIANT]
    cols = g09._universe_cols()
    close = pd.read_parquet(g09.V9C / "e_close_raw.parquet")
    circ = pd.read_parquet(g09.V9C / "e_circ_mv.parquet").reindex(columns=cols)
    ret = pd.read_parquet(CACHE / "returns.parquet").reindex(columns=cols)
    fwd5 = g09._load_factor("fwd_5d")
    grid = close.index
    bounds = g09.v7._bounds()
    rebal = [d for d in g09.v9.rebalance_grid(IS_END)
             if pd.Timestamp(IS_START) <= d <= pd.Timestamp(IS_END)]
    pmap = g09.v7._pdays(rebal, grid)
    frames = {f: g09._load_factor(f) for f in cfg["pool"]}
    efr = g09._elig_frames(cfg["elig"], cols)
    ind_asof = (g09._sw_l1([pmap[d] for d in rebal if d in pmap], cols)
                if cfg["neut"] == "size_ind" else None)
    return cfg, cols, close, circ, ret, fwd5, frames, efr, ind_asof, bounds, rebal, pmap


def _sigma_asof(ret: pd.DataFrame, pday, cols) -> pd.Series:
    """Trailing-60d TOTAL daily-return stdev up to and including pday (PIT: pday = T-1). NaN where <40 obs.
    A PROXY for idio vol (residual/beta-neutralized vol is the BUILD-0b refinement); see module docstring."""
    win = ret.loc[:pday].tail(SIGMA_WIN)
    n = win.notna().sum()
    sig = win.std(ddof=0)
    return sig.where(n >= SIGMA_MINOBS).reindex(cols)


def _weight_vectors(comp_top: pd.Series, sigma_top: pd.Series, circ_top: pd.Series) -> dict:
    """The 5 long-only weight vectors over the SAME top-K names (each normalized to sum 1)."""
    z = comp_top.astype(float)
    sg = sigma_top.reindex(z.index)
    sg = sg.fillna(sg.median() if sg.notna().any() else 1.0).clip(lower=1e-9)   # median-fill missing sigma
    out = {}
    out["eqw"] = pd.Series(1.0 / len(z), index=z.index)
    a = (sg * z).clip(lower=0.0)                                # Grinold: propto sigma*z (IC scalar washes out)
    out["alpha"] = a / a.sum() if a.sum() > 0 else out["eqw"].copy()
    sc = z - z.min() + 1e-6                                     # harness wmode="signal": propto (comp-min+eps)
    out["sigcomp"] = sc / sc.sum()
    iv = (z / sg).clip(lower=0.0)                               # MV-diagonal form: propto z/sigma
    out["invvol"] = iv / iv.sum() if iv.sum() > 0 else out["eqw"].copy()
    sq = np.sqrt(circ_top.reindex(z.index).clip(lower=0.0).fillna(0.0))          # #9: propto sqrt(circ_mv)
    out["sqrtmv"] = sq / sq.sum() if sq.sum() > 0 else out["eqw"].copy()
    return out


def _tc_pair(mu_over_sig: pd.Series, dw_sig: pd.Series) -> float:
    """Cross-sectional Pearson corr(mu/sigma, dw*sigma) over aligned finite names."""
    df = pd.concat([mu_over_sig, dw_sig], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if len(df) < 20 or df.iloc[:, 0].std() == 0 or df.iloc[:, 1].std() == 0:
        return np.nan
    return float(df.iloc[:, 0].corr(df.iloc[:, 1]))


def _corr(a: pd.Series, b: pd.Series) -> float:
    df = pd.concat([a, b], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if len(df) < 5 or df.iloc[:, 0].std() == 0 or df.iloc[:, 1].std() == 0:
        return np.nan
    return float(df.iloc[:, 0].corr(df.iloc[:, 1]))


# ================================================================ Step 1: TC + schedules + confounds =
def prepare():
    """One pass over IS rebalance dates: build the 5 explicit-weight schedules AND accumulate TC + the
    per-construction confound diagnostics (effective-N, max weight, weight tilt vs size/vol).
    Writes sched_build0_<name>.json (x5) + build0_tc.json."""
    cfg, cols, close, circ, ret, fwd5, frames, efr, ind_asof, bounds, rebal, pmap = _setup()
    scheds = {c: {} for c in CONSTRUCTIONS}
    tc_acc = {c: {"full_calib": [], "full_raw": [], "hold_calib": [], "hold_raw": []}
              for c in CONSTRUCTIONS}
    dg = {c: {"eff_n": [], "max_w": [], "corr_w_logmv": [], "corr_w_sigma": []} for c in CONSTRUCTIONS}
    ic_comp, n_elig_hist = [], []

    for d, pday, comp, broad in g09._composite_series(cfg, cols, close, circ, frames, efr,
                                                      ind_asof, bounds, rebal, pmap):
        elig = comp.notna()
        n_elig = int(elig.sum())
        dkey = str(d.date())
        if n_elig < 30:
            for c in CONSTRUCTIONS:
                scheds[c][dkey] = []
            continue
        n_elig_hist.append(n_elig)
        sigma = _sigma_asof(ret, pday, cols)
        z_all = comp.where(elig)
        logmv = np.log(circ.loc[pday].where(circ.loc[pday] > 0))

        if d in fwd5.index:                                    # composite IS rank-IC (diagnostic; washes out)
            f5 = fwd5.loc[d]
            m = z_all.notna() & f5.notna()
            if m.sum() >= 100:
                ic_comp.append(z_all[m].rank().corr(f5[m].rank()))

        top = z_all.dropna().sort_values(ascending=False).head(K)
        top_idx = top.index
        wv = _weight_vectors(top, sigma.reindex(top_idx), circ.loc[pday].reindex(top_idx))

        bench = pd.Series(0.0, index=cols)
        bench[elig] = 1.0 / n_elig
        z_elig, sig_elig = z_all[elig], sigma[elig]
        z_h, sig_h, mv_h = z_all.reindex(top_idx), sigma.reindex(top_idx), logmv.reindex(top_idx)

        for c in CONSTRUCTIONS:
            w = wv[c]
            w_full = pd.Series(0.0, index=cols)
            w_full.loc[top_idx] = w.values
            dw_sig_e = (w_full - bench)[elig] * sig_elig
            tc_acc[c]["full_calib"].append(_tc_pair(z_elig, dw_sig_e))            # HEADLINE (mu/sigma propto z)
            tc_acc[c]["full_raw"].append(_tc_pair(z_elig / sig_elig, dw_sig_e))
            dw_h = w.reindex(top_idx) - 1.0 / n_elig
            tc_acc[c]["hold_calib"].append(_tc_pair(z_h, dw_h * sig_h))           # DIAGNOSTIC (tautological)
            tc_acc[c]["hold_raw"].append(_tc_pair(z_h / sig_h, dw_h * sig_h))
            # confounds: effective breadth + incidental size/vol tilt of the WEIGHTS
            dg[c]["eff_n"].append(1.0 / float((w ** 2).sum()))
            dg[c]["max_w"].append(float(w.max()))
            dg[c]["corr_w_logmv"].append(_corr(w.reindex(top_idx), mv_h))
            dg[c]["corr_w_sigma"].append(_corr(w.reindex(top_idx), sig_h))

            scheds[c][dkey] = [[str(code).upper().replace("_", "."), float(x)]
                               for code, x in w.items() if pd.notna(x) and x > 0]

    for c in CONSTRUCTIONS:
        (CACHE / f"sched_{TAG}_{c}.json").write_text(json.dumps(scheds[c], ensure_ascii=False),
                                                     encoding="utf-8")
    wt_turn = {c: _weight_turnover(scheds[c]) for c in CONSTRUCTIONS}
    tc_summary = {c: {k: float(np.nanmean(v)) if v else float("nan") for k, v in tc_acc[c].items()}
                  for c in CONSTRUCTIONS}
    diag = {c: {"eff_n": float(np.nanmean(dg[c]["eff_n"])), "max_w": float(np.nanmean(dg[c]["max_w"])),
                "corr_w_logmv": float(np.nanmean(dg[c]["corr_w_logmv"])),
                "corr_w_sigma": float(np.nanmean(dg[c]["corr_w_sigma"])),
                "wt_turnover": wt_turn[c]} for c in CONSTRUCTIONS}
    out = {"variant": VARIANT, "K": K, "window": "IS", "start": IS_START, "end": IS_END,
           "n_rebal": len(rebal), "n_elig_median": float(np.median(n_elig_hist)) if n_elig_hist else None,
           "composite_is_rank_ic_5d": float(np.nanmean(ic_comp)) if ic_comp else None,
           "tc": tc_summary, "diag": diag}
    (CACHE / f"{TAG}_tc.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    _print_tc(out)
    return out


def _weight_turnover(sched: dict) -> float:
    """Mean per-rebalance weight-aware turnover 0.5*sum|w_t - w_{t-1}| (name-set turnover is identical
    across all same-name constructions; this captures the re-tilt cost that _turnover_sched misses)."""
    keys = sorted(sched)
    prev, tos = None, []
    for k in keys:
        rows = sched[k]
        if not rows:
            prev = None
            continue
        w = pd.Series({r[0]: float(r[1]) for r in rows})
        w = w / w.sum()
        if prev is not None:
            idx = prev.index.union(w.index)
            tos.append(0.5 * (prev.reindex(idx).fillna(0.0) - w.reindex(idx).fillna(0.0)).abs().sum())
        prev = w
    return float(np.mean(tos)) if tos else np.nan


def _print_tc(out: dict):
    d = out["diag"]
    print("\n" + "=" * 100, flush=True)
    print(f"STEP 1 — TRANSFER COEFFICIENT  (variant={out['variant']} K={out['K']} {out['window']} "
          f"{out['start']}..{out['end']}, {out['n_rebal']} rebalances)", flush=True)
    print(f"  composite IS rank-IC (5d) = {out['composite_is_rank_ic_5d']:+.4f}  [IS-fitted, optimistic]   "
          f"median eligible/date = {out['n_elig_median']:.0f}", flush=True)
    print("  HEADLINE TC = TC_full_calib (Fundamental-Law object). TC_hold = within-book diagnostic "
          "(TAUTOLOGICAL for propto-signal; invvol=1 is algebra).", flush=True)
    print("=" * 100, flush=True)
    print(f"  {'construction':10} {'TC_full':>8} {'TC_full_raw':>11} | {'TC_hold*':>8} {'TC_hold_raw':>11} | "
          f"{'eff_N':>5} {'max_w':>6} {'wt_turn':>7} {'w~size':>7} {'w~vol':>6}", flush=True)
    for c in CONSTRUCTIONS:
        t = out["tc"][c]
        print(f"  {c:10} {t['full_calib']:>8.3f} {t['full_raw']:>11.3f} | {t['hold_calib']:>8.3f} "
              f"{t['hold_raw']:>11.3f} | {d[c]['eff_n']:>5.1f} {d[c]['max_w']:>6.3f} "
              f"{d[c]['wt_turnover']:>7.3f} {d[c]['corr_w_logmv']:>+7.2f} {d[c]['corr_w_sigma']:>+6.2f}",
              flush=True)
    dtc = out['tc'][PRIMARY]['full_calib'] - out['tc'][BASELINE]['full_calib']
    print(f"\n  HEADLINE: ΔTC_full({PRIMARY} vs {BASELINE}) = {dtc:+.4f}  "
          f"(<0 => the faithful light construction does NOT raise the book's Fundamental-Law TC; "
          f"selection dominates for a {K}-of-{out['n_elig_median']:.0f} book)", flush=True)


# ================================================================ Step 2: engine run per construction =
def _run_cfg():
    from src.backtest_engine.event_driven import CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    cost = CostConfig(buy_commission=0.002, sell_commission=0.002, stamp_tax=0.0,
                      min_commission=0.0, transfer_fee=0.0)
    return cost, FixedSlippage(0.0)


def run_book(name: str):
    """Event-driven IS run of one construction's explicit-weight schedule — identical envelope to #9
    (0.2%/side, slippage 0, vol_limit 0.10, hold_on_limit_up, Model-I 5d grid, benchmark 000300.SH)."""
    from src.backtest_engine.event_driven import EventDrivenBacktester
    sched = json.loads((CACHE / f"sched_{TAG}_{name}.json").read_text(encoding="utf-8"))
    cost, slip = _run_cfg()
    strat = g09.v7.ModelIDivLowVolStrategy(sched, max_holds=K, reserve=K, weights_mode="explicit")
    bt = EventDrivenBacktester(data_dir=str(ROOT / "data"))
    res = bt.run(strategy=strat, start_time=IS_START, end_time=IS_END, benchmark="000300.SH",
                 account=1_000_000.0, exchange_config=cost, slippage=slip,
                 volume_limit=0.10, hold_on_limit_up=True,
                 preload_fields=["$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close",
                                 "$adj_factor", "$up_limit", "$down_limit"])
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    net = rep["return"].astype(float)
    net.to_frame("net").to_parquet(CACHE / f"net_{TAG}_{name}_is.parquet")
    print(f"[run {name}] saved net ({len(net)} days {IS_START}..{IS_END})", flush=True)


def run_all():
    for name in CONSTRUCTIONS:
        run_book(name)


# ================================================================ Step 3: assemble + verdict =========
def _metrics(net: pd.Series, wt_turnover=np.nan) -> dict:
    m = g09.ru.goal_metrics(net)
    m["calmar"] = m["cagr"] / abs(m["mdd"]) if m["mdd"] else np.nan
    m["wt_turnover"] = wt_turnover
    return m


def _sharpe(x: np.ndarray) -> float:
    s = x.std(ddof=0)
    return float(x.mean() / s * np.sqrt(252)) if s > 0 else np.nan


def _boot_sharpe_diff(net_c: pd.Series, net_b: pd.Series, nboot=2000, block=20) -> dict:
    """Paired stationary-block bootstrap of Sharpe(construction) - Sharpe(baseline). The two books share
    names => their daily returns are ~collinear, so pairing (same resampled blocks for both) isolates the
    construction effect. Reports the point delta and one-sided P(delta <= 0)."""
    df = pd.concat([net_c.rename("c"), net_b.rename("b")], axis=1).dropna()
    a, b = df["c"].values, df["b"].values
    n = len(a)
    point = _sharpe(a) - _sharpe(b)
    rng = np.random.default_rng(0)
    nblk = int(np.ceil(n / block))
    diffs = np.empty(nboot)
    for i in range(nboot):
        starts = rng.integers(0, n, size=nblk)
        idx = np.concatenate([np.arange(s, s + block) % n for s in starts])[:n]
        diffs[i] = _sharpe(a[idx]) - _sharpe(b[idx])
    return {"delta_sharpe": point, "p_delta_le_0": float(np.mean(diffs <= 0.0)),
            "ci95": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))]}


def assemble(do_mlflow=False):
    tc = json.loads((CACHE / f"{TAG}_tc.json").read_text())
    bar = json.loads((CACHE / "benchmark.json").read_text())["REPLAY"]["IS"] \
        if (CACHE / "benchmark.json").exists() else None
    nets, rows = {}, {}
    for name in CONSTRUCTIONS:
        p = CACHE / f"net_{TAG}_{name}_is.parquet"
        if not p.exists():
            print(f"  [assemble] MISSING net for {name} — run first", flush=True)
            continue
        net = pd.read_parquet(p)["net"].astype(float)
        net.index = pd.to_datetime(net.index)
        nets[name] = net
        m = _metrics(net, tc["diag"][name]["wt_turnover"])
        m["tc_full_calib"] = tc["tc"][name]["full_calib"]
        m["tc_hold_calib"] = tc["tc"][name]["hold_calib"]
        m["eff_n"] = tc["diag"][name]["eff_n"]
        rows[name] = m

    # reuse-fidelity cross-check: sqrtmv should reproduce the cached g09 baseline bit-for-bit
    xcheck, cp = None, CACHE / f"net_{VARIANT}_is.parquet"
    if "sqrtmv" in nets and cp.exists():
        b = pd.read_parquet(cp)["net"].astype(float).values
        if len(nets["sqrtmv"]) == len(b):
            xcheck = float(np.nanmax(np.abs(nets["sqrtmv"].values - b)))

    # paired Sharpe-difference bootstrap vs eqw (is the ~0.10 Sharpe span noise?)
    boot = {}
    if BASELINE in nets:
        for name in CONSTRUCTIONS:
            if name != BASELINE and name in nets:
                boot[name] = _boot_sharpe_diff(nets[name], nets[BASELINE])

    _print_table(rows, tc, bar, xcheck, boot)
    verdict = _verdict(rows, tc, boot)
    (CACHE / f"{TAG}_results.json").write_text(
        json.dumps({"metrics": rows, "tc": tc["tc"], "diag": tc["diag"], "bar_is": bar,
                    "reuse_xcheck_max_abs": xcheck, "boot_vs_eqw": boot, "verdict": verdict},
                   indent=1), encoding="utf-8")
    if do_mlflow:
        _mlflow(rows, tc)
    return rows, verdict


def _print_table(rows, tc, bar, xcheck, boot):
    print("\n" + "=" * 116, flush=True)
    print(f"STEP 2 — NET-OF-COST IS ({IS_START}..{IS_END})  |  s3_core deployable core, top-{K}, "
          f"SAME alpha/universe/costs; construction differs only in the weight vector", flush=True)
    print("  [absolute Sharpe; NOT the same benchmark as the TC (EW-eligible) — do not cross-cite TC->IR]",
          flush=True)
    print("=" * 116, flush=True)
    hdr = (f"  {'construction':10} {'CAGR':>8} {'Sharpe':>7} {'MDD':>8} {'Calmar':>7} {'vol':>6} "
           f"{'eff_N':>5} {'TC_full':>8} {'TC_hold*':>8}  ΔSharpe_vs_eqw (p)")
    print(hdr, flush=True)
    print("  " + "-" * (len(hdr) - 2), flush=True)
    for name in CONSTRUCTIONS:
        if name not in rows:
            continue
        m = rows[name]
        bt = ""
        if name in boot:
            bt = f"  {boot[name]['delta_sharpe']:+.2f} (p={boot[name]['p_delta_le_0']:.2f})"
        elif name == BASELINE:
            bt = "  — baseline"
        print(f"  {name:10} {m['cagr']:>+7.2%} {m['sharpe']:>7.2f} {m['mdd']:>+7.2%} {m['calmar']:>7.2f} "
              f"{m['ann_vol']:>5.1%} {m['eff_n']:>5.1f} {m['tc_full_calib']:>8.3f} "
              f"{m['tc_hold_calib']:>8.3f}{bt}", flush=True)
    if bar:
        print(f"  {'#9 REPLAY':10} {bar['cagr']:>+7.2%} {bar['sharpe']:>7.2f} {bar['mdd']:>+7.2%} "
              f"{bar['calmar']:>7.2f} {bar['ann_vol']:>5.1%} {'—':>5} {'—':>8} {'—':>8}  "
              f"<- SELECTION differs (real #9 dividend names)", flush=True)
    print("\n  construction legend:", flush=True)
    for c in CONSTRUCTIONS:
        print(f"    {c:8} {LABELS[c]}", flush=True)
    if xcheck is not None:
        ok = "OK — bit-identical" if xcheck < 1e-9 else ("close" if xcheck < 1e-3 else "MISMATCH")
        print(f"\n  reuse-fidelity cross-check: my sqrtmv vs cached g09 baseline  max|Δ daily ret| = "
              f"{xcheck:.2e}  [{ok}]", flush=True)


def _verdict(rows: dict, tc: dict, boot: dict) -> dict:
    """Gate = net Sharpe (primary, meaningful margin + bootstrap) + MDD guard. TC is NOT in the gate."""
    if BASELINE not in rows:
        return {"status": "incomplete"}
    b = rows[BASELINE]

    def eval_one(name):
        m = rows[name]
        d_sharpe = m["sharpe"] - b["sharpe"]
        d_mdd = m["mdd"] - b["mdd"]                       # mdd<0; higher (less negative) = better
        d_cagr = m["cagr"] - b["cagr"]
        p = boot.get(name, {}).get("p_delta_le_0", np.nan)
        beats = bool(d_sharpe >= SHARPE_MARGIN and d_mdd >= -MDD_TOL and (np.isnan(p) or p < 0.10))
        return {"d_sharpe": d_sharpe, "d_mdd": d_mdd, "d_cagr": d_cagr, "boot_p_delta_le_0": p,
                "d_tc_full": tc["tc"][name]["full_calib"] - tc["tc"][BASELINE]["full_calib"],
                "beats_eqw": beats}

    per = {name: eval_one(name) for name in SIGNAL_PROP if name in rows}
    faithful = per.get(PRIMARY, {})
    any_light_beats = any(v["beats_eqw"] for v in per.values())
    best_light = max(per, key=lambda n: rows[n]["sharpe"]) if per else None
    premise_holds = bool(any_light_beats)

    v = {"gate": "net Sharpe primary (margin ≥ %.2f, bootstrap p<0.10) + MDD guard (≤ +%.0fpp); "
                 "TC descriptive only" % (SHARPE_MARGIN, MDD_TOL * 100),
         "primary_faithful": PRIMARY, "baseline": BASELINE, "per_construction": per,
         "faithful_beats_eqw": faithful.get("beats_eqw"),
         "best_light": best_light, "any_light_beats_eqw": any_light_beats,
         "premise_holds": premise_holds,
         "call": ("GREENLIGHT BUILD-0 construction stack" if premise_holds else
                  "ADJUST — weight construction is a weak lever here; the deployable lever is "
                  "signal-SELECTION + universe, not weighting")}
    print("\n" + "=" * 100, flush=True)
    print("STEP 3 — VERDICT   (" + v["gate"] + ")", flush=True)
    print("=" * 100, flush=True)
    for name, e in per.items():
        tag = " [faithful §S3]" if name == PRIMARY else ""
        print(f"  {name:9}{tag:16} ΔSharpe={e['d_sharpe']:+.2f} (p={e['boot_p_delta_le_0']:.2f})  "
              f"ΔMDD={e['d_mdd']:+.2%}  ΔCAGR={e['d_cagr']:+.2%}  ΔTC_full={e['d_tc_full']:+.3f}  "
              f"beats_eqw={e['beats_eqw']}", flush=True)
    print(f"\n  faithful({PRIMARY}) beats eqw = {v['faithful_beats_eqw']}   "
          f"any signal-prop light construction beats eqw = {any_light_beats}   "
          f"=> premise_holds = {premise_holds}", flush=True)
    print(f"  → {v['call']}", flush=True)
    return v


def _mlflow(rows: dict, tc: dict):
    try:
        from src.alpha_research.mlflow_tracker import ExperimentTracker
        tr = ExperimentTracker(config_path=str(ROOT / "config.yaml"))
        for name, m in rows.items():
            tr.start_run(f"build0_tc_{VARIANT}_{name}")
            tr.log_params({"experiment": "BUILD0_TC_POC", "variant": VARIANT, "construction": name,
                           "label": LABELS[name], "K": K, "window": "IS", "start": IS_START,
                           "end": IS_END, "universe": "guorn(主板+创业板)", "cost_side": 0.002,
                           "rebalance": "5d Model-I"})
            tr.log_metrics({k: float(v) for k, v in m.items()
                            if isinstance(v, (int, float)) and np.isfinite(v)})
            tr.end_run()
        log.info("MLflow: logged %d constructions", len(rows))
    except Exception as exc:                                       # noqa: BLE001
        log.warning("MLflow logging skipped (%s: %s)", type(exc).__name__, exc)


def main():
    ap = argparse.ArgumentParser(description="BUILD-0 TC PoC (IS-only; no OOS path exists here)")
    ap.add_argument("--prepare", action="store_true", help="Step 1: TC + confounds + explicit schedules")
    ap.add_argument("--run", help="engine-run one construction (%s)" % "|".join(CONSTRUCTIONS))
    ap.add_argument("--run-all", action="store_true", help="engine-run all constructions (sequential)")
    ap.add_argument("--assemble", action="store_true", help="Step 3: comparison table + verdict")
    ap.add_argument("--mlflow", action="store_true", help="also log to MLflow (server best-effort)")
    ap.add_argument("--all", action="store_true", help="prepare -> run-all -> assemble")
    a = ap.parse_args()
    if a.all:
        prepare(); run_all(); assemble(a.mlflow); return
    if a.prepare:
        prepare()
    if a.run:
        run_book(a.run)
    if a.run_all:
        run_all()
    if a.assemble:
        assemble(a.mlflow)
    if not any((a.prepare, a.run, a.run_all, a.assemble, a.all)):
        ap.print_help()


if __name__ == "__main__":
    main()
