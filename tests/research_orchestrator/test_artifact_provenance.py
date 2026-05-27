"""Negative-test suite for artifact_provenance + release-gate enforcement (PR 1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.research_orchestrator.artifact_provenance import (
    PROVENANCE_KEY,
    PROVENANCE_SCHEMA_VERSION,
    ArtifactProvenance,
    ArtifactProvenanceError,
    attach_provenance,
    read_provenance,
    read_provenance_from_json,
)
from src.research_orchestrator.release_gate import (
    assert_formal_artifact_eligible,
    evaluate_artifact_provenance,
)


def _complete_provenance() -> ArtifactProvenance:
    return ArtifactProvenance(
        provenance_schema_version=PROVENANCE_SCHEMA_VERSION,
        legacy_artifact=False,
        provider_build_id="prod_test_001",
        calendar_policy_id="frozen_20260227_system_build",
    )


class TestArtifactProvenanceClassification:
    def test_none_payload_is_legacy(self) -> None:
        provenance = ArtifactProvenance.from_dict(None)
        assert provenance.legacy_artifact is True
        eligible, reasons = provenance.is_formal_eligible()
        assert eligible is False
        assert "legacy_artifact=true" in reasons

    def test_missing_provider_build_id_is_legacy(self) -> None:
        provenance = ArtifactProvenance.from_dict(
            {
                "provenance_schema_version": PROVENANCE_SCHEMA_VERSION,
                "calendar_policy_id": "frozen_20260227_system_build",
            }
        )
        assert provenance.legacy_artifact is True
        eligible, reasons = provenance.is_formal_eligible()
        assert eligible is False
        assert "missing_provider_build_id" in reasons

    def test_missing_calendar_policy_id_is_legacy(self) -> None:
        provenance = ArtifactProvenance.from_dict(
            {
                "provenance_schema_version": PROVENANCE_SCHEMA_VERSION,
                "provider_build_id": "prod_test_001",
            }
        )
        assert provenance.legacy_artifact is True

    def test_complete_provenance_is_eligible(self) -> None:
        provenance = _complete_provenance()
        eligible, reasons = provenance.is_formal_eligible()
        assert eligible is True
        assert reasons == []

    def test_newer_schema_raises(self) -> None:
        with pytest.raises(ArtifactProvenanceError, match="newer than reader"):
            ArtifactProvenance.from_dict(
                {
                    "provenance_schema_version": PROVENANCE_SCHEMA_VERSION + 99,
                    "provider_build_id": "prod_test_001",
                    "calendar_policy_id": "frozen_20260227_system_build",
                }
            )

    def test_zero_schema_is_legacy(self) -> None:
        provenance = ArtifactProvenance.from_dict({"provenance_schema_version": 0})
        assert provenance.legacy_artifact is True


class TestArtifactGateEnforcement:
    def test_complete_artifact_passes_gate(self) -> None:
        config: dict = {}
        attach_provenance(config, _complete_provenance())
        result = evaluate_artifact_provenance(config)
        assert result.eligible is True
        assert result.status == "passed"
        assert result.reasons == ()

    def test_legacy_artifact_fails_with_failed_legacy_status(self) -> None:
        # Pre-PR1 artifact: config has no provenance block at all.
        config: dict = {"initial_cash": 100_000, "n_days": 1950}
        result = evaluate_artifact_provenance(config)
        assert result.eligible is False
        assert result.status == "failed_legacy"
        assert result.legacy_artifact is True

    def test_missing_calendar_policy_fails_gate(self) -> None:
        config: dict = {}
        attach_provenance(
            config,
            ArtifactProvenance(provider_build_id="prod_test_001"),
        )
        result = evaluate_artifact_provenance(config)
        assert result.eligible is False
        assert "missing_calendar_policy_id" in result.reasons

    def test_assert_formal_artifact_eligible_raises(self) -> None:
        config: dict = {}
        attach_provenance(
            config,
            ArtifactProvenance(provider_build_id="prod_test_001"),
        )
        with pytest.raises(ValueError, match="Formal release blocked"):
            assert_formal_artifact_eligible(config, artifact_label="test_artifact")

    def test_assert_formal_artifact_eligible_passes(self) -> None:
        config: dict = {}
        attach_provenance(config, _complete_provenance())
        result = assert_formal_artifact_eligible(config)
        assert result.eligible is True


class TestArtifactProvenanceRoundTrip:
    def test_attach_and_read(self) -> None:
        config: dict = {}
        attached = attach_provenance(config, _complete_provenance())
        # attach mutates and returns the same dict
        assert attached is config
        assert PROVENANCE_KEY in config
        roundtripped = read_provenance(config)
        assert roundtripped.provider_build_id == "prod_test_001"
        assert roundtripped.calendar_policy_id == "frozen_20260227_system_build"
        assert roundtripped.legacy_artifact is False

    def test_read_from_json_missing_file_is_legacy(self, tmp_path: Path) -> None:
        provenance = read_provenance_from_json(tmp_path / "nope.json")
        assert provenance.legacy_artifact is True

    def test_read_from_json_corrupt_file_is_legacy(self, tmp_path: Path) -> None:
        path = tmp_path / "artifact.json"
        path.write_text("not json {", encoding="utf-8")
        provenance = read_provenance_from_json(path)
        assert provenance.legacy_artifact is True

    def test_read_from_json_complete_file(self, tmp_path: Path) -> None:
        path = tmp_path / "artifact.json"
        config: dict = {"initial_cash": 100_000}
        attach_provenance(config, _complete_provenance())
        path.write_text(json.dumps(config), encoding="utf-8")
        provenance = read_provenance_from_json(path)
        assert provenance.legacy_artifact is False
        assert provenance.provider_build_id == "prod_test_001"
