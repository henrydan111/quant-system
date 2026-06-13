# SCRIPT_STATUS: ACTIVE — P-OP worked example: certify a new operator through the harness
"""Certify the first new E1 operator — ``amplitude_conditional_sum`` (the CICC mmt_range
building block: the rolling sum of daily returns over the lookback window restricted to
HIGH-AMPLITUDE days) — through the OperatorCertification harness, and persist the cert.

This is both the worked example for the P-OP skeleton and the "generate command" an E1
operator goes through before any factor using it may enter the formal IS gate (§10A). It
proves operator SEMANTICS / ALIGNMENT / PIT-causality only — it reads no market data and
consults no truth table (so it burns no OOS window; truth parity is a separate concern).

Dry-run prints the test results + resolved status; ``--live`` persists the cert row.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.alpha_research.factor_library.operator_certification import (  # noqa: E402
    OperatorCertStore,
    run_certification,
)

WINDOW = 20
THRESHOLD = 0.04   # 4% intraday amplitude


# ---- reference (slow, obviously correct) ----
def amplitude_conditional_sum_ref(df: pd.DataFrame) -> pd.Series:
    ret, amp = df["ret"].to_numpy(float), df["amp"].to_numpy(float)
    out = np.full(len(ret), np.nan)
    for t in range(len(ret)):
        if t + 1 < WINDOW:
            continue
        s = 0.0
        for k in range(t - WINDOW + 1, t + 1):
            if amp[k] > THRESHOLD:        # high-amplitude day only
                s += ret[k]
        out[t] = s
    return pd.Series(out, index=df.index)


# ---- production vectorized ----
def amplitude_conditional_sum_vec(df: pd.DataFrame) -> pd.Series:
    contrib = df["ret"].where(df["amp"] > THRESHOLD, 0.0)
    return contrib.rolling(WINDOW, min_periods=WINDOW).sum()


def _hash_fn(fn) -> str:
    return hashlib.sha256(inspect.getsource(fn).encode()).hexdigest()[:16]


def _random_panels(n=24, length=120, seed0=0):
    panels = []
    for i in range(n):
        rng = np.random.default_rng(1000 + i + seed0)
        idx = pd.RangeIndex(length)
        panels.append(pd.DataFrame({
            "ret": rng.standard_normal(length) * 0.02,
            "amp": np.abs(rng.standard_normal(length)) * 0.05,
        }, index=idx))
    return panels


def _golden():
    # amp > 0.04 on exactly the first WINDOW days, all ret=1 -> first defined output == WINDOW
    n = WINDOW + 3
    df = pd.DataFrame({"ret": np.ones(n), "amp": np.full(n, 0.05)})
    df.loc[df.index[WINDOW:], "amp"] = 0.0   # later days excluded
    expected = amplitude_conditional_sum_ref(df)   # reference is the oracle for the golden case
    return [(df, expected)]


def _properties():
    def all_high_equals_rolling_sum(vec):
        rng = np.random.default_rng(7)
        df = pd.DataFrame({"ret": rng.standard_normal(80) * 0.02, "amp": np.full(80, 0.99)})
        got = vec(df)
        plain = df["ret"].rolling(WINDOW, min_periods=WINDOW).sum()
        return np.allclose(got.to_numpy(float), plain.to_numpy(float), atol=1e-12, equal_nan=True)

    def all_low_is_zero(vec):
        df = pd.DataFrame({"ret": np.ones(80), "amp": np.zeros(80)})
        got = vec(df).to_numpy(float)
        defined = got[~np.isnan(got)]
        return defined.size > 0 and np.allclose(defined, 0.0)

    return [all_high_equals_rolling_sum, all_low_is_zero]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="persist the cert (default: dry-run)")
    args = ap.parse_args()

    results = run_certification(
        operator_id="amplitude_conditional_sum",
        reference_fn=amplitude_conditional_sum_ref,
        vectorized_fn=amplitude_conditional_sum_vec,
        random_panels=_random_panels(),
        property_checks=_properties(),
        golden_cases=_golden(),
        window_for_pit=WINDOW,
    )
    print("test results:", results)

    store = OperatorCertStore()
    if args.live:
        dec = store.certify(
            operator_id="amplitude_conditional_sum", test_results=results,
            spec_source="CICC price-volume handbook — mmt_range (振幅条件滚动和)",
            formula_text=f"rolling_sum(ret where amp>{THRESHOLD}, window={WINDOW})",
            reference_impl_hash=_hash_fn(amplitude_conditional_sum_ref),
            vectorized_impl_hash=_hash_fn(amplitude_conditional_sum_vec),
            alignment_policy={"window_closed": "right", "min_periods": WINDOW, "lag": 0,
                              "adjustment_policy": "adjusted_returns"},
            notes="P-OP worked example; first E1 operator certified through the harness",
        )
        print(f"persisted: status={dec.status} failed={dec.failed} missing={dec.missing}")
    else:
        from src.alpha_research.factor_library.operator_certification import resolve_operator_status
        dec = resolve_operator_status("amplitude_conditional_sum", results)
        print(f"[dry-run] would persist status={dec.status} failed={dec.failed} missing={dec.missing}")
    return 0 if dec.status == "certified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
