"""Pure factor-evaluation metrics for factor-lifecycle revalidation (Phase 4).

PURE builders over already-computed ``(factor, forward_return)`` panels — NO data
loading, NO window / OOS logic (that lives in ``revalidation.py``, where the ``is_end``
leakage boundary is enforced). They reuse ``factor_eval`` and port the bespoke GROSS
long-only top-bucket metric from the revalidation scripts VERBATIM so the modules
reproduce the scripts' numbers exactly. Returned floats are UNROUNDED — CSV rounding (to
match the legacy files) happens in ``report.py``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.alpha_research.factor_eval.ic_analysis import (
    compute_ic_by_year,
    compute_ic_series,
    compute_ic_summary,
)
from src.alpha_research.factor_eval.quantile_analysis import compute_quantile_returns

DEFAULT_HORIZON = 20
DEFAULT_N_QUANTILES = 10
DEFAULT_MIN_OBS = 50


def factor_ic(factor: pd.Series, forward_return: pd.Series) -> pd.Series:
    """Per-date rank IC series (reuse ``factor_eval.compute_ic_series``)."""
    return compute_ic_series(factor, forward_return)


def rank_icir(ic: pd.Series) -> float:
    """Rank ICIR over an IC series; NaN for empty (reuse ``compute_ic_summary``)."""
    if ic is None or len(ic) == 0:
        return float("nan")
    return compute_ic_summary(ic)["rank_icir"]


def yearly_sign_consistency(ic: pd.Series, full_rank_icir: float | None = None) -> float:
    """Fraction of calendar-year folds whose annual mean RankIC has the SAME sign as the
    full-period mean RankIC — the scripts' multiple-testing-robust stability driver.
    Ported from ``revalidate_catalog_walkforward.main`` (lines 130-135)."""
    if ic is None or len(ic) == 0:
        return float("nan")
    full = full_rank_icir if full_rank_icir is not None else rank_icir(ic)
    yearly = compute_ic_by_year(ic)
    if len(yearly) == 0 or pd.isna(full) or full == 0:
        return float("nan")
    same = (np.sign(yearly["mean_rank_ic"]) == np.sign(full)).sum()
    return float(same) / float(len(yearly))


def yearly_fold_count(ic: pd.Series) -> int:
    """Number of calendar-year IC folds (the scripts' ``n_years``)."""
    if ic is None or len(ic) == 0:
        return 0
    return int(len(compute_ic_by_year(ic)))


def long_only_topbucket(
    factor: pd.Series,
    forward_return: pd.Series,
    ic_sign: float,
    *,
    horizon: int = DEFAULT_HORIZON,
    n_quantiles: int = DEFAULT_N_QUANTILES,
    min_obs: int = DEFAULT_MIN_OBS,
) -> dict:
    """GROSS long-only top-bucket excess — top-decile minus count-weighted universe,
    sign-aligned so the 'good' decile is selected in the IC's predictive direction.
    Ported VERBATIM from ``revalidate_derived_factors.long_only_topbucket`` (lines 52-75).

    GROSS = no cost / turnover deduction (the FORMAL cost-adjusted long-only viability is
    a later-phase recompute). Returns ``{lo_excess_ann, lo_sharpe, lo_hit}`` (unrounded;
    NaN when the metric is undefined)."""
    ann = 252.0 / horizon
    nan = {"lo_excess_ann": float("nan"), "lo_sharpe": float("nan"), "lo_hit": float("nan")}
    if ic_sign == 0 or pd.isna(ic_sign):
        return dict(nan)
    qdf = compute_quantile_returns(factor, forward_return, n_quantiles=n_quantiles, min_obs=min_obs)
    if qdf.empty:
        return dict(nan)
    # universe per-date = count-weighted mean across deciles (~equal-weight universe)
    uni = (
        qdf.assign(w=qdf["mean_return"] * qdf["count"])
        .groupby("date")
        .apply(lambda g: g["w"].sum() / g["count"].sum())
    )
    good_q = int(qdf["quantile"].max()) if ic_sign > 0 else int(qdf["quantile"].min())
    good = qdf[qdf["quantile"] == good_q].set_index("date")["mean_return"]
    excess = (good - uni).dropna()
    if len(excess) < min_obs:
        return dict(nan)
    mu, sd = excess.mean(), excess.std()
    return {
        "lo_excess_ann": float(mu * ann),
        "lo_sharpe": float(mu / sd * np.sqrt(ann)) if sd > 0 else float("nan"),
        "lo_hit": float((excess > 0).mean()),
    }
