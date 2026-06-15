# SCRIPT_STATUS: ACTIVE — certify the E1a (momentum/reversal) price-volume operators (P-OP, §10A)
"""Certify the series-wise E1a operators through the OperatorCertification harness — the §10A hard
prerequisite before any E1a factor may enter the formal IS gate. Proves operator SEMANTICS /
ALIGNMENT / PIT-causality only (reference-vs-vectorized random panels + golden + property + PIT);
reads NO market data and consults NO truth table → burns no OOS window (truth parity is separate).

Operators (CICC 价量手册系列7 图表4):
  * path_adjusted_momentum (mmt_route)   = period_return(W) / Σ|daily ret|   (NOT Σret/Σ|ret|;
        the handbook numerator "过去N内收益率" is the PERIOD return — GPT 5.5 Pro E1a Q1)
  * up_down_day_share      (mmt_discrete) = (#up − #down) / N = mean(sign(ret))
  * days_since_high        (mmt_highest_days) = trading days since the window high (0 = today)
  * ts_rank                (mmt_time_rank) = percentile rank of the current price within the window

Certified at BOTH W=20 (1M) and W=250 (1Y) — every E1a factor uses one of these two windows, and
long-window behaviour (warmup / min_periods=1 partial windows) is exactly where bugs hide (GPT Q5).
The composed catalog form Mean(Rank(px,250),20) for mmt_time_rank_20d is additionally checked.

(amplitude_threshold_4pct_conditional_sum for the 4%-threshold building block is certified in
certify_operators.py; the TRUE mmt_range operator amplitude_top_bottom_20pct_return_spread — top/
bottom-20%-by-rank spread — is PENDING and not yet built. cs_rank_time_avg is CROSS-SECTIONAL and
needs a panel-aware harness → deferred.)

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

W_GRID = (20, 250)        # 1M and 1Y — the two windows every E1a factor uses
PANEL_LEN = 400           # > max(W) + buffer so the 250d window has plenty of defined rows


# ───────────────────── reference (slow, obviously correct) + vectorized pairs, W-bound ─────────────────────
def make_path(W):
    """mmt_route = period_return(W) / Σ|daily ret|(W), 0-guarded on a flat window."""
    def ref(df):
        px = df["px"].to_numpy(float)
        ret = np.full(len(px), np.nan); ret[1:] = px[1:] / px[:-1] - 1
        out = np.full(len(px), np.nan)
        for t in range(len(px)):
            if t < W:                               # need px[t-W]
                continue
            period_ret = px[t] / px[t - W] - 1
            den = np.abs(ret[t - W + 1:t + 1]).sum()
            out[t] = (period_ret / den) if den > 0 else 0.0
        return pd.Series(out, index=df.index)

    def vec(df):
        px = df["px"]
        ret = px.pct_change()
        num = px / px.shift(W) - 1
        den = ret.abs().rolling(W, min_periods=W).sum()
        return (num / den).mask(den == 0, 0.0)      # den==0 → 0; warmup (den NaN) stays NaN

    return ref, vec


def make_ud(W):
    """mmt_discrete = mean(sign(ret), W)."""
    def ref(df):
        r = df["ret"].to_numpy(float); out = np.full(len(r), np.nan)
        for t in range(len(r)):
            if t + 1 < W:
                continue
            w = r[t - W + 1:t + 1]
            out[t] = ((w > 0).sum() - (w < 0).sum()) / W
        return pd.Series(out, index=df.index)

    def vec(df):
        return np.sign(df["ret"]).rolling(W, min_periods=W).mean()

    return ref, vec


def make_dsh(W):
    """mmt_highest_days = (W-1) - argmax(high over W)  (0 = high is today)."""
    def ref(df):
        h = df["high"].to_numpy(float); out = np.full(len(h), np.nan)
        for t in range(len(h)):
            if t + 1 < W:
                continue
            w = h[t - W + 1:t + 1]
            out[t] = (W - 1) - int(np.argmax(w))
        return pd.Series(out, index=df.index)

    def vec(df):
        return df["high"].rolling(W, min_periods=W).apply(lambda w: (W - 1) - int(np.argmax(w)), raw=True)

    return ref, vec


def make_tsr(W):
    """mmt_time_rank inner = average-tie percentile rank of the current px within trailing W."""
    def ref(df):
        px = df["px"].to_numpy(float); out = np.full(len(px), np.nan)
        for t in range(len(px)):
            if t + 1 < W:
                continue
            w = px[t - W + 1:t + 1]; cur = w[-1]
            less = (w < cur).sum(); equal = (w == cur).sum()
            out[t] = (less + (equal + 1) / 2.0) / W
        return pd.Series(out, index=df.index)

    def vec(df):
        return df["px"].rolling(W, min_periods=W).rank(pct=True)

    return ref, vec


# ───────────────────────── panels, golden, properties ─────────────────────────
def _panels(n=24, length=PANEL_LEN):
    out = []
    for i in range(n):
        rng = np.random.default_rng(2000 + i)
        ret = rng.standard_normal(length) * 0.02
        px = 100.0 * np.cumprod(1 + ret)
        high = px * (1 + np.abs(rng.standard_normal(length)) * 0.01)
        out.append(pd.DataFrame({"ret": ret, "px": px, "high": high}))
    return out


def _px_df(ret_arr):
    return pd.DataFrame({"px": 100.0 * np.cumprod(1.0 + ret_arr)})


def _golden(ref, input_col, W):
    """One hand-verifiable case per operator (reference is the oracle, cross-checked by vec)."""
    n = W + 4
    if input_col == "px":
        df = _px_df(np.full(n, 0.004))
    elif input_col == "ret":
        df = pd.DataFrame({"ret": np.full(n, 0.004)})
    else:  # high — a monotone-up high series → days_since_high == 0
        df = pd.DataFrame({"high": np.arange(1.0, n + 1.0)})
    return [(df, ref(df))]


def _props(op_id, W):
    """Property checks bound to W. Each takes the vectorized fn."""
    def first(v, df):
        return v(df).dropna().iloc[0]

    if op_id == "path_adjusted_momentum":
        choppy = np.resize([0.01, -0.01], W + 4)   # alternating ±1% → near-zero net path
        return [
            lambda v: first(v, _px_df(np.full(W + 4, 0.005))) > 0,          # pure uptrend → positive
            lambda v: first(v, _px_df(np.full(W + 4, -0.005))) < 0,         # pure downtrend → negative
            lambda v: abs(first(v, _px_df(choppy))) < 0.5,                  # choppy path → near 0 (|·| ≪ trend)
        ]
    if op_id == "up_down_day_share":
        return [
            lambda v: bool(np.nanmax(np.abs(v(_panels(4)[0]).to_numpy(float))) <= 1.0 + 1e-9),  # in [-1,1]
            lambda v: np.isclose(first(v, pd.DataFrame({"ret": np.full(W + 4, 0.01)})), 1.0),   # all-up → +1
            lambda v: np.isclose(first(v, pd.DataFrame({"ret": np.full(W + 4, -0.01)})), -1.0),  # all-down → −1
        ]
    if op_id == "days_since_high":
        return [
            lambda v: bool(np.nanmin(v(_panels(4)[0]).to_numpy(float)) >= 0
                           and np.nanmax(v(_panels(4)[0]).to_numpy(float)) <= W - 1),            # in [0, W-1]
            lambda v: np.isclose(first(v, pd.DataFrame({"high": np.arange(1.0, W + 4)})), 0.0),  # monotone up → 0
            lambda v: np.isclose(first(v, pd.DataFrame({"high": np.arange(W + 3, 0.0, -1)})), W - 1),  # monotone down → W-1
        ]
    if op_id == "ts_rank":
        return [
            lambda v: bool(np.nanmin(v(_panels(4)[0]).to_numpy(float)) >= 0
                           and np.nanmax(v(_panels(4)[0]).to_numpy(float)) <= 1.0 + 1e-9),       # in (0,1]
            lambda v: np.isclose(first(v, _px_df(np.full(W + 4, 0.01))), 1.0),                   # monotone up → 1.0
        ]
    return []


SPECS = {
    "path_adjusted_momentum": {
        "make": make_path, "input": "px",
        "formula": "period_return(W) / Sum(|daily_ret|, W), 0-guarded  (W in {20,250})",
        "spec": "CICC 价量 系列7 图表4 — mmt_route (路径调整动量; period-return numerator)",
    },
    "up_down_day_share": {
        "make": make_ud, "input": "ret",
        "formula": "mean(sign(ret), W) = (#up − #down)/W  (W in {20,250})",
        "spec": "CICC 价量 系列7 图表4 — mmt_discrete (信息离散度动量)",
    },
    "days_since_high": {
        "make": make_dsh, "input": "high",
        "formula": "(W-1) - argmax(high over W)  (0 = high is today; W in {20,250})",
        "spec": "CICC 价量 系列7 图表4 — mmt_highest_days (近1年最高价距今天数)",
    },
    "ts_rank": {
        "make": make_tsr, "input": "px",
        "formula": "percentile rank of current px within trailing W (avg ties)  (W in {20,250})",
        "spec": "CICC 价量 系列7 图表4 — mmt_time_rank (时序rank动量)",
    },
}


def _hash_fn(fn) -> str:
    return hashlib.sha256(inspect.getsource(fn).encode()).hexdigest()[:16]


def _composed_ts_rank_check(panels) -> bool:
    """Verify the ACTUAL catalog expression mmt_time_rank_20d = Mean(Rank(px,250),20):
    independent slow reference == vectorized, and the result is bounded [0,1] (GPT Q5)."""
    INNER, OUTER = 250, 20
    ok = True
    for df in panels:
        px = df["px"]
        vec = px.rolling(INNER, min_periods=INNER).rank(pct=True).rolling(OUTER, min_periods=OUTER).mean()
        arr = px.to_numpy(float)
        inner = np.full(len(arr), np.nan)
        for t in range(len(arr)):
            if t + 1 < INNER:
                continue
            w = arr[t - INNER + 1:t + 1]; cur = w[-1]
            inner[t] = ((w < cur).sum() + ((w == cur).sum() + 1) / 2.0) / INNER
        ref = pd.Series(inner).rolling(OUTER, min_periods=OUTER).mean().to_numpy(float)
        got = vec.to_numpy(float)
        if not np.allclose(got, ref, atol=1e-12, equal_nan=True):
            ok = False
        defined = got[~np.isnan(got)]
        if defined.size == 0 or defined.min() < 0 or defined.max() > 1.0 + 1e-9:
            ok = False
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="persist the certs (default: dry-run)")
    args = ap.parse_args()
    store = OperatorCertStore()
    panels = _panels()
    all_ok = True

    for op_id, s in SPECS.items():
        per_window = {}
        op_ok = True
        for W in W_GRID:
            ref, vec = s["make"](W)
            results = run_certification(
                operator_id=op_id, reference_fn=ref, vectorized_fn=vec,
                random_panels=panels, property_checks=_props(op_id, W),
                golden_cases=_golden(ref, s["input"], W), window_for_pit=W,
            )
            dec = resolve_operator_status(op_id, results)
            per_window[W] = (dec.status, results)
            print(f"{op_id:26} W={W:<4} status={dec.status:11} failed={dec.failed} missing={dec.missing}")
            if dec.status != "certified":
                op_ok = False
        if not op_ok:
            all_ok = False
            continue
        if args.live:
            # operator is window-agnostic; persist once, noting BOTH windows passed
            _, last_results = per_window[W_GRID[-1]]
            ref_last, vec_last = s["make"](W_GRID[-1])
            store.certify(
                operator_id=op_id, test_results=last_results, spec_source=s["spec"],
                formula_text=s["formula"], reference_impl_hash=_hash_fn(s["make"]),
                vectorized_impl_hash=_hash_fn(s["make"]),
                alignment_policy={"window_closed": "right", "min_periods": "W (eval drops partial)",
                                  "lag": 0, "adjustment_policy": "adjusted_prices",
                                  "certified_windows": list(W_GRID)},
                notes=("E1a price-volume operator certified through the P-OP harness at "
                       f"W in {list(W_GRID)} (no truth parity)"))

    composed_ok = _composed_ts_rank_check(panels)
    print(f"\ncomposed mmt_time_rank_20d = Mean(Rank(px,250),20)  ref==vec & bounded[0,1]: {composed_ok}")
    if not composed_ok:
        all_ok = False

    if args.live and all_ok:
        print("persisted:", sorted(store.certified_operators()))
    else:
        print("[dry-run]" if not args.live else "[NOT all certified — nothing forced]")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
