"""Field-status registry loader, expression parser, and gate.

Lives next to the rest of the data infrastructure because field approval is
fundamentally a data-side governance concern. Consumers (factor evaluation,
validation steps, release gate) call into this module rather than reasoning
about field approval ad-hoc.

Plan: PR 5 of the 2026-05-26 freeze plan.

Public surface
==============

* :class:`FieldStatusRegistry` — loaded YAML; exposes :meth:`resolve_field`
  and :meth:`validate_expression`.
* :func:`extract_qlib_fields` — pull every ``$field`` token out of a Qlib
  expression including occurrences inside ``Ref()``, ``Mean()``, etc.
* :func:`load_field_registry` — convenience loader using the committed YAML.
* :class:`FieldApprovalError` — raised on disallowed stage usage.
* :class:`FieldRegistryError` — raised on malformed registry YAML.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping

import yaml

logger = logging.getLogger(__name__)

DEFAULT_REGISTRY_PATH = Path("config/field_registry/field_status.yaml")

Stage = Literal[
    "sandbox_screening",
    "vectorized_screening",
    "formal_validation",
    "oos_test",
    "registry_publish",
]

_STAGES: tuple[str, ...] = (
    "sandbox_screening",
    "vectorized_screening",
    "formal_validation",
    "oos_test",
    "registry_publish",
)


class FieldRegistryError(RuntimeError):
    """Raised when the field-registry YAML is missing or malformed."""


class FieldApprovalError(RuntimeError):
    """Raised when a Qlib expression references a field disallowed at the current stage."""


# ─────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StatusDef:
    status_id: str
    description: str
    allowed: dict[str, bool]

    def allows(self, stage: str) -> bool:
        if stage not in self.allowed:
            raise FieldRegistryError(
                f"Status {self.status_id!r} has no entry for stage={stage!r}. "
                "Add it to allowed{} in field_status.yaml or fix the caller."
            )
        return bool(self.allowed[stage])


@dataclass(frozen=True)
class DatasetEntry:
    dataset_id: str
    status: str
    reason: str
    fields: tuple[str, ...] = ()
    field_prefixes: tuple[str, ...] = ()

    def matches(self, field_token: str) -> bool:
        if field_token in self.fields:
            return True
        return any(field_token.startswith(p) for p in self.field_prefixes)


@dataclass(frozen=True)
class FieldResolution:
    """Result of resolving a $field token against the registry.

    ``dataset_id == None`` means the field was unknown — the caller should
    apply the registry's ``unknown_field_policy``.
    """
    field_token: str
    dataset_id: str | None
    status_id: str | None
    allowed: bool
    reason: str
    is_unknown: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field_token,
            "dataset_id": self.dataset_id,
            "status": self.status_id,
            "allowed": self.allowed,
            "reason": self.reason,
            "is_unknown": self.is_unknown,
        }


# ─────────────────────────────────────────────────────────────────────────
# Expression parser
# ─────────────────────────────────────────────────────────────────────────


# Qlib field tokens are ASCII identifiers prefixed with `$`. They may include
# letters, digits, and underscores. Examples: $close, $pit_or_yoy,
# $top_list__close, $moneyflow_buy_sm_vol.
_FIELD_REGEX = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*")


def extract_qlib_fields(expression: str | None) -> tuple[str, ...]:
    """Return the unique sorted tuple of ``$field`` tokens in ``expression``.

    Works on raw Qlib expressions including those nested inside operators
    (``Ref($close, 1)``, ``Mean(Ref($close, 1), 20)``, etc.). The regex
    intentionally matches token form, not semantics — composite expressions
    that combine multiple fields all surface.
    """
    if not expression:
        return ()
    seen = sorted(set(_FIELD_REGEX.findall(expression)))
    return tuple(seen)


# ─────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FieldStatusRegistry:
    schema_version: int
    statuses: dict[str, StatusDef]
    datasets: dict[str, DatasetEntry]
    unknown_field_policy: dict[str, str]
    approval_log_path: str
    approvals_dir: str

    # ── Loading ────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FieldStatusRegistry":
        try:
            version = int(payload["schema_version"])
        except (KeyError, TypeError, ValueError) as exc:
            raise FieldRegistryError(
                f"field_registry missing or invalid schema_version: {exc}"
            ) from exc
        if version != 1:
            raise FieldRegistryError(
                f"Unsupported field_registry schema_version={version} (expected 1)."
            )

        for required in ("statuses", "datasets", "unknown_field_policy"):
            if required not in payload:
                raise FieldRegistryError(f"field_registry missing required field: {required}")

        statuses: dict[str, StatusDef] = {}
        for sid, sdef in (payload.get("statuses") or {}).items():
            if not isinstance(sdef, Mapping):
                raise FieldRegistryError(f"statuses[{sid}] must be a mapping")
            allowed = sdef.get("allowed") or {}
            for stage in _STAGES:
                if stage not in allowed:
                    raise FieldRegistryError(
                        f"statuses[{sid}].allowed missing stage={stage!r}"
                    )
            statuses[str(sid)] = StatusDef(
                status_id=str(sid),
                description=str(sdef.get("description", "")),
                allowed={k: bool(v) for k, v in allowed.items()},
            )

        datasets: dict[str, DatasetEntry] = {}
        for did, entry in (payload.get("datasets") or {}).items():
            if not isinstance(entry, Mapping):
                raise FieldRegistryError(f"datasets[{did}] must be a mapping")
            status = str(entry.get("status", ""))
            if not status:
                raise FieldRegistryError(f"datasets[{did}] missing status")
            if status not in statuses:
                raise FieldRegistryError(
                    f"datasets[{did}].status={status!r} is not in registered statuses "
                    f"{sorted(statuses)}"
                )
            datasets[str(did)] = DatasetEntry(
                dataset_id=str(did),
                status=status,
                reason=str(entry.get("reason", "")),
                fields=tuple(entry.get("fields") or ()),
                field_prefixes=tuple(entry.get("field_prefixes") or ()),
            )

        unknown_policy = payload.get("unknown_field_policy") or {}
        for stage in _STAGES:
            if stage not in unknown_policy:
                raise FieldRegistryError(
                    f"unknown_field_policy missing stage={stage!r}"
                )
            if unknown_policy[stage] not in {"warn", "fail"}:
                raise FieldRegistryError(
                    f"unknown_field_policy[{stage}] must be 'warn' or 'fail', "
                    f"got {unknown_policy[stage]!r}"
                )

        return cls(
            schema_version=version,
            statuses=statuses,
            datasets=datasets,
            unknown_field_policy={k: str(v) for k, v in unknown_policy.items()},
            approval_log_path=str(
                payload.get("approval_log_path", "config/field_registry/field_approval_log.jsonl")
            ),
            approvals_dir=str(
                payload.get("approvals_dir", "config/field_registry/approvals")
            ),
        )

    # ── Lookup ─────────────────────────────────────────────────────

    def _find_dataset(self, field_token: str) -> DatasetEntry | None:
        # Explicit field hit wins over prefix hit (more specific).
        for ds in self.datasets.values():
            if field_token in ds.fields:
                return ds
        for ds in self.datasets.values():
            if any(field_token.startswith(p) for p in ds.field_prefixes):
                return ds
        return None

    def resolve_field(self, field_token: str, stage: str) -> FieldResolution:
        """Resolve a $field token to (status, allowed-at-stage, reason).

        Unknown fields return ``is_unknown=True`` with ``allowed`` set per the
        registry's ``unknown_field_policy`` for the given stage. Callers may
        choose to warn vs raise based on that flag.
        """
        if stage not in _STAGES:
            raise FieldRegistryError(
                f"Unknown stage={stage!r}. Allowed: {list(_STAGES)}"
            )

        dataset = self._find_dataset(field_token)
        if dataset is None:
            policy = self.unknown_field_policy[stage]
            allowed = policy == "warn"  # warn allows the run; fail blocks it
            return FieldResolution(
                field_token=field_token,
                dataset_id=None,
                status_id=None,
                allowed=allowed,
                reason=f"unknown_field; unknown_field_policy[{stage}]={policy}",
                is_unknown=True,
            )

        status_def = self.statuses[dataset.status]
        allowed = status_def.allows(stage)
        return FieldResolution(
            field_token=field_token,
            dataset_id=dataset.dataset_id,
            status_id=dataset.status,
            allowed=allowed,
            reason=dataset.reason,
        )

    # ── Validation ─────────────────────────────────────────────────

    def validate_expression(
        self,
        expression: str | None,
        stage: str,
        *,
        raise_on_unknown: bool | None = None,
    ) -> list[FieldResolution]:
        """Resolve every field in ``expression`` and raise if any is disallowed.

        Args:
            expression: A Qlib expression string, e.g. ``Mean(Ref($close, 1), 20)``.
            stage: One of ``_STAGES``.
            raise_on_unknown: Optional override of the per-stage
                ``unknown_field_policy``. When ``None`` (default), the
                registry's policy decides whether unknown fields raise.

        Returns:
            List of :class:`FieldResolution` — one per unique field token.

        Raises:
            FieldApprovalError: If any field is disallowed at the stage, or
                if ``raise_on_unknown`` (or registry policy) says unknown
                fields are fatal at this stage.
        """
        if stage not in _STAGES:
            raise FieldRegistryError(
                f"Unknown stage={stage!r}. Allowed: {list(_STAGES)}"
            )

        fields_seen = extract_qlib_fields(expression)
        resolutions: list[FieldResolution] = []
        disallowed: list[FieldResolution] = []
        unknown_disallowed: list[FieldResolution] = []

        for f in fields_seen:
            r = self.resolve_field(f, stage)
            resolutions.append(r)
            if r.is_unknown:
                # Apply override if caller forced one.
                if raise_on_unknown is True:
                    unknown_disallowed.append(r)
                elif raise_on_unknown is False:
                    pass  # treat as warn
                elif not r.allowed:
                    unknown_disallowed.append(r)
                elif r.allowed:
                    logger.warning(
                        "Unknown Qlib field %r at stage=%s — registered no dataset.",
                        f, stage,
                    )
            else:
                if not r.allowed:
                    disallowed.append(r)

        if disallowed or unknown_disallowed:
            problems = disallowed + unknown_disallowed
            details = "; ".join(
                f"{r.field_token} (dataset={r.dataset_id}, status={r.status_id}, "
                f"reason={r.reason!r})"
                for r in problems
            )
            raise FieldApprovalError(
                f"Expression references field(s) disallowed at stage={stage}: {details}"
            )

        return resolutions

    def validate_expressions(
        self,
        expressions: Iterable[str | None],
        stage: str,
        **kwargs,
    ) -> list[FieldResolution]:
        """Convenience: validate a list of expressions and return combined resolutions."""
        out: list[FieldResolution] = []
        seen_fields: set[str] = set()
        for expr in expressions:
            for r in self.validate_expression(expr, stage, **kwargs):
                if r.field_token in seen_fields:
                    continue
                seen_fields.add(r.field_token)
                out.append(r)
        return out

    # ── Approval helpers ───────────────────────────────────────────

    def list_datasets_by_status(self, status_id: str) -> list[str]:
        return sorted(d.dataset_id for d in self.datasets.values() if d.status == status_id)


# ─────────────────────────────────────────────────────────────────────────
# Convenience loaders
# ─────────────────────────────────────────────────────────────────────────


def load_field_registry(path: str | Path | None = None) -> FieldStatusRegistry:
    """Load the committed field-status registry YAML.

    Raises :class:`FieldRegistryError` on missing file or malformed content.
    """
    target = Path(path) if path else DEFAULT_REGISTRY_PATH
    if not target.exists():
        raise FieldRegistryError(
            f"field_registry YAML not found at {target}. "
            "Expected the committed registry at config/field_registry/field_status.yaml."
        )
    try:
        with open(target, "r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as exc:
        raise FieldRegistryError(f"Failed to read field_registry at {target}: {exc}") from exc

    if not isinstance(payload, Mapping):
        raise FieldRegistryError(
            f"field_registry at {target} did not parse to a YAML mapping."
        )
    return FieldStatusRegistry.from_dict(payload)
