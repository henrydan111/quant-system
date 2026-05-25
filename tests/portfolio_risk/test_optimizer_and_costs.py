import numpy as np

from src.portfolio_risk.cost_models import MarketImpactModel
from src.portfolio_risk.optimizer import PortfolioOptimizer


def test_market_impact_model_adds_convex_participation_penalty():
    model = MarketImpactModel(commission_rate=0.0003, stamp_duty=0.001)
    trade_amount = np.array([100_000.0, -200_000.0])
    adv = np.array([10_000_000.0, 5_000_000.0])

    costs_with_adv = model.estimate_cost(trade_amount, adv=adv)
    flat_costs = model.estimate_cost(trade_amount)

    assert np.all(costs_with_adv > flat_costs)
    expected_flat = np.abs(trade_amount) * (0.0003 + 0.001 / 2.0)
    np.testing.assert_allclose(flat_costs, expected_flat)


def test_optimizer_turnover_penalty_path_returns_feasible_weight_vector(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
risk:
  max_drawdown_limit: 0.15
  max_leverage: 1.05
  single_stock_max_weight: 0.20
""".strip(),
        encoding="utf-8",
    )

    optimizer = PortfolioOptimizer(config_path=str(config_path))
    expected_returns = np.array([0.08, 0.06, 0.05, 0.03, 0.02])
    cov_matrix = np.diag([0.04, 0.03, 0.025, 0.02, 0.015])
    current_weights = np.ones(5) / 5

    weights = optimizer.optimize(expected_returns, cov_matrix, current_weights=current_weights)

    assert weights.shape == (5,)
    assert np.isfinite(weights).all()
    assert weights.sum() >= 0.89
    assert weights.sum() <= 1.06
    assert weights.min() >= -1e-6
    assert weights.max() <= 0.200001
