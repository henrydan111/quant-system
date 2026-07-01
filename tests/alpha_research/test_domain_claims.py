"""Tests for FactorDomainClaim + TaintLedger + claim-class resolver (Draft-7)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.alpha_research.factor_registry.domain_claims import (  # noqa: E402
    DomainClaimStore,
)


@pytest.fixture
def store(tmp_path):
    return DomainClaimStore(base_dir=tmp_path)


class TestTaintLedger:
    def test_record_and_query(self, store):
        eid = store.record_taint(source_type="exploratory_eval", factor_id="f1",
                                 universe_id="univ_microcap")
        t = store.taints_for("f1", universe_id="univ_microcap")
        assert len(t) == 1 and t.iloc[0]["entry_id"] == eid
        assert t.iloc[0]["taint_effect"] == "post_hoc_max_stat"

    def test_family_taint_reaches_other_factors(self, store):
        store.record_taint(source_type="idea_family", research_family_id="fam_rev",
                           universe_id="univ_microcap")
        t = store.taints_for("f_new", research_family_id="fam_rev",
                             universe_id="univ_microcap")
        assert len(t) == 1

    def test_invalid_inputs_raise(self, store):
        with pytest.raises(ValueError, match="source_type"):
            store.record_taint(source_type="nope", factor_id="f", universe_id="u")
        with pytest.raises(ValueError, match="needs factor_id"):
            store.record_taint(source_type="lineage", universe_id="u")


class TestResolveClaimClass:
    def test_clean_singleton(self, store):
        d = store.resolve_claim_class(factor_id="f1", universe_id="univ_all",
                                      pre_registered_at="2026-06-01T00:00:00Z")
        assert d.claim_class == "clean_singleton_primary"

    def test_prior_taint_downgrades_mechanically(self, store):
        store.record_taint(source_type="exploratory_eval", factor_id="f1",
                           universe_id="univ_microcap")
        d = store.resolve_claim_class(factor_id="f1", universe_id="univ_microcap",
                                      pre_registered_at="2099-01-01T00:00:00Z")
        assert d.claim_class == "tainted_post_hoc_max_stat"
        assert d.taint_entry_ids  # the driving ledger rows are cited

    def test_taint_after_declaration_does_not_downgrade(self, store):
        store.record_taint(source_type="non_primary_formal_evidence", factor_id="f1",
                           universe_id="univ_csi300")
        # declaration BEFORE the observation timestamp -> clean
        d = store.resolve_claim_class(factor_id="f1", universe_id="univ_csi300",
                                      pre_registered_at="2000-01-01T00:00:00Z")
        assert d.claim_class == "clean_singleton_primary"

    def test_override_is_audited(self, store):
        store.record_taint(source_type="idea_family", research_family_id="fam",
                           universe_id="univ_growth")
        d = store.resolve_claim_class(factor_id="f2", research_family_id="fam",
                                      universe_id="univ_growth",
                                      pre_registered_at="2099-01-01T00:00:00Z",
                                      override_reason="external prior doc 2026-05-01")
        assert d.claim_class == "clean_singleton_primary" and d.override_applied
        audit = store.taints()
        assert (audit["source_type"] == "manual_override").any()

    def test_block_taint_forces_evidence_only(self, store):
        store.record_taint(source_type="manual_override", factor_id="f3",
                           universe_id="univ_microcap", taint_effect="block_status_claim")
        d = store.resolve_claim_class(factor_id="f3", universe_id="univ_microcap",
                                      pre_registered_at="2000-01-01T00:00:00Z")
        assert d.claim_class == "evidence_only_not_status_bearing"

    def test_multi_domain_declaration(self, store):
        d = store.resolve_claim_class(factor_id="f4", universe_id="univ_csi500",
                                      pre_registered_at="2026-01-01T00:00:00Z",
                                      declared_domain_count=3)
        assert d.claim_class == "predeclared_multi_domain"


class TestClaims:
    def test_register_and_status_ladder(self, store):
        cid = store.register_claim(factor_id="f1", universe_id="univ_all")
        claims = store.claims()
        assert claims.iloc[0]["status"] == "draft_claim"
        assert claims.iloc[0]["claim_class"] == "clean_singleton_primary"
        store.set_claim_status(cid, "candidate_claim", gate_evidence_id="ev1")
        store.set_claim_status(cid, "approved_claim", sealed_oos_id="seal1")
        assert store.oos_validated_domains("f1") == ["univ_all"]

    def test_duplicate_active_claim_rejected(self, store):
        store.register_claim(factor_id="f1", universe_id="univ_all")
        with pytest.raises(ValueError, match="already exists"):
            store.register_claim(factor_id="f1", universe_id="univ_all")

    def test_evidence_only_claim_cannot_bear_status(self, store):
        store.record_taint(source_type="manual_override", factor_id="f5",
                           universe_id="univ_microcap", taint_effect="block_status_claim")
        cid = store.register_claim(factor_id="f5", universe_id="univ_microcap")
        with pytest.raises(ValueError, match="evidence_only"):
            store.set_claim_status(cid, "candidate_claim")

    def test_tainted_registration_records_class(self, store):
        store.record_taint(source_type="exploratory_eval", factor_id="f6",
                           universe_id="univ_growth")
        cid = store.register_claim(factor_id="f6", universe_id="univ_growth")
        row = store.claims().set_index("claim_id").loc[cid]
        assert row["claim_class"] == "tainted_post_hoc_max_stat"

    def test_production_scope_only_approved(self, store):
        c1 = store.register_claim(factor_id="f7", universe_id="univ_all")
        store.register_claim(factor_id="f7", universe_id="univ_csi300")
        store.set_claim_status(c1, "candidate_claim")
        # candidate is NOT production scope
        assert store.oos_validated_domains("f7") == []
        store.set_claim_status(c1, "approved_claim")
        assert store.oos_validated_domains("f7") == ["univ_all"]
