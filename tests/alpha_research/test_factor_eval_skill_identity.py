"""D2 identity-spine tests for src/alpha_research/factor_eval_skill/identity.py.

Covers: deterministic + cosmetically-stable + field-sensitive hashing; order-independent
SelectedSet hash; the mandatory assert_identity_chain (pass + every mismatch + legacy
refusal); and the load-bearing back-compat guarantee — wrapping an existing
FrozenSelectionSet in an envelope does NOT change its frozen_set_hash, and HoldoutSealStore
still keys by that hash (the spent E-wave seal stays valid).
"""
from __future__ import annotations

import pytest

from src.alpha_research.factor_eval_skill.identity import (
    DeploymentFrozenPlan,
    FrozenSelectionEnvelope,
    IdentityChainError,
    SelectedRepresentative,
    SelectedSet,
    TargetUniverseDeclaration,
    assert_identity_chain,
)
from src.research_orchestrator.frozen_selection_set import FrozenSelectionSet, SelectedFactor
from src.research_orchestrator.holdout_seal import HoldoutSealStore


def _chain(frozen_set_hash: str = "fsh_0001"):
    tud = TargetUniverseDeclaration(
        target_universe_id="univ_liquid_top300",
        universe_definition_filters={"adv_min": 300, "list_age_min_days": 365, "exclude_st": True},
        eligibility_policy="liquid_top300_by_20d_dollar_vol",
        asof_policy="pit_lag_1",
    )
    reps = (
        SelectedRepresentative("mom_overnight_20d", 1, "def_aaa", "long"),
        SelectedRepresentative("liq_vstd_20d", 2, "def_bbb", "short"),
    )
    sset = SelectedSet(
        tud_hash=tud.tud_hash, pool_hash="pool_hash", selected=reps, selection_code_hash="code_hash"
    )
    env = FrozenSelectionEnvelope(
        frozen_set_hash=frozen_set_hash,
        target_universe_declaration_hash=tud.tud_hash,
        selected_set_hash=sset.selected_set_hash,
        created_at="2026-06-21 00:00:00",
        created_by="test",
    )
    plan = DeploymentFrozenPlan(
        frozen_set_hash=frozen_set_hash,
        envelope_hash=env.envelope_hash,
        target_universe_declaration_hash=tud.tud_hash,
        deployment_universe="univ_liquid_top300",
        portfolio_side="long_only",
        construction={"topk": 30, "rebalance": "monthly"},
        pre_declared_bar={"min_cagr": "0.05", "max_mdd": "0.40", "min_sharpe": "0.80"},
    )
    return tud, sset, env, plan


# ----- hashing -----

def test_tud_hash_deterministic_and_cosmetically_stable():
    a = TargetUniverseDeclaration("Univ_Liquid_Top300 ", {"adv_min": 300}, "Policy_X", "PIT_Lag_1")
    b = TargetUniverseDeclaration("univ_liquid_top300", {"adv_min": 300}, "policy_x", "pit_lag_1")
    assert a.tud_hash == b.tud_hash  # enum case/whitespace normalized
    c = TargetUniverseDeclaration("univ_liquid_top300", {"adv_min": 301}, "policy_x", "pit_lag_1")
    assert c.tud_hash != a.tud_hash  # a structural field change DOES move the hash


def test_selected_set_hash_order_independent_and_direction_sensitive():
    tud_hash = "tud_x"
    r1 = SelectedRepresentative("a", 1, "da", "long")
    r2 = SelectedRepresentative("b", 1, "db", "short")
    s_ab = SelectedSet(tud_hash, "pool", (r1, r2), "code")
    s_ba = SelectedSet(tud_hash, "pool", (r2, r1), "code")
    assert s_ab.selected_set_hash == s_ba.selected_set_hash  # order-independent
    r2_flip = SelectedRepresentative("b", 1, "db", "long")
    s_flip = SelectedSet(tud_hash, "pool", (r1, r2_flip), "code")
    assert s_flip.selected_set_hash != s_ab.selected_set_hash  # expected_direction is part of identity


def test_envelope_hash_is_not_the_seal_key():
    _, _, env, _ = _chain("fsh_unique")
    assert env.frozen_set_hash == "fsh_unique"  # carried verbatim, never re-hashed
    assert env.envelope_hash != env.frozen_set_hash  # envelope integrity hash is separate


# ----- assert_identity_chain -----

def test_identity_chain_consistent_passes():
    tud, sset, env, plan = _chain()
    assert_identity_chain(tud, sset, env, plan)  # no raise
    assert_identity_chain(tud, sset, env)  # plan optional


def test_identity_chain_selected_set_tud_mismatch_raises():
    tud, _, env, _ = _chain()
    bad_sset = SelectedSet("WRONG_TUD", "pool", (SelectedRepresentative("a", 1, "d", "long"),), "code")
    with pytest.raises(IdentityChainError, match="SelectedSet.tud_hash"):
        assert_identity_chain(tud, bad_sset, env)


def test_identity_chain_envelope_tud_mismatch_raises():
    tud, sset, _, _ = _chain()
    bad_env = FrozenSelectionEnvelope(
        frozen_set_hash="fsh", target_universe_declaration_hash="WRONG",
        selected_set_hash=sset.selected_set_hash, created_at="t", created_by="x",
    )
    with pytest.raises(IdentityChainError, match="target_universe_declaration_hash"):
        assert_identity_chain(tud, sset, bad_env)


def test_identity_chain_envelope_selected_set_mismatch_raises():
    tud, sset, _, _ = _chain()
    bad_env = FrozenSelectionEnvelope(
        frozen_set_hash="fsh", target_universe_declaration_hash=tud.tud_hash,
        selected_set_hash="WRONG", created_at="t", created_by="x",
    )
    with pytest.raises(IdentityChainError, match="selected_set_hash"):
        assert_identity_chain(tud, sset, bad_env)


@pytest.mark.parametrize("field", ["tud", "frozen_set_hash", "envelope_hash"])
def test_identity_chain_plan_mismatch_raises(field):
    tud, sset, env, plan = _chain()
    kwargs = dict(
        frozen_set_hash=plan.frozen_set_hash,
        envelope_hash=plan.envelope_hash,
        target_universe_declaration_hash=plan.target_universe_declaration_hash,
        deployment_universe=plan.deployment_universe,
        portfolio_side=plan.portfolio_side,
        construction=dict(plan.construction),
        pre_declared_bar=dict(plan.pre_declared_bar),
    )
    if field == "tud":
        kwargs["target_universe_declaration_hash"] = "WRONG"
    elif field == "frozen_set_hash":
        kwargs["frozen_set_hash"] = "WRONG"
    elif field == "envelope_hash":
        kwargs["envelope_hash"] = "WRONG"
    bad_plan = DeploymentFrozenPlan(**kwargs)
    with pytest.raises(IdentityChainError):
        assert_identity_chain(tud, sset, env, bad_plan)


def test_legacy_envelope_cannot_assert_clean_chain():
    tud, sset, _, _ = _chain()
    legacy = FrozenSelectionEnvelope(
        frozen_set_hash="316b17bc_ewave",
        target_universe_declaration_hash=None,
        selected_set_hash=None,
        created_at="2026-06-21 00:00:00",
        created_by="ewave",
        legacy_mode=True,
        legacy_reason="pre-v1.3 seal",
    )
    with pytest.raises(IdentityChainError, match="legacy"):
        assert_identity_chain(tud, sset, legacy)


# ----- back-compat: the spent E-wave seal must stay valid -----

def _frozen_selection_set() -> FrozenSelectionSet:
    return FrozenSelectionSet(
        selected=(
            SelectedFactor("liq_vstd_20d", 2, "def_bbb", "short"),
            SelectedFactor("mom_overnight_20d", 1, "def_aaa", "long"),
        ),
        candidate_pool_hash="pool",
        selection_rule_hash="rule",
        eval_protocol_hash="proto",
        metric="rank_icir",
        portfolio_side="long_short",
        universe="univ_all",
        time_split_window="2021-01-01..2026-02-27",
        rebalance="monthly",
        neutralization="size_industry",
    )


def test_envelope_does_not_change_frozen_set_hash():
    fss = _frozen_selection_set()
    seal_key = fss.frozen_set_hash
    env = FrozenSelectionEnvelope(
        frozen_set_hash=seal_key,
        target_universe_declaration_hash="tud",
        selected_set_hash="sset",
        created_at="t",
        created_by="x",
    )
    assert env.frozen_set_hash == seal_key  # envelope carries the seal key verbatim
    # recomputing the identical FrozenSelectionSet yields the SAME hash (no mutation path)
    assert _frozen_selection_set().frozen_set_hash == seal_key


def test_holdout_seal_still_keys_by_frozen_set_hash(tmp_path):
    fss = _frozen_selection_set()
    seal_key = fss.frozen_set_hash
    store = HoldoutSealStore(tmp_path / "seals")
    store.claim_holdout_access(
        design_hash="legacy_design", seal_key=seal_key, hypothesis_id="hyp",
        structural_family="fam", profile_id="prof",
        run_dir=str(tmp_path / "run1"), step_id="s1",
    )
    # a second claim under the same frozen_set_hash is sealed — exactly the E-wave guarantee
    with pytest.raises(ValueError, match="sealed"):
        store.claim_holdout_access(
            design_hash="legacy_design", seal_key=seal_key, hypothesis_id="hyp",
            structural_family="fam", profile_id="prof",
            run_dir=str(tmp_path / "run2"), step_id="s2",
        )
