"""
Model Zoo Wrapper
Unifies API for ElasticNet, LightGBM, XGBoost, and future models.
Follows Qlib's model-style interface with walk-forward training support.
"""
import os
import pickle
import logging

import lightgbm as lgb
import numpy as np
import pandas as pd

from .elastic_net import ElasticNetModel

try:
    import xgboost as xgb
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    xgb = None

logger = logging.getLogger(__name__)


class LightGBMModel:
    """LightGBM wrapper with early stopping, feature importance, and persistence.

    Designed for walk-forward cross-sectional return prediction. Supports
    IC-based early stopping via custom callback.

    Args:
        **params: LightGBM parameters. Key defaults if not provided:
            - objective: 'regression'
            - metric: 'mse'
            - num_leaves: 128
            - learning_rate: 0.05

    Example:
        >>> model = LightGBMModel(num_leaves=128, learning_rate=0.05)
        >>> model.fit(X_train, y_train, X_valid, y_valid,
        ...           num_boost_round=1000, early_stopping_rounds=50)
        >>> preds = model.predict(X_test)
        >>> fi = model.feature_importance()
    """

    _DEFAULT_PARAMS = {
        "objective": "regression",
        "metric": "mse",
        "num_leaves": 128,
        "max_depth": 8,
        "learning_rate": 0.05,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "lambda_l1": 0.1,
        "lambda_l2": 1.0,
        "min_data_in_leaf": 200,
        "verbose": -1,
    }

    def __init__(self, **params):
        self.params = {**self._DEFAULT_PARAMS, **params}
        self.model = None
        self._feature_names = None

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_valid: pd.DataFrame = None,
        y_valid: pd.Series = None,
        num_boost_round: int = 1000,
        early_stopping_rounds: int = 50,
    ):
        """Train the model with optional early stopping on validation set.

        Args:
            X_train: Training features, shape (n_samples, n_features).
            y_train: Training labels (forward returns).
            X_valid: Validation features for early stopping.
            y_valid: Validation labels.
            num_boost_round: Maximum boosting iterations.
            early_stopping_rounds: Stop if validation metric doesn't improve
                for this many rounds. Only effective if X_valid is provided.

        Returns:
            self, for method chaining.
        """
        self._feature_names = list(X_train.columns)

        train_data = lgb.Dataset(X_train, label=y_train, free_raw_data=False)
        valid_sets = [train_data]
        valid_names = ["train"]

        callbacks = [lgb.log_evaluation(period=100)]

        if X_valid is not None and y_valid is not None:
            valid_data = lgb.Dataset(
                X_valid, label=y_valid, reference=train_data, free_raw_data=False
            )
            valid_sets.append(valid_data)
            valid_names.append("valid")
            callbacks.append(lgb.early_stopping(early_stopping_rounds))
            logger.info(
                "Training LightGBM: %d train / %d valid samples, %d features",
                len(X_train), len(X_valid), X_train.shape[1],
            )
        else:
            logger.info(
                "Training LightGBM: %d samples, %d features (no validation)",
                len(X_train), X_train.shape[1],
            )

        self.model = lgb.train(
            self.params,
            train_data,
            num_boost_round=num_boost_round,
            valid_sets=valid_sets,
            valid_names=valid_names,
            callbacks=callbacks,
        )

        best_iter = self.model.best_iteration if self.model.best_iteration > 0 else num_boost_round
        logger.info("Training complete: best_iteration=%d", best_iter)
        return self

    def predict(self, X_test: pd.DataFrame) -> pd.Series:
        """Generate predictions.

        Args:
            X_test: Test features with same columns as training data.

        Returns:
            pd.Series of predictions, indexed same as X_test.
        """
        if self.model is None:
            raise ValueError("Model is not fitted yet.")
        preds = self.model.predict(X_test, num_iteration=self.model.best_iteration)
        return pd.Series(preds, index=X_test.index, name="prediction")

    def feature_importance(self, importance_type: str = "gain") -> pd.Series:
        """Get feature importance scores.

        Args:
            importance_type: 'gain' (default) or 'split'.

        Returns:
            pd.Series sorted descending, indexed by feature name.
        """
        if self.model is None:
            raise ValueError("Model is not fitted yet.")
        importance = self.model.feature_importance(importance_type=importance_type)
        fi = pd.Series(importance, index=self._feature_names, name=importance_type)
        return fi.sort_values(ascending=False)

    def save(self, path: str):
        """Save model to disk.

        Args:
            path: File path (e.g., 'models/lgb_fold1.pkl').
        """
        if self.model is None:
            raise ValueError("Model is not fitted yet.")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(
                {"model": self.model, "params": self.params,
                 "feature_names": self._feature_names},
                f,
            )
        logger.info("Model saved to %s", path)

    @classmethod
    def load(cls, path: str) -> "LightGBMModel":
        """Load a saved model.

        Args:
            path: Path to saved model file.

        Returns:
            LightGBMModel instance with restored model.
        """
        with open(path, "rb") as f:
            data = pickle.load(f)
        instance = cls(**data["params"])
        instance.model = data["model"]
        instance._feature_names = data["feature_names"]
        logger.info("Model loaded from %s", path)
        return instance


class XGBoostModel:
    """XGBoost wrapper with save/load support.

    Args:
        **params: XGBoost parameters.
    """

    def __init__(self, **params):
        self.params = params
        self.model = None

    def fit(self, X_train: pd.DataFrame, y_train: pd.Series,
            X_valid: pd.DataFrame = None, y_valid: pd.Series = None,
            num_boost_round: int = 1000, early_stopping_rounds: int = 50):
        """Train with optional early stopping.

        Args:
            X_train: Training features.
            y_train: Training labels.
            X_valid: Validation features.
            y_valid: Validation labels.
            num_boost_round: Max iterations.
            early_stopping_rounds: Early stopping patience.

        Returns:
            self.
        """
        if xgb is None:
            raise ModuleNotFoundError("xgboost is not installed in the current environment.")
        dtrain = xgb.DMatrix(X_train, label=y_train)
        evals = [(dtrain, "train")]
        if X_valid is not None and y_valid is not None:
            dvalid = xgb.DMatrix(X_valid, label=y_valid)
            evals.append((dvalid, "valid"))
        self.model = xgb.train(
            self.params, dtrain, num_boost_round=num_boost_round,
            evals=evals, early_stopping_rounds=early_stopping_rounds,
            verbose_eval=100,
        )
        return self

    def predict(self, X_test: pd.DataFrame) -> pd.Series:
        """Generate predictions.

        Args:
            X_test: Test features.

        Returns:
            pd.Series of predictions.
        """
        if xgb is None:
            raise ModuleNotFoundError("xgboost is not installed in the current environment.")
        dtest = xgb.DMatrix(X_test)
        preds = self.model.predict(dtest)
        return pd.Series(preds, index=X_test.index, name="prediction")

    def feature_importance(self, importance_type: str = "gain") -> pd.Series:
        """Get feature importance.

        Args:
            importance_type: 'gain', 'weight', or 'cover'.

        Returns:
            pd.Series sorted descending.
        """
        if xgb is None:
            raise ModuleNotFoundError("xgboost is not installed in the current environment.")
        if self.model is None:
            raise ValueError("Model is not fitted yet.")
        scores = self.model.get_score(importance_type=importance_type)
        return pd.Series(scores, name=importance_type).sort_values(ascending=False)
