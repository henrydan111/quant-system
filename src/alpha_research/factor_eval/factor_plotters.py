"""
Factor-Specific Visualizations (因子可视化)

Publication-quality matplotlib plots for factor research. Complements
result_analysis/plotters.py (which handles portfolio-level visuals) with
factor-level charts: IC time series, quantile bar charts, decay curves,
correlation heatmaps, and composite tearsheets.

All functions accept an optional `ax` parameter for embedding in notebooks
or composing into larger figures.
"""

import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

logger = logging.getLogger(__name__)

# Consistent style across all factor plots
_STYLE_DEFAULTS = {
    "figure.facecolor": "white",
    "axes.facecolor": "#FAFAFA",
    "axes.grid": True,
    "grid.alpha": 0.3,
    "font.size": 10,
}


def plot_ic_time_series(
    ic_series: pd.DataFrame,
    rolling_window: int = 20,
    ax: plt.Axes = None,
    title: str = "IC Time Series",
) -> plt.Axes:
    """Plot daily IC with rolling mean overlay.

    Args:
        ic_series: DataFrame with column "IC" (and optionally "RankIC").
        rolling_window: Window for rolling mean smoothing.
        ax: Optional matplotlib Axes.
        title: Plot title.

    Returns:
        matplotlib Axes.
    """
    with plt.rc_context(_STYLE_DEFAULTS):
        if ax is None:
            fig, ax = plt.subplots(figsize=(12, 4))

        ic = ic_series["IC"].dropna()
        ax.bar(ic.index, ic.values, color=np.where(ic > 0, "#4CAF50", "#F44336"),
               alpha=0.5, width=1.0, label="Daily IC")
        rolling_ic = ic.rolling(rolling_window, min_periods=1).mean()
        ax.plot(rolling_ic.index, rolling_ic.values, color="#1565C0",
                linewidth=1.5, label=f"{rolling_window}d Rolling Mean")
        ax.axhline(0, color="black", linewidth=0.5)

        mean_ic = ic.mean()
        ax.axhline(mean_ic, color="#FF9800", linewidth=1, linestyle="--",
                   label=f"Mean IC = {mean_ic:.4f}")

        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_ylabel("IC")
        ax.legend(loc="upper right", fontsize=8)
        ax.tick_params(axis="x", rotation=45)

    return ax


def plot_ic_histogram(
    ic_series: pd.DataFrame,
    ax: plt.Axes = None,
    title: str = "IC Distribution",
) -> plt.Axes:
    """Plot histogram of daily IC values with normal fit.

    Args:
        ic_series: DataFrame with column "IC".
        ax: Optional matplotlib Axes.
        title: Plot title.

    Returns:
        matplotlib Axes.
    """
    with plt.rc_context(_STYLE_DEFAULTS):
        if ax is None:
            fig, ax = plt.subplots(figsize=(6, 4))

        ic = ic_series["IC"].dropna()
        sns.histplot(ic, kde=True, color="#42A5F5", alpha=0.6, ax=ax,
                     stat="density", bins=40)
        ax.axvline(ic.mean(), color="#FF9800", linewidth=1.5, linestyle="--",
                   label=f"Mean = {ic.mean():.4f}")
        ax.axvline(0, color="black", linewidth=0.5)

        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlabel("IC")
        ax.legend(fontsize=8)

    return ax


def plot_quantile_returns(
    quantile_summary: pd.DataFrame,
    ax: plt.Axes = None,
    title: str = "Quantile Annualized Returns",
) -> plt.Axes:
    """Bar chart of annualized returns per quantile group.

    Args:
        quantile_summary: Output of compute_quantile_summary.
        ax: Optional matplotlib Axes.
        title: Plot title.

    Returns:
        matplotlib Axes.
    """
    with plt.rc_context(_STYLE_DEFAULTS):
        if ax is None:
            fig, ax = plt.subplots(figsize=(6, 4))

        returns = quantile_summary["annualized_return"]
        colors = plt.cm.RdYlGn(np.linspace(0.15, 0.85, len(returns)))
        bars = ax.bar(
            [f"Q{q}" for q in returns.index],
            returns.values,
            color=colors,
            edgecolor="white",
            linewidth=0.5,
        )

        # Add value labels
        for bar, val in zip(bars, returns.values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{val:.2%}",
                ha="center", va="bottom", fontsize=8,
            )

        ax.axhline(0, color="black", linewidth=0.5)
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_ylabel("Annualized Return")
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))

    return ax


def plot_cumulative_long_short(
    ls_returns: pd.Series,
    ax: plt.Axes = None,
    title: str = "Long-Short Cumulative Return",
) -> plt.Axes:
    """Plot equity curve of long-short portfolio.

    Args:
        ls_returns: Daily long-short return series.
        ax: Optional matplotlib Axes.
        title: Plot title.

    Returns:
        matplotlib Axes.
    """
    with plt.rc_context(_STYLE_DEFAULTS):
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 4))

        cum = (1 + ls_returns).cumprod() - 1
        ax.fill_between(cum.index, 0, cum.values,
                        where=cum >= 0, color="#4CAF50", alpha=0.3)
        ax.fill_between(cum.index, 0, cum.values,
                        where=cum < 0, color="#F44336", alpha=0.3)
        ax.plot(cum.index, cum.values, color="#1565C0", linewidth=1.5)
        ax.axhline(0, color="black", linewidth=0.5)

        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_ylabel("Cumulative Return")
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
        ax.tick_params(axis="x", rotation=45)

    return ax


def plot_ic_decay(
    decay_df: pd.DataFrame,
    ax: plt.Axes = None,
    title: str = "IC Decay by Horizon",
) -> plt.Axes:
    """Plot IC and ICIR across forward return horizons.

    Args:
        decay_df: Output of compute_ic_decay.
        ax: Optional matplotlib Axes.
        title: Plot title.

    Returns:
        matplotlib Axes.
    """
    with plt.rc_context(_STYLE_DEFAULTS):
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 4))

        horizons = decay_df.index
        ax.bar(horizons, decay_df["mean_rank_ic"].abs(), color="#42A5F5",
               alpha=0.6, label="|RankIC|")
        ax2 = ax.twinx()
        ax2.plot(horizons, decay_df["rank_icir"].abs(), color="#FF9800",
                 linewidth=2, marker="o", markersize=5, label="|RankICIR|")

        ax.set_xlabel("Forward Horizon (days)")
        ax.set_ylabel("|RankIC|", color="#42A5F5")
        ax2.set_ylabel("|RankICIR|", color="#FF9800")
        ax.set_title(title, fontsize=12, fontweight="bold")

        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc="upper right", fontsize=8)

    return ax


def plot_factor_correlation_heatmap(
    corr_matrix: pd.DataFrame,
    ax: plt.Axes = None,
    title: str = "Factor Correlation Matrix",
) -> plt.Axes:
    """Annotated heatmap of cross-factor correlations.

    Args:
        corr_matrix: Output of compute_factor_correlation.
        ax: Optional matplotlib Axes.
        title: Plot title.

    Returns:
        matplotlib Axes.
    """
    with plt.rc_context(_STYLE_DEFAULTS):
        if ax is None:
            size = max(6, len(corr_matrix) * 0.6)
            fig, ax = plt.subplots(figsize=(size, size))

        mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
        sns.heatmap(
            corr_matrix, mask=mask, annot=True, fmt=".2f",
            cmap="RdBu_r", center=0, vmin=-1, vmax=1,
            square=True, ax=ax, linewidths=0.5,
            cbar_kws={"shrink": 0.8},
        )
        ax.set_title(title, fontsize=12, fontweight="bold")

    return ax


def plot_factor_report(
    factor_name: str,
    ic_series: pd.DataFrame,
    quantile_summary: pd.DataFrame,
    ls_returns: pd.Series,
    decay_df: pd.DataFrame = None,
    ic_summary: dict = None,
    save_path: str = None,
) -> plt.Figure:
    """Composite single-page factor tearsheet.

    Produces a 6-panel figure:
        Row 1: IC time series (full width)
        Row 2: IC histogram | Quantile returns | L/S equity curve
        Row 3: IC decay (if provided)

    Args:
        factor_name: Human-readable factor name for the title.
        ic_series: Output of compute_ic_series.
        quantile_summary: Output of compute_quantile_summary.
        ls_returns: Output of compute_long_short_returns.
        decay_df: Optional output of compute_ic_decay.
        ic_summary: Optional output of compute_ic_summary (for header stats).
        save_path: Optional file path to save the figure.

    Returns:
        matplotlib Figure.
    """
    has_decay = decay_df is not None and not decay_df.empty
    n_rows = 3 if has_decay else 2
    height_ratios = [2, 1.5, 1.5] if has_decay else [2, 1.5]

    with plt.rc_context(_STYLE_DEFAULTS):
        fig = plt.figure(figsize=(16, 4 * n_rows))
        gs = fig.add_gridspec(n_rows, 3, height_ratios=height_ratios,
                              hspace=0.35, wspace=0.3)

        # Row 1: IC time series (spanning all 3 columns)
        ax1 = fig.add_subplot(gs[0, :])
        plot_ic_time_series(ic_series, ax=ax1, title=f"{factor_name} — IC Time Series")

        # Row 2: IC histogram | Quantile returns | L/S curve
        ax2 = fig.add_subplot(gs[1, 0])
        plot_ic_histogram(ic_series, ax=ax2, title="IC Distribution")

        ax3 = fig.add_subplot(gs[1, 1])
        plot_quantile_returns(quantile_summary, ax=ax3, title="Quantile Returns")

        ax4 = fig.add_subplot(gs[1, 2])
        plot_cumulative_long_short(ls_returns, ax=ax4, title="L/S Cumulative")

        # Row 3: IC decay (if available)
        if has_decay:
            ax5 = fig.add_subplot(gs[2, :2])
            plot_ic_decay(decay_df, ax=ax5, title="IC Decay by Horizon")

            # Stats box
            ax6 = fig.add_subplot(gs[2, 2])
            ax6.axis("off")
            if ic_summary:
                stats_text = (
                    f"Mean IC:     {ic_summary['mean_ic']:.4f}\n"
                    f"Mean RankIC: {ic_summary['mean_rank_ic']:.4f}\n"
                    f"ICIR:        {ic_summary['icir']:.4f}\n"
                    f"RankICIR:    {ic_summary['rank_icir']:.4f}\n"
                    f"IC Hit Rate: {ic_summary['ic_hit_rate']:.2%}\n"
                    f"Days:        {ic_summary['n_days']}"
                )
                ax6.text(
                    0.1, 0.5, stats_text,
                    transform=ax6.transAxes, fontsize=11,
                    verticalalignment="center", fontfamily="monospace",
                    bbox=dict(boxstyle="round,pad=0.5", facecolor="#E3F2FD",
                              edgecolor="#90CAF9"),
                )
                ax6.set_title("Summary Statistics", fontsize=12, fontweight="bold")

        # Super title
        fig.suptitle(
            f"Factor Analysis Report: {factor_name}",
            fontsize=14, fontweight="bold", y=1.01,
        )

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches="tight")
            logger.info("Factor report saved to %s", save_path)

    return fig
