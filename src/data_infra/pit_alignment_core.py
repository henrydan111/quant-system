"""PIT-semantics alignment kernel — the single sanctioned alignment logic for
research-side fundamental data.

Part of the PIT-lookahead prevention plan (Knowledge/temp_plan/
``pit_lookahead_prevention_plan_2026-05-29_v5_FINAL.md``). Architecture:
**one PIT-semantics contract, two implementations, one oracle.**

- The production Qlib provider builder
  (:func:`src.data_infra.pit_backend.materialize_visibility_segments`) is the
  **ORACLE**. It is correct, heavily tested, and is NOT modified by this plan.
- This module is an *independent* implementation that the sandbox research
  loader (:mod:`src.data_infra.pit_research_loader`) uses, so fast research does
  not have to spin up the full Qlib provider — but it must NOT drift from the
  oracle. Drift is caught by the live loader↔provider parity test.

Why this exists at all: a family of hand-rolled ``sandbox_v*`` loaders aligned
fundamentals to trading dates by *lexically* comparing dashed ``effective_date``
strings against compact ``trade_date`` strings, which injected up to ~9 months
of earnings lookahead (188.7%→2.0% OOS on the affected champion). This kernel
removes the reason to hand-roll: it does datetime-correct, **stateful** q0
alignment with an explicit availability lag and a fail-closed duplicate policy.

Stateful q0 (the load-bearing semantic — mirrors the oracle):
    The provider keeps a ``state`` keyed by ``end_date`` and, at each
    ``effective_date``, exposes q0 = the row with the **maximum visible
    ``end_date``**. A later *restatement* of an OLDER fiscal period updates that
    older period's value but does **not** demote q0 while a newer period is
    already visible. q0 is selected by ``end_date`` visibility FIRST; the field
    value is then read as-is (NaN included) — never ``dropna`` before selecting
    q0.

Availability lag:
    ``availability_lag_bars=0`` → a value is usable ON its ``effective_date``
    (matches the provider's as-of semantics; used by the parity test).
    ``availability_lag_bars=1`` → usable from the next trading bar (the
    research-signal default, matching the repo's ``Ref($field, 1)`` /
    "no same-day raw fundamental" contract).
"""
from __future__ import annotations

from typing import Iterable, Mapping

import numpy as np
import pandas as pd

# Default duplicate policy is fail-closed. ``provider_stateful_q0`` opts into the
# (normal, expected) Case-A multi-fiscal-period collapse; it still fails closed
# on a Case-C same-period conflict (resolving those needs the dataset-specific
# provider canonicalization, which is intentionally NOT implemented here yet).
DUPLICATE_POLICIES = ("error", "provider_stateful_q0")


class PitAlignmentError(RuntimeError):
    """Generic kernel misuse (bad inputs, unknown policy)."""


class DuplicateConflictError(PitAlignmentError):
    """A true same-(ts_code, effective_date, end_date) value conflict (Case C).

    Resolving these correctly requires the provider's dataset-specific
    canonicalization chain (``report_type`` priority → ``update_flag`` →
    disclosure/f_ann/ann date → non-null payload count → deterministic
    tail/row-hash), which is NOT yet ported. Fail closed.
    """


def _as_datetime(series: pd.Series) -> pd.Series:
    """Coerce a date-like column to tz-naive datetime64. Mirrors the spirit of
    ``pit_backend.normalize_date_series`` (compact ``%Y%m%d`` first, then general).
    """
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")
    text = series.astype(str)
    parsed = pd.to_datetime(text, format="%Y%m%d", errors="coerce")
    bad = parsed.isna() & text.notna() & ~text.isin({"", "NaT", "nan", "None", "<NA>"})
    if bad.any():
        parsed.loc[bad] = pd.to_datetime(text.loc[bad], errors="coerce")
    return parsed


def _check_case_c(frame: pd.DataFrame, field: str) -> None:
    """Raise on a true same-period conflict (Case C). Restatements across
    DIFFERENT effective_dates are NOT conflicts. A conflict is any group sharing
    the exact ``(ts_code, effective_date, end_date)`` that either:

    * carries >1 distinct non-null value, OR
    * mixes null and non-null values (``[10.0, NaN]``).

    The mixed null/non-null case MUST fail closed: the downstream stateful walk
    uses last-write-wins within a group, so a ``[10.0, NaN]`` group resolves to
    10.0 or NaN depending on row order — exactly the silent, order-dependent
    collapse this kernel exists to prevent. Resolving it correctly needs the
    provider's dataset-specific canonicalization (not implemented here). Only
    fully-identical duplicates (all the same value, or all NaN) are safe to
    de-duplicate. Found via GPT 5.5 Pro PR #18 review.
    """
    sub = frame[["ts_code", "effective_date", "end_date", field]]
    grp = sub.groupby(["ts_code", "effective_date", "end_date"], sort=False)[field]
    total = grp.size()
    nonnull = grp.count()
    ndistinct = grp.nunique()  # distinct non-null (dropna=True)
    mixed = (nonnull > 0) & (nonnull < total)        # some null AND some non-null
    conflict = (ndistinct > 1) | mixed
    bad = conflict[conflict]
    if not bad.empty:
        ts, eff, end = bad.index[0]
        raise DuplicateConflictError(
            f"Case-C same-period conflict for field {field!r}: "
            f"{int(bad.sum())} (ts_code, effective_date, end_date) group(s) carry "
            f"conflicting (differing non-null, or mixed null/non-null) values "
            f"(first: ts_code={ts}, effective_date={eff!r}, end_date={end!r}). "
            f"Resolving these needs the provider's dataset-specific canonicalization "
            f"(not implemented in the kernel). Fail closed."
        )


def _stateful_q0_points(
    eff: np.ndarray, end: np.ndarray, val: np.ndarray
) -> tuple[list[pd.Timestamp], list[float]]:
    """Walk one symbol's (effective_date, end_date, value) rows in
    (effective_date, end_date) order and return the q0 step series.

    Returns ``(unique_effective_dates, q0_value_at_each)`` where the q0 value at
    an effective_date is the value of the MAX ``end_date`` currently in state
    (NaN allowed). Replicates the oracle's ``current_slots()[0]``.
    """
    state: dict[pd.Timestamp, float] = {}
    eff_points: list[pd.Timestamp] = []
    q0_points: list[float] = []
    n = len(eff)
    i = 0
    while i < n:
        e = eff[i]
        # consume all rows sharing this effective_date (rows are pre-sorted)
        while i < n and eff[i] == e:
            state[end[i]] = val[i]  # last write wins within the group (Case C already guarded)
            i += 1
        max_end = max(state)  # latest visible fiscal period = q0
        eff_points.append(e)
        q0_points.append(state[max_end])
    return eff_points, q0_points


def align_ledger_to_calendar(
    ledger_df: pd.DataFrame,
    fields: Iterable[str],
    calendar: pd.DatetimeIndex,
    *,
    availability_lag_bars: int = 0,
    duplicate_policy: str = "error",
) -> dict[str, pd.DataFrame]:
    """Align ledger fundamentals onto a trading calendar with stateful q0.

    Args:
        ledger_df: long PIT-ledger frame with ``ts_code``, ``effective_date``,
            ``end_date`` and the requested ``fields`` columns.
        fields: payload columns to align (each returned as its provider q0 alias).
        calendar: sorted, unique tz-naive trading-day ``DatetimeIndex``.
        availability_lag_bars: 0 = usable on effective_date (provider as-of /
            parity); 1 = usable next trading bar (research-signal default).
        duplicate_policy: ``"error"`` (default, fail-closed: refuses any
            multi-fiscal-period ``(ts_code, effective_date)`` so the caller must
            opt in) or ``"provider_stateful_q0"`` (does the Case-A stateful q0;
            still raises on a Case-C same-period conflict).

    Returns:
        ``{field: DataFrame(index=calendar, columns=sorted ts_code)}`` of q0
        values with the availability lag applied.
    """
    fields = list(fields)
    if duplicate_policy not in DUPLICATE_POLICIES:
        raise PitAlignmentError(
            f"unknown duplicate_policy {duplicate_policy!r}; expected one of {DUPLICATE_POLICIES}"
        )
    if availability_lag_bars < 0:
        raise PitAlignmentError("availability_lag_bars must be >= 0")
    if not isinstance(calendar, pd.DatetimeIndex):
        raise PitAlignmentError("calendar must be a pandas DatetimeIndex")
    if not calendar.is_monotonic_increasing or calendar.has_duplicates:
        raise PitAlignmentError("calendar must be sorted ascending and unique")

    required = {"ts_code", "effective_date", "end_date"}
    missing = required - set(ledger_df.columns)
    if missing:
        raise PitAlignmentError(f"ledger_df missing required columns: {sorted(missing)}")
    missing_fields = [f for f in fields if f not in ledger_df.columns]
    if missing_fields:
        raise PitAlignmentError(f"ledger_df missing requested field column(s): {missing_fields}")

    work = ledger_df[["ts_code", "effective_date", "end_date", *fields]].copy()
    work["effective_date"] = _as_datetime(work["effective_date"])
    work["end_date"] = _as_datetime(work["end_date"])
    work = work.dropna(subset=["effective_date", "end_date"])
    work = work.sort_values(["ts_code", "effective_date", "end_date"], kind="mergesort")

    ts_codes = sorted(work["ts_code"].astype(str).unique().tolist())
    out: dict[str, pd.DataFrame] = {}

    for field in fields:
        _check_case_c(work, field)
        if duplicate_policy == "error":
            multi = (
                work.groupby(["ts_code", "effective_date"])["end_date"].nunique() > 1
            )
            if multi.any():
                raise PitAlignmentError(
                    f"duplicate_policy='error' refuses multi-fiscal-period collapse for "
                    f"field {field!r}: {int(multi.sum())} (ts_code, effective_date) group(s) "
                    f"expose >1 end_date (Case A). Pass duplicate_policy='provider_stateful_q0' "
                    f"to opt into provider-equivalent stateful q0 selection."
                )

        wide = pd.DataFrame(index=calendar, columns=ts_codes, dtype="float64")
        fwork = work[["ts_code", "effective_date", "end_date", field]]
        for ts_code, grp in fwork.groupby("ts_code", sort=False):
            eff = grp["effective_date"].to_numpy()
            end = grp["end_date"].to_numpy()
            val = grp[field].to_numpy(dtype="float64")
            eff_points, q0_points = _stateful_q0_points(eff, end, val)
            if not eff_points:
                continue
            q0 = pd.Series(q0_points, index=pd.DatetimeIndex(eff_points))
            q0 = q0[~q0.index.duplicated(keep="last")].sort_index()
            # asof MERGE onto the calendar: each calendar date takes the value of
            # the latest effective_date <= T, NaN INCLUDED. A plain value-ffill
            # would wrongly overwrite an explicit NaN-at-q0 (a reported period
            # whose field is null) with the prior period's value — the exact
            # "missing-field q0" trap. merge_asof carries the active row's value
            # verbatim, and yields NaN before the first effective_date.
            qdf = pd.DataFrame({"eff": q0.index, "v": q0.to_numpy()})
            caldf = pd.DataFrame({"t": calendar})
            merged = pd.merge_asof(caldf, qdf, left_on="t", right_on="eff", direction="backward")
            aligned = pd.Series(merged["v"].to_numpy(), index=calendar)
            if availability_lag_bars:
                aligned = aligned.shift(availability_lag_bars)
            wide[str(ts_code)] = aligned.to_numpy()
        out[field] = wide

    return out
