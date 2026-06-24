# -*- coding: utf-8 -*-
"""GUORN20 walk-forward re-weighting engine — implements the SHIPPED v5 plan
[workspace/research/capital_allocation_buildout/GUORN20_REWEIGHT_PLAN.md]
(GPT-5.5 Pro cross-review R1->R5 = SHIP, 2026-06-24).

Sealed-OOS protocol (the part that makes this valid):
  * design-freeze 2023-05-31 — ALL scheme/param selection uses ONLY <= that date
  * frozen deterministic selection rule -> exactly ONE candidate (§4.0)
  * holdout 2023-06-01..2026-06-18 opened ONCE, for the frozen candidate only
  * THREE-state verdict (pass / inconclusive / fail) aggregated over block lengths 10/21/63
  * path-correct paired block bootstrap (rebuild BOTH NAV paths, never an excess path)
  * max-stat family-wise correction is a PRE-HOLDOUT-only claim
  * metrics via src/result_analysis/metrics.py; unlevered (sum=1, long-only); MLflow logged

Sign convention: MDD is stored as a POSITIVE magnitude (0.32 = -32% drawdown), so
  ΔMDD = strat_mdd_mag - ew_mdd_mag < 0  ==  candidate has the SMALLER drawdown (better).
  This matches the plan's "ΔMDD<0 = better". (result_analysis.calculate_max_drawdown
  returns a NEGATIVE number; we take abs().)

Implementation notes / disclosed deviations (see self-review):
  * floor/cap enforcement: S3 min-var and S8 max-Sharpe are clean box-QPs -> box IN cvxpy.
    S1 inv-vol, S2 ERC, S4 max-div, S5 HRP, S6 two-stage, S7 risk-tilt compute their
    natural weights then a deterministic bounded-simplex projection (their box-constrained
    forms are non-standard). All deterministic.
  * S7 tilt score = trailing Sharpe (mu/vol, floored at 0) — more stable than short-window Calmar.

NON-FORMAL research artifact.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"E:\量化系统")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
from src.result_analysis import metrics as M  # noqa: E402

# ----------------------------------------------------------------------------- config (frozen)
DATA = ROOT / "workspace/research/idea_sourcing/guorn/guorn20_daily_returns.parquet"
META = ROOT / "workspace/research/idea_sourcing/guorn/guorn20_meta.csv"
OUTDIR = ROOT / "workspace/outputs/guorn20_reweight"

DESIGN_FREEZE = pd.Timestamp("2023-05-31")
HOLDOUT_START = pd.Timestamp("2023-06-01")
HOLDOUT_END = pd.Timestamp("2026-06-18")
PRE_HOLDOUT_WINDOWS = [  # §4.3 fixed subperiods (all <= design-freeze)
    (pd.Timestamp("2014-01-02"), pd.Timestamp("2016-12-30")),
    (pd.Timestamp("2017-01-03"), pd.Timestamp("2019-12-31")),
    (pd.Timestamp("2020-01-02"), pd.Timestamp("2023-05-31")),
]
LOOKBACKS = [126, 252, 504]
CADENCES = ["ME", "QE"]            # month-end / quarter-end rebalance
CAPS = [0.10, 0.15]
FLOORS = [0.01, 0.025]
BASE_COST_BPS = 10.0              # one-way, used for selection; sensitivity at 0/5/10/20
COST_GRID_BPS = [0.0, 5.0, 10.0, 20.0]
BOOT_BLOCKS = [10, 21, 63]
BOOT_N = 10000
SEED = 20260624
RF = 0.03                         # risk-free for Sharpe/Sortino, to match 果仁 ~3%
ANNUAL = 252

# three-state pass thresholds (§4.0)
PASS_DCALMAR = 0.10
PASS_DCAGR_LB = -0.03
PASS_PROB = 0.80

# scheme complexity rank for deterministic tie-break (§4.0; lower = simpler/preferred)
COMPLEXITY = {"EW": 0, "inv_vol": 1, "two_stage": 2, "hrp": 3, "erc": 4,
              "min_var": 5, "max_div": 5, "risk_tilt": 6, "max_sharpe": 99}
DEPLOYABLE = ["inv_vol", "erc", "min_var", "max_div", "hrp", "two_stage", "risk_tilt"]  # S8 excluded
DIAGNOSTIC_ONLY = ["max_sharpe"]
BOX_IN_OPTIMIZER = {"min_var", "max_sharpe"}

import cvxpy as cp                      # noqa: E402
from sklearn.covariance import LedoitWolf  # noqa: E402
from scipy.cluster.hierarchy import linkage, to_tree  # noqa: E402


# ----------------------------------------------------------------------------- data
def load() -> tuple[pd.DataFrame, dict]:
    R = pd.read_parquet(DATA).sort_index()
    R.index = pd.to_datetime(R.index)
    meta = pd.read_csv(META, encoding="utf-8-sig")
    grp = dict(zip(meta["name"], meta["style_group"]))
    # column order stable
    cols = [c for c in meta["name"] if c in R.columns]
    R = R[cols]
    return R, grp


# ----------------------------------------------------------------------------- weighting helpers
def bounded_simplex_projection(w: np.ndarray, floor: float, cap: float, iters: int = 200) -> np.ndarray:
    """Project w onto {x: sum=1, floor<=x_i<=cap} by iterative water-filling (deterministic)."""
    n = len(w)
    if floor * n > 1 + 1e-9 or cap * n < 1 - 1e-9:
        raise ValueError(f"infeasible box: floor*n={floor*n}, cap*n={cap*n}")
    w = np.clip(np.nan_to_num(w, nan=0.0), 0, None)
    if w.sum() <= 0:
        w = np.ones(n)
    w = w / w.sum()
    for _ in range(iters):
        w = np.clip(w, floor, cap)
        s = w.sum()
        if abs(s - 1.0) < 1e-10:
            break
        at_lo = w <= floor + 1e-12
        at_hi = w >= cap - 1e-12
        free = ~(at_lo | at_hi)
        if not free.any():
            # all clipped; nudge toward feasibility uniformly among non-cap
            free = ~at_hi if s > 1 else ~at_lo
            if not free.any():
                break
        deficit = 1.0 - s
        base = w[free].sum()
        if base <= 1e-12:
            w[free] += deficit / free.sum()
        else:
            w[free] += deficit * (w[free] / base)
    return np.clip(w, floor, cap) / np.clip(w, floor, cap).sum()


def w_inv_vol(vol: np.ndarray) -> np.ndarray:
    iv = 1.0 / np.where(vol > 1e-9, vol, np.nan)
    iv = np.nan_to_num(iv, nan=np.nanmin(iv[iv > 0]) if np.any(iv > 0) else 1.0)
    return iv / iv.sum()


def w_erc(cov: np.ndarray, iters: int = 500) -> np.ndarray:
    """Equal risk contribution via Roncalli cyclical coordinate descent (unconstrained, normalized)."""
    n = cov.shape[0]
    w = 1.0 / np.sqrt(np.diag(cov))
    w = w / w.sum()
    for _ in range(iters):
        sigma_w = cov @ w
        for i in range(n):
            # target: w_i * (cov w)_i equal across i; cyclical update
            a = cov[i, i]
            b = sigma_w[i] - a * w[i]
            # solve a*w_i^2 + b*w_i - (1/n) = 0  (risk budget 1/n of total)
            c = -1.0 / n
            wi = (-b + np.sqrt(max(b * b - 4 * a * c, 0.0))) / (2 * a)
            sigma_w = sigma_w + cov[:, i] * (wi - w[i])
            w[i] = wi
        w = np.clip(w, 1e-9, None)
        w = w / w.sum()
    return w


def w_min_var(cov: np.ndarray, floor: float, cap: float) -> np.ndarray:
    n = cov.shape[0]
    w = cp.Variable(n)
    prob = cp.Problem(cp.Minimize(cp.quad_form(w, cp.psd_wrap(cov))),
                      [cp.sum(w) == 1, w >= floor, w <= cap])
    prob.solve(solver=cp.OSQP, verbose=False)
    if w.value is None:
        return bounded_simplex_projection(1.0 / np.sqrt(np.diag(cov)), floor, cap)
    return bounded_simplex_projection(np.asarray(w.value).ravel(), floor, cap)


def w_max_div(cov: np.ndarray, vol: np.ndarray) -> np.ndarray:
    """Max diversification: minimize y'Σy s.t. vol·y = 1, y>=0; w = y/sum(y)."""
    n = cov.shape[0]
    y = cp.Variable(n)
    prob = cp.Problem(cp.Minimize(cp.quad_form(y, cp.psd_wrap(cov))),
                      [vol @ y == 1, y >= 0])
    prob.solve(solver=cp.OSQP, verbose=False)
    if y.value is None or np.asarray(y.value).sum() <= 0:
        return w_inv_vol(vol)
    yv = np.clip(np.asarray(y.value).ravel(), 0, None)
    return yv / yv.sum()


def w_max_sharpe(mu: np.ndarray, cov: np.ndarray, floor: float, cap: float) -> np.ndarray:
    """Long-only tangency (NEGATIVE CONTROL): min y'Σy s.t. (mu-rf)·y=1, y>=0; normalize; box-project."""
    n = cov.shape[0]
    excess = mu - RF
    if np.all(excess <= 0):
        return bounded_simplex_projection(1.0 / np.sqrt(np.diag(cov)), floor, cap)
    y = cp.Variable(n)
    prob = cp.Problem(cp.Minimize(cp.quad_form(y, cp.psd_wrap(cov))),
                      [excess @ y == 1, y >= 0])
    prob.solve(solver=cp.OSQP, verbose=False)
    if y.value is None or np.asarray(y.value).sum() <= 0:
        return bounded_simplex_projection(np.clip(excess, 0, None), floor, cap)
    yv = np.clip(np.asarray(y.value).ravel(), 0, None)
    return bounded_simplex_projection(yv / yv.sum(), floor, cap)


def _hrp_quasi_diag(link, n):
    t = to_tree(link)
    return t.pre_order(lambda x: x.id)  # leaf order


def w_hrp(cov: np.ndarray, corr: np.ndarray) -> np.ndarray:
    """Hierarchical Risk Parity (López de Prado), trailing clustering."""
    n = cov.shape[0]
    dist = np.sqrt(np.clip((1.0 - corr) / 2.0, 0, None))
    # condensed distance
    iu = np.triu_indices(n, 1)
    link = linkage(dist[iu], method="single")
    order = _hrp_quasi_diag(link, n)
    w = np.ones(n)
    clusters = [order]
    while clusters:
        new = []
        for c in clusters:
            if len(c) <= 1:
                continue
            half = len(c) // 2
            c1, c2 = c[:half], c[half:]
            v1 = _cluster_var(cov, c1)
            v2 = _cluster_var(cov, c2)
            alpha = 1 - v1 / (v1 + v2)
            for i in c1:
                w[i] *= alpha
            for i in c2:
                w[i] *= (1 - alpha)
            new += [c1, c2]
        clusters = new
    return w / w.sum()


def _cluster_var(cov, idx):
    sub = cov[np.ix_(idx, idx)]
    iv = 1.0 / np.diag(sub)
    w = iv / iv.sum()
    return float(w @ sub @ w)


def w_two_stage(vol, cov, groups_idx) -> np.ndarray:
    """Risk-parity across a-priori style groups, EW within group (§3.3 S6)."""
    n = len(vol)
    # group-level risk parity via inverse group-vol (group vol from EW-within-group)
    g_w = {}
    for g, idx in groups_idx.items():
        gi = np.array(idx)
        win = np.zeros(n)
        win[gi] = 1.0 / len(gi)
        g_vol = np.sqrt(max(win @ cov @ win, 1e-12))
        g_w[g] = 1.0 / g_vol
    tot = sum(g_w.values())
    w = np.zeros(n)
    for g, idx in groups_idx.items():
        gi = np.array(idx)
        w[gi] = (g_w[g] / tot) / len(gi)
    return w / w.sum()


def w_risk_tilt(vol, mu) -> np.ndarray:
    """Inverse-vol x trailing-Sharpe score (floored at 0), normalized (§3.3 S7)."""
    iv = 1.0 / np.where(vol > 1e-9, vol, np.nan)
    iv = np.nan_to_num(iv, nan=0.0)
    sharpe = np.clip((mu - RF) / np.where(vol > 1e-9, vol, np.nan), 0, None)
    sharpe = np.nan_to_num(sharpe, nan=0.0)
    score = iv * (0.5 + sharpe)   # 0.5 baseline so all-negative-Sharpe still allocates by inv-vol
    if score.sum() <= 0:
        return w_inv_vol(vol)
    return score / score.sum()


# ----------------------------------------------------------------------------- window-stat cache
@dataclass
class WinStat:
    mu: np.ndarray
    vol: np.ndarray
    cov: np.ndarray
    corr: np.ndarray


def build_stat_cache(R: pd.DataFrame, lookbacks, rebal_idx_all):
    """For each L and each rebal integer-position, trailing-window stats from rows [pos-L, pos)."""
    arr = R.values
    cache = {}
    for L in lookbacks:
        for pos in rebal_idx_all:
            if pos < L:
                continue
            win = arr[pos - L:pos]
            mu = win.mean(0) * ANNUAL
            vol = win.std(0, ddof=1) * np.sqrt(ANNUAL)
            cov = LedoitWolf().fit(win).covariance_ * ANNUAL
            sd = np.sqrt(np.diag(cov))
            corr = cov / np.outer(sd, sd)
            cache[(L, pos)] = WinStat(mu, vol, cov, corr)
    return cache


def weights_for(scheme, stat: WinStat, cap, floor, groups_idx) -> np.ndarray:
    if scheme == "EW":
        n = len(stat.vol)
        return np.ones(n) / n
    if scheme == "inv_vol":
        return bounded_simplex_projection(w_inv_vol(stat.vol), floor, cap)
    if scheme == "erc":
        return bounded_simplex_projection(w_erc(stat.cov), floor, cap)
    if scheme == "min_var":
        return w_min_var(stat.cov, floor, cap)
    if scheme == "max_div":
        return bounded_simplex_projection(w_max_div(stat.cov, stat.vol), floor, cap)
    if scheme == "hrp":
        return bounded_simplex_projection(w_hrp(stat.cov, stat.corr), floor, cap)
    if scheme == "two_stage":
        return bounded_simplex_projection(w_two_stage(stat.vol, stat.cov, groups_idx), floor, cap)
    if scheme == "risk_tilt":
        return bounded_simplex_projection(w_risk_tilt(stat.vol, stat.mu), floor, cap)
    if scheme == "max_sharpe":
        return w_max_sharpe(stat.mu, stat.cov, floor, cap)
    raise ValueError(scheme)


# ----------------------------------------------------------------------------- walk-forward
def rebal_positions(R: pd.DataFrame, cadence: str):
    """Integer positions of the last trading day of each cadence period."""
    s = pd.Series(range(len(R)), index=R.index)
    pos = s.resample(cadence).last().dropna().astype(int).tolist()
    return pos


def walk_forward(R, scheme, L, cadence, cap, floor, cost_bps, cache, groups_idx):
    """Return paired daily DataFrame [strategy_return, ew_return] (cadence-matched EW), net of cost."""
    arr = R.values
    n = arr.shape[1]
    pos_list = [p for p in rebal_positions(R, cadence) if p >= L]
    if not pos_list:
        return None
    seg_bounds = pos_list + [len(R)]
    strat = np.full(len(R), np.nan)
    eww = np.full(len(R), np.nan)
    w_cur = None
    w_cur_ew = None
    cb = cost_bps / 1e4
    tov = 0.0   # cumulative one-way turnover (buys); annualized at return for the §4.0 tie-break
    for k, t0 in enumerate(pos_list):
        t1 = seg_bounds[k + 1]
        stat = cache[(L, t0)]
        w_tgt = weights_for(scheme, stat, cap, floor, groups_idx)
        w_tgt_ew = np.ones(n) / n
        # cost at rebalance (one-way buy+sell notional * bps) + turnover tracking
        if w_cur is None:
            cost = cb * np.abs(w_tgt).sum()           # initial build
            cost_ew = cb * np.abs(w_tgt_ew).sum()
            tov += float(np.abs(w_tgt).sum())
        else:
            cost = cb * (np.abs(np.maximum(w_tgt - w_cur, 0)).sum()
                         + np.abs(np.maximum(w_cur - w_tgt, 0)).sum())
            cost_ew = cb * (np.abs(np.maximum(w_tgt_ew - w_cur_ew, 0)).sum()
                            + np.abs(np.maximum(w_cur_ew - w_tgt_ew, 0)).sum())
            tov += float(np.maximum(w_tgt - w_cur, 0).sum())
        w_cur = w_tgt.copy()
        w_cur_ew = w_tgt_ew.copy()
        for d in range(t0, t1):
            rd = arr[d]
            r_s = float(w_cur @ rd)
            r_e = float(w_cur_ew @ rd)
            if d == t0:
                r_s -= cost
                r_e -= cost_ew
            strat[d] = r_s
            eww[d] = r_e
            # drift
            w_cur = w_cur * (1 + rd); w_cur = w_cur / w_cur.sum()
            w_cur_ew = w_cur_ew * (1 + rd); w_cur_ew = w_cur_ew / w_cur_ew.sum()
    out = pd.DataFrame({"strategy_return": strat, "ew_return": eww}, index=R.index).dropna()
    n_years = max(len(out) / ANNUAL, 1e-9)
    return out, tov / n_years


# ----------------------------------------------------------------------------- metrics
def calendar_cagr(r: pd.Series) -> float:
    if len(r) < 2:
        return np.nan
    total = float((1 + r).prod())
    yrs = (r.index[-1] - r.index[0]).days / 365.25
    return total ** (1 / yrs) - 1 if yrs > 0 else np.nan


def path_metrics(r: pd.Series) -> dict:
    return {
        "cagr252": M.calculate_cagr(r, annual_factor=ANNUAL),
        "cagr_cal": calendar_cagr(r),
        "vol": M.calculate_volatility(r, annual_factor=ANNUAL),
        "sharpe": M.calculate_sharpe_ratio(r, risk_free_rate=RF, annual_factor=ANNUAL),
        "sortino": M.calculate_sortino_ratio(r, risk_free_rate=RF, annual_factor=ANNUAL),
        "mdd_mag": abs(M.calculate_max_drawdown(r)),
        "calmar": M.calculate_calmar_ratio(r, annual_factor=ANNUAL),
    }


def delta_metrics(seg: pd.DataFrame) -> dict:
    s = path_metrics(seg["strategy_return"])
    e = path_metrics(seg["ew_return"])
    return {
        "d_calmar": s["calmar"] - e["calmar"],
        "d_mdd": s["mdd_mag"] - e["mdd_mag"],     # <0 = candidate smaller drawdown (better)
        "d_cagr252": s["cagr252"] - e["cagr252"],
        "d_cagr_cal": s["cagr_cal"] - e["cagr_cal"],
        "d_sharpe": s["sharpe"] - e["sharpe"],
        "strat": s, "ew": e,
    }


# ----------------------------------------------------------------------------- stationary bootstrap
def make_idx_sets(T: int, block: int, n_boot: int, seed: int) -> np.ndarray:
    """Vectorized stationary (Politis-Romano) bootstrap index matrix (n_boot, T)."""
    rng = np.random.default_rng(seed + block)
    p = 1.0 / block
    starts = rng.integers(0, T, size=(n_boot, T))
    newblk = rng.random((n_boot, T)) < p
    newblk[:, 0] = True
    out = np.empty((n_boot, T), dtype=np.int64)
    cur = starts[:, 0].copy()
    out[:, 0] = cur
    for j in range(1, T):              # loop over time (T~2300), vectorized over n_boot
        cur = np.where(newblk[:, j], starts[:, j], cur + 1)
        cur %= T
        out[:, j] = cur
    return out


def boot_deltas(s: np.ndarray, e: np.ndarray, idx: np.ndarray):
    """Paired path-correct deltas: rebuild BOTH NAV paths from resampled rows, then Δ (n_boot,)."""
    T = idx.shape[1]
    cs, ms, gs = _path_calmar_mdd_cagr(s[idx], T)
    ce, me, ge = _path_calmar_mdd_cagr(e[idx], T)
    return cs - ce, ms - me, gs - ge


def summarize_boot(dcal, dmdd, dcagr) -> dict:
    return {
        "d_calmar_med": float(np.nanmedian(dcal)),
        "d_calmar_lb": float(np.nanpercentile(dcal, 2.5)),
        "d_cagr_lb": float(np.nanpercentile(dcagr, 2.5)),
        "d_mdd_med": float(np.nanmedian(dmdd)),
        "p_dcalmar_gt0": float(np.nanmean(dcal > 0)),
    }


def _path_calmar_mdd_cagr(ret_2d: np.ndarray, T: int):
    """Vectorized over rows: ret_2d [n, T] daily returns -> (calmar, mdd_mag, cagr252) per row."""
    nav = np.cumprod(1.0 + ret_2d, axis=1)
    run_max = np.maximum.accumulate(nav, axis=1)
    dd = (run_max - nav) / run_max
    mdd = dd.max(axis=1)
    cagr = nav[:, -1] ** (ANNUAL / T) - 1.0
    calmar = np.where(mdd > 1e-9, cagr / mdd, np.nan)
    return calmar, mdd, cagr


def candidate_bootstrap(seg: pd.DataFrame, blocks, n_boot, seed) -> dict:
    """Single-candidate paired bootstrap (vectorized); per block length, CI + P(dCalmar>0)."""
    s = seg["strategy_return"].values
    e = seg["ew_return"].values
    T = len(s)
    res = {}
    for blk in blocks:
        idx = make_idx_sets(T, blk, n_boot, seed)
        dcal, dmdd, dcagr = boot_deltas(s, e, idx)
        res[blk] = summarize_boot(dcal, dmdd, dcagr)
    return res


def three_state(point_d: dict, boot: dict) -> str:
    """Aggregate three-state verdict across block lengths (§4.0/§4.1)."""
    states = []
    for blk, r in boot.items():
        if (point_d["d_mdd"] < 0 and point_d["d_calmar"] >= PASS_DCALMAR
                and r["d_cagr_lb"] >= PASS_DCAGR_LB and r["p_dcalmar_gt0"] >= PASS_PROB):
            states.append("pass")
        elif point_d["d_mdd"] >= 0 or point_d["d_calmar"] <= 0 or r["d_cagr_lb"] < PASS_DCAGR_LB:
            states.append("fail")
        else:
            states.append("inconclusive")
    if any(s == "fail" for s in states):
        return "fail"
    if all(s == "pass" for s in states):
        return "pass"
    return "inconclusive"


# ----------------------------------------------------------------------------- effective trials + max-stat
def n_eff_participation(diff_mat: np.ndarray) -> float:
    """diff_mat: [n_cfg, T] of (strat-ew) daily diffs. participation ratio of corr eigenvalues."""
    C = np.corrcoef(diff_mat)
    C = np.nan_to_num(C, nan=0.0)
    ev = np.linalg.eigvalsh(C)
    ev = np.clip(ev, 0, None)
    return float((ev.sum() ** 2) / (np.square(ev).sum() + 1e-12))


def maxstat_family(strat_mat, ew_mat, T, blk, n_boot, seed) -> np.ndarray:
    """Null dist of max ΔCalmar across configs (SHARED resample), pre-holdout (§4.1, vectorized)."""
    idx = make_idx_sets(T, blk, n_boot, seed + 777)   # one resample set, shared across configs
    dmat = np.empty((strat_mat.shape[0], n_boot))
    for c in range(strat_mat.shape[0]):
        dcal, _, _ = boot_deltas(strat_mat[c], ew_mat[c], idx)
        dmat[c] = dcal
    return np.nanmax(dmat, axis=0)


# ----------------------------------------------------------------------------- main pipeline
def file_hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="tiny grid + small bootstrap to validate")
    ap.add_argument("--no-mlflow", action="store_true")
    args = ap.parse_args()

    OUTDIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    lookbacks = [252] if args.smoke else LOOKBACKS
    cadences = ["ME"] if args.smoke else CADENCES
    caps = [0.15] if args.smoke else CAPS
    floors = [0.01] if args.smoke else FLOORS
    boot_n = 200 if args.smoke else BOOT_N
    schemes = ["EW"] + DEPLOYABLE + DIAGNOSTIC_ONLY

    R, grp = load()
    groups_idx = {}
    for j, c in enumerate(R.columns):
        groups_idx.setdefault(grp[c], []).append(j)
    print(f"[data] {R.shape} {R.index.min().date()}..{R.index.max().date()}  groups={ {k:len(v) for k,v in groups_idx.items()} }")

    pre_mask = R.index <= DESIGN_FREEZE
    print(f"[split] pre-holdout {pre_mask.sum()} days <= {DESIGN_FREEZE.date()}; holdout {(~pre_mask).sum()} days")

    # rebal positions union (for stat cache)
    all_pos = sorted(set(sum([rebal_positions(R, c) for c in cadences], [])))
    print(f"[cache] building window-stat cache for L={lookbacks} over {len(all_pos)} rebal points ...")
    cache = build_stat_cache(R, lookbacks, all_pos)

    # ---- compute every config's full daily paired series
    configs = []
    for sch in schemes:
        for L in lookbacks:
            for cad in cadences:
                if sch == "EW":
                    caps_, floors_ = [caps[0]], [floors[0]]   # EW has no box; one per (L,cad)
                else:
                    caps_, floors_ = caps, floors
                for cap in caps_:
                    for fl in floors_:
                        configs.append((sch, L, cad, cap, fl))
    print(f"[grid] {len(configs)} configs; computing walk-forward series ...")

    series = {}
    turnovers = {}
    for i, (sch, L, cad, cap, fl) in enumerate(configs):
        res = walk_forward(R, sch, L, cad, cap, fl, BASE_COST_BPS, cache, groups_idx)
        if res is not None:
            series[(sch, L, cad, cap, fl)], turnovers[(sch, L, cad, cap, fl)] = res
        if (i + 1) % 20 == 0:
            print(f"   {i+1}/{len(configs)}  ({time.time()-t0:.0f}s)")

    # ---- pre-holdout ledger + point delta metrics (deployable configs only for selection)
    rows = []
    for key, seg in series.items():
        sch, L, cad, cap, fl = key
        pre = seg[seg.index <= DESIGN_FREEZE]
        if len(pre) < ANNUAL:
            continue
        d = delta_metrics(pre)
        # annual turnover (one-way) of the candidate path, pre-holdout
        rows.append({
            "scheme": sch, "L": L, "cadence": cad, "cap": cap, "floor": fl,
            "deployable": sch in DEPLOYABLE,
            "pre_d_calmar": d["d_calmar"], "pre_d_mdd": d["d_mdd"],
            "pre_d_cagr252": d["d_cagr252"], "pre_d_cagr_cal": d["d_cagr_cal"],
            "pre_d_sharpe": d["d_sharpe"],
            "pre_strat_calmar": d["strat"]["calmar"], "pre_ew_calmar": d["ew"]["calmar"],
            "pre_strat_mdd": d["strat"]["mdd_mag"], "pre_strat_cagr252": d["strat"]["cagr252"],
            "turnover": turnovers[key], "complexity": COMPLEXITY[sch],
        })
    ledger = pd.DataFrame(rows).sort_values("pre_d_calmar", ascending=False)
    ledger.to_csv(OUTDIR / "testing_ledger.csv", index=False, encoding="utf-8-sig")
    print(f"[ledger] {len(ledger)} configs -> testing_ledger.csv")

    # ---- N_eff over deployable configs' pre-holdout diff series
    dep_keys = [k for k in series if k[0] in DEPLOYABLE]
    pre_common = series[dep_keys[0]].loc[series[dep_keys[0]].index <= DESIGN_FREEZE].index
    for k in dep_keys:
        pre_common = pre_common.intersection(series[k].index)
    diff_mat = np.vstack([(series[k].loc[pre_common, "strategy_return"]
                           - series[k].loc[pre_common, "ew_return"]).values for k in dep_keys])
    neff = n_eff_participation(diff_mat)
    print(f"[N_eff] participation ratio over {len(dep_keys)} deployable configs = {neff:.2f}")

    # ---- candidate-level pre-holdout bootstrap for the filter (deployable only)
    dep_ledger = ledger[ledger["deployable"]].copy()
    print(f"[bootstrap] candidate filter on {len(dep_ledger)} deployable configs (n={boot_n}) ...")
    boot_cache = {}
    for _, r in dep_ledger.iterrows():
        key = (r["scheme"], r["L"], r["cadence"], r["cap"], r["floor"])
        pre = series[key][series[key].index <= DESIGN_FREEZE]
        bt = candidate_bootstrap(pre, [21], boot_n, SEED)   # filter uses 21d block
        boot_cache[key] = bt
        dep_ledger.loc[_, "pre_dcalmar_med_b"] = bt[21]["d_calmar_med"]
        dep_ledger.loc[_, "pre_dcagr_lb_b"] = bt[21]["d_cagr_lb"]
        dep_ledger.loc[_, "pre_p_dcalmar_gt0"] = bt[21]["p_dcalmar_gt0"]

    # ---- frozen deterministic selection rule (§4.0)
    elig = dep_ledger[(dep_ledger["pre_d_mdd"] < 0) & (dep_ledger["pre_dcagr_lb_b"] >= PASS_DCAGR_LB)].copy()
    print(f"[select] {len(elig)}/{len(dep_ledger)} configs pass filter (ΔMDD<0 & ΔCAGR LB>=-3pp)")
    # §4.0 tie-break: rank by pre-holdout median ΔCalmar, then LOW turnover, then LOW complexity
    sort_cols, sort_asc = ["pre_dcalmar_med_b", "turnover", "complexity"], [False, True, True]
    selection_trace = dep_ledger.sort_values(sort_cols, ascending=sort_asc)
    selection_trace.to_csv(OUTDIR / "selection_trace.csv", index=False, encoding="utf-8-sig")

    frozen = None
    frozen_key = None
    if len(elig):
        elig = elig.sort_values(sort_cols, ascending=sort_asc)
        frozen = elig.iloc[0]
        frozen_key = (frozen["scheme"], int(frozen["L"]), frozen["cadence"],
                      float(frozen["cap"]), float(frozen["floor"]))
    # ---- max-stat family-wise (pre-holdout) for the selection claim
    strat_mat = np.vstack([series[k].loc[pre_common, "strategy_return"].values for k in dep_keys])
    ew_mat = np.vstack([series[k].loc[pre_common, "ew_return"].values for k in dep_keys])
    maxstat = maxstat_family(strat_mat, ew_mat, len(pre_common), 21, boot_n, SEED)
    family_p = (float(np.nanmean(maxstat >= frozen["pre_dcalmar_med_b"]))
                if frozen is not None else None)

    # ---- paired_delta_metrics: PRE for all configs; HOLDOUT for the frozen candidate ONLY
    #      (R2-Blocker-2: emitting all-configs holdout deltas would re-open the holdout for the grid)
    pdm = []
    for key, seg in series.items():
        sch, L, cad, cap, fl = key
        periods = [("pre", seg.index <= DESIGN_FREEZE)]
        if frozen_key is not None and key == frozen_key:
            periods.append(("holdout", (seg.index >= HOLDOUT_START) & (seg.index <= HOLDOUT_END)))
        for period, sl in periods:
            sub = seg[sl]
            if len(sub) < 20:
                continue
            d = delta_metrics(sub)
            pdm.append({"scheme": sch, "L": L, "cadence": cad, "cap": cap, "floor": fl,
                        "period": period, **{k: v for k, v in d.items() if k not in ("strat", "ew")}})
    pd.DataFrame(pdm).to_csv(OUTDIR / "paired_delta_metrics.csv", index=False, encoding="utf-8-sig")

    # ---- holdout: ONLY the frozen candidate, three-state verdict
    verdict = {"status": "no_eligible_candidate"}
    if frozen is not None:
        key = (frozen["scheme"], int(frozen["L"]), frozen["cadence"], float(frozen["cap"]), float(frozen["floor"]))
        seg = series[key]
        hold = seg[(seg.index >= HOLDOUT_START) & (seg.index <= HOLDOUT_END)]
        point_d = delta_metrics(hold)
        boot = candidate_bootstrap(hold, BOOT_BLOCKS, boot_n, SEED + 1)
        state = three_state(point_d, boot)
        # final selection weights (computed at last pre-holdout rebal, for deployment display)
        fw = final_weights(R, key, cache, groups_idx)
        verdict = {
            "status": state,
            "frozen_config": {"scheme": key[0], "L": key[1], "cadence": key[2], "cap": key[3], "floor": key[4]},
            "selection_basis": "pre_holdout <= 2023-05-31; deterministic rule §4.0",
            "n_eff": neff, "n_configs_deployable": len(dep_keys),
            "maxstat_q95_dcalmar": float(np.nanpercentile(maxstat, 95)),
            "family_wise_p_preholdout": family_p,
            "turnover_annual_oneway": float(frozen["turnover"]),
            "pre_holdout": {k: float(frozen[k]) for k in
                            ["pre_d_calmar", "pre_d_mdd", "pre_d_cagr252", "pre_dcalmar_med_b",
                             "pre_dcagr_lb_b", "pre_p_dcalmar_gt0"]},
            "holdout_point": {"d_calmar": point_d["d_calmar"], "d_mdd": point_d["d_mdd"],
                              "d_cagr252": point_d["d_cagr252"], "d_cagr_cal": point_d["d_cagr_cal"],
                              "d_sharpe": point_d["d_sharpe"],
                              "strat": point_d["strat"], "ew": point_d["ew"]},
            "holdout_bootstrap": boot,
            "pass_thresholds": {"d_calmar>=": PASS_DCALMAR, "d_cagr_lb>=": PASS_DCAGR_LB,
                                "p_dcalmar_gt0>=": PASS_PROB, "d_mdd<": 0},
            "recommended_weights": fw,
            "expectation_note": "inconclusive/fail -> stay at EW (acceptable & expected, §0/§8)",
        }
    cfg_meta = {
        "seed": SEED, "boot_n": boot_n, "boot_blocks": BOOT_BLOCKS, "base_cost_bps": BASE_COST_BPS,
        "design_freeze": str(DESIGN_FREEZE.date()), "holdout": [str(HOLDOUT_START.date()), str(HOLDOUT_END.date())],
        "data_file": str(DATA), "data_hash": file_hash(DATA),
        "lookbacks": lookbacks, "cadences": cadences, "caps": caps, "floors": floors,
        "smoke": args.smoke,
    }
    out = {"meta": cfg_meta, "verdict": verdict}
    (OUTDIR / "frozen_candidate.json").write_text(json.dumps(out, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
    print(f"\n[VERDICT] {verdict.get('status')}  frozen={verdict.get('frozen_config')}")
    if frozen is not None:
        print(f"  holdout point: dCalmar={point_d['d_calmar']:+.3f} dMDD={point_d['d_mdd']:+.3f} "
              f"dCAGR252={point_d['d_cagr252']:+.3%}  (block21 P(dCalmar>0)={boot[21]['p_dcalmar_gt0']:.2f})")

    # ---- MLflow (mandatory §7.6; fallback run_manifest.json)
    manifest = {**cfg_meta, "verdict_status": verdict.get("status"),
                "frozen_config": verdict.get("frozen_config"), "n_eff": neff,
                "outputs": [str(OUTDIR / f) for f in
                            ["testing_ledger.csv", "paired_delta_metrics.csv",
                             "selection_trace.csv", "frozen_candidate.json"]]}
    (OUTDIR / "run_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
    if not args.no_mlflow:
        try:
            from src.alpha_research.mlflow_tracker import ExperimentTracker  # noqa
            log_mlflow(manifest, verdict)
            print("[mlflow] logged")
        except Exception as e:
            print(f"[mlflow] unavailable ({type(e).__name__}: {e}); wrote run_manifest.json — backfill before publish")

    print(f"\n[done] {time.time()-t0:.0f}s  outputs -> {OUTDIR}")


def final_weights(R, key, cache, groups_idx) -> dict:
    """Weights the frozen config would set at the LAST pre-holdout rebalance (deployment view)."""
    sch, L, cad, cap, fl = key
    pos_list = [p for p in rebal_positions(R, cad) if p >= L and R.index[p] <= DESIGN_FREEZE]
    stat = cache[(L, pos_list[-1])]
    w = weights_for(sch, stat, cap, fl, groups_idx)
    return {c: round(float(wi), 4) for c, wi in zip(R.columns, w)}


def log_mlflow(manifest, verdict):
    import mlflow
    mlflow.set_experiment("guorn20_reweight")
    with mlflow.start_run(run_name=f"wf_{manifest['design_freeze']}"):
        mlflow.log_params({k: str(v) for k, v in manifest.items() if k != "outputs"})
        if verdict.get("frozen_config"):
            mlflow.log_params({f"frozen_{k}": v for k, v in verdict["frozen_config"].items()})
        mlflow.log_metric("n_eff", manifest["n_eff"])
        mlflow.set_tag("verdict", verdict.get("status"))
        for f in manifest["outputs"]:
            if Path(f).exists():
                mlflow.log_artifact(f)


if __name__ == "__main__":
    main()
