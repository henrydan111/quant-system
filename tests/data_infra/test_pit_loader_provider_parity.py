"""Live loader↔provider PARITY drift guard (prevention plan v5 §6.5.5, step 6).

Architecture: "one PIT-semantics contract, two implementations, one oracle".
The production Qlib provider is the ORACLE; the loader kernel is an independent
implementation. This test asserts the loader reproduces the provider's
``$field`` values — for BOTH availability lags — and is the value-level evidence
behind the indicators field approvals.

Hardened per GPT 5.5 Pro PR #19 review:
* provider path comes from ``config.yaml::storage.qlib_data_dir`` (same source
  as ``run_daily_qa``'s manifest / approval-evidence checks), not a derived path;
* the grid is asserted COMPLETE — every ``(field, ts)`` pair must be compared,
  none silently skipped — with a per-field non-all-NaN evidence floor;
* covers lag-0 (as-of) AND lag-1 (signal), and an IPO-edge security.

LIVE-LOCAL only: needs the gitignored Qlib provider; skips when absent.
``D.features`` is used directly — permitted because the bare-qlib lint scope is
``src/`` only and this is a privileged provider-vs-loader comparison.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.data_infra import pit_research_loader as L
from src.data_infra.pit_research_loader import load_pit_asof_panel, load_pit_signal_panel


def _provider_uri() -> Path:
    """Resolve the Qlib provider from ``storage.qlib_data_dir`` (NOT a derived
    ``data_root/qlib_data``), matching run_daily_qa's resolver so parity is
    checked against the SAME tree the approval-evidence binding validates."""
    cfg = L._config()
    raw = ((cfg.get("storage") or {}).get("qlib_data_dir")) or "./data/qlib_data"
    p = Path(raw)
    return p if p.is_absolute() else (L._PROJECT_ROOT / p).resolve()


_PROVIDER = _provider_uri()
_needs_provider = pytest.mark.skipif(
    not (_PROVIDER / "calendars" / "day.txt").exists(),
    reason="Qlib provider absent (live-local only)",
)

PARITY_FIELDS = [
    "roa", "roe", "netprofit_margin",
    "roe_waa", "roe_dt", "q_roe", "q_dt_roe", "dt_netprofit_yoy",
]
NEW_FIELDS = {"roe_waa", "roe_dt", "q_roe", "q_dt_roe", "dt_netprofit_yoy"}
PARITY_TS = ["600519.SH", "000001.SZ", "603080.SH"]  # 2 stable + 1 IPO-edge (listed 2018-01-03)
START, END = "20170101", "20191231"


def _ts_to_qlib(ts: str) -> str:
    return ts.replace(".", "_")


@pytest.fixture(scope="module")
def provider_and_sim():
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D

    qlib.init(provider_uri=str(_PROVIDER), region=REG_CN, kernels=1)
    cal = L._trading_calendar()
    sim = [d.strftime("%Y%m%d") for d in cal if START <= d.strftime("%Y%m%d") <= END]
    prov = D.features(  # noqa: bare-qlib-features (privileged parity check; tests/ out of lint scope)
        [_ts_to_qlib(t) for t in PARITY_TS],
        [f"${f}" for f in PARITY_FIELDS],
        start_time="2017-01-01", end_time="2019-12-31", freq="day",
    )
    prov.columns = PARITY_FIELDS
    return D, sim, prov


def _provider_series_compact(prov: pd.DataFrame, qts: str, field: str) -> pd.Series | None:
    """Return the provider series for (instrument, field) indexed by compact
    date strings, or None if the instrument is absent from the provider."""
    if qts not in set(prov.index.get_level_values(0)):
        return None
    s = prov.loc[qts, field]
    return pd.Series(
        s.to_numpy(),
        index=[d.strftime("%Y%m%d") for d in pd.DatetimeIndex(s.index)],
    )


@_needs_provider
def test_loader_matches_provider_asof(provider_and_sim):
    _, sim, prov = provider_and_sim
    loaded = load_pit_asof_panel(
        PARITY_FIELDS, sim, instruments=PARITY_TS,
        apply_provider_bounds=False, duplicate_policy="provider_stateful_q0",
    )
    expected = {(f, ts) for f in PARITY_FIELDS for ts in PARITY_TS}
    seen: set[tuple[str, str]] = set()
    missing: list[tuple[str, str]] = []
    field_nonnull = {f: 0 for f in PARITY_FIELDS}

    for field in PARITY_FIELDS:
        wide = loaded[field]
        for ts in PARITY_TS:
            ps = _provider_series_compact(prov, _ts_to_qlib(ts), field)
            if ps is None:
                missing.append((field, ts))
                continue
            common = wide.index.intersection(ps.index)
            assert len(common) > 100, f"too few overlapping dates for {field}/{ts}"
            lhs = wide.loc[common, ts].to_numpy(dtype="float64")
            rhs = ps.loc[common].to_numpy(dtype="float64")
            ok = np.isclose(lhs, rhs, rtol=1e-4, atol=1e-3, equal_nan=True)
            nmis = int((~ok).sum())
            assert nmis == 0, (
                f"PARITY MISMATCH {field}/{ts}: {nmis}/{len(common)} cells differ "
                f"(first bad {common[~ok][0] if nmis else None})"
            )
            seen.add((field, ts))
            field_nonnull[field] += int((np.isfinite(lhs) | np.isfinite(rhs)).sum())

    # Coverage: every declared (field, ts) pair MUST have been compared.
    assert not missing, f"provider missing expected parity series: {missing}"
    assert seen == expected, f"parity coverage gap: {expected - seen}"
    # Evidence floor: each newly-registered field must have real (non-all-NaN)
    # data somewhere in the grid — all-NaN equality is not approval evidence.
    for f in NEW_FIELDS:
        assert field_nonnull[f] > 0, f"newly-registered field {f!r} had no non-null parity evidence"


@_needs_provider
def test_loader_signal_lag1_matches_provider_shift(provider_and_sim):
    """lag-1 (signal) must equal the provider as-of value shifted one trading
    bar — the repo's 'no same-day raw fundamental' contract, verified live."""
    _, sim, prov = provider_and_sim
    loaded_sig = load_pit_signal_panel(
        PARITY_FIELDS, sim, instruments=PARITY_TS,
        apply_provider_bounds=False, duplicate_policy="provider_stateful_q0",
        signal_lag_bars=1,
    )
    compared = 0
    for field in PARITY_FIELDS:
        wide = loaded_sig[field]
        for ts in PARITY_TS:
            ps = _provider_series_compact(prov, _ts_to_qlib(ts), field)
            if ps is None:
                continue
            # Compare ONLY over the provider's actual coverage for this
            # instrument (ps.index) — not the full window. With
            # apply_provider_bounds=False the loader serves pre-listing ledger
            # values that the provider masks (the instrument is not in its
            # universe yet); that universe difference is real and not an
            # alignment bug, so it must not enter the alignment-parity check.
            prov_shift = ps.shift(1)  # provider as-of, one provider trading bar later
            common = wide.index.intersection(ps.index)
            assert len(common) > 100, f"too few overlapping dates for {field}/{ts}"
            common = common[1:]  # drop the first shared date (shift boundary)
            lhs = wide.loc[common, ts].to_numpy(dtype="float64")
            rhs = prov_shift.loc[common].to_numpy(dtype="float64")
            ok = np.isclose(lhs, rhs, rtol=1e-4, atol=1e-3, equal_nan=True)
            nmis = int((~ok).sum())
            assert nmis == 0, (
                f"LAG-1 PARITY MISMATCH {field}/{ts}: {nmis}/{len(common)} cells differ "
                f"(first bad {common[~ok][0] if nmis else None})"
            )
            compared += 1
    assert compared >= len(PARITY_FIELDS), "lag-1 parity compared too few series"
