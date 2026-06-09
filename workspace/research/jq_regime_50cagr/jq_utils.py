"""Shared helpers for the JQ-regime-rotation research effort.

Reuses the prior long_only_50cagr tooling (PIT-safe compute_factors cache,
VectorizedBacktester harness, PIT-safe index overlays). Adds:
  - per-calendar-year return breakdown (yearly stability check)
  - a regime-combine simulator that switches between already-computed per-book
    net-return series using a PIT-safe (shift-1) index regime signal, with
    explicit cash legs and switch costs. This REUSES the validated engine
    (each book's daily net return came from VectorizedBacktester) and only
    combines series -- it introduces no new data access and no lookahead.

Research-only code (workspace/); project-relative paths are acceptable.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PRIOR = PROJECT_ROOT / "workspace" / "research" / "long_only_50cagr"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PRIOR))            # research_utils, backtest_harness, overlay
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd

import research_utils as ru          # noqa: E402
import overlay as ov                 # noqa: E402

CACHE = PROJECT_ROOT / "workspace" / "outputs" / "long_only_50cagr"
OUT = PROJECT_ROOT / "workspace" / "outputs" / "jq_regime_50cagr"
OUT.mkdir(parents=True, exist_ok=True)


def per_year_returns(net: pd.Series) -> pd.Series:
    """Calendar-year total return from a daily net-return series."""
    net = net.dropna()
    if net.empty:
        return pd.Series(dtype=float)
    yr = net.index.year
    return net.groupby(yr).apply(lambda r: float((1.0 + r).prod() - 1.0))


def yearly_str(net: pd.Series) -> str:
    yrs = per_year_returns(net)
    return "  ".join(f"{y}:{v:+.1%}" for y, v in yrs.items())


def worst_year(net: pd.Series) -> float:
    yrs = per_year_returns(net)
    return float(yrs.min()) if len(yrs) else float("nan")


def summary_line(label: str, net: pd.Series, bench: pd.Series | None = None) -> str:
    m = ru.goal_metrics(net, bench)
    calmar = (m["cagr"] / abs(m["mdd"])) if (m["mdd"] and m["mdd"] < 0) else float("nan")
    return (f"{label:34s} CAGR={m['cagr']:+7.2%} MDD={m['mdd']:+7.2%} "
            f"Sharpe={m['sharpe']:5.2f} Calmar={calmar:4.2f} Vol={m['ann_vol']:5.1%} "
            f"worstY={worst_year(net):+6.1%} n={m['n_days']}")


def metrics_dict(label: str, net: pd.Series, bench: pd.Series | None = None) -> dict:
    m = ru.goal_metrics(net, bench)
    m["label"] = label
    m["calmar"] = (m["cagr"] / abs(m["mdd"])) if (m["mdd"] and m["mdd"] < 0) else float("nan")
    m["worst_year"] = worst_year(net)
    m["yearly"] = {int(y): float(v) for y, v in per_year_returns(net).items()}
    return m


# ---------------- regime-combine simulator ----------------
def index_ratio_signal(
    code_fast: str,
    code_slow: str,
    start: str,
    end: str,
    *,
    ma_window: int = 120,
    shift: int = 1,
) -> pd.Series:
    """PIT-safe relative-strength regime: 1.0 when code_fast's relative-to-code_slow
    ratio (lagged `shift`) is above its `ma_window` MA, else 0.0. Decision on day T
    uses index closes only through T-shift -> PIT-safe."""
    a = ov.load_index_close(code_fast)
    b = ov.load_index_close(code_slow)
    idx = a.index.intersection(b.index)
    ratio = (a.reindex(idx) / b.reindex(idx)).sort_index()
    ma = ratio.rolling(ma_window, min_periods=ma_window).mean()
    sig = (ratio.shift(shift) > ma.shift(shift)).astype(float)
    sig = sig[(sig.index >= pd.Timestamp(start)) & (sig.index <= pd.Timestamp(end))]
    return sig


def combine_regime(
    book_returns: dict[str, pd.Series],
    regime_choice: pd.Series,
    *,
    switch_cost: float = 0.0010,
    cash_label: str = "cash",
) -> pd.Series:
    """Combine multiple per-book daily net-return series into one, selecting the
    active book each day from `regime_choice` (a daily Series whose values are
    keys of book_returns, or `cash_label`). On days the active book changes,
    charge `switch_cost` (models the round-trip turnover of switching books).

    book_returns: {name -> daily net return Series}. cash leg = 0.0 return.
    regime_choice MUST be PIT-safe (built from shift>=1 signals). No lookahead.
    """
    all_idx = sorted(set().union(*[s.index for s in book_returns.values()]))
    all_idx = pd.DatetimeIndex(all_idx)
    choice = regime_choice.reindex(all_idx).ffill().fillna(cash_label)
    out = pd.Series(0.0, index=all_idx)
    for name, s in book_returns.items():
        mask = (choice == name)
        out.loc[mask] = s.reindex(all_idx).fillna(0.0).loc[mask]
    # switch cost when the active book changes day-over-day
    changed = (choice != choice.shift(1)).fillna(False)
    out = out - changed.astype(float) * switch_cost
    return out.rename("regime_net")
