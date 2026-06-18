# SCRIPT_STATUS: ACTIVE — E1d (CICC chart 40) lead/lag golden-value regression (GPT review requirement)
"""Lightweight golden-value regression locking the lead/lag SHIFT DIRECTION of the 8 E1d price-volume
correlation factors (GPT factor-logic review 2026-06-18: "add a small golden-value regression test for
the lead/lag shift direction before matrix/P-GATE"). This is an EXPRESSION/golden test, NOT an
OperatorCertification custom P-OP (no custom operator is added — the factors are inline Corr+Ref).

Three locks:
  1. NO forward Ref (no `Ref(..., -N)`) anywhere — a forward reference would be lookahead.
  2. Shift-direction STRING lock: `_post` shifts the LEADING (turnover) leg back one more vs sync;
     `_prior` shifts the price/return (counterpart) leg back. A wrong shift changes the string.
  3. NUMPY semantic golden: on a synthetic series where turnover genuinely leads, the `_post` pairing
     (turnover further back) has the strongest |corr|; where price/return leads, `_prior` peaks.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from src.alpha_research.factor_library import operators as op

W = 20
E1D = {
    "corr_price_turn_20d": op.corr_price_turn(W),
    "corr_price_turn_post_20d": op.corr_price_turn_post(W),
    "corr_price_turn_prior_20d": op.corr_price_turn_prior(W),
    "corr_ret_turn_20d": op.corr_ret_turn(W),
    "corr_ret_turn_post_20d": op.corr_ret_turn_post(W),
    "corr_ret_turn_prior_20d": op.corr_ret_turn_prior(W),
    "corr_ret_turnd_20d": op.corr_ret_turnd(W),
    "corr_ret_turnd_prior_20d": op.corr_ret_turnd_prior(W),
}
_FWD_REF = re.compile(r",\s*-\d+\s*\)")   # a Ref offset that is negative (forward) — never allowed


# ── Lock 1: no forward Ref (lookahead) in any of the 8 expressions ──────────────────────────────
def test_no_forward_ref():
    for name, expr in E1D.items():
        assert _FWD_REF.search(expr) is None, f"{name} contains a forward Ref (lookahead): {expr}"
        # every field atom must sit inside a Ref(...,>=1) frame (cheap belt-and-braces vs the full lint)
        assert "$turnover_rate" in expr or "$close" in expr
        assert expr.startswith("Corr("), f"{name} is not a Corr expression: {expr}"


# ── Lock 2: shift-direction string lock — exact golden expressions for all 8 (any shift change breaks
# this). `_RET` is the adjusted daily-return atom; `_PX` the adjusted close level; `_TURN` the lag-1
# turnover; `_TURND` Δturnover. `_post` wraps the TURNOVER leg in an extra Ref; `_prior` wraps the
# price/return leg in an extra Ref. ─────────────────────────────────────────────────────────────────
_TURN = "Ref($turnover_rate, 1)"
_TURND = "(Ref($turnover_rate, 1) - Ref($turnover_rate, 2))"
_PX = "Ref(($close * $adj_factor), 1)"
_RET = "(Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 2) - 1)"
_GOLDEN = {
    "corr_price_turn_20d": f"Corr({_TURN}, {_PX}, 20)",
    "corr_price_turn_post_20d": f"Corr(Ref({_TURN}, 1), {_PX}, 20)",            # turnover leg +1 Ref
    "corr_price_turn_prior_20d": f"Corr({_TURN}, Ref({_PX}, 1), 20)",          # price leg +1 Ref
    "corr_ret_turn_20d": f"Corr({_TURN}, {_RET}, 20)",
    "corr_ret_turn_post_20d": f"Corr(Ref({_TURN}, 1), {_RET}, 20)",            # turnover leg +1 Ref
    "corr_ret_turn_prior_20d": f"Corr({_TURN}, Ref({_RET}, 1), 20)",          # return leg +1 Ref
    "corr_ret_turnd_20d": f"Corr({_TURND}, {_RET}, 20)",
    "corr_ret_turnd_prior_20d": f"Corr({_TURND}, Ref({_RET}, 1), 20)",        # return leg +1 Ref
}


def test_shift_direction_string_lock():
    assert E1D == _GOLDEN, {k: E1D[k] for k in E1D if E1D[k] != _GOLDEN.get(k)}


# ── Lock 3: numpy semantic golden — the shift direction realizes the intended lead ──────────────
def _rolling_corr(a: pd.Series, b: pd.Series, window: int) -> float:
    """Mean rolling-window Pearson corr of a,b (mimics Qlib Corr(a,b,window) reduced to a scalar)."""
    return a.rolling(window).corr(b).iloc[window:].mean()


def _leadlag(series_turn, series_px, rel_shift_turn: int, rel_shift_px: int, window: int) -> float:
    """Replicate the expression's RELATIVE shifts: post shifts turnover back (rel_shift_turn=1);
    prior shifts the px/ret leg back (rel_shift_px=1); sync shifts neither."""
    t = pd.Series(series_turn).shift(rel_shift_turn)
    p = pd.Series(series_px).shift(rel_shift_px)
    return _rolling_corr(t, p, window)


def test_lead_lag_direction_numpy_golden():
    rng = np.random.default_rng(20260618)
    n = 400
    x = np.cumsum(rng.standard_normal(n))   # a persistent latent signal

    # Scenario A — TURNOVER leads price by 1 day: price[t] tracks the signal one day late.
    turn_A = x.copy()
    px_A = np.concatenate([[x[0]], x[:-1]])          # px[t] = x[t-1]  (price lags turnover)
    sync_A = _leadlag(turn_A, px_A, 0, 0, W)
    post_A = _leadlag(turn_A, px_A, 1, 0, W)         # turnover shifted back 1 (the _post pairing)
    prior_A = _leadlag(turn_A, px_A, 0, 1, W)        # px shifted back 1 (the _prior pairing)
    # _post (turnover further back) must align turn[t-1] with px[t]=x[t-1] -> strongest
    assert post_A > sync_A and post_A > prior_A, (post_A, sync_A, prior_A)
    assert post_A > 0.9, post_A

    # Scenario B — PRICE leads turnover by 1 day: turnover[t] tracks the signal one day late.
    px_B = x.copy()
    turn_B = np.concatenate([[x[0]], x[:-1]])        # turn[t] = x[t-1]  (turnover lags price)
    sync_B = _leadlag(turn_B, px_B, 0, 0, W)
    post_B = _leadlag(turn_B, px_B, 1, 0, W)
    prior_B = _leadlag(turn_B, px_B, 0, 1, W)        # px shifted back 1 -> aligns px[t-1] with turn[t]=x[t-1]
    assert prior_B > sync_B and prior_B > post_B, (prior_B, sync_B, post_B)
    assert prior_B > 0.9, prior_B
