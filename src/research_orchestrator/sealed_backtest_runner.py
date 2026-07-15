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
    # PR3 R6 Blocker 1: there is NO seal_store_dir field — the seal store is ALWAYS
    # HoldoutSealStore(resolve_configured_global_holdout_root()); a per-context dir let
    # two runs claim the same seal_key in two caller-chosen "worlds" and pass both
    # engine backstops.
    design_hash: str
    hypothesis_id: str
    structural_family: str
    run_dir: str
    step_id: str
    stage: str
    allow_same_run: bool
    # PR P1.4: the OOS holdout budget is keyed by seal_key; empty falls back to
    # design_hash (existing behavior). A FrozenSelectionSet-driven run sets
    # frozen_set_hash here so the seal is spent per frozen selection set.
    seal_key: str = ""

    @property
    def effective_seal_key(self) -> str:
        return self.seal_key or self.design_hash


class SealedBacktestRunner:
    def __init__(self, holdout_context: HoldoutContext | None) -> None:
        self._ctx = holdout_context

    def _claim_if_oos(self, time_split: dict | None) -> None:
        # v1.4 A8 round-3 Blocker 1 (2026-07-03): the claim decision must NOT be
        # payload-controlled. Deciding from time_split["stage"] alone let an OOS
        # HoldoutContext skip BOTH the claim and the virgin-window guard by passing a
        # payload that omits/mislabels "stage" — after which run_workspace_pipeline would
        # install a ResearchAccessContext asserting holdout_seal_claimed=True that the
        # data layer trusts. Source of truth = HoldoutContext.stage; a contradictory
        # payload stage fails closed.
        payload_stage = str((time_split or {}).get("stage", "") or "").strip()
        ctx_stage = str(getattr(self._ctx, "stage", "") or "").strip()
        if ctx_stage and payload_stage and ctx_stage != payload_stage:
            raise ValueError(
                "SealedBacktestRunner._claim_if_oos stage mismatch: "
                f"HoldoutContext.stage={ctx_stage!r} but time_split['stage']={payload_stage!r}. "
                "Refusing because an OOS payload must not be able to downgrade or bypass "
                "the legacy seal claim."
            )
        stage = ctx_stage or payload_stage
        if stage != "oos_test":
            return
        if self._ctx is None:
            raise ValueError(
                "OOS backtest requires a HoldoutContext; "
                "SealedBacktestRunner was constructed with holdout_context=None"
            )
        # v1.4 A8 (implementation-review round-2 Blocker 1): this runner claims the seal
        # DIRECTLY and its effective_seal_key falls back to design_hash — a second legacy
        # claim path beside the orchestrator chokepoint. Guard it with the SAME shared
        # helper BEFORE the store is constructed, so a virgin-window refusal writes no
        # seal row. Burned windows pass (the PR3 dry-run pilot path).
        from src.research_orchestrator.window_enforcement import (
            assert_v14_a8_no_legacy_virgin_oos_claim,
        )

        assert_v14_a8_no_legacy_virgin_oos_claim(
            stage=stage,
            time_split=time_split,
            caller=(
                "SealedBacktestRunner._claim_if_oos "
                f"(seal_key={self._ctx.effective_seal_key[:12]}…)"
            ),
        )
        from src.research_orchestrator.holdout_seal import (
            OosExecutionGuardStore,
            resolve_configured_global_holdout_root,
        )

        root = resolve_configured_global_holdout_root()
        store = HoldoutSealStore(root)
        store.claim_holdout_access(
            design_hash=self._ctx.design_hash,
            hypothesis_id=self._ctx.hypothesis_id,
            structural_family=self._ctx.structural_family,
            profile_id="sealed_backtest_runner",
            run_dir=self._ctx.run_dir,
            step_id=self._ctx.step_id,
            stage=self._ctx.stage,
            allow_same_run=self._ctx.allow_same_run,
            seal_key=self._ctx.effective_seal_key,
        )
        # R7 Blocker 1: this runner has NO result store — mark execution_started after
        # the claim and BEFORE the backtest, so a crashed run cannot be silently
        # re-executed via allow_same_run resume (there is nothing persisted to reload;
        # the holdout may already have been observed). Quarantine, never re-run.
        OosExecutionGuardStore(root).assert_and_mark_execution(
            seal_key=self._ctx.effective_seal_key,
            run_dir=self._ctx.run_dir,
            step_id=self._ctx.step_id,
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
        # R2-m1 (M4 self-heal review): a formal context without provider
        # provenance would only fail at the FIRST read (B1 pin) with a
        # confusing "generation changed" message — fail at construction
        # instead, and BEFORE _claim_if_oos so a malformed call cannot burn
        # a spend-on-attempt seal slot.
        if self._ctx is not None and (
            not str(provider_build_id).strip() or not str(calendar_policy_id).strip()
        ):
            raise ValueError(
                "run_workspace_pipeline formal context requires non-blank "
                "provider_build_id and calendar_policy_id."
            )
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
            seal_key=self._ctx.effective_seal_key,
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
