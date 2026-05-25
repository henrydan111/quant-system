"""
Factor Neutralization (因子中性化)

Cross-sectional regression-based neutralization to remove unwanted
exposures (size, industry, etc.) from raw factor values.

Method:
    For each date, regress factor values on control variables (continuous
    and/or categorical). The OLS residuals become the neutralized factor.

    factor_neutralized(t) = factor(t) - X(t) @ beta_hat(t)
"""

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

from src.alpha_research.factor_eval._utils import _normalize_multiindex


def neutralize(
    factor: pd.Series,
    controls: dict = None,
    industry: pd.Series = None,
    min_obs: int = 50,
) -> pd.Series:
    """Neutralize a factor against arbitrary continuous and categorical controls.

    Performs per-date cross-sectional OLS regression of the factor on the
    control variables and returns the residuals as the neutralized factor.

    Args:
        factor: Raw factor values with MultiIndex(datetime, instrument).
        controls: Dict of {name: pd.Series} for continuous control variables
            (e.g., {"log_mcap": log_market_cap_series}). Each Series must
            have the same MultiIndex as factor.
        industry: Optional pd.Series of industry labels for dummy encoding.
            Must have the same MultiIndex as factor.
        min_obs: Minimum stocks per cross-section for regression.

    Returns:
        pd.Series of neutralized factor values (OLS residuals), same index
        as input factor.
    """
    if controls is None and industry is None:
        logger.warning("No controls or industry provided; returning raw factor")
        return factor.copy()

    factor = _normalize_multiindex(factor)
    if controls:
        controls = {k: _normalize_multiindex(v) for k, v in controls.items()}
    if industry is not None:
        industry = _normalize_multiindex(industry)

    date_level = factor.index.names[0] if factor.index.names[0] is not None else 0
    neutralized = pd.Series(np.nan, index=factor.index, dtype=float)

    for date, f_group in factor.groupby(level=date_level):
        f = f_group.dropna()
        if len(f) < min_obs:
            continue

        # Build design matrix
        X_parts = []

        if controls:
            for name, ctrl_series in controls.items():
                try:
                    ctrl_slice = ctrl_series.loc[date].reindex(f.droplevel(0).index)
                except KeyError:
                    continue
                X_parts.append(ctrl_slice.rename(name))

        if industry is not None:
            try:
                ind_slice = industry.loc[date].reindex(f.droplevel(0).index)
            except KeyError:
                ind_slice = pd.Series(dtype=str)

            if not ind_slice.empty:
                dummies = pd.get_dummies(ind_slice, prefix="ind", drop_first=True)
                X_parts.append(dummies)

        if not X_parts:
            continue

        X = pd.concat(X_parts, axis=1)
        common = f.droplevel(0).index.intersection(X.index)
        common = common[X.loc[common].notna().all(axis=1)]

        if len(common) < min_obs:
            continue

        y = f.droplevel(0).loc[common].values.astype(float)
        X_mat = X.loc[common].values.astype(float)

        # Add intercept
        X_mat = np.column_stack([np.ones(len(X_mat)), X_mat])

        # OLS via numpy (avoids statsmodels dependency)
        try:
            beta, _, _, _ = np.linalg.lstsq(X_mat, y, rcond=None)
            residuals = y - X_mat @ beta
        except np.linalg.LinAlgError:
            logger.warning("Singular matrix on %s, skipping", date)
            continue

        # Write back residuals
        idx = pd.MultiIndex.from_arrays(
            [[date] * len(common), common],
            names=factor.index.names,
        )
        neutralized.loc[idx] = residuals

    return neutralized


def neutralize_size(
    factor: pd.Series, market_cap: pd.Series, min_obs: int = 50
) -> pd.Series:
    """Convenience: neutralize factor against log(market_cap).

    Args:
        factor: Raw factor with MultiIndex(datetime, instrument).
        market_cap: Market capitalization with same index (e.g., total_mv).
        min_obs: Minimum stocks per cross-section.

    Returns:
        Size-neutralized factor values.
    """
    log_mcap = np.log(market_cap.replace(0, np.nan))
    return neutralize(factor, controls={"log_mcap": log_mcap}, min_obs=min_obs)


def neutralize_industry(
    factor: pd.Series, industry_labels: pd.Series, min_obs: int = 50
) -> pd.Series:
    """Convenience: neutralize factor against industry dummies.

    Args:
        factor: Raw factor with MultiIndex(datetime, instrument).
        industry_labels: Industry classification labels with same index
            (e.g., Shenwan L1 industry name or code).
        min_obs: Minimum stocks per cross-section.

    Returns:
        Industry-neutralized factor values.
    """
    return neutralize(factor, industry=industry_labels, min_obs=min_obs)


def neutralize_size_industry(
    factor: pd.Series,
    market_cap: pd.Series,
    industry_labels: pd.Series,
    min_obs: int = 50,
) -> pd.Series:
    """Convenience: neutralize factor against both size and industry.

    Args:
        factor: Raw factor with MultiIndex(datetime, instrument).
        market_cap: Market capitalization with same index.
        industry_labels: Industry classification labels with same index.
        min_obs: Minimum stocks per cross-section.

    Returns:
        Size + industry neutralized factor values.
    """
    log_mcap = np.log(market_cap.replace(0, np.nan))
    return neutralize(
        factor,
        controls={"log_mcap": log_mcap},
        industry=industry_labels,
        min_obs=min_obs,
    )
