"""
Result Analysis Module

Provides standardized backtest performance metrics, interactive
Plotly charts, and the ``BacktestReport`` one-call analysis class.

Usage::

    from src.result_analysis import BacktestReport

    report = BacktestReport(strategy_returns, benchmark_returns, name="My Strategy")
    report.summary()         # Metrics table
    report.plot()            # Interactive dashboard
    report.yearly()          # Yearly breakdown
    report.monthly_heatmap() # Month×Year heatmap
    report.rolling()         # Rolling Sharpe/Vol/Return
    report.distribution()    # Return histogram
    report.to_html("out.html")
"""

from .report import BacktestReport

from .metrics import (
    calculate_total_return,
    calculate_cagr,
    calculate_volatility,
    calculate_downside_volatility,
    calculate_max_drawdown,
    calculate_max_drawdown_duration,
    calculate_drawdown_series,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_calmar_ratio,
    calculate_information_ratio,
    calculate_alpha_beta,
    calculate_win_rate,
    calculate_profit_factor,
    calculate_tail_ratio,
    calculate_skewness,
    calculate_kurtosis,
    calculate_monthly_returns,
    calculate_yearly_returns,
    calculate_monthly_return_table,
    calculate_rolling_sharpe,
    calculate_rolling_volatility,
    calculate_rolling_return,
    generate_performance_report,
    calculate_weekly_win_rate,
    calculate_monthly_win_rate,
    calculate_tracking_error,
    generate_trading_stats,
)

from .plotters import (
    plot_equity_curve,
    plot_drawdown,
    plot_excess_return,
    plot_monthly_heatmap,
    plot_yearly_returns,
    plot_return_distribution,
    plot_rolling_metrics,
    plot_dashboard,
    plot_comprehensive_report_mpl,
    # Backward compat
    plot_cumulative_returns,
    plot_comprehensive_report,
)

__all__ = [
    'BacktestReport',
    # metrics
    'calculate_total_return',
    'calculate_cagr',
    'calculate_volatility',
    'calculate_downside_volatility',
    'calculate_max_drawdown',
    'calculate_max_drawdown_duration',
    'calculate_drawdown_series',
    'calculate_sharpe_ratio',
    'calculate_sortino_ratio',
    'calculate_calmar_ratio',
    'calculate_information_ratio',
    'calculate_alpha_beta',
    'calculate_win_rate',
    'calculate_profit_factor',
    'calculate_tail_ratio',
    'calculate_skewness',
    'calculate_kurtosis',
    'calculate_monthly_returns',
    'calculate_yearly_returns',
    'calculate_monthly_return_table',
    'calculate_rolling_sharpe',
    'calculate_rolling_volatility',
    'calculate_rolling_return',
    'generate_performance_report',
    'calculate_weekly_win_rate',
    'calculate_monthly_win_rate',
    'calculate_tracking_error',
    'generate_trading_stats',
    # plotters
    'plot_equity_curve',
    'plot_drawdown',
    'plot_excess_return',
    'plot_monthly_heatmap',
    'plot_yearly_returns',
    'plot_return_distribution',
    'plot_rolling_metrics',
    'plot_dashboard',
    'plot_comprehensive_report_mpl',
    'plot_cumulative_returns',
    'plot_comprehensive_report',
]
