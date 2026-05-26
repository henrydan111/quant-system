"""Versioned, immutable execution profiles for formal backtest runs.

Plan: PR 3 of the 2026-05-26 freeze plan.

Why
===

Before PR 3, callers composed ``fill_mode + cost_config + slippage + volume_limit``
individually at each call site. That meant ``JoinQuant parity`` was a vague
label hiding parameter drift; a result artifact could be reproduced only by
carefully reading the call site.

After PR 3, every formal backtest passes ``execution_profile='<id>'``. The
profile resolves to a fully-pinned set of execution parameters; the
artifact records ``execution_profile_id + execution_profile_version +
execution_profile_hash`` so reviewers can compare runs by ID alone.

Public surface
==============

* :class:`ExecutionProfile` — frozen dataclass with a computed
  :attr:`profile_hash` property (self-excluding sha256).
* :func:`get_profile` — resolve a profile by id, raising on unknown ids.
* :func:`list_profiles` — enumerate built-in profile ids.
* :func:`resolve_cost_config` / :func:`resolve_slippage_preset` — convert
  the profile's stringly-typed factory names into concrete objects.
* :class:`ExecutionProfileError` / :class:`OverrideRequiresReasonError` —
  callers re-raise these unchanged so the release gate can surface precise
  reasons.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, fields
from typing import Any, Iterable, Literal

PROFILE_SCHEMA_VERSION = 1

DeploymentTarget = Literal[
    "joinquant_daily",
    "joinquant_minute_replica",
    "joinquant_open_close_replica",
    "local_stress",
    "screening_only",
]

Backend = Literal["event_driven", "vectorized"]
FillMode = Literal["open_close", "jq_daily_avg"]
CostConfigFactory = Literal["joinquant_default", "realistic_china"]
SlippagePreset = Literal[
    "JOINQUANT_DEFAULT_SLIPPAGE",
    "CONSERVATIVE_SLIPPAGE_10BPS",
    "NO_SLIPPAGE",
]


class ExecutionProfileError(RuntimeError):
    """Raised when an execution profile is malformed, unknown, or misused."""


class OverrideRequiresReasonError(ExecutionProfileError):
    """Raised when a formal run supplies an override without an override_reason."""


# Fields that participate in the profile_hash. profile_hash itself is
# excluded; that's the whole point of the contract — the hash is a function
# of the execution-relevant state, not a stored attribute.
_HASHED_FIELDS: tuple[str, ...] = (
    "profile_id",
    "profile_schema_version",
    "profile_version",
    "deployment_target",
    "backend",
    "fill_mode",
    "cost_config_factory",
    "slippage_preset",
    "volume_limit",
    "allowed_for_formal",
    "notes",
)


@dataclass(frozen=True)
class ExecutionProfile:
    """Immutable execution profile aggregating fill semantics, costs, and slippage."""

    profile_id: str
    profile_version: str
    deployment_target: str
    backend: str
    fill_mode: str
    cost_config_factory: str
    slippage_preset: str
    volume_limit: float
    allowed_for_formal: bool
    notes: str = ""
    profile_schema_version: int = PROFILE_SCHEMA_VERSION

    @property
    def profile_hash(self) -> str:
        """sha256 hex digest over the execution-relevant fields, excluding itself.

        Determinism: ``json.dumps(..., sort_keys=True, separators=(",", ":"))``
        is locked to a stable canonical form. Two ExecutionProfile instances
        with identical hashed fields produce byte-identical input to sha256.
        """
        payload = {name: getattr(self, name) for name in _HASHED_FIELDS}
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_provenance_dict(self) -> dict[str, Any]:
        """Return the subset of fields stamped onto ArtifactProvenance."""
        return {
            "execution_profile_id": self.profile_id,
            "execution_profile_version": self.profile_version,
            "execution_profile_hash": self.profile_hash,
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─────────────────────────────────────────────────────────────────────────
# Built-in profile registry
# ─────────────────────────────────────────────────────────────────────────


_BUILTIN_PROFILES: dict[str, ExecutionProfile] = {
    "joinquant_daily_sim": ExecutionProfile(
        profile_id="joinquant_daily_sim",
        profile_version="2026-05-26.v1",
        deployment_target="joinquant_daily",
        backend="event_driven",
        fill_mode="jq_daily_avg",
        cost_config_factory="joinquant_default",
        slippage_preset="JOINQUANT_DEFAULT_SLIPPAGE",
        volume_limit=0.25,
        allowed_for_formal=True,
        notes=(
            "Faithful local twin of JoinQuant's daily-frequency backtest path. "
            "Use for any research that will be deployed via JoinQuant daily."
        ),
    ),
    "joinquant_open_close_replica": ExecutionProfile(
        profile_id="joinquant_open_close_replica",
        profile_version="2026-05-26.v1",
        deployment_target="joinquant_open_close_replica",
        backend="event_driven",
        fill_mode="open_close",
        cost_config_factory="joinquant_default",
        slippage_preset="JOINQUANT_DEFAULT_SLIPPAGE",
        volume_limit=0.25,
        allowed_for_formal=True,
        notes=(
            "Open-fill before_market_open + close-fill on_bar variant. "
            "Closer to live execution than jq_daily_avg; use for verification."
        ),
    ),
    "realistic_china_stress": ExecutionProfile(
        profile_id="realistic_china_stress",
        profile_version="2026-05-26.v1",
        deployment_target="local_stress",
        backend="event_driven",
        fill_mode="open_close",
        cost_config_factory="realistic_china",
        slippage_preset="CONSERVATIVE_SLIPPAGE_10BPS",
        volume_limit=0.10,
        allowed_for_formal=False,
        notes=(
            "Conservative cost+slippage stress test against the actual Chinese "
            "exchange (2023-08-28 stamp tax cut, 0.2 bps transfer fee, 10 bps "
            "slippage). NOT formal-publish-eligible — used for sensitivity only."
        ),
    ),
    "vectorized_screening_close": ExecutionProfile(
        profile_id="vectorized_screening_close",
        profile_version="2026-05-26.v1",
        deployment_target="screening_only",
        backend="vectorized",
        fill_mode="open_close",  # nominally; vectorized uses deal_price='close'
        cost_config_factory="joinquant_default",
        slippage_preset="NO_SLIPPAGE",
        volume_limit=1.0,
        allowed_for_formal=False,
        notes=(
            "Fast vectorized screen via Qlib backtest. NOT formal-publish-eligible. "
            "Use only for early candidate triage before promoting to event_driven."
        ),
    ),
}


def list_profiles() -> list[str]:
    """Return the sorted list of built-in profile ids."""
    return sorted(_BUILTIN_PROFILES.keys())


def get_profile(profile_id: str) -> ExecutionProfile:
    """Resolve a profile by id; raise on unknown."""
    if profile_id not in _BUILTIN_PROFILES:
        raise ExecutionProfileError(
            f"Unknown execution_profile_id={profile_id!r}. "
            f"Known profiles: {list_profiles()}. "
            "Add a new entry to src/backtest_engine/execution_profiles.py "
            "_BUILTIN_PROFILES and bump its profile_version."
        )
    return _BUILTIN_PROFILES[profile_id]


# ─────────────────────────────────────────────────────────────────────────
# String-to-object resolvers
# ─────────────────────────────────────────────────────────────────────────


def resolve_cost_config(factory: str):
    """Resolve cost_config_factory string to a concrete CostConfig instance."""
    from src.backtest_engine.event_driven.exchange import CostConfig

    if factory == "joinquant_default":
        return CostConfig()
    if factory == "realistic_china":
        return CostConfig.realistic_china()
    raise ExecutionProfileError(
        f"Unknown cost_config_factory={factory!r}. "
        "Allowed: 'joinquant_default', 'realistic_china'."
    )


def resolve_slippage_preset(preset: str):
    """Resolve slippage_preset string to a concrete SlippageModel instance."""
    from src.backtest_engine.event_driven.exchange import (
        CONSERVATIVE_SLIPPAGE_10BPS,
        JOINQUANT_DEFAULT_SLIPPAGE,
        NoSlippage,
    )

    if preset == "JOINQUANT_DEFAULT_SLIPPAGE":
        return JOINQUANT_DEFAULT_SLIPPAGE
    if preset == "CONSERVATIVE_SLIPPAGE_10BPS":
        return CONSERVATIVE_SLIPPAGE_10BPS
    if preset == "NO_SLIPPAGE":
        return NoSlippage()
    raise ExecutionProfileError(
        f"Unknown slippage_preset={preset!r}. "
        "Allowed: 'JOINQUANT_DEFAULT_SLIPPAGE', 'CONSERVATIVE_SLIPPAGE_10BPS', 'NO_SLIPPAGE'."
    )


# ─────────────────────────────────────────────────────────────────────────
# Override detection
# ─────────────────────────────────────────────────────────────────────────


def detect_override_diff(
    *,
    profile: ExecutionProfile,
    explicit_fill_mode: str | None,
    explicit_cost_config_factory: str | None,
    explicit_slippage_preset: str | None,
    explicit_volume_limit: float | None,
) -> dict[str, list[Any]]:
    """Compute a {field: [profile_value, explicit_value]} diff for any overrides.

    Returns empty dict when caller passes no overrides. The wrapper passes
    this to ArtifactProvenance so the artifact records exactly what diverged
    from the profile baseline.
    """
    diff: dict[str, list[Any]] = {}
    if explicit_fill_mode is not None and explicit_fill_mode != profile.fill_mode:
        diff["fill_mode"] = [profile.fill_mode, explicit_fill_mode]
    if (
        explicit_cost_config_factory is not None
        and explicit_cost_config_factory != profile.cost_config_factory
    ):
        diff["cost_config_factory"] = [
            profile.cost_config_factory,
            explicit_cost_config_factory,
        ]
    if (
        explicit_slippage_preset is not None
        and explicit_slippage_preset != profile.slippage_preset
    ):
        diff["slippage_preset"] = [profile.slippage_preset, explicit_slippage_preset]
    if (
        explicit_volume_limit is not None
        and abs(float(explicit_volume_limit) - float(profile.volume_limit)) > 1e-12
    ):
        diff["volume_limit"] = [profile.volume_limit, float(explicit_volume_limit)]
    return diff
