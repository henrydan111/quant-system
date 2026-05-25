"""
IC Analysis (信息系数分析)

Wraps Qlib's calc_ic for Pearson/Spearman IC computation and adds
ICIR, hit rate, yearly breakdown, and other summary statistics that
Qlib does not provide.

Mathematical definitions:
    IC  = Pearson(factor_t, fwd_return_t)       per cross-section
    RankIC = Spearman(factor_t, fwd_return_t)   per cross-section
    ICIR = mean(IC) / std(IC)                   signal consistency
    IC Hit Rate = % of dates where sign(IC) matches expected direction
"""

import logging
import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

from src.alpha_research.factor_eval._utils import _normalize_multiindex


def _calc_ic_fallback(
    factor: pd.Series, forward_return: pd.Series, date_level: str = "datetime"
) -> pd.DataFrame:
    """Pure-pandas IC computation for when Qlib is not initialized.

    Args:
        factor: Factor values with MultiIndex(datetime, instrument).
        forward_return: Forward returns with same index structure.
        date_level: Name of the datetime level in the MultiIndex.

    Returns:
        DataFrame with columns [IC, RankIC] indexed by date.
    """
    df = pd.DataFrame({"factor": _normalize_multiindex(factor),
                        "fwd": _normalize_multiindex(forward_return)}).dropna()

    if df.empty:
        return pd.DataFrame(columns=["IC", "RankIC"])

    date_level_name = df.index.names[0] if df.index.names[0] is not None else 0

    def _corr(group):
        if len(group) < 2:
            return pd.Series({"IC": np.nan, "RankIC": np.nan})
        ic = group["factor"].corr(group["fwd"])
        ric = group["factor"].corr(group["fwd"], method="spearman")
        return pd.Series({"IC": ic, "RankIC": ric})

    result = df.groupby(level=date_level_name, group_keys=False).apply(_corr)
    return result


def compute_ic_series(
    factor: pd.Series,
    forward_return: pd.Series,
    min_obs: int = 30,
) -> pd.DataFrame:
    """Compute daily cross-sectional IC and RankIC.

    Wraps Qlib's calc_ic when available, falls back to pure pandas
    implementation otherwise. Filters out dates with fewer than
    min_obs valid observations.

    Args:
        factor: Factor values with MultiIndex(datetime, instrument).
        forward_return: Forward returns with same index structure.
        min_obs: Minimum number of stocks per cross-section. Dates
            with fewer observations are set to NaN.

    Returns:
        pd.DataFrame with columns [IC, RankIC] indexed by datetime.
    """
    factor = _normalize_multiindex(factor)
    forward_return = _normalize_multiindex(forward_return)

    try:
        from qlib.contrib.eva.alpha import calc_ic
        ic, ric = calc_ic(factor, forward_return, dropna=True)
        result = pd.DataFrame({"IC": ic, "RankIC": ric})
        logger.debug("IC computed using Qlib's calc_ic")
    except (ImportError, Exception) as e:
        logger.debug("Qlib calc_ic unavailable (%s), using fallback", e)
        result = _calc_ic_fallback(factor, forward_return)

    # Filter dates with too few observations
    if min_obs > 1:
        df = pd.DataFrame({"factor": factor, "fwd": forward_return}).dropna()
        date_level = df.index.names[0] if df.index.names[0] is not None else 0
        counts = df.groupby(level=date_level).size()
        valid_dates = counts[counts >= min_obs].index
        result = result.loc[result.index.isin(valid_dates)]

    return result


def compute_ic_summary(ic_series: pd.DataFrame) -> dict:
    """Compute aggregate IC statistics from an IC time series.

    Args:
        ic_series: DataFrame with columns [IC, RankIC] from compute_ic_series.

    Returns:
        Dictionary with keys:
            mean_ic, mean_rank_ic, std_ic, std_rank_ic,
            icir, rank_icir, ic_hit_rate, ic_positive_pct, n_days
    """
    ic = ic_series["IC"].dropna()
    ric = ic_series["RankIC"].dropna()

    mean_ic = ic.mean()
    std_ic = ic.std()
    mean_ric = ric.mean()
    std_ric = ric.std()

    icir = mean_ic / std_ic if std_ic > 0 else 0.0
    rank_icir = mean_ric / std_ric if std_ric > 0 else 0.0

    # Hit rate: % of days IC has same sign as mean_ic
    expected_sign = np.sign(mean_ic) if mean_ic != 0 else 1.0
    ic_hit_rate = (np.sign(ic) == expected_sign).mean() if len(ic) > 0 else 0.0

    # Positive pct: % of days IC > 0
    ic_positive_pct = (ic > 0).mean() if len(ic) > 0 else 0.0

    return {
        "mean_ic": mean_ic,
        "mean_rank_ic": mean_ric,
        "std_ic": std_ic,
        "std_rank_ic": std_ric,
        "icir": icir,
        "rank_icir": rank_icir,
        "ic_hit_rate": ic_hit_rate,
        "ic_positive_pct": ic_positive_pct,
        "n_days": len(ic),
    }


def compute_ic_by_year(ic_series: pd.DataFrame) -> pd.DataFrame:
    """Break down IC statistics by calendar year.

    Args:
        ic_series: DataFrame with columns [IC, RankIC] from compute_ic_series.

    Returns:
        DataFrame indexed by year with columns:
            [mean_ic, mean_rank_ic, icir, rank_icir, ic_hit_rate, n_days]
    """
    ic_series = ic_series.copy()
    ic_series.index = pd.to_datetime(ic_series.index)
    ic_series["year"] = ic_series.index.year

    results = []
    for year, group in ic_series.groupby("year"):
        ic = group["IC"].dropna()
        ric = group["RankIC"].dropna()
        if len(ic) == 0:
            continue
        mean_ic = ic.mean()
        std_ic = ic.std()
        mean_ric = ric.mean()
        std_ric = ric.std()
        expected_sign = np.sign(mean_ic) if mean_ic != 0 else 1.0
        results.append({
            "year": year,
            "mean_ic": mean_ic,
            "mean_rank_ic": mean_ric,
            "icir": mean_ic / std_ic if std_ic > 0 else 0.0,
            "rank_icir": mean_ric / std_ric if std_ric > 0 else 0.0,
            "ic_hit_rate": (np.sign(ic) == expected_sign).mean(),
            "n_days": len(ic),
        })

    return pd.DataFrame(results).set_index("year")


def compute_rolling_ic(
    ic_series: pd.DataFrame,
    window: int = 252,
) -> pd.DataFrame:
    """Compute rolling-window mean IC and ICIR from an IC time series.

    Useful for detecting regime changes and factor decay over time.

    Args:
        ic_series: DataFrame with columns [IC, RankIC] from compute_ic_series.
        window: Rolling window size in trading days (default 252 = ~1 year).

    Returns:
        pd.DataFrame indexed by date with columns:
            [rolling_mean_ic, rolling_mean_rank_ic,
             rolling_icir, rolling_rank_icir]
    """
    ic_series = ic_series.copy()
    ic_series.index = pd.to_datetime(ic_series.index)

    roll_ic = ic_series["IC"].rolling(window, min_periods=window // 2)
    roll_ric = ic_series["RankIC"].rolling(window, min_periods=window // 2)

    result = pd.DataFrame({
        "rolling_mean_ic": roll_ic.mean(),
        "rolling_mean_rank_ic": roll_ric.mean(),
        "rolling_icir": roll_ic.mean() / roll_ic.std(),
        "rolling_rank_icir": roll_ric.mean() / roll_ric.std(),
    })

    return result.dropna(how="all")


def compute_ic_by_group(
    factor: pd.Series,
    forward_return: pd.Series,
    group_labels: pd.Series,
    min_obs: int = 30,
) -> dict:
    """Compute IC statistics separately within each group.

    Splits the cross-section by group_labels (e.g., size terciles)
    and computes IC/ICIR within each group independently.

    Args:
        factor: Factor values with MultiIndex(datetime, instrument).
        forward_return: Forward returns with same index structure.
        group_labels: Group assignment per stock per date, same index
            (e.g., 'large', 'mid', 'small' from market cap terciles).
        min_obs: Minimum stocks per cross-section within each group.

    Returns:
        Dict of {group_name: ic_summary_dict} where ic_summary_dict
        is the output of compute_ic_summary.
    """
    factor = _normalize_multiindex(factor)
    forward_return = _normalize_multiindex(forward_return)
    group_labels = _normalize_multiindex(group_labels)

    df = pd.DataFrame({
        "factor": factor,
        "fwd": forward_return,
        "group": group_labels,
    }).dropna()

    if df.empty:
        return {}

    results = {}
    for group_name, group_df in df.groupby("group"):
        # Extract factor and fwd as Series with the original MultiIndex
        g_factor = group_df["factor"]
        g_fwd = group_df["fwd"]

        try:
            ic_series = compute_ic_series(g_factor, g_fwd, min_obs=min_obs)
            if ic_series.empty:
                continue
            results[group_name] = compute_ic_summary(ic_series)
        except Exception as e:
            logger.warning("IC computation failed for group %s: %s", group_name, e)
            continue

    return results


def compute_marginal_ic(
    factors_dict: dict,
    forward_return: pd.Series,
    base_factors: list,
    candidate: str,
    min_obs: int = 30,
) -> tuple:
    """Compute the marginal IC of a candidate factor after orthogonalizing
    against a set of base factors.

    For each date, the candidate factor is regressed on the base factors
    and the residual is correlated with forward returns. This measures
    the incremental information the candidate provides beyond the base.

    Mathematical definition:
        candidate_resid(t) = candidate(t) - X_base(t) @ beta_hat(t)
        Marginal IC = corr(candidate_resid(t), fwd_return(t))

    Args:
        factors_dict: Dict of {factor_name: pd.Series} for all factors.
        forward_return: Forward returns with MultiIndex(datetime, instrument).
        base_factors: List of factor names already in the model.
        candidate: Name of the candidate factor to evaluate.
        min_obs: Minimum stocks per cross-section for regression.

    Returns:
        Tuple of (marginal_ic_series, marginal_ic_summary) where
        marginal_ic_series is a DataFrame[IC, RankIC] and
        marginal_ic_summary is a dict from compute_ic_summary.
    """
    if candidate not in factors_dict:
        raise ValueError(f"Candidate '{candidate}' not found in factors_dict")

    cand = _normalize_multiindex(factors_dict[candidate])
    forward_return = _normalize_multiindex(forward_return)

    if not base_factors:
        # No base factors — marginal IC equals raw IC
        ic_series = compute_ic_series(cand, forward_return, min_obs=min_obs)
        return ic_series, compute_ic_summary(ic_series)

    # Normalize base factors
    bases = {k: _normalize_multiindex(factors_dict[k])
             for k in base_factors if k in factors_dict}
    if not bases:
        ic_series = compute_ic_series(cand, forward_return, min_obs=min_obs)
        return ic_series, compute_ic_summary(ic_series)

    # Orthogonalize candidate against base factors per date
    all_data = pd.DataFrame(bases)
    all_data["_candidate"] = cand
    all_data = all_data.dropna()

    date_level = all_data.index.names[0] if all_data.index.names[0] is not None else 0
    residuals = pd.Series(np.nan, index=cand.index, dtype=float)

    for date, group in all_data.groupby(level=date_level):
        if len(group) < min_obs:
            continue

        y = group["_candidate"].values.astype(float)
        X = group[list(bases.keys())].values.astype(float)
        X = np.column_stack([np.ones(len(X)), X])

        try:
            beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
            resid = y - X @ beta
        except np.linalg.LinAlgError:
            continue

        idx = group.index
        residuals.loc[idx] = resid

    # Compute IC of residuals vs forward returns
    ic_series = compute_ic_series(residuals, forward_return, min_obs=min_obs)
    summary = compute_ic_summary(ic_series) if not ic_series.empty else {}

    return ic_series, summary
