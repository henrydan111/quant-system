"""
Quantile Portfolio Analysis (分位组合分析)

Constructs quantile-sorted portfolios from factor values and evaluates
long-short spreads, return monotonicity, and quantile-level statistics.

Qlib's _group_return() buries quantile computation inside Plotly plotting
with no standalone data API. This module provides the raw data functions.
"""

import logging
import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

from src.alpha_research.factor_eval._utils import _normalize_multiindex


def compute_quantile_returns(
    factor: pd.Series,
    forward_return: pd.Series,
    n_quantiles: int = 5,
    min_obs: int = 50,
) -> pd.DataFrame:
    """Compute mean forward returns for each factor quantile, per date.

    Stocks are ranked cross-sectionally each day and assigned to quantile
    groups (1 = lowest factor value, N = highest).

    Args:
        factor: Factor values with MultiIndex(datetime, instrument).
        forward_return: Forward returns with same index structure.
        n_quantiles: Number of quantile groups (default 5 = quintiles).
        min_obs: Minimum stocks per cross-section; dates with fewer are skipped.

    Returns:
        DataFrame with columns [date, quantile, mean_return, count].
        Quantile 1 = lowest factor value, quantile N = highest.
    """
    df = pd.DataFrame({"factor": _normalize_multiindex(factor),
                        "fwd": _normalize_multiindex(forward_return)}).dropna()

    if df.empty:
        return pd.DataFrame(columns=["date", "quantile", "mean_return", "count"])

    date_level = df.index.names[0] if df.index.names[0] is not None else 0
    results = []

    for date, group in df.groupby(level=date_level):
        if len(group) < min_obs:
            continue
        try:
            labels = pd.qcut(
                group["factor"], n_quantiles, labels=False, duplicates="drop"
            )
        except ValueError:
            continue

        actual_n = labels.nunique()
        for q in range(actual_n):
            mask = labels == q
            results.append({
                "date": date,
                "quantile": q + 1,
                "mean_return": group.loc[mask, "fwd"].mean(),
                "count": mask.sum(),
            })

    return pd.DataFrame(results)


def compute_quantile_summary(
    quantile_df: pd.DataFrame, annual_factor: int = 252
) -> pd.DataFrame:
    """Aggregate quantile returns into annualized statistics.

    Args:
        quantile_df: Output of compute_quantile_returns.
        annual_factor: Trading days per year for annualization.

    Returns:
        DataFrame indexed by quantile with columns:
            [mean_daily_return, annualized_return, volatility, sharpe, n_days]
    """
    if quantile_df.empty:
        return pd.DataFrame()

    results = []
    for q, group in quantile_df.groupby("quantile"):
        daily_r = group["mean_return"]
        mean_r = daily_r.mean()
        std_r = daily_r.std()
        results.append({
            "quantile": q,
            "mean_daily_return": mean_r,
            "annualized_return": mean_r * annual_factor,
            "volatility": std_r * np.sqrt(annual_factor) if std_r > 0 else 0.0,
            "sharpe": (
                np.sqrt(annual_factor) * mean_r / std_r if std_r > 0 else 0.0
            ),
            "n_days": len(daily_r),
        })

    return pd.DataFrame(results).set_index("quantile")


def compute_long_short_returns(
    quantile_df: pd.DataFrame,
    long_q: int = None,
    short_q: int = 1,
) -> pd.Series:
    """Extract the daily long-short return series from quantile data.

    Args:
        quantile_df: Output of compute_quantile_returns.
        long_q: Quantile to go long. Defaults to the highest quantile.
        short_q: Quantile to go short. Defaults to 1 (lowest).

    Returns:
        pd.Series of daily (long_quantile - short_quantile) returns,
        indexed by date. Can be fed directly into result_analysis/metrics.py.
    """
    if quantile_df.empty:
        return pd.Series(dtype=float)

    if long_q is None:
        long_q = quantile_df["quantile"].max()

    long_returns = (
        quantile_df[quantile_df["quantile"] == long_q]
        .set_index("date")["mean_return"]
    )
    short_returns = (
        quantile_df[quantile_df["quantile"] == short_q]
        .set_index("date")["mean_return"]
    )

    ls = long_returns - short_returns
    ls.name = f"long_short_Q{long_q}_Q{short_q}"
    return ls.dropna()


def test_monotonicity(quantile_summary: pd.DataFrame) -> dict:
    """Test whether quantile returns are monotonically ordered.

    Uses Spearman rank correlation between quantile number and
    annualized return to assess monotonicity.

    Args:
        quantile_summary: Output of compute_quantile_summary.

    Returns:
        Dictionary with:
            is_monotonic: True if |spearman_corr| >= 0.8
            spearman_corr: Correlation between quantile rank and return
            p_value: Statistical significance
            direction: 'ascending' or 'descending'
    """
    if quantile_summary.empty or len(quantile_summary) < 3:
        return {
            "is_monotonic": False,
            "spearman_corr": 0.0,
            "p_value": 1.0,
            "direction": "unknown",
        }

    q_ranks = quantile_summary.index.values
    returns = quantile_summary["annualized_return"].values

    corr, p_value = stats.spearmanr(q_ranks, returns)
    direction = "ascending" if corr > 0 else "descending"

    return {
        "is_monotonic": abs(corr) >= 0.8,
        "spearman_corr": corr,
        "p_value": p_value,
        "direction": direction,
    }
