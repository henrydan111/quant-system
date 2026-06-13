"""Tests for the CICC replication governance skeleton (roadmap Rev5 §9/§12).

Covers the deterministic status-ceiling lattice (every level + strict-wins precedence
+ the §11.1b orientation_undetermined fail-closed), the frozen cohort manifest
(load/sha-verify/denominator freeze), the §9.3 OOS-quarantine arithmetic, the §9.2
pass-rate three-denominator guard, and the ReplicationGovernanceRecord store roundtrip
+ idempotency.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.alpha_research.factor_registry.replication_governance import (
    APPROVED_GATES,
    OOS_ELIGIBLE_GATES,
    CohortManifest,
    ReplicationGovernanceStore,
    cohort_pass_rate,
    compute_oos_quarantine_start,
    load_cohort_manifest,
    resolve_status_ceiling,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST = _PROJECT_ROOT / "config" / "replication" / "cicc_fundamental_cohort_v1.yaml"


# --------------------------------------------------------------------------- #
# 1. the deterministic lattice (§12.4)
# --------------------------------------------------------------------------- #
class TestStatusCeilingLattice:
    def test_no_caps_no_gates_sits_at_candidate(self):
        d = resolve_status_ceiling([])
        assert d.status_ceiling == "candidate_ceiling"
        assert d.blocking_reasons == ()
        # the OOS gates are what it must acquire to advance
        assert set(d.nonblocking_missing_certs) == set(OOS_ELIGIBLE_GATES)

    @pytest.mark.parametrize("reason,expected", [
        ("non_pit_data_provider", "blocked"),
        ("uncertified_operator", "blocked"),
        ("operator_experimental", "dev_evidence_only"),
        ("truth_table_unreviewed", "dev_evidence_only"),
        ("availability_floor_fail", "evidence_only"),
        ("insufficient_cross_sections", "evidence_only"),
        ("proxy_approx", "candidate_ceiling"),
        ("short_oos_power_floor_fail", "candidate_ceiling"),
    ])
    def test_each_cap_maps_to_its_level(self, reason, expected):
        d = resolve_status_ceiling([reason])
        assert d.status_ceiling == expected
        assert reason in d.blocking_reasons

    def test_strictest_cap_wins(self):
        # a blocked cap + a candidate cap → blocked (strictest), and only the
        # strictest level's reasons are surfaced as blocking.
        d = resolve_status_ceiling(["proxy_approx", "uncertified_operator", "availability_floor_fail"])
        assert d.status_ceiling == "blocked"
        assert d.blocking_reasons == ("uncertified_operator",)

    def test_oos_eligible_when_all_oos_gates_met(self):
        d = resolve_status_ceiling([], oos_eligible_gates_met=OOS_ELIGIBLE_GATES)
        assert d.status_ceiling == "eligible_for_oos"
        assert set(d.nonblocking_missing_certs) == set(APPROVED_GATES)

    def test_approved_when_all_gates_met(self):
        d = resolve_status_ceiling(
            [], oos_eligible_gates_met=OOS_ELIGIBLE_GATES, approved_gates_met=APPROVED_GATES)
        assert d.status_ceiling == "eligible_for_approved"
        assert d.blocking_reasons == () and d.nonblocking_missing_certs == ()

    def test_partial_oos_gates_still_candidate(self):
        d = resolve_status_ceiling([], oos_eligible_gates_met=["certified_operator", "coverage_pass"])
        assert d.status_ceiling == "candidate_ceiling"
        assert "denominator_frozen" in d.nonblocking_missing_certs
        assert "clean_or_calibrated_claim" in d.nonblocking_missing_certs

    def test_cap_dominates_even_when_gates_met(self):
        # a hard cap caps the claim regardless of how many positive gates are acquired.
        d = resolve_status_ceiling(
            ["derived_methodology_proxy"],
            oos_eligible_gates_met=OOS_ELIGIBLE_GATES, approved_gates_met=APPROVED_GATES)
        assert d.status_ceiling == "candidate_ceiling"
        assert "derived_methodology_proxy" in d.blocking_reasons

    # §11.1b — orientation_undetermined is NOT a ceiling cap: a weak signal is not disqualified.
    def test_orientation_undetermined_fail_closed(self):
        with pytest.raises(ValueError, match="NON_CEILING_FLAGS"):
            resolve_status_ceiling(["orientation_undetermined"])

    def test_unknown_reason_fail_closed(self):
        with pytest.raises(ValueError, match="unknown cap reason"):
            resolve_status_ceiling(["totally_made_up_reason"])


# --------------------------------------------------------------------------- #
# 2. OOS quarantine from truth-table observation (§9.3)
# --------------------------------------------------------------------------- #
class TestOosQuarantine:
    def test_truth_label_pushes_past_system_start(self):
        q, approx = compute_oos_quarantine_start("2022-07-31", "2021-01-01")
        assert q > "2022-07-31"      # label end + horizon + embargo
        assert approx is True         # calendar-day fallback (no calendar injected)

    def test_blank_truth_label_is_system_start(self):
        q, approx = compute_oos_quarantine_start("", "2021-01-01")
        assert q == "2021-01-01" and approx is False

    def test_system_start_wins_when_later(self):
        q, _ = compute_oos_quarantine_start("2015-01-01", "2021-01-01")
        assert q == "2021-01-01"      # max(...) keeps the later system OOS start

    def test_injected_calendar_is_exact(self):
        cal = [f"2022-08-{d:02d}" for d in range(1, 29)]  # 28 synthetic trading days
        q, approx = compute_oos_quarantine_start(
            "2022-07-31", "2021-01-01", horizon_trading_days=20, embargo_trading_days=5, trade_calendar=cal)
        # 20 + 5 = 25th trading day after the label end
        assert q == cal[24] and approx is False


# --------------------------------------------------------------------------- #
# 3. cohort manifest freeze + sha (§9.1/§9.2)
# --------------------------------------------------------------------------- #
class TestCohortManifest:
    def test_live_fundamental_manifest_loads_and_freezes(self):
        m = load_cohort_manifest(_MANIFEST)
        assert m.source_cohort_id == "cicc_fundamental_handbook_v1"
        # frozen denominators present (§9.2)
        for d in ("source", "daily_replicability", "formalization_candidate"):
            assert d in m.denominators
        # formalization_candidate denominator == the enumerated rows (internal consistency)
        assert m.denominators["formalization_candidate"] == len(m.factor_rows)
        # sha is content-addressed and stable
        assert m.manifest_sha and len(m.manifest_sha) == 16

    def test_sha_mismatch_raises(self, tmp_path):
        good = load_cohort_manifest(_MANIFEST)
        text = _MANIFEST.read_text(encoding="utf-8").replace(
            'manifest_sha: "%s"' % good.manifest_sha, 'manifest_sha: "deadbeefdeadbeef"')
        p = tmp_path / "tampered.yaml"
        p.write_text(text, encoding="utf-8")
        with pytest.raises(ValueError, match="manifest_sha mismatch"):
            load_cohort_manifest(p)

    def test_editing_a_row_changes_sha(self, tmp_path):
        good = load_cohort_manifest(_MANIFEST)
        # drop the declared sha so the loader recomputes without verifying, then mutate a row
        text = _MANIFEST.read_text(encoding="utf-8")
        import re
        text = re.sub(r'manifest_sha:.*\n', "", text)   # strip whole line incl trailing comment
        text = text.replace("oos_eligibility: short_window", "oos_eligibility: eligible", 1)
        p = tmp_path / "edited.yaml"
        p.write_text(text, encoding="utf-8")
        edited = load_cohort_manifest(p)
        assert edited.manifest_sha != good.manifest_sha   # content change is detectable

    def test_missing_frozen_denominator_raises(self):
        with pytest.raises(ValueError, match="freeze denominators"):
            CohortManifest(source_cohort_id="x", handbook_label_window_end="2022-12-31",
                           denominators={"source": 10}, factor_rows=[])

    def test_pass_rate_requires_three_denominators(self):
        m = load_cohort_manifest(_MANIFEST)
        pr = cohort_pass_rate(m, n_exact_oos_eligible=3, n_sealed_attempt=2, n_passed=1)
        for k in ("formalization_candidate", "exact_oos_eligible", "sealed_attempt"):
            assert k in pr and pr[k] is not None
        assert "note" in pr   # the "bare fraction is invalid" reminder


# --------------------------------------------------------------------------- #
# 4. ReplicationGovernanceRecord store (§12.3)
# --------------------------------------------------------------------------- #
class TestGovernanceStore:
    def test_upsert_resolves_ceiling_and_persists(self, tmp_path):
        s = ReplicationGovernanceStore(tmp_path)
        rec = s.upsert(
            cohort_id="cicc_fundamental_handbook_v1", factor_id="qual_cfoa_ttm",
            factor_domain_claim_id="claim_qual_cfoa_ttm_univ_all_00001",
            replication_tier="exact_certified",
            active_cap_reasons=["short_oos_power_floor_fail"],
            cohort_denominator_membership=["formalization_candidate"],
            truth_label_end="2022-12-31",
        )
        assert rec.status_ceiling == "candidate_ceiling"     # short-OOS cap
        assert "short_oos_power_floor_fail" in rec.blocking_reasons
        df = s.records()
        assert len(df) == 1 and df.iloc[0]["status_ceiling"] == "candidate_ceiling"

    def test_upsert_is_idempotent_on_key(self, tmp_path):
        s = ReplicationGovernanceStore(tmp_path)
        kw = dict(cohort_id="c", factor_id="f", factor_domain_claim_id="claim1",
                  replication_tier="proxy_approx")
        s.upsert(**kw, active_cap_reasons=["proxy_approx"])
        s.upsert(**kw, active_cap_reasons=["proxy_approx"])   # same key → replace, not append
        assert len(s.records()) == 1

    def test_unknown_tier_and_denominator_rejected(self, tmp_path):
        s = ReplicationGovernanceStore(tmp_path)
        with pytest.raises(ValueError, match="unknown replication_tier"):
            s.upsert(cohort_id="c", factor_id="f", factor_domain_claim_id="k",
                     replication_tier="not_a_tier")
        with pytest.raises(ValueError, match="unknown cohort denominator"):
            s.upsert(cohort_id="c", factor_id="f", factor_domain_claim_id="k",
                     replication_tier="proxy_approx", cohort_denominator_membership=["bogus"])

    def test_uncomputable_metrics_recorded_without_lowering_ceiling(self, tmp_path):
        # §11.1b: orientation_undetermined goes in uncomputable_metrics, NOT active_cap_reasons,
        # and does not lower the ceiling.
        s = ReplicationGovernanceStore(tmp_path)
        rec = s.upsert(
            cohort_id="c", factor_id="f", factor_domain_claim_id="k",
            replication_tier="formula_equivalent_pending",
            oos_eligible_gates_met=OOS_ELIGIBLE_GATES,
            uncomputable_metrics={"univ_microcap_q10_q1": "orientation_undetermined"},
        )
        assert rec.status_ceiling == "eligible_for_oos"      # not lowered by the weak-signal flag
        assert rec.uncomputable_metrics["univ_microcap_q10_q1"] == "orientation_undetermined"
