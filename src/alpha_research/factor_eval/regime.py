"""Simple regime summaries for gate-report diagnostics."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def summarize_regime_performance(
    returns: pd.Series | list[float] | np.ndarray,
    *,
    min_observations: int = 20,
) -> list[dict[str, Any]]:
    series = pd.Series(returns, dtype=float).dropna()
    if series.empty:
        return []
    if not isinstance(series.index, pd.DatetimeIndex):
        series.index = pd.date_range("2000-01-01", periods=len(series), freq="D")
    rows: list[dict[str, Any]] = []
    for year, window in series.groupby(series.index.year):
        if len(window) < min_observations:
            continue
        rows.append(
            {
                "regime": str(year),
                "mean_return": float(window.mean()),
                "volatility": float(window.std(ddof=1)),
                "positive": bool(window.mean() > 0),
                "observation_count": int(len(window)),
            }
        )
    return rows


def regime_pass_count(summary_rows: list[dict[str, Any]]) -> int:
    return int(sum(1 for row in summary_rows if bool(row.get("positive"))))
