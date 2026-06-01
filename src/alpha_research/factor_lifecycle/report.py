"""CSV rendering for historical-mode revalidation (Phase 4).

Renders the UNROUNDED ``revalidate_panel`` DataFrame into the EXACT columns + rounding of
the legacy ``catalog_revalidation/*.csv`` files so Phase 2's ``import_revalidation`` keeps
consuming them unchanged. Only the historical (mode-2) result is written to CSV; the
formal IS-only result is an in-memory object, never a status CSV.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

CATALOG_COLUMNS = [
    "factor", "field_eligible", "full_rank_icir", "is_rank_icir", "oos_rank_icir",
    "sign_consistency", "n_years", "status", "reason",
]
DERIVED_COLUMNS = [
    "factor", "kind", "full_rank_icir", "is_rank_icir", "oos_rank_icir",
    "sign_consistency", "status", "reason", "lo_excess_ann", "lo_sharpe", "lo_hit",
]

# Per-column rounding, matching the legacy scripts (4 dp for ICIR/excess; 3 dp for the
# consistency / sharpe / hit fractions). NaN -> None (the scripts write empty cells).
_ROUND4 = ("full_rank_icir", "is_rank_icir", "oos_rank_icir", "lo_excess_ann")
_ROUND3 = ("sign_consistency", "lo_sharpe", "lo_hit")


def _round_or_none(value, places: int):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return round(float(value), places)


def _apply_rounding(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in _ROUND4:
        if col in out.columns:
            out[col] = out[col].map(lambda v: _round_or_none(v, 4))
    for col in _ROUND3:
        if col in out.columns:
            out[col] = out[col].map(lambda v: _round_or_none(v, 3))
    return out


def to_catalog_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Catalog CSV frame: rounded, column-ordered, sorted by status asc then |OOS ICIR|
    desc (NaN last) — matches ``revalidate_catalog_walkforward`` output."""
    out = _apply_rounding(df)
    if "oos_rank_icir" in out.columns:
        oabs = pd.to_numeric(out["oos_rank_icir"], errors="coerce").abs()
        out = out.assign(_oabs=oabs).sort_values(
            ["status", "_oabs"], ascending=[True, False], na_position="last",
        ).drop(columns="_oabs")
    return out[[c for c in CATALOG_COLUMNS if c in out.columns]].reset_index(drop=True)


def to_derived_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Derived CSV frame: rounded + column-ordered (legacy script preserves build order)."""
    out = _apply_rounding(df)
    return out[[c for c in DERIVED_COLUMNS if c in out.columns]].reset_index(drop=True)


def write_catalog_csv(df: pd.DataFrame, path: str | Path) -> Path:
    path = Path(path)
    to_catalog_frame(df).to_csv(path, index=False)
    return path


def write_derived_csv(df: pd.DataFrame, path: str | Path) -> Path:
    path = Path(path)
    to_derived_frame(df).to_csv(path, index=False)
    return path
