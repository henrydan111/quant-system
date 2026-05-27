"""Artifact provenance block stamped onto every formal research artifact.

Starting with PR 1, every formal ``BacktestResult.config``, validation step
output, and registry publication carries an ``ArtifactProvenance`` block.
Older artifacts that pre-date this contract are read back as
``legacy_artifact=True``; they remain viewable for historical comparison but
cannot pass formal release gates.

This module is intentionally minimal in PR 1 — fields covering
``execution_profile_*`` are filled in by PR 3 (Versioned Execution Profiles).
The schema and reader contract land now so subsequent PRs can extend without
breaking older artifacts.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

PROVENANCE_SCHEMA_VERSION = 1
PROVENANCE_KEY = "artifact_provenance"


class ArtifactProvenanceError(RuntimeError):
    """Raised when a provenance block is malformed."""


@dataclass(frozen=True)
class ArtifactProvenance:
    """Provenance fields stamped onto formal artifacts.

    ``legacy_artifact`` is True when one or more of the formal fields below
    is missing on disk. Legacy artifacts can be viewed and compared
    historically; they cannot pass the formal release gate.
    """
    provenance_schema_version: int = PROVENANCE_SCHEMA_VERSION
    legacy_artifact: bool = False
    provider_build_id: Optional[str] = None
    calendar_policy_id: Optional[str] = None
    execution_profile_id: Optional[str] = None
    execution_profile_version: Optional[str] = None
    execution_profile_hash: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "ArtifactProvenance":
        """Read a provenance block back.

        ``None`` or missing/empty payload returns a ``legacy_artifact=True``
        instance — the caller can still display it but the release gate will
        reject it for formal eligibility.
        """
        if payload is None:
            return cls(legacy_artifact=True)
        if not isinstance(payload, Mapping):
            raise ArtifactProvenanceError(
                f"Expected provenance payload to be a mapping, got {type(payload).__name__}"
            )

        version = int(payload.get("provenance_schema_version", 0) or 0)
        if version == 0:
            return cls(legacy_artifact=True)
        if version > PROVENANCE_SCHEMA_VERSION:
            raise ArtifactProvenanceError(
                f"Artifact provenance schema_version={version} is newer than "
                f"reader version={PROVENANCE_SCHEMA_VERSION}. Upgrade the reader."
            )

        # If any of the formal-mandatory fields is missing/None, the artifact
        # is treated as legacy regardless of how the producer flagged it.
        provider_build_id = payload.get("provider_build_id")
        calendar_policy_id = payload.get("calendar_policy_id")
        formal_complete = bool(provider_build_id) and bool(calendar_policy_id)
        legacy = bool(payload.get("legacy_artifact", False)) or not formal_complete

        return cls(
            provenance_schema_version=version,
            legacy_artifact=legacy,
            provider_build_id=provider_build_id,
            calendar_policy_id=calendar_policy_id,
            execution_profile_id=payload.get("execution_profile_id"),
            execution_profile_version=payload.get("execution_profile_version"),
            execution_profile_hash=payload.get("execution_profile_hash"),
        )

    def is_formal_eligible(self) -> tuple[bool, list[str]]:
        """Return (eligible, reasons) — reasons is empty when eligible.

        PR 1: requires provider_build_id and calendar_policy_id.
        PR 3 will extend this to additionally require execution_profile_*.
        """
        reasons: list[str] = []
        if self.legacy_artifact:
            reasons.append("legacy_artifact=true")
        if not self.provider_build_id:
            reasons.append("missing_provider_build_id")
        if not self.calendar_policy_id:
            reasons.append("missing_calendar_policy_id")
        return (len(reasons) == 0, reasons)


def attach_provenance(
    artifact_config: dict[str, Any],
    provenance: ArtifactProvenance,
) -> dict[str, Any]:
    """Attach a provenance block under the canonical key.

    Mutates and returns the artifact config dict so callers can chain.
    """
    artifact_config[PROVENANCE_KEY] = provenance.to_dict()
    return artifact_config


def read_provenance(artifact_config: Mapping[str, Any] | None) -> ArtifactProvenance:
    """Read a provenance block from an artifact config dict.

    Missing key or missing artifact returns ``legacy_artifact=True`` — readers
    can still display historical results, but :meth:`is_formal_eligible` will
    return False with reason ``legacy_artifact=true``.
    """
    if artifact_config is None:
        return ArtifactProvenance.from_dict(None)
    return ArtifactProvenance.from_dict(artifact_config.get(PROVENANCE_KEY))


def read_provenance_from_json(path: str | Path) -> ArtifactProvenance:
    """Convenience: read provenance from a JSON artifact file."""
    p = Path(path)
    if not p.exists():
        return ArtifactProvenance.from_dict(None)
    try:
        with open(p, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return ArtifactProvenance.from_dict(None)
    if not isinstance(payload, dict):
        return ArtifactProvenance.from_dict(None)
    return read_provenance(payload)
