"""
Unit tests for src/alpha_research/factor_eval/

Uses synthetic data with known properties to validate correctness
of IC, quantile, neutralization, decay, and correlation functions.
"""

import sys
import os
import numpy as np
import pandas as pd

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.alpha_research.factor_eval.ic_analysis import (
    compute_ic_series,
    compute_ic_summary,
    compute_ic_by_year,
    compute_rolling_ic,
    compute_ic_by_group,
    compute_marginal_ic,
)
from src.alpha_research.factor_eval.quantile_analysis import (
    compute_quantile_returns,
    compute_quantile_summary,
    compute_long_short_returns,
    # Aliased: the production name matches pytest's test_* collection pattern,
    # so importing it un-aliased makes pytest collect it as a test and fail
    # with "fixture 'quantile_summary' not found".
    test_monotonicity as check_monotonicity,
)
from src.alpha_research.factor_eval.neutralization import (
    neutralize,
    neutralize_size,
)
from src.alpha_research.factor_eval.correlation import (
    compute_factor_correlation,
    find_redundant_pairs,
    select_uncorrelated,
)


# ─── Helpers ─────────────────────────────────────────────────────

def _make_synthetic_data(n_dates=100, n_stocks=200, seed=42):
    """Create synthetic factor + forward return data with known properties."""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range("2020-01-01", periods=n_dates)
    stocks = [f"SH{i:06d}" for i in range(n_stocks)]

    idx = pd.MultiIndex.from_product([dates, stocks], names=["datetime", "instrument"])

    # True signal + noise
    signal = pd.Series(rng.randn(len(idx)), index=idx, name="factor")
    noise = pd.Series(rng.randn(len(idx)) * 2, index=idx, name="noise")
    forward_return = signal + noise  # corr ~ 1/sqrt(5) ≈ 0.45
    forward_return.name = "fwd"

    return signal, forward_return, dates, stocks, rng


def _make_perfect_signal(n_dates=50, n_stocks=100, seed=42):
    """Factor = forward return (perfect predictor)."""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range("2020-01-01", periods=n_dates)
    stocks = [f"SH{i:06d}" for i in range(n_stocks)]
    idx = pd.MultiIndex.from_product([dates, stocks], names=["datetime", "instrument"])
    values = pd.Series(rng.randn(len(idx)), index=idx)
    return values, values.copy()


def _make_random_signal(n_dates=50, n_stocks=100, seed=42):
    """Factor is pure noise, independent of returns."""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range("2020-01-01", periods=n_dates)
    stocks = [f"SH{i:06d}" for i in range(n_stocks)]
    idx = pd.MultiIndex.from_product([dates, stocks], names=["datetime", "instrument"])
    factor = pd.Series(rng.randn(len(idx)), index=idx)
    fwd = pd.Series(rng.randn(len(idx)), index=idx)
    return factor, fwd


# ─── Tests ───────────────────────────────────────────────────────

def test_ic_perfect_signal():
    """IC should ≈ 1.0 for a perfectly correlated factor."""
    factor, fwd = _make_perfect_signal()
    ic = compute_ic_series(factor, fwd, min_obs=30)
    summary = compute_ic_summary(ic)
    assert abs(summary["mean_ic"] - 1.0) < 0.01, f"Expected IC ≈ 1.0, got {summary['mean_ic']:.4f}"
    print("  ✓ test_ic_perfect_signal PASSED")


def test_ic_random_signal():
    """IC should ≈ 0.0 for random noise."""
    factor, fwd = _make_random_signal()
    ic = compute_ic_series(factor, fwd, min_obs=30)
    summary = compute_ic_summary(ic)
    assert abs(summary["mean_ic"]) < 0.05, f"Expected |IC| < 0.05, got {summary['mean_ic']:.4f}"
    print("  ✓ test_ic_random_signal PASSED")


def test_icir_consistency():
    """ICIR should equal mean(IC) / std(IC)."""
    factor, fwd, _, _, _ = _make_synthetic_data()
    ic = compute_ic_series(factor, fwd, min_obs=30)
    summary = compute_ic_summary(ic)
    manual_icir = ic["IC"].dropna().mean() / ic["IC"].dropna().std()
    assert abs(summary["icir"] - manual_icir) < 1e-10, f"ICIR mismatch: {summary['icir']} vs {manual_icir}"
    print("  ✓ test_icir_consistency PASSED")


def test_ic_by_year():
    """Yearly breakdown should have one row per year."""
    factor, fwd, dates, _, _ = _make_synthetic_data(n_dates=500)
    ic = compute_ic_series(factor, fwd, min_obs=30)
    yearly = compute_ic_by_year(ic)
    expected_years = len(set(dates.year))
    assert len(yearly) == expected_years, f"Expected {expected_years} years, got {len(yearly)}"
    assert "icir" in yearly.columns
    print("  ✓ test_ic_by_year PASSED")


def test_quantile_monotonic():
    """Quantile returns should be monotonically increasing for a good signal."""
    factor, fwd = _make_perfect_signal(n_dates=100, n_stocks=200)
    q_returns = compute_quantile_returns(factor, fwd, n_quantiles=5, min_obs=30)
    q_summary = compute_quantile_summary(q_returns)
    mono = check_monotonicity(q_summary)
    assert mono["is_monotonic"], f"Expected monotonic, got corr={mono['spearman_corr']:.4f}"
    print("  ✓ test_quantile_monotonic PASSED")


def test_quantile_count():
    """Each quantile should have roughly equal stock counts."""
    factor, fwd, _, _, _ = _make_synthetic_data()
    q_returns = compute_quantile_returns(factor, fwd, n_quantiles=5, min_obs=30)
    if q_returns.empty:
        print("  ⚠ test_quantile_count SKIPPED (no data)")
        return
    avg_counts = q_returns.groupby("quantile")["count"].mean()
    expected = avg_counts.mean()
    for q, c in avg_counts.items():
        assert abs(c - expected) / expected < 0.15, f"Q{q} count {c} deviates from {expected}"
    print("  ✓ test_quantile_count PASSED")


def test_long_short_returns():
    """L/S returns should be positive for a good signal."""
    factor, fwd = _make_perfect_signal(n_dates=100, n_stocks=200)
    q_returns = compute_quantile_returns(factor, fwd, n_quantiles=5, min_obs=30)
    ls = compute_long_short_returns(q_returns)
    assert ls.mean() > 0, f"Expected positive L/S mean, got {ls.mean():.6f}"
    print("  ✓ test_long_short_returns PASSED")


def test_neutralize_removes_exposure():
    """Neutralized factor should have zero beta to control variable."""
    rng = np.random.RandomState(42)
    n_dates, n_stocks = 50, 200
    dates = pd.bdate_range("2020-01-01", periods=n_dates)
    stocks = [f"SH{i:06d}" for i in range(n_stocks)]
    idx = pd.MultiIndex.from_product([dates, stocks], names=["datetime", "instrument"])

    mcap = pd.Series(np.exp(rng.randn(len(idx)) + 10), index=idx)
    log_mcap = np.log(mcap)
    pure_alpha = pd.Series(rng.randn(len(idx)), index=idx)
    # Factor = alpha + 2*size exposure
    raw_factor = pure_alpha + 2 * log_mcap

    neutralized = neutralize_size(raw_factor, mcap, min_obs=30)

    # Check that neutralized factor has near-zero correlation with size
    for date in dates[:5]:
        nf = neutralized.loc[date].dropna()
        lm = log_mcap.loc[date].reindex(nf.index)
        common = nf.index.intersection(lm.dropna().index)
        if len(common) > 10:
            corr = nf[common].corr(lm[common])
            assert abs(corr) < 0.05, f"Neutralized corr with size = {corr:.4f} on {date}"
    print("  ✓ test_neutralize_removes_exposure PASSED")


def test_correlation_symmetric():
    """Correlation matrix should be symmetric."""
    factor, fwd, _, _, rng = _make_synthetic_data()
    noise = pd.Series(rng.randn(len(factor)), index=factor.index)
    factors = {"A": factor, "B": factor + noise, "C": noise}
    corr = compute_factor_correlation(factors, min_obs=30)
    for i in corr.index:
        for j in corr.columns:
            diff = abs(corr.loc[i, j] - corr.loc[j, i])
            assert diff < 1e-10, f"Asymmetry: corr[{i},{j}]={corr.loc[i,j]}, corr[{j},{i}]={corr.loc[j,i]}"
    print("  ✓ test_correlation_symmetric PASSED")


def test_redundant_detection():
    """Two identical factors should be detected as redundant."""
    factor, _, _, _, _ = _make_synthetic_data()
    factors = {"A": factor, "A_copy": factor.copy()}
    corr = compute_factor_correlation(factors, min_obs=30)
    pairs = find_redundant_pairs(corr, threshold=0.7)
    assert len(pairs) >= 1, "Expected at least 1 redundant pair"
    assert abs(pairs[0][2] - 1.0) < 0.01, f"Expected corr ≈ 1.0, got {pairs[0][2]:.4f}"
    print("  ✓ test_redundant_detection PASSED")


def test_select_uncorrelated():
    """Greedy selection should pick highest ICIR factor from each cluster."""
    factor, _, _, _, rng = _make_synthetic_data()
    noise = pd.Series(rng.randn(len(factor)), index=factor.index)
    factors = {"A": factor, "A_copy": factor.copy(), "B": noise}
    corr = compute_factor_correlation(factors, min_obs=30)
    ic_summary = {
        "A": {"icir": 0.5},
        "A_copy": {"icir": 0.3},
        "B": {"icir": 0.2},
    }
    selected = select_uncorrelated(corr, ic_summary, max_corr=0.5)
    assert "A" in selected, f"Expected 'A' in selected, got {selected}"
    assert "A_copy" not in selected, f"A_copy should be excluded, got {selected}"
    assert "B" in selected, f"Expected 'B' in selected, got {selected}"
    print("  ✓ test_select_uncorrelated PASSED")


# ─── New Function Tests ──────────────────────────────────────

def test_rolling_ic():
    """Rolling IC should have correct columns and reasonable values."""
    factor, fwd = _make_perfect_signal(n_dates=300, n_stocks=100)
    ic = compute_ic_series(factor, fwd, min_obs=30)
    rolling = compute_rolling_ic(ic, window=50)
    assert "rolling_mean_ic" in rolling.columns
    assert "rolling_rank_icir" in rolling.columns
    assert len(rolling) > 0, "Rolling IC should have at least one row"
    # For a perfect signal, rolling mean IC should be close to 1
    assert rolling["rolling_mean_ic"].mean() > 0.9, \
        f"Expected rolling mean IC > 0.9, got {rolling['rolling_mean_ic'].mean():.4f}"
    print("  ✓ test_rolling_ic PASSED")


def test_ic_by_group():
    """IC by group should return separate results for each group."""
    factor, fwd, dates, stocks, rng = _make_synthetic_data(n_dates=100, n_stocks=200)
    # Create 2 groups: first half = 'A', second half = 'B'
    group_labels = pd.Series("A", index=factor.index)
    for date in dates:
        instruments = stocks[len(stocks)//2:]
        idx = pd.MultiIndex.from_product([[date], instruments], names=["datetime", "instrument"])
        group_labels.loc[idx] = "B"

    results = compute_ic_by_group(factor, fwd, group_labels, min_obs=20)
    assert len(results) == 2, f"Expected 2 groups, got {len(results)}"
    assert "A" in results and "B" in results
    assert "mean_ic" in results["A"]
    print("  ✓ test_ic_by_group PASSED")


def test_marginal_ic():
    """Marginal IC of a factor against itself should be near zero."""
    factor, fwd, _, _, rng = _make_synthetic_data(n_dates=100, n_stocks=200)
    noise = pd.Series(rng.randn(len(factor)), index=factor.index)
    factors_dict = {"A": factor, "B": noise}

    # Marginal IC of A against itself should be ~0
    ic_series, summary = compute_marginal_ic(
        factors_dict, fwd, base_factors=["A"], candidate="A", min_obs=20
    )
    assert abs(summary.get("mean_ic", 1.0)) < 0.10, \
        f"Expected near-zero marginal IC, got {summary.get('mean_ic', 1.0):.4f}"

    # Marginal IC with no base should equal raw IC
    ic_raw, sum_raw = compute_marginal_ic(
        factors_dict, fwd, base_factors=[], candidate="A", min_obs=20
    )
    ic_direct = compute_ic_series(factor, fwd, min_obs=20)
    sum_direct = compute_ic_summary(ic_direct)
    assert abs(sum_raw["mean_ic"] - sum_direct["mean_ic"]) < 1e-10, \
        "Marginal IC with no base should equal raw IC"
    print("  ✓ test_marginal_ic PASSED")


# ─── Runner ──────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_ic_perfect_signal,
        test_ic_random_signal,
        test_icir_consistency,
        test_ic_by_year,
        test_quantile_monotonic,
        test_quantile_count,
        test_long_short_returns,
        test_neutralize_removes_exposure,
        test_correlation_symmetric,
        test_redundant_detection,
        test_select_uncorrelated,
        test_rolling_ic,
        test_ic_by_group,
        test_marginal_ic,
    ]

    print(f"\nRunning {len(tests)} factor_eval unit tests...\n")
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__} FAILED: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    if failed == 0:
        print("All tests PASSED ✓")
    else:
        print("Some tests FAILED ✗")
        sys.exit(1)
