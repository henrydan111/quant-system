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
    ApprovalEvidenceConfigError,
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
    def test_yaml_without_bindings_and_without_exemption_raises(self, tmp_path: Path) -> None:
        """PR 10c: a YAML missing BOTH binding keys and lacking an explicit
        binding_exempt marker now FAILS closed. Pre-PR-10c this silently
        skipped, which could not distinguish a true unbound record from a
        new approval that accidentally omitted the binding."""
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "2024-01-01_legacy.yaml", """
approval_id: 2024-01-01_legacy
date: 2024-01-01
dataset_id: legacy_dataset
to_status: approved
# No provider_build_id, no calendar_policy_id, no binding_exempt marker
""".strip())
        with pytest.raises(ApprovalEvidenceConfigError) as exc_info:
            load_approval_bindings(approvals)
        msg = str(exc_info.value)
        assert "2024-01-01_legacy.yaml" in msg
        assert "binding_exempt" in msg

    def test_yaml_with_explicit_exemption_is_skipped(self, tmp_path: Path) -> None:
        """PR 10c: an unbound administrative record with an explicit
        binding_exempt: true + reason is skipped from the drift scan."""
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "2026-05-27_coverage_fix.yaml", """
approval_id: 2026-05-27_coverage_fix
date: 2026-05-27
dataset_id: moneyflow
to_status: quarantine (unchanged)
binding_exempt: true
binding_exempt_reason: "Coverage/diagnostic fix only; no formal-use promotion."
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


class TestPartialBindingFailsClosed:
    """PR 10a (GPT 5.5 Pro round-6 review): partial bindings used to be
    treated as wildcard on the missing axis — a fail-open path that
    silently weakened the contract from two dimensions to one. PR 10a
    raises ApprovalEvidenceConfigError instead."""

    def test_provider_build_id_without_calendar_policy_raises(self, tmp_path: Path) -> None:
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
        with pytest.raises(ApprovalEvidenceConfigError) as exc_info:
            load_approval_bindings(approvals)
        msg = str(exc_info.value)
        assert "provider_build_id" in msg
        assert "calendar_policy_id" in msg
        # Diagnostic must point at the offending file path.
        assert "2026-05-27_pb_only.yaml" in msg

    def test_calendar_policy_without_provider_build_id_raises(self, tmp_path: Path) -> None:
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "2026-05-27_cp_only.yaml", """
approval_id: 2026-05-27_cp_only
date: 2026-05-27
dataset_id: partial_dataset
to_status: approved
calendar_policy_id: frozen_20260227_system_build
# no provider_build_id declared
""".strip())
        with pytest.raises(ApprovalEvidenceConfigError) as exc_info:
            load_approval_bindings(approvals)
        msg = str(exc_info.value)
        assert "calendar_policy_id" in msg
        assert "provider_build_id" in msg
        # Remediation guidance in the error message.
        assert "BOTH" in msg or "both" in msg

    def test_eval_propagates_partial_binding_error(self, tmp_path: Path) -> None:
        """The strict-assert wrapper must also surface partial-binding errors
        (they're raised at load_approval_bindings, so evaluate_* inherits)."""
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "partial.yaml", """
approval_id: partial
dataset_id: x
to_status: approved
provider_build_id: x
""".strip())
        manifest = tmp_path / "manifest.json"
        _write_manifest(manifest, provider_build_id="x", calendar_policy_id="y")
        with pytest.raises(ApprovalEvidenceConfigError):
            evaluate_approval_evidence_bindings(
                approvals_dir=approvals, manifest_path=manifest,
            )


class TestMalformedYamlFailsClosed:
    """PR 10a: pre-PR-10a malformed YAMLs were logged-and-skipped, a
    fail-open path that could silently disappear an approval from the
    drift check. PR 10a raises ApprovalEvidenceConfigError."""

    def test_malformed_yaml_raises(self, tmp_path: Path) -> None:
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        # Use a token that yaml.safe_load actually rejects: ``: just colons :``
        # produces a YAMLError; an unbalanced bracket like ``[unterminated``
        # would also work.
        _write_yaml(approvals / "broken.yaml", "key: value\n: bad: : indent\n  ::oops")
        with pytest.raises(ApprovalEvidenceConfigError) as exc_info:
            load_approval_bindings(approvals)
        msg = str(exc_info.value)
        assert "broken.yaml" in msg
        assert "Malformed" in msg or "malformed" in msg

    def test_non_dict_top_level_raises(self, tmp_path: Path) -> None:
        """YAMLs that parse to a list / scalar are governance errors."""
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "as_list.yaml", "- item_one\n- item_two\n")
        with pytest.raises(ApprovalEvidenceConfigError) as exc_info:
            load_approval_bindings(approvals)
        msg = str(exc_info.value)
        assert "as_list.yaml" in msg
        assert "mapping" in msg.lower()

    def test_empty_yaml_treated_as_legacy_skip(self, tmp_path: Path) -> None:
        """An empty YAML parses to None and would historically fail the
        isinstance(dict) check. PR 10a raises (since None isn't a mapping)
        rather than silently skipping."""
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "empty.yaml", "")
        with pytest.raises(ApprovalEvidenceConfigError):
            load_approval_bindings(approvals)


class TestNullOrBlankBindingFailsClosed:
    """PR 10b (GPT 5.5 Pro round-7 review): pre-PR-10b ``data.get(...)``
    collapsed "key absent" and "key present with null value" into the
    same ``None``, so an approval YAML that KEPT the binding keys but
    blanked their values (e.g. during a manual provider rebuild) was
    silently skipped as legacy. PR 10b distinguishes key absence (via
    ``in``) from a null / empty / blank / non-string value, and fails
    closed on the latter."""

    def test_both_keys_null_raises(self, tmp_path: Path) -> None:
        """Keys present but both values null (`key:` with no value).
        Pre-PR-10b this was the silent-skip fail-open path."""
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "null_values.yaml", """
approval_id: null_values
date: 2026-05-27
dataset_id: indicators
to_status: approved
provider_build_id:
calendar_policy_id:
""".strip())
        with pytest.raises(ApprovalEvidenceConfigError) as exc_info:
            load_approval_bindings(approvals)
        msg = str(exc_info.value)
        assert "null_values.yaml" in msg
        # The diagnostic must flag the value, not claim the key is absent.
        assert "null" in msg.lower() or "blank" in msg.lower() or "empty" in msg.lower()

    def test_both_keys_empty_string_raises(self, tmp_path: Path) -> None:
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "empty_str.yaml", """
approval_id: empty_str
dataset_id: indicators
to_status: approved
provider_build_id: ""
calendar_policy_id: ""
""".strip())
        with pytest.raises(ApprovalEvidenceConfigError):
            load_approval_bindings(approvals)

    def test_both_keys_whitespace_raises(self, tmp_path: Path) -> None:
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "whitespace.yaml", """
approval_id: whitespace
dataset_id: indicators
to_status: approved
provider_build_id: "   "
calendar_policy_id: "   "
""".strip())
        with pytest.raises(ApprovalEvidenceConfigError):
            load_approval_bindings(approvals)

    def test_one_key_present_null_other_absent_raises(self, tmp_path: Path) -> None:
        """provider_build_id present with null value, calendar_policy_id
        entirely absent. The partial-key check fires first (exactly one
        key present), which is still a fail-closed outcome."""
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "one_null_one_absent.yaml", """
approval_id: one_null_one_absent
dataset_id: indicators
to_status: approved
provider_build_id:
""".strip())
        with pytest.raises(ApprovalEvidenceConfigError):
            load_approval_bindings(approvals)

    def test_one_key_valid_other_null_raises(self, tmp_path: Path) -> None:
        """Both keys present, one valid, one null. Must fail closed —
        a half-blanked binding cannot validate against the manifest."""
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "half_blank.yaml", """
approval_id: half_blank
dataset_id: indicators
to_status: approved
provider_build_id: prod_full_20260421_namespace_v1
calendar_policy_id:
""".strip())
        with pytest.raises(ApprovalEvidenceConfigError) as exc_info:
            load_approval_bindings(approvals)
        msg = str(exc_info.value)
        assert "calendar_policy_id" in msg

    def test_non_string_value_raises(self, tmp_path: Path) -> None:
        """A binding value that parses to a non-string (e.g. a number or
        a list) is a governance error."""
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "non_string.yaml", """
approval_id: non_string
dataset_id: indicators
to_status: approved
provider_build_id: 12345
calendar_policy_id: frozen_20260227_system_build
""".strip())
        with pytest.raises(ApprovalEvidenceConfigError):
            load_approval_bindings(approvals)

    def test_neither_key_without_exemption_raises(self, tmp_path: Path) -> None:
        """PR 10c: a YAML with NEITHER binding key and NO binding_exempt
        marker now FAILS closed (was a silent skip in PR 10a/10b). This is
        the last fail-open path GPT 5.5 Pro flagged in round-7."""
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "unmarked.yaml", """
approval_id: unmarked
date: 2024-01-01
dataset_id: legacy_dataset
to_status: approved
""".strip())
        with pytest.raises(ApprovalEvidenceConfigError):
            load_approval_bindings(approvals)

    def test_valid_nonempty_strings_pass_and_stripped(self, tmp_path: Path) -> None:
        """Both keys present with non-empty string values pass — and the
        stored values are stripped of surrounding whitespace so a binding
        with trailing spaces still matches a clean manifest value."""
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "valid.yaml", """
approval_id: valid
dataset_id: indicators
to_status: approved
provider_build_id: "  prod_full_20260421_namespace_v1  "
calendar_policy_id: frozen_20260227_system_build
""".strip())
        bindings = load_approval_bindings(approvals)
        assert len(bindings) == 1
        # Stored value is stripped.
        assert bindings[0].declared_provider_build_id == "prod_full_20260421_namespace_v1"
        assert bindings[0].declared_calendar_policy_id == "frozen_20260227_system_build"

        # And it matches a clean manifest value (drift=False) — proving the
        # strip is applied before comparison.
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


class TestBindingExemptContract:
    """PR 10c (GPT 5.5 Pro round-7 review): both-absent YAMLs no longer
    silently skip as "legacy". An unbound administrative record MUST
    declare ``binding_exempt: true`` (strict bool) with a non-empty
    ``binding_exempt_reason``; everything else fails closed. This closes
    the last fail-open path where a new approval that accidentally omitted
    both binding keys was indistinguishable from a true unbound record."""

    def test_both_absent_no_exemption_raises(self, tmp_path: Path) -> None:
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "no_exempt.yaml", """
approval_id: no_exempt
dataset_id: x
to_status: approved
""".strip())
        with pytest.raises(ApprovalEvidenceConfigError) as exc_info:
            load_approval_bindings(approvals)
        msg = str(exc_info.value)
        assert "no_exempt.yaml" in msg
        assert "binding_exempt" in msg

    def test_exempt_without_reason_raises(self, tmp_path: Path) -> None:
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "exempt_no_reason.yaml", """
approval_id: exempt_no_reason
dataset_id: x
to_status: quarantine
binding_exempt: true
""".strip())
        with pytest.raises(ApprovalEvidenceConfigError) as exc_info:
            load_approval_bindings(approvals)
        msg = str(exc_info.value)
        assert "binding_exempt_reason" in msg

    def test_exempt_with_blank_reason_raises(self, tmp_path: Path) -> None:
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "exempt_blank_reason.yaml", """
approval_id: exempt_blank_reason
dataset_id: x
to_status: quarantine
binding_exempt: true
binding_exempt_reason: "   "
""".strip())
        with pytest.raises(ApprovalEvidenceConfigError):
            load_approval_bindings(approvals)

    def test_exempt_with_reason_is_skipped(self, tmp_path: Path) -> None:
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "exempt_ok.yaml", """
approval_id: exempt_ok
dataset_id: x
to_status: quarantine
binding_exempt: true
binding_exempt_reason: "Coverage/diagnostic fix only; no formal-use promotion."
""".strip())
        # Skipped — not in the returned bindings.
        assert load_approval_bindings(approvals) == []

    def test_exempt_false_with_no_keys_raises(self, tmp_path: Path) -> None:
        """binding_exempt: false (falsy) with no binding keys must NOT
        exempt — it falls through to the both-absent fail-closed path."""
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "exempt_false.yaml", """
approval_id: exempt_false
dataset_id: x
to_status: approved
binding_exempt: false
""".strip())
        with pytest.raises(ApprovalEvidenceConfigError):
            load_approval_bindings(approvals)

    def test_exempt_string_true_does_not_exempt(self, tmp_path: Path) -> None:
        """binding_exempt: "true" (string, not bool) must NOT exempt — a
        non-bool value can't silently disable the gate via truthiness."""
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "exempt_string.yaml", """
approval_id: exempt_string
dataset_id: x
to_status: approved
binding_exempt: "true"
binding_exempt_reason: "trying to sneak past with a string"
""".strip())
        with pytest.raises(ApprovalEvidenceConfigError):
            load_approval_bindings(approvals)

    def test_both_keys_present_with_exemption_raises_contradiction(self, tmp_path: Path) -> None:
        """A provider-bound approval cannot also be exempt — contradictory."""
        approvals = tmp_path / "approvals"
        approvals.mkdir()
        _write_yaml(approvals / "contradiction.yaml", """
approval_id: contradiction
dataset_id: indicators
to_status: approved
provider_build_id: prod_full_20260421_namespace_v1
calendar_policy_id: frozen_20260227_system_build
binding_exempt: true
binding_exempt_reason: "should not be allowed alongside bindings"
""".strip())
        with pytest.raises(ApprovalEvidenceConfigError) as exc_info:
            load_approval_bindings(approvals)
        msg = str(exc_info.value)
        assert "contradict" in msg.lower()


class TestCommittedApprovalsSatisfyContract:
    """PR 10c: the committed approval YAMLs under
    config/field_registry/approvals/ MUST satisfy the post-PR-10c contract
    — load_approval_bindings on the real directory must not raise. This is
    a guardrail proving the indicators YAML carries a valid binding and the
    quarantine_prefix_fix YAML carries the explicit binding_exempt marker
    (NOT a silent both-absent skip)."""

    def test_committed_approvals_load_without_raising(self) -> None:
        if not DEFAULT_APPROVALS_DIR.exists():
            pytest.skip("no approvals directory on this host")
        # Must not raise ApprovalEvidenceConfigError.
        bindings = load_approval_bindings(DEFAULT_APPROVALS_DIR)
        # The indicators approval YAML carries a real binding, so at least
        # one binding must be present (the quarantine_prefix_fix YAML is
        # binding_exempt and therefore skipped).
        approval_ids = {b.approval_id for b in bindings}
        assert any("indicators" in aid for aid in approval_ids), (
            f"Expected the indicators approval to produce a binding; "
            f"got approval_ids={approval_ids}"
        )

    def test_quarantine_prefix_fix_is_exempt_not_bound(self) -> None:
        """The committed quarantine_prefix_fix YAML must be binding_exempt
        (skipped), NOT produce a binding — it is a coverage/diagnostic fix,
        not a formal-use promotion."""
        if not DEFAULT_APPROVALS_DIR.exists():
            pytest.skip("no approvals directory on this host")
        bindings = load_approval_bindings(DEFAULT_APPROVALS_DIR)
        for b in bindings:
            assert "quarantine_prefix_fix" not in b.approval_file, (
                "quarantine_prefix_fix YAML must be binding_exempt (skipped), "
                "not produce a provider-bound binding."
            )


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
        so the check fires automatically. Source-level proof; the
        behavioral end-to-end lives in TestDailyQABehavioral below."""
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

    def test_pr10a_resolver_helper_is_used_in_both_audit_blocks(self) -> None:
        """PR 10a: both _provider_manifest_check and
        _approval_evidence_binding_check must consume the same
        _resolve_qlib_dir_from_config helper. Pre-PR-10a the latter
        hardcoded data/qlib_data, creating a real divergence whenever
        storage.qlib_data_dir pointed to a non-default location."""
        src = Path("scripts/run_daily_qa.py").read_text(encoding="utf-8")
        assert "def _resolve_qlib_dir_from_config" in src, (
            "PR 10a: scripts/run_daily_qa.py must define "
            "_resolve_qlib_dir_from_config so both audit blocks share "
            "the same path resolution."
        )
        # _provider_manifest_check must use the helper.
        pm_start = src.index("def _provider_manifest_check")
        pm_next = src.find("\ndef ", pm_start + 1)
        pm_body = src[pm_start:pm_next if pm_next > 0 else len(src)]
        assert "_resolve_qlib_dir_from_config" in pm_body, (
            "PR 10a: _provider_manifest_check must call "
            "_resolve_qlib_dir_from_config (the shared helper)."
        )
        # _approval_evidence_binding_check must use the helper.
        ae_start = src.index("def _approval_evidence_binding_check")
        ae_next = src.find("\ndef ", ae_start + 1)
        ae_body = src[ae_start:ae_next if ae_next > 0 else len(src)]
        assert "_resolve_qlib_dir_from_config" in ae_body, (
            "PR 10a: _approval_evidence_binding_check must call "
            "_resolve_qlib_dir_from_config (the shared helper)."
        )
        # And the hardcoded path is gone.
        assert 'PROJECT_ROOT / "data" / "qlib_data"' not in ae_body, (
            "PR 10a: _approval_evidence_binding_check must NOT hardcode "
            "PROJECT_ROOT / 'data' / 'qlib_data'. Use the shared "
            "_resolve_qlib_dir_from_config helper instead."
        )


class TestDailyQABehavioral:
    """PR 10a: behavioral proof that _approval_evidence_binding_check
    honours config.yaml::storage.qlib_data_dir. Pre-PR-10a the check
    silently used the hardcoded default even when config.yaml pointed
    elsewhere — so a daily-QA run on a non-default provider host could
    falsely report ok=True against an unrelated manifest."""

    def _setup_temp_project(
        self,
        tmp_path: Path,
        *,
        custom_qlib_subdir: str,
        manifest_provider_build_id: str,
        manifest_calendar_policy_id: str,
    ) -> None:
        """Construct a temp project root with config.yaml pointing at a
        non-default qlib_data tree, plus a fake provider_build.json and
        one approval YAML."""
        # 1. config.yaml with custom storage.qlib_data_dir
        config_content = f"""
storage:
  qlib_data_dir: ./{custom_qlib_subdir}
""".lstrip()
        (tmp_path / "config.yaml").write_text(config_content, encoding="utf-8")

        # 2. fake qlib tree with manifest
        manifest_dir = tmp_path / custom_qlib_subdir / "metadata"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "provider_build.json").write_text(
            json.dumps(
                {
                    "provider_build_id": manifest_provider_build_id,
                    "calendar_policy_id": manifest_calendar_policy_id,
                    "provider": {"calendar_end_date": "2026-02-27"},
                }
            ),
            encoding="utf-8",
        )

        # 3. one approval YAML under the expected committed path
        approvals_dir = tmp_path / "config" / "field_registry" / "approvals"
        approvals_dir.mkdir(parents=True)
        (approvals_dir / "2026-05-27_pr10a_behavioral.yaml").write_text(
            f"""approval_id: 2026-05-27_pr10a_behavioral
date: 2026-05-27
dataset_id: pr10a_test_dataset
to_status: approved
provider_build_id: {manifest_provider_build_id}
calendar_policy_id: {manifest_calendar_policy_id}
""",
            encoding="utf-8",
        )

        # 4. minimum src tree so the helper's sys.path.insert(0, src) finds
        # the approval_evidence module. Create a symlink-equivalent by
        # copying via Path operations would be expensive; instead the
        # daily-QA helper inserts project_root/src into sys.path BUT
        # imports approval_evidence as `data_infra.approval_evidence`. We
        # need that import path to resolve — since we already imported it
        # for this test file from the real src/, it stays in sys.modules
        # and re-importing works.

    def test_approval_evidence_check_uses_configured_qlib_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Set storage.qlib_data_dir to a non-default subdirectory. The
        check must find the manifest there and report ok=True against a
        matched approval binding."""
        import sys
        import scripts.run_daily_qa as qa_module

        # The daily-QA helper does ``sys.path.insert(0, project_root / "src")``
        # and then ``from data_infra.approval_evidence import ...``. In tests
        # the project_root we pass is tmp_path (no src/ there), so we must
        # pre-load the real src/ onto sys.path or the import will fail. This
        # is exactly how the helper is intended to be invoked in production
        # (PROJECT_ROOT/src is the real src tree).
        real_src = Path(__file__).resolve().parent.parent.parent / "src"
        monkeypatch.syspath_prepend(str(real_src))

        # Inject a temp PROJECT_ROOT so the shared helper resolves into
        # tmp_path/<custom_qlib_subdir>, not the real data/qlib_data tree.
        custom = "tmp_qlib_data_for_pr10a"
        self._setup_temp_project(
            tmp_path,
            custom_qlib_subdir=custom,
            manifest_provider_build_id="bid_pr10a_match",
            manifest_calendar_policy_id="cp_pr10a_match",
        )

        # Drive the parameterised helper directly with the temp root. This
        # avoids monkey-patching the module-level PROJECT_ROOT and keeps
        # the test scope tight.
        result = qa_module._approval_evidence_binding_check(project_root=tmp_path)

        # Must have found the matching approval and reported ok.
        assert result["ok"] is True, (
            f"Expected ok=True, got {result!r}. The check must consume "
            f"config.yaml::storage.qlib_data_dir, not the hardcoded default."
        )
        assert result["n_approvals_with_binding"] == 1
        assert result["n_drifted"] == 0
        # Manifest path should reflect the configured qlib_data_dir, NOT
        # the legacy hardcoded data/qlib_data.
        assert custom in result["manifest_path"], (
            f"manifest_path={result['manifest_path']!r} did not include the "
            f"configured custom subdir {custom!r}; the helper is not consuming "
            "config.yaml::storage.qlib_data_dir."
        )

    def test_approval_evidence_check_surfaces_drift_against_configured_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Invert the manifest's provider_build_id. With the configured
        path resolution, the check must surface drift (ok=False), not
        silently revalidate against the hardcoded default."""
        import scripts.run_daily_qa as qa_module

        # Make the real src/ importable for the helper's sys.path dance.
        real_src = Path(__file__).resolve().parent.parent.parent / "src"
        monkeypatch.syspath_prepend(str(real_src))

        custom = "tmp_qlib_data_for_pr10a_drift"
        self._setup_temp_project(
            tmp_path,
            custom_qlib_subdir=custom,
            manifest_provider_build_id="bid_NEW_rebuild",   # ← drifted!
            manifest_calendar_policy_id="cp_pr10a_match",
        )
        # The approval YAML still pins the OLD build_id; rewrite it now to
        # carry "bid_OLD_evidence" so the drift is observable.
        approvals_dir = tmp_path / "config" / "field_registry" / "approvals"
        (approvals_dir / "2026-05-27_pr10a_behavioral.yaml").write_text(
            """approval_id: 2026-05-27_pr10a_behavioral
date: 2026-05-27
dataset_id: pr10a_drift_dataset
to_status: approved
provider_build_id: bid_OLD_evidence
calendar_policy_id: cp_pr10a_match
""",
            encoding="utf-8",
        )

        result = qa_module._approval_evidence_binding_check(project_root=tmp_path)

        assert result["ok"] is False
        assert result["n_drifted"] == 1
        # Diagnostic must name both declared (old) and current (new) ids.
        joined_reasons = " ".join(result.get("reasons", []))
        assert "bid_OLD_evidence" in joined_reasons
        assert "bid_NEW_rebuild" in joined_reasons
