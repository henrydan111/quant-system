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
    "synthetic_lookahead_canary": "passed",
    "restatement_canary": "passed",
    "q0_canary_multiperiod": "passed",
    "q0_canary_stateful_restatement": "passed",
    "q0_canary_missing_field": "passed",
    "availability_assertion": "passed",
    "live_provider_parity": "passed",
    "dirty_tree": False,
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


# ── full artifact evaluator (fail-closed on MISSING evidence) ────────────
def test_artifact_full_set_eligible():
    assert evaluate_promotion_artifact({**_FULL_OK, "promotion_status": "approved"}).eligible


def test_artifact_missing_lint_or_parity_blocks():
    base = {"promotion_status": "approved", "independent_reproduction": {"source": "qlib_windowed_features"}}
    assert not evaluate_promotion_artifact(base).eligible  # missing everything


def test_artifact_missing_required_canary_blocks():
    # A privileged artifact that OMITS a required canary fails (fail-closed).
    for drop in ("synthetic_lookahead_canary", "restatement_canary",
                 "q0_canary_stateful_restatement", "availability_assertion"):
        art = {k: v for k, v in _FULL_OK.items() if k != drop}
        art["promotion_status"] = "approved"
        assert not evaluate_promotion_artifact(art).eligible, f"omitting {drop} should fail"


def test_artifact_parity_not_required_only_without_loader():
    art = {**_FULL_OK, "promotion_label": "deployment_candidate",
           "independent_reproduction": {"source": "joinquant_native_pit"},
           "live_provider_parity": "not_required_for_label"}
    assert evaluate_promotion_artifact(art).eligible  # no loader -> legal
    assert not evaluate_promotion_artifact({**art, "primary_used_pit_research_loader": True}).eligible
    assert not evaluate_promotion_artifact({**art, "reproduction_used_pit_research_loader": True}).eligible
    assert not evaluate_promotion_artifact(
        {**art, "independent_reproduction": {"source": "joinquant_native_pit", "used_pit_research_loader": True}}
    ).eligible


def test_artifact_dirty_tree_fail_closed():
    art = {**_FULL_OK, "promotion_status": "approved"}
    assert evaluate_promotion_artifact(art).eligible            # dirty_tree=False present
    assert not evaluate_promotion_artifact({**art, "dirty_tree": True}).eligible
    no_dirty = {k: v for k, v in art.items() if k != "dirty_tree"}
    assert not evaluate_promotion_artifact(no_dirty).eligible   # MISSING dirty_tree -> fail-closed


def test_artifact_git_sha_fail_closed():
    art = {**_FULL_OK, "promotion_status": "approved", "git_sha": "abc123"}
    assert evaluate_promotion_artifact(art, current_git_sha="abc123").eligible
    assert not evaluate_promotion_artifact(art, current_git_sha="def456").eligible  # mismatch
    no_sha = {k: v for k, v in art.items() if k != "git_sha"}
    assert not evaluate_promotion_artifact(no_sha, current_git_sha="abc123").eligible  # missing when required
    assert evaluate_promotion_artifact(no_sha).eligible  # no current_git_sha supplied -> not required


def test_artifact_failed_canary_blocks():
    art = {**_FULL_OK, "promotion_status": "approved", "q0_canary_missing_field": "FAILED"}
    assert not evaluate_promotion_artifact(art).eligible


# ── enforced registry transition (the real call site) ───────────────────
_FULL_OK_SHA = {**_FULL_OK, "git_sha": "abc123"}


def test_strategy_set_status_approved_requires_current_git_sha(tmp_path):
    # Even with full passing evidence, omitting current_git_sha must FAIL —
    # the approval must be bound to a committed HEAD (GPT round-3).
    store = StrategyRegistryStore(tmp_path)
    with pytest.raises(PromotionGateError):
        store.set_status(object_id="missing", status="approved", reason="promote",
                         promotion_evidence=_FULL_OK_SHA)  # current_git_sha omitted


def test_strategy_set_status_approved_blocked_without_evidence(tmp_path):
    store = StrategyRegistryStore(tmp_path)
    # gate fires BEFORE the object lookup, so a missing object still raises the gate error
    with pytest.raises(PromotionGateError):
        store.set_status(object_id="s1", status="approved", reason="promote", current_git_sha="abc123")
    with pytest.raises(PromotionGateError):
        store.set_status(object_id="s1", status="approved", reason="promote", current_git_sha="abc123",
                         promotion_evidence={"independent_reproduction": {"source": "pit_research_loader"}})


def test_strategy_set_status_approved_cannot_be_bypassed_via_evidence_status(tmp_path):
    # GPT cross-review P0 (strategy mirror of the factor-registry bypass): a
    # caller-supplied promotion_status="draft" must NOT downgrade the gate to
    # non-privileged. set_status force-overwrites promotion_status=status, so the
    # malicious evidence still hits the full gate -> PromotionGateError (NOT the
    # KeyError that a passed gate would raise on the absent object).
    store = StrategyRegistryStore(tmp_path)
    with pytest.raises(PromotionGateError):
        store.set_status(object_id="missing", status="approved", reason="promote",
                         promotion_evidence={"promotion_status": "draft"}, current_git_sha="abc123")


def test_strategy_set_status_approved_p11_alone_refused_under_v14(tmp_path):
    # v1.4 A8 (PR3): the P1.1 artifact gate is NECESSARY but no longer sufficient — a
    # strategy approval must additionally be wired to the ONE book sealed-evaluation
    # artifact. A P1.1-valid artifact with a matching SHA now refuses at the BOOK layer
    # (proving it got PAST the P1.1 layer): first for the missing holdout store, then —
    # with a store supplied — for the missing book_seal section. The full valid pass-path
    # is pinned end-to-end in tests/alpha_research/test_pr3_book_seal.py
    # (TestStrategyPromotionWiring::test_publish_and_full_valid_promotion).
    store = StrategyRegistryStore(tmp_path)
    with pytest.raises(PromotionGateError, match="holdout_seal_dir"):
        store.set_status(object_id="missing", status="approved", reason="promote",
                         promotion_evidence=_FULL_OK_SHA, current_git_sha="abc123")
    with pytest.raises(PromotionGateError, match="book_seal"):
        store.set_status(object_id="missing", status="approved", reason="promote",
                         promotion_evidence=_FULL_OK_SHA, current_git_sha="abc123",
                         holdout_seal_dir=tmp_path / "seals")


def test_strategy_set_status_approved_sha_mismatch_blocked(tmp_path):
    store = StrategyRegistryStore(tmp_path)
    with pytest.raises(PromotionGateError):
        store.set_status(object_id="missing", status="approved", reason="promote",
                         promotion_evidence=_FULL_OK_SHA, current_git_sha="def456")


def test_strategy_set_status_nonprivileged_not_gated(tmp_path):
    store = StrategyRegistryStore(tmp_path)
    # a non-privileged status is NOT gated (no current_git_sha needed) -> lookup -> KeyError
    with pytest.raises(KeyError):
        store.set_status(object_id="missing", status="rejected", reason="reject")
