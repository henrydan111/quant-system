"""Negative-test suite for the provider manifest contract (PR 1).

Every gate documented in PR 1 has at least one negative test here. Positive
paths are covered by the integration smoke at the end.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.data_infra.provider_manifest import (
    PROVIDER_MANIFEST_FILENAME,
    PROVIDER_MANIFEST_SCHEMA_VERSION,
    ProviderManifest,
    ProviderManifestError,
    emit_retroactive_manifest,
    load_provider_manifest,
    manifest_path_for,
    validate_provider_manifest_against_qlib,
)


def _write_manifest(qlib_dir: Path, payload: dict) -> Path:
    path = manifest_path_for(qlib_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _valid_payload(**overrides) -> dict:
    base = {
        "schema_version": PROVIDER_MANIFEST_SCHEMA_VERSION,
        "provider_build_id": "test_build_001",
        "provider_published_at": "2026-04-21T00:00:00",
        "downstream_revalidated_at": "2026-04-23T00:00:00",
        "source_git_commit": "deadbeef",
        "builder": {
            "entrypoint": "src/data_infra/pipeline/build_qlib_backend.py",
            "builder_version": None,
            "mode": "all",
            "stage": "full",
        },
        "calendar_policy_id": "frozen_20260227_system_build",
        "provider": {
            "path": "data/qlib_data",
            "region": "REG_CN",
            "calendar_start_date": "2008-01-02",
            "calendar_end_date": "2026-02-27",
            "data_end_date": "2026-02-27",
        },
        "event_endpoint_namespacing": {
            "status": "enforced",
            "affected_datasets": ["top_list", "top_inst", "block_trade", "cyq_perf"],
            "prefix_rule": "{dataset}__{column}",
            "canonical_kline_fields_protected": [
                "$open", "$high", "$low", "$close", "$vol", "$amount",
            ],
        },
        "canonical_kline_hash": None,
        "validation": None,
        "retroactive_manifest": False,
    }
    base.update(overrides)
    return base


class TestRawInputAttestationFields:
    """Phase 5-B B3.2: raw_input_manifest_root + parent_provider_build_id are OPTIONAL
    (pre-thaw manifests keep loading) but validated when present, and round-trip."""

    def test_legacy_manifest_without_fields_loads_as_none(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, _valid_payload())
        manifest = load_provider_manifest(tmp_path)
        assert manifest.raw_input_manifest_root is None
        assert manifest.parent_provider_build_id is None
        # and to_dict does NOT invent the keys (legacy round-trip stability)
        d = manifest.to_dict()
        assert "raw_input_manifest_root" not in d
        assert "parent_provider_build_id" not in d

    def test_attested_manifest_roundtrips(self, tmp_path: Path) -> None:
        root = "ab" * 32
        _write_manifest(tmp_path, _valid_payload(
            raw_input_manifest_root=root, parent_provider_build_id="parent_build_1"))
        manifest = load_provider_manifest(tmp_path)
        assert manifest.raw_input_manifest_root == root
        assert manifest.parent_provider_build_id == "parent_build_1"
        d = manifest.to_dict()
        assert d["raw_input_manifest_root"] == root
        assert d["parent_provider_build_id"] == "parent_build_1"

    def test_malformed_raw_root_fails_closed(self, tmp_path: Path) -> None:
        # A present-but-garbage attestation is corruption, not legacy — must raise.
        _write_manifest(tmp_path, _valid_payload(raw_input_manifest_root="not-a-hash"))
        with pytest.raises(ProviderManifestError, match="raw_input_manifest_root"):
            load_provider_manifest(tmp_path)
        _write_manifest(tmp_path, _valid_payload(raw_input_manifest_root="AB" * 32))  # uppercase
        with pytest.raises(ProviderManifestError, match="raw_input_manifest_root"):
            load_provider_manifest(tmp_path)

    def test_blank_parent_build_id_fails_closed(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, _valid_payload(parent_provider_build_id="  "))
        with pytest.raises(ProviderManifestError, match="parent_provider_build_id"):
            load_provider_manifest(tmp_path)


class TestProviderManifestLoadErrors:
    """Negative path: missing/malformed manifest must raise."""

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ProviderManifestError, match="not found"):
            load_provider_manifest(tmp_path)

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        path = manifest_path_for(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json {", encoding="utf-8")
        with pytest.raises(ProviderManifestError, match="Failed to read manifest"):
            load_provider_manifest(tmp_path)

    def test_wrong_schema_version_raises(self, tmp_path: Path) -> None:
        payload = _valid_payload(schema_version=999)
        _write_manifest(tmp_path, payload)
        with pytest.raises(ProviderManifestError, match="schema_version"):
            load_provider_manifest(tmp_path)

    def test_missing_required_field_raises(self, tmp_path: Path) -> None:
        payload = _valid_payload()
        del payload["provider_build_id"]
        _write_manifest(tmp_path, payload)
        with pytest.raises(ProviderManifestError, match="provider_build_id"):
            load_provider_manifest(tmp_path)

    def test_retroactive_without_evidence_raises(self, tmp_path: Path) -> None:
        payload = _valid_payload(retroactive_manifest=True)
        _write_manifest(tmp_path, payload)
        with pytest.raises(ProviderManifestError, match="retroactive_manifest"):
            load_provider_manifest(tmp_path)


class TestProviderManifestValidation:
    """Cross-checks against the live Qlib calendar."""

    def test_namespacing_unenforced_raises(self, tmp_path: Path) -> None:
        payload = _valid_payload()
        payload["event_endpoint_namespacing"]["status"] = "unenforced"
        _write_manifest(tmp_path, payload)
        manifest = load_provider_manifest(tmp_path)
        with pytest.raises(ProviderManifestError, match="namespacing"):
            validate_provider_manifest_against_qlib(manifest, "2026-02-27")

    def test_calendar_mismatch_raises_when_disallowed(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, _valid_payload())
        manifest = load_provider_manifest(tmp_path)
        with pytest.raises(ProviderManifestError, match="calendar_end_date"):
            validate_provider_manifest_against_qlib(
                manifest, "2026-05-01", allow_calendar_mismatch=False
            )

    def test_calendar_mismatch_logged_when_allowed(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, _valid_payload())
        manifest = load_provider_manifest(tmp_path)
        # Should not raise when explicitly permitted by calendar policy.
        validate_provider_manifest_against_qlib(
            manifest, "2026-05-01", allow_calendar_mismatch=True
        )

    def test_calendar_match_passes(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, _valid_payload())
        manifest = load_provider_manifest(tmp_path)
        validate_provider_manifest_against_qlib(manifest, "2026-02-27")


class TestEmitRetroactiveManifest:
    """Bootstrap path for the existing 2026-04-21 build."""

    def test_emits_atomically_with_evidence(self, tmp_path: Path) -> None:
        target = emit_retroactive_manifest(
            qlib_dir=tmp_path,
            provider_build_id="prod_test_001",
            provider_published_at="2026-04-21T00:00:00",
            downstream_revalidated_at="2026-04-23T00:00:00",
            calendar_policy_id="frozen_20260227_system_build",
            calendar_start_date="2008-01-02",
            calendar_end_date="2026-02-27",
            data_end_date="2026-02-27",
            evidence=("README snapshot", "project_state revalidation note"),
        )
        assert target.exists()
        loaded = load_provider_manifest(tmp_path)
        assert loaded.retroactive_manifest is True
        assert len(loaded.retroactive_manifest_evidence) == 2

    def test_emit_rejects_empty_evidence(self, tmp_path: Path) -> None:
        with pytest.raises(ProviderManifestError, match="evidence"):
            emit_retroactive_manifest(
                qlib_dir=tmp_path,
                provider_build_id="prod_test_002",
                provider_published_at="2026-04-21T00:00:00",
                downstream_revalidated_at=None,
                calendar_policy_id="frozen_20260227_system_build",
                calendar_start_date="2008-01-02",
                calendar_end_date="2026-02-27",
                data_end_date="2026-02-27",
                evidence=(),
            )


class TestLiveManifestIntegration:
    """Live manifest at data/qlib_data/metadata/provider_build.json."""

    def test_live_manifest_loads(self) -> None:
        # Skip when running on a host without the published provider.
        live_dir = Path("data/qlib_data")
        if not manifest_path_for(live_dir).exists():
            pytest.skip("No live provider manifest on this host")
        manifest = load_provider_manifest(live_dir)
        assert manifest.schema_version == PROVIDER_MANIFEST_SCHEMA_VERSION
        assert manifest.event_endpoint_namespacing.status == "enforced"
        assert manifest.calendar_policy_id  # non-empty
