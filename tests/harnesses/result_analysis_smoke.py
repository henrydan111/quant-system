"""
Test script for src/result_analysis module.

Validates all metrics, plotters, and BacktestReport with synthetic data.
"""
import sys
import os
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pandas as pd


def generate_synthetic_data(n_days=1000, seed=42):
    """Generate synthetic strategy and benchmark return series."""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range('2020-01-01', periods=n_days, freq='B')

    # Strategy: positive drift with higher vol
    strat_ret = rng.normal(0.0005, 0.02, n_days)
    # Benchmark: slight positive drift, lower vol
    bench_ret = rng.normal(0.0002, 0.012, n_days)

    strategy = pd.Series(strat_ret, index=dates, name='strategy')
    benchmark = pd.Series(bench_ret, index=dates, name='benchmark')
    return strategy, benchmark


def test_metrics():
    """Test all metric functions."""
    from src.result_analysis import metrics

    strat, bench = generate_synthetic_data()
    passed = 0
    total = 0

    def check(name, value, valid_range=None):
        nonlocal passed, total
        total += 1
        ok = np.isfinite(value) if isinstance(value, float) else True
        if valid_range and ok:
            ok = valid_range[0] <= value <= valid_range[1]
        status = '✅' if ok else '❌'
        print(f'  {status} {name}: {value:.4f}' if isinstance(value, float)
              else f'  {status} {name}: {value}')
        if ok:
            passed += 1
        return ok

    print('=== Metrics Tests ===')
    check('total_return', metrics.calculate_total_return(strat))
    check('cagr', metrics.calculate_cagr(strat), (-1, 5))
    check('volatility', metrics.calculate_volatility(strat), (0, 2))
    check('downside_vol', metrics.calculate_downside_volatility(strat), (0, 2))
    check('max_drawdown', metrics.calculate_max_drawdown(strat), (-1, 0))
    check('max_dd_duration', metrics.calculate_max_drawdown_duration(strat))
    check('sharpe', metrics.calculate_sharpe_ratio(strat, 0.02), (-5, 5))
    check('sortino', metrics.calculate_sortino_ratio(strat, 0.02), (-5, 10))
    check('calmar', metrics.calculate_calmar_ratio(strat), (-5, 10))
    check('info_ratio', metrics.calculate_information_ratio(strat, bench), (-5, 5))

    alpha, beta = metrics.calculate_alpha_beta(strat, bench)
    check('alpha', alpha, (-2, 2))
    check('beta', beta, (-5, 5))

    check('win_rate', metrics.calculate_win_rate(strat), (0, 1))
    check('profit_factor', metrics.calculate_profit_factor(strat), (0, 100))
    check('tail_ratio', metrics.calculate_tail_ratio(strat), (0, 10))
    check('skewness', metrics.calculate_skewness(strat), (-5, 5))
    check('kurtosis', metrics.calculate_kurtosis(strat), (-5, 50))

    # Period aggregation
    monthly = metrics.calculate_monthly_returns(strat)
    assert len(monthly) > 0, "Monthly returns empty"
    print(f'  ✅ monthly_returns: {len(monthly)} months')
    passed += 1; total += 1

    yearly = metrics.calculate_yearly_returns(strat)
    assert len(yearly) > 0, "Yearly returns empty"
    print(f'  ✅ yearly_returns: {len(yearly)} years')
    passed += 1; total += 1

    table = metrics.calculate_monthly_return_table(strat)
    assert not table.empty, "Monthly table empty"
    print(f'  ✅ monthly_table: {table.shape}')
    passed += 1; total += 1

    # Rolling
    r_sharpe = metrics.calculate_rolling_sharpe(strat)
    assert len(r_sharpe) > 0, "Rolling sharpe empty"
    print(f'  ✅ rolling_sharpe: {len(r_sharpe)} points')
    passed += 1; total += 1

    # Comprehensive report
    report = metrics.generate_performance_report(strat, bench, 0.02)
    assert 'Strategy' in report.columns, "Missing Strategy column"
    assert 'Benchmark' in report.columns, "Missing Benchmark column"
    assert len(report) >= 14, f"Expected >= 14 rows, got {len(report)}"
    print(f'  ✅ performance_report: {report.shape}')
    passed += 1; total += 1

    print(f'\nMetrics: {passed}/{total} passed')
    return passed == total


def test_plotters():
    """Test all plotter functions (create figures without showing)."""
    from src.result_analysis import plotters

    strat, bench = generate_synthetic_data()
    passed = 0
    total = 0

    def check_fig(name, fig):
        nonlocal passed, total
        total += 1
        ok = fig is not None
        status = '✅' if ok else '❌'
        print(f'  {status} {name}')
        if ok:
            passed += 1

    print('\n=== Plotter Tests ===')
    check_fig('equity_curve', plotters.plot_equity_curve(strat, bench))
    check_fig('drawdown', plotters.plot_drawdown(strat))
    check_fig('excess_return', plotters.plot_excess_return(strat, bench))
    check_fig('monthly_heatmap', plotters.plot_monthly_heatmap(strat))
    check_fig('yearly_returns', plotters.plot_yearly_returns(strat, bench))
    check_fig('return_distribution', plotters.plot_return_distribution(strat, bench))
    check_fig('rolling_metrics', plotters.plot_rolling_metrics(strat))
    check_fig('dashboard', plotters.plot_dashboard(strat, bench))

    print(f'\nPlotters: {passed}/{total} passed')
    return passed == total


def test_report():
    """Test BacktestReport class."""
    from src.result_analysis import BacktestReport

    strat, bench = generate_synthetic_data()
    passed = 0
    total = 0

    print('\n=== BacktestReport Tests ===')

    # Init
    total += 1
    report = BacktestReport(strat, bench, name='Test Strategy', risk_free_rate=0.02)
    print(f'  ✅ __init__: {report}')
    passed += 1

    # Summary (no display in test)
    total += 1
    df = report.summary(display=False)
    assert 'Strategy' in df.columns
    print(f'  ✅ summary: {df.shape}')
    passed += 1

    # Yearly (no display)
    total += 1
    yearly = report.yearly(display=False)
    assert len(yearly) > 0
    print(f'  ✅ yearly: {yearly.shape}')
    passed += 1

    # HTML export
    total += 1
    html_path = os.path.join(PROJECT_ROOT, 'workspace', 'outputs',
                             'test_report.html')
    os.makedirs(os.path.dirname(html_path), exist_ok=True)
    report.to_html(html_path)
    assert os.path.exists(html_path)
    size = os.path.getsize(html_path) / 1024
    print(f'  ✅ to_html: {html_path} ({size:.0f} KB)')
    passed += 1
    # Cleanup
    os.remove(html_path)

    print(f'\nBacktestReport: {passed}/{total} passed')
    return passed == total


if __name__ == '__main__':
    ok1 = test_metrics()
    ok2 = test_plotters()
    ok3 = test_report()

    print('\n' + '=' * 50)
    if ok1 and ok2 and ok3:
        print('ALL TESTS PASSED ✅')
    else:
        print('SOME TESTS FAILED ❌')
        sys.exit(1)
