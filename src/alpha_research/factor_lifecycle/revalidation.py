"""Factor-lifecycle revalidation — the two strictly-separated modes (Phase 4).

  * ``run_historical_*`` (mode 2) — NON-formal full-window (IS + OOS) revalidation; a
    faithful port of the legacy ``revalidate_*.py`` scripts. Results are
    ``historical_investigation`` (Phase 2 imports them as ``formal_evidence_eligible=False``).
  * ``run_is_walk_forward`` (mode 1, in ``walk_forward_validation.py``) — the FORMAL
    IS-only validator; structurally bounded so neither OOS prices NOR OOS-realizing
    labels are ever loaded.

The shared, data-loading-free core is ``revalidate_panel`` (testable without Qlib): it
takes an already-computed factor panel + forward return and emits the historical metric
rows. The window slicing here (``is_end`` / ``oos_start``) is the HISTORICAL mode's IS/OOS
split — it deliberately spans OOS and is therefore non-formal.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

from . import metrics
from .status_rules import assign_historical_status

# Canonical revalidation window (frozen, from the legacy scripts).
START = "2014-01-01"
END = "2026-02-27"
IS_END = "2020-12-31"
OOS_START = "2021-01-01"
HORIZON = 20

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_FIELD_STATUS = _PROJECT_ROOT / "config" / "field_registry" / "field_status.yaml"
_DEFAULT_QLIB_DIR = _PROJECT_ROOT / "data" / "qlib_data"

# This module IS the historical (mode-2) revalidation. It is non-formal by construction.
RESULT_EVIDENCE_CLASS = "historical_investigation"


def _field_eligible(expr: str, registry) -> bool:
    """True iff every ``$field`` in ``expr`` is allowed at the formal_validation stage.
    Ported from ``revalidate_catalog_walkforward.field_eligible``."""
    from src.data_infra.field_registry import extract_qlib_fields

    for tok in extract_qlib_fields(expr):
        if not registry.resolve_field(tok, "formal_validation").allowed:
            return False
    return True


def revalidate_panel(
    factor_panel: pd.DataFrame,
    forward_return: pd.Series,
    *,
    is_end: str = IS_END,
    oos_start: str = OOS_START,
    field_eligible: Mapping[str, bool] | None = None,
    kinds: Mapping[str, str] | None = None,
    compute_long_only: bool = False,
    horizon: int = HORIZON,
) -> pd.DataFrame:
    """Historical (mode-2) metric rows for an ALREADY-COMPUTED factor panel + forward
    return. No data loading -> testable without Qlib. Spans IS + OOS (non-formal).

    ``field_eligible`` (per-factor bool; catalog mode) caps ineligible factors at draft.
    ``kinds`` (per-factor str; derived mode) populates a ``kind`` column.
    ``compute_long_only`` adds the GROSS long-only top-bucket metric (derived mode).
    Returns an UNROUNDED DataFrame — CSV rounding happens in ``report.py``.
    """
    is_ts, oos_ts = pd.Timestamp(is_end), pd.Timestamp(oos_start)
    rows: list[dict] = []
    for name in factor_panel.columns:
        series = factor_panel[name]
        fld_ok = True if field_eligible is None else bool(field_eligible.get(name, False))
        ic = metrics.factor_ic(series, forward_return)
        row: dict = {"factor": name}
        if kinds is not None:
            row["kind"] = kinds.get(name, "")
        if field_eligible is not None:
            row["field_eligible"] = fld_ok

        if ic is None or len(ic) == 0:
            row.update({
                "full_rank_icir": np.nan, "is_rank_icir": np.nan, "oos_rank_icir": np.nan,
                "sign_consistency": np.nan, "n_years": 0,
                "status": "draft", "reason": "no IC (degenerate/all-NaN)",
            })
            if compute_long_only:
                row.update({"lo_excess_ann": np.nan, "lo_sharpe": np.nan, "lo_hit": np.nan})
            rows.append(row)
            continue

        full = metrics.rank_icir(ic)
        ic_is = ic[ic.index <= is_ts]
        ic_oos = ic[ic.index >= oos_ts]
        is_icir = metrics.rank_icir(ic_is) if len(ic_is) else np.nan
        oos_icir = metrics.rank_icir(ic_oos) if len(ic_oos) else np.nan
        sign_consistency = metrics.yearly_sign_consistency(ic, full)
        n_years = metrics.yearly_fold_count(ic)
        status, reason = assign_historical_status(fld_ok, is_icir, oos_icir, sign_consistency)
        row.update({
            "full_rank_icir": full, "is_rank_icir": is_icir, "oos_rank_icir": oos_icir,
            "sign_consistency": sign_consistency, "n_years": n_years,
            "status": status, "reason": reason,
        })
        if compute_long_only:
            row.update(metrics.long_only_topbucket(series, forward_return, np.sign(full), horizon=horizon))
        rows.append(row)
    return pd.DataFrame(rows)


def run_historical_catalog_revalidation(
    *,
    start: str = START, end: str = END, is_end: str = IS_END, oos_start: str = OOS_START,
    horizon: int = HORIZON, qlib_dir: str | Path | None = None,
    registry_path: str | Path | None = None,
    compute_factors_fn=None,
) -> pd.DataFrame:
    """Mode-2 port of ``revalidate_catalog_walkforward.main`` — the current base catalog
    (the current base catalog — live count via ``catalog_composition()``), field-eligibility-capped, full-window IS+OOS. Loads via the sanctioned
    ``operators.compute_factors`` path (injectable as ``compute_factors_fn`` for tests).
    Returns the UNROUNDED panel DataFrame (the thin script wrapper renders the CSV via
    ``report.write_catalog_csv``)."""
    from src.alpha_research.factor_library import operators
    from src.alpha_research.factor_library.catalog import get_factor_catalog
    from src.data_infra.field_registry import load_field_registry

    catalog = dict(get_factor_catalog(include_new_data=True))
    registry = load_field_registry(str(registry_path or _DEFAULT_FIELD_STATUS))
    cf = compute_factors_fn or operators.compute_factors
    factors_df, fwd_df = cf(
        catalog=catalog, start_date=start, end_date=end, horizons=[horizon],
        qlib_dir=str(qlib_dir or _DEFAULT_QLIB_DIR), kernels=1, stage="is_only",
    )
    fwd_col = f"fwd_ret_{horizon}d"
    fwd = fwd_df[fwd_col] if fwd_col in fwd_df.columns else fwd_df.iloc[:, 0]
    field_eligible = {name: _field_eligible(expr, registry) for name, expr in catalog.items()}
    return revalidate_panel(
        factors_df, fwd, is_end=is_end, oos_start=oos_start,
        field_eligible=field_eligible, horizon=horizon,
    )


def run_historical_derived_revalidation(
    *,
    start: str = START, end: str = END, is_end: str = IS_END, oos_start: str = OOS_START,
    horizon: int = HORIZON, qlib_dir: str | Path | None = None,
) -> pd.DataFrame:
    """Mode-2 port of ``revalidate_derived_factors.main`` — 20 composite + 4 industry-
    relative factors with the GROSS long-only metric. Loads base components, applies the
    Layer-2 post-processing (``add_composites`` / ``add_industry_relative_composites`` via
    PIT-safe ``build_industry_series_asof``), then ``revalidate_panel`` with long-only."""
    from src.alpha_research.factor_library import operators
    from src.alpha_research.factor_library.catalog import (
        get_composite_defs, get_factor_catalog, get_industry_relative_defs,
    )
    from src.data_infra.provider_metadata import build_industry_series_asof

    full_catalog = get_factor_catalog(include_new_data=True)
    comp_defs = get_composite_defs()
    ind_defs = get_industry_relative_defs()
    needed: set[str] = set()
    for c in comp_defs:
        needed.update(c["components"])
    for d in ind_defs:
        needed.add(d["base"])
    sub_catalog = {n: full_catalog[n] for n in needed if n in full_catalog}

    qdir = str(qlib_dir or _DEFAULT_QLIB_DIR)
    base_df, fwd_df = operators.compute_factors(
        catalog=sub_catalog, start_date=start, end_date=end, horizons=[horizon],
        qlib_dir=qdir, kernels=1, stage="is_only",
    )
    mcap_df, _ = operators.compute_factors(
        catalog={"market_cap": "Ref($total_mv, 1)"}, start_date=start, end_date=end,
        horizons=[horizon], qlib_dir=qdir, kernels=1, stage="is_only",
    )
    fwd_col = f"fwd_ret_{horizon}d"
    fwd = fwd_df[fwd_col] if fwd_col in fwd_df.columns else fwd_df.iloc[:, 0]

    comp_df = operators.add_composites(base_df.copy(), composite_defs=comp_defs)
    comp_names = [c["name"] for c in comp_defs]
    industry_series = build_industry_series_asof(base_df.index, "L1")
    ind_df = operators.add_industry_relative_composites(
        base_df.copy(), industry_series, market_cap=mcap_df["market_cap"], defs=ind_defs,
    )
    ind_names = [d["name"] for d in ind_defs]

    cols: dict[str, pd.Series] = {}
    kinds: dict[str, str] = {}
    for n in comp_names:
        if n in comp_df.columns:
            cols[n] = comp_df[n]
            kinds[n] = "composite"
    for n in ind_names:
        if n in ind_df.columns:
            cols[n] = ind_df[n]
            kinds[n] = "industry_rel"
    derived_panel = pd.DataFrame(cols)
    return revalidate_panel(
        derived_panel, fwd, is_end=is_end, oos_start=oos_start,
        kinds=kinds, compute_long_only=True, horizon=horizon,
    )
