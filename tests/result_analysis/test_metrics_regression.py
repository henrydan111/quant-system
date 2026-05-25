import numpy as np
import pandas as pd

from src.result_analysis.metrics import (
    calculate_alpha_beta,
    calculate_drawdown_series,
    calculate_information_ratio,
    calculate_max_drawdown,
    calculate_total_return,
    generate_performance_report,
)


def test_return_and_drawdown_metrics_are_compounded():
    returns = pd.Series(
        [0.10, -0.20, 0.05],
        index=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
    )

    assert calculate_total_return(returns) == np.prod([1.10, 0.80, 1.05]) - 1
    assert calculate_max_drawdown(returns) == calculate_drawdown_series(returns).min()
    assert calculate_max_drawdown(returns) < 0


def test_benchmark_relative_metrics_align_on_common_dates():
    strategy = pd.Series(
        [0.02, 0.02, -0.01, 0.04],
        index=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]),
    )
    benchmark = pd.Series(
        [0.01, 0.00, 0.02],
        index=pd.to_datetime(["2024-01-03", "2024-01-04", "2024-01-05"]),
    )

    alpha, beta = calculate_alpha_beta(strategy, benchmark, annual_factor=252)
    report = generate_performance_report(strategy, benchmark_returns=benchmark, risk_free_rate=0.0)

    assert alpha == 0.0
    assert beta == 0.0
    assert "Information Ratio" in report.index
    assert report.loc["Trading Days", "Benchmark"] == 3
    assert calculate_information_ratio(strategy.loc[benchmark.index], benchmark) != 0
