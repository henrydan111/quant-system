"""D2 — the four identity-critical typed-hash dataclasses + the mandatory
identity-chain checker for the factor-eval skill.

Design: ``workspace/research/factor_eval_methodology/FACTOR_EVAL_PARTG_BUILD_DESIGN.md``
(v2, D2). These four objects are the ONLY identity-critical ones (the other six
methodology nouns are validated YAML→payload records, not typed classes):

    TargetUniverseDeclaration  -> tud_hash
    SelectedSet                -> selected_set_hash   (carries tud_hash)
    FrozenSelectionEnvelope    -> envelope_hash        (wraps frozen_set_hash + tud_hash + selected_set_hash)
    DeploymentFrozenPlan       -> plan_hash            (references all three hashes)

Back-compat invariant (the hard part): the existing
``FrozenSelectionSet.frozen_set_hash`` is NEVER re-hashed. The
``target_universe_declaration_hash`` is carried in the IMMUTABLE
:class:`FrozenSelectionEnvelope` that WRAPS ``frozen_set_hash`` — it is never a mutable
field on a ``FrozenSelectionSet`` object. ``HoldoutSealStore`` still keys by
``frozen_set_hash``, so the already-spent E-wave seal (``316b17bc…``) stays valid; no
payload bump, no orphaned seal. :func:`assert_identity_chain` is MANDATORY (called by
the select / seal / deploy code paths), not an optional checker callers may forget.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from src.alpha_research.factor_eval_skill._hashing import (
    frozen_mapping,
    normalize_enum,
    payload_hash,
    to_jsonable,
)

SCHEMA_VERSION = 1


class IdentityChainError(ValueError):
    """Raised (fail-closed) when the TUD / SelectedSet / Envelope / Plan hashes do not
    form a consistent identity chain, or when a legacy envelope is asked to assert a
    clean v1.3 chain."""


@dataclass(frozen=True)
class TargetUniverseDeclaration:
    """The declared investable universe for a deployment-bound claim. Declared BEFORE
    Stage-2/3 interpretation (v1.3 §3); changing it after results = a new seal.

    ``tud_hash`` is the spine all four identity objects share. The universe-DEFINITION
    filters (ADV / listing-age / board / ST screens) are bound HERE, at TUD identity —
    they are NOT tuned at the Stage-8 deployment gate (v1.3 §6 / FC governance)."""

    target_universe_id: str
    universe_definition_filters: Mapping[str, Any]
    eligibility_policy: str
    asof_policy: str
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        # deep-freeze the mapping at construction so it cannot be mutated later (which would
        # silently change tud_hash) and is severed from the caller's dict.
        object.__setattr__(
            self, "universe_definition_filters", frozen_mapping(self.universe_definition_filters)
        )

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "target_universe_id": normalize_enum(self.target_universe_id),
            "universe_definition_filters": to_jsonable(self.universe_definition_filters),
            "eligibility_policy": normalize_enum(self.eligibility_policy),
            "asof_policy": normalize_enum(self.asof_policy),
        }

    @property
    def tud_hash(self) -> str:
        return payload_hash(self._payload())


@dataclass(frozen=True)
class SelectedRepresentative:
    """One member of a :class:`SelectedSet`. ``expected_direction`` REFERENCES the
    factor's existing ``expected_direction`` — the skill never invents a new direction
    field (seam trap #2)."""

    factor_id: str
    version: int
    definition_hash: str
    expected_direction: str

    def to_payload(self) -> list[Any]:
        return [
            str(self.factor_id),
            int(self.version),
            str(self.definition_hash),
            normalize_enum(self.expected_direction),
        ]


@dataclass(frozen=True)
class SelectedSet:
    """The hash-bound selected representatives (mandatory before OOS). Carries
    ``tud_hash`` so identity is anchored to the declared target. ``selected_set_hash``
    is order-independent over ``selected`` (mirrors ``FrozenSelectionSet``)."""

    tud_hash: str
    pool_hash: str
    selected: tuple[SelectedRepresentative, ...]
    selection_code_hash: str
    schema_version: int = SCHEMA_VERSION

    def _payload(self) -> dict[str, Any]:
        selected_sorted = sorted(
            (rep.to_payload() for rep in self.selected),
            key=lambda payload: (payload[0], payload[1], payload[2], payload[3]),
        )
        return {
            "schema_version": int(self.schema_version),
            "tud_hash": str(self.tud_hash),
            "pool_hash": str(self.pool_hash),
            "selected": selected_sorted,
            "selection_code_hash": str(self.selection_code_hash),
        }

    @property
    def selected_set_hash(self) -> str:
        return payload_hash(self._payload())


@dataclass(frozen=True)
class FrozenSelectionEnvelope:
    """The IMMUTABLE record that ties an existing ``frozen_set_hash`` to its
    ``target_universe_declaration_hash`` + ``selected_set_hash`` WITHOUT re-hashing the
    frozen payload. ``envelope_hash`` is an integrity hash over this record — it is NOT
    the ``HoldoutSealStore`` seal key (that stays ``frozen_set_hash``).

    A legacy (pre-v1.3) seal is represented with ``legacy_mode=True`` +
    ``target_universe_declaration_hash=None``: it stays auditable but CANNOT assert a
    clean v1.3 identity chain (:func:`assert_identity_chain` refuses it)."""

    frozen_set_hash: str
    target_universe_declaration_hash: str | None
    selected_set_hash: str | None
    created_at: str
    created_by: str
    frozen_selection_set_schema_version: int = 1
    legacy_mode: bool = False
    legacy_reason: str | None = None
    schema_version: int = SCHEMA_VERSION

    def _payload(self) -> dict[str, Any]:
        # The hashed payload is the IDENTITY BINDING only. created_at / created_by are
        # provenance (recorded as store columns), NOT in the hash — so envelope_hash is a
        # DETERMINISTIC function of the binding and survives re-creation. A DeploymentFrozenPlan
        # references envelope_hash, so a timestamp in the hash would break the chain whenever the
        # envelope is rebuilt rather than reloaded (self-review 2026-06-21).
        return {
            "schema_version": int(self.schema_version),
            "frozen_set_hash": str(self.frozen_set_hash),
            "target_universe_declaration_hash": (
                None
                if self.target_universe_declaration_hash is None
                else str(self.target_universe_declaration_hash)
            ),
            "selected_set_hash": (
                None if self.selected_set_hash is None else str(self.selected_set_hash)
            ),
            "frozen_selection_set_schema_version": int(self.frozen_selection_set_schema_version),
            "legacy_mode": bool(self.legacy_mode),
            "legacy_reason": (None if self.legacy_reason is None else str(self.legacy_reason)),
        }

    @property
    def envelope_hash(self) -> str:
        """Deterministic sha256 over the identity binding (NOT created_at/by, NOT the
        HoldoutSealStore seal key). Reproducible: rebuilding the envelope for the same
        binding yields the same hash, so a plan's envelope_hash reference is stable."""
        return payload_hash(self._payload())


@dataclass(frozen=True)
class DeploymentFrozenPlan:
    """The one-shot deployment plan. References the ranking seal (``frozen_set_hash``),
    the ``envelope_hash``, and the ``target_universe_declaration_hash`` so the deploy
    gate cannot run against a different target than the one that was sealed. Carries a
    pre-declared pass/fail bar (v1.3 §7)."""

    frozen_set_hash: str
    envelope_hash: str
    target_universe_declaration_hash: str
    deployment_universe: str
    portfolio_side: str
    construction: Mapping[str, Any]
    pre_declared_bar: Mapping[str, Any]
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "construction", frozen_mapping(self.construction))
        object.__setattr__(self, "pre_declared_bar", frozen_mapping(self.pre_declared_bar))

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "frozen_set_hash": str(self.frozen_set_hash),
            "envelope_hash": str(self.envelope_hash),
            "target_universe_declaration_hash": str(self.target_universe_declaration_hash),
            "deployment_universe": normalize_enum(self.deployment_universe),
            "portfolio_side": normalize_enum(self.portfolio_side),
            "construction": to_jsonable(self.construction),
            "pre_declared_bar": to_jsonable(self.pre_declared_bar),
        }

    @property
    def plan_hash(self) -> str:
        return payload_hash(self._payload())


@dataclass(frozen=True)
class EvalProtocolSpec:
    """Canonical evaluation-protocol identity for a sealed OOS test (GPT re-review 2026-06-21).

    ``FrozenSelectionSet.frozen_set_hash`` includes ``eval_protocol_hash``; the FrozenSelectionSet
    docstring declares the protocol identity-bearing across preprocessing / winsor / rank / horizon
    / label / quantile / cost-slippage / missing-data / tie-break / universe-filter. A THIN protocol
    hash (just horizon/n_quantiles/window/metric) would let the SAME economic OOS test be re-sealed
    under a different hash by a tool that varies one of these strings — defeating the one-shot seal.
    This captures the full set so ``protocol_hash`` is canonical across tools. Fields default to the
    actual ``reproduce_sealed_oos`` registration-metric methodology; change a default only when the
    engine's methodology changes (which SHOULD change the hash)."""

    horizon: int
    n_quantiles: int
    oos_window: str
    metric: str
    universe_filter_policy: str          # observation universe; A5 requires full_provider_universe
    portfolio_construction: str          # registration-metric book (e.g. decile_long_short)
    label_definition: str = "forward_return"
    rank_transform: str = "cs_rank"
    winsorization: str = "none"
    missing_data_policy: str = "drop"
    tie_break_policy: str = "average"
    neutralization: str = "none"
    rebalance: str = "none"              # registration observations have no rebalance schedule
    cost_slippage_for_registration: str = "gross"
    # R6 Blocker 3 + R7 Minor: the registration bar (judgment semantics) is part of the
    # FULL protocol identity — a changed bar is a DIFFERENT protocol, never a
    # reinterpretation of an already-observed OOS. REQUIRED non-blank (a protocol
    # without a bar binding is not a valid sealed protocol); cmd_seal passes
    # sealed_oos.registration_bar_hash().
    registration_bar_hash: str = ""
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not str(self.registration_bar_hash).strip():
            raise ValueError(
                "EvalProtocolSpec requires a non-blank registration_bar_hash — a sealed "
                "protocol must bind the judgment bar (R7 Minor, fail-closed)"
            )

    def _observation_payload(self) -> dict[str, Any]:
        """R7 Blocker 2 — the OBSERVATION identity: everything that determines WHAT the
        OOS test measures, EXCLUDING the judgment bar. The seal key (via
        ``FrozenSelectionSet.eval_protocol_hash``) uses THIS hash, so changing the bar
        after an observation hits the SAME seal key (and then refuses on the request
        hash / spent preflight) instead of silently minting a fresh seal."""
        return {
            "schema_version": int(self.schema_version),
            "horizon": int(self.horizon),
            "n_quantiles": int(self.n_quantiles),
            "oos_window": str(self.oos_window),
            "metric": normalize_enum(self.metric),
            "universe_filter_policy": normalize_enum(self.universe_filter_policy),
            "portfolio_construction": normalize_enum(self.portfolio_construction),
            "label_definition": normalize_enum(self.label_definition),
            "rank_transform": normalize_enum(self.rank_transform),
            "winsorization": normalize_enum(self.winsorization),
            "missing_data_policy": normalize_enum(self.missing_data_policy),
            "tie_break_policy": normalize_enum(self.tie_break_policy),
            "neutralization": normalize_enum(self.neutralization),
            "rebalance": normalize_enum(self.rebalance),
            "cost_slippage_for_registration": normalize_enum(self.cost_slippage_for_registration),
        }

    def _payload(self) -> dict[str, Any]:
        payload = self._observation_payload()
        payload["registration_bar_hash"] = str(self.registration_bar_hash)
        return payload

    @property
    def observation_protocol_hash(self) -> str:
        """The bar-EXCLUDING identity — use for seal keys (R7 B2)."""
        return payload_hash(self._observation_payload())

    @property
    def protocol_hash(self) -> str:
        """The FULL identity (bar included) — use for request hashes + persisted records."""
        return payload_hash(self._payload())


@dataclass(frozen=True)
class BookSealIdentity:
    """v1.4 A2/N2 (2026-07-03) — the BOOK seal key: every field that differentiates a
    sealed spend is HASH MATERIAL, never audit-only payload.

    ``DeploymentFrozenPlan.plan_hash`` alone is NOT a safe seal key: its payload covers
    frozen_set / envelope / TUD / universe / side / construction / pre_declared_bar but
    omits ``selected_set_hash``, the execution-profile identity, the
    :class:`EvalProtocolSpec` hash, and the OOS window — so two materially different
    sealed evaluations could share a bare ``plan_hash``. ``book_seal_key`` closes that:
    changes to construction (via ``plan_hash``), execution envelope, evaluation protocol,
    OOS window, or pass/fail bar each produce a DISTINCT key. Book seals in
    ``HoldoutSealStore`` (and every backstop/resume path) key by ``book_seal_key`` with
    NO fallback to ``design_hash`` or ``frozen_set_hash``.
    Design: FACTOR_EVAL_V1.4_AMENDMENT_book_level_promotion.md §2 A2."""

    plan_hash: str
    frozen_set_hash: str
    selected_set_hash: str
    target_universe_declaration_hash: str
    execution_envelope_hash: str     # execution-profile identity (profile id + hash)
    eval_protocol_hash: str          # EvalProtocolSpec.protocol_hash
    oos_window_id: str
    pre_declared_bar_hash: str
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def from_plan(
        cls,
        plan: DeploymentFrozenPlan,
        *,
        selected_set_hash: str,
        execution_envelope_hash: str,
        eval_protocol_hash: str,
        oos_window_id: str,
    ) -> "BookSealIdentity":
        """Derive the seal identity from a frozen plan. ``pre_declared_bar_hash`` is
        computed from the plan's own bar (it is already inside ``plan_hash``; carrying it
        explicitly keeps the key self-describing per the round-2 N2 replacement text)."""
        return cls(
            plan_hash=plan.plan_hash,
            frozen_set_hash=str(plan.frozen_set_hash),
            selected_set_hash=str(selected_set_hash),
            target_universe_declaration_hash=str(plan.target_universe_declaration_hash),
            execution_envelope_hash=str(execution_envelope_hash),
            eval_protocol_hash=str(eval_protocol_hash),
            oos_window_id=str(oos_window_id),
            pre_declared_bar_hash=payload_hash(to_jsonable(plan.pre_declared_bar)),
        )

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "plan_hash": str(self.plan_hash),
            "frozen_set_hash": str(self.frozen_set_hash),
            "selected_set_hash": str(self.selected_set_hash),
            "target_universe_declaration_hash": str(self.target_universe_declaration_hash),
            "execution_envelope_hash": str(self.execution_envelope_hash),
            "eval_protocol_hash": str(self.eval_protocol_hash),
            "oos_window_id": str(self.oos_window_id),
            "pre_declared_bar_hash": str(self.pre_declared_bar_hash),
        }

    @property
    def book_seal_key(self) -> str:
        return payload_hash(self._payload())


def assert_identity_chain(
    tud: TargetUniverseDeclaration,
    selected_set: SelectedSet,
    envelope: FrozenSelectionEnvelope,
    plan: DeploymentFrozenPlan | None = None,
) -> None:
    """Fail-closed check that the identity objects form ONE consistent chain.

    MANDATORY in the select / seal / deploy paths (not an optional checker). Enforces:

    - ``selected_set.tud_hash == tud.tud_hash``
    - ``envelope.target_universe_declaration_hash == tud.tud_hash``
    - ``envelope.selected_set_hash == selected_set.selected_set_hash``
    - if ``plan``: its ``target_universe_declaration_hash`` / ``frozen_set_hash`` /
      ``envelope_hash`` all match the chain.

    A ``legacy_mode`` envelope ALWAYS raises here — a pre-v1.3 seal is auditable but
    cannot claim a clean v1.3 chain.
    """
    if envelope.legacy_mode:
        raise IdentityChainError(
            f"legacy envelope (frozen_set_hash={envelope.frozen_set_hash}) cannot assert a "
            "clean v1.3 identity chain; pre-v1.3 seals stay auditable but are not chain-clean"
        )

    tud_hash = tud.tud_hash
    selected_set_hash = selected_set.selected_set_hash

    if selected_set.tud_hash != tud_hash:
        raise IdentityChainError(
            f"SelectedSet.tud_hash={selected_set.tud_hash} != TargetUniverseDeclaration.tud_hash={tud_hash}"
        )
    if envelope.target_universe_declaration_hash != tud_hash:
        raise IdentityChainError(
            f"Envelope.target_universe_declaration_hash={envelope.target_universe_declaration_hash} "
            f"!= tud_hash={tud_hash}"
        )
    if envelope.selected_set_hash != selected_set_hash:
        raise IdentityChainError(
            f"Envelope.selected_set_hash={envelope.selected_set_hash} "
            f"!= SelectedSet.selected_set_hash={selected_set_hash}"
        )

    if plan is not None:
        if plan.target_universe_declaration_hash != tud_hash:
            raise IdentityChainError(
                f"Plan.target_universe_declaration_hash={plan.target_universe_declaration_hash} != tud_hash={tud_hash}"
            )
        if plan.frozen_set_hash != envelope.frozen_set_hash:
            raise IdentityChainError(
                f"Plan.frozen_set_hash={plan.frozen_set_hash} != Envelope.frozen_set_hash={envelope.frozen_set_hash}"
            )
        if plan.envelope_hash != envelope.envelope_hash:
            raise IdentityChainError(
                f"Plan.envelope_hash={plan.envelope_hash} != Envelope.envelope_hash={envelope.envelope_hash}"
            )
