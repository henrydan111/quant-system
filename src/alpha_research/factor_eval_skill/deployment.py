"""D3 — deployable-form construction + event-driven wrapper, extracted from
``eval_e_wave_v2_deployment.py``.

Design: ``workspace/research/factor_eval_methodology/FACTOR_EVAL_PARTG_BUILD_DESIGN.md``
(v2, D3). Layers:

  * :func:`direction_aligned_composite` — the PURE deployable form (lifted verbatim from the
    script's ``composite_ranked``): a direction-aligned equal-weight z-score composite inside
    the liquid top-N, high = long. Unit-tested.
  * :func:`build_ranked_schedule` — builds the ``{date: [codes]}`` rebalance schedule + the
    membership turnover from a panel. Semi-pure (a ``st_codes_resolver`` callback supplies the
    ST set per date). Unit-tested with a synthetic panel.
  * :func:`run_deployment` — the SLOW event-driven orchestration (``EventDrivenBacktester``,
    1× / realistic costs). The Stage-8 deployability gate; deployability is a STRATEGY property,
    NOT a factor status. The liquid universe + composite are plan parameters.

This is where a microcap-driven gross sealed-OOS number gets haircut to the deployable figure
(the E-wave 6-core collapsed here: −3.6% CAGR / −52% MDD on the liquid universe).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import pandas as pd

DEFAULT_LIQ_TOPN = 300
DEFAULT_MIN_FACTORS = 3
DEFAULT_MIN_NAMES = 50


def direction_aligned_composite(
    day: pd.DataFrame,
    members: Sequence[tuple[str, int]],
    *,
    liq_topn: int = DEFAULT_LIQ_TOPN,
    min_factors: int = DEFAULT_MIN_FACTORS,
    min_names: int = DEFAULT_MIN_NAMES,
    st_codes: Sequence[str] = (),
    liq_col: str = "amt20",
    price_col: str = "close",
    amount_col: str = "amount",
) -> pd.Series | None:
    """Direction-aligned equal-weight z-score composite within the liquid top-N; high = long.

    ``day`` = a single-date, instrument-indexed panel with the member factor columns +
    ``liq_col`` (trailing $-vol) + ``price_col`` + ``amount_col``. ``members`` =
    ``[(factor_id, sign)]`` where ``sign=-1`` negates a held-short factor so high = long.
    Returns the ranked composite (descending) or ``None`` if the day is untradeable/too thin.
    Lifted verbatim from the E-wave script ``composite_ranked``."""
    liq = day[liq_col].dropna().sort_values(ascending=False).head(liq_topn).index
    sub = day.loc[liq]
    sub = sub[sub[price_col].notna() & (sub[amount_col].fillna(0) > 0)]  # tradeable on rebal day
    st = {str(c).upper() for c in st_codes}
    if st:
        sub = sub[~sub.index.map(lambda c: str(c).upper() in st)]
    if len(sub) < min_names:
        return None
    zs = []
    for fid, sign in members:
        col = sub[fid].astype(float)
        sd = col.std()
        if sd and np.isfinite(sd) and sd > 0:
            zs.append(sign * (col - col.mean()) / sd)
    if not zs:
        return None
    Z = pd.concat(zs, axis=1)
    comp = Z.mean(axis=1).where(Z.notna().sum(axis=1) >= min_factors)  # need >= min_factors present
    return comp.dropna().sort_values(ascending=False)  # high composite = long


def build_ranked_schedule(
    panel: pd.DataFrame,
    members: Sequence[tuple[str, int]],
    rebalance_dates: Sequence[Any],
    topk: int,
    *,
    st_codes_resolver: Callable[[Any], Sequence[str]] | None = None,
    headroom_mult: int = 3,
    **composite_kwargs: Any,
) -> tuple[dict, float]:
    """Build a ``{Timestamp: [codes]}`` ranked schedule + mean membership turnover.

    ``panel`` is a ``(datetime, instrument)``-indexed factor panel; for each rebalance date it
    slices the day, builds :func:`direction_aligned_composite`, and records the top ``headroom``
    codes (engine fallback room) + the top-``topk`` membership (for turnover). ``st_codes_resolver``
    supplies the ST set per date (default: none)."""
    headroom = topk * headroom_mult
    sched: dict = {}
    members_by_date: dict = {}
    resolver = st_codes_resolver or (lambda _d: ())
    for d in rebalance_dates:
        try:
            day = panel.xs(d, level=0)
        except KeyError:
            sched[pd.Timestamp(d)] = []
            continue
        ranked = direction_aligned_composite(day, members, st_codes=resolver(d), **composite_kwargs)
        if ranked is None:
            sched[pd.Timestamp(d)] = []
            continue
        sched[pd.Timestamp(d)] = [str(i).upper().replace("_", ".") for i in ranked.head(headroom).index]
        members_by_date[pd.Timestamp(d)] = set(ranked.head(topk).index)
    keys = sorted(members_by_date)
    churn = [
        len(members_by_date[keys[i]] - members_by_date[keys[i - 1]]) / max(len(members_by_date[keys[i]]), 1)
        for i in range(1, len(keys))
        if members_by_date[keys[i]]
    ]
    return sched, (float(np.mean(churn)) if churn else float("nan"))


@dataclass(frozen=True)
class DeploymentMetrics:
    metrics: dict
    schedule_monthly_turnover: float


def run_deployment(
    *,
    panel: pd.DataFrame,
    members: Sequence[tuple[str, int]],
    rebalance_dates: Sequence[Any],
    topk: int,
    start_time: str,
    end_time: str,
    data_dir: str,
    benchmark: str,
    capital: float,
    exchange_config: Any,
    volume_limit: float,
    preload_fields: Sequence[str],
    goal_metrics: Callable[[pd.Series, pd.Series | None], dict],
    st_codes_resolver: Callable[[Any], Sequence[str]] | None = None,
    slippage: Any = None,
    **composite_kwargs: Any,
) -> DeploymentMetrics:
    """SLOW event-driven deployment run (the Stage-8 gate). Thin wrapper over
    ``EventDrivenBacktester`` + ``RankedFallbackStrategy``; ``goal_metrics`` is injected
    (the research_utils metric fn) so this module stays free of the workspace research dep."""
    from src.backtest_engine.event_driven import EventDrivenBacktester
    from src.backtest_engine.event_driven.strategies import RankedFallbackStrategy

    sched, sched_turn = build_ranked_schedule(
        panel, members, rebalance_dates, topk, st_codes_resolver=st_codes_resolver, **composite_kwargs
    )
    bt = EventDrivenBacktester(data_dir=data_dir)
    res = bt.run(
        strategy=RankedFallbackStrategy(sched, topk=topk), start_time=start_time, end_time=end_time,
        benchmark=benchmark, account=capital, exchange_config=exchange_config, slippage=slippage,
        volume_limit=volume_limit, preload_fields=list(preload_fields),
    )
    rep = res.report.copy()
    if "date" in rep.columns:
        rep = rep.set_index(pd.to_datetime(rep["date"]))
    net = rep["return"].astype(float)
    bench = rep["bench_return"].astype(float) if "bench_return" in rep.columns else None
    m = goal_metrics(net, bench)
    m["calmar"] = m["cagr"] / abs(m["mdd"]) if m.get("mdd", 0) < 0 else float("nan")
    m["sched_monthly_turnover"] = round(sched_turn, 3)
    m.update(topk=topk)
    return DeploymentMetrics(metrics=m, schedule_monthly_turnover=float(sched_turn))
