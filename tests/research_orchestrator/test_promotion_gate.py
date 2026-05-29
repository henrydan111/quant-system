"""Promotion gate — independent PIT-correct reproduction (PIT-prevention step 11).

A strategy may be explored freely, but it cannot receive a PRIVILEGED label
(champion / deployment_candidate / live_candidate / approved) unless its signal
inputs were independently rebuilt through a PIT-correct data path. A
sandbox-loader panel is NOT sufficient.
"""
from __future__ import annotations

import pytest

from src.research_orchestrator.release_gate import (
    PRIVILEGED_PROMOTION_LABELS,
    VALID_INDEPENDENT_REPRODUCTION_SOURCES,
    PromotionGateError,
    assert_promotion_eligible,
    evaluate_promotion_eligibility,
    evaluate_promotion_from_artifact,
)


@pytest.mark.parametrize("label", sorted(PRIVILEGED_PROMOTION_LABELS))
@pytest.mark.parametrize("source", sorted(VALID_INDEPENDENT_REPRODUCTION_SOURCES))
def test_privileged_label_with_valid_source_is_eligible(label, source):
    r = evaluate_promotion_eligibility(label=label, reproduction_source=source)
    assert r.eligible and r.privileged and not r.reasons


@pytest.mark.parametrize("label", sorted(PRIVILEGED_PROMOTION_LABELS))
def test_privileged_label_without_source_fails(label):
    r = evaluate_promotion_eligibility(label=label, reproduction_source=None)
    assert not r.eligible and r.privileged
    with pytest.raises(PromotionGateError):
        assert_promotion_eligible(label=label, reproduction_source=None)


@pytest.mark.parametrize("bad", ["sandbox", "pit_research_loader", "build_pit_pivot", "", "none"])
def test_privileged_label_with_non_independent_source_fails(bad):
    r = evaluate_promotion_eligibility(label="deployment_candidate", reproduction_source=bad)
    assert not r.eligible
    with pytest.raises(PromotionGateError):
        assert_promotion_eligible(label="deployment_candidate", reproduction_source=bad)


@pytest.mark.parametrize("label", ["candidate", "research", "exploratory", "", None, "draft"])
def test_unprivileged_label_always_eligible(label):
    # Research is free — only privileged labels gate on reproduction.
    r = evaluate_promotion_eligibility(label=label, reproduction_source=None)
    assert r.eligible and not r.privileged
    assert_promotion_eligible(label=label, reproduction_source=None)  # does not raise


def test_label_normalization_case_and_whitespace():
    r = evaluate_promotion_eligibility(label="  Deployment_Candidate ", reproduction_source="qlib_windowed_features")
    assert r.privileged and r.eligible and r.label == "deployment_candidate"


def test_evaluate_from_artifact_reads_fields():
    ok = {
        "promotion_label": "champion",
        "independent_reproduction": {"source": "joinquant_native_pit", "reproduced_at": "20260530"},
    }
    assert evaluate_promotion_from_artifact(ok).eligible

    bad = {
        "promotion_label": "champion",
        "independent_reproduction": {"source": "pit_research_loader"},
    }
    assert not evaluate_promotion_from_artifact(bad).eligible

    missing_repro = {"promotion_label": "approved"}
    assert not evaluate_promotion_from_artifact(missing_repro).eligible

    exploratory = {"promotion_label": "candidate"}
    assert evaluate_promotion_from_artifact(exploratory).eligible

    assert evaluate_promotion_from_artifact(None).eligible  # no label -> unprivileged


def test_assert_returns_result_on_eligible():
    r = assert_promotion_eligible(
        label="approved", reproduction_source="audited_pit_source", artifact_label="my_strat"
    )
    assert r.eligible and r.privileged
