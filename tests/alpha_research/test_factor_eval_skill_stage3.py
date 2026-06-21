"""D5 Stage-3 reader tests for src/alpha_research/factor_eval_skill/stage3_reader.py.

Covers: status_effect via resolve_replication_ceiling (clean -> eligible_for_oos; sub
coverage -> evidence_only; missing target -> fail-closed); target_universe_pass via
assign_candidate_status; the NEW cross-universe flags (illiquidity_bound = the E-wave
failure mode; sign-flip is diagnostic and does NOT block a small-cap-target factor);
the role split (ranking / filter N-A / both); and persist round-trip.
"""
from __future__ import annotations

import pytest

from src.alpha_research.factor_eval_skill.identity import TargetUniverseDeclaration
from src.alpha_research.factor_eval_skill.stage3_reader import (
    MatrixResults,
    stage3_caps,
)
from src.alpha_research.factor_eval_skill.stores import Stage3QualityRecordStore


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


# ----- status_effect: the P-GATE call -----

def test_clean_broad_factor_is_eligible_for_oos():
    rows = [_row("f", u, 0.45, cov="broad") for u in ("univ_all", "univ_csi300", "univ_liquid_top300")]
    rec = stage3_caps(MatrixResults(rows), factor_id="f", definition_hash="d",
                      tud=_tud("univ_liquid_top300"), role="ranking")
    assert rec.status_effect == "eligible_for_oos"  # no caps + all OOS gates acquired
    assert rec.target_universe_pass is True
    assert rec.layer1_methodology_hash == "l1hash"  # derived from the matrix row


def test_sub_coverage_target_caps_at_evidence_only():
    rows = [_row("f", "univ_liquid_top300", 0.45, cov="sub")]
    rec = stage3_caps(MatrixResults(rows), factor_id="f", definition_hash="d",
                      tud=_tud("univ_liquid_top300"), role="ranking")
    assert rec.status_effect == "evidence_only"  # availability_floor_fail
    assert rec.quality_flags["coverage_sub"] is True


def test_missing_target_row_is_fail_closed():
    # factor evaluated on univ_all but NOT on the declared liquid target
    rows = [_row("f", "univ_all", 0.45)]
    rec = stage3_caps(MatrixResults(rows), factor_id="f", definition_hash="d",
                      tud=_tud("univ_liquid_top300"), role="ranking")
    assert rec.status_effect == "evidence_only"  # availability_audit_missing (coverage not observed)
    assert rec.target_universe_pass is False


# ----- cross-universe flags (the NEW logic) -----

def test_illiquidity_bound_is_the_ewave_failure_mode():
    # strong on microcap, collapses on liquid -> the exact E-wave deployment failure
    rows = [
        _row("f", "univ_all", 0.40),
        _row("f", "univ_microcap", 0.40),
        _row("f", "univ_liquid_top300", 0.05),  # below the 0.10 IS bar
    ]
    rec = stage3_caps(MatrixResults(rows), factor_id="f", definition_hash="d",
                      tud=_tud("univ_liquid_top300"), role="ranking")
    assert rec.quality_flags["illiquidity_bound"] is True
    assert rec.quality_flags["liquid_fail"] is True
    assert rec.target_universe_pass is False  # weak on the declared liquid target


def test_sign_flip_is_diagnostic_not_a_block_for_smallcap_target():
    # flips sign across the broad core universes, but is strong on its declared microcap target
    rows = [
        _row("f", "univ_all", 0.30, sign=1.0),
        _row("f", "univ_csi300", -0.30, sign=1.0),   # opposite sign in CSI300
        _row("f", "univ_microcap", 0.40, sign=1.0),
        _row("f", "univ_liquid_top300", 0.06),
    ]
    rec = stage3_caps(MatrixResults(rows), factor_id="f", definition_hash="d",
                      tud=_tud("univ_microcap"), role="ranking")
    assert rec.quality_flags["sign_flip_across_core_universes"] is True
    assert rec.cross_universe_sign_divergence is True
    # v1.3 §5: the flip is DIAGNOSTIC — the factor still PASSES on its declared target
    assert rec.target_universe_pass is True


def test_noise_sign_does_not_count_as_flip():
    # tiny |icir| in one core universe is noise, not a determinate opposite sign
    rows = [
        _row("f", "univ_all", 0.30),
        _row("f", "univ_csi300", -0.02),  # |0.02| < SIGN_EPSILON -> indeterminate
        _row("f", "univ_liquid_top300", 0.30),
    ]
    rec = stage3_caps(MatrixResults(rows), factor_id="f", definition_hash="d",
                      tud=_tud("univ_liquid_top300"), role="ranking")
    assert rec.quality_flags["sign_flip_across_core_universes"] is False


# ----- role split -----

def test_filter_role_has_no_ic_pass():
    rows = [_row("f", "univ_all", 0.45)]
    rec = stage3_caps(MatrixResults(rows), factor_id="f", definition_hash="d",
                      tud=_tud("univ_all"), role="filter")
    assert rec.target_universe_pass is None  # IC bar N/A to a filter
    assert rec.filter_component["ic_bar_applicable"] is False


def test_both_role_has_separate_components():
    rows = [_row("f", "univ_liquid_top300", 0.45)]
    rec = stage3_caps(MatrixResults(rows), factor_id="f", definition_hash="d",
                      tud=_tud("univ_liquid_top300"), role="both")
    assert rec.ranking_component is not None and rec.ranking_component["target_universe_pass"] is True
    assert rec.filter_component is not None


def test_bad_role_raises():
    rows = [_row("f", "univ_all", 0.45)]
    with pytest.raises(ValueError, match="role must be one of"):
        stage3_caps(MatrixResults(rows), factor_id="f", definition_hash="d",
                    tud=_tud("univ_all"), role="nonsense")


# ----- persist round-trip -----

def test_persist_roundtrip_ranking(tmp_path):
    rows = [_row("f", "univ_liquid_top300", 0.45, cov="broad")]
    rec = stage3_caps(MatrixResults(rows), factor_id="f", definition_hash="d",
                      tud=_tud("univ_liquid_top300"), role="ranking")
    store = Stage3QualityRecordStore(tmp_path)
    rec.persist(store)
    got = store.latest(
        factor_id="f", definition_hash="d", layer1_methodology_hash="l1hash",
        target_universe_declaration_hash=rec.target_universe_declaration_hash,
    )
    assert got is not None
    assert got["status_effect"] == "eligible_for_oos"
    assert got["target_universe_pass"] == "True"


def test_persist_filter_stores_na(tmp_path):
    rows = [_row("f", "univ_all", 0.45)]
    rec = stage3_caps(MatrixResults(rows), factor_id="f", definition_hash="d",
                      tud=_tud("univ_all"), role="filter")
    store = Stage3QualityRecordStore(tmp_path)
    rec.persist(store)
    got = store.latest(
        factor_id="f", definition_hash="d", layer1_methodology_hash="l1hash",
        target_universe_declaration_hash=rec.target_universe_declaration_hash,
    )
    assert got["target_universe_pass"] == "na"  # filter -> N/A, not False


# ----- loader -----

def test_from_jsonl_roundtrip(tmp_path):
    import json
    p = tmp_path / "results.jsonl"
    p.write_text("\n".join(json.dumps(_row("f", u, 0.3)) for u in ("univ_all", "univ_csi300")), encoding="utf-8")
    matrix = MatrixResults.from_jsonl(p)
    assert matrix.has_factor("f")
    assert set(matrix.universe_rows("f")) == {"univ_all", "univ_csi300"}
