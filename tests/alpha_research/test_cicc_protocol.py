"""Tests for the CICC truth-comparison protocol evaluator."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.alpha_research.factor_eval.cicc_protocol import (  # noqa: E402
    CiccProtocolConfig,
    evaluate_cicc_protocol,
    month_end_schedule,
)

RNG = np.random.default_rng(7)
N_STOCKS = 200
DATES = pd.bdate_range("2018-01-01", "2021-12-31")
INSTS = [f"S{i:04d}" for i in range(N_STOCKS)]


def _panel(perfect_factor: bool):
    """Synthetic monthly world: returns realized month->month; factor either
    perfectly rank-predicts next-month returns or is pure noise."""
    sched = month_end_schedule(DATES)
    close = pd.DataFrame(np.nan, index=DATES, columns=INSTS)
    factor = pd.DataFrame(np.nan, index=DATES, columns=INSTS)
    prices = np.full(N_STOCKS, 100.0)
    for i, t in enumerate(sched):
        close.loc[t] = prices
        if i + 1 < len(sched):
            # next-month per-stock return: spread by rank + noise-free
            ranks = RNG.permutation(N_STOCKS)
            rets = -0.10 + 0.20 * ranks / (N_STOCKS - 1)
            if perfect_factor:
                factor.loc[t] = ranks.astype(float)
            else:
                factor.loc[t] = RNG.normal(size=N_STOCKS)
            prices = prices * (1.0 + rets)
    close = close.ffill()
    universe = pd.DataFrame(True, index=DATES, columns=INSTS)
    return factor, close, universe, sched


class TestMonthEndSchedule:
    def test_last_trading_day_per_month(self):
        sched = month_end_schedule(DATES, start="2018-01-01", end="2018-06-30")
        assert len(sched) == 6
        assert sched[0] == pd.Timestamp("2018-01-31")
        assert sched[4] == pd.Timestamp("2018-05-31")

    def test_window_clamp(self):
        sched = month_end_schedule(DATES, start="2021-01-01")
        assert sched.min() >= pd.Timestamp("2021-01-01")


class TestEvaluate:
    def test_perfect_factor_metrics(self):
        factor, close, universe, sched = _panel(perfect_factor=True)
        res = evaluate_cicc_protocol(factor, close, universe, schedule=sched)
        # perfect rank prediction: IC == 1 every period
        assert res.ic_mean == pytest.approx(1.0, abs=1e-9)
        assert res.p_ic_pos == 1.0 and res.p_ic_gt2 == 1.0
        assert res.direction == 1
        assert res.monotonicity == pytest.approx(1.0, abs=1e-9)
        # group 10 earns the top decile of the -10%..+10% spread
        assert res.group_ann[-1] > res.group_ann[0]
        assert res.long_ann > 1.0  # ~+9% monthly compounds hugely
        assert res.n_periods == len(sched) - 1
        assert len(res.group_ann) == 10 and len(res.group_mean_count) == 10
        assert all(c == pytest.approx(20.0) for c in res.group_mean_count)
        # IC==1 every month -> zero std -> IR undefined? std==0 -> nan guard
        assert res.ic_ir != res.ic_ir or res.ic_ir > 0

    def test_noise_factor_is_insignificant(self):
        factor, close, universe, sched = _panel(perfect_factor=False)
        res = evaluate_cicc_protocol(factor, close, universe, schedule=sched)
        assert abs(res.ic_mean) < 0.05
        assert abs(res.ic_t) < 2.5
        assert abs(res.monotonicity) < 0.9

    def test_negative_factor_long_leg_is_group1(self):
        factor, close, universe, sched = _panel(perfect_factor=True)
        res = evaluate_cicc_protocol(-factor, close, universe, schedule=sched)
        assert res.direction == -1
        assert res.ic_mean == pytest.approx(-1.0, abs=1e-9)
        # long leg = group 1 (lowest of the negated factor = best stocks)
        assert res.long_ann > 1.0

    def test_pinned_direction_overrides_ic_sign(self):
        factor, close, universe, sched = _panel(perfect_factor=True)
        res = evaluate_cicc_protocol(
            factor, close, universe, schedule=sched,
            config=CiccProtocolConfig(direction=-1),
        )
        assert res.direction == -1
        assert res.long_ann < 0  # deliberately wrong side loses

    def test_universe_mask_scopes_cross_section(self):
        factor, close, universe, sched = _panel(perfect_factor=True)
        universe.iloc[:, 100:] = False  # only first 100 names eligible
        res = evaluate_cicc_protocol(factor, close, universe, schedule=sched)
        assert all(c == pytest.approx(10.0) for c in res.group_mean_count)

    def test_too_few_periods_raises(self):
        factor, close, universe, sched = _panel(perfect_factor=True)
        with pytest.raises(ValueError, match="usable periods"):
            evaluate_cicc_protocol(factor, close, universe, schedule=sched[:6])

    def test_benchmark_series_used_for_excess(self):
        factor, close, universe, sched = _panel(perfect_factor=True)
        zero_bench = pd.Series(0.0, index=sched[:-1])
        res_b = evaluate_cicc_protocol(factor, close, universe, schedule=sched,
                                       benchmark_monthly=zero_bench)
        # zero benchmark -> excess == long annualized exactly
        assert res_b.long_excess_ann == pytest.approx(res_b.long_ann, rel=1e-9)

    def test_turnover_zero_when_membership_static(self):
        # constant factor ranks every month -> identical long group -> turnover 0
        sched = month_end_schedule(DATES)
        close = pd.DataFrame(np.nan, index=DATES, columns=INSTS)
        prices = np.full(N_STOCKS, 100.0)
        static_ranks = np.arange(N_STOCKS, dtype=float)
        factor = pd.DataFrame(np.nan, index=DATES, columns=INSTS)
        rng2 = np.random.default_rng(11)
        for i, t in enumerate(sched):
            close.loc[t] = prices
            factor.loc[t] = static_ranks
            prices = prices * (1.0 + rng2.normal(0.0, 0.03, N_STOCKS))
        close = close.ffill()
        universe = pd.DataFrame(True, index=DATES, columns=INSTS)
        res = evaluate_cicc_protocol(factor, close, universe, schedule=sched)
        assert res.long_turnover == pytest.approx(0.0, abs=1e-12)

    def test_to_row_has_cicc_columns(self):
        factor, close, universe, sched = _panel(perfect_factor=True)
        row = evaluate_cicc_protocol(factor, close, universe, schedule=sched).to_row()
        for col in ("IC均值", "IC_IR", "t值", "多头年化", "多头超额", "超额回撤", "换手", "单调性"):
            assert col in row
