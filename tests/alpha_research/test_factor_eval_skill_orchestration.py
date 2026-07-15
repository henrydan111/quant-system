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


@pytest.fixture(autouse=True)
def _isolate_canonical_holdout_root(tmp_path, monkeypatch):
    """PR3 R5 B1: cmd_seal's seal store + budget ledger now derive from the ONE configured
    canonical root — NOT a ctx field. Isolate it per test so the multiplicity denominator
    doesn't read the real data/holdout_seals (the historical E-wave/GP/arXiv seals). A test
    that needs a specific root re-patches the resolver in its own body (that wins)."""
    import src.research_orchestrator.holdout_seal as hs_mod
    monkeypatch.setattr(hs_mod, "resolve_configured_global_holdout_root",
                        lambda: tmp_path / "_canonical_holdout")


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
    cmd_gate(ctx)  # select now requires a candidate-eligible gate decision
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
    cmd_gate(ctx)  # select now requires a candidate-eligible gate decision
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
    # a 2-factor pool with NO precomputed correlation -> fail-closed (no no-redundancy selection).
    # require_eligibility=False isolates the corr guard (eligibility is exercised separately).
    with pytest.raises(FactorEvalError, match="exposure correlation"):
        cmd_select(ctx, matrix_path=_matrix_file(tmp_path), pool={"tf": "x", "tf2": "y"},
                   caps={"x": 1, "y": 1}, floor=0.10, require_eligibility=False)


def test_live_seal_uses_configured_root_and_catalog_gate(tmp_path, monkeypatch):
    # PR3 R4 B1/B3: a live seal derives EVERY sealed store from the CONFIGURED global
    # holdout root (tests monkeypatch the resolver — there is no caller path to fork a
    # sealed world), and expressions must resolve from the CURRENT catalog: the fake
    # test factor "tf" is not in the catalog, so the live path refuses at the
    # definition-binding gate BEFORE any claim — nothing lands in the configured root
    # or the ledger.
    import src.research_orchestrator.holdout_seal as hs_mod
    import src.research_orchestrator.promotion_evidence as pe
    from src.research_orchestrator.promotion_evidence import PromotionEvidenceError

    monkeypatch.setattr(hs_mod, "resolve_configured_global_holdout_root",
                        lambda: tmp_path / "configured_holdout")
    # provenance loads before the catalog gate; stub it (a bare cmd_seal has qlib_dir="")
    # so the test reaches the definition-binding refusal it is asserting.
    monkeypatch.setattr(pe, "_load_provider_provenance",
                        lambda qdir: {"provider_build_id": "pb", "calendar_policy_id": "cp",
                                      "calendar_end": "2026-02-27"})
    matrix = _matrix_file(tmp_path)
    ctx = _ctx(tmp_path)
    _register(ctx)
    cmd_declare_target(ctx, target_universe_id="univ_liquid_top300", eligibility_policy="l", asof_policy="pit_lag_1")
    cmd_characterize(ctx, matrix_path=matrix)
    cmd_gate(ctx)
    cmd_select(ctx, matrix_path=matrix, pool={"tf": "x"}, caps={"x": 1}, floor=0.10)
    with pytest.raises(PromotionEvidenceError, match="not in the current catalog"):
        cmd_seal(ctx, mode="live", oos_start="2021-01-01", oos_end="2026-02-27")
    from src.research_orchestrator.holdout_seal import HoldoutSealStore
    from src.alpha_research.factor_eval_skill.stores import OosWindowLedgerStore
    assert HoldoutSealStore(tmp_path / "configured_holdout").list_events().empty
    assert OosWindowLedgerStore(ctx.store_root).distinct_frozen_sets("2021-01-01..2026-02-27") == []


# ----- GPT re-review hardening (2026-06-21) -----

def _full_pipeline_to_select(ctx, tmp_path, target="univ_liquid_top300"):
    matrix = _matrix_file(tmp_path)
    _register(ctx)
    cmd_declare_target(ctx, target_universe_id=target, eligibility_policy="l", asof_policy="pit_lag_1")
    cmd_characterize(ctx, matrix_path=matrix)
    cmd_gate(ctx)
    cmd_select(ctx, matrix_path=matrix, pool={"tf": "x"}, caps={"x": 1}, floor=0.10)
    return matrix


def test_seal_dryrun_mode_removed(tmp_path):
    # dryrun was an OOS-leak path (run-local seal + real OOS) -> removed
    with pytest.raises(FactorEvalError, match="dryrun removed"):
        cmd_seal(_ctx(tmp_path), mode="dryrun")


def test_portfolio_side_is_identity_bearing(tmp_path):
    ctx = _ctx(tmp_path)
    _full_pipeline_to_select(ctx, tmp_path)
    ls = cmd_seal(ctx, mode="show", oos_start="2021-01-01", oos_end="2026-02-27", portfolio_side="long_short")
    lo = cmd_seal(ctx, mode="show", oos_start="2021-01-01", oos_end="2026-02-27", portfolio_side="long_only")
    assert ls["frozen_set_hash"] != lo["frozen_set_hash"]  # portfolio_side moves the hash
    assert lo["portfolio_side"] == "long_only"


def test_select_uses_declared_target_universe_not_univ_all(tmp_path):
    ctx = _ctx(tmp_path)
    _matrix_file(tmp_path)
    _register(ctx)
    cmd_declare_target(ctx, target_universe_id="univ_csi300", eligibility_policy="l", asof_policy="pit_lag_1")
    cmd_characterize(ctx, matrix_path=tmp_path / "results.jsonl")
    cmd_gate(ctx)
    sel = cmd_select(ctx, matrix_path=tmp_path / "results.jsonl", pool={"tf": "x"}, caps={"x": 1}, floor=0.10)
    assert sel["selection_universe"] == "univ_csi300"  # the declared target, not a hardcoded univ_all


def test_select_refuses_un_eligible_factor(tmp_path):
    # a weak factor that fails its gate cannot be selected (fail-closed)
    weak = tmp_path / "weak.jsonl"
    weak.write_text("\n".join(json.dumps(_row("tf", u, 0.02)) for u in ALL_UNIVERSES), encoding="utf-8")
    ctx = _ctx(tmp_path)
    _register(ctx)
    cmd_declare_target(ctx, target_universe_id="univ_liquid_top300", eligibility_policy="l", asof_policy="pit_lag_1")
    cmd_characterize(ctx, matrix_path=weak)
    assert cmd_gate(ctx)["candidate_eligible"] is False
    with pytest.raises(FactorEvalError, match="not candidate_eligible"):
        cmd_select(ctx, matrix_path=weak, pool={"tf": "x"}, caps={"x": 1}, floor=0.10)


def test_pool_hash_includes_full_factor_identity(tmp_path):
    def pool_hash_for(suffix, defhash):
        ctx = _ctx(tmp_path / suffix,
                   resolver=lambda fid, _d=defhash: FactorIdentity(fid, _d, 2, "", "$close"))
        _register(ctx)
        cmd_declare_target(ctx, target_universe_id="univ_liquid_top300", eligibility_policy="l", asof_policy="pit_lag_1")
        cmd_characterize(ctx, matrix_path=_matrix_file(tmp_path))
        cmd_gate(ctx)
        return cmd_select(ctx, matrix_path=_matrix_file(tmp_path), pool={"tf": "x"}, caps={"x": 1}, floor=0.10)["pool_hash"]
    # a changed factor definition_hash -> a different candidate_pool_hash (not factor-ID-only)
    assert pool_hash_for("a", "def_tf_A") != pool_hash_for("b", "def_tf_B")


def test_pool_eligibility_requires_ranking_role_and_matching_methodology(tmp_path):
    # GPT re-verify: a filter-role or stale-Layer-1-methodology Stage-3 record must NOT satisfy
    # ranking eligibility for a selected ranking set.
    import numpy as np
    import pandas as pd
    from src.alpha_research.factor_eval_skill.stores import Stage3QualityRecordStore

    rows = []
    for fac in ("A", "B"):
        for u in ALL_UNIVERSES:
            r = _row(fac, u, 0.45)
            r["layer1_methodology_hash"] = "L1"
            rows.append(r)
    matrix = tmp_path / "m.jsonl"
    matrix.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    ctx = _ctx(tmp_path)  # fake resolver -> def_<fid>, version 2, native
    cmd_register(ctx, factor_id="A", mode="deployment_bound", evidence_tier="theory_a_priori",
                 direction_source="theory", role="ranking", role_direction="long")
    cmd_declare_target(ctx, target_universe_id="univ_liquid_top300", eligibility_policy="l", asof_policy="pit_lag_1")
    cmd_characterize(ctx, matrix_path=matrix)
    cmd_gate(ctx)
    tud_hash = ctx._read("tud.json")["tud_hash"]
    store = Stage3QualityRecordStore(ctx.store_root)
    corr = tmp_path / "corr.parquet"
    pd.DataFrame(np.eye(2), index=["A", "B"], columns=["A", "B"]).to_parquet(corr)

    # (i) B has ONLY a FILTER record on the target -> must not qualify B for ranking selection
    store.record_quality(factor_id="B", definition_hash="def_B", layer1_methodology_hash="L1",
                         target_universe_declaration_hash=tud_hash, role="filter", quality_flags={},
                         universe_profile={}, target_universe_pass=None, cross_universe_sign_divergence=False,
                         status_effect="eligible_for_oos")
    with pytest.raises(FactorEvalError, match="eligible ranking/both"):
        cmd_select(ctx, matrix_path=matrix, pool={"A": "x", "B": "y"}, caps={"x": 1, "y": 1},
                   floor=0.10, corr_path=str(corr))

    # (ii) B now also has a RANKING record but under a STALE methodology -> still ineligible
    store.record_quality(factor_id="B", definition_hash="def_B", layer1_methodology_hash="STALE",
                         target_universe_declaration_hash=tud_hash, role="ranking", quality_flags={},
                         universe_profile={}, target_universe_pass=True, cross_universe_sign_divergence=False,
                         status_effect="eligible_for_oos")
    with pytest.raises(FactorEvalError, match="eligible ranking/both"):
        cmd_select(ctx, matrix_path=matrix, pool={"A": "x", "B": "y"}, caps={"x": 1, "y": 1},
                   floor=0.10, corr_path=str(corr))

    # (iii) B with a matching-methodology RANKING record -> now selectable
    store.record_quality(factor_id="B", definition_hash="def_B", layer1_methodology_hash="L1",
                         target_universe_declaration_hash=tud_hash, role="ranking", quality_flags={},
                         universe_profile={}, target_universe_pass=True, cross_universe_sign_divergence=False,
                         status_effect="eligible_for_oos")
    sel = cmd_select(ctx, matrix_path=matrix, pool={"A": "x", "B": "y"}, caps={"x": 1, "y": 1},
                     floor=0.10, corr_path=str(corr))
    assert set(m["factor_id"] for m in sel["members"]) <= {"A", "B"}


def test_seal_live_enforces_multiplicity_acknowledge(tmp_path, monkeypatch):
    # PR3 R5 B1: the seal store + budget ledger derive from the CONFIGURED canonical root
    # (monkeypatched here) — not a ctx field. The 5 historical seals must live there.
    import src.research_orchestrator.holdout_seal as hs_mod
    from src.research_orchestrator.holdout_seal import HoldoutSealStore
    canonical = tmp_path / "holdout"
    monkeypatch.setattr(hs_mod, "resolve_configured_global_holdout_root", lambda: canonical)
    ctx = _ctx(tmp_path)
    hs = HoldoutSealStore(canonical)
    for i in range(5):  # 5 historical seals + this pending = 6 -> warn band (warn=5)
        hs.claim_holdout_access(design_hash="d", seal_key=f"h{i}", hypothesis_id="x",
                                structural_family="f", profile_id="p", run_dir=str(tmp_path / f"r{i}"), step_id="s")
    _full_pipeline_to_select(ctx, tmp_path)
    # live hits the acknowledge band -> refused BEFORE any OOS backtest (no ack passed)
    with pytest.raises(FactorEvalError, match="acknowledgement"):
        cmd_seal(ctx, mode="live", oos_start="2021-01-01", oos_end="2026-02-27")


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
