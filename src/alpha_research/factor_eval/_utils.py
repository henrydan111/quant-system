"""
Internal utilities for factor_eval.

Provides index normalization so that all public functions accept
either MultiIndex(datetime, instrument) or MultiIndex(instrument, datetime)
— matching Qlib's native output format automatically.
"""

import pandas as pd


def _normalize_multiindex(data):
    """Ensure a Series or DataFrame has MultiIndex(datetime, instrument) order.

    Qlib's D.features() returns MultiIndex(instrument, datetime), but
    factor_eval's internal logic assumes level 0 = datetime, level 1 =
    instrument. This function detects the order and swaps if needed.

    Detection heuristic:
        - If level 0 has dtype datetime64 → already (datetime, instrument)
        - If level 1 has dtype datetime64 → swap levels
        - If names contain 'datetime'/'date' → use that as level 0
        - Fallback: check if level 0 values look like timestamps

    Args:
        data: pd.Series or pd.DataFrame with 2-level MultiIndex.

    Returns:
        Same type as input, with MultiIndex(datetime, instrument) order.
        If input has a single index or isn't a MultiIndex, returns as-is.
    """
    if not isinstance(data.index, pd.MultiIndex):
        return data

    if data.index.nlevels != 2:
        return data

    level_0 = data.index.get_level_values(0)
    level_1 = data.index.get_level_values(1)

    # Check by dtype
    l0_is_datetime = pd.api.types.is_datetime64_any_dtype(level_0)
    l1_is_datetime = pd.api.types.is_datetime64_any_dtype(level_1)

    if l0_is_datetime and not l1_is_datetime:
        return data  # Already (datetime, instrument)

    if l1_is_datetime and not l0_is_datetime:
        return data.swaplevel().sort_index()  # Swap to (datetime, instrument)

    # Check by level names
    names = [str(n).lower() if n is not None else "" for n in data.index.names]
    if any(kw in names[1] for kw in ("datetime", "date", "time")):
        if not any(kw in names[0] for kw in ("datetime", "date", "time")):
            return data.swaplevel().sort_index()

    if any(kw in names[0] for kw in ("datetime", "date", "time")):
        return data  # Level 0 is already datetime

    # Fallback: try to infer from values — if level 0 is string-like
    # instrument codes (e.g., "000001_SZ") and level 1 is timestamp
    try:
        if isinstance(level_0[0], str) and not isinstance(level_1[0], str):
            return data.swaplevel().sort_index()
    except (IndexError, TypeError):
        pass

    # Cannot determine — return as-is (assume correct)
    return data
