"""D4 orchestration tests for src/alpha_research/factor_eval_skill/orchestration.py.

Covers the full register -> declare_target -> characterize -> gate -> select -> seal(show)
pipeline on an INJECTED native factor (no live registry), the mode rules (deployment_bound
requires a target; exploratory defaults to univ_all), the native/cohort governance contract
+ GPT's no-native-fallback rule, the mandatory identity chain at seal/deploy, and the
STRUCTURAL forbidden-verb invariant (factor-eval has no deploy; strategy-build has no seal).
"""
from __future__ import annotations

import json

import pytest

from src.alpha_research.factor_eval_skill.orchestration import (
    FactorEvalContext,
    FactorEvalError,
    FactorIdentity,
    cmd_characterize,
    cmd_declare_target,
    cmd_deploy,
    cmd_gate,
    cmd_register,
    cmd_seal,
    cmd_select,
    resolve_governance,
)
from src.alpha_research.factor_eval_skill.stage3_reader import ALL_UNIVERSES
from src.alpha_research.factor_eval_skill.stores import FrozenSelectionEnvelopeStore


def _row(factor, universe, icir, *, cov="broad"):
    return {
        "factor": factor, "universe_id": universe, "heldout_rank_icir": icir,
        "mean_rank_ic": icir / 10.0, "sign_consistency": 1.0, "coverage_tier": cov,
        "effective_ic_days": 2600, "field_eligible": True, "layer1_methodology_hash": "l1hash",
    }


def _matrix_file(tmp_path, factor="tf"):
    p = tmp_path / "results.jsonl"
    p.write_text("\n".join(json.dumps(_row(factor, u, 0.45)) for u in ALL_UNIVERSES), encoding="utf-8")
    return p


def _resolver(cohort=""):
    def resolve(factor_id):
        return FactorIdentity(factor_id, f"def_{factor_id}", 2, cohort, "$close")
    return resolve


def _ctx(tmp_path, resolver=None):
    return FactorEvalContext.create(run_dir=tmp_path / "run", store_root=tmp_path / "store",
                                    registry_root=tmp_path / "reg", resolve_factor=resolver or _resolver())


def _register(ctx, mode="deployment_bound", **kw):
    return cmd_register(ctx, factor_id="tf", mode=mode, evidence_tier="theory_a_priori",
                        direction_source="theory", role="ranking", role_direction="long", **kw)


# ----- the full pipeline -----

def test_full_pipeline_native_factor(tmp_path):
    matrix = _matrix_file(tmp_path)
    ctx = _ctx(tmp_path)
    reg = _register(ctx)
    assert reg["definition_hash"] == "def_tf"
    cmd_declare_target(ctx, target_universe_id="univ_liquid_top300", eligibility_policy="liq", asof_policy="pit_lag_1")
    ch = cmd_characterize(ctx, matrix_path=matrix)
    assert ch["status_effect"] == "eligible_for_oos"
    assert ch["target_universe_pass"] is True
    assert ch["factor_class"] == "native"
    gate = cmd_gate(ctx)
    assert gate["candidate_eligible"] is True
    sel = cmd_select(ctx, matrix_path=matrix, pool={"tf": "x"}, caps={"x": 1}, floor=0.10)
    assert [m["factor_id"] for m in sel["members"]] == ["tf"]
    seal = cmd_seal(ctx, mode="show", oos_start="2021-01-01", oos_end="2026-02-27")
    assert seal["frozen_set_hash"] and seal["envelope_hash"]
    assert seal["held_sides"][0]["side"] == "long"  # positive factor -> held long
    # D6: seal --show discloses the system-level multiplicity this spend would add to
    assert seal["multiplicity"]["n_spent"] == 1 and seal["multiplicity"]["action"] == "disclose"
    # the envelope was persisted via the conflict-guarded store
    env = FrozenSelectionEnvelopeStore(ctx.store_root).get_envelope(seal["frozen_set_hash"])
    assert env is not None and env["envelope_hash"] == seal["envelope_hash"]


# ----- mode rules -----

def test_deployment_bound_requires_target_before_characterize(tmp_path):
    ctx = _ctx(tmp_path)
    _register(ctx, mode="deployment_bound")
    with pytest.raises(FactorEvalError, match="deployment_bound"):
        cmd_characterize(ctx, matrix_path=_matrix_file(tmp_path))


def test_exploratory_defaults_to_univ_all(tmp_path):
    ctx = _ctx(tmp_path)
    _register(ctx, mode="exploratory_research")
    ch = cmd_characterize(ctx, matrix_path=_matrix_file(tmp_path))
    assert ch["target_universe_id"] == "univ_all"


# ----- governance contract -----

def test_resolve_governance_native_and_cohort():
    assert resolve_governance(FactorIdentity("tf", "d", 1, "", "$c")).factor_class == "native"
    g = resolve_governance(FactorIdentity("cf", "d", 1, "cicc_x", "$c"),
                           replication_tier="proxy_approx", claim_class="c", oos_eligibility="pending")
    assert g.factor_class == "cohort" and g.replication_tier == "proxy_approx"


def test_declared_cohort_without_manifest_row_fails_not_native():
    # GPT rule: a declared cohort with no replication_cohort_id must FAIL, never fall back to native
    with pytest.raises(FactorEvalError, match="manifest row was expected"):
        resolve_governance(FactorIdentity("tf", "d", 1, "", "$c"), factor_class="cohort",
                           replication_tier="proxy_approx", claim_class="c", oos_eligibility="pending")


def test_cohort_factor_caps_lower_through_the_pipeline(tmp_path):
    # a cohort factor with proxy_approx tier -> candidate_ceiling (not eligible_for_oos)
    matrix = _matrix_file(tmp_path)
    ctx = _ctx(tmp_path, resolver=_resolver(cohort="cicc_x"))
    _register(ctx, mode="deployment_bound")
    cmd_declare_target(ctx, target_universe_id="univ_liquid_top300", eligibility_policy="liq", asof_policy="pit_lag_1")
    ch = cmd_characterize(ctx, matrix_path=matrix, replication_tier="proxy_approx",
                          claim_class="clean_singleton_primary", oos_eligibility="pending")
    assert ch["factor_class"] == "cohort"
    assert ch["status_effect"] == "candidate_ceiling"


# ----- identity chain enforcement -----

def test_seal_rejects_tud_mismatch(tmp_path):
    matrix = _matrix_file(tmp_path)
    ctx = _ctx(tmp_path)
    _register(ctx)
    cmd_declare_target(ctx, target_universe_id="univ_liquid_top300", eligibility_policy="liq", asof_policy="pit_lag_1")
    cmd_characterize(ctx, matrix_path=matrix)
    cmd_select(ctx, matrix_path=matrix, pool={"tf": "x"}, caps={"x": 1}, floor=0.10)
    corrupt = ctx._read("selected_set.json")
    corrupt["tud_hash"] = "WRONG"
    ctx._write("selected_set.json", corrupt)
    with pytest.raises(FactorEvalError, match="tud_hash"):
        cmd_seal(ctx, mode="show", oos_start="a", oos_end="b")


def test_deploy_show_builds_plan_and_chains(tmp_path):
    matrix = _matrix_file(tmp_path)
    ctx = _ctx(tmp_path)
    _register(ctx)
    cmd_declare_target(ctx, target_universe_id="univ_liquid_top300", eligibility_policy="liq", asof_policy="pit_lag_1")
    cmd_characterize(ctx, matrix_path=matrix)
    cmd_select(ctx, matrix_path=matrix, pool={"tf": "x"}, caps={"x": 1}, floor=0.10)
    seal = cmd_seal(ctx, mode="show", oos_start="2021-01-01", oos_end="2026-02-27")
    out = cmd_deploy(ctx, mode="show", deployment_universe="univ_liquid_top300", portfolio_side="long_only",
                     construction={"topk": 30}, pre_declared_bar={"min_cagr": "0.05"})
    assert out["plan_hash"]
    assert out["frozen_set_hash"] == seal["frozen_set_hash"]


def test_deploy_requires_seal_artifact(tmp_path):
    ctx = _ctx(tmp_path)
    with pytest.raises(FactorEvalError, match="seal"):
        cmd_deploy(ctx, mode="show", deployment_universe="u", portfolio_side="long_only",
                   construction={}, pre_declared_bar={})


# ----- self-review fixes (2026-06-21) -----

def test_select_multi_factor_requires_corr(tmp_path):
    ctx = _ctx(tmp_path)
    _register(ctx)
    cmd_declare_target(ctx, target_universe_id="univ_all", eligibility_policy="r", asof_policy="pit_lag_1")
    # a 2-factor pool with NO precomputed correlation -> fail-closed (no no-redundancy selection)
    with pytest.raises(FactorEvalError, match="exposure correlation"):
        cmd_select(ctx, matrix_path=_matrix_file(tmp_path), pool={"tf": "x", "tf2": "y"},
                   caps={"x": 1, "y": 1}, floor=0.10)


def test_live_seal_requires_global_holdout_root(tmp_path):
    matrix = _matrix_file(tmp_path)
    ctx = _ctx(tmp_path)  # no holdout_seal_root configured
    _register(ctx)
    cmd_declare_target(ctx, target_universe_id="univ_liquid_top300", eligibility_policy="l", asof_policy="pit_lag_1")
    cmd_characterize(ctx, matrix_path=matrix)
    cmd_select(ctx, matrix_path=matrix, pool={"tf": "x"}, caps={"x": 1}, floor=0.10)
    # a live seal without the global store is refused BEFORE any spend/backtest
    with pytest.raises(FactorEvalError, match="holdout_seal_root"):
        cmd_seal(ctx, mode="live", oos_start="2021-01-01", oos_end="2026-02-27")
    # ... and no spend leaked into the ledger
    from src.alpha_research.factor_eval_skill.stores import OosWindowLedgerStore
    assert OosWindowLedgerStore(ctx.store_root).distinct_frozen_sets("2021-01-01..2026-02-27") == []


# ----- forbidden-verb invariant (structural) -----

def test_forbidden_verbs_are_structural():
    from workspace.scripts import factor_eval_cli as fe
    from workspace.scripts import strategy_build_cli as sb
    # factor-eval wires seal but NOT deploy; strategy-build wires deploy but NOT seal
    assert hasattr(fe, "cmd_seal") and not hasattr(fe, "cmd_deploy")
    assert hasattr(sb, "cmd_deploy") and not hasattr(sb, "cmd_seal")
    fe_cmds = set(fe.build_parser()._subparsers._group_actions[0].choices)
    sb_cmds = set(sb.build_parser()._subparsers._group_actions[0].choices)
    assert "seal" in fe_cmds and "deploy" not in fe_cmds
    assert sb_cmds == {"deploy"}
