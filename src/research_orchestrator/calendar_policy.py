"""Calendar policy loader and validator.

The calendar policy is a committed YAML under ``config/calendar_policies/``
that records why a formal run is operating against a particular calendar
window. It exists so a frozen calendar (e.g. the 2026-02-27 freeze during
system construction) is treated as an explicit governance decision rather
than accidental staleness.

Plan: PR 1 of the 2026-05-26 freeze plan.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

CALENDAR_POLICY_SCHEMA_VERSION = 1
CALENDAR_POLICY_DIR = Path("config/calendar_policies")


class CalendarPolicyError(RuntimeError):
    """Raised when the calendar policy is missing, malformed, or violated."""


@dataclass(frozen=True)
class CalendarPolicy:
    policy_id: str
    policy_schema_version: int
    calendar_start_date: str
    calendar_end_date: str
    data_end_date: str
    frozen: bool
    reason: str
    established_at: str
    allowed_modes: tuple[str, ...]
    default_formal_behavior: str
    max_calendar_lag_days: Optional[int] = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CalendarPolicy":
        try:
            schema_version = int(payload["policy_schema_version"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CalendarPolicyError(
                f"Calendar policy missing or invalid policy_schema_version: {exc}"
            ) from exc

        if schema_version != CALENDAR_POLICY_SCHEMA_VERSION:
            raise CalendarPolicyError(
                f"Unsupported policy_schema_version={schema_version} "
                f"(expected {CALENDAR_POLICY_SCHEMA_VERSION})."
            )

        required = (
            "policy_id",
            "calendar_start_date",
            "calendar_end_date",
            "data_end_date",
            "frozen",
            "reason",
            "established_at",
            "allowed_modes",
            "default_formal_behavior",
        )
        for r in required:
            if r not in payload:
                raise CalendarPolicyError(f"Calendar policy missing required field: {r}")

        frozen = bool(payload["frozen"])
        max_lag = payload.get("max_calendar_lag_days")
        if not frozen and max_lag is None:
            raise CalendarPolicyError(
                f"Calendar policy {payload['policy_id']!r} is not frozen "
                "but does not define max_calendar_lag_days. When frozen=false "
                "the policy must specify a maximum lag (days)."
            )

        return cls(
            policy_id=str(payload["policy_id"]),
            policy_schema_version=schema_version,
            calendar_start_date=str(payload["calendar_start_date"]),
            calendar_end_date=str(payload["calendar_end_date"]),
            data_end_date=str(payload["data_end_date"]),
            frozen=frozen,
            reason=str(payload["reason"]),
            established_at=str(payload["established_at"]),
            allowed_modes=tuple(str(m) for m in payload["allowed_modes"]),
            default_formal_behavior=str(payload["default_formal_behavior"]),
            max_calendar_lag_days=int(max_lag) if max_lag is not None else None,
            notes=tuple(str(n) for n in payload.get("notes", ())),
        )

    def permits_calendar_mismatch(self, run_mode: str) -> bool:
        """Whether this policy permits a formal run to proceed when the
        live Qlib calendar end-date differs from ``self.calendar_end_date``.

        Frozen policies grant permission only for explicitly allowed modes;
        non-frozen policies fall through to ``max_calendar_lag_days`` (callers
        check the lag separately).
        """
        if not self.frozen:
            return False
        return run_mode in self.allowed_modes

    def assert_run_mode_allowed(self, run_mode: str) -> None:
        if run_mode not in self.allowed_modes:
            raise CalendarPolicyError(
                f"Run mode {run_mode!r} is not in this policy's allowed_modes "
                f"{list(self.allowed_modes)} (policy={self.policy_id!r}). "
                "Pass a different --calendar-policy or add the mode if it is "
                "deliberately permitted."
            )


def policy_path_for(policy_id: str, root: Path | None = None) -> Path:
    base = Path(root) if root else CALENDAR_POLICY_DIR
    return base / f"{policy_id}.yaml"


def load_calendar_policy(policy_id: str, *, root: Path | None = None) -> CalendarPolicy:
    """Load a calendar policy by id from ``config/calendar_policies/``.

    Raises :class:`CalendarPolicyError` on missing or malformed file.
    """
    path = policy_path_for(policy_id, root=root)
    if not path.exists():
        raise CalendarPolicyError(
            f"Calendar policy {policy_id!r} not found at {path}. "
            "Add a YAML file under config/calendar_policies/ or pass an existing policy id."
        )
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as exc:
        raise CalendarPolicyError(f"Failed to read calendar policy at {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise CalendarPolicyError(
            f"Calendar policy file {path} did not parse to a YAML mapping."
        )
    return CalendarPolicy.from_dict(payload)
