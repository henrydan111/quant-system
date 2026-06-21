"""factor_eval_skill — the thin orchestration/contracts layer for the factor-evaluation
methodology (v1.3).

This package builds ONLY the contracts + identity spine + provenance sidecars; it reuses
the existing engines verbatim (catalog / PIT linters / unified-eval matrix / lifecycle IS
gate / FrozenSelectionSet / HoldoutSealStore / reproduce_sealed_oos / event-driven
backtester). See ``workspace/research/factor_eval_methodology/FACTOR_EVAL_PARTG_BUILD_DESIGN.md``
(v2) for the build design and ``FACTOR_EVAL_METHODOLOGY_v1.3.md`` for the methodology.

Step 1 (this module set): D1 storage + D2 identity spine.
"""
from __future__ import annotations

from src.alpha_research.factor_eval_skill._hashing import (
    canonical_json,
    normalize_enum,
    normalize_mapping,
    payload_hash,
)
from src.alpha_research.factor_eval_skill.identity import (
    DeploymentFrozenPlan,
    FrozenSelectionEnvelope,
    IdentityChainError,
    SelectedRepresentative,
    SelectedSet,
    TargetUniverseDeclaration,
    assert_identity_chain,
)
from src.alpha_research.factor_eval_skill.stage3_reader import (
    ALL_UNIVERSES,
    CORE_UNIVERSES,
    LIQUID_UNIVERSE,
    MICROCAP_UNIVERSE,
    MatrixResults,
    Stage3QualityRecord,
    stage3_caps,
)
from src.alpha_research.factor_eval_skill.stores import (
    EVIDENCE_TIERS,
    ROLES,
    FactorProvenanceStore,
    FilterCharacterizationStore,
    FilterDeploymentGateStore,
    FrozenSelectionEnvelopeStore,
    RoleDeclarationStore,
    Stage3QualityRecordStore,
)

__all__ = [
    # hashing
    "canonical_json",
    "normalize_enum",
    "normalize_mapping",
    "payload_hash",
    # D2 identity spine
    "TargetUniverseDeclaration",
    "SelectedRepresentative",
    "SelectedSet",
    "FrozenSelectionEnvelope",
    "DeploymentFrozenPlan",
    "assert_identity_chain",
    "IdentityChainError",
    # D1 stores
    "FactorProvenanceStore",
    "RoleDeclarationStore",
    "Stage3QualityRecordStore",
    "FilterCharacterizationStore",
    "FilterDeploymentGateStore",
    "FrozenSelectionEnvelopeStore",
    "EVIDENCE_TIERS",
    "ROLES",
    # D5 Stage-3 reader
    "MatrixResults",
    "Stage3QualityRecord",
    "stage3_caps",
    "CORE_UNIVERSES",
    "LIQUID_UNIVERSE",
    "MICROCAP_UNIVERSE",
    "ALL_UNIVERSES",
]
