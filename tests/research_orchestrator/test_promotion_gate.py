"""Promotion gate — independent PIT-correct reproduction (PIT-prevention step 11).

A strategy may be explored freely, but it cannot receive a PRIVILEGED registry
status ("approved") or promotion label (champion / deployment_candidate /
live_candidate) unless its signal inputs were independently rebuilt through a
PIT-correct data path. A sandbox-loader panel is NOT sufficient. The
StrategyRegistryStore.set_status transition enforces this (not just a helper).
"""
from __future__ import annotations

import pytest

from src.research_orchestrator.registries import StrategyRegistryStore
from src.research_orchestrator.release_gate import (
    PRIVILEGED_PROMOTION_LABELS,
    PRIVILEGED_REGISTRY_STATUSES,
    VALID_INDEPENDENT_REPRODUCTION_SOURCES,
    PromotionGateError,
    assert_promotion_eligible,
    evaluate_promotion_artifact,
    evaluate_promotion_eligibility,
)

_FULL_OK = {
    "independent_reproduction": {"source": "qlib_windowed_features"},
    "unsafe_pit_dates_lint": "passed",
    "live_provider_parity": "passed",
}


# ── core source-level check ─────────────────────────────────────────────
@pytest.mark.parametrize("label", sorted(PRIVILEGED_PROMOTION_LABELS))
@pytest.mark.parametrize("source", sorted(VALID_INDEPENDENT_REPRODUCTION_SOURCES - {"audited_pit_source"}))
def test_privileged_label_with_valid_source_eligible(label, source):
    r = evaluate_promotion_eligibility(label=label, reproduction_source=source)
    assert r.eligible and r.privileged


def test_privileged_status_approved_gated():
    assert evaluate_promotion_eligibility(status="approved", reproduction_source="qlib_windowed_features").eligible
    assert not evaluate_promotion_eligibility(status="approved", reproduction_source=None).eligible
    assert not evaluate_promotion_eligibility(status="approved", reproduction_source="pit_research_loader").eligible


@pytest.mark.parametrize("bad", ["sandbox", "pit_research_loader", "build_pit_pivot", "", "none"])
def test_non_independent_source_fails(bad):
    assert not evaluate_promotion_eligibility(label="champion", reproduction_source=bad).eligible
    with pytest.raises(PromotionGateError):
        assert_promotion_eligible(label="champion", reproduction_source=bad)


@pytest.mark.parametrize("s_or_l", [{"label": "candidate"}, {"status": "under_review"}, {"label": None}, {"status": "rejected"}])
def test_unprivileged_always_eligible(s_or_l):
    r = evaluate_promotion_eligibility(reproduction_source=None, **s_or_l)
    assert r.eligible and not r.privileged


def test_audited_source_requires_named_evidence():
    # bare magic string is insufficient
    assert not evaluate_promotion_eligibility(
        status="approved", reproduction_source="audited_pit_source"
    ).eligible
    # with source_name + audit_artifact -> eligible
    r = evaluate_promotion_eligibility(
        status="approved", reproduction_source="audited_pit_source",
        reproduction_evidence={"source_name": "vendorX_pit", "audit_artifact": "audits/x.json"},
    )
    assert r.eligible


# ── full artifact evaluator ─────────────────────────────────────────────
def test_artifact_requires_lint_and_parity():
    base = {"promotion_status": "approved", "independent_reproduction": {"source": "qlib_windowed_features"}}
    # missing lint + parity -> ineligible
    assert not evaluate_promotion_artifact(base).eligible
    # full -> eligible
    assert evaluate_promotion_artifact({**base, "unsafe_pit_dates_lint": "passed", "live_provider_parity": "passed"}).eligible


def test_artifact_parity_not_required_only_without_loader():
    art = {
        "promotion_label": "deployment_candidate",
        "independent_reproduction": {"source": "joinquant_native_pit"},
        "unsafe_pit_dates_lint": "passed",
        "live_provider_parity": "not_required_for_label",
    }
    assert evaluate_promotion_artifact(art).eligible  # no loader used -> legal
    art["primary_used_pit_research_loader"] = True
    assert not evaluate_promotion_artifact(art).eligible  # loader used -> illegal


def test_artifact_dirty_tree_and_git_sha():
    art = {**_FULL_OK, "promotion_status": "approved", "git_sha": "abc123", "dirty_tree": False}
    assert evaluate_promotion_artifact(art, current_git_sha="abc123").eligible
    assert not evaluate_promotion_artifact(art, current_git_sha="def456").eligible  # sha mismatch
    assert not evaluate_promotion_artifact({**art, "dirty_tree": True}, current_git_sha="abc123").eligible


def test_artifact_failed_canary_blocks():
    art = {**_FULL_OK, "promotion_status": "approved", "q0_canary": "FAILED"}
    assert not evaluate_promotion_artifact(art).eligible


# ── enforced registry transition (the real call site) ───────────────────
def test_strategy_set_status_approved_blocked_without_evidence(tmp_path):
    store = StrategyRegistryStore(tmp_path)
    # gate fires BEFORE the object lookup, so a missing object still raises the gate error
    with pytest.raises(PromotionGateError):
        store.set_status(object_id="s1", status="approved", reason="promote")
    with pytest.raises(PromotionGateError):
        store.set_status(object_id="s1", status="approved", reason="promote",
                         promotion_evidence={"independent_reproduction": {"source": "pit_research_loader"}})


def test_strategy_set_status_approved_passes_gate_with_evidence(tmp_path):
    store = StrategyRegistryStore(tmp_path)
    # valid evidence -> gate passes -> KeyError for the (absent) object proves we got PAST the gate
    with pytest.raises(KeyError):
        store.set_status(object_id="missing", status="approved", reason="promote", promotion_evidence=_FULL_OK)


def test_strategy_set_status_nonprivileged_not_gated(tmp_path):
    store = StrategyRegistryStore(tmp_path)
    # a non-privileged status is NOT gated -> proceeds to lookup -> KeyError (not PromotionGateError)
    with pytest.raises(KeyError):
        store.set_status(object_id="missing", status="rejected", reason="reject")
