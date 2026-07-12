# SCRIPT_STATUS: ACTIVE — BUILD-0 PoC: transfer-coefficient (TC) measurement + light-construction screen
"""BUILD-0 first empirical task of STRATEGY_DEVELOPMENT_METHODOLOGY_v1.0 — v2 (post GPT §10 REWORK).

An IS-only, EXPLORATORY SCREEN (not a deployable backtest) of whether re-weighting a fixed top-30 name set
changes net risk-adjusted return, to inform (not decide) whether to build the §S3 construction stack.

WHAT THIS IS AND IS NOT (folded from the GPT §10 REWORK, 2026-07-11 — see FINDINGS §7):
  * It VARIES ONLY the weight vector over a FIXED top-30 selection. It does NOT estimate selection or
    universe effects (the universe never changes) — so it cannot rank selection/universe vs weighting.
  * It is a SCREEN, not an equivalence test: "no proxy passed" does NOT prove weighting is a weak lever.
  * The 3 signal-proportional variants are UNCONSTRAINED weight PROXIES, NOT the §S3 light constructor
    (§S3 mandates residual/idio σ, portfolio-level size/industry neutrality, single-name + industry caps,
    ADV + turnover/cost penalties). `--max-weight` and `--sigma residual` add the FIRST two of those.
  * Orientation is A-PRIORI (value/quality long, low-vol short-high-vol) — the IS-IC-fit signs COINCIDE
    with the a-priori signs exactly (verified), so the composite carries NO cross-time fitted parameter and
    NO orientation lookahead. `--orientation is_fit` (g09 static IC signs) reproduces `a_priori` bit-for-bit.
  * Window isolation: every input is truncated to <= IS_END on load; this run does not compute any value
    from the sealed 2021-2026 window. It still OPENS caches that physically contain OOS rows, so it does
    NOT certify the window pristine — treat 2021-2026 as potentially-observed-for-this-design.

Controlled experiment: SAME top-30 names of the s3_core book (value+quality+low-vol, size+industry-
neutralized composite `comp`, non-microcap), 5 weight vectors, identical event-driven envelope (0.2%/side,
slippage 0, volume_limit 0.10, hold_on_limit_up, Model-I 5d, benchmark 000300.SH, ¥1M, total-return).
  eqw     : 1/K                        (low-TC baseline; no σ, no orientation dependence)
  alpha   : propto sigma*z             (Grinold-form; UNCONSTRAINED total-σ proxy — NOT the §S3 constructor)
  sigcomp : propto (comp - min + eps)  (score-proportional; the harness wmode="signal"; propto z)
  invvol  : propto z/sigma             (MV-diagonal FORM; its holdings-TC≈1 is a structural near-identity)
  sqrtmv  : propto sqrt(circ_mv)       (#9's own weighting — a SIZE tilt; also a reuse cross-check)

Config (namespaced by --tag): --orientation {a_priori|is_fit|walk_forward}  --sigma {total|residual}
  --max-weight <cap in (0,1]>  --familywise (fail-closed screen).  IS-only 2014-2020; NO OOS path exists.

Reuses guorn_optimize_09 (NO edits) for _neutralize / eligibility / the cached panel / the strategy+engine;
metrics via research_utils.goal_metrics. Emits an evidence manifest (git SHA + input/output SHA-256 + config
+ provider/calendar ids) so the verdict is reproducible; marks NON_EVIDENTIARY (IS design probe).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
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

VARIANT = "s3_core_sind_k30"
K = g09.VARIANTS[VARIANT].get("topk", 10)
POOL = g09.VARIANTS[VARIANT]["pool"]
CONSTRUCTIONS = ("eqw", "alpha", "sigcomp", "invvol", "sqrtmv")
SIGNAL_PROP = ("alpha", "sigcomp", "invvol")
BASELINE = "eqw"
# A-PRIORI economic directions (value/quality long; low-volatility anomaly = short high vol). Verified to
# COINCIDE with the IS-IC-fit signs for every POOL_CORE factor -> the composite has no fitted orientation.
APRIORI_SIGNS = {f: (-1.0 if f == "risk_vol_20d" else 1.0) for f in POOL}
LABELS = {
    "eqw": "equal-weight (low-TC baseline)",
    "alpha": "propto sigma*z  (Grinold-form; UNCONSTRAINED total/residual-σ proxy — NOT the §S3 constructor)",
    "sigcomp": "propto comp    (score-proportional; harness wmode=signal)",
    "invvol": "propto z/sigma  (MV-diagonal form; holdings-TC≈1 is a structural near-identity, not an edge)",
    "sqrtmv": "propto sqrt(mv) (#9 size weighting; reuse cross-check)",
}
SHARPE_MARGIN = 0.10                      # a Sharpe lift below this is not deployment-relevant
MDD_TOL = 0.02
SCREEN_ALPHA = 0.10                       # per-construction bootstrap tail-mass threshold (UNADJUSTED; not FWER)
SIGMA_WIN, SIGMA_MINOBS = 60, 40
WF_MIN_OBS = 12                           # walk-forward: min past ICs before trusting a fitted sign
CACHE = g09.CACHE
IS_START, IS_END = g09.IS_START, g09.IS_END


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _realization_date(grid, d, h=5):
    """The trading day on which a factor-date-d, h-day-forward label REALIZES (open_days[pos(d)+h]).
    Used to enforce the label-realization boundary: an IC/orientation may only use dates whose label is
    realized <= IS_END, else it reads returns from the sealed OOS window (CLAUDE.md §3.5 IsEndLeakage)."""
    pos = grid.searchsorted(pd.Timestamp(d))
    return grid[pos + h] if pos + h < len(grid) else None


# ================================================================ shared preamble (window-isolated) ==
def _setup():
    """Assemble inputs and TRUNCATE every date-indexed frame to <= IS_END (Blocker-1: no OOS row ever
    enters a computation). returns.parquet + the factor panels are already <= IS_END by construction."""
    cfg = g09.VARIANTS[VARIANT]
    cols = g09._universe_cols()
    end = pd.Timestamp(IS_END)
    close = pd.read_parquet(g09.V9C / "e_close_raw.parquet").loc[:end]
    circ = pd.read_parquet(g09.V9C / "e_circ_mv.parquet").reindex(columns=cols).loc[:end]
    ret = pd.read_parquet(CACHE / "returns.parquet").reindex(columns=cols).loc[:end]
    fwd5 = g09._load_factor("fwd_5d").loc[:end]
    for nm, fr in (("close", close), ("circ", circ), ("ret", ret), ("fwd5", fwd5)):
        assert fr.index.max() <= end, f"{nm} has rows > IS_END — window isolation broken"
    grid = close.index
    bounds = g09.v7._bounds()
    rebal = [d for d in g09.v9.rebalance_grid(IS_END)
             if pd.Timestamp(IS_START) <= d <= end]
    pmap = g09.v7._pdays(rebal, grid)
    frames = {f: g09._load_factor(f).loc[:end] for f in cfg["pool"]}
    efr = g09._elig_frames(cfg["elig"], cols)
    ind_asof = (g09._sw_l1([pmap[d] for d in rebal if d in pmap], cols)
                if cfg["neut"] == "size_ind" else None)
    mkt = ret.mean(axis=1)                                    # equal-weight market proxy (<= IS_END)
    return cfg, cols, close, circ, ret, fwd5, mkt, frames, efr, ind_asof, bounds, rebal, pmap


# ================================================================ orientation (a_priori / wf / is_fit) =
def _walkforward_signs(cfg, cols, frames, fwd5, grid, rebal, pmap):
    """Per-rebalance-date sign for each factor from an EXPANDING IC over past rebalance dates whose 5d
    label is REALIZED by pday(d) (real(d')=grid[pos(d')+5] <= pday(d)); a-priori fallback below MIN_OBS."""
    ic_by_date = {f: {} for f in cfg["pool"]}
    real, end = {}, pd.Timestamp(IS_END)
    for d in rebal:
        rz = _realization_date(grid, d, 5)
        real[d] = rz if rz is not None else pd.Timestamp("2100-01-01")
        if d not in fwd5.index or real[d] > end:             # B1: never even COMPUTE an OOS-realized IC
            continue
        f5 = fwd5.loc[d]
        for f in cfg["pool"]:
            fr = frames[f]
            fv = (fr.loc[d] if d in fr.index else g09.v7._row(fr, d)).reindex(cols)
            m = fv.notna() & f5.notna()
            if m.sum() >= 100:
                ic_by_date[f][d] = fv[m].rank().corr(f5[m].rank())
    signs = {}
    for d in rebal:
        pday = pmap.get(d)
        cutoff = pday if pday is not None else pd.Timestamp(IS_START)
        sd = {}
        for f in cfg["pool"]:
            past = [v for dd, v in ic_by_date[f].items() if real[dd] <= cutoff and pd.notna(v)]
            sd[f] = (1.0 if np.mean(past) >= 0 else -1.0) if len(past) >= WF_MIN_OBS else APRIORI_SIGNS[f]
        signs[d] = sd
    return signs


def _composite_oriented(orientation, cfg, cols, close, circ, frames, efr, ind_asof, bounds, rebal, pmap,
                        fwd5=None):
    """Yield (d, pday, comp, broad). is_fit -> delegate to the trusted g09 static-IC-sign composite.
    a_priori / walk_forward -> same neutralize+blend, but with a-priori (or expanding-IC) signs."""
    if orientation == "is_fit":
        yield from g09._composite_series(cfg, cols, close, circ, frames, efr, ind_asof, bounds, rebal, pmap)
        return
    grid = close.index
    wf = _walkforward_signs(cfg, cols, frames, fwd5, grid, rebal, pmap) if orientation == "walk_forward" else None
    for d in rebal:
        pday = pmap.get(d)
        if pday is None:
            continue
        cr = close.loc[pday]
        st = g09.ru.st_codes_on(d)
        listed = pd.Series([(bounds.get(str(c).upper()) is not None
                             and bounds[str(c).upper()][0] <= pday <= bounds[str(c).upper()][1])
                            for c in cols], index=cols)
        not_st = pd.Series([str(c).upper() not in st for c in cols], index=cols)
        broad = listed & cr.notna() & not_st & (cr >= 2.0).fillna(False)
        if broad.sum() < 30:
            continue
        logmv = np.log(circ.loc[pday].where(circ.loc[pday] > 0))
        ind = (ind_asof.loc[pday] if (ind_asof is not None and pday in ind_asof.index)
               else pd.Series("NA", index=cols))
        sign = wf[d] if wf is not None else APRIORI_SIGNS
        comp = pd.Series(0.0, index=cols); wsum = pd.Series(0.0, index=cols)
        for f in cfg["pool"]:
            fr = frames[f]
            fval = (fr.loc[d] if d in fr.index else g09.v7._row(fr, d)).reindex(cols)
            z = g09._neutralize(fval, logmv, ind, broad, cfg["neut"]) * sign[f]
            comp = comp.add(z.fillna(0.0), fill_value=0.0)
            wsum = wsum.add(z.notna().astype(float), fill_value=0.0)
        comp = (comp / wsum.where(wsum > 0)).where(broad & g09._elig_mask(cfg["elig"], efr, d, pday, cols))
        yield d, pday, comp, broad


def verify_orientation_equivalence():
    """Blocker-2: DEMONSTRATE a_priori == is_fit (signs coincide -> identical composite -> identical
    selection), so the existing is_fit results carry no orientation lookahead."""
    cfg, cols, close, circ, ret, fwd5, mkt, frames, efr, ind_asof, bounds, rebal, pmap = _setup()
    gf = {d: comp for d, _, comp, _ in _composite_oriented("is_fit", cfg, cols, close, circ, frames, efr,
                                                           ind_asof, bounds, rebal, pmap)}
    ap = {d: comp for d, _, comp, _ in _composite_oriented("a_priori", cfg, cols, close, circ, frames, efr,
                                                           ind_asof, bounds, rebal, pmap, fwd5)}
    dmax, sel_diff, n = 0.0, 0, 0
    for d in gf:
        if d not in ap:
            continue
        n += 1
        a, b = gf[d].dropna(), ap[d].dropna()
        j = a.index.intersection(b.index)
        dmax = max(dmax, float((a[j] - b[j]).abs().max() if len(j) else 0.0))
        ta = set(a.sort_values(ascending=False).head(K).index)
        tb = set(b.sort_values(ascending=False).head(K).index)
        sel_diff += len(ta ^ tb)
    print(f"[orient-equiv] a_priori vs is_fit over {n} dates: max|Δcomp|={dmax:.2e}  top-{K} selection "
          f"symmetric-diff total={sel_diff}  => {'IDENTICAL (no orientation lookahead)' if dmax < 1e-9 and sel_diff == 0 else 'DIFFER — investigate'}",
          flush=True)
    return {"dates": n, "max_abs_comp_diff": dmax, "topk_selection_symdiff": sel_diff,
            "identical": bool(dmax < 1e-9 and sel_diff == 0)}


# ================================================================ sigma (total | residual) ==========
def _sigma_asof(ret, mkt, pday, cols, mode):
    """Trailing-60d vol up to pday (PIT: pday=T-1). total = raw daily-return stdev; residual = market-model
    idio vol = total*sqrt(1-corr(stock,market)^2) (single-factor residual, removes the beta/market tilt)."""
    win = ret.loc[:pday].tail(SIGMA_WIN)
    n = win.notna().sum()
    tot = win.std(ddof=0).where(n >= SIGMA_MINOBS)
    if mode == "total":
        return tot.reindex(cols)
    m = mkt.loc[:pday].tail(SIGMA_WIN)
    rho = win.corrwith(m)                                     # corr(stock, market) over the window
    resid = tot * np.sqrt((1.0 - rho ** 2).clip(lower=1e-6))
    return resid.reindex(cols)


# ================================================================ weights + concentration cap =========
class InfeasibleCapError(ValueError):
    """cap too tight for a fully-invested long-only book: n * cap < 1."""


def _cap_simplex(w: pd.Series, cap: float) -> pd.Series:
    """Project long-only w onto {w>=0, sum=1, w<=cap} by water-filling. Redistributes over-cap mass to
    EVERY coordinate with headroom (including zero-weight ones), never fails open: raises
    InfeasibleCapError if a fully-invested book cannot satisfy the cap (n*cap<1); asserts sum & cap."""
    if not (0.0 < cap <= 1.0):
        raise ValueError(f"cap must be in (0,1]; got {cap}")
    n = len(w)
    if n == 0:
        return w
    if n * cap < 1.0 - 1e-12:
        raise InfeasibleCapError(f"n*cap = {n}*{cap} < 1 — cannot fully invest under the cap")
    w = w.clip(lower=0.0).astype(float)
    w = pd.Series(1.0 / n, index=w.index) if w.sum() <= 0 else w / w.sum()
    if cap >= 1.0:
        return w
    for _ in range(2000):
        over = w > cap + 1e-15
        if not over.any():
            break
        excess = float((w[over] - cap).sum())
        w[over] = cap
        head = w < cap - 1e-15                                # coordinates with headroom (INCLUDING zeros)
        if not head.any():
            break
        w[head] = w[head] + excess / int(head.sum())         # add equally; sum conserved; re-loop caps overflow
    assert abs(w.sum() - 1.0) < 1e-9 and (w <= cap + 1e-9).all(), "cap-simplex postcondition violated"
    return w


def _weight_vectors(comp_top, sigma_top, circ_top, max_weight) -> dict:
    z = comp_top.astype(float)
    sg = sigma_top.reindex(z.index)
    sg = sg.fillna(sg.median() if sg.notna().any() else 1.0).clip(lower=1e-9)
    raw = {}
    raw["eqw"] = pd.Series(1.0 / len(z), index=z.index)
    a = (sg * z).clip(lower=0.0); raw["alpha"] = a / a.sum() if a.sum() > 0 else raw["eqw"].copy()
    sc = z - z.min() + 1e-6; raw["sigcomp"] = sc / sc.sum()
    iv = (z / sg).clip(lower=0.0); raw["invvol"] = iv / iv.sum() if iv.sum() > 0 else raw["eqw"].copy()
    sq = np.sqrt(circ_top.reindex(z.index).clip(lower=0.0).fillna(0.0))
    raw["sqrtmv"] = sq / sq.sum() if sq.sum() > 0 else raw["eqw"].copy()
    return {c: _cap_simplex(w, max_weight) for c, w in raw.items()}


def _tc_pair(a, b):
    df = pd.concat([a, b], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if len(df) < 20 or df.iloc[:, 0].std() == 0 or df.iloc[:, 1].std() == 0:
        return np.nan
    return float(df.iloc[:, 0].corr(df.iloc[:, 1]))


def _corr(a, b):
    df = pd.concat([a, b], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if len(df) < 5 or df.iloc[:, 0].std() == 0 or df.iloc[:, 1].std() == 0:
        return np.nan
    return float(df.iloc[:, 0].corr(df.iloc[:, 1]))


def _agg(v):
    a = np.array([x for x in v if pd.notna(x)], dtype=float)
    if not len(a):
        return {"mean": float("nan"), "p95": float("nan"), "max": float("nan")}
    return {"mean": float(a.mean()), "p95": float(np.percentile(a, 95)), "max": float(a.max())}


# ================================================================ prepare (TC + schedules + confounds) =
def prepare(orientation, sigma_mode, max_weight, tag):
    cfg, cols, close, circ, ret, fwd5, mkt, frames, efr, ind_asof, bounds, rebal, pmap = _setup()
    grid, end = close.index, pd.Timestamp(IS_END)
    scheds = {c: {} for c in CONSTRUCTIONS}
    tc_acc = {c: {"full_calib": [], "full_raw": [], "hold_calib": [], "hold_raw": []} for c in CONSTRUCTIONS}
    dg = {c: {"eff_n": [], "max_w": [], "corr_w_logmv": [], "corr_w_sigma": []} for c in CONSTRUCTIONS}
    ic_comp, n_elig_hist, max_ic_real = [], [], None
    for d, pday, comp, broad in _composite_oriented(orientation, cfg, cols, close, circ, frames, efr,
                                                    ind_asof, bounds, rebal, pmap, fwd5):
        elig = comp.notna(); n_elig = int(elig.sum()); dkey = str(d.date())
        if n_elig < 30:
            for c in CONSTRUCTIONS:
                scheds[c][dkey] = []
            continue
        n_elig_hist.append(n_elig)
        sigma = _sigma_asof(ret, mkt, pday, cols, sigma_mode)
        z_all = comp.where(elig); logmv = np.log(circ.loc[pday].where(circ.loc[pday] > 0))
        rz = _realization_date(grid, d, 5)                   # B1: only ICs whose label realizes <= IS_END
        if d in fwd5.index and rz is not None and rz <= end:
            f5 = fwd5.loc[d]; m = z_all.notna() & f5.notna()
            if m.sum() >= 100:
                ic_comp.append(z_all[m].rank().corr(f5[m].rank()))
                max_ic_real = rz if max_ic_real is None else max(max_ic_real, rz)
        top = z_all.dropna().sort_values(ascending=False).head(K); top_idx = top.index
        wv = _weight_vectors(top, sigma.reindex(top_idx), circ.loc[pday].reindex(top_idx), max_weight)
        bench = pd.Series(0.0, index=cols); bench[elig] = 1.0 / n_elig
        z_elig, sig_elig = z_all[elig], sigma[elig]
        z_h, sig_h, mv_h = z_all.reindex(top_idx), sigma.reindex(top_idx), logmv.reindex(top_idx)
        for c in CONSTRUCTIONS:
            w = wv[c]; w_full = pd.Series(0.0, index=cols); w_full.loc[top_idx] = w.values
            dw_sig_e = (w_full - bench)[elig] * sig_elig
            tc_acc[c]["full_calib"].append(_tc_pair(z_elig, dw_sig_e))
            tc_acc[c]["full_raw"].append(_tc_pair(z_elig / sig_elig, dw_sig_e))
            dw_h = w.reindex(top_idx) - 1.0 / n_elig
            tc_acc[c]["hold_calib"].append(_tc_pair(z_h, dw_h * sig_h))
            tc_acc[c]["hold_raw"].append(_tc_pair(z_h / sig_h, dw_h * sig_h))
            dg[c]["eff_n"].append(1.0 / float((w ** 2).sum())); dg[c]["max_w"].append(float(w.max()))
            dg[c]["corr_w_logmv"].append(_corr(w.reindex(top_idx), mv_h))
            dg[c]["corr_w_sigma"].append(_corr(w.reindex(top_idx), sig_h))
            scheds[c][dkey] = [[str(code).upper().replace("_", "."), float(x)]
                               for code, x in w.items() if pd.notna(x) and x > 0]
    for c in CONSTRUCTIONS:
        (CACHE / f"sched_{tag}_{c}.json").write_text(json.dumps(scheds[c], ensure_ascii=False), encoding="utf-8")
    tc_summary = {c: {k: float(np.nanmean(v)) if v else float("nan") for k, v in tc_acc[c].items()}
                  for c in CONSTRUCTIONS}
    diag = {c: {"eff_n": _agg(dg[c]["eff_n"]), "max_w": _agg(dg[c]["max_w"]),
                "corr_w_logmv": float(np.nanmean(dg[c]["corr_w_logmv"])) if any(pd.notna(dg[c]["corr_w_logmv"])) else None,
                "corr_w_sigma": float(np.nanmean(dg[c]["corr_w_sigma"])) if any(pd.notna(dg[c]["corr_w_sigma"])) else None,
                "wt_turnover": _weight_turnover(scheds[c])} for c in CONSTRUCTIONS}
    out = {"tag": tag, "variant": VARIANT, "K": K, "window": "IS", "start": IS_START, "end": IS_END,
           "orientation": orientation, "sigma": sigma_mode, "max_weight": max_weight,
           "n_rebal": len(rebal), "n_elig_median": float(np.median(n_elig_hist)) if n_elig_hist else None,
           "composite_is_rank_ic_5d": float(np.nanmean(ic_comp)) if ic_comp else None,
           "max_ic_label_realization": (str(max_ic_real.date()) if max_ic_real is not None else None),
           "tc": tc_summary, "diag": diag}
    (CACHE / f"{tag}_tc.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    _print_tc(out)
    return out


def _weight_turnover(sched):
    keys = sorted(sched); prev, tos = None, []
    for k in keys:
        rows = sched[k]
        if not rows:
            prev = None; continue
        w = pd.Series({r[0]: float(r[1]) for r in rows}); w = w / w.sum()
        if prev is not None:
            idx = prev.index.union(w.index)
            tos.append(0.5 * (prev.reindex(idx).fillna(0.0) - w.reindex(idx).fillna(0.0)).abs().sum())
        prev = w
    return float(np.mean(tos)) if tos else np.nan


def _print_tc(out):
    d = out["diag"]
    print("\n" + "=" * 108, flush=True)
    print(f"STEP 1 — TC + confounds  [tag={out['tag']}  orient={out['orientation']}  σ={out['sigma']}  "
          f"cap={out['max_weight']}]  ({out['n_rebal']} rebalances)", flush=True)
    print(f"  composite IS rank-IC(5d)={out['composite_is_rank_ic_5d']:+.4f} [IS-fitted, optimistic]  "
          f"median eligible/date={out['n_elig_median']:.0f}", flush=True)
    print("  HEADLINE TC = TC_full_calib. TC_hold* = within-book DIAGNOSTIC (near-identity for propto-signal).",
          flush=True)
    print("=" * 108, flush=True)
    print(f"  {'con':9}{'TC_full':>8}{'TC_hold*':>9} | eff_N(mean/max) max_w(mean/p95/MAX)   w~size w~vol", flush=True)
    for c in CONSTRUCTIONS:
        t = out["tc"][c]; e, mw = d[c]["eff_n"], d[c]["max_w"]
        ws = "  flat" if d[c]["corr_w_logmv"] is None else f"{d[c]['corr_w_logmv']:+.2f}"
        wv = "  flat" if d[c]["corr_w_sigma"] is None else f"{d[c]['corr_w_sigma']:+.2f}"
        print(f"  {c:9}{t['full_calib']:>8.3f}{t['hold_calib']:>9.3f} | {e['mean']:>5.1f}/{e['max']:<5.1f}    "
              f"{mw['mean']:.3f}/{mw['p95']:.3f}/{mw['max']:.3f}   {ws:>6} {wv:>6}", flush=True)


# ================================================================ engine run =========================
def run_book(tag, name):
    from src.backtest_engine.event_driven import EventDrivenBacktester, CostConfig
    from src.backtest_engine.event_driven.exchange import FixedSlippage
    sched = json.loads((CACHE / f"sched_{tag}_{name}.json").read_text(encoding="utf-8"))
    cost = CostConfig(buy_commission=0.002, sell_commission=0.002, stamp_tax=0.0,
                      min_commission=0.0, transfer_fee=0.0)
    strat = g09.v7.ModelIDivLowVolStrategy(sched, max_holds=K, reserve=K, weights_mode="explicit")
    bt = EventDrivenBacktester(data_dir=str(ROOT / "data"))
    res = bt.run(strategy=strat, start_time=IS_START, end_time=IS_END, benchmark="000300.SH",
                 account=1_000_000.0, exchange_config=cost, slippage=FixedSlippage(0.0),
                 volume_limit=0.10, hold_on_limit_up=True,
                 preload_fields=["$open", "$close", "$high", "$low", "$vol", "$amount", "$pre_close",
                                 "$adj_factor", "$up_limit", "$down_limit"])
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    net = rep["return"].astype(float)
    net.to_frame("net").to_parquet(CACHE / f"net_{tag}_{name}_is.parquet")
    print(f"[run {tag}/{name}] saved net ({len(net)} days {IS_START}..{IS_END})", flush=True)


def run_all(tag):
    for name in CONSTRUCTIONS:
        run_book(tag, name)


# ================================================================ assemble + INCONCLUSIVE verdict =====
def _metrics(net, wt):
    m = g09.ru.goal_metrics(net); m["calmar"] = m["cagr"] / abs(m["mdd"]) if m["mdd"] else np.nan
    m["wt_turnover"] = wt; return m


def _sharpe(x):
    s = x.std(ddof=0); return float(x.mean() / s * np.sqrt(252)) if s > 0 else np.nan


def _boot_sharpe_diff(net_c, net_b, nboot=2000, block=20):
    """Paired CIRCULAR moving-block bootstrap of Sharpe(c)-Sharpe(b). Reports the tail MASS P(Δ*<=0) — a
    bootstrap tail probability, NOT a null-calibrated p-value — and the 95% CI. NaN if degenerate."""
    df = pd.concat([net_c.rename("c"), net_b.rename("b")], axis=1).dropna()
    a, b = df["c"].values, df["b"].values; n = len(a)
    if n < 60:
        return {"delta_sharpe": float("nan"), "tail_mass_le_0": float("nan"), "ci95": [float("nan")] * 2}
    point = _sharpe(a) - _sharpe(b)
    rng = np.random.default_rng(0); nblk = int(np.ceil(n / block)); diffs = np.empty(nboot)
    for i in range(nboot):
        idx = np.concatenate([np.arange(s, s + block) % n for s in rng.integers(0, n, size=nblk)])[:n]
        diffs[i] = _sharpe(a[idx]) - _sharpe(b[idx])
    return {"delta_sharpe": point, "tail_mass_le_0": float(np.mean(diffs <= 0.0)),
            "ci95": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))]}


def _evidence_manifest(tag, tc, rows):
    inputs = ["returns.parquet", "is_ic.json", "benchmark.json"] + [f"factor_panel/{f}.parquet" for f in POOL] + \
             ["factor_panel/fwd_5d.parquet"]
    in_hashes = {p: (_sha256(CACHE / p) if (CACHE / p).exists() else None) for p in inputs}
    for n in ("e_close_raw", "e_circ_mv"):
        pth = CACHE.parent / "verify09_cache" / f"{n}.parquet"
        in_hashes[f"verify09_cache/{n}.parquet"] = _sha256(pth) if pth.exists() else None
    for rel in ("data/reference/trade_cal.parquet",                        # rebalance grid / calendar
                "data/qlib_data/instruments/st_stocks.txt",                # ST membership (broad mask)
                "data/universe/industry_sw2021_members/industry_sw2021_members.parquet"):  # SW L1 neutralization
        pth = ROOT / rel
        in_hashes[rel] = _sha256(pth) if pth.exists() else None
    out_hashes = {}
    for c in CONSTRUCTIONS:
        for f in (f"sched_{tag}_{c}.json", f"net_{tag}_{c}_is.parquet"):
            out_hashes[f] = _sha256(CACHE / f) if (CACHE / f).exists() else None
    out_hashes[f"{tag}_tc.json"] = _sha256(CACHE / f"{tag}_tc.json") if (CACHE / f"{tag}_tc.json").exists() else None
    # content-address the FULL local dependency chain (M3: commit OR content-address-freeze). guorn_optimize_09
    # + research_utils are otherwise untracked/ignored; freezing their SHA-256 pins the exact reused code.
    dep_rel = ["workspace/scripts/build0_tc_poc.py", "workspace/scripts/guorn_optimize_09.py",
               "workspace/scripts/guorn_verify_07_divlowvol.py", "workspace/scripts/guorn_verify_09_divheavy.py",
               "workspace/scripts/guorn_universe.py", "workspace/scripts/guorn_beta.py",
               "workspace/research/long_only_50cagr/research_utils.py"]
    frozen_deps = {p: (_sha256(ROOT / p) if (ROOT / p).exists() else None) for p in dep_rel}
    pbuild = ROOT / "data" / "qlib_data" / "metadata" / "provider_build.json"
    pinfo = {}
    if pbuild.exists():
        try:
            pj = json.loads(pbuild.read_text())
            pinfo = {"provider_build_id": pj.get("provider_build_id"),
                     "calendar_policy_id": pj.get("calendar_policy_id")}
        except Exception:                                     # noqa: BLE001
            pinfo = {}
    try:
        sha = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                             capture_output=True, text=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain",
                                     "workspace/scripts/build0_tc_poc.py"],
                                    capture_output=True, text=True).stdout.strip())
    except Exception:                                         # noqa: BLE001
        sha, dirty = None, None
    provider_ok = bool(pinfo.get("provider_build_id")) and bool(pinfo.get("calendar_policy_id"))
    reproducible = (sha is not None and dirty is False                     # generated from a CLEAN commit
                    and all(v for v in in_hashes.values())
                    and all(v for v in out_hashes.values()) and all(v for v in frozen_deps.values())
                    and provider_ok)
    return {"evidence_class": "NON_EVIDENTIARY_IS_DESIGN_PROBE",
            # This is a PARTIAL, host-local reproducibility bundle: all listed SHA-256 reconcile on this host,
            # but the results JSONs live under gitignored workspace/outputs (no external root hash) and full
            # execution config / env-lock are not captured. `reproducible_from_clean_commit` is True only when
            # git is clean AND every listed hash + provider id is present; it is NOT a durable evidence manifest.
            "reproducible_from_clean_commit": bool(reproducible), "git_head": sha, "worktree_dirty": dirty,
            "cli_config": {"tag": tag, "orientation": tc["orientation"], "sigma": tc["sigma"],
                           "max_weight": tc["max_weight"], "window": [IS_START, IS_END], "variant": VARIANT,
                           "screen_alpha": SCREEN_ALPHA, "sharpe_margin": SHARPE_MARGIN, "mdd_tol": MDD_TOL,
                           "boot_block": 20, "boot_nboot": 2000, "sigma_win": SIGMA_WIN},
            "provider": pinfo, "python": sys.version.split()[0],
            "frozen_local_deps_sha256": frozen_deps,
            "input_sha256": in_hashes, "output_sha256": out_hashes}


def assemble(tag, do_mlflow=False):
    tc = json.loads((CACHE / f"{tag}_tc.json").read_text())
    bar = json.loads((CACHE / "benchmark.json").read_text())["REPLAY"]["IS"] \
        if (CACHE / "benchmark.json").exists() else None
    nets, rows = {}, {}
    for name in CONSTRUCTIONS:
        p = CACHE / f"net_{tag}_{name}_is.parquet"
        if not p.exists():
            print(f"  [assemble] MISSING net for {tag}/{name}", flush=True); continue
        net = pd.read_parquet(p)["net"].astype(float); net.index = pd.to_datetime(net.index)
        nets[name] = net; m = _metrics(net, tc["diag"][name]["wt_turnover"])
        m["tc_full_calib"] = tc["tc"][name]["full_calib"]; m["eff_n"] = tc["diag"][name]["eff_n"]["mean"]
        m["max_w"] = tc["diag"][name]["max_w"]["max"]; rows[name] = m
    boot = {n: _boot_sharpe_diff(nets[n], nets[BASELINE]) for n in CONSTRUCTIONS
            if n != BASELINE and n in nets and BASELINE in nets}
    _print_table(tag, tc, rows, bar, boot)
    verdict = _verdict(rows, tc, boot)
    manifest = _evidence_manifest(tag, tc, rows)
    (CACHE / f"{tag}_results.json").write_text(json.dumps(
        {"config": manifest["cli_config"], "metrics": rows, "tc": tc["tc"], "diag": tc["diag"],
         "bar_is": bar, "boot_vs_eqw": boot, "verdict": verdict, "evidence_manifest": manifest},
        indent=1), encoding="utf-8")
    print(f"\n  reproducibility bundle: reproducible_from_clean_commit="
          f"{manifest['reproducible_from_clean_commit']} (git={str(manifest['git_head'])[:12]} "
          f"dirty={manifest['worktree_dirty']}) class={manifest['evidence_class']} "
          f"provider={manifest['provider'].get('provider_build_id','?')}", flush=True)
    if do_mlflow:
        _mlflow(tag, rows, tc)
    return rows, verdict


def _print_table(tag, tc, rows, bar, boot):
    print("\n" + "=" * 116, flush=True)
    print(f"STEP 2 — NET-OF-COST IS  [tag={tag} orient={tc['orientation']} σ={tc['sigma']} cap={tc['max_weight']}] "
          f"— SAME top-{K} names; weights differ only", flush=True)
    print("  [absolute Sharpe; TC benchmark (EW-eligible) ≠ PnL benchmark (000300.SH) — do NOT cross-cite TC→IR]",
          flush=True)
    print("=" * 116, flush=True)
    print(f"  {'con':9}{'CAGR':>8}{'Sharpe':>7}{'MDD':>8}{'vol':>6}{'effN':>5}{'maxW':>6}{'TC_full':>8}  ΔSharpe (tail-mass; 95%CI)", flush=True)
    for name in CONSTRUCTIONS:
        if name not in rows:
            continue
        m = rows[name]; bt = "  — baseline"
        if name in boot:
            bb = boot[name]; bt = f"  {bb['delta_sharpe']:+.2f} (tm={bb['tail_mass_le_0']:.2f}; [{bb['ci95'][0]:+.2f},{bb['ci95'][1]:+.2f}])"
        print(f"  {name:9}{m['cagr']:>+7.2%}{m['sharpe']:>7.2f}{m['mdd']:>+7.2%}{m['ann_vol']:>5.1%}"
              f"{m['eff_n']:>5.1f}{m['max_w']:>6.2f}{m['tc_full_calib']:>8.3f}{bt}", flush=True)
    if bar:
        print(f"  {'#9REPLAY':9}{bar['cagr']:>+7.2%}{bar['sharpe']:>7.2f}{bar['mdd']:>+7.2%}{bar['ann_vol']:>5.1%}"
              f"{'—':>5}{'—':>6}{'—':>8}  <- DIFFERENT NAMES (selection, not weighting)", flush=True)
    for c in CONSTRUCTIONS:
        print(f"    {c:8} {LABELS[c]}", flush=True)


def _verdict(rows, tc, boot):
    """EXPLORATORY, UNADJUSTED screen (NOT an equivalence test, NO familywise/FWER control — `tail_mass`
    is a bootstrap tail probability, not a null-calibrated p-value). Fail-CLOSED at BOTH levels: a
    construction passes only with finite tail-mass < SCREEN_ALPHA AND ΔSharpe ≥ margin AND MDD-not-worse;
    and the FAMILY result is `incomplete` (never a pass) unless every declared SIGNAL_PROP member is present
    with a finite tail-mass — a missing/degenerate member can never yield a family-level positive."""
    family_ok = (BASELINE in rows and all(n in rows and n in boot for n in SIGNAL_PROP))
    if not family_ok:
        return {"status": "incomplete", "screen_passed": False,
                "reason": "a declared family member (baseline or a signal-proportional construction) is "
                          "missing — fail-closed (no family-level positive is possible)",
                "baseline": BASELINE, "per_construction": {}}
    b = rows[BASELINE]
    def screen(name):
        m = rows[name]; d_sh = m["sharpe"] - b["sharpe"]; d_mdd = m["mdd"] - b["mdd"]
        tm = boot.get(name, {}).get("tail_mass_le_0", float("nan"))
        passed = bool(np.isfinite(tm) and d_sh >= SHARPE_MARGIN and d_mdd >= -MDD_TOL and tm < SCREEN_ALPHA)
        return {"d_sharpe": d_sh, "d_mdd": d_mdd, "d_cagr": m["cagr"] - b["cagr"],
                "tail_mass_le_0": tm, "d_tc_full": tc["tc"][name]["full_calib"] - tc["tc"][BASELINE]["full_calib"],
                "screen_passed": passed}
    per = {n: screen(n) for n in SIGNAL_PROP}
    any_passed = any(v["screen_passed"] for v in per.values())
    v = {"gate": "EXPLORATORY UNADJUSTED screen (no FWER control; tail-mass is not a p-value), fail-closed: "
                 "finite tail-mass < %.2f AND ΔSharpe ≥ %.2f AND MDD no more than %.0fpp worse; family "
                 "incomplete unless all members present. TC descriptive only" % (SCREEN_ALPHA, SHARPE_MARGIN, MDD_TOL * 100),
         "baseline": BASELINE, "per_construction": per, "any_signalprop_passed_screen": any_passed,
         "screen_passed": any_passed, "status": "INCONCLUSIVE_no_greenlight",
         "call": ("A signal-proportional proxy passed the UNADJUSTED exploratory screen — a positive family "
                  "claim would still require a preregistered primary contrast or a joint null-calibrated "
                  "max-statistic across all configs; not a deployment decision." if any_passed else
                  "INCONCLUSIVE / no greenlight. No signal-proportional proxy produced a screen-qualified "
                  "positive result; record only that there is NO positive evidence. This single-window, "
                  "post-hoc, NON-equivalence, unadjusted screen does NOT establish that weighting is a weak "
                  "lever, and does NOT rank selection/universe ahead of weighting (universe never varied). "
                  "Only unconstrained σ-proxies + a single-name cap were tested — NOT the §S3 constructor.")}
    print("\n" + "=" * 100, flush=True)
    print("STEP 3 — SCREEN RESULT (" + v["gate"] + ")", flush=True)
    print("=" * 100, flush=True)
    for name, e in per.items():
        print(f"  {name:9} ΔSharpe={e['d_sharpe']:+.2f} (tail-mass={e['tail_mass_le_0']:.2f})  "
              f"ΔMDD={e['d_mdd']:+.2%}  ΔCAGR={e['d_cagr']:+.2%}  ΔTC_full={e['d_tc_full']:+.3f}  "
              f"screen_passed={e['screen_passed']}", flush=True)
    print(f"\n  any signal-prop construction passed the screen = {any_passed}  =>  {v['status']}", flush=True)
    print(f"  → {v['call']}", flush=True)
    return v


def _mlflow(tag, rows, tc):
    try:
        from src.alpha_research.mlflow_tracker import ExperimentTracker
        tr = ExperimentTracker(config_path=str(ROOT / "config.yaml"))
        for name, m in rows.items():
            tr.start_run(f"build0_{tag}_{name}")
            tr.log_params({"experiment": "BUILD0_TC_POC", "tag": tag, "construction": name,
                           "orientation": tc["orientation"], "sigma": tc["sigma"],
                           "max_weight": tc["max_weight"], "K": K, "window": "IS"})
            tr.log_metrics({k: float(v) for k, v in m.items() if isinstance(v, (int, float)) and np.isfinite(v)})
            tr.end_run()
    except Exception as exc:                                   # noqa: BLE001
        log.warning("MLflow skipped (%s: %s)", type(exc).__name__, exc)


def main():
    ap = argparse.ArgumentParser(description="BUILD-0 TC PoC v2 (IS-only screen; no OOS path)")
    ap.add_argument("--verify-orientation", action="store_true", help="demonstrate a_priori == is_fit (Blocker-2)")
    ap.add_argument("--prepare", action="store_true", help="Step 1: TC + confounds + schedules")
    ap.add_argument("--run", help="engine-run one construction")
    ap.add_argument("--run-all", action="store_true", help="engine-run all constructions")
    ap.add_argument("--assemble", action="store_true", help="Step 3: table + fail-closed screen + manifest")
    ap.add_argument("--all", action="store_true", help="prepare -> run-all -> assemble")
    ap.add_argument("--orientation", default="a_priori", choices=("a_priori", "is_fit", "walk_forward"))
    ap.add_argument("--sigma", default="total", choices=("total", "residual"))
    ap.add_argument("--max-weight", type=float, default=1.0, help="single-name weight cap in (0,1]")
    ap.add_argument("--tag", default="build0")
    ap.add_argument("--mlflow", action="store_true")
    a = ap.parse_args()
    cfg = (a.orientation, a.sigma, a.max_weight, a.tag)
    if a.verify_orientation:
        verify_orientation_equivalence()
    if a.all:
        prepare(*cfg); run_all(a.tag); assemble(a.tag, a.mlflow); return
    if a.prepare:
        prepare(*cfg)
    if a.run:
        run_book(a.tag, a.run)
    if a.run_all:
        run_all(a.tag)
    if a.assemble:
        assemble(a.tag, a.mlflow)
    if not any((a.verify_orientation, a.prepare, a.run, a.run_all, a.assemble, a.all)):
        ap.print_help()


if __name__ == "__main__":
    main()
