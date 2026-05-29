"""Live loader↔provider PARITY test (prevention plan v5 §6.5.5, step 6).

The architecture is "one PIT-semantics contract, two implementations, one
oracle": the production Qlib provider is the ORACLE, and the research loader's
kernel is an independent implementation. This test is the drift guard — it
asserts that ``load_pit_asof_panel(availability_lag_bars=0,
apply_provider_bounds=False)`` reproduces the provider's ``$field`` values
exactly, across a sample grid spanning before-first / between / on-effective /
after-restatement dates.

LIVE-LOCAL only: needs the gitignored Qlib provider under ``data/qlib_data``.
Skips when absent (so it never runs in offline/public CI). Uses ``D.features``
directly — permitted here because the bare-qlib lint scope is ``src/`` only, and
this is a privileged provider-vs-loader comparison.

Parity is compared with ``apply_provider_bounds=False`` so the loader's extra
delist/IPO masking does not enter the comparison — this isolates the ALIGNMENT
semantics (stateful q0 + as-of), which is what must match the provider.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.data_infra import pit_research_loader as L
from src.data_infra.pit_research_loader import load_pit_asof_panel

_PROVIDER = L._data_root() / "qlib_data"
_needs_provider = pytest.mark.skipif(
    not (_PROVIDER / "calendars" / "day.txt").exists(),
    reason="Qlib provider absent (live-local only)",
)

# Plain cumulative indicator ratios that (a) are field-registry-approved and
# (b) exist as provider bins, and do NOT need single-quarter derivation.
PARITY_FIELDS = ["roa", "roe", "netprofit_margin"]
PARITY_TS = ["600519.SH", "000001.SZ"]  # dotted (loader) <-> underscore (provider)
START, END = "20170101", "20191231"


def _ts_to_qlib(ts: str) -> str:
    return ts.replace(".", "_")


@_needs_provider
def test_loader_matches_provider_asof():
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D

    qlib.init(provider_uri=str(_PROVIDER), region=REG_CN, kernels=1)

    cal = L._trading_calendar()
    sim = [d.strftime("%Y%m%d") for d in cal if START <= d.strftime("%Y%m%d") <= END]

    # Loader: as-of (lag 0), no bounds mask, so only alignment semantics compare.
    loaded = load_pit_asof_panel(
        PARITY_FIELDS, sim, instruments=PARITY_TS,
        apply_provider_bounds=False, duplicate_policy="provider_stateful_q0",
    )

    qlib_codes = [_ts_to_qlib(t) for t in PARITY_TS]
    prov = D.features(  # noqa: bare-qlib-features (privileged parity check, tests/ out of lint scope)
        qlib_codes, [f"${f}" for f in PARITY_FIELDS],
        start_time="2017-01-01", end_time="2019-12-31", freq="day",
    )
    prov.columns = PARITY_FIELDS

    compared = 0
    for field in PARITY_FIELDS:
        wide = loaded[field]  # index=compact str, columns=dotted ts
        for ts in PARITY_TS:
            qts = _ts_to_qlib(ts)
            try:
                prov_series = prov.loc[qts, field]
            except KeyError:
                continue
            # provider datetime index -> compact str
            prov_compact = pd.Series(
                prov_series.to_numpy(),
                index=[d.strftime("%Y%m%d") for d in pd.DatetimeIndex(prov_series.index)],
            )
            common = wide.index.intersection(prov_compact.index)
            assert len(common) > 100, f"too few overlapping dates for {field}/{ts}"
            lhs = wide.loc[common, ts].to_numpy(dtype="float64")
            rhs = prov_compact.loc[common].to_numpy(dtype="float64")
            # provider stores float32; allow float32-scale tolerance.
            ok = np.isclose(lhs, rhs, rtol=1e-4, atol=1e-3, equal_nan=True)
            mism = int((~ok).sum())
            assert mism == 0, (
                f"PARITY MISMATCH {field}/{ts}: {mism}/{len(common)} cells differ "
                f"(first bad date {common[~ok][0] if mism else None}; "
                f"loader={lhs[~ok][:3] if mism else None} provider={rhs[~ok][:3] if mism else None})"
            )
            compared += 1

    assert compared >= 2, "parity test compared too few (field, ts) series"
