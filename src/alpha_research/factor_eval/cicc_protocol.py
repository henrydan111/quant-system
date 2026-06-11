"""CICC-handbook evaluation protocol — the truth-comparison standard (对照层).

Implements the EXACT methodology of the 中金因子手册 effectiveness tables so our
replicated factors can be compared cell-by-cell against the transcribed truth values
(Knowledge/AI量化增强/CICC_因子表现真值.md). This is deliberately NOT our formal
methodology (no HAC, no heldout split, no neutralization, gross returns): during the
Phase-C calibration every methodological variable is pinned to CICC's published
protocol so residual mismatches isolate to factor construction or underlying data.

Documented protocol knobs (图表2/3 指标说明):
    - monthly rebalance; factor sampled at the rebalance cross-section
    - IC = Spearman rank corr(factor_t, next-period stock return)
    - t值 = plain t of the monthly IC series (non-overlapping, so plain t is valid)
    - 10 equal-count groups, ascending factor value (group 1 lowest)
    - 单调性 = Spearman(group index, group annualized return)
    - long leg (多头) = the best group per the factor's FULL-WINDOW IC sign
      (in-sample direction — CICC's own convention; fine for the对照 layer only)
    - gross returns, no costs

Dark knobs (NOT in the handbook — calibrated in Phase C, then frozen):
    - rebalance timing: factor at month-end close, return month-end -> month-end
    - benchmark for 超额: universe equal-weight (全市场域) or the index itself
    - group weighting: equal-weight within groups
    - 换手: single-side long-group membership turnover per rebalance

Evidence produced here is descriptive/refresh-class only — NEVER a promotion input.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CiccProtocolConfig:
    n_groups: int = 10
    min_names: int = 30          # skip rebalance cross-sections thinner than this
    annualization: int = 12      # monthly periods
    direction: int | None = None  # +1/-1 to pin a priori; None = full-window IC sign


@dataclass
class CiccFactorResult:
    """One factor × one universe, CICC-comparable columns."""

    ic_mean: float
    ic_ir: float
    ic_t: float
    p_ic_pos: float
    p_ic_gt2: float
    p_ic_neg: float
    p_ic_ltm2: float
    n_periods: int
    direction: int
    long_ann: float
    long_excess_ann: float
    excess_mdd: float
    long_turnover: float
    monotonicity: float
    group_ann: list  # length n_groups, ascending factor order
    group_mean_count: list
    ic_series: pd.Series = field(repr=False, default=None)

    def to_row(self) -> dict:
        return {
            "IC均值": self.ic_mean, "IC_IR": self.ic_ir, "t值": self.ic_t,
            "P(IC>0)": self.p_ic_pos, "P(IC>0.02)": self.p_ic_gt2,
            "P(IC<0)": self.p_ic_neg, "P(IC<-0.02)": self.p_ic_ltm2,
            "多头年化": self.long_ann, "多头超额": self.long_excess_ann,
            "超额回撤": self.excess_mdd, "换手": self.long_turnover,
            "单调性": self.monotonicity, "n_periods": self.n_periods,
            "direction": self.direction,
        }


def month_end_schedule(dates: pd.DatetimeIndex, start=None, end=None) -> pd.DatetimeIndex:
    """Last trading date per calendar month within [start, end]."""
    d = dates
    if start is not None:
        d = d[d >= pd.Timestamp(start)]
    if end is not None:
        d = d[d <= pd.Timestamp(end)]
    s = pd.Series(d, index=d)
    return pd.DatetimeIndex(s.groupby([d.year, d.month]).max().to_numpy())


def _annualize(monthly: pd.Series, periods: int = 12) -> float:
    """Geometric annualization of a monthly return series."""
    m = monthly.dropna()
    if m.empty:
        return float("nan")
    total = float((1.0 + m).prod())
    if total <= 0:
        return -1.0
    return total ** (periods / len(m)) - 1.0


def _max_drawdown(curve: pd.Series) -> float:
    """Max drawdown (negative number) of a cumulative-growth curve."""
    if curve.empty:
        return float("nan")
    peak = curve.cummax()
    return float((curve / peak - 1.0).min())


def evaluate_cicc_protocol(
    factor: pd.DataFrame,
    close: pd.DataFrame,
    universe: pd.DataFrame,
    *,
    schedule: pd.DatetimeIndex,
    benchmark_monthly: pd.Series | None = None,
    config: CiccProtocolConfig = CiccProtocolConfig(),
) -> CiccFactorResult:
    """Run the CICC monthly 10-group protocol for one factor on one universe.

    Args:
        factor: wide (dates × instruments) factor values, FULL-MARKET computed
            (Layer-1) — the universe mask scopes it here (Layer-2/3).
        close: wide ADJUSTED close (total-return basis is a calibration knob; pass
            whatever basis the calibration freezes).
        universe: wide boolean mask (build_universe_mask output).
        schedule: rebalance dates (month-ends); period return runs schedule[i] ->
            schedule[i+1].
        benchmark_monthly: per-period benchmark return aligned to ``schedule[:-1]``
            (the entry date indexes the period). None -> universe equal-weight mean.

    Returns CiccFactorResult; raises ValueError when fewer than 12 usable periods.
    """
    cfg = config
    ics: list[float] = []
    period_idx: list[pd.Timestamp] = []
    group_rets: dict[int, list[float]] = {g: [] for g in range(1, cfg.n_groups + 1)}
    group_counts: dict[int, list[int]] = {g: [] for g in range(1, cfg.n_groups + 1)}
    long_members_hist: dict[pd.Timestamp, dict[int, pd.Index]] = {}
    bench_rets: list[float] = []

    sched = pd.DatetimeIndex(schedule).sort_values()
    for i in range(len(sched) - 1):
        t0, t1 = sched[i], sched[i + 1]
        if t0 not in factor.index or t0 not in close.index or t1 not in close.index:
            continue
        elig = universe.loc[t0] if t0 in universe.index else None
        if elig is None:
            continue
        f = factor.loc[t0].where(elig)
        p0, p1 = close.loc[t0], close.loc[t1]
        ret = p1 / p0 - 1.0
        df = pd.DataFrame({"f": f, "r": ret}).dropna()
        if len(df) < cfg.min_names:
            continue

        ic = stats.spearmanr(df["f"], df["r"]).statistic
        if ic != ic:
            continue
        ics.append(float(ic))
        period_idx.append(t0)

        labels = pd.qcut(df["f"].rank(method="first"), cfg.n_groups, labels=False)
        members: dict[int, pd.Index] = {}
        for g in range(cfg.n_groups):
            sel = df[labels == g]
            group_rets[g + 1].append(float(sel["r"].mean()))
            group_counts[g + 1].append(int(len(sel)))
            members[g + 1] = sel.index
        long_members_hist[t0] = members

        bench_rets.append(
            float(benchmark_monthly.loc[t0]) if benchmark_monthly is not None and t0 in benchmark_monthly.index
            else float(df["r"].mean())
        )

    n = len(ics)
    if n < 12:
        raise ValueError(f"cicc_protocol: only {n} usable periods (<12)")

    ic_arr = np.asarray(ics)
    ic_mean = float(ic_arr.mean())
    ic_std = float(ic_arr.std(ddof=1))
    ic_ir = ic_mean / ic_std if ic_std > 0 else float("nan")
    ic_t = ic_ir * math.sqrt(n) if ic_ir == ic_ir else float("nan")

    direction = cfg.direction if cfg.direction in (1, -1) else (1 if ic_mean >= 0 else -1)
    long_g = cfg.n_groups if direction > 0 else 1

    idx = pd.DatetimeIndex(period_idx)
    long_monthly = pd.Series(group_rets[long_g], index=idx)
    bench_monthly = pd.Series(bench_rets, index=idx)
    excess_monthly = long_monthly - bench_monthly

    long_ann = _annualize(long_monthly, cfg.annualization)
    # CICC's 多头超额 is the annualized active return; geometric difference of the
    # compounded curves is the calibration default (a dark knob — see module doc).
    bench_ann = _annualize(bench_monthly, cfg.annualization)
    long_excess_ann = (1.0 + long_ann) / (1.0 + bench_ann) - 1.0 if bench_ann == bench_ann else float("nan")
    excess_curve = (1.0 + excess_monthly).cumprod()
    excess_mdd = _max_drawdown(excess_curve)

    # single-side membership turnover of the long group, averaged over rebalances
    turns: list[float] = []
    prev: pd.Index | None = None
    for t in idx:
        cur = long_members_hist[t][long_g]
        if prev is not None and len(cur):
            turns.append(1.0 - len(prev.intersection(cur)) / len(cur))
        prev = cur
    long_turnover = float(np.mean(turns)) if turns else float("nan")

    group_ann = [_annualize(pd.Series(group_rets[g], index=idx), cfg.annualization)
                 for g in range(1, cfg.n_groups + 1)]
    mono = float(stats.spearmanr(np.arange(1, cfg.n_groups + 1), group_ann).statistic)

    return CiccFactorResult(
        ic_mean=ic_mean, ic_ir=ic_ir, ic_t=ic_t,
        p_ic_pos=float((ic_arr > 0).mean()), p_ic_gt2=float((ic_arr > 0.02).mean()),
        p_ic_neg=float((ic_arr < 0).mean()), p_ic_ltm2=float((ic_arr < -0.02).mean()),
        n_periods=n, direction=direction,
        long_ann=long_ann, long_excess_ann=long_excess_ann,
        excess_mdd=excess_mdd, long_turnover=long_turnover,
        monotonicity=mono, group_ann=group_ann,
        group_mean_count=[float(np.mean(group_counts[g])) for g in range(1, cfg.n_groups + 1)],
        ic_series=pd.Series(ic_arr, index=idx),
    )
