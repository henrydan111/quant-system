"""
Factor Evaluation Toolkit (因子评估工具箱)

A reusable library for rigorous single-factor analysis. Provides IC/ICIR
computation (wrapping Qlib), quantile portfolio analysis, factor neutralization,
decay analysis, cross-factor correlation, and publication-quality visualizations.

Usage:
    from src.alpha_research.factor_eval import (
        compute_ic_series, compute_ic_summary, compute_ic_by_year,
        compute_quantile_returns, compute_quantile_summary,
        compute_long_short_returns, test_monotonicity,
        neutralize, neutralize_size, neutralize_industry,
        compute_ic_decay, find_optimal_horizon,
        compute_factor_correlation, find_redundant_pairs, select_uncorrelated,
    )

Data Convention:
    All functions expect pd.Series or pd.DataFrame with
    MultiIndex(datetime, instrument) — the standard output of
    qlib.data.D.features().
"""

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
    test_monotonicity,
)
from src.alpha_research.factor_eval.neutralization import (
    neutralize,
    neutralize_size,
    neutralize_industry,
    neutralize_size_industry,
)
from src.alpha_research.factor_eval.decay_analysis import (
    compute_ic_decay,
    find_optimal_horizon,
)
from src.alpha_research.factor_eval.correlation import (
    compute_factor_correlation,
    find_redundant_pairs,
    select_uncorrelated,
)
from src.alpha_research.factor_eval.cost_aware_eval import (
    annualized_turnover,
    cost_adjusted_returns,
    cost_adjusted_sharpe,
)
from src.alpha_research.factor_eval.regime import summarize_regime_performance, regime_pass_count
from src.alpha_research.factor_eval.statistical_tests import (
    bootstrap_sharpe_ci,
    deflated_sharpe_ratio,
    probabilistic_sharpe_ratio,
)

__all__ = [
    # IC Analysis
    "compute_ic_series",
    "compute_ic_summary",
    "compute_ic_by_year",
    "compute_rolling_ic",
    "compute_ic_by_group",
    "compute_marginal_ic",
    # Quantile Analysis
    "compute_quantile_returns",
    "compute_quantile_summary",
    "compute_long_short_returns",
    "test_monotonicity",
    # Neutralization
    "neutralize",
    "neutralize_size",
    "neutralize_industry",
    "neutralize_size_industry",
    # Decay
    "compute_ic_decay",
    "find_optimal_horizon",
    # Correlation
    "compute_factor_correlation",
    "find_redundant_pairs",
    "select_uncorrelated",
    # Cost-aware evaluation
    "annualized_turnover",
    "cost_adjusted_returns",
    "cost_adjusted_sharpe",
    # Regime
    "summarize_regime_performance",
    "regime_pass_count",
    # Statistical rigor
    "bootstrap_sharpe_ci",
    "probabilistic_sharpe_ratio",
    "deflated_sharpe_ratio",
]
