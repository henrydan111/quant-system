"""Sanctioned sandbox front door for PIT fundamentals (the lightweight adapter).

Part of the PIT-lookahead prevention plan (v5 FINAL §6.2). This is the ONLY
approved way for research/sandbox code to align ``data/pit_ledger/*`` onto a
trading-date axis. It is a thin adapter over :mod:`src.data_infra.pit_alignment_core`
(the shared semantics kernel); the production Qlib provider remains the oracle,
and the kernel is bound to it by a differential parity test.

Two layers (do NOT collapse them — see the repo's "no same-day raw fundamental"
contract):

* :func:`load_pit_asof_panel` — ``availability_lag_bars=0``: a value is usable
  ON its ``effective_date``. This matches the provider's as-of semantics and is
  what the parity test compares. Use for data inspection / parity, NOT signal
  ranking.
* :func:`load_pit_signal_panel` — ``signal_lag_bars=1`` by default: a value is
  usable from the NEXT trading bar. This is the research-signal default (mirrors
  ``Ref($field, 1)``). ``lag=0`` is never the silent default for signals.

Both default to ``apply_provider_bounds=True`` (delist + IPO-lag masking via the
same contract as ``provider_metadata.stock_basic_bounds``) because direct PIT-
ledger consumers bypass the instruments-sidecar guard and must apply it
themselves. Both return provider-compatible **q0 aliases** only (slot-depth
fields like ``roa_q1`` are out of scope for v1).

Duplicate policy (deliberate, documented per GPT 5.5 Pro review — "Option B"):
the **kernel** default is fail-closed ``"error"``, but the **public loader**
defaults to ``"provider_stateful_q0"`` because multi-fiscal-period visibility
(Case A) is the normal, provider-equivalent path for fundamentals — erroring by
default would make the loader unusable. A true same-period conflict (Case C)
still fails closed under both. "Fail-closed default" therefore means: kernel =
error; loader = provider_stateful_q0 (Case A) + hard-fail on Case C.

Field governance is fail-closed: a requested field must POSITIVELY resolve in
the field registry (unknown or quarantined fields are refused even at
``sandbox_screening``). The indicator columns ``roe_waa, q_roe, q_dt_roe,
roe_dt, dt_netprofit_yoy`` — consumed by the now-invalidated v33/val_heavy
champions, and exposed as unregistered when this fail-closed gate landed — were
registered 2026-05-29 via the governed indicators approval
(``approvals/2026-05-29_indicators_loader_qfields.yaml``) after live parity
verification. Any OTHER indicator column remains fail-closed until likewise
registered.
"""
from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
import yaml

from src.data_infra import provider_metadata as pm
from src.data_infra.field_registry import FieldApprovalError, load_field_registry
from src.data_infra.pit_alignment_core import align_ledger_to_calendar

DEFAULT_STAGE = "sandbox_screening"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class PitResearchLoaderError(RuntimeError):
    """Loader misuse (bad sim_dates, unknown ledger, etc.)."""


@functools.lru_cache(maxsize=1)
def _config() -> dict:
    with open(_PROJECT_ROOT / "config.yaml", "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _data_root() -> Path:
    raw = (((_config().get("storage") or {}).get("data_root")) or "./data")
    root = Path(raw)
    return root if root.is_absolute() else (_PROJECT_ROOT / root).resolve()


def _ledger_path(ledger: str) -> Path:
    return _data_root() / "pit_ledger" / ledger / f"{ledger}.parquet"


@functools.lru_cache(maxsize=1)
def _trading_calendar() -> pd.DatetimeIndex:
    cal = pd.read_parquet(_data_root() / "reference" / "trade_cal.parquet",
                          columns=["cal_date", "is_open"])
    cal = cal[cal["is_open"] == 1]
    idx = pd.to_datetime(cal["cal_date"].astype(str), format="%Y%m%d")
    return pd.DatetimeIndex(sorted(idx.unique()))


@functools.lru_cache(maxsize=1)
def _bounds_map() -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    """Vectorized ``ts_code -> (effective_list_date, delist_date)``.

    Mirrors ``provider_metadata.stock_basic_bounds`` (effective_list =
    list_date + IPO_LAG_DAYS; delist_date) but precomputed for the whole table
    so masking is vectorized, not a per-cell call. Equivalence to the canonical
    helper is regression-tested.
    """
    sb = pd.read_parquet(_data_root() / "reference" / "stock_basic.parquet")
    out: dict[str, tuple[pd.Timestamp, pd.Timestamp]] = {}
    list_dt = pd.to_datetime(sb.get("list_date"), errors="coerce")
    eff = list_dt + pd.Timedelta(days=pm.IPO_LAG_DAYS)
    delist = pd.to_datetime(sb.get("delist_date"), errors="coerce") if "delist_date" in sb.columns else pd.Series(pd.NaT, index=sb.index)
    codes = sb["ts_code"].astype(str).str.upper()
    for c, lo, hi in zip(codes, eff, delist):
        out[c] = (lo, hi)
    return out


def _validate_sim_dates(sim_dates: Sequence[str], calendar: pd.DatetimeIndex) -> pd.DatetimeIndex:
    arr = list(sim_dates)
    if not arr:
        raise PitResearchLoaderError("sim_dates is empty")
    if any(not (isinstance(d, str) and len(d) == 8 and d.isdigit()) for d in arr):
        raise PitResearchLoaderError("sim_dates must be compact 'YYYYMMDD' strings")
    if len(set(arr)) != len(arr):
        raise PitResearchLoaderError("sim_dates must be unique")
    if list(arr) != sorted(arr):
        raise PitResearchLoaderError("sim_dates must be sorted ascending")
    idx = pd.to_datetime(pd.Index(arr), format="%Y%m%d")
    missing = idx.difference(calendar)
    if len(missing):
        sample = [d.strftime("%Y%m%d") for d in missing[:5]]
        raise PitResearchLoaderError(
            f"sim_dates contains {len(missing)} non-trading day(s) (not in trade_cal): {sample}"
        )
    return idx


def _normalize_field(f: str) -> str:
    """Return the bare ledger column name, stripping a single leading ``$`` so
    ``"roa"`` and ``"$roa"`` are the SAME identity (no ``"$$roa"`` bug)."""
    s = str(f)
    s = s[1:] if s.startswith("$") else s
    if not s or s.startswith("$"):
        raise PitResearchLoaderError(f"invalid field name {f!r}")
    return s


def _validate_fields(fields: list[str], stage: str) -> None:
    """Fail-closed field governance for the sanctioned loader.

    Unlike the general factor-expression path (whose ``unknown_field_policy``
    only *warns* in sandbox), the sanctioned raw PIT loader requires a POSITIVE
    registry match: a field that is unknown OR not allowed at ``stage`` is
    refused — even in ``sandbox_screening``. ``fields`` are bare names already
    normalized by :func:`_normalize_field`; we resolve the ``$``-prefixed token
    so a bare name cannot bypass governance by dropping the ``$``.
    """
    reg = load_field_registry()
    disallowed: list[str] = []
    for f in fields:
        token = f"${f}"
        res = reg.resolve_field(token, stage)
        if res.is_unknown or not res.allowed:
            disallowed.append(f"{token} ({res.reason})")
    if disallowed:
        raise FieldApprovalError(
            f"field(s) not PIT-approved at stage={stage!r} — the sanctioned loader "
            f"requires a positive field-registry match (unknown/quarantined fields are "
            f"refused, even in sandbox): {disallowed}"
        )


def _apply_bounds(wide: pd.DataFrame, bounds: dict[str, tuple]) -> pd.DataFrame:
    """NaN-out cells where date < effective_list_date or date > delist_date.
    NaT bounds (unknown list/still-listed) → no mask (numpy NaT comparisons are False)."""
    cols = list(wide.columns)
    # pd.to_datetime normalizes Timestamp / NaT / float-nan uniformly to NaT.
    lo = pd.to_datetime(pd.Series([bounds.get(str(c), (pd.NaT, pd.NaT))[0] for c in cols])).to_numpy()
    hi = pd.to_datetime(pd.Series([bounds.get(str(c), (pd.NaT, pd.NaT))[1] for c in cols])).to_numpy()
    dates = wide.index.values.astype("datetime64[ns]")[:, None]
    values = wide.to_numpy(dtype="float64", copy=True)
    mask = (dates < lo[None, :]) | (dates > hi[None, :])
    values[mask] = np.nan
    return pd.DataFrame(values, index=wide.index, columns=wide.columns)


def _load(
    fields: Iterable[str],
    sim_dates: Sequence[str],
    *,
    ledger: str,
    lag: int,
    apply_provider_bounds: bool,
    duplicate_policy: str,
    stage: str,
    instruments: Sequence[str] | None,
) -> dict[str, pd.DataFrame]:
    fields = [_normalize_field(f) for f in fields]
    if not fields:
        raise PitResearchLoaderError("fields is empty")
    calendar = _trading_calendar()
    sim_idx = _validate_sim_dates(sim_dates, calendar)
    _validate_fields(fields, stage)

    path = _ledger_path(ledger)
    if not path.exists():
        raise PitResearchLoaderError(f"unknown/absent ledger {ledger!r}: {path}")
    led = pd.read_parquet(path, columns=["ts_code", "effective_date", "end_date", *fields])
    if instruments is not None:
        keep = {str(s).upper() for s in instruments}
        led = led[led["ts_code"].astype(str).str.upper().isin(keep)]

    # Align over the full trading calendar up to the sim window end, so asof and
    # the trading-bar lag are correct, THEN slice to the requested sim_dates.
    full_cal = calendar[calendar <= sim_idx.max()]
    aligned = align_ledger_to_calendar(
        led, fields, full_cal, availability_lag_bars=lag, duplicate_policy=duplicate_policy
    )

    bounds = _bounds_map() if apply_provider_bounds else None
    out: dict[str, pd.DataFrame] = {}
    for field, wide in aligned.items():
        sliced = wide.loc[sim_idx]
        if bounds is not None:
            sliced = _apply_bounds(sliced, bounds)
        sliced.index = pd.Index([d.strftime("%Y%m%d") for d in sliced.index], name="trade_date")
        out[field] = sliced
    return out


def load_pit_asof_panel(
    fields: Iterable[str],
    sim_dates: Sequence[str],
    *,
    ledger: str = "indicators",
    apply_provider_bounds: bool = True,
    duplicate_policy: str = "provider_stateful_q0",
    stage: str = DEFAULT_STAGE,
    instruments: Sequence[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Data-as-of panel (``availability_lag_bars=0``). Matches provider as-of
    semantics; use for parity / inspection, NOT signal ranking. Returns
    ``{field: DataFrame(index=compact sim_dates, columns=ts_code)}`` of q0 aliases."""
    return _load(
        fields, sim_dates, ledger=ledger, lag=0,
        apply_provider_bounds=apply_provider_bounds, duplicate_policy=duplicate_policy,
        stage=stage, instruments=instruments,
    )


def load_pit_signal_panel(
    fields: Iterable[str],
    sim_dates: Sequence[str],
    *,
    ledger: str = "indicators",
    signal_lag_bars: int = 1,
    apply_provider_bounds: bool = True,
    duplicate_policy: str = "provider_stateful_q0",
    stage: str = DEFAULT_STAGE,
    instruments: Sequence[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Research-signal panel. ``signal_lag_bars`` defaults to **1** (no same-day
    raw fundamental use; mirrors ``Ref($field, 1)``). lag=0 must be chosen
    explicitly via :func:`load_pit_asof_panel`. Returns ``{field:
    DataFrame(index=compact sim_dates, columns=ts_code)}`` of q0 aliases."""
    if signal_lag_bars < 1:
        raise PitResearchLoaderError(
            "load_pit_signal_panel requires signal_lag_bars >= 1 (same-day raw "
            "fundamental use is not approved). Use load_pit_asof_panel for lag=0."
        )
    return _load(
        fields, sim_dates, ledger=ledger, lag=signal_lag_bars,
        apply_provider_bounds=apply_provider_bounds, duplicate_policy=duplicate_policy,
        stage=stage, instruments=instruments,
    )
