from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.backtest_engine.event_driven import EventDrivenBacktester
from src.backtest_engine.vectorized import VectorizedBacktester
from src.research_orchestrator.holdout_seal import HoldoutSealStore


@dataclass(frozen=True)
class HoldoutContext:
    design_hash: str
    hypothesis_id: str
    structural_family: str
    run_dir: str
    step_id: str
    stage: str
    allow_same_run: bool
    seal_store_dir: str


class SealedBacktestRunner:
    def __init__(self, holdout_context: HoldoutContext | None) -> None:
        self._ctx = holdout_context

    def _claim_if_oos(self, time_split: dict | None) -> None:
        stage = str((time_split or {}).get("stage", "") or "")
        if stage != "oos_test":
            return
        if self._ctx is None:
            raise ValueError(
                "OOS backtest requires a HoldoutContext; "
                "SealedBacktestRunner was constructed with holdout_context=None"
            )
        store = HoldoutSealStore(self._ctx.seal_store_dir)
        store.claim_holdout_access(
            design_hash=self._ctx.design_hash,
            hypothesis_id=self._ctx.hypothesis_id,
            structural_family=self._ctx.structural_family,
            profile_id="sealed_backtest_runner",
            run_dir=self._ctx.run_dir,
            step_id=self._ctx.step_id,
            stage=self._ctx.stage,
            allow_same_run=self._ctx.allow_same_run,
        )

    def run_vectorized(self, *, time_split: dict | None = None, **kwargs: Any) -> Any:
        self._claim_if_oos(time_split)
        backtester = kwargs.pop("backtester", None) or VectorizedBacktester()
        return backtester.run(time_split=time_split, holdout_context=self._ctx, **kwargs)

    def run_event_driven(self, *, time_split: dict | None = None, **kwargs: Any) -> Any:
        self._claim_if_oos(time_split)
        backtester = kwargs.pop("backtester", None) or EventDrivenBacktester()
        return backtester.run(time_split=time_split, holdout_context=self._ctx, **kwargs)

    def run_workspace_pipeline(
        self,
        *,
        pipeline_fn: Callable[..., Any],
        time_split: dict | None = None,
        pipeline_args: Any,
    ) -> Any:
        self._claim_if_oos(time_split)
        if isinstance(pipeline_args, dict):
            return pipeline_fn(**pipeline_args)
        return pipeline_fn(pipeline_args)
