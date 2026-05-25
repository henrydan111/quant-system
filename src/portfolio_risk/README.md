# Portfolio & Risk Management (`src/portfolio_risk/`)

The Portfolio Risk module translates theoretical prediction signals into actionable, real-world portfolio weights while strictly enforcing risk constraints and modeling transaction friction.

## Architecture & Responsibilities

```text
portfolio_risk/
├── optimizer.py        → class PortfolioOptimizer (cvxpy-based)
├── risk_models/
│   └── __init__.py     → class MultiFactorRiskModel (Barra-style)
└── cost_models/
    └── __init__.py     → class MarketImpactModel (slippage + commissions)
```

---

## Public API Reference

### `PortfolioOptimizer` (`optimizer.py`)

Mean-Variance optimizer using `cvxpy`. Maximizes risk-adjusted returns subject to position and leverage constraints.

| Method | Description |
|--------|-------------|
| `__init__(config_path)` | Reads `risk` section from `config.yaml` for `max_weight`, `max_leverage` |
| `optimize(expected_returns, cov_matrix, current_weights) → np.ndarray` | Solve: `max w'μ - λw'Σw - cost(|w - w₀|)` subject to `0 ≤ wᵢ ≤ max_weight`, `0.9 ≤ Σw ≤ max_leverage`. Falls back to equal-weight on failure |

**Optimization objective:**
```
Maximize:  w^T * μ  -  λ * w^T * Σ * w  -  0.01 * ||w - w_0||₁
Subject to: sum(w) ∈ [0.9, max_leverage]
            0 ≤ wᵢ ≤ max_weight
```

**Parameters from `config.yaml`:**
```yaml
risk:
  max_drawdown_limit: 0.15
  max_leverage: 1.5
  single_stock_max_weight: 0.05
```

---

### `MultiFactorRiskModel` (`risk_models/__init__.py`)

Barra-style multi-factor risk model estimating asset covariance via factor decomposition.

| Method | Description |
|--------|-------------|
| `__init__(num_factors)` | Default: 10 factors |
| `fit(returns, exposures)` | `returns`: (N_stocks, T_days). `exposures`: (N_stocks, K_factors) — e.g. Industry, Market Cap. Estimates factor covariance + idiosyncratic risk |
| `predict_portfolio_risk(weights) → float` | Computes `Risk = w' * (X * F * X' + Δ) * w` |

**Status:** Structural skeleton — `fit()` needs concrete PCA/OLS factor extraction implementation.

---

### `MarketImpactModel` (`cost_models/__init__.py`)

Models real-world transaction friction including commissions, stamp duty, and nonlinear market impact.

| Method | Description |
|--------|-------------|
| `__init__(commission_rate, stamp_duty)` | Default: commission 0.03%, stamp duty 0.1% |
| `estimate_cost(trade_amount, adv) → np.ndarray` | Base cost + optional Almgren-Chriss-style market impact: `cost = |trade| × (commission + stamp/2) + |trade| × 0.1 × √(|trade|/ADV)` |

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `cvxpy` | Convex optimization (optimizer) |
| `numpy`, `pandas` | Numerical computation |
| `pyyaml` | Config loading |

## Cross-Module Relationships

```text
alpha_research (predictions)
        ↓
  PortfolioOptimizer ← MultiFactorRiskModel (covariance)
        ↓               MarketImpactModel (cost penalty)
  target weights
        ↓
  backtest_engine (execution simulation)
```

## Usage

```python
from src.portfolio_risk.optimizer import PortfolioOptimizer

optimizer = PortfolioOptimizer()
weights = optimizer.optimize(expected_returns, cov_matrix, current_weights)
```
