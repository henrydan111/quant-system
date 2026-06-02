# ──────────────────────────────────────────────────────────────────────
# PR 7 of 2026-05-26 freeze plan — SCRIPT_STATUS header block.
# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: joinquant_attribution_only
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   Independent-recompute parity for the Wave-1 statement-field promotion
#   (income/balancesheet/cashflow _sq_q*/_q* derived variants). The provider
#   DERIVES these variants (quarter-canonical serving) — they are NOT stored
#   ledger columns, so the loader↔provider parity harness used for the
#   indicators approval cannot validate them. This script recomputes the
#   provider's derivation FROM SCRATCH in pandas, directly off the PIT ledger
#   (data/pit_ledger/<family>/<family>.parquet), WITHOUT importing the
#   provider's own derivation functions (no circularity), then compares to the
#   provider's D.features output cell-by-cell. This is the fail-closed evidence
#   behind the income/balancesheet/cashflow approval. Read-only.
#
#   Semantics reproduced (from pit_backend.py, re-implemented independently):
#     * snapshot _q{slot}: the period-end value of the slot-th most-recently-
#       disclosed fiscal period, as-of each calendar date (visible state).
#     * flow _sq_q{slot}: current-cumulative − prior-fiscal-quarter-cumulative
#       using the cumulative state VISIBLE at each date; Q1 (month==3) single-
#       quarter == cumulative; irregular period-ends → NaN.
# ──────────────────────────────────────────────────────────────────────
"""Independent statement-field provider parity. LIVE-LOCAL (needs the provider)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LEDGER = ROOT / "data" / "pit_ledger"
QLIB = ROOT / "data" / "qlib_data"
TS = ["600519.SH", "000001.SZ", "000002.SZ"]
START, END = "2017-01-01", "2019-12-31"

# (family, base_field, kind, slots-to-check)
TARGETS = [
    ("income", "total_revenue", "flow", [0, 1]),
    ("income", "ebit", "flow", [0]),
    ("income", "n_income_attr_p", "flow", [0]),
    ("balancesheet", "total_assets", "snapshot", [0]),
    ("balancesheet", "total_liab", "snapshot", [0]),
    ("cashflow", "n_cashflow_act", "flow", [0]),
]


def _prev_quarter_end(ts: pd.Timestamp):
    """Previous FISCAL quarter-end (Q1->prevQ4, Q2->Q1, Q3->Q2, Q4->Q3).
    Returns None for non-standard period ends (the provider's NaN path)."""
    m, y = ts.month, ts.year
    if (m, ts.day) == (3, 31):
        return pd.Timestamp(y - 1, 12, 31)
    if (m, ts.day) == (6, 30):
        return pd.Timestamp(y, 3, 31)
    if (m, ts.day) == (9, 30):
        return pd.Timestamp(y, 6, 30)
    if (m, ts.day) == (12, 31):
        return pd.Timestamp(y, 9, 30)
    return None


def _trading_calendar() -> pd.DatetimeIndex:
    cal = pd.read_parquet(ROOT / "data" / "reference" / "trade_cal.parquet")
    cal = cal[cal["is_open"] == 1]
    d = pd.to_datetime(cal["cal_date"].astype(str))
    return pd.DatetimeIndex(sorted(d))


def independent_series(family: str, base: str, kind: str, slot: int,
                       ts_code: str, cal: pd.DatetimeIndex) -> pd.Series:
    """Recompute the provider's _q{slot} (snapshot) / _sq_q{slot} (flow) value
    as-of each calendar date, independently from the ledger."""
    led = pd.read_parquet(
        LEDGER / family / f"{family}.parquet",
        columns=["ts_code", "effective_date", "end_date", base],
    )
    led = led[led["ts_code"] == ts_code].copy()
    if led.empty:
        return pd.Series(np.nan, index=cal, dtype="float64")
    led["effective_date"] = pd.to_datetime(led["effective_date"])
    led["end_date"] = pd.to_datetime(led["end_date"])
    led = led.dropna(subset=["effective_date", "end_date"]).sort_values(
        ["effective_date", "end_date"]
    )

    # Walk effective_date events, maintaining the visible {end_date: value} state.
    events = list(led.groupby("effective_date", sort=True))
    out = pd.Series(np.nan, index=cal, dtype="float64")
    state: dict[pd.Timestamp, float] = {}
    ev_idx = 0
    for i, date in enumerate(cal):
        # apply all events with effective_date <= date
        while ev_idx < len(events) and events[ev_idx][0] <= date:
            _, rows = events[ev_idx]
            for _, r in rows.iterrows():
                v = r[base]
                # latest write for an end_date wins (rows already eff-date sorted)
                state[pd.Timestamp(r["end_date"])] = (
                    float(v) if pd.notna(v) else np.nan
                )
            ev_idx += 1
        if not state:
            continue
        ordered = sorted(state.keys(), reverse=True)  # slot 0 = most recent period
        if slot >= len(ordered):
            continue
        end_date = ordered[slot]
        cur = state.get(end_date, np.nan)
        if kind == "snapshot":
            out.iloc[i] = cur
        else:  # flow single-quarter
            if pd.isna(cur):
                continue
            prior_end = _prev_quarter_end(end_date)
            if prior_end is None:
                continue
            if end_date.month == 3:
                out.iloc[i] = cur  # Q1 single-quarter == cumulative
                continue
            prior = state.get(prior_end, np.nan)
            if pd.notna(prior):
                out.iloc[i] = cur - prior
    return out


def main() -> int:
    if not (QLIB / "calendars" / "day.txt").exists():
        print("PROVIDER ABSENT — live-local only. Skipping.")
        return 0
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D

    qlib.init(provider_uri=str(QLIB), region=REG_CN, kernels=1)
    cal = _trading_calendar()
    cal = cal[(cal >= START) & (cal <= END)]

    fields = []
    for fam, base, kind, slots in TARGETS:
        for s in slots:
            suffix = f"_q{s}" if kind == "snapshot" else f"_sq_q{s}"
            fields.append((fam, base, kind, s, base + suffix))

    qts = [t.replace(".", "_") for t in TS]
    prov = D.features(  # noqa: bare-qlib-features (privileged provider parity, workspace script)
        qts, [f"${f[4]}" for f in fields],
        start_time=START, end_time=END, freq="day",
    )
    prov.columns = [f[4] for f in fields]

    total_cmp = 0
    total_mismatch = 0
    print(f"{'field':30s} {'ts':10s} {'cmp':>6s} {'mismatch':>9s} {'nonnull':>8s}  verdict")
    any_fail = False
    for (fam, base, kind, slot, colname) in fields:
        for ts_code in TS:
            qt = ts_code.replace(".", "_")
            try:
                pser = prov.loc[qt, colname]
            except KeyError:
                print(f"{colname:30s} {ts_code:10s}   provider missing instrument — skip")
                continue
            pser = pd.Series(
                pser.to_numpy(dtype="float64"),
                index=pd.DatetimeIndex(pser.index),
            )
            ours = independent_series(fam, base, kind, slot, ts_code, cal)
            common = pser.index.intersection(ours.index)
            lhs = pser.reindex(common).to_numpy(dtype="float64")
            rhs = ours.reindex(common).to_numpy(dtype="float64")
            # relative tolerance (float32 provider storage); both-NaN counts as equal
            ok = np.isclose(lhs, rhs, rtol=1e-3, atol=1.0, equal_nan=True)
            nmis = int((~ok).sum())
            nonnull = int((np.isfinite(lhs) | np.isfinite(rhs)).sum())
            total_cmp += len(common)
            total_mismatch += nmis
            verdict = "PASS" if nmis == 0 else "FAIL"
            if nmis:
                any_fail = True
                first_bad = common[~ok][0]
            else:
                first_bad = ""
            print(f"{colname:30s} {ts_code:10s} {len(common):6d} {nmis:9d} {nonnull:8d}  {verdict} {first_bad}")

    print(f"\nTOTAL: {total_cmp} cells compared, {total_mismatch} mismatches")
    print("RESULT:", "FAIL" if any_fail else "PASS (provider derivation reproduced independently)")
    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
