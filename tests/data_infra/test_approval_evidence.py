"""PR 10 follow-up to the 2026-05-26 freeze plan (after PR 9c merged):
provider-build invalidation automation for field-registry approval YAMLs.

Approval YAMLs under ``config/field_registry/approvals/`` pin both
``provider_build_id`` and ``calendar_policy_id`` as evidence that the
on-disk verification was performed against a specific Qlib provider
build. This module's tests verify that
:func:`src.data_infra.approval_evidence.evaluate_approval_evidence_bindings`
catches drift between any approval's binding and the current manifest.

Scenarios covered:

  1. Matched binding → no drift, eligible.
  2. Mismatched ``provider_build_id`` → drift reported.
  3. Mismatched ``calendar_policy_id`` → drift reported.
  4. Both mismatched → both reasons surfaced.
  5. Legacy YAML without bindings → silently skipped.
  6. Missing manifest → FileNotFoundError raised.
  7. Missing approvals directory → empty result, no raise.
  8. Strict variant (:func:`assert_no_approval_evidence_drift`) raises
     ApprovalEvidenceDriftError with a precise diagnostic.
  9. Live registry smoke: the committed approval YAMLs do not drift
     against the committed provider_build.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.data_infra.approval_evidence import (
    ApprovalBinding,
    ApprovalBindingDrift,
    ApprovalEvidenceDriftError,
    DEFAULT_APPROVALS_DIR,
    DEFAULT_PROVIDER_MANIFEST,
    assert_no_approval_evidence_drift,
    evaluate_approval_evidence_bindings,
    load_approval_bindings,
    load_current_manifest,
)


# ─────────────────────────────────────────────────────────────────────────
# Test fixtures
# ─────────────────────────────────────────────────────────────────────────


def _write_yaml(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _write_manifest(path: Path, *, provider_build_id: str, calendar_policy_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "provider_build_id": provider_build_id,
                "calendar_policy_id": calendar_policy_id,
                "provider": {"calendar_end_date": "2026-02-27"},
            }
        ),
        encoding="utf-8",
    )


# ─────────────────────────────────────────────────────────────────────────
# Core behavior — drift detection
# ─────────────────────────────────────────────────────────────────────────


class TestMatchedBinding:
    def test_matched_binding_no_drift(self, tmp_path: Path) -> None:
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "2026-05-27_test_dataset_approved.yaml", """
approval_id: 2026-05-27_test_dataset_approved
date: 2026-05-27
dataset_id: test_dataset
to_status: approved
provider_build_id: prod_full_20260421_namespace_v1
calendar_policy_id: frozen_20260227_system_build
""".strip())
        manifest = tmp_path / "manifest.json"
        _write_manifest(
            manifest,
            provider_build_id="prod_full_20260421_namespace_v1",
            calendar_policy_id="frozen_20260227_system_build",
        )
        drifts = evaluate_approval_evidence_bindings(
            approvals_dir=approvals, manifest_path=manifest,
        )
        assert len(drifts) == 1
        assert drifts[0].drift is False
        assert drifts[0].provider_build_id_match is True
        assert drifts[0].calendar_policy_id_match is True
        assert drifts[0].reasons() == []


class TestProviderBuildDrift:
    def test_provider_build_id_mismatch(self, tmp_path: Path) -> None:
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "2026-05-27_drift_test.yaml", """
approval_id: 2026-05-27_drift_test
date: 2026-05-27
dataset_id: indicators
to_status: approved
provider_build_id: prod_full_20260421_namespace_v1
calendar_policy_id: frozen_20260227_system_build
""".strip())
        manifest = tmp_path / "manifest.json"
        _write_manifest(
            manifest,
            provider_build_id="prod_full_20260601_rebuild_v2",  # changed!
            calendar_policy_id="frozen_20260227_system_build",
        )
        drifts = evaluate_approval_evidence_bindings(
            approvals_dir=approvals, manifest_path=manifest,
        )
        assert len(drifts) == 1
        d = drifts[0]
        assert d.drift is True
        assert d.provider_build_id_match is False
        assert d.calendar_policy_id_match is True
        reasons = d.reasons()
        assert any("provider_build_id" in r for r in reasons)
        assert any("prod_full_20260421_namespace_v1" in r for r in reasons)
        assert any("prod_full_20260601_rebuild_v2" in r for r in reasons)


class TestCalendarPolicyDrift:
    def test_calendar_policy_id_mismatch(self, tmp_path: Path) -> None:
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "2026-05-27_cp_drift.yaml", """
approval_id: 2026-05-27_cp_drift
date: 2026-05-27
dataset_id: indicators
to_status: approved
provider_build_id: prod_full_20260421_namespace_v1
calendar_policy_id: frozen_20260227_system_build
""".strip())
        manifest = tmp_path / "manifest.json"
        _write_manifest(
            manifest,
            provider_build_id="prod_full_20260421_namespace_v1",
            calendar_policy_id="rolling_20260601_post_freeze",  # changed!
        )
        drifts = evaluate_approval_evidence_bindings(
            approvals_dir=approvals, manifest_path=manifest,
        )
        d = drifts[0]
        assert d.drift is True
        assert d.provider_build_id_match is True
        assert d.calendar_policy_id_match is False
        reasons = d.reasons()
        assert any("calendar_policy_id" in r for r in reasons)


class TestBothMismatched:
    def test_both_mismatched_yields_two_reasons(self, tmp_path: Path) -> None:
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "2026-05-27_both_drift.yaml", """
approval_id: 2026-05-27_both_drift
date: 2026-05-27
dataset_id: indicators
to_status: approved
provider_build_id: prod_full_20260421_namespace_v1
calendar_policy_id: frozen_20260227_system_build
""".strip())
        manifest = tmp_path / "manifest.json"
        _write_manifest(
            manifest,
            provider_build_id="other_build",
            calendar_policy_id="other_policy",
        )
        drifts = evaluate_approval_evidence_bindings(
            approvals_dir=approvals, manifest_path=manifest,
        )
        d = drifts[0]
        assert d.drift is True
        reasons = d.reasons()
        assert len(reasons) == 2
        assert any("provider_build_id" in r for r in reasons)
        assert any("calendar_policy_id" in r for r in reasons)


# ─────────────────────────────────────────────────────────────────────────
# Edge cases — legacy YAML, missing files
# ─────────────────────────────────────────────────────────────────────────


class TestLegacyYamlSkipped:
    def test_yaml_without_bindings_is_skipped(self, tmp_path: Path) -> None:
        """Pre-PR-9a-round-3 approval YAMLs don't carry the binding
        contract; they must be silently skipped, not raise."""
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "2024-01-01_legacy.yaml", """
approval_id: 2024-01-01_legacy
date: 2024-01-01
dataset_id: legacy_dataset
to_status: approved
# No provider_build_id, no calendar_policy_id — predates PR 9a round-3
""".strip())
        manifest = tmp_path / "manifest.json"
        _write_manifest(
            manifest,
            provider_build_id="prod_full_20260421_namespace_v1",
            calendar_policy_id="frozen_20260227_system_build",
        )
        # Both bindings list and drift list should be empty (skipped).
        assert load_approval_bindings(approvals) == []
        assert evaluate_approval_evidence_bindings(
            approvals_dir=approvals, manifest_path=manifest,
        ) == []


class TestPartialBinding:
    def test_yaml_with_only_provider_build_id(self, tmp_path: Path) -> None:
        """An approval with only one of the two bindings should be
        included in the scan; the missing one is treated as a wildcard."""
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "2026-05-27_pb_only.yaml", """
approval_id: 2026-05-27_pb_only
date: 2026-05-27
dataset_id: partial_dataset
to_status: approved
provider_build_id: prod_full_20260421_namespace_v1
# no calendar_policy_id declared
""".strip())
        manifest = tmp_path / "manifest.json"
        _write_manifest(
            manifest,
            provider_build_id="prod_full_20260421_namespace_v1",
            calendar_policy_id="anything_at_all",
        )
        drifts = evaluate_approval_evidence_bindings(
            approvals_dir=approvals, manifest_path=manifest,
        )
        assert len(drifts) == 1
        d = drifts[0]
        # Declared pb matches, declared cp is None → treated as wildcard match
        assert d.drift is False
        assert d.provider_build_id_match is True
        assert d.calendar_policy_id_match is True


class TestMissingManifest:
    def test_missing_manifest_raises(self, tmp_path: Path) -> None:
        """A formal-mode caller cannot validate against an absent manifest
        and must fail loudly."""
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "x.yaml", """
approval_id: x
dataset_id: x
to_status: approved
provider_build_id: anything
calendar_policy_id: anything
""".strip())
        missing_manifest = tmp_path / "does_not_exist.json"
        with pytest.raises(FileNotFoundError, match="Provider manifest not found"):
            evaluate_approval_evidence_bindings(
                approvals_dir=approvals, manifest_path=missing_manifest,
            )


class TestMissingApprovalsDir:
    def test_missing_approvals_dir_returns_empty(self, tmp_path: Path) -> None:
        """When no approvals directory exists, the scan returns empty
        without raising — there's simply nothing to check."""
        manifest = tmp_path / "manifest.json"
        _write_manifest(
            manifest,
            provider_build_id="x",
            calendar_policy_id="y",
        )
        missing_dir = tmp_path / "no_approvals_here"
        drifts = evaluate_approval_evidence_bindings(
            approvals_dir=missing_dir, manifest_path=manifest,
        )
        assert drifts == []


# ─────────────────────────────────────────────────────────────────────────
# Strict variant — assert_no_approval_evidence_drift
# ─────────────────────────────────────────────────────────────────────────


class TestStrictAssert:
    def test_passes_silently_on_matched_bindings(self, tmp_path: Path) -> None:
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "ok.yaml", """
approval_id: ok
dataset_id: ok_dataset
to_status: approved
provider_build_id: prod_full_20260421_namespace_v1
calendar_policy_id: frozen_20260227_system_build
""".strip())
        manifest = tmp_path / "manifest.json"
        _write_manifest(
            manifest,
            provider_build_id="prod_full_20260421_namespace_v1",
            calendar_policy_id="frozen_20260227_system_build",
        )
        # Should not raise; returns the (empty-drift) records.
        result = assert_no_approval_evidence_drift(
            approvals_dir=approvals, manifest_path=manifest,
        )
        assert len(result) == 1
        assert result[0].drift is False

    def test_raises_with_diagnostic_on_drift(self, tmp_path: Path) -> None:
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "stale.yaml", """
approval_id: stale_evidence
dataset_id: indicators
to_status: approved
provider_build_id: old_build_id
calendar_policy_id: frozen_20260227_system_build
""".strip())
        manifest = tmp_path / "manifest.json"
        _write_manifest(
            manifest,
            provider_build_id="new_build_id",
            calendar_policy_id="frozen_20260227_system_build",
        )
        with pytest.raises(ApprovalEvidenceDriftError) as exc_info:
            assert_no_approval_evidence_drift(
                approvals_dir=approvals, manifest_path=manifest,
            )
        msg = str(exc_info.value)
        assert "stale_evidence" in msg
        assert "old_build_id" in msg
        assert "new_build_id" in msg
        assert "indicators" in msg

    def test_drift_message_lists_remediation(self, tmp_path: Path) -> None:
        """Drift diagnostics must explain how to recover, not just what
        broke. Operators reading the daily-QA report need actionable
        guidance."""
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "x.yaml", """
approval_id: x
dataset_id: x
to_status: approved
provider_build_id: old
calendar_policy_id: old
""".strip())
        manifest = tmp_path / "manifest.json"
        _write_manifest(
            manifest,
            provider_build_id="new",
            calendar_policy_id="new",
        )
        with pytest.raises(ApprovalEvidenceDriftError) as exc_info:
            assert_no_approval_evidence_drift(
                approvals_dir=approvals, manifest_path=manifest,
            )
        msg = str(exc_info.value)
        # Remediation path is explicit.
        assert "re-verifying" in msg or "re-verify" in msg
        assert "revert" in msg or "refresh" in msg


# ─────────────────────────────────────────────────────────────────────────
# Live registry smoke — committed approvals against committed manifest
# ─────────────────────────────────────────────────────────────────────────


class TestLiveRegistrySmoke:
    def test_committed_approvals_match_committed_manifest(self) -> None:
        """Sanity check against the committed
        ``config/field_registry/approvals/*.yaml`` files +
        ``data/qlib_data/metadata/provider_build.json``. If this fails,
        either the provider was rebuilt without refreshing approval
        evidence, OR an approval YAML was edited with a stale binding.

        Skipped (not failed) if either the approvals directory or the
        manifest is missing on this host — the binary contract is enforced
        on the production publish host, not on every developer machine.
        """
        if not DEFAULT_APPROVALS_DIR.exists():
            pytest.skip("no approvals directory on this host")
        if not DEFAULT_PROVIDER_MANIFEST.exists():
            pytest.skip("no provider manifest on this host")
        drifts = evaluate_approval_evidence_bindings()
        drifted = [d for d in drifts if d.drift]
        assert not drifted, (
            "Committed approval YAMLs drift against the current provider "
            "manifest:\n"
            + "\n".join(f"  - {r}" for d in drifted for r in d.reasons())
        )


# ─────────────────────────────────────────────────────────────────────────
# Daily QA wiring (source-level proof)
# ─────────────────────────────────────────────────────────────────────────


class TestDailyQAWiring:
    def test_run_daily_qa_invokes_approval_evidence_check(self) -> None:
        """``scripts/run_daily_qa.py`` must include the new audit block
        so the check fires automatically. Source-level proof; a
        behavioral end-to-end is heavier (needs full Qlib layout)."""
        src = Path("scripts/run_daily_qa.py").read_text(encoding="utf-8")
        assert "_approval_evidence_binding_check" in src, (
            "scripts/run_daily_qa.py must define and call "
            "_approval_evidence_binding_check (PR 10 follow-up to PR 9c)."
        )
        # The check must be appended to the `checks` list in main().
        main_idx = src.index("def main(")
        main_body = src[main_idx:]
        assert "checks.append(_approval_evidence_binding_check())" in main_body, (
            "main() must call checks.append(_approval_evidence_binding_check())."
        )
        # The label must match what evaluate_approval_evidence_bindings
        # surfaces in its return record.
        assert '"approval_evidence_binding"' in src, (
            "Audit-block label must be 'approval_evidence_binding'."
        )
