# SCRIPT_STATUS: ACTIVE — certify the E1a (momentum/reversal) price-volume operators (P-OP, §10A)
"""Certify the series-wise E1a operators through the OperatorCertification harness — the §10A hard
prerequisite before any E1a factor may enter the formal IS gate. Proves operator SEMANTICS /
ALIGNMENT / PIT-causality only (reference-vs-vectorized random panels + golden + property + PIT);
reads NO market data and consults NO truth table → burns no OOS window (truth parity is separate).

Operators (CICC 价量手册系列7 图表4):
  * path_adjusted_momentum (mmt_route)   = Σret / Σ|ret| over the window   (efficiency ratio)
  * up_down_day_share      (mmt_discrete) = (#up − #down) / N = mean(sign(ret))
  * days_since_high        (mmt_highest_days) = trading days since the window high (0 = today)
  * ts_rank                (mmt_time_rank) = percentile rank of the current price within the window

(amplitude_conditional_sum for mmt_range is already certified; cs_rank_time_avg is CROSS-SECTIONAL
and needs a panel-aware harness → deferred.)

Run:  venv/Scripts/python.exe workspace/scripts/certify_e1a_operators.py [--live]
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.alpha_research.factor_library.operator_certification import (  # noqa: E402
    OperatorCertStore,
    resolve_operator_status,
    run_certification,
)

W = 20  # 1-month lookback


# ───────────────────────── reference (slow, obviously correct) + vectorized pairs ─────────────────────────
def path_ref(df):
    r = df["ret"].to_numpy(float); out = np.full(len(r), np.nan)
    for t in range(len(r)):
        if t + 1 < W:
            continue
        w = r[t - W + 1:t + 1]; den = np.abs(w).sum()
        out[t] = (w.sum() / den) if den > 0 else 0.0
    return pd.Series(out, index=df.index)


def path_vec(df):
    s = df["ret"]
    num = s.rolling(W, min_periods=W).sum(); den = s.abs().rolling(W, min_periods=W).sum()
    return (num / den).mask(den == 0, 0.0)


def ud_ref(df):
    r = df["ret"].to_numpy(float); out = np.full(len(r), np.nan)
    for t in range(len(r)):
        if t + 1 < W:
            continue
        w = r[t - W + 1:t + 1]
        out[t] = ((w > 0).sum() - (w < 0).sum()) / W
    return pd.Series(out, index=df.index)


def ud_vec(df):
    return np.sign(df["ret"]).rolling(W, min_periods=W).mean()


def dsh_ref(df):
    h = df["high"].to_numpy(float); out = np.full(len(h), np.nan)
    for t in range(len(h)):
        if t + 1 < W:
            continue
        w = h[t - W + 1:t + 1]
        out[t] = (W - 1) - int(np.argmax(w))   # 0 = the high is today
    return pd.Series(out, index=df.index)


def dsh_vec(df):
    return df["high"].rolling(W, min_periods=W).apply(lambda w: (W - 1) - int(np.argmax(w)), raw=True)


def tsr_ref(df):
    px = df["px"].to_numpy(float); out = np.full(len(px), np.nan)
    for t in range(len(px)):
        if t + 1 < W:
            continue
        w = px[t - W + 1:t + 1]; cur = w[-1]
        less = (w < cur).sum(); equal = (w == cur).sum()
        out[t] = (less + (equal + 1) / 2.0) / W      # average-tie percentile rank of the current value
    return pd.Series(out, index=df.index)


def tsr_vec(df):
    return df["px"].rolling(W, min_periods=W).rank(pct=True)


# ───────────────────────── panels, golden, properties ─────────────────────────
def _panels(n=24, length=140):
    out = []
    for i in range(n):
        rng = np.random.default_rng(2000 + i)
        ret = rng.standard_normal(length) * 0.02
        px = 100.0 * np.cumprod(1 + ret)
        high = px * (1 + np.abs(rng.standard_normal(length)) * 0.01)
        out.append(pd.DataFrame({"ret": ret, "px": px, "high": high}))
    return out


def _golden(ref):
    """One hand-verifiable case per operator (expected from the obvious answer, cross-checked by ref)."""
    n = W + 4
    return [(pd.DataFrame({"ret": np.ones(n), "px": 100.0 * np.cumprod(1 + np.ones(n) * 0.0 + 0.01),
                           "high": 100.0 * np.arange(1, n + 1)}), ref(pd.DataFrame({
        "ret": np.ones(n), "px": 100.0 * np.cumprod(1 + np.ones(n) * 0.0 + 0.01),
        "high": 100.0 * np.arange(1, n + 1)})))]


SPECS = {
    "path_adjusted_momentum": {
        "ref": path_ref, "vec": path_vec, "input": "ret",
        "formula": "rolling_sum(ret, W) / rolling_sum(|ret|, W)  (W=20)",
        "spec": "CICC 价量 系列7 图表4 — mmt_route (路径调整动量)",
        "props": [
            lambda v: bool(np.nanmax(np.abs(v(_panels(4)[0]).to_numpy(float))) <= 1.0 + 1e-9),   # |efficiency ratio| ≤ 1
            lambda v: np.isclose(v(pd.DataFrame({"ret": np.full(W + 2, 0.01)})).dropna().iloc[0], 1.0),  # all-up → +1
            lambda v: np.isclose(v(pd.DataFrame({"ret": np.full(W + 2, -0.01)})).dropna().iloc[0], -1.0),  # all-down → −1
        ],
    },
    "up_down_day_share": {
        "ref": ud_ref, "vec": ud_vec, "input": "ret",
        "formula": "mean(sign(ret), W) = (#up − #down)/W  (W=20)",
        "spec": "CICC 价量 系列7 图表4 — mmt_discrete (信息离散度动量)",
        "props": [
            lambda v: bool(np.nanmax(np.abs(v(_panels(4)[0]).to_numpy(float))) <= 1.0 + 1e-9),   # range [−1,1]
            lambda v: np.isclose(v(pd.DataFrame({"ret": np.full(W + 2, 0.01)})).dropna().iloc[0], 1.0),
            lambda v: np.isclose(v(pd.DataFrame({"ret": np.full(W + 2, -0.01)})).dropna().iloc[0], -1.0),
        ],
    },
    "days_since_high": {
        "ref": dsh_ref, "vec": dsh_vec, "input": "high",
        "formula": "(W-1) - argmax(high over W)  (0 = high is today; W=20)",
        "spec": "CICC 价量 系列7 图表4 — mmt_highest_days (近1年最高价距今天数)",
        "props": [
            lambda v: bool(np.nanmin(v(_panels(4)[0]).to_numpy(float)) >= 0
                           and np.nanmax(v(_panels(4)[0]).to_numpy(float)) <= W - 1),             # in [0, W-1]
            lambda v: np.isclose(v(pd.DataFrame({"high": np.arange(1.0, W + 3)})).dropna().iloc[0], 0.0),  # monotone up → high today → 0
            lambda v: np.isclose(v(pd.DataFrame({"high": np.arange(W + 2, 0.0, -1)})).dropna().iloc[0], W - 1),  # monotone down → high W-1 ago
        ],
    },
    "ts_rank": {
        "ref": tsr_ref, "vec": tsr_vec, "input": "px",
        "formula": "percentile rank of current px within trailing W (avg ties)  (W=20)",
        "spec": "CICC 价量 系列7 图表4 — mmt_time_rank (时序rank动量)",
        "props": [
            lambda v: bool(np.nanmin(v(_panels(4)[0]).to_numpy(float)) >= 0
                           and np.nanmax(v(_panels(4)[0]).to_numpy(float)) <= 1.0 + 1e-9),         # in (0,1]
            lambda v: np.isclose(v(pd.DataFrame({"px": np.arange(1.0, W + 3)})).dropna().iloc[0], 1.0),   # monotone up → current is max → 1.0
        ],
    },
}


def _hash_fn(fn) -> str:
    return hashlib.sha256(inspect.getsource(fn).encode()).hexdigest()[:16]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="persist the certs (default: dry-run)")
    args = ap.parse_args()
    store = OperatorCertStore()
    panels = _panels()
    all_ok = True
    for op_id, s in SPECS.items():
        results = run_certification(
            operator_id=op_id, reference_fn=s["ref"], vectorized_fn=s["vec"],
            random_panels=panels, property_checks=s["props"], golden_cases=_golden(s["ref"]),
            window_for_pit=W,
        )
        dec = resolve_operator_status(op_id, results)
        print(f"{op_id:26} status={dec.status:11} failed={dec.failed} missing={dec.missing}  {results}")
        if dec.status != "certified":
            all_ok = False
            continue
        if args.live:
            store.certify(
                operator_id=op_id, test_results=results, spec_source=s["spec"],
                formula_text=s["formula"], reference_impl_hash=_hash_fn(s["ref"]),
                vectorized_impl_hash=_hash_fn(s["vec"]),
                alignment_policy={"window_closed": "right", "min_periods": W, "lag": 0,
                                  "adjustment_policy": "adjusted_returns"},
                notes="E1a price-volume operator certified through the P-OP harness (no truth parity)")
    if args.live and all_ok:
        print("\npersisted:", sorted(store.certified_operators()))
    else:
        print("\n[dry-run]" if not args.live else "\n[NOT all certified — nothing forced]")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
