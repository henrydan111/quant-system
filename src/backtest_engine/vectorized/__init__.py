"""
Vectorized Backtest Engine (向量化回测引擎)

Production-quality wrapper around Qlib's backtest infrastructure. Provides
configurable strategy, exchange, and benchmark settings with correct
A-share cost and limit modeling.

Delegates performance metrics to:
- Qlib's ``risk_analysis()`` for annualized return, IR, MDD, std
- ``result_analysis/metrics.py`` for Sharpe, Sortino, Win Rate

Usage:
    from src.backtest_engine.vectorized import VectorizedBacktester

    bt = VectorizedBacktester()
    result = bt.run(predictions, start_time="2020-01-01", end_time="2023-12-31")
    print(result.summary)
"""

import os
import logging
from typing import Any
import numpy as np
import pandas as pd
import yaml

logger = logging.getLogger(__name__)

# Default A-share exchange configuration (中国A股默认交易参数)
# NOTE on limit_threshold:
#   Our Qlib data has $change = 涨跌额 (absolute yuan), NOT percentage.
#   Qlib's float-based limit_threshold compares against $change, which fails.
#   Instead, use expression-based tuple with $pct_chg (Tushare field, in % units:
#   9.5 means 9.5%, not 0.095). This properly detects 涨跌停.
_DEFAULT_EXCHANGE_KWARGS = {
    "freq": "day",
    "limit_threshold": ("Ge($pct_chg, 9.5)", "Le($pct_chg, -9.5)"),  # 涨跌停 ±9.5%
    "deal_price": "close",        # 成交价: close / vwap
    "open_cost": 0.0005,          # 买入佣金 0.05%
    "close_cost": 0.0015,         # 卖出佣金 + 印花税 0.15%
    "min_cost": 5,                # 最低佣金 ¥5
}


class BacktestResult:
    """Container for backtest results with lazy metric computation.

    Attributes:
        report: Qlib report DataFrame (return, cost, bench, turnover per day).
        positions: Qlib Position dict (holdings per day).
        indicators: Qlib indicator dict (turnover, etc.).
        summary: Dict of summary statistics.
        config: Dict of backtest configuration used.
    """

    def __init__(self, report, positions, indicators, config):
        self.report = report
        self.positions = positions
        self.indicators = indicators
        self.config = config
        self._summary = None

    @property
    def summary(self) -> dict:
        """Lazily compute summary statistics from the report.

        Returns:
            Dict with keys: annualized_return, sharpe, sortino,
                max_drawdown, volatility, win_rate, turnover,
                excess_annualized_return, information_ratio, n_days.
        """
        if self._summary is not None:
            return self._summary

        if self.report is None or self.report.empty:
            self._summary = {}
            return self._summary

        # Use Qlib's risk_analysis for standard metrics
        try:
            from qlib.contrib.evaluate import risk_analysis
            excess_ret = self.report["return"] - self.report["bench"] - self.report["cost"]
            qlib_analysis = risk_analysis(excess_ret, freq="day")
            qlib_metrics = {
                "excess_annualized_return": float(qlib_analysis.loc["annualized_return", "risk"]),
                "information_ratio": float(qlib_analysis.loc["information_ratio", "risk"]),
            }
        except Exception as e:
            logger.warning("Qlib risk_analysis failed: %s, computing manually", e)
            qlib_metrics = {}

        # Use result_analysis for additional metrics
        try:
            from src.result_analysis.metrics import (
                calculate_sharpe_ratio,
                calculate_sortino_ratio,
                calculate_max_drawdown,
                calculate_volatility,
                calculate_win_rate,
            )
            net_returns = self.report["return"] - self.report["cost"]

            self._summary = {
                "annualized_return": float(net_returns.mean() * 252),
                "sharpe": float(calculate_sharpe_ratio(net_returns)),
                "sortino": float(calculate_sortino_ratio(net_returns)),
                "max_drawdown": float(calculate_max_drawdown(net_returns)),
                "volatility": float(calculate_volatility(net_returns)),
                "win_rate": float(calculate_win_rate(net_returns)),
                "n_days": len(net_returns),
                **qlib_metrics,
            }
        except ImportError:
            # Fallback if result_analysis not available
            net_returns = self.report["return"] - self.report["cost"]
            std = net_returns.std()
            self._summary = {
                "annualized_return": float(net_returns.mean() * 252),
                "sharpe": float(np.sqrt(252) * net_returns.mean() / std) if std > 0 else 0.0,
                "max_drawdown": float(((1 + net_returns).cumprod().cummax() - (1 + net_returns).cumprod()).max()),
                "n_days": len(net_returns),
                **qlib_metrics,
            }

        # Add turnover from indicators
        try:
            if self.indicators:
                first_freq = list(self.indicators.keys())[0]
                ind = self.indicators[first_freq]
                if hasattr(ind, "get") and "1day" in self.indicators:
                    ind = self.indicators["1day"]
                if isinstance(ind, dict) and "turnover" in ind:
                    self._summary["turnover"] = float(ind["turnover"].mean())
                elif isinstance(ind, tuple) and len(ind) > 0:
                    first_ind = ind[0] if isinstance(ind, tuple) else ind
                    if isinstance(first_ind, dict) and "turnover" in first_ind:
                        self._summary["turnover"] = float(first_ind["turnover"].mean())
        except Exception:
            pass

        return self._summary

    def __repr__(self):
        if self.summary:
            lines = [f"BacktestResult ({self.summary.get('n_days', '?')} days)"]
            for k, v in self.summary.items():
                if isinstance(v, float):
                    lines.append(f"  {k}: {v:.4f}")
                else:
                    lines.append(f"  {k}: {v}")
            return "\n".join(lines)
        return "BacktestResult(empty)"


class VectorizedBacktester:
    """Production-quality Qlib-based backtester with configurable strategies.

    Reads ``config.yaml`` for Qlib data paths and risk parameters. Supports
    TopkDropout and WeightStrategy modes.

    Args:
        config_path: Path to config.yaml. Defaults to project root config.
        qlib_dir: Override Qlib data directory. If None, reads from config.
    """

    def __init__(self, config_path: str = None, qlib_dir: str = None):
        # Resolve config path
        if config_path is None:
            project_root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            )
            config_path = os.path.join(project_root, "config.yaml")

        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        # Resolve Qlib directory
        if qlib_dir is not None:
            self._qlib_dir = qlib_dir
        else:
            raw_path = self.config["storage"]["qlib_data_dir"]
            if not os.path.isabs(raw_path):
                project_root = os.path.dirname(config_path)
                raw_path = os.path.join(project_root, raw_path)
            self._qlib_dir = os.path.normpath(raw_path)

        self._qlib_initialized = False

    def _ensure_qlib_init(self):
        """Initialize Qlib lazily on first backtest run."""
        if self._qlib_initialized:
            return

        import qlib
        from qlib.config import REG_CN

        try:
            # Keep Qlib single-process by default on this Windows setup; larger
            # joblib-based query fan-out is currently blocked by pipe permissions.
            qlib.init(provider_uri=self._qlib_dir, region=REG_CN, kernels=1)
            logger.info("Qlib initialized with data dir: %s", self._qlib_dir)
        except Exception:
            # Already initialized (e.g., in notebook context)
            logger.debug("Qlib already initialized or reinit skipped")

        self._qlib_initialized = True

    def run(
        self,
        predictions: pd.DataFrame,
        start_time: str,
        end_time: str,
        benchmark: str = "000300_SH",
        account: float = 1_000_000_000.0,
        topk: int = 50,
        n_drop: int = 5,
        exchange_kwargs: dict = None,
        strategy_type: str = "topk_dropout",
        custom_weights: pd.DataFrame = None,
        hold_thresh: int = 1,
        only_tradable: bool = False,
        forbid_all_trade_at_limit: bool = False,
        time_split: dict | None = None,
        holdout_context: Any | None = None,
        execution_profile: str | None = None,
        calendar_policy_id: str | None = None,
    ) -> BacktestResult:
        """Run a backtest with full Qlib integration.

        Args:
            predictions: DataFrame or Series with MultiIndex(datetime, instrument)
                and prediction scores.
            start_time: Backtest start date (e.g., "2020-01-01").
            end_time: Backtest end date (e.g., "2023-12-31").
            benchmark: Benchmark index code in Qlib underscore format
                (e.g., "000300_SH" for CSI 300).  Defaults to CSI 300.
                NOTE: Qlib uses '{code}_{exchange}' format, NOT 'SH000300'.
            account: Initial capital in CNY (default 1 billion).
            topk: Number of top stocks to hold (TopkDropout strategy).
            n_drop: Number of stocks to rotate per rebalance.
            exchange_kwargs: Override exchange configuration. If None, uses
                A-share defaults (涨跌停 9.5%, commission 0.05%/0.15%).
            strategy_type: "topk_dropout" (default) or "weight_strategy".
            custom_weights: For weight_strategy: DataFrame with columns
                [datetime, instrument, weight]. Ignored for topk_dropout.
            hold_thresh: Minimum holding periods before allowing sell.
            only_tradable: If True, only trade tradable stocks.
            forbid_all_trade_at_limit: If True, cancel ALL trades when any
                target stock is at price limit. Default False = skip individual
                limit stocks and trade the rest (recommended for small-cap).

        Returns:
            BacktestResult with report, positions, indicators, and summary.

        Raises:
            ValueError: If predictions is empty or date range is invalid.
            RuntimeError: If Qlib backtest execution fails.
        """
        # PR 3 of 2026-05-26 freeze plan: profile resolution. Only screening
        # profiles (backend='vectorized', allowed_for_formal=False) may be
        # passed to the vectorized backtester. Formal event-driven profiles
        # are rejected loudly so callers cannot accidentally run a JoinQuant
        # parity profile on the vectorized stack.
        profile_obj = None
        if execution_profile is not None:
            from src.backtest_engine.execution_profiles import (
                ExecutionProfileError,
                get_profile,
            )
            profile_obj = get_profile(execution_profile)
            if profile_obj.backend != "vectorized":
                raise ExecutionProfileError(
                    f"execution_profile={execution_profile!r} has backend={profile_obj.backend!r} "
                    "but VectorizedBacktester only accepts vectorized profiles. "
                    "Formal profiles target the event-driven engine."
                )
            if profile_obj.allowed_for_formal:
                # Defensive: a vectorized profile flagged allowed_for_formal=True
                # would be a contract bug — formal == event_driven only.
                raise ExecutionProfileError(
                    f"execution_profile={execution_profile!r} declares "
                    "allowed_for_formal=True with backend=vectorized — formal "
                    "runs require the event-driven backend. Fix the profile "
                    "definition or pass it to EventDrivenBacktester instead."
                )

        self._ensure_qlib_init()
        from qlib.backtest import backtest

        # Validate inputs
        if predictions is None or (isinstance(predictions, pd.DataFrame) and predictions.empty):
            raise ValueError("predictions cannot be None or empty")
        if time_split:
            stage = str(time_split.get("stage", "") or "")
            allowed_start = str(time_split.get("oos_start" if stage == "oos_test" else "is_start", "") or "")
            allowed_end = str(time_split.get("oos_end" if stage == "oos_test" else "is_end", "") or "")
            if allowed_start and pd.Timestamp(start_time) < pd.Timestamp(allowed_start):
                raise ValueError(f"TimeSplit violation: start_time {start_time} is before allowed window {allowed_start}")
            if allowed_end and pd.Timestamp(end_time) > pd.Timestamp(allowed_end):
                raise ValueError(f"TimeSplit violation: end_time {end_time} is after allowed window {allowed_end}")
            if stage == "oos_test":
                if holdout_context is None:
                    raise ValueError(
                        "Engine backstop: time_split.stage='oos_test' requires a holdout_context. "
                        "Sandbox mode cannot touch the holdout window."
                    )
                from src.research_orchestrator.holdout_seal import HoldoutSealStore

                store = HoldoutSealStore(holdout_context.seal_store_dir)
                events = store.list_events(design_hash=holdout_context.design_hash)
                matching = events[
                    (events["run_dir"] == holdout_context.run_dir)
                    & (events["step_id"] == holdout_context.step_id)
                ]
                if matching.empty:
                    raise ValueError(
                        f"Engine backstop: OOS run on design_hash={holdout_context.design_hash} "
                        f"but no seal claim found for run_dir={holdout_context.run_dir}, "
                        f"step_id={holdout_context.step_id}. Did you call SealedBacktestRunner?"
                    )

        # Extract signal Series
        if isinstance(predictions, pd.DataFrame):
            pred_series = predictions.iloc[:, 0]
        else:
            pred_series = predictions

        # Merge exchange kwargs with defaults
        final_exchange = _DEFAULT_EXCHANGE_KWARGS.copy()
        if exchange_kwargs:
            final_exchange.update(exchange_kwargs)

        # Build strategy config
        if strategy_type == "topk_dropout":
            strategy_config = {
                "class": "TopkDropoutStrategy",
                "module_path": "qlib.contrib.strategy",
                "kwargs": {
                    "signal": pred_series,
                    "topk": topk,
                    "n_drop": n_drop,
                    "hold_thresh": hold_thresh,
                    "only_tradable": only_tradable,
                    "forbid_all_trade_at_limit": forbid_all_trade_at_limit,
                },
            }
        elif strategy_type == "weight_strategy":
            if custom_weights is None:
                raise ValueError("custom_weights required for weight_strategy")
            strategy_config = {
                "class": "WeightStrategyBase",
                "module_path": "qlib.contrib.strategy",
                "kwargs": {
                    "signal": pred_series,
                },
            }
        else:
            raise ValueError(f"Unknown strategy_type: {strategy_type}")

        executor_config = {
            "class": "SimulatorExecutor",
            "module_path": "qlib.backtest.executor",
            "kwargs": {
                "time_per_step": "day",
                "generate_portfolio_metrics": True,
            },
        }

        # Log configuration
        bt_config = {
            "start_time": start_time,
            "end_time": end_time,
            "benchmark": benchmark,
            "strategy_type": strategy_type,
            "topk": topk,
            "n_drop": n_drop,
            "account": account,
            "exchange": final_exchange,
        }
        logger.info("Starting backtest: %s to %s, benchmark=%s, topk=%d",
                     start_time, end_time, benchmark, topk)

        # Execute backtest
        # NOTE: Qlib benchmark must use underscore format: '000300_SH' not 'SH000300'.
        # The built-in CSI300_BENCH = 'SH000300' only works with Qlib's official
        # data downloads.  Custom databases use '{code}_{exchange}' format.
        try:
            portfolio_metric_dict, indicator_dict = backtest(
                start_time=start_time,
                end_time=end_time,
                strategy=strategy_config,
                executor=executor_config,
                benchmark=benchmark,
                account=account,
                exchange_kwargs=final_exchange,
            )
        except Exception as e:
            logger.error("Backtest execution failed: %s", e, exc_info=True)
            raise RuntimeError(f"Qlib backtest failed: {e}") from e

        # Unpack results correctly (Qlib returns dict keyed by freq)
        report = None
        positions = None

        if isinstance(portfolio_metric_dict, dict):
            # Qlib returns {freq_str: (report_df, positions_dict)}
            for freq_key, value in portfolio_metric_dict.items():
                if isinstance(value, (tuple, list)) and len(value) == 2:
                    report, positions = value
                    break
            if report is None:
                # Try first value directly
                first_val = list(portfolio_metric_dict.values())[0]
                if isinstance(first_val, (tuple, list)):
                    report = first_val[0]
                    positions = first_val[1] if len(first_val) > 1 else None
                else:
                    report = first_val
        elif isinstance(portfolio_metric_dict, (tuple, list)):
            report = portfolio_metric_dict[0]
            positions = portfolio_metric_dict[1] if len(portfolio_metric_dict) > 1 else None

        logger.info("Backtest completed: %d trading days", len(report) if report is not None else 0)

        # PR 1 + PR 3: stamp provenance onto bt_config so vectorized results
        # carry the same artifact_provenance shape as event-driven results.
        # Vectorized profiles are screening-only by contract — the artifact
        # is legacy-eligible-for-formal-gate=False on purpose.
        from src.research_orchestrator.artifact_provenance import (
            ArtifactProvenance,
            attach_provenance,
        )
        from src.data_infra.provider_manifest import (
            ProviderManifestError,
            load_provider_manifest,
        )

        provider_build_id: str | None = None
        try:
            qlib_dir = self._qlib_dir
            manifest = load_provider_manifest(qlib_dir)
            provider_build_id = manifest.provider_build_id
        except ProviderManifestError as exc:
            logger.warning(
                "Vectorized provider manifest unavailable (%s). Result marked legacy_artifact.",
                exc,
            )

        provenance_kwargs: dict[str, Any] = {
            "provider_build_id": provider_build_id,
            "calendar_policy_id": calendar_policy_id,
        }
        if profile_obj is not None:
            provenance_kwargs.update(profile_obj.to_provenance_dict())
        provenance = ArtifactProvenance(**provenance_kwargs)
        provenance = ArtifactProvenance.from_dict(provenance.to_dict())
        attach_provenance(bt_config, provenance)

        return BacktestResult(
            report=report,
            positions=positions,
            indicators=indicator_dict,
            config=bt_config,
        )

    def compare(
        self,
        signals: dict,
        start_time: str,
        end_time: str,
        **kwargs,
    ) -> pd.DataFrame:
        """Run multiple backtests and compare results side-by-side.

        Args:
            signals: Dict of {signal_name: predictions_df}.
            start_time: Backtest start date.
            end_time: Backtest end date.
            **kwargs: Additional arguments passed to run().

        Returns:
            DataFrame comparing summary statistics across signals.
        """
        results = {}
        for name, preds in signals.items():
            logger.info("Running backtest for signal: %s", name)
            try:
                result = self.run(preds, start_time, end_time, **kwargs)
                results[name] = result.summary
            except Exception as e:
                logger.error("Backtest failed for %s: %s", name, e)
                results[name] = {"error": str(e)}

        return pd.DataFrame(results).T
