"""Provider build manifest loader and validator.

The manifest lives at ``data/qlib_data/metadata/provider_build.json`` on each
host (the ``data/qlib_data/`` tree itself is gitignored). It exists because the
binary Qlib provider is intentionally excluded from version control, so the
repository alone cannot prove which provider was used to produce a given
formal research artifact. Every formal backtest, validation step, and registry
publication MUST record ``provider_build_id`` taken from this file.

Plan: PR 1 of the 2026-05-26 freeze plan.

Public surface
==============

* :class:`ProviderManifest` — frozen dataclass mirroring the on-disk JSON.
* :func:`load_provider_manifest` — load from disk; raises :class:`ProviderManifestError`
  on missing file, schema-incompatible content, or validation failure.
* :func:`validate_provider_manifest_against_qlib` — cross-check the manifest's
  ``calendar_end_date`` against the actual Qlib calendar; raises on mismatch
  unless the calendar policy explicitly permits it.
* :func:`emit_retroactive_manifest` — emit a ``retroactive_manifest=true``
  build.json for an already-published provider (used once to bootstrap the
  current 2026-04-21 build).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

PROVIDER_MANIFEST_SCHEMA_VERSION = 1
PROVIDER_MANIFEST_FILENAME = "provider_build.json"

DEFAULT_CANONICAL_KLINE_FIELDS_PROTECTED = (
    "$open", "$high", "$low", "$close", "$vol", "$amount",
)
DEFAULT_EVENT_NAMESPACED_DATASETS = (
    "top_list", "top_inst", "block_trade", "cyq_perf",
)


class ProviderManifestError(RuntimeError):
    """Raised when the provider manifest is missing, invalid, or inconsistent."""


@dataclass(frozen=True)
class ProviderBlock:
    path: str
    region: str
    calendar_start_date: str
    calendar_end_date: str
    data_end_date: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProviderBlock":
        return cls(
            path=str(payload["path"]),
            region=str(payload["region"]),
            calendar_start_date=str(payload["calendar_start_date"]),
            calendar_end_date=str(payload["calendar_end_date"]),
            data_end_date=str(payload["data_end_date"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "region": self.region,
            "calendar_start_date": self.calendar_start_date,
            "calendar_end_date": self.calendar_end_date,
            "data_end_date": self.data_end_date,
        }


@dataclass(frozen=True)
class EventNamespacingBlock:
    status: str
    affected_datasets: tuple[str, ...]
    prefix_rule: str
    canonical_kline_fields_protected: tuple[str, ...]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EventNamespacingBlock":
        return cls(
            status=str(payload["status"]),
            affected_datasets=tuple(str(x) for x in payload["affected_datasets"]),
            prefix_rule=str(payload["prefix_rule"]),
            canonical_kline_fields_protected=tuple(
                str(x) for x in payload["canonical_kline_fields_protected"]
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "affected_datasets": list(self.affected_datasets),
            "prefix_rule": self.prefix_rule,
            "canonical_kline_fields_protected": list(self.canonical_kline_fields_protected),
        }


@dataclass(frozen=True)
class ProviderManifest:
    schema_version: int
    provider_build_id: str
    provider_published_at: str
    calendar_policy_id: str
    provider: ProviderBlock
    event_endpoint_namespacing: EventNamespacingBlock
    downstream_revalidated_at: Optional[str] = None
    source_git_commit: Optional[str] = None
    builder: Optional[dict[str, Any]] = None
    canonical_kline_hash: Optional[dict[str, Any]] = None
    validation: Optional[dict[str, Any]] = None
    retroactive_manifest: bool = False
    retroactive_manifest_evidence: tuple[str, ...] = field(default_factory=tuple)
    # Phase 5-B (calendar unfreeze, B3.2): bind the published build to the exact raw-input
    # cut it consumed (sha256 root of the full-readset raw_input_manifest) and to its parent
    # build. OPTIONAL — pre-thaw manifests lack them and must keep loading; presence for
    # formal runs is enforced by the release gate when the calendar policy requires it
    # (require_raw_input_attestation), NOT by this loader.
    raw_input_manifest_root: Optional[str] = None
    parent_provider_build_id: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProviderManifest":
        try:
            schema_version = int(payload["schema_version"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderManifestError(
                f"Manifest missing or invalid schema_version: {exc}"
            ) from exc

        if schema_version != PROVIDER_MANIFEST_SCHEMA_VERSION:
            raise ProviderManifestError(
                f"Unsupported manifest schema_version={schema_version} "
                f"(expected {PROVIDER_MANIFEST_SCHEMA_VERSION})."
            )

        for required in (
            "provider_build_id",
            "provider_published_at",
            "calendar_policy_id",
            "provider",
            "event_endpoint_namespacing",
        ):
            if required not in payload:
                raise ProviderManifestError(f"Manifest missing required field: {required}")

        retroactive = bool(payload.get("retroactive_manifest", False))
        evidence = tuple(str(x) for x in payload.get("retroactive_manifest_evidence", ()))
        if retroactive and not evidence:
            raise ProviderManifestError(
                "retroactive_manifest=true requires a non-empty "
                "retroactive_manifest_evidence array."
            )

        # Phase 5-B: when present, raw_input_manifest_root must be a sha256 hex root — a
        # malformed value is a corrupted attestation, not a legacy manifest (fail closed).
        raw_root = payload.get("raw_input_manifest_root")
        if raw_root is not None:
            raw_root = str(raw_root)
            if len(raw_root) != 64 or any(c not in "0123456789abcdef" for c in raw_root):
                raise ProviderManifestError(
                    f"raw_input_manifest_root must be a 64-char lowercase sha256 hex root, "
                    f"got {raw_root!r}."
                )
        parent_build = payload.get("parent_provider_build_id")
        if parent_build is not None:
            parent_build = str(parent_build)
            if not parent_build.strip():
                raise ProviderManifestError(
                    "parent_provider_build_id, when present, must be a non-blank string."
                )

        return cls(
            schema_version=schema_version,
            provider_build_id=str(payload["provider_build_id"]),
            provider_published_at=str(payload["provider_published_at"]),
            calendar_policy_id=str(payload["calendar_policy_id"]),
            provider=ProviderBlock.from_dict(payload["provider"]),
            event_endpoint_namespacing=EventNamespacingBlock.from_dict(
                payload["event_endpoint_namespacing"]
            ),
            downstream_revalidated_at=(
                str(payload["downstream_revalidated_at"])
                if payload.get("downstream_revalidated_at") is not None
                else None
            ),
            source_git_commit=(
                str(payload["source_git_commit"])
                if payload.get("source_git_commit") is not None
                else None
            ),
            builder=payload.get("builder"),
            canonical_kline_hash=payload.get("canonical_kline_hash"),
            validation=payload.get("validation"),
            retroactive_manifest=retroactive,
            retroactive_manifest_evidence=evidence,
            raw_input_manifest_root=raw_root,
            parent_provider_build_id=parent_build,
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema_version": self.schema_version,
            "provider_build_id": self.provider_build_id,
            "provider_published_at": self.provider_published_at,
            "downstream_revalidated_at": self.downstream_revalidated_at,
            "source_git_commit": self.source_git_commit,
            "builder": self.builder,
            "calendar_policy_id": self.calendar_policy_id,
            "provider": self.provider.to_dict(),
            "event_endpoint_namespacing": self.event_endpoint_namespacing.to_dict(),
            "canonical_kline_hash": self.canonical_kline_hash,
            "validation": self.validation,
            "retroactive_manifest": self.retroactive_manifest,
        }
        if self.retroactive_manifest:
            out["retroactive_manifest_evidence"] = list(self.retroactive_manifest_evidence)
        # Emit the Phase 5-B attestation bindings only when present, so pre-thaw manifests
        # round-trip byte-stable (schema keeps them optional).
        if self.raw_input_manifest_root is not None:
            out["raw_input_manifest_root"] = self.raw_input_manifest_root
        if self.parent_provider_build_id is not None:
            out["parent_provider_build_id"] = self.parent_provider_build_id
        return out


def manifest_path_for(qlib_dir: str | os.PathLike[str]) -> Path:
    """Canonical manifest location for a given Qlib provider directory."""
    return Path(qlib_dir) / "metadata" / PROVIDER_MANIFEST_FILENAME


def load_provider_manifest(qlib_dir: str | os.PathLike[str]) -> ProviderManifest:
    """Load and validate the provider manifest for ``qlib_dir``.

    Raises :class:`ProviderManifestError` if the file is missing, schema-incompatible,
    or fails internal consistency checks (e.g., retroactive_manifest without evidence).
    """
    path = manifest_path_for(qlib_dir)
    if not path.exists():
        raise ProviderManifestError(
            f"Provider manifest not found at {path}. "
            "Formal runs require a provider_build.json. Emit one via "
            "src.data_infra.provider_manifest.emit_retroactive_manifest(...) "
            "for an already-published provider, or via the build pipeline."
        )

    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ProviderManifestError(f"Failed to read manifest at {path}: {exc}") from exc

    return ProviderManifest.from_dict(payload)


def validate_provider_manifest_against_qlib(
    manifest: ProviderManifest,
    qlib_calendar_end_date: str,
    *,
    allow_calendar_mismatch: bool = False,
) -> None:
    """Cross-check the manifest against the live Qlib calendar.

    Args:
        manifest: ProviderManifest loaded from disk.
        qlib_calendar_end_date: ``D.calendar()[-1].strftime('%Y-%m-%d')``.
        allow_calendar_mismatch: When True (typically supplied by the calendar
            policy), a mismatch is logged but does not raise.

    Raises:
        ProviderManifestError: When namespacing is not enforced, or when the
            calendar mismatches and ``allow_calendar_mismatch`` is False.
    """
    if manifest.event_endpoint_namespacing.status != "enforced":
        raise ProviderManifestError(
            "Provider manifest reports event_endpoint_namespacing.status="
            f"{manifest.event_endpoint_namespacing.status!r} (expected 'enforced'). "
            "Formal research requires a namespace-correct provider. Rebuild via "
            "scripts/audit_qlib.py + build_qlib_backend.py and re-emit the manifest."
        )

    if manifest.provider.calendar_end_date != qlib_calendar_end_date:
        message = (
            f"Manifest calendar_end_date={manifest.provider.calendar_end_date} "
            f"does not match live Qlib calendar end {qlib_calendar_end_date}. "
            "Either rebuild the provider or load the appropriate calendar policy."
        )
        if allow_calendar_mismatch:
            logger.warning("calendar policy permits mismatch: %s", message)
            return
        raise ProviderManifestError(message)


def compute_canonical_kline_hash(
    *,
    sentinel_instruments: Iterable[str],
    sentinel_dates: Iterable[str],
    fields: Iterable[str] = DEFAULT_CANONICAL_KLINE_FIELDS_PROTECTED,
    qlib_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Compute a tamper-evidence hash over a small fixed set of D.features readings.

    The function defers the ``qlib`` import to keep this module importable
    without a live provider. Returns a dict ready to slot into
    ``provider_build.json``'s ``canonical_kline_hash`` field.
    """
    import pandas as pd
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D

    if qlib_dir is not None:
        qlib.init(provider_uri=str(qlib_dir), region=REG_CN, kernels=1)

    instruments = sorted(sentinel_instruments)
    dates = sorted(sentinel_dates)
    fields_t = tuple(fields)

    payload_parts: list[str] = []
    for inst in instruments:
        for date in dates:
            try:
                # noqa: bare-qlib-features — privileged admin call computing the
                # provider attestation hash itself. Intentionally bypasses
                # qlib_windowed_features (no ResearchAccessContext applies to a
                # provider-attestation operation; it runs at manifest-emit time,
                # outside any research stage).
                frame = D.features([inst], list(fields_t), start_time=date, end_time=date)  # noqa: bare-qlib-features
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("sentinel read failed for %s @ %s: %s", inst, date, exc)
                payload_parts.append(f"{inst}|{date}|UNREADABLE")
                continue
            if frame.empty:
                payload_parts.append(f"{inst}|{date}|EMPTY")
                continue
            for f in fields_t:
                value = frame.iloc[0].get(f, None) if f in frame.columns else None
                if value is None or (isinstance(value, float) and pd.isna(value)):
                    payload_parts.append(f"{inst}|{date}|{f}|NA")
                else:
                    payload_parts.append(f"{inst}|{date}|{f}|{float(value):.10f}")

    canonical = "\n".join(payload_parts).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    return {
        "method": "sha256_over_selected_sentinel_D_features",
        "sentinel_instruments": instruments,
        "sentinel_dates": dates,
        "sha256": digest,
    }


def emit_retroactive_manifest(
    *,
    qlib_dir: str | os.PathLike[str],
    provider_build_id: str,
    provider_published_at: str,
    downstream_revalidated_at: Optional[str],
    calendar_policy_id: str,
    calendar_start_date: str,
    calendar_end_date: str,
    data_end_date: str,
    evidence: Iterable[str],
    namespacing_status: str = "enforced",
    affected_datasets: Iterable[str] = DEFAULT_EVENT_NAMESPACED_DATASETS,
    canonical_kline_fields_protected: Iterable[str] = DEFAULT_CANONICAL_KLINE_FIELDS_PROTECTED,
    canonical_kline_hash: Optional[dict[str, Any]] = None,
    validation: Optional[dict[str, Any]] = None,
    region: str = "REG_CN",
    builder_entrypoint: str = "src/data_infra/pipeline/build_qlib_backend.py",
    builder_mode: str = "all",
    builder_stage: str = "full",
    source_git_commit: Optional[str] = None,
) -> Path:
    """Emit a retroactive manifest for a provider that was published before the
    manifest contract existed. Used once to bootstrap the existing 2026-04-21
    build.

    The function performs an atomic write (temp file + os.replace) so concurrent
    readers never see a partial JSON file.
    """
    qlib_dir = Path(qlib_dir)
    evidence_list = [str(e) for e in evidence]
    if not evidence_list:
        raise ProviderManifestError(
            "emit_retroactive_manifest requires a non-empty evidence iterable."
        )

    manifest = ProviderManifest(
        schema_version=PROVIDER_MANIFEST_SCHEMA_VERSION,
        provider_build_id=provider_build_id,
        provider_published_at=provider_published_at,
        downstream_revalidated_at=downstream_revalidated_at,
        source_git_commit=source_git_commit,
        builder={
            "entrypoint": builder_entrypoint,
            "builder_version": None,
            "mode": builder_mode,
            "stage": builder_stage,
        },
        calendar_policy_id=calendar_policy_id,
        provider=ProviderBlock(
            path=str(qlib_dir).replace("\\", "/"),
            region=region,
            calendar_start_date=calendar_start_date,
            calendar_end_date=calendar_end_date,
            data_end_date=data_end_date,
        ),
        event_endpoint_namespacing=EventNamespacingBlock(
            status=namespacing_status,
            affected_datasets=tuple(affected_datasets),
            prefix_rule="{dataset}__{column}",
            canonical_kline_fields_protected=tuple(canonical_kline_fields_protected),
        ),
        canonical_kline_hash=canonical_kline_hash,
        validation=validation,
        retroactive_manifest=True,
        retroactive_manifest_evidence=tuple(evidence_list),
    )

    target = manifest_path_for(qlib_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + f".tmp.{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(manifest.to_dict(), handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, target)
    logger.info("Wrote retroactive provider manifest to %s", target)
    return target


def emit_manifest_at_publish(
    *,
    qlib_dir: str | os.PathLike[str],
    provider_build_id: str,
    calendar_policy_id: str,
    calendar_start_date: str,
    calendar_end_date: str,
    data_end_date: str,
    source_git_commit: Optional[str] = None,
    builder_mode: str = "all",
    builder_stage: str = "full",
    canonical_kline_hash: Optional[dict[str, Any]] = None,
    validation: Optional[dict[str, Any]] = None,
    raw_input_manifest_root: Optional[str] = None,
    parent_provider_build_id: Optional[str] = None,
) -> Path:
    """Emit a fresh manifest for a provider that is being published right now.

    Called from the builder's ``publish()`` path after the atomic os.replace().
    Distinct from :func:`emit_retroactive_manifest` because no evidence array
    is required (the manifest is being produced contemporaneously with the
    publish).

    ``raw_input_manifest_root`` / ``parent_provider_build_id`` (Phase 5-B B3.2)
    bind the published build to the attested raw-input cut and its parent build;
    the monthly atomic publish transaction supplies them, legacy callers omit.
    """
    qlib_dir = Path(qlib_dir)
    now_iso = datetime.utcnow().replace(microsecond=0).isoformat()

    manifest = ProviderManifest(
        schema_version=PROVIDER_MANIFEST_SCHEMA_VERSION,
        provider_build_id=provider_build_id,
        provider_published_at=now_iso,
        downstream_revalidated_at=None,
        source_git_commit=source_git_commit,
        builder={
            "entrypoint": "src/data_infra/pipeline/build_qlib_backend.py",
            "builder_version": None,
            "mode": builder_mode,
            "stage": builder_stage,
        },
        calendar_policy_id=calendar_policy_id,
        provider=ProviderBlock(
            path=str(qlib_dir).replace("\\", "/"),
            region="REG_CN",
            calendar_start_date=calendar_start_date,
            calendar_end_date=calendar_end_date,
            data_end_date=data_end_date,
        ),
        event_endpoint_namespacing=EventNamespacingBlock(
            status="enforced",
            affected_datasets=DEFAULT_EVENT_NAMESPACED_DATASETS,
            prefix_rule="{dataset}__{column}",
            canonical_kline_fields_protected=DEFAULT_CANONICAL_KLINE_FIELDS_PROTECTED,
        ),
        canonical_kline_hash=canonical_kline_hash,
        validation=validation,
        retroactive_manifest=False,
        raw_input_manifest_root=raw_input_manifest_root,
        parent_provider_build_id=parent_provider_build_id,
    )

    target = manifest_path_for(qlib_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + f".tmp.{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(manifest.to_dict(), handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, target)
    logger.info("Wrote provider manifest to %s", target)
    return target
