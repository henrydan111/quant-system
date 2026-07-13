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

import json
from typing import Any, Mapping, Sequence

import pandas as pd

from src.alpha_research.factor_eval_skill._hashing import (
    canonical_json,
    normalize_enum,
    normalize_mapping,
    payload_hash,
)
from src.alpha_research.factor_eval_skill._store import (
    AppendOnlyStore,
    _atomic_write_dataframe as _store_atomic_write,
    _now_str as _store_now,
)
from src.alpha_research.factor_eval_skill.identity import FrozenSelectionEnvelope
from src.research_orchestrator.file_lock import file_lock

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
        fresh_oos_eligible: bool | None = None,
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
        # fresh-OOS eligibility derives from tier: only oos_informed has SPENT its OOS window
        # (GPT cross-review 2026-06-21 — was hardcoded False for every tier).
        if fresh_oos_eligible is None:
            fresh_oos_eligible = tier != "oos_informed"
        if tier == "oos_informed" and fresh_oos_eligible:
            raise ValueError("oos_informed cannot set fresh_oos_eligible=True (OOS already spent)")
        # the IS-informed / OOS-informed tiers MUST carry the multiplicity scope they are meant
        # to link into — a blank scope would let the tier bypass the multiplicity denominator.
        if tier in ("a_priori_is_informed", "oos_informed") and not str(multiplicity_scope_id).strip():
            raise ValueError(f"{tier} requires a non-blank multiplicity_scope_id")
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
    # role is part of the key: a factor can be ranking in one context and filter in another,
    # so a filter record must not shadow a ranking record on latest() (GPT cross-review).
    KEY_FIELDS = (
        "factor_id",
        "definition_hash",
        "layer1_methodology_hash",
        "target_universe_declaration_hash",
        "role",
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
        # Enforce immutability at the persistence boundary: a frozen_set_hash binds to exactly
        # one envelope. Re-recording the SAME binding is idempotent; a DIFFERENT binding for the
        # same frozen_set_hash is fail-closed (else "latest wins" would make the binding mutable —
        # GPT cross-review 2026-06-21).
        existing = self.get_envelope(envelope.frozen_set_hash)
        if existing is not None:
            if str(existing["envelope_hash"]) == envelope.envelope_hash:
                return existing
            raise ValueError(
                f"conflicting FrozenSelectionEnvelope for frozen_set_hash={envelope.frozen_set_hash}: "
                f"existing envelope_hash={existing['envelope_hash']} != new {envelope.envelope_hash}"
            )
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


class FrozenSealAliasStore(AppendOnlyStore):
    """Maps a canonical ``frozen_set_hash`` to a legacy / other-tool ``frozen_set_hash`` for the SAME
    economic selection+protocol (GPT re-review 2026-06-21). A live-seal preflight checks the canonical
    hash AND its aliases against the spent seal_keys, so the SAME economic OOS test cannot be re-spent
    under a different hash just because a pre-v1.3 tool serialized the protocol differently. Empty by
    default; populated manually when a known equivalence is migrated."""

    FILENAME = "frozen_seal_alias.parquet"
    COLUMNS = ("record_id", "recorded_at", "canonical_frozen_set_hash", "legacy_frozen_set_hash", "reason")
    SCHEMA = {column: "string" for column in COLUMNS}
    KEY_FIELDS = ("canonical_frozen_set_hash", "legacy_frozen_set_hash")

    def record_alias(self, *, canonical: str, legacy: str, reason: str = "") -> dict[str, Any]:
        return self.record(canonical_frozen_set_hash=str(canonical),
                           legacy_frozen_set_hash=str(legacy), reason=str(reason))

    def aliases_for(self, canonical_frozen_set_hash: str) -> list[str]:
        frame = self._load()
        frame = frame[frame["canonical_frozen_set_hash"].astype("string") == str(canonical_frozen_set_hash)]
        return sorted(frame["legacy_frozen_set_hash"].astype("string").dropna().unique().tolist())


class OosWindowLedgerStore(AppendOnlyStore):
    """D6 seal-layer count: append-only record of which FROZEN SETS spent which OOS WINDOW
    (the `HoldoutSealStore` event log does NOT record the window). One row per
    (oos_window_id, frozen_set_hash) — idempotent (a frozen set spends a window once). The
    report/approval layer (:mod:`multiplicity`) reads this to compute the system-level
    cross-factor multiplicity; this store NEVER changes any OOS metric or per-set bar."""

    FILENAME = "oos_window_ledger.parquet"
    # v1.4 A6 (2026-07-03): three additive columns migrate the ledger from frozen-set-only
    # counting to the book_seal_key spend unit. ``spend_unit_type`` in
    # {frozen_set, book_seal, a5_signal_replication_study}; legacy rows (blank/NA) read as
    # frozen_set. ``AppendOnlyStore._load`` back-fills missing columns, so pre-v1.4 parquet
    # files load unchanged.
    COLUMNS = (
        "record_id",
        "recorded_at",
        "oos_window_id",
        "frozen_set_hash",
        "evidence_tier",
        "factor_ids",
        "seal_mode",
        "spend_unit_type",
        "book_seal_key",
        "override_id",
        # PR3 REWORK (R1 Major 3): A6 disclosure fields — additive, back-filled blank on
        # legacy rows by AppendOnlyStore._load.
        "book_plan_hash",
        "structural_family",
        "request_hash",
    )
    SCHEMA = {column: "string" for column in COLUMNS}
    KEY_FIELDS = ("oos_window_id", "frozen_set_hash")

    def record_spend(
        self, *, oos_window_id: str, frozen_set_hash: str, evidence_tier: str = "",
        factor_ids: Sequence[str] = (), seal_mode: str = "live",
    ) -> dict[str, Any]:
        """Record one window-tagged spend. Idempotent on (oos_window_id, frozen_set_hash) —
        a frozen set spending the same window again returns the existing row."""
        existing = self._latest_window_frozen_unit(
            oos_window_id=str(oos_window_id),
            frozen_set_hash=str(frozen_set_hash),
            spend_unit_types={"", "frozen_set"},
        )
        if existing is not None:
            return existing
        return self.record(
            oos_window_id=str(oos_window_id),
            frozen_set_hash=str(frozen_set_hash),
            evidence_tier=normalize_enum(evidence_tier) if evidence_tier else "",
            factor_ids=canonical_json(sorted(str(f) for f in factor_ids)),
            seal_mode=normalize_enum(seal_mode),
            spend_unit_type="frozen_set",
        )

    def _latest_window_frozen_unit(
        self, *, oos_window_id: str, frozen_set_hash: str, spend_unit_types: set[str],
    ) -> dict[str, Any] | None:
        """Idempotency lookup SCOPED BY SPEND-UNIT TYPE (implementation-review Blocker 2):
        a book row on the same (window, frozen_set) must never mask a legacy/A5 row's
        idempotency check — the row types are distinct spends."""
        frame = self._load()
        if frame.empty:
            return None
        spend_type = frame["spend_unit_type"].astype("string").fillna("")
        mask = (
            (frame["oos_window_id"].astype("string") == str(oos_window_id))
            & (frame["frozen_set_hash"].astype("string") == str(frozen_set_hash))
            & (spend_type.isin(spend_unit_types))
        )
        sub = frame[mask]
        if sub.empty:
            return None
        return sub.iloc[-1].to_dict()

    def record_book_spend(
        self, *, oos_window_id: str, book_seal_key: str, frozen_set_hash: str,
        evidence_tier: str = "", factor_ids: Sequence[str] = (), seal_mode: str = "live",
    ) -> dict[str, Any]:
        """v1.4 A2/A6: record one BOOK spend, idempotent on (oos_window_id, book_seal_key)
        — NOT on frozen_set_hash, because two plans sharing a frozen set but differing in
        construction / execution envelope / eval protocol / bar are DISTINCT spends
        (round-2 N2). ``frozen_set_hash`` is carried for disclosure/overlap accounting."""
        if not str(book_seal_key).strip():
            raise ValueError("record_book_spend requires a non-empty book_seal_key")
        existing = self.latest(oos_window_id=str(oos_window_id), book_seal_key=str(book_seal_key))
        if existing is not None:
            return existing
        return self.record(
            oos_window_id=str(oos_window_id),
            frozen_set_hash=str(frozen_set_hash),
            evidence_tier=normalize_enum(evidence_tier) if evidence_tier else "",
            factor_ids=canonical_json(sorted(str(f) for f in factor_ids)),
            seal_mode=normalize_enum(seal_mode),
            spend_unit_type="book_seal",
            book_seal_key=str(book_seal_key),
        )

    def record_study_spend(
        self, *, oos_window_id: str, frozen_set_hash: str, override_id: str = "",
        evidence_tier: str = "", factor_ids: Sequence[str] = (), seal_mode: str = "live",
    ) -> dict[str, Any]:
        """v1.4 A5: record a statusless signal-replication-study spend. On a FRESH
        (virgin) window ``override_id`` (the pre-recorded
        fresh_window_signal_replication_override_id) is REQUIRED by the caller's policy
        gate; this store records, it does not decide. Counts against the A6 budget.
        Idempotency is scoped to A5 rows only (Blocker 2: a pre-existing BOOK row on the
        same frozen set must not swallow the study's spend record)."""
        existing = self._latest_window_frozen_unit(
            oos_window_id=str(oos_window_id),
            frozen_set_hash=str(frozen_set_hash),
            spend_unit_types={"a5_signal_replication_study"},
        )
        if existing is not None:
            return existing
        return self.record(
            oos_window_id=str(oos_window_id),
            frozen_set_hash=str(frozen_set_hash),
            evidence_tier=normalize_enum(evidence_tier) if evidence_tier else "",
            factor_ids=canonical_json(sorted(str(f) for f in factor_ids)),
            seal_mode=normalize_enum(seal_mode),
            spend_unit_type="a5_signal_replication_study",
            override_id=str(override_id),
        )

    def reserve_book_spend(
        self,
        *,
        oos_window_id: str,
        book_seal_key: str,
        frozen_set_hash: str,
        book_plan_hash: str,
        request_hash: str,
        structural_family: str = "",
        factor_ids: Sequence[str] = (),
        seal_mode: str = "live",
        virgin: bool = False,
        warn_threshold: int = 3,
        hard_threshold: int = 5,
        multiplicity_ack: bool = False,
        override_store=None,
        multiplicity_override_id: str = "",
    ) -> dict[str, Any]:
        """PR3 REWORK (R1 Blocker 5 + R2 Blocker 5/Major 2) — the ATOMIC spend
        reservation: under ONE lock this (1) recognizes an existing ``(window,
        book_seal_key)`` row with the IDENTICAL ``request_hash`` as a RESUME (returned
        with ``resumed=True``; a blank/legacy or different recorded hash REFUSES —
        strict equality, R2 M2), (2) counts distinct existing spend-unit keys,
        (3) enforces the virgin budget — the warn band needs ``multiplicity_ack``; at/
        over the hard threshold the authorization is RE-READ FROM the
        ``OverrideAuthorizationStore`` (``override_store`` + ``multiplicity_override_id``
        via :meth:`require_consumed`, request-bound) — a caller-shaped dict can never
        satisfy it (R2 B5), (4) appends the spend-on-attempt row. The reservation
        happens BEFORE the holdout claim, so a crash between the two leaves a recorded
        spend and an unclaimed seal — the budget over-counts (conservative), never
        under-counts."""
        if not str(book_seal_key).strip():
            raise ValueError("reserve_book_spend requires a non-empty book_seal_key")
        if not str(request_hash).strip():
            raise ValueError("reserve_book_spend requires a non-empty request_hash")
        with file_lock(self.lock_path):
            frame = self._load()
            window_mask = frame["oos_window_id"].astype("string") == str(oos_window_id)
            sub = frame[window_mask]
            keys = sub["book_seal_key"].astype("string").fillna("")
            fallback = sub["frozen_set_hash"].astype("string").fillna("")
            merged = keys.where(keys.str.len() > 0, fallback)
            existing_keys = {k for k in merged.dropna().unique().tolist() if k}
            mine = sub[sub["book_seal_key"].astype("string") == str(book_seal_key)]
            if not mine.empty:
                row = mine.iloc[-1].to_dict()
                # R2 Major 2: STRICT equality — a blank (legacy) recorded hash is
                # quarantined, never a wildcard that resumes any request.
                if str(row.get("request_hash") or "") != str(request_hash):
                    raise ValueError(
                        f"reserve_book_spend: book_seal_key {book_seal_key} was reserved under "
                        f"request_hash {row.get('request_hash')!r} — this call's "
                        f"{request_hash!r} cannot resume it (a blank legacy row is quarantined; "
                        "a changed request is a new spend attempt)"
                    )
                row["resumed"] = True
                return row
            if virgin:
                # R3 Blocker 1: INCLUSIVE boundaries, matching virgin_window_multiplicity
                # exactly — the 3rd spend (n>=warn) requires acknowledgement, the 5th
                # spend (n>=hard) requires the consumed a6 authorization. `>` was an
                # off-by-one that let the 5th spend through un-authorized.
                n_would_be = len(existing_keys) + 1
                if n_would_be >= hard_threshold:
                    # R2 B5: the authorization is verified FROM the store, in here —
                    # never trusted from a caller-supplied mapping.
                    if override_store is None or not str(multiplicity_override_id).strip():
                        raise ValueError(
                            f"virgin-window book budget HARD STOP (would be spend #{n_would_be} >= "
                            f"{hard_threshold}): requires a pre-recorded, CONSUMED a6_multiplicity "
                            "authorization verified from the OverrideAuthorizationStore "
                            "(override_store + multiplicity_override_id) — caller input is never "
                            "an authorization"
                        )
                    override_store.require_consumed(
                        kind="a6_multiplicity",
                        override_id=str(multiplicity_override_id),
                        oos_window_id=str(oos_window_id),
                        scope_key=str(book_seal_key),
                        consumed_by_request_hash=str(request_hash),
                    )
                elif n_would_be >= warn_threshold and not multiplicity_ack:
                    raise ValueError(
                        f"virgin-window book budget acknowledge band (would be spend #{n_would_be} >= "
                        f"{warn_threshold}): pass multiplicity_ack=True after reviewer acknowledgement"
                    )
            recorded_at = _store_now()
            row = {column: "" for column in self.COLUMNS}
            row.update(
                {
                    "oos_window_id": str(oos_window_id),
                    "frozen_set_hash": str(frozen_set_hash),
                    "factor_ids": canonical_json(sorted(str(f) for f in factor_ids)),
                    "seal_mode": normalize_enum(seal_mode),
                    "spend_unit_type": "book_seal",
                    "book_seal_key": str(book_seal_key),
                    "book_plan_hash": str(book_plan_hash),
                    "structural_family": str(structural_family),
                    "request_hash": str(request_hash),
                    "override_id": str(multiplicity_override_id),
                }
            )
            row["recorded_at"] = recorded_at
            row["record_id"] = self._record_id(row, recorded_at)
            frame = pd.concat([frame, pd.DataFrame([row])], ignore_index=True)
            _store_atomic_write(frame, self.log_path)
            row["resumed"] = False
            return row

    def reserve_a5_study_spend(
        self,
        *,
        oos_window_id: str,
        frozen_set_hash: str,
        override_id: str,
        request_hash: str,
        factor_ids: Sequence[str] = (),
        seal_mode: str = "live",
        warn_threshold: int = 3,
        hard_threshold: int = 5,
        multiplicity_ack: bool = False,
        override_store=None,
        a6_multiplicity_override_id: str = "",
    ) -> dict[str, Any]:
        """PR3 REWORK (R2 Blocker 4 + R3 Blocker 2/3) — the ATOMIC A5 study reservation,
        called by ``reproduce_sealed_oos`` (against the CANONICAL ledger derived from the
        global holdout root, never a caller-selected path) BEFORE its holdout claim.
        Idempotent on the A5 unit ``(window, frozen_set_hash)`` with STRICT request
        binding (``request_hash`` is mandatory non-blank; a changed recipe can never
        resume a prior A5 spend). The A6 virgin budget is enforced IN HERE, under this
        lock, with INCLUSIVE boundaries matching ``virgin_window_multiplicity``: the
        3rd distinct spend-unit key requires ``multiplicity_ack``; the 5th requires a
        pre-recorded CONSUMED ``a6_multiplicity`` authorization verified FROM the
        ``override_store`` — an A5 authorization grants exceptional ACCESS, it never
        replaces A6's multiplicity control (R3 Blocker 2)."""
        if not str(override_id).strip():
            raise ValueError("reserve_a5_study_spend requires the consumed A5 override_id")
        if not str(request_hash).strip():
            raise ValueError(
                "reserve_a5_study_spend requires a non-blank request_hash (the A5 spend is "
                "bound to ONE recipe — R3 Blocker 3)"
            )
        with file_lock(self.lock_path):
            frame = self._load()
            mask = (
                (frame["oos_window_id"].astype("string") == str(oos_window_id))
                & (frame["frozen_set_hash"].astype("string") == str(frozen_set_hash))
                & (frame["spend_unit_type"].astype("string").fillna("") == "a5_signal_replication_study")
            )
            mine = frame[mask]
            if not mine.empty:
                row = mine.iloc[-1].to_dict()
                if str(row.get("request_hash") or "") != str(request_hash):
                    raise ValueError(
                        f"reserve_a5_study_spend: (window={oos_window_id}, frozen_set="
                        f"{frozen_set_hash}) was reserved under request_hash "
                        f"{row.get('request_hash')!r}, not {request_hash!r} — a changed "
                        "recipe cannot resume a prior A5 spend (blank legacy rows are "
                        "quarantined)"
                    )
                row["resumed"] = True
                return row
            # R3 Blocker 2: the A6 virgin budget applies to A5 spends too, atomically here.
            window_mask = frame["oos_window_id"].astype("string") == str(oos_window_id)
            sub = frame[window_mask]
            keys = sub["book_seal_key"].astype("string").fillna("")
            fallback = sub["frozen_set_hash"].astype("string").fillna("")
            merged = keys.where(keys.str.len() > 0, fallback)
            existing_keys = {k for k in merged.dropna().unique().tolist() if k}
            n_would_be = len(existing_keys) + 1
            if n_would_be >= hard_threshold:
                if override_store is None or not str(a6_multiplicity_override_id).strip():
                    raise ValueError(
                        f"virgin-window A5 budget HARD STOP (would be spend #{n_would_be} >= "
                        f"{hard_threshold}): requires a pre-recorded a6_multiplicity "
                        "authorization (override_store + a6_multiplicity_override_id) — the A5 "
                        "access authorization does NOT replace A6's multiplicity control"
                    )
                # R4 Major 1: the a6 authorization is CONSUMED here, bound to THIS A5
                # request — an authorization consumed for some other recipe can never
                # admit this spend, and consumption happens only when the hard band is
                # actually hit (no waste below it).
                override_store.consume_authorization(
                    kind="a6_multiplicity",
                    override_id=str(a6_multiplicity_override_id),
                    oos_window_id=str(oos_window_id),
                    scope_key=str(frozen_set_hash),
                    consumed_by_request_hash=str(request_hash),
                )
            elif n_would_be >= warn_threshold and not multiplicity_ack:
                raise ValueError(
                    f"virgin-window A5 budget acknowledge band (would be spend #{n_would_be} >= "
                    f"{warn_threshold}): pass multiplicity_ack=True after reviewer acknowledgement"
                )
            recorded_at = _store_now()
            row = {column: "" for column in self.COLUMNS}
            row.update(
                {
                    "oos_window_id": str(oos_window_id),
                    "frozen_set_hash": str(frozen_set_hash),
                    "factor_ids": canonical_json(sorted(str(f) for f in factor_ids)),
                    "seal_mode": normalize_enum(seal_mode),
                    "spend_unit_type": "a5_signal_replication_study",
                    "override_id": str(override_id),
                    "request_hash": str(request_hash or ""),
                }
            )
            row["recorded_at"] = recorded_at
            row["record_id"] = self._record_id(row, recorded_at)
            frame = pd.concat([frame, pd.DataFrame([row])], ignore_index=True)
            _store_atomic_write(frame, self.log_path)
            row["resumed"] = False
            return row

    def distinct_frozen_sets(self, oos_window_id: str) -> list[str]:
        frame = self._load()
        frame = frame[frame["oos_window_id"].astype("string") == str(oos_window_id)]
        return sorted(frame["frozen_set_hash"].astype("string").dropna().unique().tolist())

    def tier_counts(self, oos_window_id: str) -> dict[str, int]:
        """Distinct-frozen-set counts by evidence_tier for the window."""
        frame = self._load()
        frame = frame[frame["oos_window_id"].astype("string") == str(oos_window_id)]
        frame = frame.drop_duplicates(subset=["frozen_set_hash"])
        counts: dict[str, int] = {}
        for tier in frame["evidence_tier"].astype("string").fillna(""):
            key = tier or "unspecified"
            counts[key] = counts.get(key, 0) + 1
        return counts

    def distinct_spend_keys(self, oos_window_id: str) -> list[str]:
        """v1.4 A6: the per-window SPEND-UNIT keys — ``book_seal_key`` where set (book
        spends), else ``frozen_set_hash`` (legacy / frozen-set / A5-study rows). This is
        the virgin-window budget's counting unit; ``book_plan_hash`` grouping is
        disclosure-only and lives in the report layer."""
        frame = self._load()
        frame = frame[frame["oos_window_id"].astype("string") == str(oos_window_id)]
        if frame.empty:
            return []
        keys = frame["book_seal_key"].astype("string").fillna("")
        fallback = frame["frozen_set_hash"].astype("string").fillna("")
        merged = keys.where(keys.str.len() > 0, fallback)
        return sorted(k for k in merged.dropna().unique().tolist() if k)


class TudEquivalenceAliasStore(AppendOnlyStore):
    """v1.4 A7/N1 — the migration relief for PRE-v1.4 candidates whose Stage-5 evidence
    predates the TUD machinery. An alias binds that legacy evidence to a full
    TUD-relevant payload; acceptance requires EXACT equality between the alias payload
    and the current TUD on ``target_universe_id`` + ``universe_definition_filters`` +
    ``eligibility_policy`` + ``asof_policy`` (the full live TUD identity — round-2 N1:
    universe-id equality alone is NEVER sufficient). Anything absent, stale,
    non-canonical, or mismatched -> the resolver refuses ``candidate_scope_mismatch`` and
    the candidate must pass a target-scoped IS re-audition under the current TUD.
    Aliases must be recorded BEFORE Stage-7 freeze (``recorded_before_stage7_freeze``)."""

    FILENAME = "tud_equivalence_alias.parquet"
    COLUMNS = (
        "record_id",
        "recorded_at",
        "alias_id",
        "alias_version",
        "created_at",
        "recorded_before_stage7_freeze",
        "factor_id",
        "factor_version",
        "definition_hash",
        "source_evidence_id",
        "stage5_methodology_hash",
        "evidence_window",
        "target_universe_id",
        "universe_definition_filters_json",
        "eligibility_policy",
        "asof_policy",
        "data_policy_ids_json",
        "alias_payload_hash",
    )
    SCHEMA = {column: "string" for column in COLUMNS}
    KEY_FIELDS = ("alias_id", "alias_version")

    # Fields that must be non-empty for the alias to be acceptable at all (N1: "if any
    # required field is absent ... the resolver refuses"). Implementation-review
    # Blocker 3: the FULL migration payload is required — including the factor VERSION
    # and the data/calendar policy identifiers needed to reproduce the Stage-5 panel.
    REQUIRED_FIELDS = (
        "alias_id",
        "alias_version",
        "created_at",
        "recorded_before_stage7_freeze",
        "factor_id",
        "factor_version",
        "definition_hash",
        "source_evidence_id",
        "stage5_methodology_hash",
        "evidence_window",
        "target_universe_id",
        "universe_definition_filters_json",
        "eligibility_policy",
        "asof_policy",
        "data_policy_ids_json",
    )

    def record_alias(self, **fields: Any) -> dict[str, Any]:
        if fields.get("recorded_before_stage7_freeze") not in (True, "True", "true"):
            raise ValueError(
                "TudEquivalenceAliasStore.record_alias: recorded_before_stage7_freeze=True is "
                "required (an alias recorded after freeze cannot back a clean admission)"
            )
        fields["recorded_before_stage7_freeze"] = "True"
        missing = [f for f in self.REQUIRED_FIELDS if not str(fields.get(f) or "").strip()]
        if missing:
            raise ValueError(f"TudEquivalenceAliasStore.record_alias missing required fields: {missing}")
        # Blocker 3: the data/calendar identifiers must be REAL (canonical JSON with a
        # non-empty provider_build_id + calendar_policy_id), not a placeholder — without
        # them the alias cannot prove which data regime produced the Stage-5 evidence.
        try:
            data_policy = json.loads(str(fields.get("data_policy_ids_json") or ""))
        except json.JSONDecodeError as exc:
            raise ValueError(
                "TudEquivalenceAliasStore.record_alias: data_policy_ids_json must be "
                "canonical JSON carrying the Stage-5 provider/calendar/data-policy ids"
            ) from exc
        if not isinstance(data_policy, Mapping) or not all(
            str(data_policy.get(k, "")).strip()
            for k in ("provider_build_id", "calendar_policy_id")
        ):
            raise ValueError(
                "TudEquivalenceAliasStore.record_alias: data_policy_ids_json must carry "
                "non-empty provider_build_id and calendar_policy_id; otherwise run a "
                "target-scoped IS re-audition under the current TUD"
            )
        payload = {k: str(fields.get(k, "")) for k in self.REQUIRED_FIELDS}
        fields["alias_payload_hash"] = payload_hash(payload)
        return self.record(**fields)

    def latest_for_factor(self, *, factor_id: str, definition_hash: str) -> dict[str, Any] | None:
        return self.latest(factor_id=str(factor_id), definition_hash=str(definition_hash))
