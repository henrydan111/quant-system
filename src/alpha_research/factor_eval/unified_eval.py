"""Unified factor evaluation — leak-safe composed metrics (P0a correctness core).

The 2026-06-10 GPT 5.5 Pro code-grounded review (spec:
``workspace/research/factor_expansion/unified_eval_standard.md`` Revision 3) flagged two
correctness-critical gaps where existing primitives do NOT, by themselves, give a leak-safe
composed metric. This module closes the two highest-priority ones plus the shared shape
classifier:

1. :func:`leak_safe_decay_ic_vector` — per-horizon ``is_end``-clipped decay. NEVER feed a single
   price series to :func:`factor_eval.decay_analysis.compute_ic_decay` (it computes
   ``price(t+h)/price(t)-1`` with NO ``is_end`` guard → a 40d label realizes past ``is_end`` → leak).
   We rebuild a validated ``IsWindowedPanel`` per horizon (each independently drops factor dates whose
   horizon-h realization exceeds ``is_end``) and compute IC against that panel's label.
2. :func:`resolve_orientation` — non-circular direction for the monotonicity shape. NEVER use the
   registry ``expected_direction`` (it is OBSERVED from the heldout ICIR via
   ``walk_forward_validation._expected_direction`` → circular). Use a predeclared economic prior where
   given, else a train-window-only IC sign; emit a ``direction_source``.
3. :func:`classify_quantile_shape` — the oriented adjacent-bucket sign-vector shape classifier
   (promoted from the probe script to a tested module fn), with the ``insufficient_quantiles`` guard.

All functions are IS-only and injectable (no Qlib needed for unit tests).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.alpha_research.factor_eval.ic_analysis import compute_ic_series
from src.alpha_research.factor_lifecycle.walk_forward_validation import build_is_windowed_panel

DEFAULT_DECAY_HORIZONS = (5, 10, 20, 40)


def _to_dt_inst(s: pd.Series) -> pd.Series:
    """Normalize a MultiIndex Series to (datetime, instrument)."""
    return (s.swaplevel(0, 1) if s.index.names[0] != "datetime" else s).sort_index()


# ------------------------------------------------------- P0b: overlap-adjusted significance
def hac_mean_tstat(series, *, lags: int = 40) -> dict:
    """Newey-West (Bartlett-kernel) HAC t-stat of the MEAN of a serially-correlated series.

    The headline significance for overlapping ``horizon``-day labels: daily-sampled 20d IC overlaps
    19/20 → the IID t-stat is inflated ~√horizon. The Bartlett kernel guarantees a non-negative
    long-run variance ``Ω̂ = γ₀ + 2·Σ_{l=1}^{L}(1 − l/(L+1))·γ_l``; ``Var(mean) = Ω̂/T``. Pass
    ``lags ≥ horizon`` (default 40; the driver should report sensitivity at 20/40/60). This is the
    PRIMARY significance statistic — NOT ``statistical_tests.bootstrap_sharpe_ci`` (IID Sharpe).
    """
    x = pd.Series(series, dtype=float).dropna().to_numpy()
    T = int(len(x))
    if T < 3:
        return {"mean": None, "hac_se": None, "hac_t": None, "hac_p": None, "lags": 0, "n": T}
    mean = float(x.mean())
    e = x - mean
    L = min(int(lags), T - 1)
    omega = float(e @ e) / T  # γ₀
    for l in range(1, L + 1):
        w = 1.0 - l / (L + 1)
        omega += 2.0 * w * float(e[l:] @ e[:-l]) / T
    var_mean = omega / T
    if var_mean <= 0:
        return {"mean": mean, "hac_se": None, "hac_t": None, "hac_p": None, "lags": L, "n": T}
    se = float(np.sqrt(var_mean))
    t = mean / se
    from math import erfc, sqrt
    p = float(erfc(abs(t) / sqrt(2.0)))  # two-sided normal
    return {"mean": mean, "hac_se": se, "hac_t": float(t), "hac_p": p, "lags": L, "n": T}


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
def one_way_turnover(factor: pd.Series, *, rebalance_days: int = 20, top_q: float = 0.2,
                     trading_days: int = 252, min_names: int = 5) -> dict:
    """True one-way membership turnover `|A_t Δ A_{t-rebal}|/(|A_t|+|A_prev|) × (252/rebal)`.

    Top-bucket (the long book) is the headline; bottom-bucket reported separately; plus the
    boundary `tie_rate` (fraction of the cross-section sitting exactly on the top threshold —
    inflated for discrete/tie-heavy factors, which makes membership churn unstable).
    """
    f = _to_dt_inst(factor).dropna()
    df = f.reset_index()
    df.columns = ["datetime", "instrument", "val"]
    dates = sorted(df["datetime"].unique())
    rebal = dates[::rebalance_days]
    top_prev = bot_prev = None
    top_churn, bot_churn, tie_rates = [], [], []
    for d in rebal:
        g = df[df["datetime"] == d]
        n = len(g)
        if n < min_names:
            continue
        hi, lo = g["val"].quantile(1 - top_q), g["val"].quantile(top_q)
        top = set(g.loc[g["val"] >= hi, "instrument"])
        bot = set(g.loc[g["val"] <= lo, "instrument"])
        tie_rates.append(float((g["val"] == hi).sum()) / n)
        if top_prev is not None and (top or top_prev):
            top_churn.append(len(top ^ top_prev) / (len(top) + len(top_prev)))
        if bot_prev is not None and (bot or bot_prev):
            bot_churn.append(len(bot ^ bot_prev) / (len(bot) + len(bot_prev)))
        top_prev, bot_prev = top, bot
    ann = trading_days / rebalance_days
    return {
        "turnover_ann": float(np.mean(top_churn)) * ann if top_churn else float("nan"),
        "bottom_turnover_ann": float(np.mean(bot_churn)) * ann if bot_churn else float("nan"),
        "tie_rate": float(np.mean(tie_rates)) if tie_rates else float("nan"),
        "n_rebalances": len(rebal),
    }


def long_leg_excess_ir(factor: pd.Series, label: pd.Series, benchmark_fwd_return: pd.Series, *,
                       top_q: float = 0.2, cost_bps_per_turnover: float = 25.0,
                       rebalance_days: int = 20, trading_days: int = 252, min_names: int = 5) -> dict:
    """Deployable A-share headline: equal-weight top-quantile LONG-ONLY excess vs benchmark, net cost.

    ``factor`` MUST already be oriented (top bucket = intended-best; see :func:`resolve_orientation`).
    ``label`` = per-name forward return at the rebalance horizon; ``benchmark_fwd_return`` = the index
    forward return over the SAME horizon, indexed by date. Long-side cost only (no borrow fee) applied
    as ``one_way_turnover × cost_bps_per_turnover`` (default 25bps ≈ realistic_china long-side
    round-trip: sell stamp 5 + 2×commission 2.5 + slippage 10 + transfer 1). Returns annualized excess
    + its IR. This is the deployable number — a combined long-short spread is NOT (A-shares can't short).
    """
    f, lab = _to_dt_inst(factor), _to_dt_inst(label)
    joined = pd.DataFrame({"f": f, "r": lab}).dropna()
    if joined.empty:
        return {"long_leg_excess_ann": None, "long_leg_excess_ir": None, "n_rebalances": 0}
    dates = sorted(joined.index.get_level_values("datetime").unique())
    rebal = dates[::rebalance_days]
    excess, prev_top = [], None
    for d in rebal:
        g = joined.xs(d, level="datetime")
        if len(g) < min_names:
            continue
        top = g[g["f"] >= g["f"].quantile(1 - top_q)]
        cur = set(top.index)
        turn = len(cur ^ prev_top) / (len(cur) + len(prev_top)) if prev_top else 1.0
        bench = benchmark_fwd_return.get(d, np.nan)
        excess.append(float(top["r"].mean()) - float(bench) - turn * cost_bps_per_turnover / 1e4)
        prev_top = cur
    ex = pd.Series(excess).dropna()
    if len(ex) < 2:
        return {"long_leg_excess_ann": None, "long_leg_excess_ir": None, "n_rebalances": int(len(ex))}
    ann = trading_days / rebalance_days
    std = float(ex.std())
    ir = float(ex.mean() / std * np.sqrt(ann)) if std > 0 else float("nan")
    return {"long_leg_excess_ann": float(ex.mean() * ann), "long_leg_excess_ir": ir,
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
def resolve_orientation(ic_by_date: pd.Series, *, train_dates=None, economic_prior=None) -> dict:
    """Resolve a NON-CIRCULAR orientation sign for the monotonicity shape.

    NEVER uses the registry ``expected_direction`` (observed from heldout ICIR → circular).
    Priority: (1) ``economic_prior`` (predeclared ±1) → ``direction_source='economic_prior'``;
    (2) sign of mean IC over ``train_dates`` ONLY → ``'train_fold'``; (3) zero/empty →
    ``'undetermined'`` (sign defaults to +1, shape reported without a pass/fail polarity claim).

    ``ic_by_date`` is a per-date IC (or RankIC) Series. ``train_dates`` is the set/Index of dates in
    the walk-forward TRAIN windows only (NOT the full IS span, NOT the heldout blocks).
    """
    if economic_prior in (1, -1, 1.0, -1.0):
        return {"sign": float(economic_prior), "direction_source": "economic_prior"}
    if train_dates is not None and ic_by_date is not None and len(ic_by_date):
        idx = ic_by_date.index
        sel = idx.isin(list(train_dates))
        train_ic = ic_by_date[sel].dropna()
        if len(train_ic):
            m = float(train_ic.mean())
            if m > 0:
                return {"sign": 1.0, "direction_source": "train_fold"}
            if m < 0:
                return {"sign": -1.0, "direction_source": "train_fold"}
    return {"sign": 1.0, "direction_source": "undetermined"}


# --------------------------------------------------------------------------- leak-safe decay
def _rank_icir(rank_ic: pd.Series) -> float:
    r = rank_ic.dropna()
    return float(r.mean() / r.std()) if len(r) > 1 and r.std() > 0 else float("nan")


def leak_safe_decay_ic_vector(
    factor: pd.Series,
    adj_close: pd.Series,
    *,
    is_end,
    horizons=DEFAULT_DECAY_HORIZONS,
    trade_cal=None,
    min_obs: int = 30,
) -> dict:
    """Leak-safe IC-decay vector: for each horizon, an INDEPENDENTLY ``is_end``-clipped panel.

    Both ``factor`` and ``adj_close`` MUST already be capped at ``is_end`` (asserted by
    :func:`build_is_windowed_panel`). For each ``h`` we build a fresh ``IsWindowedPanel`` — which
    drops every factor date whose horizon-``h`` realization exceeds ``is_end`` — and compute the
    cross-sectional RankIC vs that panel's label. Returns per-horizon
    ``{mean_rank_ic, rank_icir, n_dates, max_realization}`` plus ``half_life`` (first horizon whose
    ``|rank_icir|`` ≤ half the peak; ``None`` if it never decays that far within the grid).

    This is the SANCTIONED decay path — never call ``compute_ic_decay(price.shift(-h))`` (no guard).
    """
    factor = factor if isinstance(factor, pd.Series) else pd.Series(factor)
    fdf = factor.to_frame("__f__")
    vec: dict[int, dict] = {}
    for h in horizons:
        panel = build_is_windowed_panel(fdf, adj_close, is_end=is_end, horizon=int(h), trade_cal=trade_cal)
        fser = panel.factor_panel["__f__"]
        # normalize to (datetime, instrument) for the IC helper
        fser = (fser.swaplevel(0, 1) if fser.index.names[0] != "datetime" else fser).sort_index()
        lab = panel.label
        lab = (lab.swaplevel(0, 1) if lab.index.names[0] != "datetime" else lab).sort_index()
        ic = compute_ic_series(fser, lab, min_obs=min_obs)
        rank_ic = ic["RankIC"] if "RankIC" in ic.columns else ic.iloc[:, -1]
        vec[int(h)] = {
            "mean_rank_ic": float(rank_ic.dropna().mean()) if len(rank_ic.dropna()) else float("nan"),
            "rank_icir": _rank_icir(rank_ic),
            "n_dates": int(rank_ic.dropna().shape[0]),
            "max_realization": str(pd.Timestamp(panel.max_label_realization_date).date()),
        }
    # half-life vs the peak |rank_icir|
    icirs = {h: abs(v["rank_icir"]) for h, v in vec.items() if v["rank_icir"] == v["rank_icir"]}
    half_life = None
    if icirs:
        peak_h = max(icirs, key=icirs.get)
        peak = icirs[peak_h]
        for h in sorted(h for h in icirs if h >= peak_h):
            if icirs[h] <= 0.5 * peak:
                half_life = h
                break
    return {"horizons": list(horizons), "vector": vec, "half_life": half_life,
            "note": "leak-safe: each horizon independently is_end-clipped via build_is_windowed_panel"}
