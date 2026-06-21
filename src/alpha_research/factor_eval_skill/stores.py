"""D1 — the three scope-split provenance sidecars + the two filter sidecars + the D2
envelope store, for the factor-eval skill.

Design: ``workspace/research/factor_eval_methodology/FACTOR_EVAL_PARTG_BUILD_DESIGN.md``
(v2, D1 + D2). GPT review R1 split v1's single ``factor_provenance.parquet`` into stores
by LIFETIME/SCOPE, because ``quality_flags`` / ``universe_profile`` /
``target_universe_declaration_hash`` are per factor × target-universe × Layer-1
methodology — NOT stable per-factor attributes. One ``factor_id``+version row cannot
represent (research-valid on ``univ_all``, target-failing on ``liquid_top300``) without
overwriting scope.

    FactorProvenanceStore        key: factor_id + definition_hash               (per factor identity)
    RoleDeclarationStore         key: + role_context_hash                       (per role context)
    Stage3QualityRecordStore     key: + layer1_methodology_hash + tud_hash      (per factor×target×methodology)
    FilterCharacterizationStore  factor-eval output (Stage 2-5)
    FilterDeploymentGateStore    strategy-build output (Stage 8)
    FrozenSelectionEnvelopeStore D2 immutable envelope persistence (key: frozen_set_hash)

Seam traps folded: evidence_tier is NOT a replication-governance field; RoleDeclaration's
``direction`` REFERENCES ``expected_direction`` (no 4th direction system); Stage-0
provenance is its own store (NOT a fake ``Hypothesis``); the envelope is append-only
(``tud_hash`` is never a mutable property on a FrozenSelectionSet object).
"""
from __future__ import annotations

from typing import Any, Mapping

from src.alpha_research.factor_eval_skill._hashing import (
    canonical_json,
    normalize_enum,
    normalize_mapping,
    payload_hash,
)
from src.alpha_research.factor_eval_skill._store import AppendOnlyStore
from src.alpha_research.factor_eval_skill.identity import FrozenSelectionEnvelope

# evidence_tier is a provenance/multiplicity field — NOT replication_tier_planned /
# evidence_class / formal_evidence_eligible / cohort oos_eligibility (seam trap #1).
EVIDENCE_TIERS = ("theory_a_priori", "a_priori_is_informed", "oos_informed")
ROLES = ("ranking", "filter", "both")


def _b(value: Any) -> str:
    """Canonical boolean string."""
    return str(bool(value))


class FactorProvenanceStore(AppendOnlyStore):
    """Per-factor-identity provenance (Stage-0). Lives here, NOT in a fake ``Hypothesis``
    (which is strategy+OOS-bound). Enforces the IS-spent rule: an ``a_priori_is_informed``
    factor may NOT cite IS as confirmation."""

    FILENAME = "factor_provenance.parquet"
    COLUMNS = (
        "record_id",
        "recorded_at",
        "factor_id",
        "definition_hash",
        "evidence_tier",
        "direction_source",
        "may_cite_is_as_confirmation",
        "fresh_oos_eligible",
        "multiplicity_scope_id",
        "prior_contradicted_by_is",
        "rationale",
        "committed_by",
    )
    SCHEMA = {column: "string" for column in COLUMNS}
    KEY_FIELDS = ("factor_id", "definition_hash")

    def record_provenance(
        self,
        *,
        factor_id: str,
        definition_hash: str,
        evidence_tier: str,
        direction_source: str,
        multiplicity_scope_id: str,
        may_cite_is_as_confirmation: bool | None = None,
        fresh_oos_eligible: bool = False,
        prior_contradicted_by_is: bool = False,
        rationale: str = "",
        committed_by: str = "factor-eval",
    ) -> dict[str, Any]:
        tier = normalize_enum(evidence_tier)
        if tier not in EVIDENCE_TIERS:
            raise ValueError(f"evidence_tier must be one of {EVIDENCE_TIERS}, got {evidence_tier!r}")
        # IS-spent rule (the core evidence-tier wiring point): a_priori_is_informed lets
        # IS GENERATE the hypothesis but never CONFIRM it. Default flows from the tier;
        # an explicit True for that tier is a contradiction.
        if may_cite_is_as_confirmation is None:
            may_cite_is_as_confirmation = tier != "a_priori_is_informed"
        if tier == "a_priori_is_informed" and may_cite_is_as_confirmation:
            raise ValueError(
                "a_priori_is_informed cannot set may_cite_is_as_confirmation=True (IS-spent rule)"
            )
        return self.record(
            factor_id=str(factor_id),
            definition_hash=str(definition_hash),
            evidence_tier=tier,
            direction_source=normalize_enum(direction_source),
            may_cite_is_as_confirmation=_b(may_cite_is_as_confirmation),
            fresh_oos_eligible=_b(fresh_oos_eligible),
            multiplicity_scope_id=str(multiplicity_scope_id),
            prior_contradicted_by_is=_b(prior_contradicted_by_is),
            rationale=str(rationale),
            committed_by=str(committed_by),
        )


class RoleDeclarationStore(AppendOnlyStore):
    """Per (factor, role-context) declaration. ``role_context_hash`` is computed from the
    declared context mapping (the StrategyContext / target the role is declared against),
    so the same factor can be ``ranking`` in one context and ``filter`` in another without
    collision. ``direction`` references the factor's ``expected_direction`` — not a new
    direction field."""

    FILENAME = "role_declaration.parquet"
    COLUMNS = (
        "record_id",
        "recorded_at",
        "factor_id",
        "definition_hash",
        "role_context_hash",
        "role",
        "filter_role_subtype",
        "threshold",
        "direction",
        "declared_before_stage",
        "role_context_json",
    )
    SCHEMA = {column: "string" for column in COLUMNS}
    KEY_FIELDS = ("factor_id", "definition_hash", "role_context_hash")

    def record_role(
        self,
        *,
        factor_id: str,
        definition_hash: str,
        role: str,
        role_context: Mapping[str, Any],
        direction: str,
        filter_role_subtype: str = "",
        threshold: str = "",
        declared_before_stage: str = "stage_2",
    ) -> dict[str, Any]:
        role_norm = normalize_enum(role)
        if role_norm not in ROLES:
            raise ValueError(f"role must be one of {ROLES}, got {role!r}")
        context = normalize_mapping(role_context)
        role_context_hash = payload_hash(context)
        return self.record(
            factor_id=str(factor_id),
            definition_hash=str(definition_hash),
            role_context_hash=role_context_hash,
            role=role_norm,
            filter_role_subtype=(normalize_enum(filter_role_subtype) if filter_role_subtype else ""),
            threshold=str(threshold),
            direction=normalize_enum(direction),
            declared_before_stage=normalize_enum(declared_before_stage),
            role_context_json=canonical_json(context),
        )


class Stage3QualityRecordStore(AppendOnlyStore):
    """Per (factor × target-universe × Layer-1 methodology) machine-binding caps. The key
    encodes the SCOPE — the same factor can pass on one target and fail on another, and
    both rows coexist. ``status_effect`` maps onto the existing ``STATUS_CEILINGS`` (no
    parallel status universe)."""

    FILENAME = "stage3_quality_record.parquet"
    COLUMNS = (
        "record_id",
        "recorded_at",
        "factor_id",
        "definition_hash",
        "layer1_methodology_hash",
        "target_universe_declaration_hash",
        "role",
        "quality_flags_json",
        "universe_profile_json",
        "target_universe_pass",
        "cross_universe_sign_divergence",
        "status_effect",
    )
    SCHEMA = {column: "string" for column in COLUMNS}
    KEY_FIELDS = (
        "factor_id",
        "definition_hash",
        "layer1_methodology_hash",
        "target_universe_declaration_hash",
    )

    def record_quality(
        self,
        *,
        factor_id: str,
        definition_hash: str,
        layer1_methodology_hash: str,
        target_universe_declaration_hash: str,
        role: str,
        quality_flags: Mapping[str, Any],
        universe_profile: Mapping[str, Any],
        target_universe_pass: bool | None,
        cross_universe_sign_divergence: bool,
        status_effect: str,
    ) -> dict[str, Any]:
        role_norm = normalize_enum(role)
        if role_norm not in ROLES:
            raise ValueError(f"role must be one of {ROLES}, got {role!r}")
        # A filter role has no IC pass/fail — persist None as "na", not "False".
        pass_str = "na" if target_universe_pass is None else _b(target_universe_pass)
        return self.record(
            factor_id=str(factor_id),
            definition_hash=str(definition_hash),
            layer1_methodology_hash=str(layer1_methodology_hash),
            target_universe_declaration_hash=str(target_universe_declaration_hash),
            role=role_norm,
            quality_flags_json=canonical_json(normalize_mapping(quality_flags)),
            universe_profile_json=canonical_json(normalize_mapping(universe_profile)),
            target_universe_pass=pass_str,
            cross_universe_sign_divergence=_b(cross_universe_sign_divergence),
            status_effect=normalize_enum(status_effect),
        )


class FilterCharacterizationStore(AppendOnlyStore):
    """factor-eval output (Stage 2-5): a filter is CHARACTERIZED (excluded-tail return,
    threshold stability, breadth) — NOT given an IC-based pass/fail. A filter cannot
    "pass" outside a StrategyContext (that is :class:`FilterDeploymentGateStore`)."""

    FILENAME = "filter_characterization.parquet"
    COLUMNS = (
        "record_id",
        "recorded_at",
        "factor_id",
        "definition_hash",
        "role",
        "target_universe_declaration_hash",
        "threshold",
        "excluded_tail_return",
        "threshold_stability",
        "breadth",
        "verdict",
    )
    SCHEMA = {column: "string" for column in COLUMNS}
    KEY_FIELDS = ("factor_id", "definition_hash", "role", "target_universe_declaration_hash", "threshold")

    def record_characterization(
        self,
        *,
        factor_id: str,
        definition_hash: str,
        target_universe_declaration_hash: str,
        threshold: str,
        excluded_tail_return: float | str,
        threshold_stability: float | str,
        breadth: float | str,
        verdict: str,
        role: str = "filter",
    ) -> dict[str, Any]:
        return self.record(
            factor_id=str(factor_id),
            definition_hash=str(definition_hash),
            role=normalize_enum(role),
            target_universe_declaration_hash=str(target_universe_declaration_hash),
            threshold=str(threshold),
            excluded_tail_return=str(excluded_tail_return),
            threshold_stability=str(threshold_stability),
            breadth=str(breadth),
            verdict=normalize_enum(verdict),
        )


class FilterDeploymentGateStore(AppendOnlyStore):
    """strategy-build output (Stage 8): the A/B pass/fail of a filter INSIDE a
    ``DeploymentFrozenPlan`` (keyed by ``plan_hash``). Marginal Sharpe/MDD deltas, not IC."""

    FILENAME = "filter_deployment_gate.parquet"
    COLUMNS = (
        "record_id",
        "recorded_at",
        "plan_hash",
        "filter_id",
        "threshold",
        "marginal_sharpe_delta",
        "marginal_mdd_delta",
        "verdict",
    )
    SCHEMA = {column: "string" for column in COLUMNS}
    KEY_FIELDS = ("plan_hash", "filter_id", "threshold")

    def record_gate(
        self,
        *,
        plan_hash: str,
        filter_id: str,
        threshold: str,
        marginal_sharpe_delta: float | str,
        marginal_mdd_delta: float | str,
        verdict: str,
    ) -> dict[str, Any]:
        return self.record(
            plan_hash=str(plan_hash),
            filter_id=str(filter_id),
            threshold=str(threshold),
            marginal_sharpe_delta=str(marginal_sharpe_delta),
            marginal_mdd_delta=str(marginal_mdd_delta),
            verdict=normalize_enum(verdict),
        )


class FrozenSelectionEnvelopeStore(AppendOnlyStore):
    """D2 immutable envelope persistence (key: ``frozen_set_hash``). Records the binding
    ``frozen_set_hash`` ↔ ``tud_hash`` ↔ ``selected_set_hash`` WITHOUT touching the seal
    key. ``legacy_mode`` rows (pre-v1.3 seals) stay auditable but are not chain-clean."""

    FILENAME = "frozen_selection_envelope.parquet"
    COLUMNS = (
        "record_id",
        "recorded_at",
        "frozen_set_hash",
        "envelope_hash",
        "target_universe_declaration_hash",
        "selected_set_hash",
        "frozen_selection_set_schema_version",
        "legacy_mode",
        "legacy_reason",
        "created_at",
        "created_by",
        "envelope_json",
    )
    SCHEMA = {column: "string" for column in COLUMNS}
    KEY_FIELDS = ("frozen_set_hash",)

    def record_envelope(self, envelope: FrozenSelectionEnvelope) -> dict[str, Any]:
        return self.record(
            frozen_set_hash=str(envelope.frozen_set_hash),
            envelope_hash=envelope.envelope_hash,
            target_universe_declaration_hash=(envelope.target_universe_declaration_hash or ""),
            selected_set_hash=(envelope.selected_set_hash or ""),
            frozen_selection_set_schema_version=str(envelope.frozen_selection_set_schema_version),
            legacy_mode=_b(envelope.legacy_mode),
            legacy_reason=(envelope.legacy_reason or ""),
            created_at=str(envelope.created_at),
            created_by=str(envelope.created_by),
            envelope_json=canonical_json(envelope._payload()),
        )

    def get_envelope(self, frozen_set_hash: str) -> dict[str, Any] | None:
        return self.latest(frozen_set_hash=str(frozen_set_hash))
