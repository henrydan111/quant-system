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

Schema contract
===============

Each approval YAML under ``config/field_registry/approvals/`` SHOULD
carry both ``provider_build_id`` and ``calendar_policy_id`` keys at the
top level. YAMLs predating the PR 9a round-3 binding contract (those
without either key) are silently skipped — they cannot be validated.
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

    YAMLs that don't carry at least one of ``provider_build_id`` or
    ``calendar_policy_id`` are silently skipped — those predate the PR 9a
    round-3 binding contract and cannot be drift-checked.
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
        except Exception as exc:  # noqa: BLE001 — defensive scan
            logger.warning("Skipping malformed approval YAML %s: %s", path, exc)
            continue
        if not isinstance(data, dict):
            continue
        pb_id = data.get("provider_build_id")
        cp_id = data.get("calendar_policy_id")
        if pb_id is None and cp_id is None:
            # Legacy YAML without binding — silently skip.
            continue
        out.append(
            ApprovalBinding(
                approval_id=str(data.get("approval_id") or path.stem),
                approval_file=str(path),
                dataset_id=str(data.get("dataset_id") or ""),
                to_status=str(data.get("to_status") or ""),
                date=str(data.get("date") or ""),
                declared_provider_build_id=(str(pb_id) if pb_id is not None else None),
                declared_calendar_policy_id=(str(cp_id) if cp_id is not None else None),
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
        pb_match = (
            b.declared_provider_build_id is None
            or b.declared_provider_build_id == current_pb
        )
        cp_match = (
            b.declared_calendar_policy_id is None
            or b.declared_calendar_policy_id == current_cp
        )
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
    "ApprovalEvidenceDriftError",
    "DEFAULT_APPROVALS_DIR",
    "DEFAULT_PROVIDER_MANIFEST",
    "assert_no_approval_evidence_drift",
    "evaluate_approval_evidence_bindings",
    "load_approval_bindings",
    "load_current_manifest",
]
