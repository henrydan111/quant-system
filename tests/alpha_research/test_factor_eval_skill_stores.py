"""D1 sidecar-store tests for src/alpha_research/factor_eval_skill/stores.py.

Covers: round-trip + persistence-across-instances; the IS-spent rule + evidence_tier /
role validation; scope-keyed coexistence (the reason D1 is three stores, not one);
unknown-field rejection; append-only latest; and envelope-store legacy rows.
"""
from __future__ import annotations

import json

import pytest

from src.alpha_research.factor_eval_skill.identity import FrozenSelectionEnvelope
from src.alpha_research.factor_eval_skill.stores import (
    FactorProvenanceStore,
    FilterCharacterizationStore,
    FilterDeploymentGateStore,
    FrozenSelectionEnvelopeStore,
    RoleDeclarationStore,
    Stage3QualityRecordStore,
)


# ----- FactorProvenanceStore -----

def test_provenance_roundtrip_and_persist_across_instances(tmp_path):
    store = FactorProvenanceStore(tmp_path)
    store.record_provenance(
        factor_id="mom_overnight_20d", definition_hash="def_a",
        evidence_tier="theory_a_priori", direction_source="theory",
        multiplicity_scope_id="oos_2021_2026",
    )
    # reopen with a fresh instance — data persists on disk
    reopened = FactorProvenanceStore(tmp_path)
    row = reopened.latest(factor_id="mom_overnight_20d", definition_hash="def_a")
    assert row is not None
    assert row["evidence_tier"] == "theory_a_priori"
    assert row["may_cite_is_as_confirmation"] == "True"  # theory tier may cite


def test_provenance_is_spent_rule(tmp_path):
    store = FactorProvenanceStore(tmp_path)
    # a_priori_is_informed defaults may_cite -> False (IS generates, never confirms)
    row = store.record_provenance(
        factor_id="f", definition_hash="d", evidence_tier="a_priori_is_informed",
        direction_source="is_observed", multiplicity_scope_id="m",
    )
    assert row["may_cite_is_as_confirmation"] == "False"
    # explicitly trying to cite IS for that tier is a contradiction -> raise
    with pytest.raises(ValueError, match="IS-spent"):
        store.record_provenance(
            factor_id="f", definition_hash="d", evidence_tier="a_priori_is_informed",
            direction_source="is_observed", multiplicity_scope_id="m",
            may_cite_is_as_confirmation=True,
        )


def test_provenance_rejects_bad_evidence_tier(tmp_path):
    store = FactorProvenanceStore(tmp_path)
    with pytest.raises(ValueError, match="evidence_tier"):
        store.record_provenance(
            factor_id="f", definition_hash="d", evidence_tier="made_up_tier",
            direction_source="theory", multiplicity_scope_id="m",
        )


# ----- RoleDeclarationStore -----

def test_role_context_hash_distinguishes_contexts(tmp_path):
    store = RoleDeclarationStore(tmp_path)
    r1 = store.record_role(
        factor_id="f", definition_hash="d", role="ranking",
        role_context={"strategy": "guoren_A", "universe": "univ_liquid_top300"},
        direction="long",
    )
    r2 = store.record_role(
        factor_id="f", definition_hash="d", role="filter",
        role_context={"strategy": "guoren_B", "universe": "univ_all"},
        direction="long", filter_role_subtype="risk_exclusion",
    )
    assert r1["role_context_hash"] != r2["role_context_hash"]  # different contexts, no collision
    # the role_context_json round-trips to the normalized mapping
    assert json.loads(r2["role_context_json"])["strategy"] == "guoren_b" or \
        json.loads(r2["role_context_json"])["strategy"] == "guoren_B"


def test_role_rejects_bad_role(tmp_path):
    store = RoleDeclarationStore(tmp_path)
    with pytest.raises(ValueError, match="role must be one of"):
        store.record_role(
            factor_id="f", definition_hash="d", role="sometimes",
            role_context={}, direction="long",
        )


# ----- Stage3QualityRecordStore: the scope-coexistence reason D1 is split -----

def test_stage3_same_factor_two_targets_coexist(tmp_path):
    store = Stage3QualityRecordStore(tmp_path)
    common = dict(
        factor_id="liq_vstd_20d", definition_hash="d", layer1_methodology_hash="m1", role="ranking",
        quality_flags={}, universe_profile={}, cross_universe_sign_divergence=False,
    )
    store.record_quality(
        target_universe_declaration_hash="tud_all", target_universe_pass=True,
        status_effect="candidate_ceiling", **common,
    )
    store.record_quality(
        target_universe_declaration_hash="tud_liquid", target_universe_pass=False,
        status_effect="availability_floor_fail", **common,
    )
    all_rows = store.list_all()
    assert len(all_rows) == 2  # both scopes coexist; neither overwrites the other
    liquid = store.latest(
        factor_id="liq_vstd_20d", definition_hash="d", layer1_methodology_hash="m1",
        target_universe_declaration_hash="tud_liquid",
    )
    assert liquid["target_universe_pass"] == "False"
    assert liquid["status_effect"] == "availability_floor_fail"


# ----- base store invariants -----

def test_unknown_field_rejected(tmp_path):
    store = FactorProvenanceStore(tmp_path)
    with pytest.raises(ValueError, match="unknown fields"):
        store.record(factor_id="f", bogus_column="x")


def test_append_only_latest_returns_newest(tmp_path):
    store = FactorProvenanceStore(tmp_path)
    store.record_provenance(
        factor_id="f", definition_hash="d", evidence_tier="theory_a_priori",
        direction_source="theory", multiplicity_scope_id="m", rationale="first",
    )
    store.record_provenance(
        factor_id="f", definition_hash="d", evidence_tier="theory_a_priori",
        direction_source="theory", multiplicity_scope_id="m", rationale="second",
    )
    assert len(store.list_all()) == 2  # append-only, not overwrite
    assert store.latest(factor_id="f", definition_hash="d")["rationale"] == "second"


# ----- filter stores -----

def test_filter_characterization_roundtrip(tmp_path):
    store = FilterCharacterizationStore(tmp_path)
    store.record_characterization(
        factor_id="real_debt_ratio", definition_hash="d",
        target_universe_declaration_hash="tud", threshold="<0.8",
        excluded_tail_return=-0.12, threshold_stability=0.9, breadth=0.4, verdict="useful",
    )
    row = store.latest(
        factor_id="real_debt_ratio", definition_hash="d", role="filter",
        target_universe_declaration_hash="tud", threshold="<0.8",
    )
    assert row is not None and row["verdict"] == "useful"


def test_filter_deployment_gate_roundtrip(tmp_path):
    store = FilterDeploymentGateStore(tmp_path)
    store.record_gate(
        plan_hash="plan_x", filter_id="delist_risk", threshold="==0",
        marginal_sharpe_delta=0.15, marginal_mdd_delta=0.03, verdict="pass",
    )
    row = store.latest(plan_hash="plan_x", filter_id="delist_risk", threshold="==0")
    assert row is not None and row["verdict"] == "pass"


# ----- envelope store -----

def test_envelope_store_roundtrip(tmp_path):
    store = FrozenSelectionEnvelopeStore(tmp_path)
    env = FrozenSelectionEnvelope(
        frozen_set_hash="fsh", target_universe_declaration_hash="tud",
        selected_set_hash="sset", created_at="t", created_by="x",
    )
    store.record_envelope(env)
    got = store.get_envelope("fsh")
    assert got is not None
    assert got["envelope_hash"] == env.envelope_hash
    assert got["legacy_mode"] == "False"
    assert json.loads(got["envelope_json"])["frozen_set_hash"] == "fsh"


def test_envelope_store_legacy_row(tmp_path):
    store = FrozenSelectionEnvelopeStore(tmp_path)
    legacy = FrozenSelectionEnvelope(
        frozen_set_hash="316b17bc_ewave", target_universe_declaration_hash=None,
        selected_set_hash=None, created_at="t", created_by="ewave",
        legacy_mode=True, legacy_reason="pre-v1.3 seal",
    )
    store.record_envelope(legacy)
    got = store.get_envelope("316b17bc_ewave")
    assert got["legacy_mode"] == "True"
    assert got["legacy_reason"] == "pre-v1.3 seal"
    assert got["target_universe_declaration_hash"] == ""  # None -> empty string on disk
