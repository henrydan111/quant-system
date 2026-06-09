"""Validate the simulator as a TOTAL-return proxy by reproducing the prior effort's
known event-driven OOS number (VL@core k40 RAW -> event-driven +11.64% total return).
If the simulator (total-return, frictionless) lands near +11.6% (a touch higher, since
it ignores limit/suspension friction), it is validated for relative screening and as a
total-return proxy whose absolute level is mildly optimistic.
"""
from __future__ import annotations
import numpy as np, pandas as pd
import jq_rep_utils as JR
import research_utils as ru
import backtest_harness as bh

OOS_START, OOS_END = "2021-01-01", "2026-02-26"
F = JR.factor_panel()
VAL_W = {"val_bp": 1.0, "val_ep_ttm": 1.0, "val_sp_ttm": 1.0, "val_cftp": 1.0}
LOWVOL_W = {"risk_vol_60d": 1.0, "risk_downvol_60d": 1.0}
W = {**VAL_W, **LOWVOL_W}
NEG = {**{k: False for k in VAL_W}, **{k: True for k in LOWVOL_W}}

rebal = ru.monthly_rebalance_dates(OOS_START, OOS_END)
uni = ru.build_universe_mask(F, rebal, liq_pct_floor=0.40)
score = bh.build_composite_signal(F, W, NEG, rebal, uni)
hold = {}
for d, g in score.groupby(level=0):
    hold[pd.Timestamp(d)] = list(g.droplevel(0).sort_values(ascending=False).head(40).index)
net = JR.simulate_eqw_monthly(hold, OOS_START, OOS_END, cost_oneway=0.00185, max_weight=0.10)
m = ru.goal_metrics(net)
print(f"SIMULATOR  VL@core k40 OOS  CAGR={m['cagr']:+.2%} MDD={m['mdd']:+.2%} Sharpe={m['sharpe']:.2f}")
print("known EVENT-DRIVEN total: +11.64% / -14.52% / 0.80 ; vectorized price: +6.17% / -19.03% / 0.47")
print(f"simulator vs event-driven CAGR delta = {m['cagr']-0.1164:+.2%}")
