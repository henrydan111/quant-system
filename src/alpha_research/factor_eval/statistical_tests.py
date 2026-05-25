"""Lightweight statistical rigor helpers for formal hypothesis testing."""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd


def _to_series(values: pd.Series | list[float] | np.ndarray) -> pd.Series:
    if isinstance(values, pd.Series):
        return values.astype(float).dropna()
    return pd.Series(values, dtype=float).dropna()


def bootstrap_sharpe_ci(
    returns: pd.Series | list[float] | np.ndarray,
    *,
    n_bootstrap: int = 1000,
    trading_days: int = 252,
    ci: float = 0.95,
    random_state: int = 42,
) -> dict[str, float]:
    series = _to_series(returns)
    if series.empty:
        return {"sharpe": np.nan, "ci_low": np.nan, "ci_high": np.nan}
    rng = np.random.default_rng(random_state)
    sharpe_samples: list[float] = []
    values = series.to_numpy(dtype=float)
    for _ in range(int(n_bootstrap)):
        sample = rng.choice(values, size=len(values), replace=True)
        std = float(np.std(sample, ddof=1))
        sharpe = float(np.sqrt(trading_days) * np.mean(sample) / std) if std > 0 else np.nan
        sharpe_samples.append(sharpe)
    alpha = (1.0 - float(ci)) / 2.0
    return {
        "sharpe": float(np.sqrt(trading_days) * series.mean() / series.std(ddof=1)) if series.std(ddof=1) > 0 else np.nan,
        "ci_low": float(np.nanquantile(sharpe_samples, alpha)),
        "ci_high": float(np.nanquantile(sharpe_samples, 1.0 - alpha)),
    }


def probabilistic_sharpe_ratio(
    returns: pd.Series | list[float] | np.ndarray,
    *,
    benchmark_sharpe: float = 0.0,
    trading_days: int = 252,
) -> float:
    series = _to_series(returns)
    if len(series) < 2:
        return np.nan
    mean = float(series.mean())
    std = float(series.std(ddof=1))
    if std <= 0:
        return np.nan
    sharpe = float(np.sqrt(trading_days) * mean / std)
    skew = float(series.skew())
    kurtosis = float(series.kurtosis() + 3.0)
    numerator = (sharpe - float(benchmark_sharpe)) * math.sqrt(len(series) - 1.0)
    denominator = math.sqrt(max(1e-12, 1.0 - skew * sharpe + ((kurtosis - 1.0) / 4.0) * (sharpe ** 2)))
    return float(NormalDist().cdf(numerator / denominator))


def deflated_sharpe_ratio(
    returns: pd.Series | list[float] | np.ndarray,
    *,
    number_of_trials: int,
    benchmark_sharpe: float = 0.0,
    trading_days: int = 252,
) -> float:
    if number_of_trials <= 0:
        raise ValueError("number_of_trials must be positive")
    adjustment = math.sqrt(2.0 * math.log(max(number_of_trials, 1)))
    return probabilistic_sharpe_ratio(
        returns,
        benchmark_sharpe=float(benchmark_sharpe) + adjustment / math.sqrt(trading_days),
        trading_days=trading_days,
    )
