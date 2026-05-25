"""
Cross-Factor Correlation Analysis (因子相关性分析)

Computes average cross-sectional correlations between factors to detect
redundancy and support diversified multi-factor model construction.

Unlike simple panel correlation, this computes correlation per date
cross-section and then averages — giving a more robust measure of
factor similarity.
"""

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

from src.alpha_research.factor_eval._utils import _normalize_multiindex


def compute_factor_correlation(
    factors: dict,
    method: str = "spearman",
    min_obs: int = 50,
) -> pd.DataFrame:
    """Compute average cross-sectional correlation between multiple factors.

    For each date, computes the pairwise correlation matrix across all
    factors, then averages across dates.

    Args:
        factors: Dict of {factor_name: pd.Series} where each Series has
            MultiIndex(datetime, instrument).
        method: Correlation method, "spearman" (default) or "pearson".
        min_obs: Minimum stocks per date for correlation computation.

    Returns:
        pd.DataFrame: Average correlation matrix (factor × factor).
    """
    if len(factors) < 2:
        raise ValueError("Need at least 2 factors for correlation analysis")

    factor_names = list(factors.keys())
    factors = {k: _normalize_multiindex(v) for k, v in factors.items()}
    aligned = pd.DataFrame(factors)

    date_level = aligned.index.names[0] if aligned.index.names[0] is not None else 0

    corr_matrices = []
    for date, group in aligned.groupby(level=date_level):
        daily = group.droplevel(0).dropna()
        if len(daily) < min_obs:
            continue
        corr = daily.corr(method=method)
        corr_matrices.append(corr)

    if not corr_matrices:
        return pd.DataFrame(np.nan, index=factor_names, columns=factor_names)

    avg_corr = pd.concat(corr_matrices).groupby(level=0).mean()
    avg_corr = avg_corr.reindex(index=factor_names, columns=factor_names)

    return avg_corr


def find_redundant_pairs(
    corr_matrix: pd.DataFrame, threshold: float = 0.7
) -> list:
    """Find pairs of factors with correlation above the threshold.

    Args:
        corr_matrix: Output of compute_factor_correlation.
        threshold: Absolute correlation threshold for redundancy.

    Returns:
        List of tuples (factor_a, factor_b, correlation), sorted by
        absolute correlation descending.
    """
    pairs = []
    names = corr_matrix.index.tolist()

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            corr = corr_matrix.loc[names[i], names[j]]
            if abs(corr) >= threshold:
                pairs.append((names[i], names[j], corr))

    pairs.sort(key=lambda x: abs(x[2]), reverse=True)
    return pairs


def select_uncorrelated(
    corr_matrix: pd.DataFrame,
    ic_summary: dict,
    max_corr: float = 0.5,
) -> list:
    """Greedily select factors to maximize diversification.

    Selects factors in order of descending ICIR, skipping any
    factor that is too correlated with an already-selected factor.

    Args:
        corr_matrix: Output of compute_factor_correlation.
        ic_summary: Dict of {factor_name: {"icir": float, ...}}, e.g.,
            from running compute_ic_summary on each factor.
        max_corr: Maximum allowed absolute correlation with any
            already-selected factor.

    Returns:
        List of selected factor names, ordered by ICIR descending.
    """
    # Sort factors by absolute ICIR descending
    ranked = sorted(
        ic_summary.items(),
        key=lambda x: abs(x[1].get("icir", 0)),
        reverse=True,
    )

    selected = []
    for factor_name, _ in ranked:
        if factor_name not in corr_matrix.index:
            continue

        # Check correlation with all already-selected factors
        is_ok = True
        for sel in selected:
            corr = abs(corr_matrix.loc[factor_name, sel])
            if corr >= max_corr:
                is_ok = False
                logger.debug(
                    "Skipping %s: corr=%.3f with %s (threshold=%.2f)",
                    factor_name, corr, sel, max_corr,
                )
                break

        if is_ok:
            selected.append(factor_name)

    return selected
