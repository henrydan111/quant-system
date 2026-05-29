from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.research_orchestrator.registries.typed_store import TypedRegistryStore
from src.research_orchestrator.release_gate import (
    PRIVILEGED_REGISTRY_STATUSES,
    PromotionGateError,
    assert_promotion_artifact_eligible,
)


class StrategyRegistryStore(TypedRegistryStore):
    def __init__(self, registry_dir: str | Path) -> None:
        super().__init__(
            registry_dir,
            registry_slug="strategy_registry",
            allowed_object_types=("strategy_candidate",),
            review_title="Strategy Registry Review",
        )

    def set_status(
        self,
        *,
        object_id: str,
        status: str,
        reason: str,
        version: int | None = None,
        source_run_id: str | None = None,
        promotion_evidence: Mapping[str, Any] | None = None,
        current_git_sha: str | None = None,
    ) -> dict[str, Any]:
        """Gate privileged promotions (PIT-prevention step 11).

        A transition to a PRIVILEGED registry status (e.g. ``"approved"``) is the
        decision-layer act that the val_heavy near-deployment slipped through. It
        is now refused unless ``promotion_evidence`` proves the strategy's signal
        panel was INDEPENDENTLY reconstructed through a PIT-correct data path
        (``qlib_windowed_features`` / JoinQuant-native / ``audited_pit_source``) —
        a sandbox/loader panel is insufficient — AND the evidence artifact passes
        the lint/parity/clean-tree checks (see
        :func:`src.research_orchestrator.release_gate.evaluate_promotion_artifact`).

        Non-privileged transitions (candidate / under_review / rejected / archived)
        are unchanged. Raises :class:`PromotionGateError` when the gate fails.
        """
        if str(status).strip().lower() in PRIVILEGED_REGISTRY_STATUSES:
            # current_git_sha is MANDATORY for a privileged transition — it binds
            # the approval to a committed HEAD (the artifact's git_sha must match),
            # so the gate cannot be satisfied from an uncommitted / unknown tree by
            # simply omitting the SHA. (GPT PR #22 round-3.)
            if not current_git_sha:
                raise PromotionGateError(
                    f"Promotion gate blocked strategy_candidate:{object_id}: "
                    f"current_git_sha is required for a privileged registry status "
                    f"transition (binds the approval to a committed HEAD)"
                )
            artifact = dict(promotion_evidence or {})
            artifact.setdefault("promotion_status", status)
            assert_promotion_artifact_eligible(
                artifact,
                current_git_sha=current_git_sha,
                artifact_label=f"strategy_candidate:{object_id}",
            )
        return super().set_status(
            object_id=object_id,
            status=status,
            reason=reason,
            version=version,
            source_run_id=source_run_id,
        )
