"""Sanity-check the custom equal-weight simulator vs the proven VectorizedBacktester.

Same book (top-40 by value composite, liquid universe, monthly, ALWAYS 40 — no
cash-out so both engines are directly comparable) run through both. If CAGR/MDD
agree within a couple points, the custom simulator (used for the JQ replications
with cash-out) is trustworthy.
"""
from __future__ import annotations
import numpy as np, pandas as pd
import jq_rep_utils as JR
import research_utils as ru
import backtest_harness as bh

IS_START, IS_END = "2014-01-01", "2020-12-31"
F = JR.factor_panel()
VAL_W = {"val_bp": 1.0, "val_ep_ttm": 1.0, "val_sp_ttm": 1.0, "val_cftp": 1.0}
VAL_NEG = {k: False for k in VAL_W}

# --- vectorized (ground truth) ---
m = bh.run_composite_backtest(F, VAL_W, VAL_NEG, IS_START, IS_END,
                              universe_kwargs={"liq_pct_floor": 0.40},
                              topk=40, benchmark="000905_SH", label="value k40 VECTORIZED")
print(f"VECTORIZED   CAGR={m['cagr']:+7.2%} MDD={m['mdd']:+7.2%} Sharpe={m['sharpe']:.2f}")

# --- custom simulator: same top-40 holdings ---
rebal = ru.monthly_rebalance_dates(IS_START, IS_END)
uni = ru.build_universe_mask(F, rebal, liq_pct_floor=0.40)
score = bh.build_composite_signal(F, VAL_W, VAL_NEG, rebal, uni)  # (date,inst)->composite rank
hold = {}
for d, g in score.groupby(level=0):
    hold[pd.Timestamp(d)] = list(g.droplevel(0).sort_values(ascending=False).head(40).index)
# harness costs are open 5bps + close 15bps -> one-way avg = (0.0005+0.0015)/2 = 0.0010
net = JR.simulate_eqw_monthly(hold, IS_START, IS_END, cost_oneway=0.0010)
mm = ru.goal_metrics(net)
print(f"SIMULATOR    CAGR={mm['cagr']:+7.2%} MDD={mm['mdd']:+7.2%} Sharpe={mm['sharpe']:.2f}")
print(f"delta CAGR = {mm['cagr']-m['cagr']:+.2%}  (simulator - vectorized)")
print("OK" if abs(mm['cagr']-m['cagr']) < 0.03 else "WARN: >3% divergence — investigate")
