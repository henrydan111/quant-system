"""Pure runtime helpers for the hypothesis_validation profile (Gate C).

Translates a `PrescribedRecipe` into the concrete inputs needed by each
step handler:

- `materialize_universe(...)` → date-indexed eligibility map (NOT a flat set)
- `compute_factor_frame(...)` → DataFrame with one column per component
- `compute_composite_score(...)` → Series of composite scores per (date, instrument)
- `compute_schedule(...)` → target-weights schedule, codes converted Qlib → Tushare

Each function is a pure transformation: no I/O, no global state. The step
handlers in `validation_steps.py` orchestrate Qlib feature loading and pass
the resulting frames into these helpers.

Plan ref: jolly-seeking-lollipop Gate C.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

import numpy as np
import pandas as pd

from src.research_orchestrator.hypothesis import (
    CompositeKind,
    PrescribedComponent,
    PrescribedRecipe,
    UniverseSpec,
)

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# Universe materialization
# ════════════════════════════════════════════════════════════════════════════

def materialize_universe(
    *,
    universe: UniverseSpec,
    raw_fields: dict[str, pd.Series],
    support: Any,
    rebal_dates: list[pd.Timestamp],
    listing_days_ok: Callable[[str, pd.Timestamp], bool],
    theme_resolver: Callable[[str, str], Any] | None = None,
) -> dict[pd.Timestamp, set[str]]:
    """Return a date-indexed eligibility map for the prescription's universe.

    For `kind="theme"`: looks up the named UniverseCandidate inside the
    referenced ThemeSpec via `theme_resolver(theme_id, candidate_id)`.

    For `kind="broad"`: uses `universe.broad_filters` directly.

    Both paths delegate to `theme_strategy.pipeline.build_universe_eligibility`
    so the filter semantics are identical to discovery profiles.

    Args:
        universe: UniverseSpec from the prescription.
        raw_fields: dict of {field_name: Series} as in ThemeArtifacts.raw_fields.
        support: ResearchSupport bundle.
        rebal_dates: trading-day timestamps for which to materialize the map.
        listing_days_ok: callable (qlib_code, date) -> bool checking
            min_listing_days.
        theme_resolver: callable (theme_id, candidate_id) -> UniverseCandidate.
            Required for kind="theme".

    Returns:
        dict[date -> set[qlib_code]]: eligible instruments per rebalance date.
    """
    from src.alpha_research.theme_strategy.pipeline import build_universe_eligibility

    universe.validate()
    if universe.kind == "theme":
        if theme_resolver is None:
            raise ValueError(
                "materialize_universe(kind='theme') requires a theme_resolver "
                "callable (theme_id, candidate_id) -> UniverseCandidate"
            )
        candidate = theme_resolver(universe.theme_id, universe.theme_universe_candidate_id)
    else:
        candidate = universe.broad_filters
    return build_universe_eligibility(
        raw_fields=raw_fields,
        support=support,
        universe=candidate,
        rebal_dates=rebal_dates,
        listing_days_ok=listing_days_ok,
    )


# ════════════════════════════════════════════════════════════════════════════
# Factor frame computation
# ════════════════════════════════════════════════════════════════════════════

def compute_factor_frame(
    *,
    prescription: PrescribedRecipe,
    factor_series_map: dict[str, pd.Series],
) -> pd.DataFrame:
    """Assemble a DataFrame with one column per prescription component.

    Two-phase responsibility separation (Codex round-5 patch #4):
    - PERMISSION: handle_validation_object_resolver already proved every
      component is registry-approved BEFORE this function runs.
    - COMPUTATION: this function consumes a `factor_series_map` whose keys
      are the resolved factor names and whose values are precomputed Series
      (loaded by the dataset_build step from Qlib using the catalog
      expression). It does NOT re-check permission and does NOT load Qlib.

    For v1, only `kind="raw"` is supported (the inline transformations
    `industry_relative` and `size_industry_neutralized` are deferred to v2;
    transformed factor names like `val_bp_industry_rel` are referenced
    DIRECTLY with kind="raw" — see PrescribedComponent docstring).

    Args:
        prescription: validated PrescribedRecipe.
        factor_series_map: dict of {factor_name: Series} with each Series
            having a (datetime, instrument) MultiIndex. Caller guarantees
            every component name is present.

    Returns:
        DataFrame with one column per component, MultiIndex(datetime, instrument).
    """
    missing = [
        c.factor_name for c in prescription.components
        if c.factor_name not in factor_series_map
    ]
    if missing:
        # System inconsistency: registry approved but catalog cannot compute.
        raise KeyError(
            f"compute_factor_frame: factor_series_map missing entries for "
            f"{missing}. The resolver approved these but the dataset_build "
            f"step did not produce them. This indicates a mismatch between "
            f"factor_registry and factor_library.catalog / "
            f"get_industry_relative_defs() — investigate the imports."
        )
    columns: dict[str, pd.Series] = {}
    for component in prescription.components:
        columns[component.factor_name] = factor_series_map[component.factor_name]
    return pd.DataFrame(columns)


# ════════════════════════════════════════════════════════════════════════════
# Composite score computation
# ════════════════════════════════════════════════════════════════════════════

def compute_composite_score(
    *,
    factor_frame: pd.DataFrame,
    prescription: PrescribedRecipe,
) -> pd.Series:
    """Compute the cross-sectional composite score per (date, instrument).

    Algorithm:
    1. For each component, transform the raw factor series:
       - composite_kind="rank_weighted": cross-sectional percentile rank
         per date (rank_pct in [0, 1]).
       - composite_kind="zscore_weighted": cross-sectional z-score per date.
    2. Apply direction: sign = +1 for "higher_is_better", -1 for "lower_is_better".
    3. Multiply by absolute weight: contribution = sign * transform * weight.
    4. Sum contributions across components.

    Per Codex round-3, validate() rejects non-positive weights so we only
    handle weight > 0 here. The single source of sign is `direction`.

    Args:
        factor_frame: DataFrame from compute_factor_frame() with one column
            per component, MultiIndex(datetime, instrument).
        prescription: validated PrescribedRecipe; provides composite_kind,
            components (with weight + direction).

    Returns:
        Series of composite scores, MultiIndex(datetime, instrument).
    """
    if not factor_frame.columns.size:
        raise ValueError("compute_composite_score: factor_frame has no columns")

    contributions: list[pd.Series] = []
    for component in prescription.components:
        col = factor_frame[component.factor_name]
        if prescription.composite_kind == "rank_weighted":
            # Cross-sectional pct rank per date. Pandas rank(pct=True) handles ties.
            ranked = col.groupby(level="datetime").rank(pct=True, na_option="keep")
        elif prescription.composite_kind == "zscore_weighted":
            # Cross-sectional z-score per date.
            grouped = col.groupby(level="datetime")
            ranked = (col - grouped.transform("mean")) / grouped.transform("std")
        else:
            raise ValueError(
                f"compute_composite_score: unknown composite_kind={prescription.composite_kind!r}"
            )
        sign = 1.0 if component.direction == "higher_is_better" else -1.0
        contributions.append(sign * ranked * float(component.weight))

    composite = sum(contributions, start=pd.Series(0.0, index=factor_frame.index))
    composite.name = "composite_score"
    return composite


# ════════════════════════════════════════════════════════════════════════════
# Schedule (target weights) computation
# ════════════════════════════════════════════════════════════════════════════

def _qlib_to_tushare_code(qlib_code: str) -> str:
    """Convert ``000001_SZ`` (Qlib underscore form) to ``000001.SZ``
    (Tushare dot form). Per CLAUDE.md §3 hard invariant. Robust to mixed
    case input (the published provider uses lowercase suffixes)."""
    if "." in qlib_code:
        return qlib_code  # already Tushare-form
    if "_" in qlib_code:
        sym, exch = qlib_code.rsplit("_", 1)
        return f"{sym}.{exch.upper()}"
    return qlib_code


def compute_schedule(
    *,
    composite_score: pd.Series,
    eligible_map: dict[pd.Timestamp, set[str]],
    prescription: PrescribedRecipe,
) -> pd.DataFrame:
    """Build the target-weights schedule from composite scores + eligibility.

    Per rebalance date:
    1. Restrict to eligible instruments on that date.
    2. Take TopK by composite score (descending).
    3. Apply portfolio.weighting_rule + portfolio.score_to_weight (v1 only
       supports "equal" + "topk_equal", so each selected name gets weight
       target_gross_exposure / topk).
    4. Cap each weight by portfolio.max_position_weight (validate_against_topk
       already verified target_gross_exposure / topk ≤ max_position_weight).
    5. Convert qlib codes to Tushare dot-form for downstream event-driven
       backtester consumption.

    Args:
        composite_score: Series with MultiIndex(datetime, instrument).
        eligible_map: dict[date -> set of qlib_code] from materialize_universe.
        prescription: validated PrescribedRecipe.

    Returns:
        DataFrame with columns [datetime, ts_code, weight], one row per
        (rebalance_date, selected_stock). ts_code is Tushare dot-form.
    """
    rows: list[dict[str, Any]] = []
    per_name_weight = float(prescription.portfolio.target_gross_exposure) / int(prescription.topk)
    if per_name_weight > prescription.portfolio.max_position_weight + 1e-6:
        # Should already be caught by PortfolioConstruction.validate_against_topk;
        # belt-and-suspenders check.
        raise ValueError(
            f"compute_schedule: per-name weight {per_name_weight} exceeds "
            f"max_position_weight {prescription.portfolio.max_position_weight}"
        )

    score_reset = composite_score.reset_index()
    # Determine column names robustly (MultiIndex name order may vary).
    cols = score_reset.columns.tolist()
    dt_col = next((c for c in cols if "datetime" in str(c).lower() or "date" in str(c).lower()), cols[0])
    inst_col = next((c for c in cols if "instrument" in str(c).lower() or "stock" in str(c).lower() or "ts_code" in str(c).lower()), cols[1])
    score_col = cols[-1]

    for rebal_date, eligible in eligible_map.items():
        if not eligible:
            continue
        try:
            day_scores = score_reset[score_reset[dt_col] == rebal_date]
        except Exception:
            continue
        day_scores = day_scores[day_scores[inst_col].isin(eligible)]
        day_scores = day_scores.dropna(subset=[score_col])
        if day_scores.empty:
            continue
        topk = day_scores.nlargest(prescription.topk, score_col)
        for _, r in topk.iterrows():
            rows.append({
                "datetime": pd.Timestamp(rebal_date),
                "ts_code": _qlib_to_tushare_code(str(r[inst_col])),
                "weight": per_name_weight,
            })
    return pd.DataFrame(rows, columns=["datetime", "ts_code", "weight"])
