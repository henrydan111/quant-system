"""D5 — the Stage-3 machine-binding reader.

Design: ``workspace/research/factor_eval_methodology/FACTOR_EVAL_PARTG_BUILD_DESIGN.md``
(v2, D5). Reads the 7-universe matrix (``unified_eval_universe_matrix`` →
``results.jsonl``) for one factor and emits a TARGET- and ROLE-aware
:class:`Stage3QualityRecord`. The CLI ``gate`` / ``select`` commands (D4) MUST read this.

This module REUSES the engines — it does NOT re-implement the gate or the ceiling:

  * ``status_effect`` is produced by calling ``resolve_replication_ceiling`` (the P-GATE
    lattice) on the DECLARED-TARGET universe row — mapped onto the existing
    ``STATUS_CEILINGS`` (no parallel status universe).
  * ``target_universe_pass`` (ranking) is produced by calling ``assign_candidate_status``
    (the exact IS bar |rank_icir|≥0.10 ∧ sign_consistency≥0.70) on the target row.

The ONLY new logic is the cross-universe flags
(``sign_flip_across_core_universes`` / ``liquid_fail`` / ``illiquidity_bound``). They are
DIAGNOSTIC quality flags surfaced for the human + select stage — the v1.3 §5 rule holds:
cross-universe divergence does NOT auto-cap unless it is a fail ON the declared target
(captured by ``target_universe_pass``), so a small-cap-target factor is never re-blocked
merely for flipping in CSI300.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from src.alpha_research.factor_eval_skill.identity import TargetUniverseDeclaration
from src.alpha_research.factor_eval_skill.stores import ROLES, Stage3QualityRecordStore
from src.alpha_research.factor_lifecycle.status_rules import (
    CAND_HELDOUT_ICIR_MIN,
    CAND_SIGN_CONSISTENCY_MIN,
    assign_candidate_status,
)
from src.alpha_research.factor_registry.replication_governance import (
    resolve_replication_ceiling,
)

# The broad-market cap-benchmark universes used for the sign-flip DIAGNOSIS (not a cap).
# NOTE (GPT cross-review): this is deliberately the four cap-index benchmarks — univ_growth /
# univ_liquid_top300 / univ_microcap are EXCLUDED here because their divergence is covered by
# dedicated flags (liquid_fail, illiquidity_bound) or is a style signal, not a market-segment
# reversal. The flag name says "core" (these four), not "all", to avoid overclaiming.
CORE_UNIVERSES = ("univ_all", "univ_csi300", "univ_csi500", "univ_csi1000")
LIQUID_UNIVERSE = "univ_liquid_top300"
MICROCAP_UNIVERSE = "univ_microcap"
ALL_UNIVERSES = (
    "univ_all",
    "univ_csi300",
    "univ_csi500",
    "univ_csi1000",
    "univ_growth",
    LIQUID_UNIVERSE,
    MICROCAP_UNIVERSE,
)

# Below this |heldout_rank_icir| the sign is noise — it does not count as a determinate
# direction for cross-universe flip detection.
SIGN_EPSILON = 0.05

# Matrix row keys (the unified_eval results.jsonl 54-col schema).
_K_FACTOR = "factor"
_K_UNIVERSE = "universe_id"
_K_ICIR = "heldout_rank_icir"
_K_MEAN_IC = "mean_rank_ic"
_K_SIGN = "sign_consistency"
_K_COV_TIER = "coverage_tier"
_K_EFF_DAYS = "effective_ic_days"
_K_FIELD_OK = "field_eligible"
_K_L1_HASH = "layer1_methodology_hash"
# Core metrics a row must carry to be trusted in strict mode. effective_ic_days is included
# (GPT re-verify 2026-06-21): the P-GATE temporal-depth cap only fires when effective_ic_days
# is NOT None, so a row missing it would silently dodge the availability floor.
_CORE_METRIC_KEYS = (_K_ICIR, _K_SIGN, _K_COV_TIER, _K_EFF_DAYS)


class MatrixResults:
    """Index of a unified-eval ``results.jsonl`` by ``(factor, universe_id)``.

    ``strict=True`` fails the load on malformed evidence (GPT cross-review 2026-06-21) — the
    Stage-3 reader must not silently trust duplicate / errored / incomplete rows: duplicate
    factor×universe, a row carrying an ``error``, a blank/unknown ``universe_id``, a missing
    ``layer1_methodology_hash``, or a missing core metric. ``strict_factor`` SCOPES the strict
    check to one factor-under-eval (other factors' legitimately-incomplete rows — e.g.
    northbound on microcap — load lenient); ``strict`` with no ``strict_factor`` validates the
    whole file. Default ``strict=False`` preserves the lenient loader for ad-hoc inspection."""

    def __init__(self, rows: list[Mapping[str, Any]], *, strict: bool = False,
                 strict_factor: str | None = None) -> None:
        self._by_factor: dict[str, dict[str, dict]] = defaultdict(dict)
        errors: list[str] = []
        for i, row in enumerate(rows):
            factor = row.get(_K_FACTOR)
            universe = row.get(_K_UNIVERSE)
            in_scope = strict and (strict_factor is None or str(factor or "") == str(strict_factor))
            if not factor or not universe:
                if in_scope:
                    errors.append(f"row {i}: blank factor/universe_id")
                continue
            factor, universe = str(factor), str(universe)
            if in_scope:
                if universe not in ALL_UNIVERSES:
                    errors.append(f"row {i} ({factor}): unknown universe_id {universe!r}")
                if universe in self._by_factor.get(factor, {}):
                    errors.append(f"row {i}: duplicate {factor} x {universe}")
                if row.get("error"):
                    errors.append(f"row {i} ({factor} x {universe}): carries error={row['error']!r}")
                if not str(row.get(_K_L1_HASH, "")).strip():
                    errors.append(f"row {i} ({factor} x {universe}): missing layer1_methodology_hash")
                for key in _CORE_METRIC_KEYS:
                    if row.get(key) is None:
                        errors.append(f"row {i} ({factor} x {universe}): missing {key}")
            self._by_factor[factor][universe] = dict(row)
        if strict and errors:
            shown = "\n  ".join(errors[:20])
            raise ValueError(f"MatrixResults strict validation failed ({len(errors)} issue(s)):\n  {shown}")

    @classmethod
    def from_jsonl(cls, path: str | Path, *, strict: bool = False,
                   strict_factor: str | None = None) -> "MatrixResults":
        rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
        return cls(rows, strict=strict, strict_factor=strict_factor)

    def universe_rows(self, factor_id: str) -> dict[str, dict]:
        return dict(self._by_factor.get(str(factor_id), {}))

    def row(self, factor_id: str, universe_id: str) -> dict | None:
        return self._by_factor.get(str(factor_id), {}).get(str(universe_id))

    def has_factor(self, factor_id: str) -> bool:
        return str(factor_id) in self._by_factor


def _f(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        out = float(value)
        return out if out == out else default  # NaN-safe
    except (TypeError, ValueError):
        return default


def _orientation(row: Mapping[str, Any] | None) -> int:
    """+1 / -1 for a determinate IS direction, 0 if missing or |ICIR| < SIGN_EPSILON."""
    if row is None:
        return 0
    icir = _f(row.get(_K_ICIR))
    if abs(icir) < SIGN_EPSILON:
        return 0
    return 1 if icir > 0 else -1


@dataclass(frozen=True)
class Stage3QualityRecord:
    """Target+role-aware Stage-3 caps for one factor. ``status_effect`` is a
    ``STATUS_CEILINGS`` value; ``target_universe_pass`` is the IS-bar verdict on the
    DECLARED target (``None`` for a pure filter — the IC bar does not apply)."""

    factor_id: str
    definition_hash: str
    layer1_methodology_hash: str
    target_universe_declaration_hash: str
    target_universe_id: str
    role: str
    quality_flags: dict
    universe_profile: dict
    target_universe_pass: bool | None
    cross_universe_sign_divergence: bool
    status_effect: str
    ranking_component: dict | None = field(default=None)
    filter_component: dict | None = field(default=None)

    def persist(self, store: Stage3QualityRecordStore) -> dict[str, Any]:
        """Append this record to the Stage3QualityRecordStore (the scope-keyed sidecar)."""
        return store.record_quality(
            factor_id=self.factor_id,
            definition_hash=self.definition_hash,
            layer1_methodology_hash=self.layer1_methodology_hash,
            target_universe_declaration_hash=self.target_universe_declaration_hash,
            role=self.role,
            quality_flags=self.quality_flags,
            universe_profile=self.universe_profile,
            target_universe_pass=self.target_universe_pass,  # None (filter) -> "na" in the store
            cross_universe_sign_divergence=self.cross_universe_sign_divergence,
            status_effect=self.status_effect,
        )


def _universe_profile(urows: Mapping[str, dict]) -> dict:
    profile = {}
    for universe, row in urows.items():
        profile[universe] = {
            "heldout_rank_icir": _f(row.get(_K_ICIR)),
            "mean_rank_ic": _f(row.get(_K_MEAN_IC)),
            "sign_consistency": _f(row.get(_K_SIGN)),
            "coverage_tier": str(row.get(_K_COV_TIER, "")),
            "field_eligible": bool(row.get(_K_FIELD_OK, False)),
        }
    return profile


def _cross_universe_flags(urows: Mapping[str, dict], target_row: Mapping[str, Any] | None) -> dict:
    """The NEW cross-universe diagnostics (not a cap by themselves)."""
    # sign flip across the broad-market core universes (determinate signs only)
    core_signs = [_orientation(urows.get(u)) for u in CORE_UNIVERSES if urows.get(u) is not None]
    determinate = {s for s in core_signs if s != 0}
    sign_flip = len(determinate) > 1

    primary_sign = _orientation(urows.get("univ_all"))
    liquid = urows.get(LIQUID_UNIVERSE)
    micro = urows.get(MICROCAP_UNIVERSE)

    # liquid_fail: not evaluated on liquid, OR weak on liquid, OR sign disagrees with primary
    if liquid is None:
        liquid_fail = True
    else:
        liquid_weak = abs(_f(liquid.get(_K_ICIR))) < CAND_HELDOUT_ICIR_MIN
        liquid_sign = _orientation(liquid)
        liquid_flipped = primary_sign != 0 and liquid_sign != 0 and liquid_sign != primary_sign
        liquid_fail = bool(liquid_weak or liquid_flipped)

    # illiquidity_bound (the E-wave failure mode): strong on microcap, weak on liquid
    illiquidity_bound = False
    if micro is not None and liquid is not None:
        micro_strong = abs(_f(micro.get(_K_ICIR))) >= CAND_HELDOUT_ICIR_MIN
        liquid_weak = abs(_f(liquid.get(_K_ICIR))) < CAND_HELDOUT_ICIR_MIN
        illiquidity_bound = bool(micro_strong and liquid_weak)

    coverage_sub = bool(target_row is not None and str(target_row.get(_K_COV_TIER, "")) == "sub")
    field_ineligible_on_target = bool(target_row is not None and not target_row.get(_K_FIELD_OK, False))

    return {
        "sign_flip_across_core_universes": sign_flip,
        "liquid_fail": liquid_fail,
        "illiquidity_bound": illiquidity_bound,
        "coverage_sub": coverage_sub,
        "field_ineligible_on_target": field_ineligible_on_target,
    }


@dataclass(frozen=True)
class Stage3GovernanceInputs:
    """Explicit P-GATE governance inputs — the caller MUST declare native vs cohort so a
    cohort factor can never be silently under-capped by permissive defaults (GPT cross-review
    2026-06-21). Use :meth:`native` for a base catalog factor (no replication concern) or
    :meth:`cohort` for a CICC-cohort factor (manifest-resolved values REQUIRED)."""

    factor_class: str  # "native" | "cohort"
    replication_tier: str
    claim_class: str
    oos_eligibility: str
    require_claim: bool
    max_stat_calibrated: bool = False
    denominator_frozen: bool = True
    has_uncertified_operator: bool = False
    truth_observed: bool = False
    power_floor_pass: bool = False

    @classmethod
    def native(cls) -> "Stage3GovernanceInputs":
        """A base catalog factor: no replication concern, no domain-claim requirement."""
        return cls(
            factor_class="native", replication_tier="exact_certified",
            claim_class="clean_singleton_primary", oos_eligibility="pending", require_claim=False,
        )

    @classmethod
    def cohort(
        cls, *, replication_tier: str, claim_class: str, oos_eligibility: str,
        require_claim: bool = True, **kwargs: Any,
    ) -> "Stage3GovernanceInputs":
        """A CICC-cohort factor: the manifest-resolved tier + OOS eligibility + claim are
        REQUIRED. Fail-closed if any are blank."""
        if not str(replication_tier).strip() or not str(oos_eligibility).strip():
            raise ValueError("cohort governance requires manifest-resolved replication_tier + oos_eligibility")
        if require_claim and not str(claim_class).strip():
            raise ValueError("cohort governance requires a resolved FactorDomainClaim (claim_class)")
        return cls(
            factor_class="cohort", replication_tier=replication_tier, claim_class=claim_class,
            oos_eligibility=oos_eligibility, require_claim=require_claim, **kwargs,
        )


def stage3_caps(
    matrix: MatrixResults,
    *,
    factor_id: str,
    definition_hash: str,
    tud: TargetUniverseDeclaration,
    role: str,
    governance: Stage3GovernanceInputs,
    ceiling_overrides: Mapping[str, Any] | None = None,
) -> Stage3QualityRecord:
    """Read the 7-universe matrix for ``factor_id`` and emit target+role-aware caps.

    ``tud`` supplies BOTH the declared ``target_universe_id`` (which row is the target) and
    the ``tud_hash`` (the store scope key). ``governance`` (``Stage3GovernanceInputs.native()``
    or ``.cohort(...)``) supplies the P-GATE inputs EXPLICITLY — a cohort factor cannot be
    under-capped by a forgotten manifest value. ``layer1_methodology_hash`` is DERIVED from the
    matrix rows (authoritative for the Layer-1 methodology). ``status_effect`` is the
    ``resolve_replication_ceiling`` ceiling on the target row; ``target_universe_pass`` is
    ``assign_candidate_status`` on the target row.
    """
    role_norm = str(role).strip().lower()
    if role_norm not in ROLES:
        raise ValueError(f"role must be one of {ROLES}, got {role!r}")

    urows = matrix.universe_rows(factor_id)
    target_universe_id = tud.target_universe_id
    target_row = urows.get(target_universe_id)

    # layer1_methodology_hash: authoritative from the matrix (reference-invariant → same
    # across universes); prefer the target row, fall back to any row, else "".
    l1_hash = ""
    if target_row is not None:
        l1_hash = str(target_row.get(_K_L1_HASH, ""))
    elif urows:
        l1_hash = str(next(iter(urows.values())).get(_K_L1_HASH, ""))

    profile = _universe_profile(urows)
    flags = _cross_universe_flags(urows, target_row)

    # ---- status_effect: CALL the P-GATE on the target row (fail-closed if absent) ----
    coverage_observed = target_row is not None
    coverage_tier = str(target_row.get(_K_COV_TIER, "")) if target_row is not None else ""
    effective_ic_days = target_row.get(_K_EFF_DAYS) if target_row is not None else None
    overrides = dict(ceiling_overrides or {})
    decision = resolve_replication_ceiling(
        replication_tier=governance.replication_tier,
        claim_class=governance.claim_class,
        coverage_tier=coverage_tier,
        effective_ic_days=effective_ic_days,
        oos_eligibility=governance.oos_eligibility,
        coverage_observed=coverage_observed,
        require_claim=governance.require_claim,
        max_stat_calibrated=governance.max_stat_calibrated,
        denominator_frozen=governance.denominator_frozen,
        has_uncertified_operator=governance.has_uncertified_operator,
        truth_observed=governance.truth_observed,
        power_floor_pass=governance.power_floor_pass,
        **overrides,
    )
    status_effect = decision.status_ceiling

    # ---- target_universe_pass: CALL the IS bar on the target row (ranking only) ----
    def _ranking_pass() -> bool:
        if target_row is None:
            return False
        field_ok = bool(target_row.get(_K_FIELD_OK, False))
        status, _reason = assign_candidate_status(
            field_ok, _f(target_row.get(_K_ICIR)), _f(target_row.get(_K_SIGN))
        )
        return status == "candidate"

    ranking_component: dict | None = None
    filter_component: dict | None = None
    if role_norm == "ranking":
        target_universe_pass: bool | None = _ranking_pass()
    elif role_norm == "filter":
        # A filter is CHARACTERIZED in a StrategyContext (Stage 8 / FilterCharacterizationStore),
        # NOT given an IC pass/fail here. The IC bar does not apply.
        target_universe_pass = None
        filter_component = {
            "ic_bar_applicable": False,
            "characterization_pending": True,
            "note": "filter pass/fail is a Stage-8 strategy A/B, not an IC bar",
        }
    else:  # both
        rp = _ranking_pass()
        target_universe_pass = rp
        ranking_component = {"target_universe_pass": rp, "status_effect": status_effect}
        filter_component = {"ic_bar_applicable": False, "characterization_pending": True}

    return Stage3QualityRecord(
        factor_id=str(factor_id),
        definition_hash=str(definition_hash),
        layer1_methodology_hash=l1_hash,
        target_universe_declaration_hash=tud.tud_hash,
        target_universe_id=str(target_universe_id),
        role=role_norm,
        quality_flags=flags,
        universe_profile=profile,
        target_universe_pass=target_universe_pass,
        cross_universe_sign_divergence=bool(flags["sign_flip_across_core_universes"]),
        status_effect=status_effect,
        ranking_component=ranking_component,
        filter_component=filter_component,
    )
