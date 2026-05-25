"""
BacktestReport — One-call backtest performance analysis.

Usage in Jupyter::

    from src.result_analysis import BacktestReport

    report = BacktestReport(strategy_returns, benchmark_returns, name="Small-Cap")
    report.summary()           # Metrics table
    report.plot()              # Interactive dashboard
    report.yearly()            # Annual returns breakdown
    report.monthly_heatmap()   # Year×Month heatmap
    report.rolling()           # Rolling Sharpe / Vol / Return
    report.distribution()      # Return histogram
    report.to_html("out.html") # Standalone HTML export
"""

import logging
import pandas as pd
from typing import Optional

from . import metrics
from . import plotters

logger = logging.getLogger(__name__)


class BacktestReport:
    """
    Standardized backtest performance report.

    Wraps ``metrics`` and ``plotters`` into a convenient interface
    for interactive Jupyter analysis.

    Args:
        strategy_returns: pd.Series of daily **net** returns with DatetimeIndex.
        benchmark_returns: Optional pd.Series of daily benchmark returns.
        name: Strategy display name (used in chart titles).
        risk_free_rate: Annual risk-free rate (default 2% — China 10Y bond proxy).
    """

    def __init__(self,
                 strategy_returns: pd.Series,
                 benchmark_returns: Optional[pd.Series] = None,
                 name: str = 'Strategy',
                 risk_free_rate: float = 0.02):
        # Validate input
        if not isinstance(strategy_returns, pd.Series):
            raise TypeError("strategy_returns must be a pd.Series")
        if strategy_returns.empty:
            raise ValueError("strategy_returns is empty")

        self.strategy_returns = strategy_returns.copy()
        self.name = name
        self.risk_free_rate = risk_free_rate

        # Align benchmark if provided
        if benchmark_returns is not None:
            common = strategy_returns.index.intersection(benchmark_returns.index)
            self.strategy_returns = strategy_returns.loc[common]
            self.benchmark_returns = benchmark_returns.loc[common].copy()
            logger.info("Aligned %d common trading days", len(common))
        else:
            self.benchmark_returns = None

    # ─── Metrics ──────────────────────────────────────────────

    def summary(self, display: bool = True) -> pd.DataFrame:
        """
        Compute and display all performance metrics.

        Args:
            display: If True, return styled DataFrame for Jupyter rendering.

        Returns:
            DataFrame of metrics (styled if display=True, raw if False).
        """
        report = metrics.generate_performance_report(
            self.strategy_returns,
            self.benchmark_returns,
            self.risk_free_rate,
        )

        if display:
            try:
                from IPython.display import display as ipy_display

                # Format rules: percentages for ratios, integers for counts
                int_rows = {'Trading Days', 'Max DD Duration (days)'}
                ratio_rows = {'Sharpe Ratio', 'Sortino Ratio', 'Calmar Ratio',
                              'Information Ratio', 'Profit Factor',
                              'Tail Ratio', 'Beta'}

                def fmt(v, row_name=''):
                    if pd.isna(v):
                        return '–'
                    if row_name in int_rows:
                        return f'{int(v):,}'
                    if row_name in ratio_rows:
                        return f'{v:.3f}'
                    if isinstance(v, float) and abs(v) < 100:
                        return f'{v:.2%}'
                    if isinstance(v, float):
                        return f'{v:.2f}'
                    return str(v)

                formatted = report.copy()
                for col in formatted.columns:
                    formatted[col] = [
                        fmt(formatted.loc[idx, col], idx)
                        for idx in formatted.index
                    ]
                ipy_display(formatted)
            except ImportError:
                print(report.to_string())
            # Don't return df — Jupyter would auto-display it again
            return None

        return report

    # ─── Main Dashboard ───────────────────────────────────────

    def plot(self, interactive: bool = True, log_scale: bool = True):
        """
        Display the main performance dashboard.

        Args:
            interactive: Use Plotly (True) or matplotlib (False).
            log_scale: Log y-axis for equity curve.
        """
        if interactive:
            fig = plotters.plot_dashboard(
                self.strategy_returns,
                self.benchmark_returns,
                name=self.name,
                log_scale=log_scale,
            )
            fig.show()
        else:
            plotters.plot_comprehensive_report_mpl(
                self.strategy_returns,
                self.benchmark_returns,
            )

    # ─── Yearly Breakdown ─────────────────────────────────────

    def yearly(self, display: bool = True) -> pd.DataFrame:
        """
        Yearly returns breakdown with interactive bar chart.

        Returns:
            DataFrame of yearly returns.
        """
        yearly_strat = metrics.calculate_yearly_returns(self.strategy_returns)
        data = {'Strategy': yearly_strat}

        if self.benchmark_returns is not None:
            yearly_bench = metrics.calculate_yearly_returns(self.benchmark_returns)
            data['Benchmark'] = yearly_bench

        yearly_df = pd.DataFrame(data)
        if self.benchmark_returns is not None:
            yearly_df['Excess'] = yearly_df['Strategy'] - yearly_df['Benchmark']

        if display:
            try:
                from IPython.display import display as ipy_display
                styled = yearly_df.style.format('{:.2%}').background_gradient(
                    cmap='RdYlGn', vmin=-0.5, vmax=0.5
                )
                ipy_display(styled)
            except ImportError:
                print(yearly_df.to_string(float_format='{:.2%}'.format))

            # Interactive chart
            fig = plotters.plot_yearly_returns(
                self.strategy_returns,
                self.benchmark_returns,
                name=self.name,
            )
            fig.show()
            # Don't return df — Jupyter would auto-display it again
            return None

        return yearly_df

    # ─── Monthly Heatmap ──────────────────────────────────────

    def monthly_heatmap(self):
        """Display interactive monthly return heatmap."""
        fig = plotters.plot_monthly_heatmap(
            self.strategy_returns, name=self.name
        )
        fig.show()

    # ─── Rolling Metrics ──────────────────────────────────────

    def rolling(self, window: int = 252):
        """
        Display rolling Sharpe, volatility, and return.

        Args:
            window: Rolling window in trading days (default 252 = 1 year).
        """
        fig = plotters.plot_rolling_metrics(
            self.strategy_returns,
            window=window,
            risk_free_rate=self.risk_free_rate,
            name=self.name,
        )
        fig.show()

    # ─── Return Distribution ──────────────────────────────────

    def distribution(self):
        """Display daily return distribution histogram."""
        fig = plotters.plot_return_distribution(
            self.strategy_returns,
            self.benchmark_returns,
            name=self.name,
        )
        fig.show()

    # ─── Individual Charts ────────────────────────────────────

    def equity_curve(self, log_scale: bool = True):
        """Display standalone equity curve chart."""
        fig = plotters.plot_equity_curve(
            self.strategy_returns,
            self.benchmark_returns,
            name=self.name,
            log_scale=log_scale,
        )
        fig.show()

    def drawdown(self):
        """Display standalone drawdown chart."""
        fig = plotters.plot_drawdown(
            self.strategy_returns, name=self.name
        )
        fig.show()

    def excess_return(self):
        """Display cumulative excess return chart."""
        if self.benchmark_returns is None:
            logger.warning("No benchmark provided — cannot compute excess return")
            return
        fig = plotters.plot_excess_return(
            self.strategy_returns,
            self.benchmark_returns,
            name=self.name,
        )
        fig.show()

    # ─── Export ────────────────────────────────────────────────

    def to_html(self, path: str):
        """
        Export a standalone HTML report with all charts.

        Args:
            path: Output file path (e.g., 'report.html').
        """
        import plotly.io as pio

        charts = []

        # Dashboard
        charts.append(plotters.plot_dashboard(
            self.strategy_returns, self.benchmark_returns,
            name=self.name,
        ))

        # Monthly heatmap
        charts.append(plotters.plot_monthly_heatmap(
            self.strategy_returns, name=self.name,
        ))

        # Yearly
        charts.append(plotters.plot_yearly_returns(
            self.strategy_returns, self.benchmark_returns,
            name=self.name,
        ))

        # Rolling
        charts.append(plotters.plot_rolling_metrics(
            self.strategy_returns,
            risk_free_rate=self.risk_free_rate,
            name=self.name,
        ))

        # Distribution
        charts.append(plotters.plot_return_distribution(
            self.strategy_returns, self.benchmark_returns,
            name=self.name,
        ))

        # Build HTML
        report_df = metrics.generate_performance_report(
            self.strategy_returns,
            self.benchmark_returns,
            self.risk_free_rate,
        )

        html_parts = [
            '<!DOCTYPE html>',
            '<html><head>',
            f'<title>{self.name} — Backtest Report</title>',
            '<meta charset="utf-8">',
            '<style>',
            'body { font-family: Inter, Arial, sans-serif; margin: 40px; '
            'background: #fafafa; }',
            'h1 { color: #333; }',
            'table { border-collapse: collapse; margin: 20px 0; }',
            'th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: right; }',
            'th { background: #f5f5f5; }',
            '</style>',
            '</head><body>',
            f'<h1>{self.name} — Backtest Report</h1>',
            report_df.to_html(float_format=lambda x: f'{x:.4f}'
                              if isinstance(x, float) else str(x)),
        ]

        for chart in charts:
            html_parts.append(pio.to_html(chart, full_html=False,
                                          include_plotlyjs='cdn'))

        html_parts.extend(['</body></html>'])

        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html_parts))

        logger.info("HTML report saved to %s", path)
        print(f'Report exported: {path}')

    # ─── Trading Statistics ───────────────────────────────────

    def trading_analysis(self,
                         holdings: dict,
                         df: pd.DataFrame,
                         report_df: pd.DataFrame = None,
                         buy_cost: float = 0.0005,
                         sell_cost: float = 0.0015,
                         display: bool = True):
        """
        Compute and display 果仁-style trading statistics.

        Args:
            holdings: Dict {pd.Timestamp: [stock_codes]} from backtester.
            df: Full DataFrame with MultiIndex(instrument, datetime).
            report_df: Optional Qlib report DataFrame (has turnover column).
            buy_cost: Buy cost fraction.
            sell_cost: Sell cost fraction.
            display: If True, show styled table in Jupyter.

        Returns:
            pd.Series of trading statistics.
        """
        stats = metrics.generate_trading_stats(
            holdings=holdings,
            df=df,
            strategy_returns=self.strategy_returns,
            benchmark_returns=self.benchmark_returns,
            report_df=report_df,
            buy_cost=buy_cost,
            sell_cost=sell_cost,
        )

        if display:
            try:
                from IPython.display import display as ipy_display, HTML

                # Format as styled table
                fmt_stats = {}
                pct_keys = [
                    '年换手率', '平均交易收益', '正收益平均', '负收益平均',
                    '交易赢率', '持仓停牌股票比例', '日赢率', '周赢率', '月赢率',
                    '调仓指令可执行比例', '指数跟踪误差', '平均持仓仓位',
                ]
                for key, val in stats.items():
                    # Check if this metric should be formatted as percentage
                    if any(p in key for p in pct_keys):
                        fmt_stats[key] = f'{val:.2%}'
                    elif isinstance(val, float):
                        fmt_stats[key] = f'{val:.2f}'
                    else:
                        fmt_stats[key] = str(int(val))

                stats_df = pd.DataFrame(
                    list(fmt_stats.values()),
                    index=list(fmt_stats.keys()),
                    columns=[self.name],
                )

                html = (
                    f'<h3>📊 Trading Analysis — {self.name}</h3>'
                    + stats_df.to_html(escape=False)
                )
                ipy_display(HTML(html))

            except ImportError:
                print(stats.to_string())

            return None  # prevent double-display in Jupyter

        return stats

    # ─── Repr ─────────────────────────────────────────────────

    def __repr__(self):
        n_days = len(self.strategy_returns)
        bench_str = '+ benchmark' if self.benchmark_returns is not None else 'no benchmark'
        return f'BacktestReport("{self.name}", {n_days} days, {bench_str})'
