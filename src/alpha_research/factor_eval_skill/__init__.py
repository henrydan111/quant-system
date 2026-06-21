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
from src.alpha_research.factor_eval_skill.deployment import (
    DeploymentMetrics,
    build_ranked_schedule,
    direction_aligned_composite,
    run_deployment,
)
from src.alpha_research.factor_eval_skill.marginal import (
    MarginalSelection,
    select_marginal,
)
from src.alpha_research.factor_eval_skill.sealed_oos import (
    DEFAULT_LS_SHARPE_FLOOR,
    DEFAULT_N_QUANTILES,
    DIR_MAP,
    SealedOosVerdict,
    direction_aligned_pass,
    evaluate_sealed_oos_bar,
    run_sealed_oos,
    sides_from_frozen_set,
)
from src.alpha_research.factor_eval_skill.stage3_reader import (
    ALL_UNIVERSES,
    CORE_UNIVERSES,
    LIQUID_UNIVERSE,
    MICROCAP_UNIVERSE,
    MatrixResults,
    Stage3GovernanceInputs,
    Stage3QualityRecord,
    stage3_caps,
)
from src.alpha_research.factor_eval_skill.multiplicity import (
    ACTION_ACKNOWLEDGE,
    ACTION_DISCLOSE,
    ACTION_REQUIRE,
    MultiplicityReport,
    oos_window_multiplicity,
)
from src.alpha_research.factor_eval_skill.stores import (
    EVIDENCE_TIERS,
    ROLES,
    FactorProvenanceStore,
    FilterCharacterizationStore,
    FilterDeploymentGateStore,
    FrozenSelectionEnvelopeStore,
    OosWindowLedgerStore,
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
    "OosWindowLedgerStore",
    "EVIDENCE_TIERS",
    "ROLES",
    # D6 OOS-window multiplicity
    "oos_window_multiplicity",
    "MultiplicityReport",
    "ACTION_DISCLOSE",
    "ACTION_ACKNOWLEDGE",
    "ACTION_REQUIRE",
    # D5 Stage-3 reader
    "MatrixResults",
    "Stage3GovernanceInputs",
    "Stage3QualityRecord",
    "stage3_caps",
    "CORE_UNIVERSES",
    "LIQUID_UNIVERSE",
    "MICROCAP_UNIVERSE",
    "ALL_UNIVERSES",
    # D3 extracted library (marginal / sealed-OOS / deployment)
    "select_marginal",
    "MarginalSelection",
    "direction_aligned_pass",
    "evaluate_sealed_oos_bar",
    "run_sealed_oos",
    "sides_from_frozen_set",
    "SealedOosVerdict",
    "DIR_MAP",
    "DEFAULT_LS_SHARPE_FLOOR",
    "DEFAULT_N_QUANTILES",
    "direction_aligned_composite",
    "build_ranked_schedule",
    "run_deployment",
    "DeploymentMetrics",
]
