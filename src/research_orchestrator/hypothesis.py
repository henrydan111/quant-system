from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from src.alpha_research.walk_forward import TimeSplit
from src.research_orchestrator._types import AssetRef


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_text(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def _sorted_factor_refs(values: list[AssetRef]) -> list[dict[str, Any]]:
    ordered = sorted(
        values,
        key=lambda item: (
            str(item.object_type),
            str(item.object_name),
            str(item.object_id),
            str(item.definition_hash),
            int(item.version) if item.version is not None else -1,
        ),
    )
    return [item.to_dict() for item in ordered]


def _horizon_bucket(days: int) -> str:
    if days <= 5:
        return "1-5"
    if days <= 20:
        return "6-20"
    if days <= 60:
        return "21-60"
    return "60+"


class LaxCriteriaError(ValueError):
    """Raised when a formal hypothesis declares looser criteria than the profile floor rails."""


SUCCESS_CRITERIA_FLOORS: dict[str, dict[str, float]] = {
    "factor_screening": {
        "min_rank_icir": 0.02,
        "min_deflated_sharpe": 0.5,
        "min_cost_adjusted_sharpe": 0.3,
        "max_drawdown": 0.40,
        "max_annual_turnover": 5.0,
        "min_monotonicity_pvalue": 0.10,
        "max_correlation_to_approved": 0.85,
    },
    "theme_strategy": {
        "min_rank_icir": 0.025,
        "min_deflated_sharpe": 0.6,
        "min_cost_adjusted_sharpe": 0.4,
        "max_drawdown": 0.35,
        "max_annual_turnover": 4.0,
        "min_monotonicity_pvalue": 0.10,
        "max_correlation_to_approved": 0.80,
    },
    "event_driven_signal_research": {
        "min_rank_icir": 0.03,
        "min_deflated_sharpe": 0.8,
        "min_cost_adjusted_sharpe": 0.5,
        "max_drawdown": 0.35,
        "max_annual_turnover": 6.0,
        "min_monotonicity_pvalue": 0.10,
        "max_correlation_to_approved": 0.80,
    },
    "ml_signal_model_research": {
        "min_rank_icir": 0.03,
        "min_deflated_sharpe": 0.8,
        "min_cost_adjusted_sharpe": 0.5,
        "max_drawdown": 0.35,
        "max_annual_turnover": 6.0,
        "min_monotonicity_pvalue": 0.10,
        "max_correlation_to_approved": 0.80,
    },
    "strategy_improvement": {
        "min_rank_icir": 0.035,
        "min_deflated_sharpe": 1.0,
        "min_cost_adjusted_sharpe": 0.7,
        "max_drawdown": 0.30,
        "max_annual_turnover": 4.0,
        "min_monotonicity_pvalue": 0.05,
        "max_correlation_to_approved": 0.75,
    },
    # Plan ref: jolly-seeking-lollipop Gate A. Validation profile floors
    # mirror theme_strategy at v1 — tightenable later. Per Codex round-2,
    # CLI registration must accept --profile-id to validate ONLY against
    # the targeted profile's floors (not all profiles); without it, a
    # validation hypothesis with these floors would still fail
    # strategy_improvement validation.
    "hypothesis_validation": {
        "min_rank_icir": 0.025,
        "min_deflated_sharpe": 0.6,
        "min_cost_adjusted_sharpe": 0.4,
        "max_drawdown": 0.35,
        "max_annual_turnover": 4.0,
        "min_monotonicity_pvalue": 0.10,
        "max_correlation_to_approved": 0.80,
    },
}

FLOOR_DIRECTIONS: dict[str, Literal["at_least", "at_most"]] = {
    "min_rank_icir": "at_least",
    "min_deflated_sharpe": "at_least",
    "min_cost_adjusted_sharpe": "at_least",
    "max_drawdown": "at_most",
    "max_annual_turnover": "at_most",
    "min_monotonicity_pvalue": "at_most",
    "max_correlation_to_approved": "at_most",
}


def validate_success_criteria_floor_rails(
    hypothesis: "Hypothesis",
    profile_id: str,
    *,
    allow_override: bool = False,
) -> None:
    if allow_override:
        return
    floors = SUCCESS_CRITERIA_FLOORS.get(str(profile_id), {})
    if not floors:
        return
    criteria = hypothesis.success_criteria
    violations: list[str] = []
    for field_name, floor_value in floors.items():
        declared = getattr(criteria, field_name, None)
        direction = FLOOR_DIRECTIONS.get(field_name)
        if direction is None:
            raise ValueError(
                f"FLOOR_DIRECTIONS missing entry for {field_name!r} in profile {profile_id!r}"
            )
        if declared is None:
            op = ">=" if direction == "at_least" else "<="
            violations.append(
                f"{field_name} is None but profile {profile_id!r} requires declared {op} {floor_value}"
            )
            continue
        if direction == "at_least" and float(declared) < float(floor_value):
            violations.append(
                f"{field_name}={declared} is looser than profile {profile_id!r} floor {floor_value} (must be >=)"
            )
        if direction == "at_most" and float(declared) > float(floor_value):
            violations.append(
                f"{field_name}={declared} is looser than profile {profile_id!r} floor {floor_value} (must be <=)"
            )
    if violations:
        raise LaxCriteriaError("; ".join(violations))


@dataclass(frozen=True)
class HypothesisSource:
    source_type: Literal["academic_paper", "sellside_report", "domain", "market_observation"]
    identifier: str
    title: str
    authors: list[str] = field(default_factory=list)
    url: str = ""
    publication_date: str = ""
    publisher: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExpectedEffect:
    statistic: Literal["rank_ic", "icir", "sharpe", "alpha"]
    point_estimate: float
    ci_low: float
    ci_high: float
    horizon_days: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PreRegisteredConcerns:
    most_likely_failure_mode: str
    weakest_assumption: str
    what_would_falsify_this: str
    priors_on_cost_sensitivity: str = ""

    def normalized_dict(self) -> dict[str, str]:
        return {
            "most_likely_failure_mode": _normalize_text(self.most_likely_failure_mode),
            "weakest_assumption": _normalize_text(self.weakest_assumption),
            "what_would_falsify_this": _normalize_text(self.what_would_falsify_this),
            "priors_on_cost_sensitivity": _normalize_text(self.priors_on_cost_sensitivity),
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SuccessCriteria:
    min_rank_icir: float | None = None
    min_deflated_sharpe: float | None = None
    min_cost_adjusted_sharpe: float | None = None
    max_drawdown: float | None = None
    max_annual_turnover: float | None = None
    min_monotonicity_pvalue: float | None = None
    max_correlation_to_approved: float | None = None
    min_regime_pass_count: int | None = None
    effect_size_must_be_in_ci: bool = False
    custom_rules: list[dict[str, Any]] = field(default_factory=list)

    def normalized_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {key: value for key, value in payload.items() if value not in (None, [], {})}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ────────────────────────────────────────────────────────────────────────────
# Prescription schema (jolly-seeking-lollipop Gate A)
#
# A `PrescribedRecipe` lets a Hypothesis carry a fully-specified recipe
# (universe + components + composite + topk + rebalance + portfolio + costs)
# that the new `hypothesis_validation` profile runs verbatim through
# IS+gate+OOS+publish, instead of auto-searching. Existing profiles ignore
# this field; existing hypotheses without it remain byte-identical in
# `design_hash()` (the field is conditionally included only when not None).
#
# Codex round-1 through round-5 review history shaped these definitions:
# - UniverseKind: only "theme" + "broad" (membership folded into broad
#   because UniverseCandidate.membership_source already supports csi300/500/
#   1000/all_market/st_only).
# - CompositeKind: only "rank_weighted" / "zscore_weighted". Dropped
#   "ic_weighted" (would reintroduce discovery), "raw_weighted" (different
#   scales), "rank_sum_equal" (ambiguous about whether stored weights
#   matter).
# - PrescribedComponent: factor_name references the already-transformed name
#   directly with kind="raw" (e.g., "val_bp_industry_rel" not "val_bp" +
#   kind="industry_relative"). validate() rejects non-"raw" in v1. Weight
#   must be > 0; sign is carried by `direction`.
# - PortfolioConstruction: only weighting_rule="equal", side="long_only",
#   score_to_weight="topk_equal" in v1. validate_against_topk() enforces
#   feasibility against target_gross_exposure.
# - CostModel: when use_exchange_defaults=True, all other fields are
#   ignored. When False, slippage_bps/stamp_tax/half_spread_bps apply.
#   stamp_tax=False is implemented by constructing a CostConfig with stamp
#   rates set to zero — NOT a flag pass-through.
# - allow_candidate_components: opt-in escape hatch for accepting candidate-
#   registry-only factors (default False = require source_layer=="formal").
# ────────────────────────────────────────────────────────────────────────────

UniverseKind = Literal["theme", "broad"]
ComponentKind = Literal["raw", "industry_relative", "size_industry_neutralized"]
CompositeKind = Literal["rank_weighted", "zscore_weighted"]
WeightingRule = Literal["equal"]
PortfolioSide = Literal["long_only"]
ScoreToWeight = Literal["topk_equal"]
ComponentDirection = Literal["higher_is_better", "lower_is_better"]


@dataclass(frozen=True)
class UniverseSpec:
    kind: UniverseKind
    theme_id: str = ""
    theme_universe_candidate_id: str = ""
    broad_filters: Any = None  # UniverseCandidate; typed as Any to avoid circular import

    def validate(self) -> None:
        if self.kind == "theme":
            if not self.theme_id or not self.theme_universe_candidate_id:
                raise ValueError(
                    "UniverseSpec.kind='theme' requires both theme_id and theme_universe_candidate_id"
                )
            if self.broad_filters is not None:
                raise ValueError("UniverseSpec.kind='theme' must not set broad_filters")
        elif self.kind == "broad":
            if self.broad_filters is None:
                raise ValueError(
                    "UniverseSpec.kind='broad' requires broad_filters: UniverseCandidate"
                )
            from src.alpha_research.theme_strategy.schema import UniverseCandidate
            if not isinstance(self.broad_filters, UniverseCandidate):
                raise ValueError(
                    f"UniverseSpec.broad_filters must be UniverseCandidate, got {type(self.broad_filters).__name__}"
                )
            if self.theme_id or self.theme_universe_candidate_id:
                raise ValueError("UniverseSpec.kind='broad' must not set theme_id/theme_universe_candidate_id")
        else:
            raise ValueError(f"Unknown UniverseSpec.kind: {self.kind!r}")

    def normalized_dict(self) -> dict[str, Any]:
        """Stable dict for design_hash."""
        if self.kind == "theme":
            return {"kind": "theme", "theme_id": self.theme_id, "theme_universe_candidate_id": self.theme_universe_candidate_id}
        return {"kind": "broad", "broad_filters": self.broad_filters.to_dict()}

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "theme_id": self.theme_id,
            "theme_universe_candidate_id": self.theme_universe_candidate_id,
            "broad_filters": self.broad_filters.to_dict() if self.broad_filters is not None else None,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "UniverseSpec":
        broad_payload = payload.get("broad_filters")
        broad_filters = None
        if broad_payload is not None:
            from src.alpha_research.theme_strategy.schema import UniverseCandidate
            broad_filters = UniverseCandidate.from_dict(broad_payload)
        return cls(
            kind=str(payload["kind"]),  # type: ignore[arg-type]
            theme_id=str(payload.get("theme_id", "") or ""),
            theme_universe_candidate_id=str(payload.get("theme_universe_candidate_id", "") or ""),
            broad_filters=broad_filters,
        )


@dataclass(frozen=True)
class PrescribedComponent:
    factor_name: str
    weight: float
    kind: ComponentKind = "raw"
    direction: ComponentDirection = "higher_is_better"

    def to_dict(self) -> dict[str, Any]:
        return {
            "factor_name": self.factor_name,
            "weight": float(self.weight),
            "kind": self.kind,
            "direction": self.direction,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PrescribedComponent":
        return cls(
            factor_name=str(payload["factor_name"]),
            weight=float(payload["weight"]),
            kind=str(payload.get("kind", "raw")),  # type: ignore[arg-type]
            direction=str(payload.get("direction", "higher_is_better")),  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class CostModel:
    slippage_bps: float = 10.0
    stamp_tax: bool = True
    half_spread_bps: float = 0.0
    use_exchange_defaults: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CostModel":
        return cls(
            slippage_bps=float(payload.get("slippage_bps", 10.0)),
            stamp_tax=bool(payload.get("stamp_tax", True)),
            half_spread_bps=float(payload.get("half_spread_bps", 0.0)),
            use_exchange_defaults=bool(payload.get("use_exchange_defaults", False)),
        )


@dataclass(frozen=True)
class PortfolioConstruction:
    weighting_rule: WeightingRule = "equal"
    side: PortfolioSide = "long_only"
    target_gross_exposure: float = 1.0
    max_position_weight: float = 0.10
    score_to_weight: ScoreToWeight = "topk_equal"

    def validate_against_topk(self, topk: int) -> None:
        """Codex round-3: max_position_weight × topk must accommodate target_gross_exposure."""
        if self.max_position_weight * topk < self.target_gross_exposure - 1e-6:
            raise ValueError(
                f"PortfolioConstruction infeasible: max_position_weight ({self.max_position_weight}) "
                f"× topk ({topk}) = {self.max_position_weight * topk} < target_gross_exposure "
                f"({self.target_gross_exposure}). Either raise max_position_weight, raise topk, "
                f"or lower target_gross_exposure."
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PortfolioConstruction":
        return cls(
            weighting_rule=str(payload.get("weighting_rule", "equal")),  # type: ignore[arg-type]
            side=str(payload.get("side", "long_only")),  # type: ignore[arg-type]
            target_gross_exposure=float(payload.get("target_gross_exposure", 1.0)),
            max_position_weight=float(payload.get("max_position_weight", 0.10)),
            score_to_weight=str(payload.get("score_to_weight", "topk_equal")),  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class PrescribedRecipe:
    universe: UniverseSpec
    components: tuple[PrescribedComponent, ...]
    composite_kind: CompositeKind
    topk: int
    rebalance_days: int
    neutralization: tuple[str, ...] = field(default_factory=tuple)
    portfolio: PortfolioConstruction = field(default_factory=PortfolioConstruction)
    cost_model: CostModel = field(default_factory=CostModel)
    allow_candidate_components: bool = False
    # UNFREEZE_PLAN.md D1 / GPT R4-M2: the calendar policy this prescription is
    # pinned to. REQUIRED for formal backtest steps — _formal_calendar_policy_id
    # fails closed when unset and NEVER falls back to the live provider
    # manifest. None (not "") is the unset sentinel per POLICY001b.
    calendar_policy_id: str | None = None

    def validate(self) -> None:
        self.universe.validate()
        if not self.components:
            raise ValueError("PrescribedRecipe.components must be non-empty")
        if self.topk <= 0:
            raise ValueError(f"PrescribedRecipe.topk must be > 0, got {self.topk}")
        if self.rebalance_days <= 0:
            raise ValueError(f"PrescribedRecipe.rebalance_days must be > 0, got {self.rebalance_days}")
        names = [c.factor_name for c in self.components]
        if len(set(names)) != len(names):
            raise ValueError("PrescribedRecipe.components: duplicate factor_name")
        # v1 ComponentKind enforcement (Codex round-5 patch #3): the Literal allows future
        # values but v1 only supports kind="raw". Reject others with a clear, actionable message.
        for c in self.components:
            if c.kind != "raw":
                raise ValueError(
                    f"PrescribedComponent kind={c.kind!r} not supported in v1 — only 'raw' is "
                    f"available. For industry-relative variants (val_bp_industry_rel, mom_idio_20d, "
                    f"etc.), reference the already-transformed factor name DIRECTLY with kind='raw'. "
                    f"Inline 'industry_relative'/'size_industry_neutralized' transforms are deferred to v2."
                )
            if c.weight <= 0:
                raise ValueError(
                    f"PrescribedComponent {c.factor_name!r}: weight must be > 0; "
                    f"use direction for sign (got weight={c.weight})"
                )
        # Codex round-3: portfolio feasibility against topk
        self.portfolio.validate_against_topk(self.topk)
        # Allow only "size" and "industry" neutralization in v1
        for n in self.neutralization:
            if n not in ("size", "industry"):
                raise ValueError(
                    f"PrescribedRecipe.neutralization: unknown {n!r}; allowed = ('size', 'industry')"
                )

    def normalized_dict(self) -> dict[str, Any]:
        """Stable dict for design_hash. Sort components by factor_name for determinism."""
        sorted_components = sorted(
            (c.to_dict() for c in self.components),
            key=lambda d: d["factor_name"],
        )
        return {
            "universe": self.universe.normalized_dict(),
            "components": sorted_components,
            "composite_kind": self.composite_kind,
            "topk": int(self.topk),
            "rebalance_days": int(self.rebalance_days),
            "neutralization": sorted(self.neutralization),
            "portfolio": self.portfolio.to_dict(),
            "cost_model": self.cost_model.to_dict(),
            "allow_candidate_components": bool(self.allow_candidate_components),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "universe": self.universe.to_dict(),
            "components": [c.to_dict() for c in self.components],
            "composite_kind": self.composite_kind,
            "topk": int(self.topk),
            "rebalance_days": int(self.rebalance_days),
            "neutralization": list(self.neutralization),
            "portfolio": self.portfolio.to_dict(),
            "cost_model": self.cost_model.to_dict(),
            "allow_candidate_components": bool(self.allow_candidate_components),
            # R4-M2: the pin must survive the request-file round trip
            # (to_dict/from_dict is the NORMAL formal-run path). Deliberately
            # NOT in normalized_dict()/design_hash — execution-environment
            # binding, not design identity.
            "calendar_policy_id": self.calendar_policy_id,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PrescribedRecipe":
        raw_policy = payload.get("calendar_policy_id")
        return cls(
            universe=UniverseSpec.from_dict(payload["universe"]),
            components=tuple(PrescribedComponent.from_dict(c) for c in payload.get("components", [])),
            composite_kind=str(payload["composite_kind"]),  # type: ignore[arg-type]
            topk=int(payload["topk"]),
            rebalance_days=int(payload["rebalance_days"]),
            neutralization=tuple(str(n) for n in payload.get("neutralization", [])),
            portfolio=PortfolioConstruction.from_dict(payload.get("portfolio", {})),
            cost_model=CostModel.from_dict(payload.get("cost_model", {})),
            allow_candidate_components=bool(payload.get("allow_candidate_components", False)),
            calendar_policy_id=str(raw_policy) if raw_policy is not None else None,
        )


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    thesis_statement: str
    mechanism: str
    source: HypothesisSource
    factor_refs: list[AssetRef] = field(default_factory=list)
    factor_yaml_hashes: list[str] = field(default_factory=list)
    universe: str = ""
    benchmark: str = ""
    time_split: TimeSplit | None = None
    rebalance_frequency: str = ""
    neutralization: list[str] = field(default_factory=list)
    expected_sign: int = 1
    expected_effect: ExpectedEffect | None = None
    expected_decay_horizon_days: int = 0
    success_criteria: SuccessCriteria = field(default_factory=SuccessCriteria)
    pre_registered_concerns: PreRegisteredConcerns | None = None
    pre_registered_at: str = ""
    registered_by: str = ""
    # jolly-seeking-lollipop Gate A: optional prescription for the new
    # hypothesis_validation profile. Last position keeps kwarg compat.
    prescription: PrescribedRecipe | None = None

    def validate(self) -> None:
        if not self.hypothesis_id:
            raise ValueError("Hypothesis.hypothesis_id is required")
        if not self.universe:
            raise ValueError("Hypothesis.universe is required")
        if not self.benchmark:
            raise ValueError("Hypothesis.benchmark is required")
        if self.expected_effect is None:
            raise ValueError("Hypothesis.expected_effect is required")
        if self.pre_registered_concerns is None:
            raise ValueError("Hypothesis.pre_registered_concerns is required")
        if self.time_split is None:
            raise ValueError("Hypothesis.time_split is required")
        if not self.time_split.is_start:
            raise ValueError("Hypothesis.time_split.is_start is required")
        if not self.time_split.is_end:
            raise ValueError("Hypothesis.time_split.is_end is required")
        if not self.time_split.oos_start:
            raise ValueError("Hypothesis.time_split.oos_start is required")
        if not self.time_split.oos_end:
            raise ValueError("Hypothesis.time_split.oos_end is required")
        for ref in self.factor_refs:
            ref.validate()
        if self.prescription is not None:
            self.prescription.validate()

    def design_hash(self) -> str:
        self.validate()
        payload = {
            "factor_refs": _sorted_factor_refs(self.factor_refs),
            "factor_yaml_hashes": sorted(str(value).strip() for value in self.factor_yaml_hashes if str(value).strip()),
            "universe": _normalize_text(self.universe),
            "benchmark": _normalize_text(self.benchmark),
            "time_split": {
                key: value
                for key, value in sorted(self.time_split.to_dict().items())
                if key != "stage"
            },
            "rebalance_frequency": _normalize_text(self.rebalance_frequency),
            "neutralization": sorted(_normalize_text(value) for value in self.neutralization if _normalize_text(value)),
            "expected_sign": int(self.expected_sign),
            "expected_effect": self.expected_effect.to_dict(),
            "expected_decay_horizon_days": int(self.expected_decay_horizon_days),
            "success_criteria": self.success_criteria.normalized_dict(),
            "pre_registered_concerns": self.pre_registered_concerns.normalized_dict(),
        }
        # Backward-compat invariant: include prescription ONLY when non-None
        # so design_hash() is byte-identical for hypotheses that pre-date this
        # field. Existing seals and cache rows keyed on design_hash remain valid.
        if self.prescription is not None:
            payload["prescription"] = self.prescription.normalized_dict()
        return _sha256_text(_json_dumps(payload))

    def prose_hash(self) -> str:
        payload = {
            "thesis_statement": str(self.thesis_statement),
            "mechanism": str(self.mechanism),
            "source": self.source.to_dict(),
            "pre_registered_at": str(self.pre_registered_at),
            "registered_by": str(self.registered_by),
        }
        return _sha256_text(_json_dumps(payload))

    def structural_family(self) -> str:
        ref_types = sorted({ref.object_type for ref in self.factor_refs})
        horizon = int(self.expected_effect.horizon_days) if self.expected_effect is not None else 0
        payload = {
            "factor_types": ref_types,
            "factor_yaml_hashes": sorted(str(value) for value in self.factor_yaml_hashes),
            "universe": _normalize_text(self.universe),
            "benchmark": _normalize_text(self.benchmark),
            "neutralization": sorted(_normalize_text(value) for value in self.neutralization if _normalize_text(value)),
            "horizon_days": horizon,
        }
        return _sha256_text(_json_dumps(payload))

    def economic_family(self) -> str:
        payload = {
            "factor_refs": _sorted_factor_refs(self.factor_refs),
            "factor_yaml_hashes": sorted(str(value) for value in self.factor_yaml_hashes),
            "horizon_bucket": _horizon_bucket(int(self.expected_decay_horizon_days or 0)),
            "neutralization": sorted(
                _normalize_text(value) for value in self.neutralization if _normalize_text(value)
            ),
        }
        return _sha256_text(_json_dumps(payload))[:32]

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "thesis_statement": self.thesis_statement,
            "mechanism": self.mechanism,
            "source": self.source.to_dict(),
            "factor_refs": [item.to_dict() for item in self.factor_refs],
            "factor_yaml_hashes": list(self.factor_yaml_hashes),
            "universe": self.universe,
            "benchmark": self.benchmark,
            "time_split": self.time_split.to_dict() if self.time_split is not None else None,
            "rebalance_frequency": self.rebalance_frequency,
            "neutralization": list(self.neutralization),
            "expected_sign": self.expected_sign,
            "expected_effect": self.expected_effect.to_dict() if self.expected_effect is not None else None,
            "expected_decay_horizon_days": self.expected_decay_horizon_days,
            "success_criteria": self.success_criteria.to_dict(),
            "pre_registered_concerns": (
                self.pre_registered_concerns.to_dict() if self.pre_registered_concerns is not None else None
            ),
            "pre_registered_at": self.pre_registered_at,
            "registered_by": self.registered_by,
            "prescription": self.prescription.to_dict() if self.prescription is not None else None,
            "design_hash": self.design_hash(),
            "prose_hash": self.prose_hash(),
            "structural_family": self.structural_family(),
            "economic_family": self.economic_family(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Hypothesis":
        expected_effect_payload = payload.get("expected_effect")
        concerns_payload = payload.get("pre_registered_concerns")
        return cls(
            hypothesis_id=str(payload.get("hypothesis_id", "") or ""),
            thesis_statement=str(payload.get("thesis_statement", "") or ""),
            mechanism=str(payload.get("mechanism", "") or ""),
            source=HypothesisSource(**dict(payload.get("source", {}))),
            factor_refs=[AssetRef(**item) for item in payload.get("factor_refs", [])],
            factor_yaml_hashes=[str(item) for item in payload.get("factor_yaml_hashes", [])],
            universe=str(payload.get("universe", "") or ""),
            benchmark=str(payload.get("benchmark", "") or ""),
            time_split=TimeSplit.from_dict(dict(payload.get("time_split", {}))) if payload.get("time_split") else None,
            rebalance_frequency=str(payload.get("rebalance_frequency", "") or ""),
            neutralization=[str(item) for item in payload.get("neutralization", [])],
            expected_sign=int(payload.get("expected_sign", 1) or 1),
            expected_effect=ExpectedEffect(**dict(expected_effect_payload)) if expected_effect_payload else None,
            expected_decay_horizon_days=int(payload.get("expected_decay_horizon_days", 0) or 0),
            success_criteria=SuccessCriteria(**dict(payload.get("success_criteria", {}))),
            pre_registered_concerns=(
                PreRegisteredConcerns(**dict(concerns_payload)) if concerns_payload else None
            ),
            pre_registered_at=str(payload.get("pre_registered_at", "") or ""),
            registered_by=str(payload.get("registered_by", "") or ""),
            prescription=(
                PrescribedRecipe.from_dict(payload["prescription"])
                if payload.get("prescription") is not None
                else None
            ),
        )
