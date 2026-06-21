"""D5 Stage-3 reader tests for src/alpha_research/factor_eval_skill/stage3_reader.py.

Covers: status_effect via resolve_replication_ceiling (clean -> eligible_for_oos; sub
coverage -> evidence_only; missing target -> fail-closed); the explicit native/cohort
governance contract (a cohort tier caps where native would not; the cohort factory is
fail-closed); target_universe_pass via assign_candidate_status; the NEW cross-universe
flags (illiquidity_bound = the E-wave failure mode; sign-flip is diagnostic, not a block
for a small-cap target); the role split; persist round-trip; and the strict matrix loader.
"""
from __future__ import annotations

import json

import pytest

from src.alpha_research.factor_eval_skill.identity import TargetUniverseDeclaration
from src.alpha_research.factor_eval_skill.stage3_reader import (
    MatrixResults,
    Stage3GovernanceInputs,
    stage3_caps,
)
from src.alpha_research.factor_eval_skill.stores import Stage3QualityRecordStore

NATIVE = Stage3GovernanceInputs.native()


def _row(factor, universe, icir, *, sign=1.0, cov="broad", field_ok=True, eff_days=2600, l1="l1hash"):
    return {
        "factor": factor,
        "universe_id": universe,
        "heldout_rank_icir": icir,
        "mean_rank_ic": icir / 10.0,
        "sign_consistency": sign,
        "coverage_tier": cov,
        "effective_ic_days": eff_days,
        "field_eligible": field_ok,
        "layer1_methodology_hash": l1,
    }


def _tud(universe_id):
    return TargetUniverseDeclaration(
        target_universe_id=universe_id,
        universe_definition_filters={"u": universe_id},
        eligibility_policy="p",
        asof_policy="pit_lag_1",
    )


def _caps(rows, target, role, governance=NATIVE):
    return stage3_caps(MatrixResults(rows), factor_id="f", definition_hash="d",
                       tud=_tud(target), role=role, governance=governance)


# ----- status_effect: the P-GATE call -----

def test_clean_broad_factor_is_eligible_for_oos():
    rows = [_row("f", u, 0.45, cov="broad") for u in ("univ_all", "univ_csi300", "univ_liquid_top300")]
    rec = _caps(rows, "univ_liquid_top300", "ranking")
    assert rec.status_effect == "eligible_for_oos"  # no caps + all OOS gates acquired
    assert rec.target_universe_pass is True
    assert rec.layer1_methodology_hash == "l1hash"  # derived from the matrix row


def test_sub_coverage_target_caps_at_evidence_only():
    rows = [_row("f", "univ_liquid_top300", 0.45, cov="sub")]
    rec = _caps(rows, "univ_liquid_top300", "ranking")
    assert rec.status_effect == "evidence_only"  # availability_floor_fail
    assert rec.quality_flags["coverage_sub"] is True


def test_missing_target_row_is_fail_closed():
    rows = [_row("f", "univ_all", 0.45)]  # not evaluated on the declared liquid target
    rec = _caps(rows, "univ_liquid_top300", "ranking")
    assert rec.status_effect == "evidence_only"  # availability_audit_missing (coverage not observed)
    assert rec.target_universe_pass is False


# ----- explicit governance contract (the GPT cross-review primary fix) -----

def test_cohort_tier_caps_where_native_would_not():
    # the SAME clean broad row: native -> eligible_for_oos; cohort proxy_approx -> candidate_ceiling
    rows = [_row("f", "univ_liquid_top300", 0.45, cov="broad")]
    assert _caps(rows, "univ_liquid_top300", "ranking", NATIVE).status_effect == "eligible_for_oos"
    cohort = Stage3GovernanceInputs.cohort(
        replication_tier="proxy_approx", claim_class="clean_singleton_primary", oos_eligibility="pending",
    )
    assert _caps(rows, "univ_liquid_top300", "ranking", cohort).status_effect == "candidate_ceiling"


def test_cohort_factory_is_fail_closed():
    with pytest.raises(ValueError, match="manifest-resolved"):
        Stage3GovernanceInputs.cohort(replication_tier="", claim_class="c", oos_eligibility="pending")
    with pytest.raises(ValueError, match="FactorDomainClaim"):
        Stage3GovernanceInputs.cohort(replication_tier="proxy_approx", claim_class="", oos_eligibility="pending")


def test_stage3_caps_requires_governance():
    rows = [_row("f", "univ_all", 0.45)]
    with pytest.raises(TypeError):  # governance is a required keyword-only arg
        stage3_caps(MatrixResults(rows), factor_id="f", definition_hash="d", tud=_tud("univ_all"), role="ranking")


# ----- cross-universe flags (the NEW logic) -----

def test_illiquidity_bound_is_the_ewave_failure_mode():
    rows = [
        _row("f", "univ_all", 0.40),
        _row("f", "univ_microcap", 0.40),
        _row("f", "univ_liquid_top300", 0.05),  # below the 0.10 IS bar
    ]
    rec = _caps(rows, "univ_liquid_top300", "ranking")
    assert rec.quality_flags["illiquidity_bound"] is True
    assert rec.quality_flags["liquid_fail"] is True
    assert rec.target_universe_pass is False  # weak on the declared liquid target


def test_sign_flip_is_diagnostic_not_a_block_for_smallcap_target():
    rows = [
        _row("f", "univ_all", 0.30, sign=1.0),
        _row("f", "univ_csi300", -0.30, sign=1.0),   # opposite sign in CSI300
        _row("f", "univ_microcap", 0.40, sign=1.0),
        _row("f", "univ_liquid_top300", 0.06),
    ]
    rec = _caps(rows, "univ_microcap", "ranking")
    assert rec.quality_flags["sign_flip_across_core_universes"] is True
    assert rec.cross_universe_sign_divergence is True
    assert rec.target_universe_pass is True  # v1.3 §5: still passes on its declared target


def test_noise_sign_does_not_count_as_flip():
    rows = [
        _row("f", "univ_all", 0.30),
        _row("f", "univ_csi300", -0.02),  # |0.02| < SIGN_EPSILON -> indeterminate
        _row("f", "univ_liquid_top300", 0.30),
    ]
    rec = _caps(rows, "univ_liquid_top300", "ranking")
    assert rec.quality_flags["sign_flip_across_core_universes"] is False


# ----- role split -----

def test_filter_role_has_no_ic_pass():
    rec = _caps([_row("f", "univ_all", 0.45)], "univ_all", "filter")
    assert rec.target_universe_pass is None  # IC bar N/A to a filter
    assert rec.filter_component["ic_bar_applicable"] is False


def test_both_role_has_separate_components():
    rec = _caps([_row("f", "univ_liquid_top300", 0.45)], "univ_liquid_top300", "both")
    assert rec.ranking_component is not None and rec.ranking_component["target_universe_pass"] is True
    assert rec.filter_component is not None


def test_bad_role_raises():
    with pytest.raises(ValueError, match="role must be one of"):
        _caps([_row("f", "univ_all", 0.45)], "univ_all", "nonsense")


# ----- persist round-trip -----

def test_persist_roundtrip_ranking(tmp_path):
    rec = _caps([_row("f", "univ_liquid_top300", 0.45, cov="broad")], "univ_liquid_top300", "ranking")
    store = Stage3QualityRecordStore(tmp_path)
    rec.persist(store)
    got = store.latest(
        factor_id="f", definition_hash="d", layer1_methodology_hash="l1hash",
        target_universe_declaration_hash=rec.target_universe_declaration_hash, role="ranking",
    )
    assert got is not None
    assert got["status_effect"] == "eligible_for_oos"
    assert got["target_universe_pass"] == "True"


def test_persist_filter_stores_na(tmp_path):
    rec = _caps([_row("f", "univ_all", 0.45)], "univ_all", "filter")
    store = Stage3QualityRecordStore(tmp_path)
    rec.persist(store)
    got = store.latest(
        factor_id="f", definition_hash="d", layer1_methodology_hash="l1hash",
        target_universe_declaration_hash=rec.target_universe_declaration_hash, role="filter",
    )
    assert got["target_universe_pass"] == "na"  # filter -> N/A, not False


def test_ranking_and_filter_records_coexist(tmp_path):
    # role is part of the key -> a filter record must not shadow a ranking record
    store = Stage3QualityRecordStore(tmp_path)
    _caps([_row("f", "univ_all", 0.45)], "univ_all", "ranking").persist(store)
    _caps([_row("f", "univ_all", 0.45)], "univ_all", "filter").persist(store)
    assert len(store.list_all()) == 2


# ----- loader -----

def test_from_jsonl_roundtrip(tmp_path):
    p = tmp_path / "results.jsonl"
    p.write_text("\n".join(json.dumps(_row("f", u, 0.3)) for u in ("univ_all", "univ_csi300")), encoding="utf-8")
    matrix = MatrixResults.from_jsonl(p)
    assert matrix.has_factor("f")
    assert set(matrix.universe_rows("f")) == {"univ_all", "univ_csi300"}


def test_strict_loader_rejects_malformed_rows():
    # duplicate factor x universe
    with pytest.raises(ValueError, match="duplicate"):
        MatrixResults([_row("f", "univ_all", 0.3), _row("f", "univ_all", 0.4)], strict=True)
    # row carrying an error
    bad = _row("f", "univ_all", 0.3)
    bad["error"] = "compute failed"
    with pytest.raises(ValueError, match="error"):
        MatrixResults([bad], strict=True)
    # missing layer1_methodology_hash
    nol1 = _row("f", "univ_all", 0.3)
    nol1.pop("layer1_methodology_hash")
    with pytest.raises(ValueError, match="layer1_methodology_hash"):
        MatrixResults([nol1], strict=True)
    # unknown universe
    with pytest.raises(ValueError, match="unknown universe_id"):
        MatrixResults([_row("f", "univ_bogus", 0.3)], strict=True)
    # lenient mode tolerates them
    MatrixResults([_row("f", "univ_all", 0.3), _row("f", "univ_all", 0.4)], strict=False)
