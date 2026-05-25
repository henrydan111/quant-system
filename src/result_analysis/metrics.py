"""
Backtest Performance Metrics

Provides functions for computing standard quantitative strategy
performance metrics from daily return series.

All functions expect a pd.Series of **simple daily returns**
(not log returns) with a DatetimeIndex.
"""

import numpy as np
import pandas as pd
from typing import Tuple


# ─── Core Return Metrics ──────────────────────────────────────────

def calculate_total_return(returns: pd.Series) -> float:
    """
    Total compounded return over the full period.

    Formula: prod(1 + r_i) - 1
    """
    if returns.empty:
        return 0.0
    return (1 + returns).prod() - 1


def calculate_cagr(returns: pd.Series, annual_factor: int = 252) -> float:
    """
    Compound Annual Growth Rate.

    Formula: (1 + total_return) ^ (252 / N) - 1
    """
    if len(returns) < 2:
        return 0.0
    total = calculate_total_return(returns)
    n_years = len(returns) / annual_factor
    if n_years <= 0 or total <= -1:
        return 0.0
    return (1 + total) ** (1 / n_years) - 1


# ─── Risk Metrics ─────────────────────────────────────────────────

def calculate_volatility(returns: pd.Series, annual_factor: int = 252) -> float:
    """
    Annualized volatility (standard deviation of returns).

    Formula: std(r) * sqrt(252)
    """
    if returns.empty:
        return 0.0
    return returns.std() * np.sqrt(annual_factor)


def calculate_downside_volatility(returns: pd.Series,
                                   target: float = 0.0,
                                   annual_factor: int = 252) -> float:
    """
    Annualized downside volatility (semi-deviation below target).

    Formula: std(r[r < target]) * sqrt(252)
    """
    downside = returns[returns < target]
    if downside.empty:
        return 0.0
    return downside.std() * np.sqrt(annual_factor)


def calculate_max_drawdown(returns: pd.Series) -> float:
    """
    Maximum Drawdown — largest peak-to-trough decline.

    Returns:
        Negative float (e.g., -0.35 means -35% drawdown).
    """
    if returns.empty:
        return 0.0
    cumulative = (1 + returns).cumprod()
    peak = cumulative.expanding(min_periods=1).max()
    drawdown = (cumulative - peak) / peak
    return drawdown.min()


def calculate_max_drawdown_duration(returns: pd.Series) -> int:
    """
    Maximum Drawdown Duration — longest period (in trading days)
    spent below the previous high-water mark.

    Returns:
        Number of trading days.
    """
    if returns.empty:
        return 0
    cumulative = (1 + returns).cumprod()
    peak = cumulative.expanding(min_periods=1).max()
    underwater = cumulative < peak

    max_duration = 0
    current_duration = 0
    for is_under in underwater:
        if is_under:
            current_duration += 1
            max_duration = max(max_duration, current_duration)
        else:
            current_duration = 0

    return max_duration


def calculate_drawdown_series(returns: pd.Series) -> pd.Series:
    """
    Full drawdown time series.

    Returns:
        pd.Series of drawdown values (negative, same index as returns).
    """
    if returns.empty:
        return pd.Series(dtype=float)
    cumulative = (1 + returns).cumprod()
    peak = cumulative.expanding(min_periods=1).max()
    return (cumulative - peak) / peak


# ─── Risk-Adjusted Metrics ────────────────────────────────────────

def calculate_sharpe_ratio(returns: pd.Series,
                           risk_free_rate: float = 0.0,
                           annual_factor: int = 252) -> float:
    """
    Annualized Sharpe Ratio.

    Formula: sqrt(252) * mean(r - rf) / std(r - rf)

    Args:
        risk_free_rate: Annual risk-free rate (e.g., 0.02 for 2%).
    """
    if returns.empty or returns.std() == 0:
        return 0.0
    daily_rf = (1 + risk_free_rate) ** (1 / annual_factor) - 1
    excess = returns - daily_rf
    return np.sqrt(annual_factor) * excess.mean() / excess.std()


def calculate_sortino_ratio(returns: pd.Series,
                            risk_free_rate: float = 0.0,
                            annual_factor: int = 252) -> float:
    """
    Annualized Sortino Ratio — like Sharpe but penalizes only downside.

    Formula: sqrt(252) * mean(r - rf) / downside_std(r - rf)
    """
    if returns.empty:
        return 0.0
    daily_rf = (1 + risk_free_rate) ** (1 / annual_factor) - 1
    excess = returns - daily_rf
    downside = excess[excess < 0]
    if downside.empty or downside.std() == 0:
        return 0.0
    return np.sqrt(annual_factor) * excess.mean() / downside.std()


def calculate_calmar_ratio(returns: pd.Series,
                           annual_factor: int = 252) -> float:
    """
    Calmar Ratio — CAGR / |Max Drawdown|.

    Higher is better. Measures return per unit of drawdown risk.
    """
    cagr = calculate_cagr(returns, annual_factor)
    mdd = calculate_max_drawdown(returns)
    if mdd == 0:
        return 0.0
    return cagr / abs(mdd)


def calculate_information_ratio(strategy_returns: pd.Series,
                                benchmark_returns: pd.Series,
                                annual_factor: int = 252) -> float:
    """
    Information Ratio — risk-adjusted excess return vs benchmark.

    Formula: sqrt(252) * mean(r_s - r_b) / std(r_s - r_b)
    """
    if strategy_returns.empty or benchmark_returns.empty:
        return 0.0
    excess = strategy_returns - benchmark_returns
    if excess.std() == 0:
        return 0.0
    return np.sqrt(annual_factor) * excess.mean() / excess.std()


# ─── Regression Metrics ───────────────────────────────────────────

def calculate_alpha_beta(strategy_returns: pd.Series,
                         benchmark_returns: pd.Series,
                         annual_factor: int = 252) -> Tuple[float, float]:
    """
    CAPM Alpha and Beta via OLS regression.

    Formula: r_s = alpha + beta * r_b + epsilon

    Returns:
        (annualized_alpha, beta) tuple.
    """
    if strategy_returns.empty or benchmark_returns.empty:
        return (0.0, 0.0)
    # Align
    common = strategy_returns.index.intersection(benchmark_returns.index)
    if len(common) < 10:
        return (0.0, 0.0)
    y = strategy_returns.loc[common].values
    x = benchmark_returns.loc[common].values
    # OLS: beta = cov(x,y)/var(x), alpha = mean(y) - beta*mean(x)
    cov_matrix = np.cov(x, y)
    if cov_matrix[0, 0] == 0:
        return (0.0, 0.0)
    beta = cov_matrix[0, 1] / cov_matrix[0, 0]
    daily_alpha = y.mean() - beta * x.mean()
    annual_alpha = daily_alpha * annual_factor
    return (annual_alpha, beta)


# ─── Distribution Metrics ─────────────────────────────────────────

def calculate_win_rate(returns: pd.Series) -> float:
    """
    Percentage of positive return days.
    """
    if returns.empty:
        return 0.0
    return (returns > 0).mean()


def calculate_profit_factor(returns: pd.Series) -> float:
    """
    Profit Factor — sum of gains / |sum of losses|.

    Formula: sum(r[r > 0]) / |sum(r[r < 0])|

    Returns:
        Ratio >= 0. Values > 1 mean net profitable.
    """
    gains = returns[returns > 0].sum()
    losses = abs(returns[returns < 0].sum())
    if losses == 0:
        return float('inf') if gains > 0 else 0.0
    return gains / losses


def calculate_tail_ratio(returns: pd.Series,
                         quantile: float = 0.05) -> float:
    """
    Tail Ratio — right tail vs left tail behavior.

    Formula: |percentile(r, 1-q)| / |percentile(r, q)|

    Values > 1 indicate fatter right tail (good).
    """
    if returns.empty:
        return 0.0
    right = abs(returns.quantile(1 - quantile))
    left = abs(returns.quantile(quantile))
    if left == 0:
        return 0.0
    return right / left


def calculate_profit_loss_ratio(returns: pd.Series) -> float:
    """Profit/Loss Ratio (盈亏比) — average win / |average loss|.

    JoinQuant definition: mean(r[r>0]) / |mean(r[r<0])|

    Args:
        returns: Daily return series.

    Returns:
        Ratio >= 0. Values > 1 indicate larger average wins than losses.
    """
    winners = returns[returns > 0]
    losers = returns[returns < 0]
    if losers.empty or winners.empty:
        return 0.0
    return winners.mean() / abs(losers.mean())


def calculate_max_drawdown_period(returns: pd.Series) -> tuple:
    """Maximum Drawdown Period (最大回撤区间).

    Finds the start date (peak) and end date (trough) of the
    worst drawdown in the return series.

    Args:
        returns: Daily return series with DatetimeIndex.

    Returns:
        (start_date, end_date) as 'YYYY/MM/DD' strings.
    """
    if returns.empty:
        return ('', '')
    cumulative = (1 + returns).cumprod()
    peak = cumulative.expanding(min_periods=1).max()
    dd = (cumulative - peak) / peak

    # End of max drawdown = date of worst trough
    end_idx = dd.idxmin()

    # Start of max drawdown = date of the peak before the trough
    peak_before = cumulative.loc[:end_idx]
    start_idx = peak_before.idxmax()

    return (start_idx.strftime('%Y/%m/%d'), end_idx.strftime('%Y/%m/%d'))


def calculate_skewness(returns: pd.Series) -> float:
    """Daily return skewness."""
    if returns.empty:
        return 0.0
    return returns.skew()


def calculate_kurtosis(returns: pd.Series) -> float:
    """Daily return excess kurtosis (Fisher definition)."""
    if returns.empty:
        return 0.0
    return returns.kurtosis()


# ─── Period Aggregation ───────────────────────────────────────────

def calculate_monthly_returns(returns: pd.Series) -> pd.Series:
    """
    Aggregate daily returns into monthly compounded returns.

    Returns:
        pd.Series indexed by month period.
    """
    if returns.empty:
        return pd.Series(dtype=float)
    monthly = returns.groupby(returns.index.to_period('M')).apply(
        lambda x: (1 + x).prod() - 1
    )
    return monthly


def calculate_yearly_returns(returns: pd.Series) -> pd.Series:
    """
    Aggregate daily returns into yearly compounded returns.

    Returns:
        pd.Series indexed by year.
    """
    if returns.empty:
        return pd.Series(dtype=float)
    yearly = returns.groupby(returns.index.year).apply(
        lambda x: (1 + x).prod() - 1
    )
    yearly.index.name = 'Year'
    return yearly


def calculate_monthly_return_table(returns: pd.Series) -> pd.DataFrame:
    """
    Year × Month return pivot table for heatmap visualization.

    Returns:
        DataFrame with years as rows, months (1–12) as columns.
    """
    if returns.empty:
        return pd.DataFrame()
    monthly = calculate_monthly_returns(returns)
    df = monthly.to_frame('return')
    df['year'] = monthly.index.year
    df['month'] = monthly.index.month
    pivot = df.pivot_table(values='return', index='year', columns='month')
    pivot.columns = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                     'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    return pivot


# ─── Rolling Metrics ──────────────────────────────────────────────

def calculate_rolling_sharpe(returns: pd.Series,
                             window: int = 252,
                             risk_free_rate: float = 0.0,
                             annual_factor: int = 252) -> pd.Series:
    """Rolling annualized Sharpe ratio."""
    daily_rf = (1 + risk_free_rate) ** (1 / annual_factor) - 1
    excess = returns - daily_rf
    rolling_mean = excess.rolling(window).mean()
    rolling_std = excess.rolling(window).std()
    return (rolling_mean / rolling_std * np.sqrt(annual_factor)).dropna()


def calculate_rolling_volatility(returns: pd.Series,
                                 window: int = 60,
                                 annual_factor: int = 252) -> pd.Series:
    """Rolling annualized volatility."""
    return (returns.rolling(window).std() * np.sqrt(annual_factor)).dropna()


def calculate_rolling_return(returns: pd.Series,
                             window: int = 252) -> pd.Series:
    """Rolling compounded return over the window."""
    return returns.rolling(window).apply(
        lambda x: (1 + x).prod() - 1, raw=False
    ).dropna()


# ─── Comprehensive Report ─────────────────────────────────────────

def generate_performance_report(strategy_returns: pd.Series,
                                benchmark_returns: pd.Series = None,
                                risk_free_rate: float = 0.02) -> pd.DataFrame:
    """
    Generate a comprehensive performance metrics DataFrame.

    Args:
        strategy_returns: Daily net return series.
        benchmark_returns: Optional daily benchmark return series.
        risk_free_rate: Annual risk-free rate (default 2%).

    Returns:
        DataFrame with metric names as index, Strategy/Benchmark as columns.
    """
    metrics = {
        'Total Return': calculate_total_return(strategy_returns),
        'CAGR': calculate_cagr(strategy_returns),
        'Annualized Volatility': calculate_volatility(strategy_returns),
        'Sharpe Ratio': calculate_sharpe_ratio(strategy_returns, risk_free_rate),
        'Sortino Ratio': calculate_sortino_ratio(strategy_returns, risk_free_rate),
        'Calmar Ratio': calculate_calmar_ratio(strategy_returns),
        'Max Drawdown': calculate_max_drawdown(strategy_returns),
        'Max DD Duration (days)': calculate_max_drawdown_duration(strategy_returns),
        'Win Rate': calculate_win_rate(strategy_returns),
        'Profit Factor': calculate_profit_factor(strategy_returns),
        'Tail Ratio': calculate_tail_ratio(strategy_returns),
        'Skewness': calculate_skewness(strategy_returns),
        'Kurtosis': calculate_kurtosis(strategy_returns),
        'Trading Days': len(strategy_returns),
    }

    df = pd.DataFrame([metrics], index=['Strategy']).T

    if benchmark_returns is not None:
        common = strategy_returns.index.intersection(benchmark_returns.index)
        br = benchmark_returns.loc[common]
        sr = strategy_returns.loc[common]

        bench_metrics = {
            'Total Return': calculate_total_return(br),
            'CAGR': calculate_cagr(br),
            'Annualized Volatility': calculate_volatility(br),
            'Sharpe Ratio': calculate_sharpe_ratio(br, risk_free_rate),
            'Sortino Ratio': calculate_sortino_ratio(br, risk_free_rate),
            'Calmar Ratio': calculate_calmar_ratio(br),
            'Max Drawdown': calculate_max_drawdown(br),
            'Max DD Duration (days)': calculate_max_drawdown_duration(br),
            'Win Rate': calculate_win_rate(br),
            'Profit Factor': calculate_profit_factor(br),
            'Tail Ratio': calculate_tail_ratio(br),
            'Skewness': calculate_skewness(br),
            'Kurtosis': calculate_kurtosis(br),
            'Trading Days': len(br),
        }
        df['Benchmark'] = pd.Series(bench_metrics)

        # Excess metrics
        alpha, beta = calculate_alpha_beta(sr, br)
        ir = calculate_information_ratio(sr, br)
        excess_ret = sr - br
        df.loc['Alpha (ann.)', 'Strategy'] = alpha
        df.loc['Beta', 'Strategy'] = beta
        df.loc['Information Ratio', 'Strategy'] = ir
        df.loc['Excess CAGR', 'Strategy'] = calculate_cagr(excess_ret)

    return df


# ─── Additional Win‐Rate Metrics ──────────────────────────────────

def calculate_weekly_win_rate(returns: pd.Series) -> float:
    """
    Fraction of weeks with positive compounded return (周赢率).
    """
    if returns.empty:
        return 0.0
    weekly = returns.groupby(returns.index.to_period('W')).apply(
        lambda x: (1 + x).prod() - 1
    )
    return (weekly > 0).mean()


def calculate_monthly_win_rate(returns: pd.Series) -> float:
    """
    Fraction of months with positive compounded return (月赢率).
    """
    if returns.empty:
        return 0.0
    monthly = calculate_monthly_returns(returns)
    return (monthly > 0).mean()


def calculate_tracking_error(strategy_returns: pd.Series,
                             benchmark_returns: pd.Series,
                             annual_factor: int = 252) -> float:
    """
    Annualized Tracking Error (指数跟踪误差).

    Formula: std(r_strategy - r_benchmark) * sqrt(252)
    """
    if strategy_returns.empty or benchmark_returns.empty:
        return 0.0
    excess = strategy_returns - benchmark_returns
    return excess.std() * np.sqrt(annual_factor)


# ─── Trading‐Level Statistics (果仁‐Style) ─────────────────────────

def generate_trading_stats(
    holdings: dict,
    df: pd.DataFrame,
    strategy_returns: pd.Series = None,
    benchmark_returns: pd.Series = None,
    report_df: pd.DataFrame = None,
    buy_cost: float = 0.0005,
    sell_cost: float = 0.0015,
) -> pd.Series:
    """
    Compute 果仁‐style trading statistics from holdings data.

    Args:
        holdings: Dict {pd.Timestamp: [list of stock codes]} — stocks
            held starting from each rebalance date.
        df: Full DataFrame with MultiIndex(instrument, datetime) containing
            at least 'adj_close', 'vol', 'daily_ret', 'is_limit_up',
            'is_limit_down' columns.
        strategy_returns: Optional daily return series (for win rates).
        benchmark_returns: Optional benchmark return series (for tracking error).
        report_df: Optional Qlib report DataFrame (for turnover column).
        buy_cost: Buy transaction cost fraction.
        sell_cost: Sell transaction cost fraction.

    Returns:
        pd.Series with metric name as index, suitable for display.
    """
    stats = {}
    rebal_dates = sorted(holdings.keys())
    all_dates = df.index.get_level_values(1).unique().sort_values()

    # ─── 平均持仓股票数 (Avg stocks held per rebalance) ─────────
    stock_counts = [len(v) for v in holdings.values()]
    stats['平均持仓股票数 (Avg Stocks Held)'] = np.mean(stock_counts) if stock_counts else 0

    # ─── 换股次数 (Number of stock changes) ─────────────────────
    total_changes = 0
    prev_set = set()
    for dt in rebal_dates:
        curr_set = set(holdings[dt])
        if prev_set:
            sold = prev_set - curr_set
            bought = curr_set - prev_set
            total_changes += len(sold) + len(bought)
        else:
            total_changes += len(curr_set)  # initial buy
        prev_set = curr_set
    stats['换股次数 (Stock Changes)'] = total_changes

    # ─── Build per-trade records ────────────────────────────────
    # Track each stock's entry/exit dates and compute return
    trades = []
    # Expand holdings into daily positions
    daily_positions = {}
    current_stocks = []
    for dt in all_dates:
        if dt in holdings:
            current_stocks = holdings[dt]
        if current_stocks:
            daily_positions[dt] = list(current_stocks)

    # Track stock entry/exit
    stock_entry = {}  # {stock: entry_date}
    prev_stocks = set()
    for dt in rebal_dates:
        curr_stocks = set(holdings[dt])
        # Stocks sold
        for stk in prev_stocks - curr_stocks:
            if stk in stock_entry:
                entry_dt = stock_entry.pop(stk)
                # Compute return for this trade
                try:
                    entry_price = df.loc[(stk, entry_dt), 'adj_close']
                    exit_price = df.loc[(stk, dt), 'adj_close']
                    if np.isfinite(entry_price) and np.isfinite(exit_price) and entry_price > 0:
                        trade_ret = (exit_price / entry_price) - 1 - buy_cost - sell_cost
                        hold_days = len(all_dates[(all_dates >= entry_dt) & (all_dates <= dt)])
                        trades.append({
                            'stock': stk, 'entry': entry_dt, 'exit': dt,
                            'return': trade_ret, 'hold_days': hold_days,
                        })
                except (KeyError, TypeError):
                    pass
        # Stocks bought
        for stk in curr_stocks - prev_stocks:
            stock_entry[stk] = dt
        prev_stocks = curr_stocks

    trade_df = pd.DataFrame(trades) if trades else pd.DataFrame(
        columns=['stock', 'entry', 'exit', 'return', 'hold_days']
    )

    # ─── 平均持有天数 (Avg holding days per trade) ──────────────
    stats['平均持有天数 (Avg Holding Days)'] = (
        trade_df['hold_days'].mean() if len(trade_df) > 0 else 0
    )

    # ─── 平均交易收益 (Avg trade return) ────────────────────────
    stats['平均交易收益 (Avg Trade Return)'] = (
        trade_df['return'].mean() if len(trade_df) > 0 else 0
    )

    # ─── 正收益平均 / 负收益平均 ────────────────────────────────
    winners = trade_df[trade_df['return'] > 0]['return'] if len(trade_df) > 0 else pd.Series(dtype=float)
    losers = trade_df[trade_df['return'] < 0]['return'] if len(trade_df) > 0 else pd.Series(dtype=float)
    stats['正收益平均 (Avg Winning Trade)'] = winners.mean() if len(winners) > 0 else 0
    stats['负收益平均 (Avg Losing Trade)'] = losers.mean() if len(losers) > 0 else 0

    # ─── 交易赢率 (Trade win rate) ──────────────────────────────
    stats['交易赢率 (Trade Win Rate)'] = (
        (trade_df['return'] > 0).mean() if len(trade_df) > 0 else 0
    )

    # ─── 年换手率 (Annual turnover) ─────────────────────────────
    if report_df is not None and 'turnover' in report_df.columns:
        # Qlib report: turnover is daily fraction
        stats['年换手率 (Annual Turnover)'] = report_df['turnover'].mean() * 252
    else:
        # Estimate from stock changes
        n_years = len(all_dates) / 252
        if n_years > 0:
            stats['年换手率 (Annual Turnover)'] = total_changes / n_years / np.mean(stock_counts) if np.mean(stock_counts) > 0 else 0
        else:
            stats['年换手率 (Annual Turnover)'] = 0

    # ─── 持仓停牌股票比例 (Suspended stock ratio) ───────────────
    total_held = 0
    total_suspended = 0
    for dt, stocks in daily_positions.items():
        for stk in stocks:
            total_held += 1
            try:
                vol = df.loc[(stk, dt), 'vol']
                if vol == 0 or (isinstance(vol, float) and not np.isfinite(vol)):
                    total_suspended += 1
            except KeyError:
                total_suspended += 1  # missing = suspended
    stats['持仓停牌股票比例 (Suspended Ratio)'] = (
        total_suspended / total_held if total_held > 0 else 0
    )

    # ─── 日赢率 / 周赢率 / 月赢率 ──────────────────────────────
    if strategy_returns is not None and not strategy_returns.empty:
        stats['日赢率 (Daily Win Rate)'] = calculate_win_rate(strategy_returns)
        stats['周赢率 (Weekly Win Rate)'] = calculate_weekly_win_rate(strategy_returns)
        stats['月赢率 (Monthly Win Rate)'] = calculate_monthly_win_rate(strategy_returns)

    # ─── 指数跟踪误差 (Tracking error) ─────────────────────────
    if strategy_returns is not None and benchmark_returns is not None:
        stats['指数跟踪误差 (Tracking Error)'] = calculate_tracking_error(
            strategy_returns, benchmark_returns
        )

    # ─── 调仓指令可执行比例 (Order execution rate) ──────────────
    if 'is_limit_up' in df.columns:
        total_intended = 0
        total_executable = 0
        prev_set = set()
        for dt in rebal_dates:
            curr_set = set(holdings[dt])
            to_buy = curr_set - prev_set
            for stk in to_buy:
                total_intended += 1
                try:
                    if not df.loc[(stk, dt), 'is_limit_up']:
                        total_executable += 1
                except KeyError:
                    pass
            to_sell = prev_set - curr_set
            for stk in to_sell:
                total_intended += 1
                try:
                    if not df.loc[(stk, dt), 'is_limit_down']:
                        total_executable += 1
                except KeyError:
                    pass
            prev_set = curr_set
        stats['调仓指令可执行比例 (Order Exec Rate)'] = (
            total_executable / total_intended if total_intended > 0 else 0
        )

    # ─── 平均持仓仓位 (Avg position utilization) ───────────────
    if report_df is not None and 'return' in report_df.columns:
        # Approximate: if cost > 0, there's trading → position > 0
        # A better measure: 1 - cash_ratio, but we estimate from returns
        non_zero_days = (report_df['return'].abs() > 1e-10).mean()
        stats['平均持仓仓位 (Avg Position)'] = non_zero_days
    else:
        # Manual backtest: almost always fully invested
        invested_days = sum(1 for dt in all_dates if dt in daily_positions)
        stats['平均持仓仓位 (Avg Position)'] = invested_days / len(all_dates) if len(all_dates) > 0 else 0

    return pd.Series(stats)
