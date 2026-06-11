"""Unified factor evaluation — the P0+P1 leak-safe correctness, significance, and frozen-methodology
core (spec: ``workspace/research/factor_expansion/unified_eval_standard.md``, Revisions 3–4).

Contents:
- **P0a correctness:** :func:`leak_safe_decay_ic_vector` (per-horizon ``is_end``-clipped decay — never
  the unguarded ``compute_ic_decay``), :func:`resolve_orientation` (non-circular direction: economic
  prior else train-window sign; NEVER the registry ``expected_direction``, which is observed from the
  heldout ICIR), :func:`classify_quantile_shape` (oriented sign-vector shape classifier).
- **P0b significance:** :func:`hac_mean_tstat` (Bartlett Newey-West HAC for overlapping labels),
  :func:`moving_block_bootstrap_mean_ci` (dependence-preserving robustness CI).
- **P0c deployable proxies:** :func:`one_way_turnover` (true equal-weight ``0.5·Σ|Δw|``),
  :func:`long_leg_excess_ir` (A-share long-leg excess vs benchmark, fail-closed, screening proxy).
- **P1 frozen methodology:** :class:`EvalMethodology` (hashed freeze incl. code commit + factor
  definition hashes), :func:`residual_ic_vs_controls` (winsor→cs-z→residualize vs the frozen
  ``STYLE_CONTROLS_V1``), :func:`neutralized_rank_icir`, :func:`index_forward_returns`.
- **P1c scale helpers:** :func:`build_decay_labels` / ``precomputed_labels`` and
  ``processed_controls`` fast paths (the labels and control transforms are factor-independent — build
  once, reuse across the full catalog).

All functions are IS-only and injectable (no Qlib needed for unit tests).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import hashlib
import json
from dataclasses import asdict, dataclass

from src.alpha_research.factor_eval.ic_analysis import compute_ic_series, compute_marginal_ic
from src.alpha_research.factor_eval.neutralization import neutralize_size_industry
from src.alpha_research.factor_library.operators import cs_zscore, winsorize
from src.alpha_research.factor_lifecycle.walk_forward_validation import (
    IsEndLeakageError,
    build_is_windowed_panel,
    load_open_trading_days,
)

DEFAULT_DECAY_HORIZONS = (5, 10, 20, 40)

# The FROZEN style-control set (Rev3 §B.7; all 14 verified present in the catalog). Residual IC vs
# this proves a factor is not merely size/value/momentum/quality/liquidity beta. FROZEN + hashed —
# choosing controls after seeing results would turn residual IC into another discovered metric.
STYLE_CONTROLS_V1 = (
    "size_ln_mcap", "size_ln_mcap_sq", "val_ep_ttm", "val_bp", "val_sp_ttm",
    "mom_return_20d", "mom_return_120d", "rev_return_5d", "qual_gross_profitability",
    "qual_accruals", "liq_log_dollar_vol", "liq_turnover_20d", "liq_amihud_20d", "risk_vol_20d",
)


def _f(v):
    if v is None:
        return None
    try:
        v = float(v)
        return None if v != v else v
    except (TypeError, ValueError):
        return None


def _to_dt_inst(s: pd.Series) -> pd.Series:
    """Normalize a MultiIndex Series to (datetime, instrument)."""
    return (s.swaplevel(0, 1) if s.index.names[0] != "datetime" else s).sort_index()


# ------------------------------------------------------- P1a: frozen methodology + style residual
@dataclass(frozen=True)
class EvalMethodology:
    """The FROZEN, HASHED methodology for a unified-eval run (Rev3 §B.6).

    The 185-factor dashboard is a discovery search surface → the whole methodology (style controls,
    benchmark policy, HAC/bootstrap settings, cost, reference-set membership) MUST be frozen and hashed
    BEFORE the full run so it can't be tuned after seeing results. ``methodology_hash`` is membership-
    (not order-) stable for the set-like fields. Stamp it on every produced evidence row.
    """
    is_start: str
    is_end: str
    # F1a (universe plan Draft-7 §3.2): the evaluation domain. Every metric in a run
    # is computed on THIS universe's masked cross-section; one methodology_hash per
    # domain. "univ_all" = the historical full-market behavior (backward compatible:
    # all pre-F1 evidence rows are semantically univ_all).
    universe_id: str = "univ_all"
    reference_set_stable: tuple = ()   # approved factor ids EXCLUDING provisionals — the DEFAULT base
    reference_set_current: tuple = ()  # approved incl. provisionals (shown, flagged)
    provisional_factors: tuple = ()    # the canary-contingent approvals (e.g. report_rc eps_diffusion)
    style_controls_v1: tuple = STYLE_CONTROLS_V1
    hac_lags: int = 40
    hac_lag_sensitivity: tuple = (20, 40, 60)
    bootstrap_block_len: int = 20
    bootstrap_n_boot: int = 2000
    bootstrap_ci: float = 0.95
    bootstrap_seed: int = 42
    cost_bps_per_turnover: float = 25.0
    include_initial_cost: bool = True
    rebalance_days: int = 20
    horizon: int = 20
    decay_horizons: tuple = DEFAULT_DECAY_HORIZONS
    # top_q is the LONG-LEG deployable-proxy book size (top 20% ≈ a realistic holding
    # set even on index domains) — deliberately NOT tied to n_quantiles: the 10-group
    # profile is the descriptive/shape standard (2026-06-11 unification, matches
    # factor_lifecycle + the CICC protocol), the proxy book is an implementability metric.
    top_q: float = 0.2
    n_quantiles: int = 10
    winsor_limits: tuple = (0.01, 0.99)
    trading_days: int = 252
    benchmarks: tuple = ("000300_SH", "000905_SH")  # show BOTH — no per-factor selection → no snooping
    benchmark_policy: str = "show_both_no_selection"
    benchmark_close_field: str = "$close"
    benchmark_calendar_policy: str = "exact_trade_calendar_capped_to_is_end"
    mt_t_bar: float = 3.0  # applied as |hac_t| ≥ bar (direction-aware; inverse factors have hac_t<0)
    # orientation (GPT R3: train-fold sign, shape judged on heldout — NOT the observed registry field)
    orientation_policy: str = "economic_prior_else_train_heldout"
    orientation_train_frac: float = 0.60
    orientation_min_train_t: float = 1.0
    shape_eval_window: str = "heldout_after_orientation"
    # per-date sample minimums (each a distinct, hashed knob — no hidden defaults)
    ic_min_obs: int = 30
    quantile_min_obs: int = 50
    residual_min_obs: int = 30
    neutralize_min_obs: int = 50
    neutralized_ic_min_obs: int = 30
    turnover_min_names: int = 5
    long_leg_min_names: int = 5
    # coverage peer-grouping thresholds (were hardcoded in the driver — F-audit 2026-06-10)
    coverage_full_min: float = 0.90
    coverage_broad_min: float = 0.50
    # residual / neutralization construction
    residual_transform: str = "winsorize_then_cs_zscore"
    residual_metric: str = "rank_ic"
    neutralization_mcap_field: str = "$total_mv"
    neutralization_industry_source: str = "PIT_SW2021_L1"
    # provenance — distinct implementations with identical field values must NOT share a hash
    code_commit: str = ""
    reference_set_definition_hashes: tuple = ()   # ((factor_id, def_hash), …), driver fills
    style_control_definition_hashes: tuple = ()

    @property
    def methodology_hash(self) -> str:
        d = asdict(self)
        for k in ("reference_set_stable", "reference_set_current", "provisional_factors",
                  "style_controls_v1", "reference_set_definition_hashes",
                  "style_control_definition_hashes"):
            d[k] = sorted(d[k])  # membership, not order, defines identity
        return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()[:16]


def preprocess_for_residual(factors_dict: dict, names, *, winsor=(0.01, 0.99)) -> dict:
    """Winsorize→cs-z-score a set of factor series ONCE (the residual-pipeline input transform).

    The transform is per-factor and date-local — it does NOT depend on which candidate is being
    residualized — so for a full-catalog run compute it once for every involved name and pass the
    result to :func:`residual_ic_vs_controls` via ``processed_controls`` (the per-candidate
    re-processing of 14 controls × 3 reference sets × N factors was the dominant cost at scale).
    """
    return {nm: cs_zscore(winsorize(_to_dt_inst(factors_dict[nm]), winsor[0], winsor[1]))
            for nm in names}


def residual_ic_vs_controls(candidate_name: str, factors_dict: dict, forward_return: pd.Series, *,
                            control_names=STYLE_CONTROLS_V1, winsor=(0.01, 0.99), min_obs: int = 30,
                            hac_lags: int = 40, processed_controls: dict | None = None) -> dict:
    """Residual IC of a candidate after orthogonalizing against the FROZEN style controls.

    The Rev3 §B.7 pipeline (do NOT call ``compute_marginal_ic`` raw): per date winsorize → cross-
    sectional z-score the candidate AND each control, then residualize the candidate on the controls
    and correlate the residual with the forward return. Reports ``raw_control_coverage`` (fraction of
    the candidate's non-null cells where ALL controls are present) AND ``effective_residual_coverage``
    (label-aligned — the cells the residual IC is actually evaluated on), plus the HAC t of the
    residual RankIC (overlap-aware). ``processed_controls`` may carry the output of
    :func:`preprocess_for_residual` (covering candidate + controls) to skip re-transforming at scale.
    """
    if processed_controls is not None:
        proc = {nm: (processed_controls[nm] if nm in processed_controls
                     else cs_zscore(winsorize(_to_dt_inst(factors_dict[nm]), winsor[0], winsor[1])))
                for nm in [candidate_name, *control_names]}
    else:
        proc = {nm: cs_zscore(winsorize(_to_dt_inst(factors_dict[nm]), winsor[0], winsor[1]))
                for nm in [candidate_name, *control_names]}
    fwd = _to_dt_inst(forward_return)
    series, summ = compute_marginal_ic(proc, fwd, base_factors=list(control_names),
                                       candidate=candidate_name, min_obs=min_obs)
    rank_ic = (series["RankIC"] if "RankIC" in series.columns else series.iloc[:, -1]).dropna()
    hac = hac_mean_tstat(rank_ic, lags=hac_lags)
    cand = _to_dt_inst(factors_dict[candidate_name]).dropna()
    ctrl = pd.DataFrame({nm: _to_dt_inst(factors_dict[nm]) for nm in control_names}).reindex(cand.index)
    raw_control_coverage = float(ctrl.notna().all(axis=1).mean()) if len(cand) else float("nan")
    # effective coverage: candidate ∩ label ∩ all-controls, over candidate ∩ label (the cells the
    # residual IC is actually evaluated on — listwise deletion + the label's trailing-horizon drop can
    # make this materially smaller than raw_control_coverage).
    lab_idx = fwd.dropna().index
    cl = cand.index.intersection(lab_idx)
    effective_residual_coverage = (float(ctrl.reindex(cl).notna().all(axis=1).mean())
                                   if len(cl) else float("nan"))
    return {
        "residual_mean_rank_ic": _f(summ.get("mean_rank_ic")),
        "residual_rank_icir": _f(summ.get("rank_icir")),
        "residual_hac_t": hac.get("hac_t"),
        "raw_control_coverage": raw_control_coverage,
        "effective_residual_coverage": effective_residual_coverage,
        "n_dates": int(len(rank_ic)),
        "n_controls": len(control_names),
    }


# ------------------------------------------------------- P1b-data: neutralized IC + index fwd returns
def neutralized_rank_icir(factor: pd.Series, label: pd.Series, market_cap: pd.Series,
                          industry: pd.Series, *, min_obs: int = 30, neutralize_min_obs: int = 50,
                          hac_lags: int = 40) -> dict:
    """Size+industry-neutralized RankIC / ICIR — separates genuine alpha from style beta.

    Per-date OLS-residualize the factor on log market cap + industry dummies
    (``neutralize_size_industry``), then RankIC vs the forward return + an overlap-aware HAC t.
    ``neutralize_min_obs`` is the per-date min for the NEUTRALIZATION regression (explicitly passed —
    NOT the neutralizer's hidden default 50); ``min_obs`` is the later IC min. Both are distinct,
    hashed knobs (GPT round-3: do not hide the difference).
    """
    neut = neutralize_size_industry(_to_dt_inst(factor), _to_dt_inst(market_cap),
                                    _to_dt_inst(industry), min_obs=neutralize_min_obs)
    ic = compute_ic_series(_to_dt_inst(neut), _to_dt_inst(label), min_obs=min_obs)
    rank_ic = (ic["RankIC"] if "RankIC" in ic.columns else ic.iloc[:, -1]).dropna()
    hac = hac_mean_tstat(rank_ic, lags=hac_lags)
    return {"neutralized_mean_rank_ic": _f(rank_ic.mean()), "neutralized_rank_icir": _rank_icir(rank_ic),
            "neutralized_hac_t": hac.get("hac_t"), "n_dates": int(len(rank_ic))}


def index_forward_returns(index_close: pd.Series, *, horizon: int, is_end, trade_cal=None) -> pd.Series:
    """Forward return of a benchmark index over ``horizon`` trading days, by the EXACT calendar.

    ``index_close`` is a datetime-indexed close series (one index), which MUST be capped at ``is_end``
    (asserted — an uncapped series could realize a post-``is_end`` benchmark return = leak). For date
    ``t`` the return uses ``close[open_days[pos(t)+horizon]] / close[t] − 1`` (same row-based
    realization as the factor label); the trailing ``horizon`` dates with no realized close are dropped.
    """
    s = index_close.dropna().sort_index()
    if len(s) and pd.Timestamp(s.index.max()) > pd.Timestamp(is_end):
        raise IsEndLeakageError(
            f"index_close max date {pd.Timestamp(s.index.max()).date()} > is_end "
            f"{pd.Timestamp(is_end).date()} — cap the benchmark close at is_end (leak guard)")
    open_days = load_open_trading_days(trade_cal)
    dates = pd.DatetimeIndex(sorted(s.index))
    pos = open_days.searchsorted(dates, side="left")
    out = {}
    for d, p in zip(dates, pos):
        tgt = p + int(horizon)
        if tgt < len(open_days):
            rd = open_days[tgt]
            if rd in s.index:
                out[pd.Timestamp(d)] = float(s.loc[rd] / s.loc[d] - 1.0)
    return pd.Series(out, name="index_fwd_return")


# ------------------------------------------------------- P0b: overlap-adjusted significance
def hac_mean_tstat(series, *, lags: int = 40) -> dict:
    """Newey-West (Bartlett-kernel) HAC t-stat of the MEAN of a serially-correlated series.

    The headline significance for overlapping ``horizon``-day labels: daily-sampled 20d IC overlaps
    19/20 → the IID t-stat is inflated ~√horizon. The Bartlett kernel guarantees a non-negative
    long-run variance ``Ω̂ = γ₀ + 2·Σ_{l=1}^{L}(1 − l/(L+1))·γ_l``; ``Var(mean) = Ω̂/T``. Pass
    ``lags ≥ horizon`` (default 40; the driver should report sensitivity at 20/40/60). This is the
    PRIMARY significance statistic — NOT ``statistical_tests.bootstrap_sharpe_ci`` (IID Sharpe).
    """
    if int(lags) < 0:
        raise ValueError(f"lags must be non-negative, got {lags}")
    x = pd.Series(series, dtype=float).dropna().to_numpy()
    T = int(len(x))
    if T < 3:
        return {"mean": None, "hac_se": None, "hac_t": None, "hac_p": None, "lags": 0, "n": T,
                "small_sample_warning": True}
    mean = float(x.mean())
    e = x - mean
    L = min(int(lags), T - 1)
    # The HAC t-stat / normal p are ASYMPTOTIC — flag thin samples (sub-coverage factors drop dates).
    small_sample = bool(T < max(100, 4 * L))
    omega = float(e @ e) / T  # γ₀
    for l in range(1, L + 1):
        w = 1.0 - l / (L + 1)
        omega += 2.0 * w * float(e[l:] @ e[:-l]) / T
    var_mean = omega / T
    if var_mean <= 0:
        return {"mean": mean, "hac_se": None, "hac_t": None, "hac_p": None, "lags": L, "n": T,
                "small_sample_warning": small_sample}
    se = float(np.sqrt(var_mean))
    t = mean / se
    from math import erfc, sqrt
    p = float(erfc(abs(t) / sqrt(2.0)))  # two-sided normal (asymptotic)
    return {"mean": mean, "hac_se": se, "hac_t": float(t), "hac_p": p, "lags": L, "n": T,
            "small_sample_warning": small_sample}


def moving_block_bootstrap_mean_ci(series, *, block_len: int = 20, n_boot: int = 2000,
                                   ci: float = 0.95, seed: int = 42) -> dict:
    """Moving-block bootstrap CI for the MEAN (robustness check alongside HAC).

    Resamples contiguous blocks of length ``block_len`` (≈ the label horizon) on the DATE-LEVEL
    series — preserving the overlap dependence structure — NOT IID values. Deterministic given
    ``seed``.
    """
    x = pd.Series(series, dtype=float).dropna().to_numpy()
    T = int(len(x))
    if T < block_len or T < 3:
        return {"mean": float(x.mean()) if T else None, "ci_low": None, "ci_high": None, "n": T}
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(T / block_len))
    starts_hi = T - block_len + 1
    means = np.empty(n_boot)
    for b in range(n_boot):
        starts = rng.integers(0, starts_hi, size=n_blocks)
        sample = np.concatenate([x[s:s + block_len] for s in starts])[:T]
        means[b] = sample.mean()
    alpha = (1.0 - ci) / 2.0
    return {"mean": float(x.mean()), "ci_low": float(np.quantile(means, alpha)),
            "ci_high": float(np.quantile(means, 1.0 - alpha)), "block_len": block_len, "n": T}


# ------------------------------------------------------- P0c: turnover + long-leg excess
def _one_way_weight_turnover(cur: set, prev: set) -> float:
    """TRUE equal-weight one-way portfolio turnover `0.5·Σ_{i∈union}|w_cur_i − w_prev_i|` with equal
    weights `1/|bucket|`. Differs from membership churn `|Δ|/(|A|+|prev|)` when bucket sizes drift
    (e.g. prev 100 ⊂ cur 200 → weight turnover 0.5, churn 0.333). This is the cost-relevant number.
    """
    if not cur and not prev:
        return float("nan")
    wc = 1.0 / len(cur) if cur else 0.0
    wp = 1.0 / len(prev) if prev else 0.0
    s = 0.0
    for i in cur | prev:
        s += abs((wc if i in cur else 0.0) - (wp if i in prev else 0.0))
    return 0.5 * s


def one_way_turnover(factor: pd.Series, *, rebalance_days: int = 20, rebalance_dates=None,
                     top_q: float = 0.2, trading_days: int = 252, min_names: int = 5) -> dict:
    """Annualized TRUE equal-weight one-way portfolio turnover of the top bucket (the long book).

    Per rebalance, `turnover = 0.5·Σ|Δw|` (equal weights) — the cost-relevant metric, NOT membership
    churn (they differ when bucket sizes drift via ties/coverage). Bottom bucket reported separately.
    Plus instability diagnostics: top/bottom boundary `tie_rate` (fraction exactly on the threshold)
    and bucket size fractions. Returns both the candidate and the used (post-`min_names`) rebalance
    counts. Pass a FIXED ``rebalance_dates`` schedule (a trading-calendar grid) for cross-factor
    comparability — else each factor uses its own ``dates[::rebalance_days]`` (not comparable; GPT R3).

    Annualization caveat: ``× trading_days/rebalance_days`` assumes every scheduled rebalance executes;
    if a factor skips scheduled dates (cross-section < ``min_names``), per-executed-rebalance churn is
    annualized at the SCHEDULE frequency — compare ``n_rebalances_used`` vs ``n_rebalance_candidates``
    before trusting the annualized figure for gap-skipping factors.
    """
    f = _to_dt_inst(factor).dropna()
    df = f.reset_index()
    df.columns = ["datetime", "instrument", "val"]
    by_date = {pd.Timestamp(d): g for d, g in df.groupby("datetime")}  # one pass, not a scan per date
    dates = sorted(by_date)
    rebal = [pd.Timestamp(d) for d in rebalance_dates] if rebalance_dates is not None else dates[::rebalance_days]
    top_prev = bot_prev = None
    top_t, bot_t, top_tie, bot_tie, top_frac, bot_frac = [], [], [], [], [], []
    used = 0
    for d in rebal:
        g = by_date.get(pd.Timestamp(d))
        n = 0 if g is None else len(g)
        if n < min_names:
            continue
        used += 1
        hi, lo = g["val"].quantile(1 - top_q), g["val"].quantile(top_q)
        top = set(g.loc[g["val"] >= hi, "instrument"])
        bot = set(g.loc[g["val"] <= lo, "instrument"])
        top_tie.append(float((g["val"] == hi).sum()) / n)
        bot_tie.append(float((g["val"] == lo).sum()) / n)
        top_frac.append(len(top) / n)
        bot_frac.append(len(bot) / n)
        if top_prev is not None:
            top_t.append(_one_way_weight_turnover(top, top_prev))
        if bot_prev is not None:
            bot_t.append(_one_way_weight_turnover(bot, bot_prev))
        top_prev, bot_prev = top, bot
    ann = trading_days / rebalance_days

    def _m(a):
        a = [v for v in a if v == v]
        return float(np.mean(a)) if a else float("nan")

    return {
        "turnover_ann": _m(top_t) * ann if top_t else float("nan"),
        "bottom_turnover_ann": _m(bot_t) * ann if bot_t else float("nan"),
        "tie_rate": _m(top_tie), "bottom_tie_rate": _m(bot_tie),
        "top_bucket_frac": _m(top_frac), "bottom_bucket_frac": _m(bot_frac),
        "n_rebalance_candidates": len(rebal), "n_rebalances_used": used,
    }


def long_leg_excess_ir(factor: pd.Series, label: pd.Series, benchmark_fwd_return: pd.Series, *,
                       top_q: float = 0.2, cost_bps_per_turnover: float = 25.0,
                       rebalance_days: int = 20, rebalance_dates=None, horizon: int | None = None,
                       trading_days: int = 252, min_names: int = 5,
                       include_initial_cost: bool = True) -> dict:
    """A-share deployable-PROXY (IS): equal-weight top-quantile LONG-ONLY excess vs benchmark, net cost.

    This is a SCREENING PROXY, NOT a backtest IR — it ignores limit-up/down, suspensions, T+1, ST/new-
    listing filters, liquidity/participation caps, partial fills, real order price, nonlinear slippage,
    and top-K (vs top-quantile) construction; names with a missing forward label are dropped (which can
    hide suspension/delist friction). Use the event-driven engine for a deployable figure.

    ``factor`` MUST already be oriented (top bucket = intended-best; see :func:`resolve_orientation` —
    refuse to call this when ``orientation_valid`` is False). ``label`` = per-name forward return at the
    rebalance ``horizon``; ``benchmark_fwd_return`` = the index forward return over the SAME ``horizon``,
    indexed by date (FAIL-CLOSED: a missing benchmark date raises, never silently advances the book).
    ``horizon`` defaults to ``rebalance_days`` (non-overlapping); the IR annualizes by √(252/rebal).
    Long-side cost only (no borrow fee): ``one_way_turnover × cost_bps_per_turnover`` (default 25bps ≈
    realistic_china long-side round-trip = sell stamp 5 + 2×commission 2.5 + slippage 10 + transfer 1).
    """
    if horizon is not None and int(horizon) != int(rebalance_days):
        raise ValueError(f"horizon ({horizon}) must equal rebalance_days ({rebalance_days}) for "
                         "non-overlapping IR annualization; pass aligned values or omit horizon")
    bench_idx = set(pd.Timestamp(d) for d in benchmark_fwd_return.index)
    f, lab = _to_dt_inst(factor), _to_dt_inst(label)
    joined = pd.DataFrame({"f": f, "r": lab}).dropna()
    if joined.empty:
        return {"long_leg_excess_ann": None, "long_leg_excess_ir_proxy_is": None, "n_rebalances": 0}
    dates = sorted(joined.index.get_level_values("datetime").unique())
    date_set = set(pd.Timestamp(d) for d in dates)
    rebal = [pd.Timestamp(d) for d in rebalance_dates] if rebalance_dates is not None else dates[::rebalance_days]
    excess, prev_top = [], None
    for d in rebal:
        dt = pd.Timestamp(d)
        if dt not in date_set:  # a fixed external schedule may name dates absent from this factor
            continue
        g = joined.xs(dt, level="datetime")
        if len(g) < min_names:
            continue
        if dt not in bench_idx or pd.isna(benchmark_fwd_return.loc[dt]):
            raise ValueError(f"missing benchmark forward return at {dt.date()} (fail-closed; a "
                             "silently-dropped benchmark would corrupt the next row's turnover)")
        top = g[g["f"] >= g["f"].quantile(1 - top_q)]
        cur = set(top.index)
        turn = _one_way_weight_turnover(cur, prev_top) if prev_top is not None else (
            1.0 if include_initial_cost else 0.0)
        excess.append(float(top["r"].mean()) - float(benchmark_fwd_return.loc[dt])
                      - turn * cost_bps_per_turnover / 1e4)
        prev_top = cur
    ex = pd.Series(excess).dropna()
    if len(ex) < 2:
        return {"long_leg_excess_ann": None, "long_leg_excess_ir_proxy_is": None,
                "n_rebalances": int(len(ex))}
    ann = trading_days / rebalance_days
    std = float(ex.std())
    ir = float(ex.mean() / std * np.sqrt(ann)) if std > 0 else float("nan")
    return {"long_leg_excess_ann": float(ex.mean() * ann), "long_leg_excess_ir_proxy_is": ir,
            "n_rebalances": int(len(ex))}


# --------------------------------------------------------------------------- shape classifier
def classify_quantile_shape(quantile_returns) -> dict:
    """Classify the shape of a quantile-return curve via the adjacent-bucket difference SIGN VECTOR.

    The curve MUST already be oriented (see :func:`resolve_orientation`) so the intended-best
    quantile is the LAST bucket. Returns ``mono_shape`` ∈ {monotonic_up, monotonic_down,
    top_reversal, bottom_reversal, U_shape, inverted_U, irregular}, the ``mono_step_signs`` string,
    and ``mono_frac_dominant`` (= max(#up,#down)/n_steps — a DIAGNOSTIC, not a headline). Fewer than
    3 buckets (discrete/tie-heavy factor) → ``None`` + ``mono_reason='insufficient_quantiles(n=…)'``.
    """
    ar = [float(x) for x in quantile_returns if x == x]  # drop NaN
    if len(ar) < 3:
        return {"mono_shape": None, "mono_step_signs": None, "mono_frac_dominant": None,
                "monotonic_spearman": None, "mono_reason": f"insufficient_quantiles(n={len(ar)})"}
    d = np.diff(np.asarray(ar, dtype=float))
    signs = "".join("+" if x > 1e-12 else ("-" if x < -1e-12 else "0") for x in d)
    n = len(signs)
    pos, neg = signs.count("+"), signs.count("-")
    if pos == n:
        shape = "monotonic_up"
    elif neg == n:
        shape = "monotonic_down"
    elif signs[:-1].count("+") == n - 1 and signs[-1] == "-":
        shape = "top_reversal"
    elif signs[0] == "-" and signs[1:].count("+") == n - 1:
        shape = "bottom_reversal"
    elif signs == "-" * neg + "+" * pos:
        shape = "U_shape"
    elif signs == "+" * pos + "-" * neg:
        shape = "inverted_U"
    else:
        shape = "irregular"
    from scipy import stats
    sp = stats.spearmanr(range(len(ar)), ar)[0]
    return {"mono_shape": shape, "mono_step_signs": signs,
            "mono_frac_dominant": round(max(pos, neg) / n, 4),
            "monotonic_spearman": None if sp != sp else round(float(sp), 4), "mono_reason": None}


# --------------------------------------------------------------------------- non-circular direction
def resolve_orientation(ic_by_date: pd.Series, *, train_dates=None, economic_prior=None,
                        min_train_t: float = 1.0) -> dict:
    """Resolve a NON-CIRCULAR orientation sign for the monotonicity shape.

    NEVER uses the registry ``expected_direction`` (observed from heldout ICIR → circular).
    Priority: (1) ``economic_prior`` (predeclared ±1) → ``'economic_prior'`` (always valid);
    (2) sign of mean IC over ``train_dates`` ONLY, but ONLY if the train-window signal is strong
    enough (HAC |t| ≥ ``min_train_t``) → ``'train_fold'``; (3) weak/zero/empty → ``'undetermined'``.

    Returns ``orientation_valid`` — downstream consumers (e.g. :func:`long_leg_excess_ir`, the shape
    pass/fail label) MUST refuse a "top bucket is intended-best" claim when it is ``False`` (the sign
    defaults to +1 only so the raw bucket vector can still be displayed). Train-date matching is
    type-normalized to ``Timestamp`` so a string/Timestamp mismatch can't silently yield no match.
    """
    if economic_prior in (1, -1, 1.0, -1.0):
        return {"sign": float(economic_prior), "direction_source": "economic_prior",
                "orientation_valid": True}
    if train_dates is not None and ic_by_date is not None and len(ic_by_date):
        ic = ic_by_date.copy()
        ic.index = pd.DatetimeIndex([pd.Timestamp(d) for d in ic.index])
        train_set = {pd.Timestamp(d) for d in train_dates}
        train_ic = ic[ic.index.isin(train_set)].dropna()
        if len(train_ic) >= 3:
            m = float(train_ic.mean())
            t = hac_mean_tstat(train_ic, lags=min(40, len(train_ic) - 1)).get("hac_t")
            # weak-signal guard: a tiny noisy train mean must NOT manufacture false orientation
            # precision. When HAC t is undefined (zero-variance / constant series) the signal is
            # strong iff the constant mean is non-trivially non-zero.
            strong = (abs(m) > 1e-9) if t is None else (abs(t) >= min_train_t)
            if m != 0 and strong:
                return {"sign": 1.0 if m > 0 else -1.0, "direction_source": "train_fold",
                        "orientation_valid": True, "train_hac_t": None if t is None else float(t)}
    return {"sign": 1.0, "direction_source": "undetermined", "orientation_valid": False}


# --------------------------------------------------------------------------- leak-safe decay
def _rank_icir(rank_ic: pd.Series) -> float:
    r = rank_ic.dropna()
    return float(r.mean() / r.std()) if len(r) > 1 and r.std() > 0 else float("nan")


def build_decay_labels(index_template: pd.MultiIndex, adj_close: pd.Series, *, is_end,
                       horizons=DEFAULT_DECAY_HORIZONS, trade_cal=None) -> dict:
    """Build the per-horizon ``is_end``-clipped forward-return labels ONCE for a whole panel.

    The decay label depends only on (index, adj_close, calendar, horizon) — NOT on the factor values —
    so a full-catalog run must not rebuild it per factor (185×4 panel builds was the dominant decay
    cost). Each horizon's label goes through :func:`build_is_windowed_panel` (a constant dummy column
    on ``index_template``), inheriting every ``is_end`` belt; rows whose horizon-``h`` realization
    exceeds ``is_end`` are absent from that label. Returns ``{h: {"label": Series(dt,inst),
    "max_realization": str}}`` for :func:`leak_safe_decay_ic_vector`'s ``precomputed_labels``.
    """
    dummy = pd.DataFrame({"__d__": 1.0}, index=index_template)
    out: dict[int, dict] = {}
    for h in horizons:
        panel = build_is_windowed_panel(dummy, adj_close, is_end=is_end, horizon=int(h),
                                        trade_cal=trade_cal)
        lab = panel.label
        lab = (lab.swaplevel(0, 1) if lab.index.names[0] != "datetime" else lab).sort_index()
        out[int(h)] = {"label": lab,
                       "max_realization": str(pd.Timestamp(panel.max_label_realization_date).date())}
    return out


def leak_safe_decay_ic_vector(
    factor: pd.Series,
    adj_close: pd.Series = None,
    *,
    is_end,
    horizons=DEFAULT_DECAY_HORIZONS,
    trade_cal=None,
    min_obs: int = 30,
    precomputed_labels: dict | None = None,
) -> dict:
    """Leak-safe IC-decay vector: for each horizon, an INDEPENDENTLY ``is_end``-clipped panel.

    Both ``factor`` and ``adj_close`` MUST already be capped at ``is_end`` (asserted by
    :func:`build_is_windowed_panel`). For each ``h`` we build a fresh ``IsWindowedPanel`` — which
    drops every factor date whose horizon-``h`` realization exceeds ``is_end`` — and compute the
    cross-sectional RankIC vs that panel's label. Returns per-horizon
    ``{mean_rank_ic, rank_icir, n_dates, max_realization}`` plus ``half_life_vs_shortest``.

    ``precomputed_labels`` (from :func:`build_decay_labels`, built on the SAME index/adj_close/is_end)
    skips the per-factor panel rebuilds — required at full-catalog scale. The IC join restricts the
    factor to the label's surviving cells, so the clipping is inherited unchanged.

    This is the SANCTIONED decay path — never call ``compute_ic_decay(price.shift(-h))`` (no guard).
    """
    factor = factor if isinstance(factor, pd.Series) else pd.Series(factor)
    f_dt = (factor.swaplevel(0, 1) if factor.index.names[0] != "datetime" else factor).sort_index()
    vec: dict[int, dict] = {}
    for h in horizons:
        if precomputed_labels is not None:
            entry = precomputed_labels[int(h)]
            lab, max_real = entry["label"], entry["max_realization"]
            fser = f_dt
        else:
            if adj_close is None:
                raise ValueError("adj_close is required when precomputed_labels is not given")
            panel = build_is_windowed_panel(factor.to_frame("__f__"), adj_close, is_end=is_end,
                                            horizon=int(h), trade_cal=trade_cal)
            fser = panel.factor_panel["__f__"]
            fser = (fser.swaplevel(0, 1) if fser.index.names[0] != "datetime" else fser).sort_index()
            lab = panel.label
            lab = (lab.swaplevel(0, 1) if lab.index.names[0] != "datetime" else lab).sort_index()
            max_real = str(pd.Timestamp(panel.max_label_realization_date).date())
        ic = compute_ic_series(fser, lab, min_obs=min_obs)
        rank_ic = ic["RankIC"] if "RankIC" in ic.columns else ic.iloc[:, -1]
        vec[int(h)] = {
            "mean_rank_ic": float(rank_ic.dropna().mean()) if len(rank_ic.dropna()) else float("nan"),
            "rank_icir": _rank_icir(rank_ic),
            "n_dates": int(rank_ic.dropna().shape[0]),
            "max_realization": max_real,
        }
    # half-life vs the SHORTEST horizon's |rank_icir| (NOT peak-relative — peak selection is hidden
    # horizon mining; the shortest horizon is the freshest signal, a fixed non-selected reference).
    icirs = {h: abs(v["rank_icir"]) for h, v in vec.items() if v["rank_icir"] == v["rank_icir"]}
    half_life = None
    if icirs:
        h0 = min(icirs)
        base = icirs[h0]
        if base > 0:
            for h in sorted(h for h in icirs if h > h0):
                if icirs[h] <= 0.5 * base:
                    half_life = h
                    break
    return {"horizons": list(horizons), "vector": vec, "half_life_vs_shortest": half_life,
            "note": "leak-safe: each horizon independently is_end-clipped via build_is_windowed_panel; "
                    "half_life is vs the shortest horizon (not peak-relative)"}
