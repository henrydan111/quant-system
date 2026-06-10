"""Tests for the P0a leak-safe unified-eval core (src/alpha_research/factor_eval/unified_eval.py).

Covers the two correctness-critical fixes from the 2026-06-10 GPT 5.5 Pro review:
  - leak_safe_decay_ic_vector: each horizon independently is_end-clipped (NO post-is_end label).
  - resolve_orientation: NON-circular — never the observed registry direction; train-window sign only.
Plus the promoted classify_quantile_shape classifier (canonical shapes + insufficient-quantiles guard).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.alpha_research.factor_eval.unified_eval import (
    EvalMethodology,
    classify_quantile_shape,
    hac_mean_tstat,
    leak_safe_decay_ic_vector,
    long_leg_excess_ir,
    moving_block_bootstrap_mean_ci,
    one_way_turnover,
    residual_ic_vs_controls,
    resolve_orientation,
)


# ----------------------------------------------------------------- classify_quantile_shape
@pytest.mark.parametrize("returns,expected", [
    ([1, 2, 3, 4, 5], "monotonic_up"),
    ([5, 4, 3, 2, 1], "monotonic_down"),
    ([1, 2, 3, 4, 2], "top_reversal"),       # body up, top inverts (the eps_diffusion pattern)
    ([4, 2, 3, 4, 5], "bottom_reversal"),    # -+++
    ([5, 2, 1, 2, 5], "U_shape"),            # --++
    ([1, 4, 5, 4, 1], "inverted_U"),         # ++--
    ([3, 3.1, 2.9, 3.05, 2.95], "irregular"),
])
def test_classify_shape_canonical(returns, expected):
    out = classify_quantile_shape(returns)
    assert out["mono_shape"] == expected
    assert out["mono_reason"] is None
    assert 0.0 <= out["mono_frac_dominant"] <= 1.0


def test_classify_shape_insufficient_quantiles():
    out = classify_quantile_shape([1.0, 2.0])  # discrete/tie-heavy → <3 buckets
    assert out["mono_shape"] is None
    assert out["mono_step_signs"] is None
    assert out["mono_reason"].startswith("insufficient_quantiles(n=2)")


def test_classify_shape_top_reversal_real_eps_values():
    # the real earn_eps_diffusion_60 quantile-return curve from the probe
    out = classify_quantile_shape([2.4623, 3.3777, 3.9219, 4.7043, 2.3085])
    assert out["mono_shape"] == "top_reversal"
    assert out["mono_step_signs"] == "+++-"


# ----------------------------------------------------------------- resolve_orientation (non-circular)
def test_orientation_economic_prior_wins():
    # economic prior overrides any data sign
    dates = pd.date_range("2020-01-01", periods=10, freq="D")
    ic = pd.Series(np.linspace(0.1, 0.2, 10), index=dates)  # positive in-data
    out = resolve_orientation(ic, train_dates=dates, economic_prior=-1)
    assert out["sign"] == -1.0
    assert out["direction_source"] == "economic_prior"


def test_orientation_train_fold_ignores_heldout_sign():
    # CRITICAL non-circularity: train window is POSITIVE, heldout/full-sample is NEGATIVE.
    # The resolver must return the TRAIN sign (+1), never the full-sample observed sign.
    dates = pd.date_range("2020-01-01", periods=20, freq="D")
    train_dates = dates[:10]
    vals = np.concatenate([np.full(10, +0.05), np.full(10, -0.30)])  # full mean < 0
    ic = pd.Series(vals, index=dates)
    assert ic.mean() < 0  # the (circular) full-sample sign would be NEGATIVE
    out = resolve_orientation(ic, train_dates=train_dates)
    assert out["sign"] == 1.0  # train-only sign is POSITIVE → non-circular
    assert out["direction_source"] == "train_fold"


def test_orientation_undetermined_on_zero():
    dates = pd.date_range("2020-01-01", periods=10, freq="D")
    ic = pd.Series(np.zeros(10), index=dates)
    out = resolve_orientation(ic, train_dates=dates)
    assert out["sign"] == 1.0
    assert out["direction_source"] == "undetermined"


# ----------------------------------------------------------------- leak_safe_decay_ic_vector
def _synthetic_panel(n_days=100, n_inst=35, is_end_pos=80, seed=0):
    """Synthetic (instrument, datetime) factor + adj_close capped at is_end, on an injected calendar."""
    cal = pd.bdate_range("2020-01-01", periods=n_days)
    is_end = cal[is_end_pos]
    factor_dates = cal[: is_end_pos + 1]  # through is_end
    insts = [f"{i:06d}_SZ" for i in range(n_inst)]
    idx = pd.MultiIndex.from_product([insts, factor_dates], names=["instrument", "datetime"])
    rng = np.random.default_rng(seed)
    factor = pd.Series(rng.normal(size=len(idx)), index=idx, name="f")
    # adj_close: random-walk-ish positive prices, capped at is_end (NO data past is_end)
    base = pd.Series(100 + rng.normal(size=len(idx)).cumsum() * 0.0, index=idx)
    adj = (base + rng.uniform(50, 150, size=len(idx))).rename("adj")
    return factor, adj, is_end, list(cal)


def test_decay_is_leak_safe_per_horizon():
    factor, adj, is_end, cal = _synthetic_panel()
    out = leak_safe_decay_ic_vector(
        factor, adj, is_end=is_end, horizons=(5, 10, 20, 40), trade_cal=cal, min_obs=10
    )
    vec = out["vector"]
    # (1) NO horizon's label realizes past is_end
    for h, v in vec.items():
        assert pd.Timestamp(v["max_realization"]) <= pd.Timestamp(is_end), f"h={h} leaks past is_end"
    # (2) longer horizon drops MORE tail factor dates (fewer usable dates)
    assert vec[40]["n_dates"] < vec[20]["n_dates"] < vec[5]["n_dates"]
    # (3) all horizons produced a vector entry + the leak-safe note
    assert set(vec) == {5, 10, 20, 40}
    assert "leak-safe" in out["note"]


def test_decay_rejects_uncapped_inputs():
    # adj_close extending PAST is_end must be rejected by the underlying builder (belt 0)
    from src.alpha_research.factor_lifecycle.walk_forward_validation import IsEndLeakageError
    factor, adj, is_end, cal = _synthetic_panel()
    earlier_is_end = cal[60]  # factor/adj extend to cal[80] > cal[60]
    with pytest.raises(IsEndLeakageError):
        leak_safe_decay_ic_vector(factor, adj, is_end=earlier_is_end, horizons=(5,), trade_cal=cal)


# ----------------------------------------------------------------- P0b: HAC / block bootstrap
def _ar1(rho=0.6, T=500, mean=0.3, seed=0):
    rng = np.random.default_rng(seed)
    e = rng.normal(size=T)
    x = np.empty(T)
    x[0] = e[0]
    for i in range(1, T):
        x[i] = rho * x[i - 1] + e[i]
    return pd.Series(x + mean)


def test_hac_se_exceeds_iid_for_positive_autocorrelation():
    # THE point of HAC: overlapping/serially-correlated labels inflate the IID t-stat. A positively
    # autocorrelated series must get a LARGER HAC SE than the naive IID SE → a smaller, honest t.
    x = _ar1(rho=0.6, T=500)
    hac = hac_mean_tstat(x, lags=40)
    iid_se = float(x.std(ddof=1) / np.sqrt(len(x)))
    assert hac["hac_se"] > iid_se
    assert hac["hac_t"] is not None and hac["hac_p"] is not None
    assert hac["lags"] == 40


def test_hac_constant_series_is_degenerate():
    out = hac_mean_tstat(pd.Series([2.0] * 50), lags=20)
    assert out["hac_se"] is None and out["hac_t"] is None


def test_block_bootstrap_brackets_mean_and_is_deterministic():
    x = _ar1(rho=0.5, T=300)
    a = moving_block_bootstrap_mean_ci(x, block_len=20, n_boot=500, seed=1)
    b = moving_block_bootstrap_mean_ci(x, block_len=20, n_boot=500, seed=1)
    assert a["ci_low"] < a["mean"] < a["ci_high"]
    assert a["ci_low"] == b["ci_low"] and a["ci_high"] == b["ci_high"]  # seeded → deterministic


# ----------------------------------------------------------------- P0c: turnover + long-leg excess
def _cs_panel(n_inst=50, n_days=200, seed=0):
    insts = [f"{i:06d}_SZ" for i in range(n_inst)]
    dates = pd.bdate_range("2020-01-01", periods=n_days)
    idx = pd.MultiIndex.from_product([dates, insts], names=["datetime", "instrument"])
    return idx, dates, insts


def test_turnover_static_near_zero_rotating_high():
    idx, dates, insts = _cs_panel()
    # static rank (factor = instrument position, same every date) → top bucket never changes
    static = pd.Series(np.tile(np.arange(len(insts)), len(dates)), index=idx, dtype=float)
    t_static = one_way_turnover(static, rebalance_days=20, top_q=0.2)
    assert t_static["turnover_ann"] < 0.5  # ≈ 0
    # fully random each date → top bucket churns
    rng = np.random.default_rng(0)
    rot = pd.Series(rng.normal(size=len(idx)), index=idx)
    t_rot = one_way_turnover(rot, rebalance_days=20, top_q=0.2)
    assert t_rot["turnover_ann"] > t_static["turnover_ann"]
    assert 0.0 <= t_rot["tie_rate"] <= 1.0


def test_long_leg_excess_positive_when_top_beats_benchmark():
    idx, dates, insts = _cs_panel()
    rng = np.random.default_rng(1)
    factor = pd.Series(rng.normal(size=len(idx)), index=idx)
    # label correlated with factor → the top bucket has high forward return
    label = pd.Series(0.5 * factor.to_numpy() + rng.normal(size=len(idx)) * 0.01, index=idx)
    zero_bench = pd.Series(0.0, index=pd.DatetimeIndex(dates))
    out = long_leg_excess_ir(factor, label, zero_bench, top_q=0.2, cost_bps_per_turnover=0.0,
                             rebalance_days=20)
    assert out["long_leg_excess_ann"] > 0
    assert out["long_leg_excess_ir_proxy_is"] > 0


# ----------------------------------------------------------------- round-2 GPT 5.5 Pro fixes
def test_hac_formula_exact_small_vector():
    # independently recompute the Newey-West Bartlett estimator and match the function exactly
    x = np.array([1.0, 2.0, 4.0, 8.0])
    T, L = len(x), 2
    e = x - x.mean()
    g0 = (e @ e) / T
    omega = g0 + 2.0 * sum((1 - l / (L + 1)) * (e[l:] @ e[:-l]) / T for l in range(1, L + 1))
    se_exp = float(np.sqrt(omega / T))
    out = hac_mean_tstat(pd.Series(x), lags=2)
    assert out["hac_se"] == pytest.approx(se_exp, rel=1e-9)
    assert out["hac_t"] == pytest.approx(x.mean() / se_exp, rel=1e-9)


def test_hac_rejects_negative_lags():
    with pytest.raises(ValueError):
        hac_mean_tstat(pd.Series([1.0, 2.0, 3.0]), lags=-1)


def test_orientation_weak_signal_is_undetermined():
    # tiny noisy train mean → HAC |t| < 1 → must NOT manufacture a sign
    rng = np.random.default_rng(3)
    dates = pd.date_range("2020-01-01", periods=60, freq="D")
    ic = pd.Series(rng.normal(0.02, 1.0, 60), index=dates)  # |t| ≈ 0.15
    out = resolve_orientation(ic, train_dates=dates, min_train_t=1.0)
    assert out["direction_source"] == "undetermined"
    assert out["orientation_valid"] is False


def test_true_weight_turnover_differs_from_membership_churn():
    from src.alpha_research.factor_eval.unified_eval import _one_way_weight_turnover
    prev, cur = set(range(100)), set(range(200))  # cur ⊇ prev, sizes drift 100→200
    # true equal-weight one-way turnover = 0.5 (NOT the membership churn 100/300 = 0.333)
    assert _one_way_weight_turnover(cur, prev) == pytest.approx(0.5)


def test_long_leg_excess_fails_closed_on_missing_benchmark():
    idx, dates, insts = _cs_panel()
    rng = np.random.default_rng(2)
    factor = pd.Series(rng.normal(size=len(idx)), index=idx)
    label = pd.Series(rng.normal(size=len(idx)), index=idx)
    partial_bench = pd.Series(0.0, index=pd.DatetimeIndex(dates[:50]))  # misses rebal date day 60
    with pytest.raises(ValueError):
        long_leg_excess_ir(factor, label, partial_bench, rebalance_days=20)


# ----------------------------------------------------------------- P1a: methodology freeze + residual
def _methodology(**kw):
    base = dict(is_start="2014-01-01", is_end="2020-12-31",
                reference_set_stable=("a", "b"), reference_set_current=("a", "b", "c"),
                provisional_factors=("c",))
    base.update(kw)
    return EvalMethodology(**base)


def test_methodology_hash_membership_stable_and_field_sensitive():
    m1 = _methodology(reference_set_stable=("a", "b"), reference_set_current=("a", "b", "c"))
    m2 = _methodology(reference_set_stable=("b", "a"), reference_set_current=("c", "b", "a"))  # reorder
    assert m1.methodology_hash == m2.methodology_hash  # membership, not order
    assert _methodology(cost_bps_per_turnover=30.0).methodology_hash != m1.methodology_hash
    assert _methodology(hac_lags=60).methodology_hash != m1.methodology_hash
    assert len(m1.methodology_hash) == 16


def test_residual_ic_orthogonal_retains_redundant_collapses():
    idx, dates, insts = _cs_panel(n_inst=60, n_days=80)
    rng = np.random.default_rng(7)
    c1 = pd.Series(rng.normal(size=len(idx)), index=idx)
    c2 = pd.Series(rng.normal(size=len(idx)), index=idx)
    new = pd.Series(rng.normal(size=len(idx)), index=idx)              # ⊥ controls
    combo = 0.7 * c1 + 0.3 * c2                                        # a linear combo of controls
    label = pd.Series(0.5 * new.to_numpy() + rng.normal(size=len(idx)) * 0.05, index=idx)  # driven by `new`
    fd = {"c1": c1, "c2": c2, "new": new, "combo": combo}
    orth = residual_ic_vs_controls("new", fd, label, control_names=["c1", "c2"], min_obs=20)
    redun = residual_ic_vs_controls("combo", fd, label, control_names=["c1", "c2"], min_obs=20)
    # the orthogonal-new factor keeps its predictive info after residualizing; the control-combo loses it
    assert abs(orth["residual_mean_rank_ic"]) > abs(redun["residual_mean_rank_ic"])
    assert orth["residual_coverage"] == pytest.approx(1.0, abs=0.02)  # synthetic = full coverage
    assert orth["n_controls"] == 2
