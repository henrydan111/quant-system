"""Cost-aware evaluation helpers kept separate from cross-sectional IC analysis."""

from __future__ import annotations

import numpy as np
import pandas as pd


def annualized_turnover(turnover: pd.Series | list[float] | np.ndarray, *, trading_days: int = 252) -> float:
    series = pd.Series(turnover, dtype=float).dropna()
    if series.empty:
        return np.nan
    return float(series.mean() * trading_days)


def cost_adjusted_returns(
    gross_returns: pd.Series | list[float] | np.ndarray,
    turnover: pd.Series | list[float] | np.ndarray,
    *,
    cost_bps_per_unit_turnover: float,
) -> pd.Series:
    gross = pd.Series(gross_returns, dtype=float).dropna()
    aligned_turnover = pd.Series(turnover, dtype=float).reindex(gross.index).fillna(0.0)
    cost_rate = float(cost_bps_per_unit_turnover) / 10_000.0
    return gross - aligned_turnover * cost_rate


def cost_adjusted_sharpe(
    gross_returns: pd.Series | list[float] | np.ndarray,
    turnover: pd.Series | list[float] | np.ndarray,
    *,
    cost_bps_per_unit_turnover: float,
    trading_days: int = 252,
) -> float:
    net = cost_adjusted_returns(
        gross_returns,
        turnover,
        cost_bps_per_unit_turnover=cost_bps_per_unit_turnover,
    )
    std = float(net.std(ddof=1))
    if std <= 0:
        return np.nan
    return float(np.sqrt(trading_days) * net.mean() / std)
