"""
IC Decay Analysis (IC衰减分析)

Measures how a factor's predictive power decays across different forward
return horizons, helping determine optimal holding period and rebalance
frequency.

The key output is an IC decay curve: ICIR plotted against forward horizon.
The peak of this curve indicates the optimal prediction horizon.
"""

import logging
import numpy as np
import pandas as pd

from src.alpha_research.factor_eval.ic_analysis import (
    compute_ic_series,
    compute_ic_summary,
)

logger = logging.getLogger(__name__)

from src.alpha_research.factor_eval._utils import _normalize_multiindex


def compute_ic_decay(
    factor: pd.Series,
    price: pd.Series,
    horizons: list = None,
    min_obs: int = 30,
) -> pd.DataFrame:
    """Compute IC/ICIR at multiple forward return horizons.

    For each horizon h, computes forward returns as price(t+h)/price(t) - 1,
    then calculates IC statistics against the factor.

    Args:
        factor: Factor values with MultiIndex(datetime, instrument).
        price: Adjusted close prices with same index structure.
        horizons: List of forward return horizons in trading days.
            Defaults to [1, 2, 3, 5, 10, 20, 40, 60].
        min_obs: Minimum stocks per cross-section for IC computation.

    Returns:
        DataFrame indexed by horizon with columns:
            [mean_ic, mean_rank_ic, icir, rank_icir, n_days]
    """
    factor = _normalize_multiindex(factor)
    price = _normalize_multiindex(price)

    if horizons is None:
        horizons = [1, 2, 3, 5, 10, 20, 40, 60]

    results = []
    date_level = price.index.names[0] if price.index.names[0] is not None else 0
    inst_level = price.index.names[1] if len(price.index.names) > 1 and price.index.names[1] is not None else 1

    for h in horizons:
        # Compute forward returns for this horizon
        fwd_ret = price.groupby(level=inst_level).shift(-h) / price - 1
        fwd_ret = fwd_ret.replace([np.inf, -np.inf], np.nan)

        # Compute IC series
        ic_series = compute_ic_series(factor, fwd_ret, min_obs=min_obs)

        if ic_series.empty:
            results.append({
                "horizon": h,
                "mean_ic": np.nan,
                "mean_rank_ic": np.nan,
                "icir": np.nan,
                "rank_icir": np.nan,
                "n_days": 0,
            })
            continue

        summary = compute_ic_summary(ic_series)
        results.append({
            "horizon": h,
            "mean_ic": summary["mean_ic"],
            "mean_rank_ic": summary["mean_rank_ic"],
            "icir": summary["icir"],
            "rank_icir": summary["rank_icir"],
            "n_days": summary["n_days"],
        })

    return pd.DataFrame(results).set_index("horizon")


def find_optimal_horizon(decay_df: pd.DataFrame) -> dict:
    """Find the optimal forward return horizon from decay analysis.

    Identifies the horizon with the best ICIR (absolute value) and
    estimates the half-life of predictive power.

    Args:
        decay_df: Output of compute_ic_decay.

    Returns:
        Dictionary with:
            best_horizon_ic: Horizon with highest |mean_ic|
            best_horizon_icir: Horizon with highest |icir|
            peak_icir: The peak ICIR value
            half_life: Horizon where |ICIR| drops to 50% of peak (estimated)
    """
    if decay_df.empty or decay_df["icir"].isna().all():
        return {
            "best_horizon_ic": None,
            "best_horizon_icir": None,
            "peak_icir": None,
            "half_life": None,
        }

    abs_ic = decay_df["mean_ic"].abs()
    abs_icir = decay_df["icir"].abs()

    best_ic_h = abs_ic.idxmax()
    best_icir_h = abs_icir.idxmax()
    peak_icir = abs_icir.max()

    # Estimate half-life: first horizon after peak where |ICIR| < 0.5 * peak
    half_threshold = 0.5 * peak_icir
    post_peak = abs_icir.loc[best_icir_h:]
    below_half = post_peak[post_peak < half_threshold]
    half_life = int(below_half.index[0]) if not below_half.empty else None

    return {
        "best_horizon_ic": int(best_ic_h),
        "best_horizon_icir": int(best_icir_h),
        "peak_icir": peak_icir,
        "half_life": half_life,
    }
