# SCRIPT_STATUS: ACTIVE — certify the E1b (volatility) price-volume operators (P-OP, §10A)
"""Certify the ONE genuine custom E1b operator — ``sign_conditional_std`` — through the
OperatorCertification harness (§10A: semantics / alignment / PIT only; NO truth parity, burns no OOS),
and verify the first-use built-ins ``Greater`` / ``Less`` (elementwise max/min) used by the shadow
factors. The shadow lines + high/low ratio are plain Greater/Less arithmetic (no custom operator), so
only ``sign_conditional_std`` is persisted to the cert store (the manifest's sole E1b required_operator).

``sign_conditional_std`` (CICC 下行/上行波动率): TRUE subset standard deviation of daily returns over
only the sign-matching, LIMIT-EXCLUDED days in the window — NOT the zero-fill ``risk_downvol`` proxy.
ddof=1 (matches Qlib Std); NaN when <2 selected obs (the sum-of-squares form gives 0/0 automatically);
NaN limit_status -> included (exclude only KNOWN limit days); NaN ret -> not selected. GPT E1b review B1.

Run:  venv/Scripts/python.exe workspace/scripts/certify_e1b_operators.py [--live]
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.alpha_research.factor_library.operator_certification import (  # noqa: E402
    OperatorCertStore, resolve_operator_status, run_certification,
)

W_GRID = (20, 60, 120)        # 1M / 3M / 6M
PANEL_LEN = 320               # > max(W) + buffer


# ── reference (slow, obviously-correct) + vectorized (mirrors the Qlib expression) ──
def _select(ret: np.ndarray, lim: np.ndarray, sign: str) -> np.ndarray:
    """Boolean selection: sign-matching AND not a KNOWN limit day. NaN ret -> False (numpy compare);
    NaN limit -> |.|>=0.5 is False -> NOT a limit -> included (we exclude only known limit days)."""
    signed = (ret < 0) if sign == "down" else (ret > 0)
    is_limit = np.abs(lim) >= 0.5            # NaN -> False
    return signed & ~is_limit


def make_ref(W, sign):
    def ref(df):
        ret = df["ret"].to_numpy(float); lim = df["limit"].to_numpy(float)
        out = np.full(len(ret), np.nan)
        for t in range(len(ret)):
            lo = max(0, t - W + 1)
            sel = _select(ret[lo:t + 1], lim[lo:t + 1], sign)
            vals = ret[lo:t + 1][sel]
            vals = vals[~np.isnan(vals)]
            if len(vals) >= 2:
                out[t] = np.std(vals, ddof=1)      # sample std (ddof=1) over the selected subset ONLY
        return pd.Series(out, index=df.index)
    return ref


def make_vec(W, sign):
    """Vectorized sum-of-squares subset std — the exact pandas analogue of the Qlib expression
    Power((Σm² - (Σm)²/n)/(n-1), 0.5) with n=Σsel, m=If(sel, ret, 0)."""
    def vec(df):
        ret = df["ret"]; lim = df["limit"]
        signed = ((ret < 0) if sign == "down" else (ret > 0)).astype(float)
        not_limit = 1.0 - (lim.abs() >= 0.5).astype(float)          # NaN limit -> 0 -> not_limit=1
        sel = signed * not_limit
        masked = np.where(sel > 0.5, ret.to_numpy(float), 0.0)
        masked = pd.Series(masked, index=df.index)
        n = sel.rolling(W, min_periods=1).sum()
        s1 = masked.rolling(W, min_periods=1).sum()
        s2 = (masked * masked).rolling(W, min_periods=1).sum()
        var = (s2 - s1 * s1 / n) / (n - 1.0)
        ge = (n >= 2).astype(float)
        mask = ge / ge                                              # 1 for n>=2, 0/0=NaN for n<2 (explicit floor)
        return np.sqrt(np.maximum(var, 0.0)) * mask                # clamp tiny-neg var; NaN when n<2
    return vec


def _panels(n=24, length=PANEL_LEN):
    out = []
    for i in range(n):
        rng = np.random.default_rng(7000 + i)
        ret = rng.standard_normal(length) * 0.02
        # inject limit days (~3%): +1 on big-up, -1 on big-down, else 0; a few NaN limit + NaN ret
        lim = np.zeros(length)
        lim[ret > 0.045] = 1.0
        lim[ret < -0.045] = -1.0
        lim[rng.random(length) < 0.02] = np.nan          # unknown-limit days
        ret[rng.random(length) < 0.01] = np.nan          # suspended days
        out.append(pd.DataFrame({"ret": ret, "limit": lim}))
    return out


def _props(sign, W):
    """Properties bound to (sign, W)."""
    def first_defined(v, df):
        s = v(df).dropna()
        return s.iloc[0] if len(s) else np.nan

    def all_down(df_len=W + 4):
        # all-down panel, no limits: down-vol == full std of the returns; up-vol == NaN (no up days)
        rng = np.random.default_rng(99)
        r = -np.abs(rng.standard_normal(df_len)) * 0.01 - 0.001
        return pd.DataFrame({"ret": r, "limit": np.zeros(df_len)})

    props = [
        lambda v: bool(np.all(v(_panels(4)[0]).dropna() >= -1e-12)),       # std is non-negative
    ]
    if sign == "down":
        props.append(lambda v: not np.isnan(first_defined(v, all_down())))  # down-vol defined on all-down
        props.append(lambda v: np.isnan(make_vec(W, "up")(all_down()).dropna().iloc[0])
                     if len(make_vec(W, "up")(all_down()).dropna()) else True)  # up-vol NaN on all-down
    return props


def _golden(sign, W):
    """Hand-verifiable: a window with exactly two selected (sign-matching, unlimited) returns ->
    std(ddof=1) of those two; a one-selected window -> NaN (min 2 obs)."""
    # construct ret so that within the first full window there are exactly 2 down days, no limits
    n = W + 2
    ret = np.full(n, 0.005)            # all up
    ret[0] = -0.02; ret[1] = -0.04     # two down days at the start
    lim = np.zeros(n)
    df = pd.DataFrame({"ret": ret, "limit": lim})
    return [(df, make_ref(W, sign)(df))]   # ref is the oracle; vec is cross-checked against it


def _verify_greater_less() -> bool:
    """First-use semantic check for Qlib Greater/Less (elementwise max/min) via D.features on a tiny
    real slice — Greater(open,close)=max, Less(open,close)=min."""
    import qlib
    from qlib.data import D
    from qlib.config import REG_CN
    qlib.init(provider_uri=str(PROJECT_ROOT / "data" / "qlib_data"), region=REG_CN, kernels=1)
    df = D.features(["000001_SZ"], ["Greater($open,$close)", "Less($open,$close)", "$open", "$close"],
                    start_time="2021-01-01", end_time="2021-03-31")
    df.columns = ["gt", "ls", "o", "c"]
    df = df.dropna()
    ok_gt = bool(np.allclose(df["gt"], np.maximum(df["o"], df["c"])))
    ok_ls = bool(np.allclose(df["ls"], np.minimum(df["o"], df["c"])))
    print(f"first-use Greater==elementwise-max: {ok_gt} | Less==elementwise-min: {ok_ls}")
    return ok_gt and ok_ls


def _hash_fn(fn) -> str:
    return hashlib.sha256(inspect.getsource(fn).encode()).hexdigest()[:16]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="persist the cert (default: dry-run)")
    args = ap.parse_args()
    store = OperatorCertStore()
    panels = _panels()
    all_ok = True

    op_id = "sign_conditional_std"
    per_window = {}
    for W in W_GRID:
        for sign in ("down", "up"):
            ref, vec = make_ref(W, sign), make_vec(W, sign)
            results = run_certification(
                operator_id=op_id, reference_fn=ref, vectorized_fn=vec, random_panels=panels,
                property_checks=_props(sign, W), golden_cases=_golden(sign, W), window_for_pit=W)
            dec = resolve_operator_status(op_id, results)
            per_window[f"W{W}_{sign}"] = results
            print(f"{op_id:22} W={W:<4} {sign:4} status={dec.status:11} failed={dec.failed} missing={dec.missing}")
            if dec.status != "certified":
                all_ok = False

    gl_ok = _verify_greater_less()
    if not gl_ok:
        all_ok = False

    if args.live and all_ok:
        # status resolves from the conservative deepest-window/down row; both windows+signs persisted.
        last = per_window[f"W{W_GRID[-1]}_down"]
        store.certify(
            operator_id=op_id, test_results=last,
            spec_source="CICC 价量 系列7 图表16 — 下行/上行波动率 (subset std, limit-excluded)",
            formula_text="Power((Sum(m^2,N) - Sum(m,N)^2/Sum(sel,N)) / (Sum(sel,N)-1), 0.5); "
                         "sel=[ret<0|>0]*(1-[|limit_status|>=0.5]); m=If(sel,ret,0); ddof=1; NaN if n<2",
            reference_impl_hash=_hash_fn(make_ref), vectorized_impl_hash=_hash_fn(make_vec),
            alignment_policy={"window_closed": "right", "min_periods": "1 (warmed by the 2008 runway in "
                              "the 2010+ IS eval, same as E1a)", "lag": 0, "adjustment_policy": "adjusted_returns",
                              "limit_basis": "materialized $limit_status (raw close vs raw published limits)",
                              "certified_windows": list(W_GRID), "signs": ["down", "up"]},
            per_window_results={k: v for k, v in per_window.items()},
            notes="E1b volatility subset-std operator certified at W in {20,60,120} x {down,up} (no truth "
                  "parity). Greater/Less verified as elementwise max/min (first use). Shadows are plain "
                  "Greater/Less arithmetic (no custom operator).")
        print("persisted:", sorted(store.certified_operators()))
    else:
        print("[dry-run]" if not args.live else "[NOT all certified — nothing persisted]")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
