from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.backtest_engine.event_driven import EventDrivenBacktester
from src.backtest_engine.vectorized import VectorizedBacktester
from src.research_orchestrator.holdout_seal import HoldoutSealStore
from src.research_orchestrator.research_access_context import (
    ResearchAccessContext,
    research_access_context,
)


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
        time_split: dict,
        pipeline_args: Any,
        provider_build_id: str = "",
        calendar_policy_id: str = "",
        allowed_fields: Any = None,
    ) -> Any:
        """Run a workspace pipeline under a sealed access context.

        PR 6 of the 2026-05-26 freeze plan tightened this signature:
        ``time_split`` is no longer optional, and the pipeline is wrapped in
        a :class:`ResearchAccessContext` so any ``qlib_windowed_features``
        call inside the pipeline inherits the window / seal / field
        constraints. Pipelines that try to read outside the allowed window,
        or trigger OOS without a seal claim, raise the appropriate
        ``HoldoutWindowViolation`` / ``HoldoutSealViolation`` at the
        data-access layer rather than silently leaking holdout data.

        ``pipeline_fn`` is called as ``pipeline_fn(time_split=time_split,
        holdout_context=self._ctx, **pipeline_args)`` when
        ``pipeline_args`` is a dict, or
        ``pipeline_fn(time_split, self._ctx, pipeline_args)`` otherwise.
        """
        self._claim_if_oos(time_split)

        if self._ctx is None:
            # Sandbox / non-OOS pipeline — no context to install.
            if isinstance(pipeline_args, dict):
                return pipeline_fn(time_split=time_split, **pipeline_args)
            return pipeline_fn(time_split, pipeline_args)

        research_ctx = ResearchAccessContext.from_split(
            run_id=self._ctx.run_dir,
            step_id=self._ctx.step_id,
            stage=self._ctx.stage,
            design_hash=self._ctx.design_hash,
            time_split=time_split,
            provider_build_id=provider_build_id,
            calendar_policy_id=calendar_policy_id,
            holdout_context_id=self._ctx.run_dir,
            holdout_seal_claimed=True,  # _claim_if_oos already enforced it
            allowed_fields=allowed_fields,
        )
        with research_access_context(research_ctx):
            if isinstance(pipeline_args, dict):
                return pipeline_fn(
                    time_split=time_split,
                    holdout_context=self._ctx,
                    **pipeline_args,
                )
            return pipeline_fn(time_split, self._ctx, pipeline_args)
