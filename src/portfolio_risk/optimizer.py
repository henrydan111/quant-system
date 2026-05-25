"""
Portfolio Optimizer
Uses cvxpy to find optimal weights given alpha forecasts and risk constraints.
"""
import cvxpy as cp
import logging
import numpy as np
import yaml


logger = logging.getLogger(__name__)


class PortfolioOptimizer:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)["risk"]
        
        self.max_weight = self.config["single_stock_max_weight"]
        self.max_leverage = self.config["max_leverage"]
        
    def optimize(self, expected_returns: np.ndarray, cov_matrix: np.ndarray, current_weights: np.ndarray = None):
        """
        Maximize: w^T * mu - lambda * w^T * Cov * w - cost(|w - w_0|)
        Subject to: sum(w) = 1 (or bounded by leverage), 0 <= w_i <= max_weight
        """
        expected_returns = np.asarray(expected_returns, dtype=float)
        cov_matrix = np.asarray(cov_matrix, dtype=float)
        n = len(expected_returns)
        if n == 0:
            return np.array([], dtype=float)
        if cov_matrix.shape != (n, n):
            raise ValueError(f"cov_matrix must have shape {(n, n)}, got {cov_matrix.shape}")
        if current_weights is not None:
            current_weights = np.asarray(current_weights, dtype=float)
            if current_weights.shape != (n,):
                raise ValueError(f"current_weights must have shape {(n,)}, got {current_weights.shape}")

        w = cp.Variable(n)
        
        # Hyperparameters (should ideally be calibrated)
        risk_aversion = 1.0
        
        # Objective
        portfolio_return = expected_returns.T @ w
        portfolio_risk = cp.quad_form(w, cov_matrix)
        
        objective_expr = portfolio_return - risk_aversion * portfolio_risk
        
        # Constraints
        constraints = [
            cp.sum(w) <= self.max_leverage,
            cp.sum(w) >= 0.9, # fully invested
            w >= 0,           # long only constraint (if required)
            w <= self.max_weight
        ]
        
        # Turnover penalty
        if current_weights is not None:
            turnover = cp.norm(w - current_weights, 1)
            objective_expr -= 0.01 * turnover # Turnover penalty coefficient
            
        prob = cp.Problem(cp.Maximize(objective_expr), constraints)
        
        installed = set(cp.installed_solvers())
        for solver in ("CLARABEL", "ECOS", "OSQP", "SCS"):
            if solver not in installed:
                continue
            try:
                prob.solve(solver=solver)
            except Exception as exc:
                logger.warning("Optimization failed with solver %s: %s", solver, exc)
                continue
            if prob.status in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE} and w.value is not None:
                return np.asarray(w.value, dtype=float).reshape(n)
            logger.warning("Optimization solver %s returned status %s", solver, prob.status)

        logger.warning("Optimization failed with all available solvers; falling back to equal weights.")
        return np.ones(n, dtype=float) / n
