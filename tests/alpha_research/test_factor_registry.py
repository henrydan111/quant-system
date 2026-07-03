import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.alpha_research.factor_registry import FactorRegistryStore

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_OUTPUTS = PROJECT_ROOT / "workspace" / "outputs"


def _passing_promotion_evidence(git_sha: str = "abc123") -> dict:
    """A complete promotion artifact that passes assert_promotion_artifact_eligible:
    an INDEPENDENT PIT-correct reproduction source + every required canary/lint/parity
    check 'passed' + a clean tree + a git_sha to be matched against current_git_sha.
    (promotion_status is force-set by the gated writer.)"""
    return {
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
        "git_sha": git_sha,
    }


def _override_payload() -> dict:
    """A complete v1.4 legacy_factor_approval_override payload (round-1 M4)."""
    return {
        "issue_id": "GOV-TEST-1",
        "user_signoff_artifact": "workspace/outputs/test_signoff.json",
        "reviewer_identity": "test_reviewer",
        "reason_code": "test_legacy_exception",
        "scope": "single-factor test scope",
        "not_a_new_research_promotion": True,
    }


def _mint_legacy_approved(store, factor_id: str, git_sha: str = "legacy_sha") -> None:
    """Test fixture: create a LEGACY approved row through the sole audited door."""
    store.legacy_factor_approval_override(
        factor_id=factor_id, reason="test fixture legacy approval",
        override=_override_payload(),
        promotion_evidence=_passing_promotion_evidence(git_sha=git_sha),
        current_git_sha=git_sha,
    )


class FactorRegistryTests(unittest.TestCase):
    def make_temp_dir(self, name: str):
        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(prefix=f"{name}_", dir=WORKSPACE_OUTPUTS)

    def test_sync_catalog_creates_expected_current_counts(self):
        # Counts are DERIVED from catalog_composition() (the single source of truth),
        # never hard-coded — the catalog grows as factors are added. This still
        # enforces the real invariant: sync output == catalog composition, the
        # base/composite/industry_relative partition is correct, no duplicate ids,
        # and re-sync is idempotent (no row growth).
        from src.alpha_research.factor_library.catalog import catalog_composition
        comp = catalog_composition()
        with self.make_temp_dir("factor_registry_sync") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            result = store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")

            current_df = store.factor_master[store.factor_master["is_current"].fillna(False)].copy()

            self.assertEqual(result["current_factor_count"], comp["total"])
            self.assertEqual(len(current_df), comp["total"])
            self.assertEqual(int((current_df["factor_kind"] == "base").sum()), comp["base"])
            self.assertEqual(int((current_df["factor_kind"] == "composite").sum()), comp["composite"])
            self.assertEqual(int((current_df["factor_kind"] == "industry_relative").sum()), comp["industry_relative"])

            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:05:00")
            current_df = store.factor_master[store.factor_master["is_current"].fillna(False)].copy()
            self.assertEqual(len(current_df), comp["total"])
            self.assertEqual(current_df["factor_id"].nunique(), comp["total"])

    def test_base_factor_definition_change_creates_new_version(self):
        with self.make_temp_dir("factor_registry_base_version") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            with (
                patch(
                    "src.alpha_research.factor_registry.store.get_factor_catalog",
                    side_effect=[
                        {"toy_factor": "Ref($close, 1)"},
                        {"toy_factor": "Ref($close, 2)"},
                    ],
                ),
                patch(
                    "src.alpha_research.factor_registry.store.get_composite_defs",
                    return_value=[],
                ),
                patch(
                    "src.alpha_research.factor_registry.store.get_category_map",
                    return_value={"toy_factor": "Toy"},
                ),
            ):
                store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
                store.sync_catalog(record_run=False, generated_at="2026-04-04 21:10:00")

            factor_rows = store.factor_master[store.factor_master["factor_id"] == "toy_factor"].sort_values("version")
            self.assertEqual(factor_rows["version"].tolist(), [1, 2])
            self.assertEqual(factor_rows["is_current"].tolist(), [False, True])
            self.assertEqual(factor_rows.iloc[-1]["status"], "draft")

    def test_composite_definition_change_creates_new_version(self):
        with self.make_temp_dir("factor_registry_composite_version") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            with (
                patch(
                    "src.alpha_research.factor_registry.store.get_factor_catalog",
                    return_value={},
                ),
                patch(
                    "src.alpha_research.factor_registry.store.get_composite_defs",
                    side_effect=[
                        [{"name": "comp_toy", "components": ["a", "b"]}],
                        [{"name": "comp_toy", "components": ["a", "b"], "weights": [0.7, 0.3]}],
                    ],
                ),
                patch(
                    "src.alpha_research.factor_registry.store.get_category_map",
                    return_value={"comp_toy": "Composite"},
                ),
            ):
                store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
                store.sync_catalog(record_run=False, generated_at="2026-04-04 21:10:00")

            factor_rows = store.factor_master[store.factor_master["factor_id"] == "comp_toy"].sort_values("version")
            self.assertEqual(factor_rows["version"].tolist(), [1, 2])
            self.assertEqual(factor_rows["is_current"].tolist(), [False, True])

    def test_set_status_updates_master_and_history(self):
        with self.make_temp_dir("factor_registry_status") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")

            # Non-privileged transition: exercises the master + history update
            # mechanics. The privileged "approved" path is gated (PR P1.1) and is
            # covered by test_set_status_approved_requires_promotion_gate.
            result = store.set_status(
                factor_id="liq_vol_cv_20d",
                status="candidate",
                reason="manual promotion",
            )

            current_row = store.factor_master[
                (store.factor_master["factor_id"] == "liq_vol_cv_20d")
                & (store.factor_master["is_current"].fillna(False))
            ].iloc[0]
            self.assertEqual(result["new_status"], "candidate")
            self.assertEqual(current_row["status"], "candidate")
            self.assertEqual(len(store.status_history), 1)
            self.assertEqual(store.status_history.iloc[0]["reason"], "manual promotion")

    def test_set_status_approved_retired_v14(self):
        # v1.4 A3: the factor-level 'approved' mint is RETIRED. set_status refuses
        # candidate->approved ALWAYS — even with a perfect promotion artifact and a
        # matching git sha — and there is NO keyword bypass (round-1 M4).
        from src.research_orchestrator.release_gate import FactorLevelApprovedRetiredError

        with self.make_temp_dir("factor_registry_gate") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")

            with self.assertRaises(FactorLevelApprovedRetiredError):
                store.set_status(factor_id="liq_vol_cv_20d", status="approved", reason="x")

            # Even a FULLY passing artifact + sha is refused: the mint is retired,
            # not evidence-gated.
            with self.assertRaises(FactorLevelApprovedRetiredError):
                store.set_status(
                    factor_id="liq_vol_cv_20d", status="approved", reason="x",
                    promotion_evidence=_passing_promotion_evidence(git_sha="abc123"),
                    current_git_sha="abc123",
                )

            # No string-argument escape hatch exists on set_status (round-1 M4).
            with self.assertRaises(TypeError):
                store.set_status(
                    factor_id="liq_vol_cv_20d", status="approved", reason="x",
                    legacy_exception_reason="please",
                )

            row = store.factor_master[
                (store.factor_master["factor_id"] == "liq_vol_cv_20d")
                & (store.factor_master["is_current"].fillna(False))
            ].iloc[0]
            self.assertEqual(row["status"], "draft")

    def test_legacy_override_is_the_sole_gated_mint(self):
        # v1.4 A3/M4: legacy_factor_approval_override keeps the FULL old promotion gate
        # (independent reproduction + canaries + sha) AND requires the audited override
        # payload. On success the row becomes approved with approval_validity=="valid".
        from src.research_orchestrator.release_gate import PromotionGateError

        with self.make_temp_dir("factor_registry_override") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")

            # Missing override payload fields -> refused.
            incomplete = _override_payload()
            del incomplete["issue_id"]
            with self.assertRaises(PromotionGateError):
                store.legacy_factor_approval_override(
                    factor_id="liq_vol_cv_20d", reason="x", override=incomplete,
                    promotion_evidence=_passing_promotion_evidence(git_sha="abc123"),
                    current_git_sha="abc123",
                )

            # The machine-readable assertion must be literally True (not a string).
            lying = _override_payload()
            lying["not_a_new_research_promotion"] = "True"
            with self.assertRaises(PromotionGateError):
                store.legacy_factor_approval_override(
                    factor_id="liq_vol_cv_20d", reason="x", override=lying,
                    promotion_evidence=_passing_promotion_evidence(git_sha="abc123"),
                    current_git_sha="abc123",
                )

            # A sandbox/loader reproduction source is NOT independent -> gate blocks.
            bad = _passing_promotion_evidence(git_sha="abc123")
            bad["independent_reproduction"] = {"source": "pit_research_loader"}
            with self.assertRaises(PromotionGateError):
                store.legacy_factor_approval_override(
                    factor_id="liq_vol_cv_20d", reason="x", override=_override_payload(),
                    promotion_evidence=bad, current_git_sha="abc123",
                )

            # GPT cross-review P0 (inherited): promotion_status in the evidence cannot
            # downgrade the gate.
            with self.assertRaises(PromotionGateError):
                store.legacy_factor_approval_override(
                    factor_id="liq_vol_cv_20d", reason="x", override=_override_payload(),
                    promotion_evidence={"promotion_status": "draft"}, current_git_sha="abc123",
                )
            row = store.factor_master[
                (store.factor_master["factor_id"] == "liq_vol_cv_20d")
                & (store.factor_master["is_current"].fillna(False))
            ].iloc[0]
            self.assertEqual(row["status"], "draft")

            # Full payload + full evidence + sha -> the audited mint succeeds.
            result = store.legacy_factor_approval_override(
                factor_id="liq_vol_cv_20d", reason="promote",
                override=_override_payload(),
                promotion_evidence=_passing_promotion_evidence(git_sha="abc123"),
                current_git_sha="abc123",
            )
            self.assertEqual(result["new_status"], "approved")
            row = store.factor_master[
                (store.factor_master["factor_id"] == "liq_vol_cv_20d")
                & (store.factor_master["is_current"].fillna(False))
            ].iloc[0]
            self.assertEqual(row["status"], "approved")
            self.assertEqual(row["approval_validity"], "valid")
            # The override audit payload lands in the status history.
            self.assertIn("legacy_factor_approval_override", store.status_history.iloc[-1]["reason"])

    def test_a3_writer_gate_matrix(self):
        # v1.4 §5 acceptance test: candidate->approved refused; approved->candidate and
        # approved->deprecated ALLOWED (revocation paths keep working); legacy
        # revalidation only via the dedicated evidence-gated path.
        from src.research_orchestrator.release_gate import (
            FactorLevelApprovedRetiredError,
            PromotionGateError,
        )

        with self.make_temp_dir("factor_registry_matrix") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")

            # candidate->approved refused.
            store.set_status(factor_id="liq_vol_cv_20d", status="candidate", reason="is-gate")
            with self.assertRaises(FactorLevelApprovedRetiredError):
                store.set_status(factor_id="liq_vol_cv_20d", status="approved", reason="promote")

            # Build a legacy approved row through the audited door, then downgrade paths:
            _mint_legacy_approved(store, "liq_vol_cv_20d")
            result = store.set_status(
                factor_id="liq_vol_cv_20d", status="candidate", reason="revocation test"
            )
            self.assertEqual(result["old_status"], "approved")
            self.assertEqual(result["new_status"], "candidate")

            _mint_legacy_approved(store, "rev_up_down_ratio_20d")
            result = store.set_status(
                factor_id="rev_up_down_ratio_20d", status="deprecated", reason="retire test"
            )
            self.assertEqual(result["new_status"], "deprecated")

            # revalidate_legacy_approved refuses a NON-approved row (can never mint).
            with self.assertRaises(PromotionGateError):
                store.revalidate_legacy_approved(
                    factor_id="liq_vol_cv_20d", reason="x",
                    revalidation_evidence=_passing_promotion_evidence(git_sha="s2"),
                    current_git_sha="s2",
                    current_definition_hash="whatever",
                )

    def test_set_approval_validity_cannot_revalidate_approved_row(self):
        # GPT cross-review P0: set_approval_validity is the drift/downgrade path; it
        # must NOT flip an approved row back to "valid" (that re-opens it as a formal
        # factor without the promotion gate). Downgrades are allowed.
        with self.make_temp_dir("factor_registry_revalidate") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
            _mint_legacy_approved(store, "liq_vol_cv_20d", git_sha="s1")
            # downgrade (valid -> stale) is allowed
            store.set_approval_validity(factor_id="liq_vol_cv_20d", validity="stale", reason="provider rebuild")
            row = store.factor_master[
                (store.factor_master["factor_id"] == "liq_vol_cv_20d")
                & (store.factor_master["is_current"].fillna(False))
            ].iloc[0]
            self.assertEqual(row["approval_validity"], "stale")
            # re-validation back to valid via this method is refused
            with self.assertRaises(ValueError):
                store.set_approval_validity(factor_id="liq_vol_cv_20d", validity="valid", reason="hand-wave")

            # v1.4 A3/M2: the dedicated evidence-gated door DOES re-affirm validity —
            # without a mint and without touching status.
            stored_hash = row["definition_hash"]
            result = store.revalidate_legacy_approved(
                factor_id="liq_vol_cv_20d", reason="canary rerun clean",
                revalidation_evidence=_passing_promotion_evidence(git_sha="s2"),
                current_git_sha="s2",
                current_definition_hash=stored_hash,
            )
            self.assertEqual(result["approval_validity"], "valid")
            row = store.factor_master[
                (store.factor_master["factor_id"] == "liq_vol_cv_20d")
                & (store.factor_master["is_current"].fillna(False))
            ].iloc[0]
            self.assertEqual(row["status"], "approved")
            self.assertEqual(row["approval_validity"], "valid")

            # Definition drift without a migration record -> refused.
            from src.research_orchestrator.release_gate import PromotionGateError
            with self.assertRaises(PromotionGateError):
                store.revalidate_legacy_approved(
                    factor_id="liq_vol_cv_20d", reason="x",
                    revalidation_evidence=_passing_promotion_evidence(git_sha="s3"),
                    current_git_sha="s3",
                    current_definition_hash="a_different_hash",
                )

    def test_approval_validity_backfill_is_fail_closed(self):
        # A row persisted as approved with a BLANK approval_validity (pre-column
        # upgrade) is normalized to requires_revalidation on load; a non-approved
        # blank row becomes valid.
        with self.make_temp_dir("factor_registry_validity") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
            idx = store.factor_master.index[
                store.factor_master["factor_id"] == "liq_vol_cv_20d"
            ][0]
            store.factor_master.at[idx, "status"] = "approved"
            store.factor_master.at[idx, "approval_validity"] = pd.NA
            store.save()

            reloaded = FactorRegistryStore(temp_dir)
            row = reloaded.factor_master[
                reloaded.factor_master["factor_id"] == "liq_vol_cv_20d"
            ].iloc[0]
            self.assertEqual(row["status"], "approved")
            self.assertEqual(row["approval_validity"], "requires_revalidation")

    def test_export_current_approved_is_fail_closed_on_validity(self):
        # An "approved" export is the deployable set: a stale-approved row is excluded
        # by default and only included under include_invalid=True.
        with self.make_temp_dir("factor_registry_export") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
            ids = store.factor_master["factor_id"].tolist()
            valid_id, stale_id = ids[0], ids[1]
            for fid, validity in ((valid_id, "valid"), (stale_id, "stale")):
                i = store.factor_master.index[store.factor_master["factor_id"] == fid][0]
                store.factor_master.at[i, "status"] = "approved"
                store.factor_master.at[i, "approval_validity"] = validity

            out = Path(temp_dir) / "approved.csv"
            self.assertEqual(store.export_current(out, status="approved"), 1)
            self.assertEqual(store.export_current(out, status="approved", include_invalid=True), 2)

    def test_current_catalog_definition_hashes_round_trip(self):
        # PR P1.3: the hash map from the current code catalog must equal the
        # definition_hash sync_catalog wrote for every current row (base / composite /
        # industry-relative) — the apples-to-apples parity the drift gate relies on.
        with self.make_temp_dir("factor_registry_defhash") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
            code = store.current_catalog_definition_hashes()
            current = store.factor_master[store.factor_master["is_current"].fillna(False)]
            self.assertEqual(len(code), len(current))
            mismatches = [
                r["factor_id"] for _, r in current.iterrows()
                if code.get(r["factor_id"]) != r["definition_hash"]
            ]
            self.assertEqual(mismatches, [])
            self.assertTrue(
                {"base", "composite", "industry_relative"}.issubset(set(current["factor_kind"]))
            )

    def test_cli_set_status_approved_without_evidence_exits_2(self):
        # PR P1.1: the registry CLI must NOT be an unaudited approval door. Without
        # --promotion-evidence-json, set-status --status approved exits 2 and never
        # reaches the store. (Non-approved statuses are unaffected.)
        import subprocess
        import sys

        with self.make_temp_dir("factor_registry_cli") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
            store.save()
            cli = PROJECT_ROOT / "workspace" / "scripts" / "factor_registry_cli.py"
            proc = subprocess.run(
                [
                    sys.executable, str(cli),
                    "--registry-dir", str(temp_dir),
                    "set-status", "--factor", "liq_vol_cv_20d",
                    "--status", "approved", "--reason", "x",
                ],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("promotion-evidence-json", proc.stderr + proc.stdout)
            # the factor must still be draft (no bypass write happened)
            reloaded = FactorRegistryStore(temp_dir)
            row = reloaded.factor_master[
                reloaded.factor_master["factor_id"] == "liq_vol_cv_20d"
            ].iloc[0]
            self.assertEqual(row["status"], "draft")

    def test_phase2_schema_columns_present_with_fail_closed_defaults(self):
        # PR P2.1: the evidence/metadata columns exist; new rows get fail-closed
        # defaults; status is untouched (the Phase-1 boundary).
        with self.make_temp_dir("factor_registry_p2_schema") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
            for col in ("signal_role", "signal_role_suggested", "long_only_viable_provisional",
                        "field_eligibility_snapshot_json", "latest_provider_build_id",
                        "expected_direction", "last_revalidated_at"):
                self.assertIn(col, store.factor_master.columns)
            for col in ("lo_sharpe_gross", "lo_excess_ann_gross", "oos_ls_sharpe", "retain_pct",
                        "evidence_class", "formal_evidence_eligible", "source_hash", "provider_build_id"):
                self.assertIn(col, store.factor_evidence.columns)
            from src.alpha_research.factor_library.catalog import catalog_composition
            current = store.factor_master[store.factor_master["is_current"].fillna(False)]
            self.assertEqual(len(current), catalog_composition()["total"])  # P2.1 changes no row count
            row = current.iloc[0]
            self.assertEqual(row["signal_role"], "unassigned")
            self.assertEqual(row["signal_role_suggested"], "unassigned")
            self.assertEqual(row["long_only_viable_provisional"], "non_viable")
            self.assertEqual(row["status"], "draft")  # P2.1 promotes/changes nothing

    def test_phase2_metadata_backfills_fail_closed_on_load(self):
        # A pre-P2.1 on-disk registry (no Phase-2 columns) loads back with the
        # fail-closed defaults via _normalize_phase2_metadata.
        with self.make_temp_dir("factor_registry_p2_backfill") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
            legacy = store.factor_master.drop(columns=[
                "signal_role", "signal_role_suggested", "long_only_viable_provisional",
            ])
            legacy.to_parquet(store.factor_master_path, index=False)

            reloaded = FactorRegistryStore(temp_dir)
            row = reloaded.factor_master[
                reloaded.factor_master["is_current"].fillna(False)
            ].iloc[0]
            self.assertEqual(row["signal_role"], "unassigned")
            self.assertEqual(row["signal_role_suggested"], "unassigned")
            self.assertEqual(row["long_only_viable_provisional"], "non_viable")

    def test_derive_long_only_viable_boundaries(self):
        # PR P2.2: the fail-closed decision order at its thresholds.
        from src.alpha_research.factor_registry.store import _derive_long_only_viable
        self.assertEqual(_derive_long_only_viable(None, 0.1, 0.7), "non_viable")   # missing
        self.assertEqual(_derive_long_only_viable(1.0, 0.1, 0.60), "viable")       # exactly at thresholds
        self.assertEqual(_derive_long_only_viable(1.4, 0.12, 0.66), "viable")
        self.assertEqual(_derive_long_only_viable(1.2, 0.1, 0.59), "review_only")  # high sharpe, low hit
        self.assertEqual(_derive_long_only_viable(0.7, 0.1, 0.9), "review_only")   # mid sharpe
        self.assertEqual(_derive_long_only_viable(0.49, 0.1, 0.9), "non_viable")   # sharpe < 0.5
        self.assertEqual(_derive_long_only_viable(2.0, -0.01, 0.9), "non_viable")  # excess < 0
        self.assertEqual(_derive_long_only_viable(2.0, 0.0, 0.9), "non_viable")    # excess == 0

    def test_refresh_derives_long_only_viable_from_evidence(self):
        # PR P2.2: refresh reads the latest GROSS LO evidence and derives
        # long_only_viable_provisional + the latest_lo_sharpe_gross/oos mirrors;
        # status is never touched; a factor with no LO evidence stays non_viable.
        from src.alpha_research.factor_registry.store import (
            _apply_schema, FACTOR_EVIDENCE_COLUMNS, FACTOR_EVIDENCE_SCHEMA,
        )
        with self.make_temp_dir("factor_registry_p2_derive") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
            target = store.factor_master[store.factor_master["is_current"].fillna(False)].iloc[0]
            fid, ver = target["factor_id"], int(target["version"])
            ev = _apply_schema(pd.DataFrame([{
                "run_id": "rv1", "run_type": "revalidation", "factor_id": fid, "version": ver,
                "is_current_at_import": True, "evidence_time": "2026-05-01 00:00:00",
                "lo_sharpe_gross": 1.4, "lo_excess_ann_gross": 0.12, "lo_hit": 0.66,
                "oos_rank_icir": 0.31, "evidence_class": "historical_investigation",
                "formal_evidence_eligible": False,
            }]), FACTOR_EVIDENCE_COLUMNS, FACTOR_EVIDENCE_SCHEMA)
            store.factor_evidence = pd.concat([store.factor_evidence, ev], ignore_index=True)
            store.refresh_master_derived_fields()

            row = store.factor_master[
                (store.factor_master["factor_id"] == fid)
                & (store.factor_master["is_current"].fillna(False))
            ].iloc[0]
            self.assertEqual(row["long_only_viable_provisional"], "viable")
            self.assertAlmostEqual(float(row["latest_lo_sharpe_gross"]), 1.4)
            self.assertAlmostEqual(float(row["latest_oos_rank_icir"]), 0.31)
            self.assertEqual(row["status"], "draft")  # P2.2 derives evidence, never status
            other = store.factor_master[
                (store.factor_master["factor_id"] != fid)
                & (store.factor_master["is_current"].fillna(False))
            ].iloc[0]
            self.assertEqual(other["long_only_viable_provisional"], "non_viable")

    def test_import_revalidation_definition_bound_evidence_only(self):
        # PR P2.3: import attaches evidence ONLY to in-sync factors (registry hash ==
        # current catalog hash), SKIPS drifted + unknown factors (fail-closed, never by
        # name), labels rows historical_investigation / formal_evidence_eligible=False,
        # never touches status, derives viability, and is idempotent.
        with self.make_temp_dir("factor_registry_p2_import") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
            current = store.factor_master[store.factor_master["is_current"].fillna(False)]
            in_sync = current.iloc[0]["factor_id"]
            drift_fid = current.iloc[1]["factor_id"]
            # corrupt the drift factor's registry definition_hash -> drift vs catalog
            idx = store.factor_master.index[
                (store.factor_master["factor_id"] == drift_fid)
                & (store.factor_master["is_current"].fillna(False))
            ][0]
            store.factor_master.at[idx, "definition_hash"] = "deadbeef" * 8

            csv_path = Path(temp_dir) / "derived.csv"
            pd.DataFrame([
                {"factor": in_sync, "kind": "base", "is_rank_icir": 0.2, "oos_rank_icir": 0.31,
                 "sign_consistency": 0.8, "lo_excess_ann": 0.12, "lo_sharpe": 1.4, "lo_hit": 0.66},
                {"factor": drift_fid, "kind": "base", "is_rank_icir": 0.1, "oos_rank_icir": 0.1,
                 "sign_consistency": 0.7, "lo_excess_ann": 0.05, "lo_sharpe": 0.6, "lo_hit": 0.55},
                {"factor": "totally_unknown_factor", "kind": "base", "is_rank_icir": 0.1,
                 "oos_rank_icir": 0.1, "sign_consistency": 0.7, "lo_excess_ann": 0.0,
                 "lo_sharpe": 0.0, "lo_hit": 0.0},
            ]).to_csv(csv_path, index=False)

            report = store.import_revalidation(derived_csv=csv_path, provider_build_id="pb1", run_id="rv_test")
            self.assertIn(in_sync, report["attached"])
            self.assertIn(drift_fid, report["skipped_drift"])
            self.assertIn("totally_unknown_factor", report["skipped_unknown"])

            ev = store.factor_evidence[
                (store.factor_evidence["factor_id"] == in_sync)
                & (store.factor_evidence["run_type"] == "revalidation")
            ]
            self.assertEqual(len(ev), 1)
            erow = ev.iloc[0]
            self.assertEqual(erow["evidence_class"], "historical_investigation")
            self.assertEqual(bool(erow["formal_evidence_eligible"]), False)
            self.assertAlmostEqual(float(erow["lo_sharpe_gross"]), 1.4)
            self.assertTrue(str(erow["source_hash"]))  # bound to the definition_hash

            mrow = store.factor_master[
                (store.factor_master["factor_id"] == in_sync)
                & (store.factor_master["is_current"].fillna(False))
            ].iloc[0]
            self.assertEqual(mrow["long_only_viable_provisional"], "viable")
            self.assertEqual(mrow["status"], "draft")  # P2.3 writes evidence, never status
            # the drifted factor got NO evidence
            self.assertTrue(store.factor_evidence[
                (store.factor_evidence["factor_id"] == drift_fid)
                & (store.factor_evidence["run_type"] == "revalidation")
            ].empty)

            # idempotent: re-import keeps exactly one evidence row for in_sync
            store.import_revalidation(derived_csv=csv_path, provider_build_id="pb1", run_id="rv_test")
            ev2 = store.factor_evidence[
                (store.factor_evidence["factor_id"] == in_sync)
                & (store.factor_evidence["run_type"] == "revalidation")
            ]
            self.assertEqual(len(ev2), 1)

    def test_refresh_mirrors_provenance_and_suggests_role_for_viable(self):
        # GPT PR-#31 finding 1: refresh mirrors provider/calendar/last_revalidated_at
        # from the bound evidence, and a viable factor gets signal_role_suggested=
        # long_only_alpha — while the authoritative signal_role stays unassigned.
        with self.make_temp_dir("factor_registry_p2_f1") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
            in_sync = store.factor_master[
                store.factor_master["is_current"].fillna(False)
            ].iloc[0]["factor_id"]
            csv_path = Path(temp_dir) / "derived.csv"
            pd.DataFrame([{
                "factor": in_sync, "kind": "base", "is_rank_icir": 0.2, "oos_rank_icir": 0.31,
                "sign_consistency": 0.8, "lo_excess_ann": 0.12, "lo_sharpe": 1.4, "lo_hit": 0.66,
            }]).to_csv(csv_path, index=False)
            store.import_revalidation(
                derived_csv=csv_path, provider_build_id="pbZ", calendar_policy_id="calZ",
                run_id="rv_f1",
            )
            row = store.factor_master[
                (store.factor_master["factor_id"] == in_sync)
                & (store.factor_master["is_current"].fillna(False))
            ].iloc[0]
            self.assertEqual(row["long_only_viable_provisional"], "viable")
            self.assertEqual(row["latest_provider_build_id"], "pbZ")
            self.assertEqual(row["latest_calendar_policy_id"], "calZ")
            self.assertTrue(str(row["last_revalidated_at"]).strip())
            self.assertEqual(row["signal_role_suggested"], "long_only_alpha")
            self.assertEqual(row["signal_role"], "unassigned")  # authoritative role untouched

    def test_sync_catalog_alone_leaves_revalidation_mirrors_blank(self):
        # GPT PR-#31 re-review: a plain sync_catalog writes a catalog_sync evidence row
        # (blank source_hash) — it must NOT stamp last_revalidated_at / provider /
        # calendar mirrors, which reflect REVALIDATION evidence only (run_type ==
        # "revalidation"). (On the pre-fix any-bound-row code this found the sync
        # timestamp on all 177 -> this test fails there.)
        with self.make_temp_dir("factor_registry_p2_revalonly") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=True, generated_at="2026-04-04 21:00:00")
            from src.alpha_research.factor_library.catalog import catalog_composition
            cur = store.factor_master[store.factor_master["is_current"].fillna(False)]
            self.assertEqual(len(cur), catalog_composition()["total"])
            self.assertTrue((cur["last_revalidated_at"].astype(str).str.strip() == "").all())
            self.assertTrue((cur["latest_provider_build_id"].astype(str).str.strip() == "").all())
            self.assertTrue((cur["latest_calendar_policy_id"].astype(str).str.strip() == "").all())

    def test_refresh_no_cross_row_metric_mixing(self):
        # GPT PR-#31 finding 2: a newer PARTIAL LO row (Sharpe only) must NOT inherit an
        # older row's excess/hit. Derive from the single latest LO-bearing row's tuple;
        # a partial latest tuple -> non_viable. (On the pre-fix independent-latest code
        # this asserted "viable" — this test fails there.)
        from src.alpha_research.factor_registry.store import (
            _apply_schema, FACTOR_EVIDENCE_COLUMNS, FACTOR_EVIDENCE_SCHEMA,
        )
        with self.make_temp_dir("factor_registry_p2_f2") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
            target = store.factor_master[store.factor_master["is_current"].fillna(False)].iloc[0]
            fid, ver, dh = target["factor_id"], int(target["version"]), target["definition_hash"]
            rows = _apply_schema(pd.DataFrame([
                {"run_id": "old", "run_type": "revalidation", "factor_id": fid, "version": ver,
                 "is_current_at_import": True, "evidence_time": "2026-05-01 00:00:00", "source_hash": dh,
                 "lo_sharpe_gross": 1.4, "lo_excess_ann_gross": 0.12, "lo_hit": 0.66},   # complete -> viable
                {"run_id": "new", "run_type": "revalidation", "factor_id": fid, "version": ver,
                 "is_current_at_import": True, "evidence_time": "2026-06-01 00:00:00", "source_hash": dh,
                 "lo_sharpe_gross": 1.9, "lo_excess_ann_gross": None, "lo_hit": None},      # partial!
            ]), FACTOR_EVIDENCE_COLUMNS, FACTOR_EVIDENCE_SCHEMA)
            store.factor_evidence = pd.concat([store.factor_evidence, rows], ignore_index=True)
            store.refresh_master_derived_fields()
            row = store.factor_master[
                (store.factor_master["factor_id"] == fid)
                & (store.factor_master["is_current"].fillna(False))
            ].iloc[0]
            self.assertEqual(row["long_only_viable_provisional"], "non_viable")
            self.assertAlmostEqual(float(row["latest_lo_sharpe_gross"]), 1.9)  # latest row's Sharpe

    def test_refresh_ignores_stale_definition_evidence(self):
        # GPT PR-#31 finding 3: evidence whose nonblank source_hash != the row's CURRENT
        # definition_hash is ignored (stale-definition guard), so it cannot drive
        # viability even though it physically remains in factor_evidence. (On the pre-fix
        # code this asserted "viable" — this test fails there.)
        from src.alpha_research.factor_registry.store import (
            _apply_schema, FACTOR_EVIDENCE_COLUMNS, FACTOR_EVIDENCE_SCHEMA,
        )
        with self.make_temp_dir("factor_registry_p2_f3") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
            target = store.factor_master[store.factor_master["is_current"].fillna(False)].iloc[0]
            fid, ver, dh = target["factor_id"], int(target["version"]), target["definition_hash"]
            ev = _apply_schema(pd.DataFrame([{
                "run_id": "rv", "run_type": "revalidation", "factor_id": fid, "version": ver,
                "is_current_at_import": True, "evidence_time": "2026-05-01 00:00:00", "source_hash": dh,
                "lo_sharpe_gross": 1.4, "lo_excess_ann_gross": 0.12, "lo_hit": 0.66,
            }]), FACTOR_EVIDENCE_COLUMNS, FACTOR_EVIDENCE_SCHEMA)
            store.factor_evidence = pd.concat([store.factor_evidence, ev], ignore_index=True)
            store.refresh_master_derived_fields()
            idx = store.factor_master.index[
                (store.factor_master["factor_id"] == fid)
                & (store.factor_master["is_current"].fillna(False))
            ][0]
            self.assertEqual(store.factor_master.at[idx, "long_only_viable_provisional"], "viable")
            # registry definition drifts (nonblank mismatch vs the evidence source_hash)
            store.factor_master.at[idx, "definition_hash"] = "cafe" * 16
            store.refresh_master_derived_fields()
            self.assertEqual(store.factor_master.at[idx, "long_only_viable_provisional"], "non_viable")
            self.assertTrue(pd.isna(store.factor_master.at[idx, "latest_lo_sharpe_gross"]))

    def test_field_eligibility_snapshot_base_and_composite(self):
        # GPT PR-#31 finding 4: refresh populates field_eligibility_snapshot_json from the
        # live registry — BASE factors resolve their $fields (resolved=true); COMPOSITE /
        # INDUSTRY_RELATIVE are fail-closed resolved=false (transitive deps deferred to P3).
        with self.make_temp_dir("factor_registry_p2_f4") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
            cur = store.factor_master[store.factor_master["is_current"].fillna(False)]
            base_snap = json.loads(cur[cur["factor_kind"] == "base"].iloc[0]["field_eligibility_snapshot_json"])
            self.assertTrue(base_snap["resolved"])
            self.assertIn("all_allowed", base_snap)
            self.assertIsInstance(base_snap["fields"], dict)
            self.assertTrue(base_snap["fields"])  # a base factor references at least one $field
            for kind in ("composite", "industry_relative"):
                rows = cur[cur["factor_kind"] == kind]
                if rows.empty:
                    continue
                comp_snap = json.loads(rows.iloc[0]["field_eligibility_snapshot_json"])
                self.assertFalse(comp_snap["resolved"])  # fail-closed: never all_allowed=true
                self.assertNotIn("all_allowed", comp_snap)

    def test_html_review_surfaces_phase2_columns(self):
        # PR P2.4: the registry review HTML surfaces the LO metric / viability / signal-role.
        with self.make_temp_dir("factor_registry_p2_html") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
            html = store.render_html_review().read_text(encoding="utf-8")
            for label in ("Long-only viability", "Long-only Sharpe (gross)", "OOS Rank ICIR",
                          "Signal role", "Approval validity"):
                self.assertIn(label, html)

    def test_cli_import_revalidation_attaches_evidence(self):
        # PR P2.4: the import-revalidation CLI attaches definition-bound, labeled
        # evidence (and never changes status).
        import subprocess
        import sys

        with self.make_temp_dir("factor_registry_p2_cli") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
            store.save()
            in_sync = store.factor_master[
                store.factor_master["is_current"].fillna(False)
            ].iloc[0]["factor_id"]
            csv_path = Path(temp_dir) / "derived.csv"
            pd.DataFrame([{
                "factor": in_sync, "kind": "base", "is_rank_icir": 0.2, "oos_rank_icir": 0.31,
                "sign_consistency": 0.8, "lo_excess_ann": 0.12, "lo_sharpe": 1.4, "lo_hit": 0.66,
            }]).to_csv(csv_path, index=False)
            cli = PROJECT_ROOT / "workspace" / "scripts" / "factor_registry_cli.py"
            proc = subprocess.run(
                [sys.executable, str(cli), "--registry-dir", str(temp_dir),
                 "import-revalidation", "--derived-csv", str(csv_path), "--run-id", "rv_cli"],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("attached", proc.stdout + proc.stderr)
            reloaded = FactorRegistryStore(temp_dir)
            ev = reloaded.factor_evidence[
                (reloaded.factor_evidence["factor_id"] == in_sync)
                & (reloaded.factor_evidence["run_type"] == "revalidation")
            ]
            self.assertEqual(len(ev), 1)
            self.assertEqual(ev.iloc[0]["evidence_class"], "historical_investigation")
            # status untouched
            self.assertEqual(reloaded.factor_master[
                reloaded.factor_master["factor_id"] == in_sync
            ].iloc[0]["status"], "draft")

    def test_save_generates_human_readable_html_review(self):
        with self.make_temp_dir("factor_registry_html") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-04-04 21:00:00")
            store.save()

            html_path = Path(temp_dir) / "factor_registry_review.html"
            self.assertTrue(html_path.exists())
            html_text = html_path.read_text(encoding="utf-8")
            self.assertIn("Formal Factor Registry Review", html_text)
            self.assertIn("liq_vol_cv_20d", html_text)
            self.assertIn("All Current Factors", html_text)

    def test_import_screening_is_idempotent_and_marks_legacy_binding_without_hashes(self):
        with self.make_temp_dir("factor_registry_screening") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            run_dir = Path(temp_dir) / "screening_run"
            run_dir.mkdir(parents=True, exist_ok=True)

            metadata = {
                "generated_at": "2026-04-04 21:00:00",
                "start_date": "2012-01-01",
                "end_date": "2025-12-31",
                "include_new_data": True,
                "requested_kernels": "qlib default",
                "effective_kernels": "qlib default",
            }
            report_df = pd.DataFrame(
                [
                    {
                        "factor": "liq_vol_cv_20d",
                        "grade": "A (Graduated)",
                        "mean_rank_ic_5d": -0.05,
                        "rank_icir_5d": -0.70,
                        "ic_hit_rate_5d": 0.73,
                        "monotonic": True,
                        "ls_ann_return": -1.17,
                    },
                    {
                        "factor": "comp_val_qual",
                        "grade": "B (Strong IC)",
                        "mean_rank_ic_5d": 0.03,
                        "rank_icir_5d": 0.42,
                        "ic_hit_rate_5d": 0.61,
                        "monotonic": False,
                        "ls_ann_return": 0.22,
                    },
                ]
            )
            (run_dir / "factor_screening_run_metadata.json").write_text(
                json.dumps(metadata, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )
            report_df.to_csv(run_dir / "factor_screening_report.csv", index=False)

            store.import_screening(run_dir)
            store.import_screening(run_dir)

            screening_rows = store.factor_evidence[store.factor_evidence["run_type"] == "screening"]
            self.assertEqual(len(screening_rows), 2)

            liq_row = store.factor_master[
                (store.factor_master["factor_id"] == "liq_vol_cv_20d")
                & (store.factor_master["is_current"].fillna(False))
            ].iloc[0]
            self.assertEqual(liq_row["definition_binding"], "legacy_best_effort")
            self.assertEqual(liq_row["latest_screening_grade"], "A (Graduated)")
            self.assertEqual(liq_row["recommended_status"], "candidate")

    def test_import_research_aggregates_validation_and_selection_counts(self):
        with self.make_temp_dir("factor_registry_research") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            run_dir = Path(temp_dir) / "research_run"
            run_dir.mkdir(parents=True, exist_ok=True)

            metadata = {
                "generated_at": "2026-04-04 21:00:00",
                "benchmark": "000905.SH",
                "folds": [
                    {
                        "train_start": "2012-01-01",
                        "train_end": "2016-12-31",
                        "validation_start": "2017-01-01",
                        "validation_end": "2018-12-31",
                        "test_start": "2019-01-01",
                        "test_end": "2019-12-31",
                    }
                ],
                "kernel_meta": {
                    "requested_kernels": "qlib default",
                    "effective_kernels": "1",
                },
            }
            metrics_df = pd.DataFrame(
                [
                    {
                        "factor": "liq_vol_cv_20d",
                        "grade": "A (Graduated)",
                        "category": "Liquidity",
                        "mean_rank_ic_5d": -0.05,
                        "rank_icir_5d": -0.93,
                        "ic_hit_rate_5d": 0.78,
                        "best_decay_horizon": 10,
                        "peak_decay_icir": 0.76,
                        "ls_ann_return": -0.70,
                        "monotonic": True,
                    },
                    {
                        "factor": "comp_val_qual",
                        "grade": "B (Strong IC)",
                        "category": "Composite",
                        "mean_rank_ic_5d": 0.03,
                        "rank_icir_5d": 0.35,
                        "ic_hit_rate_5d": 0.61,
                        "best_decay_horizon": 20,
                        "peak_decay_icir": 0.40,
                        "ls_ann_return": 0.15,
                        "monotonic": False,
                    },
                ]
            )
            decisions_df = pd.DataFrame(
                [
                    {"factor": "liq_vol_cv_20d", "fold_id": "fold_01", "val_rank_icir": -0.8, "validation_pass": True},
                    {"factor": "liq_vol_cv_20d", "fold_id": "fold_02", "val_rank_icir": -0.7, "validation_pass": True},
                    {"factor": "liq_vol_cv_20d", "fold_id": "fold_03", "val_rank_icir": -0.6, "validation_pass": True},
                    {"factor": "liq_vol_cv_20d", "fold_id": "fold_04", "val_rank_icir": -0.5, "validation_pass": True},
                    {"factor": "comp_val_qual", "fold_id": "fold_01", "val_rank_icir": 0.2, "validation_pass": True},
                ]
            )
            selected_df = pd.DataFrame(
                [
                    {"fold_id": "fold_01", "selection_rank": 1, "factor": "liq_vol_cv_20d"},
                    {"fold_id": "fold_02", "selection_rank": 1, "factor": "liq_vol_cv_20d"},
                    {"fold_id": "fold_03", "selection_rank": 1, "factor": "liq_vol_cv_20d"},
                    {"fold_id": "fold_04", "selection_rank": 1, "factor": "liq_vol_cv_20d"},
                ]
            )

            (run_dir / "run_metadata.json").write_text(
                json.dumps(metadata, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )
            metrics_df.to_csv(run_dir / "factor_research_metrics.csv", index=False)
            decisions_df.to_csv(run_dir / "factor_selection_decisions.csv", index=False)
            selected_df.to_csv(run_dir / "selected_core_factors_by_fold.csv", index=False)

            store.import_research(run_dir)

            liq_row = store.factor_master[
                (store.factor_master["factor_id"] == "liq_vol_cv_20d")
                & (store.factor_master["is_current"].fillna(False))
            ].iloc[0]
            self.assertEqual(int(liq_row["latest_validation_pass_count"]), 4)
            self.assertEqual(int(liq_row["latest_selected_fold_count"]), 4)
            self.assertEqual(liq_row["recommended_status"], "approved")


class FactorRegistryIntegrationTests(unittest.TestCase):
    SCREENING_RUN_DIR = PROJECT_ROOT / "workspace" / "research" / "alpha_mining" / "latest_backend_screening_20260401_new_data"
    RESEARCH_RUN_DIR = PROJECT_ROOT / "workspace" / "research" / "alpha_mining" / "event_driven_strategy_research_full_20260401_main"

    def make_temp_dir(self, name: str):
        WORKSPACE_OUTPUTS.mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(prefix=f"{name}_", dir=WORKSPACE_OUTPUTS)

    @unittest.skipUnless(
        SCREENING_RUN_DIR.exists() and RESEARCH_RUN_DIR.exists(),
        "real screening/research run dirs not present",
    )
    def test_real_screening_and_research_imports(self):
        with self.make_temp_dir("factor_registry_real") as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=True, generated_at="2026-04-04 21:00:00")
            screening_result = store.import_screening(self.SCREENING_RUN_DIR)
            research_result = store.import_research(self.RESEARCH_RUN_DIR)

            self.assertEqual(screening_result["factor_count"], 149)
            self.assertEqual(research_result["factor_count"], 43)

            liq_row = store.factor_master[
                (store.factor_master["factor_id"] == "liq_vol_cv_20d")
                & (store.factor_master["is_current"].fillna(False))
            ].iloc[0]
            rev_row = store.factor_master[
                (store.factor_master["factor_id"] == "rev_max_return_20d")
                & (store.factor_master["is_current"].fillna(False))
            ].iloc[0]
            comp_row = store.factor_master[
                (store.factor_master["factor_id"] == "comp_defensive")
                & (store.factor_master["is_current"].fillna(False))
            ].iloc[0]

            self.assertEqual(liq_row["latest_screening_grade"], "A (Graduated)")
            self.assertGreaterEqual(int(liq_row["latest_validation_pass_count"]), 1)
            self.assertGreaterEqual(int(rev_row["latest_selected_fold_count"]), 1)
            self.assertNotEqual(comp_row["latest_screening_grade"], "")

            _mint_legacy_approved(store, "liq_vol_cv_20d", git_sha="integ_sha")
            export_path = Path(temp_dir) / "approved.csv"
            export_count = store.export_current(export_path, status="approved")
            export_df = pd.read_csv(export_path)

            self.assertEqual(export_count, len(export_df))
            self.assertTrue((export_df["status"] == "approved").all())


class FormalRefreshEvidenceTests(unittest.TestCase):
    """2026-06-10 unified merge: the UNGATED refresh writer for the formal methodology.

    Two-class taxonomy: discovery (screening) / formal (lifecycle methodology). Refresh rows
    share the formal methodology but must NEVER look gate-approved — run_type
    'factor_lifecycle_auto', evidence_class 'formal_auto', formal_evidence_eligible=False
    (the "refresh" label was retired 2026-06-11 — external taxonomy is discovery/formal only).
    """

    def _record(self, fid: str, **over) -> dict:
        rec = {
            "factor": fid, "heldout_rank_icir": 0.30, "sign_consistency": 1.0,
            "mean_rank_ic": 0.02, "mean_rank_ic_hac_t": 3.2,
            "neutralized_rank_icir": 0.4, "neutralized_hac_t": 4.1,
            "mono_shape": "monotonic_up", "direction_source": "train_fold",
            "coverage": 0.99, "coverage_tier": "full", "turnover_ann": 5.0,
            "resid_ic_vs_approved_stable_oriented": 0.02,
            "resid_ic_vs_style_controls_v1_oriented": 0.01,
            "long_leg_ir_proxy_is_csi300": 0.5, "long_leg_ir_proxy_is_csi500": 1.1,
            "decay_icir_40": 0.25,  # column-less metric → must survive via unified_metrics_json
        }
        rec.update(over)
        return rec

    def test_refresh_rows_are_formal_methodology_but_never_gate_eligible(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-06-10 12:00:00")
            fid = store.factor_master[store.factor_master["is_current"].fillna(False)].iloc[0]["factor_id"]
            out = store.record_formal_refresh_evidence(
                run_id="unified_refresh_testhash", records=[self._record(fid)],
                methodology_hash="testhash", source_path="workspace/outputs/unified_eval",
                generated_at="2026-06-10 12:01:00",
            )
            self.assertEqual(out["attached"], [fid])
            ev = store.factor_evidence
            row = ev[ev["factor_id"] == fid].iloc[-1]
            self.assertEqual(row["run_type"], "factor_lifecycle_auto")
            self.assertEqual(row["evidence_class"], "formal_auto")
            self.assertFalse(bool(row["formal_evidence_eligible"]))  # NEVER gate-eligible
            self.assertEqual(row["methodology_hash"], "testhash")
            self.assertAlmostEqual(float(row["is_rank_icir"]), 0.30)
            self.assertAlmostEqual(float(row["neutralized_rank_icir"]), 0.4)
            self.assertEqual(row["mono_shape"], "monotonic_up")
            payload = json.loads(row["unified_metrics_json"])
            self.assertAlmostEqual(payload["decay_icir_40"], 0.25)  # full record preserved

    def test_refresh_writer_is_definition_bound_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-06-10 12:00:00")
            cur = store.factor_master[store.factor_master["is_current"].fillna(False)]
            fid = cur.iloc[0]["factor_id"]
            # poison the stored definition hash → drifted → must be SKIPPED, never attached
            store.factor_master.loc[store.factor_master["factor_id"] == fid, "definition_hash"] = "drifted"
            out = store.record_formal_refresh_evidence(
                run_id="r1", records=[self._record(fid), self._record("no_such_factor")],
                methodology_hash="h",
            )
            self.assertIn(fid, out["skipped_drift"])
            self.assertIn("no_such_factor", out["skipped_unknown"])
            self.assertEqual(out["attached"], [])

    def test_refresh_writer_idempotent_per_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-06-10 12:00:00")
            fid = store.factor_master[store.factor_master["is_current"].fillna(False)].iloc[0]["factor_id"]
            for _ in range(2):  # re-import the same run → no duplicate rows
                store.record_formal_refresh_evidence(
                    run_id="rX", records=[self._record(fid)], methodology_hash="h")
            ev = store.factor_evidence
            self.assertEqual(int(((ev["run_id"] == "rX") & (ev["factor_id"] == fid)).sum()), 1)

    def test_old_evidence_parquet_widens_on_load(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = FactorRegistryStore(temp_dir)
            store.sync_catalog(record_run=False, generated_at="2026-06-10 12:00:00")
            store.save()
            # simulate an OLD on-disk evidence file lacking the new columns
            ev_path = Path(temp_dir) / "factor_evidence.parquet"
            old = pd.read_parquet(ev_path)
            old = old.drop(columns=[c for c in old.columns if c in (
                "methodology_hash", "unified_metrics_json", "mono_shape")], errors="ignore")
            old.to_parquet(ev_path, index=False)
            reloaded = FactorRegistryStore(temp_dir)  # must not raise; new columns appear as NA
            for col in ("methodology_hash", "unified_metrics_json", "mono_shape"):
                self.assertIn(col, reloaded.factor_evidence.columns)


if __name__ == "__main__":
    unittest.main()
