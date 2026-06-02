# Frozen OOS Top Set — selection trace (mechanical)

Generated 2026-05-31T00:59:22 by applying the PRE-COMMITTED rule (oos_topset_selection_rule.md) to the Wave-2 IS screen (screening_is_50).
**OOS NOT YET RUN.** Rule was frozen before the screen; this trace is deterministic.

## Frozen top set (13 factors)

| Factor | Tier | ICIR_20d | LS Sharpe | LS MaxDD% |
|---|---|---|---|---|
| `grow_n_income_attr_p_yoy_accel_q` | Tier1 | 0.499 | 5.35 | 0.09 |
| `grow_operate_profit_yoy_accel_q` | Tier1 | 0.501 | 4.74 | 0.07 |
| `grow_total_revenue_yoy_accel_q` | Tier1 | 0.449 | 3.58 | 0.09 |
| `grow_operate_profit_yoy_q` | Tier1 | 0.326 | 2.88 | 0.32 |
| `grow_n_income_attr_p_yoy_q` | Tier1 | 0.305 | 2.83 | 0.45 |
| `rev_turnover_spike_5d` | Tier2 | 0.268 | 2.60 | 0.52 |
| `qual_piotroski_fscore_9pt` | Tier1 | 0.334 | 2.22 | 0.64 |
| `acc_cash_roa_ttm` | Tier1 | 0.301 | 1.64 | 1.19 |
| `acc_cfo_to_ni_ttm` | Tier2 | 0.308 | 1.36 | 0.54 |
| `val_retearn_yield` | Tier2 | 0.287 | 1.10 | 1.71 |
| `liq_zero_ret_days_10d` | Tier2 | 0.296 | 1.09 | 0.61 |
| `val_fcf_ev_ttm` | Tier2 | 0.270 | 1.01 | 0.51 |
| `val_ebit_ev_ttm` | Tier2 | 0.283 | 0.93 | 1.27 |

## Redundancy prune (logged discretionary step)

- dropped `grow_revenue_yoy_accel_q` (kept `grow_total_revenue_yoy_accel_q` — higher LS Sharpe)

## Full decision trace (all 50)

| Factor | Decision | Reason | ICIR20 | LS | MDD% |
|---|---|---|---|---|---|
| `acc_cash_roa_ttm` | SELECT (Tier1) | passes frozen rule | 0.301 | 1.64 | 1.19 |
| `acc_cfo_to_ni_ttm` | SELECT (Tier2) | passes frozen rule | 0.308 | 1.36 | 0.54 |
| `grow_n_income_attr_p_yoy_accel_q` | SELECT (Tier1) | passes frozen rule | 0.499 | 5.35 | 0.09 |
| `grow_n_income_attr_p_yoy_q` | SELECT (Tier1) | passes frozen rule | 0.305 | 2.83 | 0.45 |
| `grow_operate_profit_yoy_accel_q` | SELECT (Tier1) | passes frozen rule | 0.501 | 4.74 | 0.07 |
| `grow_operate_profit_yoy_q` | SELECT (Tier1) | passes frozen rule | 0.326 | 2.88 | 0.32 |
| `grow_total_revenue_yoy_accel_q` | SELECT (Tier1) | passes frozen rule | 0.449 | 3.58 | 0.09 |
| `liq_zero_ret_days_10d` | SELECT (Tier2) | passes frozen rule | 0.296 | 1.09 | 0.61 |
| `qual_piotroski_fscore_9pt` | SELECT (Tier1) | passes frozen rule | 0.334 | 2.22 | 0.64 |
| `rev_turnover_spike_5d` | SELECT (Tier2) | passes frozen rule | 0.268 | 2.60 | 0.52 |
| `val_ebit_ev_ttm` | SELECT (Tier2) | passes frozen rule | 0.283 | 0.93 | 1.27 |
| `val_fcf_ev_ttm` | SELECT (Tier2) | passes frozen rule | 0.270 | 1.01 | 0.51 |
| `val_retearn_yield` | SELECT (Tier2) | passes frozen rule | 0.287 | 1.10 | 1.71 |
| `acc_asset_growth` | exclude | eligible but below Tier1/Tier2 thresholds | -0.015 | 0.40 | 1.23 |
| `acc_capex_intensity_ttm` | exclude | eligible but below Tier1/Tier2 thresholds | 0.143 | 1.36 | 0.97 |
| `acc_dWC_inventory` | exclude | eligible but below Tier1/Tier2 thresholds | 0.129 | 1.30 | 0.56 |
| `acc_dWC_receivables` | exclude | eligible but below Tier1/Tier2 thresholds | -0.020 | 0.57 | 0.84 |
| `acc_goodwill_ratio` | EXCLUDE | structural-zero-pending (Round-6) | -0.183 | -0.30 | 1.94 |
| `acc_inventory_sales_mismatch_yoy` | exclude | eligible but below Tier1/Tier2 thresholds | -0.454 | -4.51 | 1.45 |
| `acc_net_share_issuance` | exclude | eligible but below Tier1/Tier2 thresholds | 0.133 | 1.41 | 0.23 |
| `acc_noa_scaled` | EXCLUDE | structural-zero-pending (Round-6) | -0.051 | 0.18 | 1.38 |
| `acc_receivables_sales_mismatch_yoy` | exclude | eligible but below Tier1/Tier2 thresholds | -0.498 | -4.72 | 1.78 |
| `acc_total_accruals_ttm` | exclude | eligible but below Tier1/Tier2 thresholds | -0.270 | -1.58 | 1.58 |
| `grow_revenue_yoy_accel_q` | exclude | redundancy-pruned (kept grow_total_revenue_yoy_accel_q) | 0.459 | 3.54 | 0.09 |
| `grow_revenue_yoy_q` | exclude | eligible but below Tier1/Tier2 thresholds | 0.242 | 2.77 | 0.52 |
| `grow_total_revenue_yoy_q` | exclude | eligible but below Tier1/Tier2 thresholds | 0.240 | 2.76 | 0.52 |
| `liq_roll_spread_low_20d` | EXCLUDE | short-side (|icir|=0.47, LS sign opposite) | 0.469 | -4.36 | 0.16 |
| `liq_zero_ret_days_20d` | exclude | eligible but below Tier1/Tier2 thresholds | 0.299 | -1.37 | 0.22 |
| `liq_zero_ret_days_5d` | exclude | eligible but below Tier1/Tier2 thresholds | 0.290 | 0.23 | 0.08 |
| `liq_zero_ret_ex_susp_20d` | exclude | eligible but below Tier1/Tier2 thresholds | 0.299 | -1.37 | 0.22 |
| `mom_52w_high_proximity` | exclude | eligible but below Tier1/Tier2 thresholds | -0.036 | -0.76 | 5.13 |
| `mom_continuous_info_252d_dir` | exclude | eligible but below Tier1/Tier2 thresholds | -0.072 | -0.71 | 2.75 |
| `mom_skip5d_120d` | exclude | eligible but below Tier1/Tier2 thresholds | -0.205 | -1.62 | 5.40 |
| `mom_volscaled_120d` | exclude | eligible but below Tier1/Tier2 thresholds | -0.265 | -2.21 | 6.93 |
| `mom_volscaled_20d` | exclude | eligible but below Tier1/Tier2 thresholds | -0.347 | -2.75 | 8.28 |
| `mom_volscaled_60d` | exclude | eligible but below Tier1/Tier2 thresholds | -0.426 | -3.09 | 8.23 |
| `qual_cash_collection_ttm` | exclude | eligible but below Tier1/Tier2 thresholds | 0.069 | -0.04 | 0.67 |
| `qual_gross_profitability_ttm` | exclude | eligible but below Tier1/Tier2 thresholds | 0.102 | 0.95 | 1.56 |
| `qual_margin_ebit_of_gr` | exclude | eligible but below Tier1/Tier2 thresholds | 0.080 | 0.14 | 2.01 |
| `qual_margin_op_of_gr` | exclude | eligible but below Tier1/Tier2 thresholds | 0.114 | 0.35 | 2.12 |
| `qual_margin_profit_to_gr` | exclude | eligible but below Tier1/Tier2 thresholds | 0.105 | 0.40 | 2.02 |
| `rev_gap_reversal_1d` | exclude | eligible but below Tier1/Tier2 thresholds | -0.334 | -3.56 | 5.40 |
| `rev_high_turnover_1d` | exclude | eligible but below Tier1/Tier2 thresholds | 0.100 | 2.09 | 0.37 |
| `risk_gap_vol_20d` | exclude | eligible but below Tier1/Tier2 thresholds | -0.547 | -2.42 | 6.43 |
| `risk_garman_klass_20d` | exclude | eligible but below Tier1/Tier2 thresholds | -0.570 | -2.44 | 7.74 |
| `risk_parkinson_logrange_120d` | exclude | eligible but below Tier1/Tier2 thresholds | -0.419 | -1.24 | 4.64 |
| `risk_parkinson_logrange_20d` | exclude | eligible but below Tier1/Tier2 thresholds | -0.537 | -2.21 | 7.36 |
| `risk_parkinson_logrange_60d` | exclude | eligible but below Tier1/Tier2 thresholds | -0.473 | -1.69 | 6.06 |
| `tech_high_breakout_freshness_250d` | exclude | eligible but below Tier1/Tier2 thresholds | 0.025 | -0.50 | 2.76 |
| `val_ncav_to_price` | exclude | eligible but below Tier1/Tier2 thresholds | 0.205 | 1.99 | 0.84 |
