"""Provider-build binding checks for field-registry approval YAMLs.

PR 10 follow-up to the 2026-05-26 freeze plan (after PR 9c merged): every
approval YAML under ``config/field_registry/approvals/`` that promotes a
dataset to a new status records a ``provider_build_id`` +
``calendar_policy_id`` binding pinning the on-disk evidence to a specific
Qlib provider build. This module reads those bindings and compares them
against the current ``data/qlib_data/metadata/provider_build.json``
manifest, so a future provider rebuild whose ``provider_build_id`` differs
from any approval's binding surfaces as a drift report rather than
silently revalidating the approval.

Why this matters
================

The PR 9a round-3 indicators approval YAML pinned
``provider_build_id: prod_full_20260421_namespace_v1`` and
``calendar_policy_id: frozen_20260227_system_build`` as evidence that the
on-disk verification was performed against that specific build. The
approval YAML's ``notes`` block states explicitly that "future provider
rebuild whose calendar_policy_id or provider_build_id differs from these
values means the approval evidence must be re-verified before formal use."

Pre-PR-10 that contract was operator-discipline only. PR 10 adds a
machine check so a stale approval is surfaced automatically.

Wired into
==========

- ``scripts/run_daily_qa.py``: new ``approval_evidence_binding`` audit
  block. Fails the daily QA on any drift with a precise diagnostic.
- ``src/research_orchestrator/release_gate.py``: callers can use
  :func:`evaluate_approval_evidence_bindings` (returns drift records) or
  :func:`assert_no_approval_evidence_drift` (raises on drift) when
  publishing a formal artifact whose dataset dependencies overlap with
  approved field-registry datasets.

Schema contract (PR 10a + PR 10b)
=================================

Each approval YAML under ``config/field_registry/approvals/`` is held to
the following contract (enforced by :func:`load_approval_bindings`):

  * Modern approval YAMLs MUST carry BOTH ``provider_build_id`` AND
    ``calendar_policy_id`` keys with non-empty string values.
  * Legacy YAMLs predating the PR 9a round-3 binding contract may omit
    BOTH keys; they are silently skipped because they cannot be
    validated.
  * Partial (exactly one key), null / empty / blank / non-string valued,
    malformed (unparseable), or non-mapping YAMLs FAIL daily QA with
    :class:`ApprovalEvidenceConfigError`. None of these can silently
    disappear from the drift scan.

The schema documentation lives at
``config/field_registry/approvals/README.md``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


# Canonical default locations (relative to project root). Tests typically
# inject explicit paths.
DEFAULT_APPROVALS_DIR = Path("config/field_registry/approvals")
DEFAULT_PROVIDER_MANIFEST = Path("data/qlib_data/metadata/provider_build.json")


class ApprovalEvidenceDriftError(RuntimeError):
    """Raised by :func:`assert_no_approval_evidence_drift` on any drift."""


class ApprovalEvidenceConfigError(RuntimeError):
    """Raised by :func:`load_approval_bindings` on malformed approval YAMLs.

    PR 10a (post-PR-10 review): pre-PR-10a the scanner logged a warning
    and silently skipped (a) YAMLs that failed to parse, (b) YAMLs whose
    top level was not a mapping, and (c) YAMLs declaring exactly one of
    ``provider_build_id`` / ``calendar_policy_id`` (treated as wildcard
    on the missing axis). All three are fail-open paths for a governance
    artifact and PR 10a converts them to hard failures. Legacy YAMLs
    with BOTH binding keys absent are still silently skipped because
    they predate the binding contract."""


@dataclass(frozen=True)
class ApprovalBinding:
    """A single approval YAML's binding to a provider build + calendar policy.

    Fields with ``None`` values mean the source YAML did not declare that
    key. Bindings with BOTH declared values None are filtered out by
    :func:`load_approval_bindings` (treated as legacy / pre-contract).
    """

    approval_id: str
    approval_file: str
    dataset_id: str
    to_status: str
    date: str
    declared_provider_build_id: str | None
    declared_calendar_policy_id: str | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ApprovalBindingDrift:
    """Per-approval drift record produced by
    :func:`evaluate_approval_evidence_bindings`.

    ``drift=True`` means at least one of the declared bindings does not
    match the current manifest. Operators consume the ``reasons`` list
    for diagnostics; release-gate callers consume the boolean ``drift``.
    """

    binding: ApprovalBinding
    current_provider_build_id: str | None
    current_calendar_policy_id: str | None
    provider_build_id_match: bool
    calendar_policy_id_match: bool

    @property
    def drift(self) -> bool:
        return not (self.provider_build_id_match and self.calendar_policy_id_match)

    def reasons(self) -> list[str]:
        out: list[str] = []
        if not self.provider_build_id_match:
            out.append(
                f"{self.binding.approval_id}: dataset={self.binding.dataset_id!r} "
                f"declared provider_build_id="
                f"{self.binding.declared_provider_build_id!r} but current="
                f"{self.current_provider_build_id!r}"
            )
        if not self.calendar_policy_id_match:
            out.append(
                f"{self.binding.approval_id}: dataset={self.binding.dataset_id!r} "
                f"declared calendar_policy_id="
                f"{self.binding.declared_calendar_policy_id!r} but current="
                f"{self.current_calendar_policy_id!r}"
            )
        return out

    def to_dict(self) -> dict:
        return {
            **self.binding.to_dict(),
            "current_provider_build_id": self.current_provider_build_id,
            "current_calendar_policy_id": self.current_calendar_policy_id,
            "provider_build_id_match": self.provider_build_id_match,
            "calendar_policy_id_match": self.calendar_policy_id_match,
            "drift": self.drift,
            "reasons": self.reasons(),
        }


def load_approval_bindings(
    approvals_dir: Path | str = DEFAULT_APPROVALS_DIR,
) -> list[ApprovalBinding]:
    """Scan an approvals directory for YAML files and extract bindings.

    Contract (PR 10a, hardened by PR 10b):

      * BOTH ``provider_build_id`` AND ``calendar_policy_id`` keys absent
        → legacy approval, silently skipped.
      * BOTH binding keys present with non-empty string values →
        validated.
      * Exactly ONE key present → :class:`ApprovalEvidenceConfigError` —
        partial bindings would silently reduce the contract from two
        dimensions to one (wildcard on the missing axis), a fail-open
        path that PR 10a removes.
      * BOTH keys present but EITHER value is null / empty / blank /
        non-string → :class:`ApprovalEvidenceConfigError` (PR 10b). Pre-PR-10b
        ``data.get(...)`` collapsed "key absent" and "key present with
        null value" into the same ``None``, so a YAML that kept the keys
        but blanked their values (e.g. during a manual provider rebuild)
        was silently skipped as legacy — a fail-open path PR 10b closes.

    Other fail-closed conditions:

      * YAML parse failure → :class:`ApprovalEvidenceConfigError`.
      * Top-level structure that is not a mapping (e.g. a list or
        scalar) → :class:`ApprovalEvidenceConfigError`.

    The strictness is intentional: ``config/field_registry/approvals/``
    is a governance directory. A malformed, partial, or value-blanked
    YAML cannot weaken the daily-QA gate by silently disappearing from
    the scan.
    """
    # Lazy yaml import so the module is importable in minimal envs.
    import yaml

    root = Path(approvals_dir)
    if not root.exists():
        return []
    out: list[ApprovalBinding] = []
    for path in sorted(root.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 — re-raise as governance error
            raise ApprovalEvidenceConfigError(
                f"Malformed approval YAML at {path}: {exc}. "
                "PR 10a requires every approval YAML to be parseable; fix the "
                "file or remove it before re-running daily QA."
            ) from exc
        if not isinstance(data, dict):
            raise ApprovalEvidenceConfigError(
                f"Approval YAML at {path} must parse to a mapping (dict), "
                f"got {type(data).__name__}. PR 10a requires every approval "
                "YAML to be a top-level mapping."
            )
        # PR 10b: distinguish KEY ABSENCE from a key present with a
        # null / blank value. ``data.get(...)`` returns None for both,
        # which let a value-blanked YAML skip as legacy. Use ``in`` for
        # presence and validate the value separately.
        has_pb = "provider_build_id" in data
        has_cp = "calendar_policy_id" in data
        if not has_pb and not has_cp:
            # True legacy YAML predating the binding contract — skip.
            continue
        if has_pb != has_cp:
            # Exactly one key declared — fail closed. Partial bindings
            # would silently weaken the drift check to one axis.
            missing = "calendar_policy_id" if has_pb else "provider_build_id"
            present = "provider_build_id" if has_pb else "calendar_policy_id"
            raise ApprovalEvidenceConfigError(
                f"Approval YAML at {path} declares {present!r} but not "
                f"{missing!r}. Approval evidence must bind BOTH "
                "provider_build_id AND calendar_policy_id (with non-empty "
                "string values), or omit BOTH keys as a legacy approval. "
                f"Add {missing!r} or remove {present!r} to mark this "
                "approval legacy."
            )
        # Both keys present — values MUST be non-empty strings. A null /
        # empty / blank / non-string value is a governance error, NOT a
        # legacy skip (PR 10b).
        pb_id = data["provider_build_id"]
        cp_id = data["calendar_policy_id"]
        for key, value in (
            ("provider_build_id", pb_id),
            ("calendar_policy_id", cp_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ApprovalEvidenceConfigError(
                    f"Approval YAML at {path} declares {key!r} but its value "
                    f"is null / empty / blank / non-string ({value!r}). "
                    "Approval evidence must bind both axes to non-empty "
                    "string values, or omit BOTH keys as a legacy approval. "
                    "A value-blanked binding cannot silently skip the "
                    "drift check."
                )
        out.append(
            ApprovalBinding(
                approval_id=str(data.get("approval_id") or path.stem),
                approval_file=str(path),
                dataset_id=str(data.get("dataset_id") or ""),
                to_status=str(data.get("to_status") or ""),
                date=str(data.get("date") or ""),
                declared_provider_build_id=pb_id.strip(),
                declared_calendar_policy_id=cp_id.strip(),
            )
        )
    return out


def load_current_manifest(
    manifest_path: Path | str = DEFAULT_PROVIDER_MANIFEST,
) -> dict | None:
    """Read the current provider build manifest. Returns ``None`` if missing."""
    p = Path(manifest_path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def evaluate_approval_evidence_bindings(
    *,
    approvals_dir: Path | str = DEFAULT_APPROVALS_DIR,
    manifest_path: Path | str = DEFAULT_PROVIDER_MANIFEST,
) -> list[ApprovalBindingDrift]:
    """Compare each approval YAML's binding against the current manifest.

    Returns a list of drift records, one per approval YAML with a
    declared binding. Callers filter on the ``drift`` field to find
    stale approvals.

    Raises:
        FileNotFoundError: when the provider manifest is missing. A
            missing manifest is a hard failure because formal-mode
            artifacts cannot be attested without one.
    """
    bindings = load_approval_bindings(approvals_dir)
    manifest = load_current_manifest(manifest_path)
    if manifest is None:
        raise FileNotFoundError(
            f"Provider manifest not found at {manifest_path}. Cannot "
            f"validate approval-evidence bindings against current build. "
            f"Either publish a manifest (StagedQlibBackendBuilder.publish "
            f"emits one) or use a sandbox path that skips this check."
        )
    current_pb = manifest.get("provider_build_id")
    current_cp = manifest.get("calendar_policy_id")

    out: list[ApprovalBindingDrift] = []
    for b in bindings:
        # PR 10a contract: load_approval_bindings guarantees both
        # declared_provider_build_id and declared_calendar_policy_id are
        # non-None for any binding it returns (partial bindings raise at
        # load time). The match logic is therefore a literal equality
        # check, NOT a "None means wildcard" relaxation.
        pb_match = b.declared_provider_build_id == current_pb
        cp_match = b.declared_calendar_policy_id == current_cp
        out.append(
            ApprovalBindingDrift(
                binding=b,
                current_provider_build_id=(
                    str(current_pb) if current_pb is not None else None
                ),
                current_calendar_policy_id=(
                    str(current_cp) if current_cp is not None else None
                ),
                provider_build_id_match=pb_match,
                calendar_policy_id_match=cp_match,
            )
        )
    return out


def assert_no_approval_evidence_drift(
    *,
    approvals_dir: Path | str = DEFAULT_APPROVALS_DIR,
    manifest_path: Path | str = DEFAULT_PROVIDER_MANIFEST,
) -> list[ApprovalBindingDrift]:
    """Strict variant: raise :class:`ApprovalEvidenceDriftError` on drift.

    Returns the full drift-record list on success so callers that want
    to log/persist them can do so without re-running the scan.
    """
    drifts = evaluate_approval_evidence_bindings(
        approvals_dir=approvals_dir, manifest_path=manifest_path
    )
    drifted = [d for d in drifts if d.drift]
    if drifted:
        msgs = "\n".join(
            f"  - {reason}"
            for d in drifted
            for reason in d.reasons()
        )
        raise ApprovalEvidenceDriftError(
            f"Approval-evidence binding drift detected "
            f"({len(drifted)} of {len(drifts)} approvals drifted):\n{msgs}\n\n"
            f"Either (a) refresh the affected approval YAMLs with the new "
            f"provider_build_id + calendar_policy_id after re-verifying the "
            f"on-disk evidence under the new build, or (b) revert the "
            f"provider rebuild that introduced the drift."
        )
    return drifts


__all__ = [
    "ApprovalBinding",
    "ApprovalBindingDrift",
    "ApprovalEvidenceConfigError",
    "ApprovalEvidenceDriftError",
    "DEFAULT_APPROVALS_DIR",
    "DEFAULT_PROVIDER_MANIFEST",
    "assert_no_approval_evidence_drift",
    "evaluate_approval_evidence_bindings",
    "load_approval_bindings",
    "load_current_manifest",
]
