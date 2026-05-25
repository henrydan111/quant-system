from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


SourceType = Literal["raw_field", "field_transform", "factor_alias"]
TransformFamily = Literal[
    "level_rank",
    "change",
    "acceleration",
    "stability",
    "relative_position",
    "ratio_spread",
    "persistence",
    "interaction",
]
EconomicRole = Literal[
    "core_thesis",
    "confirmation",
    "execution_guardrail",
    "diagnostic_only",
]
CoverageTier = Literal["A", "B", "C", "D"]
BoardPolicy = Literal["all", "mainboard"]
MembershipSource = Literal["all_market", "csi300", "csi500", "csi1000", "st_only"]
StMode = Literal["exclude", "include_only", "ignore"]


@dataclass(frozen=True)
class FieldInventoryRow:
    field_name: str
    field_family: str
    provider_source: str
    coverage_start: str
    coverage_end: str
    coverage_ratio: float
    freq_type: str
    pit_safe: bool
    theme_tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ComponentSpec:
    component_id: str
    theme_id: str
    source_fields: tuple[str, ...]
    source_type: SourceType
    transform_family: TransformFamily
    transform_params: dict[str, Any]
    expected_sign: int
    economic_role: EconomicRole
    coverage_tier: CoverageTier = "D"
    notes: str = ""


@dataclass(frozen=True)
class SignalRecipe:
    recipe_id: str
    theme_id: str
    component_ids: tuple[str, ...]
    weights: tuple[float, ...]
    construction_rule: str
    selection_note: str = ""


@dataclass(frozen=True)
class UniverseCandidate:
    candidate_id: str
    membership_source: MembershipSource
    board_policy: BoardPolicy
    st_mode: StMode
    min_listing_days: int
    market_cap_min: float | None = None
    market_cap_max: float | None = None
    price_cap: float | None = None
    liquidity_floor: float | None = None
    revenue_floor: float | None = None
    northbound_required: bool = False
    profitability_field: str | None = None
    profitability_positive: bool = False
    ret250_pctile_max: float | None = None
    special_filters: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable representation. Tuples are converted to lists.

        Plan ref: jolly-seeking-lollipop Gate A — added so PrescribedRecipe
        can roundtrip a UniverseCandidate via JSON. Reuse this method in
        any new code that needs to serialize a UniverseCandidate; do NOT
        write parallel ad-hoc serialization.
        """
        return {
            "candidate_id": self.candidate_id,
            "membership_source": self.membership_source,
            "board_policy": self.board_policy,
            "st_mode": self.st_mode,
            "min_listing_days": int(self.min_listing_days),
            "market_cap_min": self.market_cap_min,
            "market_cap_max": self.market_cap_max,
            "price_cap": self.price_cap,
            "liquidity_floor": self.liquidity_floor,
            "revenue_floor": self.revenue_floor,
            "northbound_required": bool(self.northbound_required),
            "profitability_field": self.profitability_field,
            "profitability_positive": bool(self.profitability_positive),
            "ret250_pctile_max": self.ret250_pctile_max,
            "special_filters": list(self.special_filters),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "UniverseCandidate":
        """Inverse of `to_dict`; restores special_filters tuple."""
        special = payload.get("special_filters", []) or []
        return cls(
            candidate_id=str(payload["candidate_id"]),
            membership_source=str(payload["membership_source"]),  # type: ignore[arg-type]
            board_policy=str(payload["board_policy"]),  # type: ignore[arg-type]
            st_mode=str(payload["st_mode"]),  # type: ignore[arg-type]
            min_listing_days=int(payload["min_listing_days"]),
            market_cap_min=payload.get("market_cap_min"),
            market_cap_max=payload.get("market_cap_max"),
            price_cap=payload.get("price_cap"),
            liquidity_floor=payload.get("liquidity_floor"),
            revenue_floor=payload.get("revenue_floor"),
            northbound_required=bool(payload.get("northbound_required", False)),
            profitability_field=payload.get("profitability_field"),
            profitability_positive=bool(payload.get("profitability_positive", False)),
            ret250_pctile_max=payload.get("ret250_pctile_max"),
            special_filters=tuple(str(item) for item in special),
        )


@dataclass(frozen=True)
class ThemeSpec:
    theme_id: str
    thesis: str
    benchmark: str
    data_start: str
    universe_candidates: tuple[UniverseCandidate, ...]
    anchor_recipes: tuple[str, ...]
    event_driven_defaults: dict[str, Any]
    topk_grid: tuple[int, ...]
    rebalance_grid: tuple[int, ...]
    recipe_seeds: tuple[str, ...]
    diagnostic_rebalance_days: int
    notes: str = ""


@dataclass(frozen=True)
class ComponentDiagnostic:
    component_id: str
    theme_id: str
    coverage_ratio: float
    coverage_tier: CoverageTier
    mean_rank_ic: float
    rank_icir: float
    positive_validation_folds: int
    total_validation_folds: int
    direction_consistent: bool
    max_abs_corr: float
    marginal_rank_icir: float
    cluster_id: str
    selection_score: float
    selected_for_recipe: bool
    rejection_reason: str = ""


@dataclass(frozen=True)
class VariantSummary:
    theme_id: str
    stage: str
    universe_id: str
    recipe_id: str
    topk: int
    rebalance_days: int
    stitched_relative_excess_return: float
    positive_excess_folds: int
    holdout_relative_excess_return: float
    worst_max_drawdown: float
    avg_turnover: float

