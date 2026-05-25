"""
ElasticNet wrapper for cross-sectional factor combination research.

This keeps the model API aligned with the existing LightGBM/XGBoost wrappers:
fit, predict, save, load, and factor-importance style accessors.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

import pandas as pd
from sklearn.linear_model import ElasticNet


LOGGER = logging.getLogger(__name__)


class ElasticNetModel:
    """Small sklearn ElasticNet wrapper with stable persistence helpers."""

    _DEFAULT_PARAMS = {
        "alpha": 0.001,
        "l1_ratio": 0.5,
        "fit_intercept": True,
        "max_iter": 5000,
        "tol": 1e-4,
        "random_state": 42,
        "selection": "cyclic",
    }

    def __init__(self, **params):
        self.params = {**self._DEFAULT_PARAMS, **params}
        self.model: ElasticNet | None = None
        self._feature_names: list[str] | None = None

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_valid: pd.DataFrame | None = None,
        y_valid: pd.Series | None = None,
    ) -> "ElasticNetModel":
        """Train the ElasticNet model.

        Validation inputs are accepted for API compatibility with the tree
        wrappers, even though sklearn ElasticNet does not use them directly.
        """
        self._feature_names = list(X_train.columns)
        self.model = ElasticNet(**self.params)
        LOGGER.info(
            "Training ElasticNet: %d train / %s valid samples, %d features, alpha=%.6f, l1_ratio=%.3f",
            len(X_train),
            "none" if X_valid is None else str(len(X_valid)),
            X_train.shape[1],
            float(self.params["alpha"]),
            float(self.params["l1_ratio"]),
        )
        self.model.fit(X_train, y_train)
        return self

    def predict(self, X_test: pd.DataFrame) -> pd.Series:
        if self.model is None:
            raise ValueError("Model is not fitted yet.")
        preds = self.model.predict(X_test)
        return pd.Series(preds, index=X_test.index, name="prediction")

    def coefficients(self) -> pd.Series:
        if self.model is None:
            raise ValueError("Model is not fitted yet.")
        if self._feature_names is None:
            raise ValueError("Feature names are missing.")
        return pd.Series(self.model.coef_, index=self._feature_names, name="coefficient")

    def feature_importance(self) -> pd.Series:
        coef = self.coefficients().abs().rename("abs_coefficient")
        return coef.sort_values(ascending=False)

    def save(self, path: str) -> None:
        if self.model is None:
            raise ValueError("Model is not fitted yet.")
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as handle:
            pickle.dump(
                {
                    "model": self.model,
                    "params": self.params,
                    "feature_names": self._feature_names,
                },
                handle,
            )
        LOGGER.info("ElasticNet model saved to %s", target)

    @classmethod
    def load(cls, path: str) -> "ElasticNetModel":
        target = Path(path)
        with target.open("rb") as handle:
            payload = pickle.load(handle)
        instance = cls(**payload["params"])
        instance.model = payload["model"]
        instance._feature_names = list(payload["feature_names"])
        LOGGER.info("ElasticNet model loaded from %s", target)
        return instance
