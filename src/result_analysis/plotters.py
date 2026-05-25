"""
Backtest Performance Visualization

Interactive charts using Plotly for Jupyter notebook display.
Falls back to matplotlib when ``interactive=False`` (e.g., for PDF export).

All public ``plot_*`` functions accept a daily return pd.Series and
return a Plotly figure (or matplotlib axes when ``interactive=False``).
"""

import numpy as np
import pandas as pd
from typing import Optional

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

from .metrics import (
    calculate_drawdown_series,
    calculate_monthly_return_table,
    calculate_yearly_returns,
    calculate_rolling_sharpe,
    calculate_rolling_volatility,
    calculate_rolling_return,
)

# ─── Color Palette ────────────────────────────────────────────────

COLORS = {
    'strategy': '#E53935',
    'benchmark': '#1E88E5',
    'excess': '#43A047',
    'drawdown': '#E53935',
    'positive': '#43A047',
    'negative': '#E53935',
    'neutral': '#757575',
}

LAYOUT_DEFAULTS = dict(
    template='plotly_white',
    font=dict(family='Inter, Arial, sans-serif', size=12),
    hovermode='x unified',
    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    margin=dict(l=60, r=30, t=50, b=40),
)


# ─── 1. Equity Curve ─────────────────────────────────────────────

def plot_equity_curve(strategy_returns: pd.Series,
                      benchmark_returns: Optional[pd.Series] = None,
                      name: str = 'Strategy',
                      log_scale: bool = True) -> go.Figure:
    """
    Interactive equity curve — cumulative return of strategy vs benchmark.

    Args:
        strategy_returns: Daily returns series.
        benchmark_returns: Optional benchmark daily returns.
        name: Strategy display name.
        log_scale: Use log y-axis (recommended for long backtests).

    Returns:
        Plotly Figure.
    """
    cum_ret = (1 + strategy_returns).cumprod()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=cum_ret.index, y=cum_ret.values,
        name=name, line=dict(color=COLORS['strategy'], width=2),
        hovertemplate='%{x|%Y-%m-%d}<br>Return: %{y:.2f}x<extra></extra>',
    ))

    if benchmark_returns is not None:
        bench_cum = (1 + benchmark_returns).cumprod()
        fig.add_trace(go.Scatter(
            x=bench_cum.index, y=bench_cum.values,
            name='CSI 300', line=dict(color=COLORS['benchmark'], width=1.5, dash='dot'),
            hovertemplate='%{x|%Y-%m-%d}<br>Return: %{y:.2f}x<extra></extra>',
        ))

    fig.update_layout(
        title=f'{name} — Equity Curve',
        yaxis_title='Cumulative Return (×)',
        yaxis_type='log' if log_scale else 'linear',
        height=400,
        **LAYOUT_DEFAULTS,
    )
    return fig


# ─── 2. Drawdown Chart ───────────────────────────────────────────

def plot_drawdown(strategy_returns: pd.Series,
                  name: str = 'Strategy') -> go.Figure:
    """
    Interactive drawdown chart — underwater equity curve.

    Hover shows drawdown percentage and date.
    """
    dd = calculate_drawdown_series(strategy_returns)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dd.index, y=dd.values,
        fill='tozeroy',
        name='Drawdown',
        line=dict(color=COLORS['drawdown'], width=1),
        fillcolor='rgba(229, 57, 53, 0.2)',
        hovertemplate='%{x|%Y-%m-%d}<br>DD: %{y:.1%}<extra></extra>',
    ))

    fig.update_layout(
        title=f'{name} — Drawdown',
        yaxis_title='Drawdown',
        yaxis_tickformat='.0%',
        height=250,
        **LAYOUT_DEFAULTS,
    )
    return fig


# ─── 3. Excess Return ────────────────────────────────────────────

def plot_excess_return(strategy_returns: pd.Series,
                       benchmark_returns: pd.Series,
                       name: str = 'Strategy') -> go.Figure:
    """
    Cumulative excess return vs benchmark.
    """
    excess = strategy_returns - benchmark_returns
    cum_excess = (1 + excess).cumprod()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=cum_excess.index, y=cum_excess.values,
        name='Excess Return',
        line=dict(color=COLORS['excess'], width=2),
        hovertemplate='%{x|%Y-%m-%d}<br>Excess: %{y:.2f}x<extra></extra>',
    ))
    fig.add_hline(y=1.0, line_dash='dash', line_color='gray', line_width=0.5)

    fig.update_layout(
        title=f'{name} — Cumulative Excess Return (vs Benchmark)',
        yaxis_title='Excess Return (×)',
        height=300,
        **LAYOUT_DEFAULTS,
    )
    return fig


# ─── 4. Monthly Heatmap ──────────────────────────────────────────

def plot_monthly_heatmap(strategy_returns: pd.Series,
                         name: str = 'Strategy') -> go.Figure:
    """
    Year × Month return heatmap (like a performance calendar).

    Cell color: green = positive, red = negative.
    Hover shows exact return percentage.
    """
    table = calculate_monthly_return_table(strategy_returns)
    if table.empty:
        return go.Figure()

    # Add annual column
    yearly = calculate_yearly_returns(strategy_returns)
    table['Year Total'] = yearly.values

    text = table.applymap(lambda v: f'{v:.1%}' if pd.notna(v) else '')

    fig = go.Figure(data=go.Heatmap(
        z=table.values,
        x=table.columns.tolist(),
        y=[str(y) for y in table.index],
        text=text.values,
        texttemplate='%{text}',
        textfont=dict(size=10),
        colorscale=[
            [0.0, '#E53935'],
            [0.35, '#FFCDD2'],
            [0.5, '#FFFFFF'],
            [0.65, '#C8E6C9'],
            [1.0, '#43A047'],
        ],
        zmid=0,
        showscale=True,
        colorbar=dict(title='Return', tickformat='.0%'),
        hovertemplate='%{y} %{x}<br>Return: %{text}<extra></extra>',
    ))

    fig.update_layout(
        title=f'{name} — Monthly Returns',
        yaxis=dict(autorange='reversed'),
        height=max(300, len(table) * 25 + 100),
        **LAYOUT_DEFAULTS,
    )
    return fig


# ─── 5. Yearly Bar Chart ─────────────────────────────────────────

def plot_yearly_returns(strategy_returns: pd.Series,
                        benchmark_returns: Optional[pd.Series] = None,
                        name: str = 'Strategy') -> go.Figure:
    """
    Side-by-side yearly return bar chart.
    """
    yearly_strat = calculate_yearly_returns(strategy_returns)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[str(y) for y in yearly_strat.index],
        y=yearly_strat.values,
        name=name,
        marker_color=COLORS['strategy'],
        hovertemplate='%{x}<br>Return: %{y:.1%}<extra></extra>',
    ))

    if benchmark_returns is not None:
        yearly_bench = calculate_yearly_returns(benchmark_returns)
        fig.add_trace(go.Bar(
            x=[str(y) for y in yearly_bench.index],
            y=yearly_bench.values,
            name='Benchmark',
            marker_color=COLORS['benchmark'],
            hovertemplate='%{x}<br>Return: %{y:.1%}<extra></extra>',
        ))

    fig.update_layout(
        title=f'{name} — Yearly Returns',
        yaxis_title='Annual Return',
        yaxis_tickformat='.0%',
        barmode='group',
        height=350,
        **LAYOUT_DEFAULTS,
    )
    fig.add_hline(y=0, line_color='gray', line_width=0.5)
    return fig


# ─── 6. Return Distribution ──────────────────────────────────────

def plot_return_distribution(strategy_returns: pd.Series,
                             benchmark_returns: Optional[pd.Series] = None,
                             name: str = 'Strategy') -> go.Figure:
    """
    Histogram of daily returns with optional benchmark overlay.
    """
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=strategy_returns.values,
        name=name,
        marker_color=COLORS['strategy'],
        opacity=0.7,
        nbinsx=80,
        histnorm='probability density',
    ))

    if benchmark_returns is not None:
        fig.add_trace(go.Histogram(
            x=benchmark_returns.values,
            name='Benchmark',
            marker_color=COLORS['benchmark'],
            opacity=0.4,
            nbinsx=80,
            histnorm='probability density',
        ))

    fig.update_layout(
        title=f'{name} — Daily Return Distribution',
        xaxis_title='Daily Return',
        yaxis_title='Density',
        barmode='overlay',
        height=350,
        **LAYOUT_DEFAULTS,
    )
    fig.add_vline(x=0, line_dash='dash', line_color='gray', line_width=0.5)
    return fig


# ─── 7. Rolling Metrics ──────────────────────────────────────────

def plot_rolling_metrics(strategy_returns: pd.Series,
                         window: int = 252,
                         risk_free_rate: float = 0.02,
                         name: str = 'Strategy') -> go.Figure:
    """
    3-panel chart: rolling Sharpe, rolling volatility, rolling return.
    """
    r_sharpe = calculate_rolling_sharpe(strategy_returns, window, risk_free_rate)
    r_vol = calculate_rolling_volatility(strategy_returns, window)
    r_ret = calculate_rolling_return(strategy_returns, window)

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        subplot_titles=[
            f'Rolling {window}d Sharpe',
            f'Rolling {window}d Volatility',
            f'Rolling {window}d Return',
        ],
        vertical_spacing=0.08,
    )

    fig.add_trace(go.Scatter(
        x=r_sharpe.index, y=r_sharpe.values,
        name='Sharpe', line=dict(color=COLORS['strategy'], width=1.5),
        hovertemplate='%{x|%Y-%m-%d}<br>Sharpe: %{y:.2f}<extra></extra>',
    ), row=1, col=1)
    fig.add_hline(y=0, line_dash='dash', line_color='gray',
                  line_width=0.5, row=1, col=1)

    fig.add_trace(go.Scatter(
        x=r_vol.index, y=r_vol.values,
        name='Volatility', line=dict(color='#FF9800', width=1.5),
        hovertemplate='%{x|%Y-%m-%d}<br>Vol: %{y:.1%}<extra></extra>',
    ), row=2, col=1)
    fig.update_yaxes(tickformat='.0%', row=2, col=1)

    fig.add_trace(go.Scatter(
        x=r_ret.index, y=r_ret.values,
        name='Return', line=dict(color=COLORS['excess'], width=1.5),
        hovertemplate='%{x|%Y-%m-%d}<br>Return: %{y:.1%}<extra></extra>',
    ), row=3, col=1)
    fig.update_yaxes(tickformat='.0%', row=3, col=1)
    fig.add_hline(y=0, line_dash='dash', line_color='gray',
                  line_width=0.5, row=3, col=1)

    fig.update_layout(
        title=f'{name} — Rolling Metrics ({window}d window)',
        height=600,
        showlegend=False,
        **LAYOUT_DEFAULTS,
    )
    return fig


# ─── 8. Dashboard (Multi-panel) ──────────────────────────────────

def plot_dashboard(strategy_returns: pd.Series,
                   benchmark_returns: Optional[pd.Series] = None,
                   name: str = 'Strategy',
                   log_scale: bool = True) -> go.Figure:
    """
    Combined dashboard with equity curve, excess return, and drawdown.

    This is the main at-a-glance view.
    """
    cum_ret = (1 + strategy_returns).cumprod()
    dd = calculate_drawdown_series(strategy_returns)

    has_bench = benchmark_returns is not None
    n_rows = 3 if has_bench else 2
    heights = [3, 2, 1.5] if has_bench else [3, 1.5]
    subtitles = ['Equity Curve', 'Excess Return', 'Drawdown'] if has_bench \
        else ['Equity Curve', 'Drawdown']

    fig = make_subplots(
        rows=n_rows, cols=1, shared_xaxes=True,
        subplot_titles=subtitles,
        vertical_spacing=0.06,
        row_heights=heights,
    )

    # Panel 1: Equity curve
    fig.add_trace(go.Scatter(
        x=cum_ret.index, y=cum_ret.values,
        name=name, line=dict(color=COLORS['strategy'], width=2),
        hovertemplate='%{x|%Y-%m-%d}<br>%{y:.2f}x<extra></extra>',
    ), row=1, col=1)

    if has_bench:
        bench_cum = (1 + benchmark_returns).cumprod()
        fig.add_trace(go.Scatter(
            x=bench_cum.index, y=bench_cum.values,
            name='Benchmark', line=dict(color=COLORS['benchmark'], width=1.5, dash='dot'),
            hovertemplate='%{x|%Y-%m-%d}<br>%{y:.2f}x<extra></extra>',
        ), row=1, col=1)

        # Panel 2: Excess
        excess = strategy_returns - benchmark_returns
        cum_excess = (1 + excess).cumprod()
        fig.add_trace(go.Scatter(
            x=cum_excess.index, y=cum_excess.values,
            name='Excess', line=dict(color=COLORS['excess'], width=1.5),
            showlegend=True,
            hovertemplate='%{x|%Y-%m-%d}<br>%{y:.2f}x<extra></extra>',
        ), row=2, col=1)
        fig.add_hline(y=1.0, line_dash='dash', line_color='gray',
                      line_width=0.5, row=2, col=1)
        dd_row = 3
    else:
        dd_row = 2

    # Drawdown panel
    fig.add_trace(go.Scatter(
        x=dd.index, y=dd.values,
        name='Drawdown', fill='tozeroy',
        line=dict(color=COLORS['drawdown'], width=1),
        fillcolor='rgba(229, 57, 53, 0.2)',
        showlegend=True,
        hovertemplate='%{x|%Y-%m-%d}<br>DD: %{y:.1%}<extra></extra>',
    ), row=dd_row, col=1)
    fig.update_yaxes(tickformat='.0%', row=dd_row, col=1)

    if log_scale:
        fig.update_yaxes(type='log', row=1, col=1)

    fig.update_layout(
        title=f'{name} — Performance Dashboard',
        height=650,
        **LAYOUT_DEFAULTS,
    )
    return fig


# ─── Matplotlib Fallback ─────────────────────────────────────────

def plot_comprehensive_report_mpl(strategy_returns: pd.Series,
                                  benchmark_returns: Optional[pd.Series] = None,
                                  save_path: Optional[str] = None):
    """
    Static matplotlib comprehensive report (for PDF export).

    Creates a 3-panel figure: cumulative returns, drawdown, distribution.
    """
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(3, 1, figsize=(14, 10),
                             gridspec_kw={'height_ratios': [3, 1.5, 1.5]})

    # Panel 1: Cumulative
    cum_ret = (1 + strategy_returns).cumprod()
    axes[0].plot(cum_ret.index, cum_ret.values, label='Strategy',
                 color=COLORS['strategy'], linewidth=1.5)
    if benchmark_returns is not None:
        bench_cum = (1 + benchmark_returns).cumprod()
        axes[0].plot(bench_cum.index, bench_cum.values, label='Benchmark',
                     color=COLORS['benchmark'], linewidth=1.2, linestyle='--')
    axes[0].set_ylabel('Cumulative Return')
    axes[0].set_yscale('log')
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    # Panel 2: Drawdown
    dd = calculate_drawdown_series(strategy_returns)
    axes[1].fill_between(dd.index, dd.values, 0, color=COLORS['drawdown'], alpha=0.3)
    axes[1].plot(dd.index, dd.values, color=COLORS['drawdown'], linewidth=0.8)
    axes[1].set_ylabel('Drawdown')
    axes[1].grid(alpha=0.3)

    # Panel 3: Distribution
    axes[2].hist(strategy_returns.values, bins=80, density=True,
                 color=COLORS['strategy'], alpha=0.6, label='Strategy')
    if benchmark_returns is not None:
        axes[2].hist(benchmark_returns.values, bins=80, density=True,
                     color=COLORS['benchmark'], alpha=0.3, label='Benchmark')
    axes[2].set_xlabel('Daily Return')
    axes[2].set_ylabel('Density')
    axes[2].legend()
    axes[2].grid(alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


# Backward compat aliases
def plot_cumulative_returns(strategy_returns, benchmark_returns=None, ax=None, title='Cumulative Returns'):
    """Legacy matplotlib cumulative return plot."""
    import matplotlib.pyplot as plt
    if ax is None:
        _, ax = plt.subplots(figsize=(10, 5))
    cum = (1 + strategy_returns).cumprod()
    ax.plot(cum.index, cum, label='Strategy', color=COLORS['strategy'], linewidth=2)
    if benchmark_returns is not None:
        bench = (1 + benchmark_returns).cumprod()
        ax.plot(bench.index, bench, label='Benchmark', color=COLORS['benchmark'],
                linestyle='--', linewidth=2)
    ax.set_title(title)
    ax.set_ylabel('Cumulative Return')
    ax.legend()
    ax.grid(alpha=0.3)
    return ax


def plot_comprehensive_report(strategy_returns, benchmark_returns=None, save_path=None):
    """Legacy alias for matplotlib comprehensive report."""
    return plot_comprehensive_report_mpl(strategy_returns, benchmark_returns, save_path)
