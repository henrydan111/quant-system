# Batch Factor Screening Review (Latest Backend, New-Data Included)

## Executive Summary
- This run screened **149** factors from the latest backend with `include_new_data = True`.
- The strongest factor by `|Rank ICIR|` was **liq_vol_cv_20d**.
- Requested kernels: **qlib default**; effective kernels: **qlib default**.
- Grade split: A=18, B=25, C=72, D=34.

## Run Metadata
- Generated at: `2026-04-01 20:11:51`
- Date window: `2012-01-01` to `2026-02-27`
- Horizons: `5, 10, 20`
- Engine: `batch`
- Include new data: `True`
- Qlib provider: `E:\量化系统\data\qlib_data`
- Cache mode: `refresh`
- Requested kernels: `qlib default`
- Effective kernels: `qlib default`

## Grade Distribution
| Grade | Count |
| --- | --- |
| A (Graduated) | 18 |
| B (Strong IC) | 25 |
| C (Moderate) | 72 |
| D (Weak) | 34 |

## Top 20 Factors
| factor | grade | rank_icir_5d | monotonic | ls_ann_return | warning_flags |
| --- | --- | --- | --- | --- | --- |
| liq_vol_cv_20d | A (Graduated) | -0.729 | Y | -117.5% |  |
| liq_log_dollar_vol | A (Graduated) | -0.542 | Y | -192.1% |  |
| rev_max_return_20d | B (Strong IC) | -0.539 | N | -80.5% |  |
| comp_rev_low_turn | A (Graduated) | +0.484 | Y | +118.9% |  |
| mom_intraday_20d | A (Graduated) | -0.479 | Y | -142.9% |  |
| liq_vol_surge | B (Strong IC) | -0.474 | N | -99.4% |  |
| liq_turnover_f_5d | B (Strong IC) | -0.472 | N | -135.6% |  |
| liq_turnover_ratio_5_60 | B (Strong IC) | -0.466 | N | -99.5% |  |
| mom_ewm_60d | A (Graduated) | -0.461 | Y | -131.2% |  |
| risk_skew_60d | A (Graduated) | -0.459 | Y | -59.0% |  |
| mom_high_moment_20d | B (Strong IC) | -0.456 | N | -98.1% |  |
| tech_skew_20d | A (Graduated) | -0.451 | Y | -57.3% |  |
| mom_ewm_20d | B (Strong IC) | -0.435 | N | -107.7% |  |
| mom_weighted_120d | A (Graduated) | -0.407 | Y | -120.4% |  |
| tech_close_to_low_20d | B (Strong IC) | -0.406 | N | -70.3% |  |
| liq_turnover_5d | B (Strong IC) | -0.403 | N | -119.8% |  |
| risk_vol_10d | B (Strong IC) | -0.402 | N | -69.7% |  |
| liq_turnover_f_20d | B (Strong IC) | -0.393 | N | -117.0% |  |
| liq_vol_ratio_ma5 | B (Strong IC) | -0.387 | N | -84.5% |  |
| tech_price_to_ma60 | A (Graduated) | -0.386 | Y | -140.5% |  |

## A / B Grade Candidates
| factor | grade | rank_icir_5d | monotonic | ls_ann_return | warning_flags |
| --- | --- | --- | --- | --- | --- |
| liq_vol_cv_20d | A (Graduated) | -0.729 | Y | -117.5% |  |
| liq_log_dollar_vol | A (Graduated) | -0.542 | Y | -192.1% |  |
| rev_max_return_20d | B (Strong IC) | -0.539 | N | -80.5% |  |
| comp_rev_low_turn | A (Graduated) | +0.484 | Y | +118.9% |  |
| mom_intraday_20d | A (Graduated) | -0.479 | Y | -142.9% |  |
| liq_vol_surge | B (Strong IC) | -0.474 | N | -99.4% |  |
| liq_turnover_f_5d | B (Strong IC) | -0.472 | N | -135.6% |  |
| liq_turnover_ratio_5_60 | B (Strong IC) | -0.466 | N | -99.5% |  |
| mom_ewm_60d | A (Graduated) | -0.461 | Y | -131.2% |  |
| risk_skew_60d | A (Graduated) | -0.459 | Y | -59.0% |  |
| mom_high_moment_20d | B (Strong IC) | -0.456 | N | -98.1% |  |
| tech_skew_20d | A (Graduated) | -0.451 | Y | -57.3% |  |
| mom_ewm_20d | B (Strong IC) | -0.435 | N | -107.7% |  |
| mom_weighted_120d | A (Graduated) | -0.407 | Y | -120.4% |  |
| tech_close_to_low_20d | B (Strong IC) | -0.406 | N | -70.3% |  |
| liq_turnover_5d | B (Strong IC) | -0.403 | N | -119.8% |  |
| risk_vol_10d | B (Strong IC) | -0.402 | N | -69.7% |  |
| liq_turnover_f_20d | B (Strong IC) | -0.393 | N | -117.0% |  |
| liq_vol_ratio_ma5 | B (Strong IC) | -0.387 | N | -84.5% |  |
| tech_price_to_ma60 | A (Graduated) | -0.386 | Y | -140.5% |  |
| risk_vol_5d | B (Strong IC) | -0.375 | N | -45.1% |  |
| liq_turnover_10d | B (Strong IC) | -0.373 | N | -113.5% |  |
| risk_vol_20d | B (Strong IC) | -0.372 | N | -74.4% |  |
| mom_return_20d | B (Strong IC) | -0.371 | N | -122.4% |  |
| tech_rsi_28 | B (Strong IC) | -0.370 | N | -80.9% |  |
| liq_spread_proxy_20d | B (Strong IC) | -0.367 | N | -76.1% |  |
| risk_range_ratio_20d | B (Strong IC) | -0.361 | N | -73.0% |  |
| comp_small_value | A (Graduated) | +0.358 | Y | +127.4% |  |
| val_pb_change_60d | A (Graduated) | -0.357 | Y | -117.5% |  |
| flow_net_inflow_20d | B (Strong IC) | +0.357 | N | +85.7% |  |
| grow_profit_trend | A (Graduated) | +0.344 | Y | +24.6% | reduced_quantiles |
| comp_size_quality | A (Graduated) | +0.341 | Y | +103.9% |  |
| mom_return_60d | A (Graduated) | -0.336 | Y | -118.0% |  |
| tech_price_to_ma20 | B (Strong IC) | -0.335 | N | -107.5% |  |
| liq_turnover_20d | A (Graduated) | -0.332 | Y | -101.5% |  |
| liq_amihud_20d | A (Graduated) | +0.325 | Y | +144.7% |  |
| tech_ma5_ma20_ratio | B (Strong IC) | -0.322 | N | -96.0% |  |
| risk_vol_of_vol | A (Graduated) | -0.321 | Y | -49.0% |  |
| north_hold_change_5d | B (Strong IC) | +0.309 | N | +73.3% | reduced_quantiles |
| comp_defensive | B (Strong IC) | +0.303 | N | +47.8% |  |
| grow_rev_trend | A (Graduated) | +0.302 | Y | +97.8% | reduced_quantiles |
| mom_return_10d | B (Strong IC) | -0.302 | N | -88.7% |  |
| rev_return_10d | B (Strong IC) | +0.302 | N | +88.6% |  |

## New-Data Factor Highlights
| family | factor | grade | rank_icir_5d | monotonic | ls_ann_return | warning_flags |
| --- | --- | --- | --- | --- | --- | --- |
| moneyflow / flow | flow_net_inflow_20d | B (Strong IC) | +0.357 | N | +85.7% |  |
| northbound / north | north_hold_change_5d | B (Strong IC) | +0.309 | N | +73.3% | reduced_quantiles |
| northbound / north | north_hold_change_20d | C (Moderate) | +0.283 | N | +86.3% | reduced_quantiles |
| moneyflow / flow | flow_large_small_ratio | C (Moderate) | +0.280 | N | +37.8% |  |
| northbound / north | north_accumulation_20d | C (Moderate) | +0.277 | N | +38.7% | reduced_quantiles |
| margin | margin_net_buy_20d | C (Moderate) | -0.245 | N | -14.3% | reduced_quantiles |
| northbound / north | north_flow_momentum | C (Moderate) | +0.231 | N | +171.8% | reduced_quantiles |
| moneyflow / flow | flow_net_inflow_5d | C (Moderate) | +0.220 | N | +43.7% |  |
| moneyflow / flow | flow_large_buy_ratio_5d | C (Moderate) | -0.197 | N | -29.3% |  |
| moneyflow / flow | flow_inflow_surge | C (Moderate) | -0.187 | N | -31.5% |  |
| earnings | earn_earnings_momentum | C (Moderate) | +0.162 | N | +136.0% | reduced_quantiles |
| margin | margin_sl_balance_change | C (Moderate) | -0.124 | N | -14.2% | reduced_quantiles |
| moneyflow / flow | flow_large_net_pct_20d | C (Moderate) | +0.111 | Y | +45.0% |  |
| earnings | earn_surprise_revenue | C (Moderate) | +0.105 | Y | +33.5% |  |
| northbound / north | north_hold_pct | D (Weak) | +0.085 | N | +133.8% | reduced_quantiles |
| margin | margin_balance_pct | D (Weak) | -0.070 | N | -11.4% | reduced_quantiles |
| moneyflow / flow | flow_small_net_pct_20d | D (Weak) | -0.014 | Y | -54.2% |  |
| earnings | earn_surprise_eps | D (Weak) | -0.014 | N | +55.4% | reduced_quantiles,constant_xs |

Covered families in this run: `earnings, margin, moneyflow / flow, northbound / north`
Families with no matching factor names in this run: `forecast, holder, limit`

## Warnings And Caveats
- `L/S` is a diagnostic based on overlapping forward returns, not a directly tradable return estimate.
- Kernel mode in this run was `requested_kernels = qlib default` and `effective_kernels = qlib default`.
- Warning flag frequency:
  - `reduced_quantiles`: 26
  - `constant_xs`: 3
  - `low_obs`: 2

## All Factor Performance

### A (Graduated)
| factor | grade | rank_icir_5d | rank_icir_10d | rank_icir_20d | mean_rank_ic_5d | ic_hit_rate_5d | monotonic | ls_ann_return | warning_flags | obs_coverage_primary | rankic_coverage_primary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| liq_vol_cv_20d | A (Graduated) | -0.729 | -0.768 | -0.713 | -0.052 | 73.2% | Y | -117.5% |  | 100.0% | 100.0% |
| liq_log_dollar_vol | A (Graduated) | -0.542 | -0.646 | -0.738 | -0.074 | 65.8% | Y | -192.1% |  | 100.0% | 100.0% |
| comp_rev_low_turn | A (Graduated) | +0.484 | +0.505 | +0.550 | +0.066 | 60.3% | Y | +118.9% |  | 100.0% | 100.0% |
| mom_intraday_20d | A (Graduated) | -0.479 | -0.530 | -0.602 | -0.064 | 63.8% | Y | -142.9% |  | 100.0% | 100.0% |
| mom_ewm_60d | A (Graduated) | -0.461 | -0.506 | -0.552 | -0.073 | 52.9% | Y | -131.2% |  | 100.0% | 100.0% |
| risk_skew_60d | A (Graduated) | -0.459 | -0.522 | -0.525 | -0.039 | 62.8% | Y | -59.0% |  | 100.0% | 100.0% |
| tech_skew_20d | A (Graduated) | -0.451 | -0.517 | -0.525 | -0.037 | 62.9% | Y | -57.3% |  | 100.0% | 100.0% |
| mom_weighted_120d | A (Graduated) | -0.407 | -0.465 | -0.505 | -0.064 | 50.6% | Y | -120.4% |  | 100.0% | 100.0% |
| tech_price_to_ma60 | A (Graduated) | -0.386 | -0.437 | -0.481 | -0.062 | 61.2% | Y | -140.5% |  | 100.0% | 100.0% |
| comp_small_value | A (Graduated) | +0.358 | +0.422 | +0.498 | +0.050 | 61.0% | Y | +127.4% |  | 100.0% | 100.0% |
| val_pb_change_60d | A (Graduated) | -0.357 | -0.429 | -0.482 | -0.052 | 59.8% | Y | -117.5% |  | 100.0% | 100.0% |
| grow_profit_trend | A (Graduated) | +0.344 | +0.301 | +0.334 | +0.008 | 54.8% | Y | +24.6% | reduced_quantiles | 53.0% | 53.0% |
| comp_size_quality | A (Graduated) | +0.341 | +0.410 | +0.492 | +0.035 | 63.4% | Y | +103.9% |  | 100.0% | 100.0% |
| mom_return_60d | A (Graduated) | -0.336 | -0.399 | -0.438 | -0.052 | 60.2% | Y | -118.0% |  | 100.0% | 100.0% |
| liq_turnover_20d | A (Graduated) | -0.332 | -0.405 | -0.473 | -0.059 | 60.9% | Y | -101.5% |  | 100.0% | 100.0% |
| liq_amihud_20d | A (Graduated) | +0.325 | +0.408 | +0.494 | +0.045 | 50.1% | Y | +144.7% |  | 100.0% | 100.0% |
| risk_vol_of_vol | A (Graduated) | -0.321 | -0.388 | -0.460 | -0.038 | 58.0% | Y | -49.0% |  | 100.0% | 100.0% |
| grow_rev_trend | A (Graduated) | +0.302 | +0.255 | +0.271 | +0.006 | 58.4% | Y | +97.8% | reduced_quantiles | 52.8% | 52.8% |

### B (Strong IC)
| factor | grade | rank_icir_5d | rank_icir_10d | rank_icir_20d | mean_rank_ic_5d | ic_hit_rate_5d | monotonic | ls_ann_return | warning_flags | obs_coverage_primary | rankic_coverage_primary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rev_max_return_20d | B (Strong IC) | -0.539 | -0.621 | -0.671 | -0.069 | 58.9% | N | -80.5% |  | 100.0% | 100.0% |
| liq_vol_surge | B (Strong IC) | -0.474 | -0.488 | -0.509 | -0.051 | 69.3% | N | -99.4% |  | 100.0% | 100.0% |
| liq_turnover_f_5d | B (Strong IC) | -0.472 | -0.554 | -0.631 | -0.076 | 67.9% | N | -135.6% |  | 100.0% | 100.0% |
| liq_turnover_ratio_5_60 | B (Strong IC) | -0.466 | -0.479 | -0.505 | -0.050 | 69.4% | N | -99.5% |  | 100.0% | 100.0% |
| mom_high_moment_20d | B (Strong IC) | -0.456 | -0.517 | -0.580 | -0.073 | 59.4% | N | -98.1% |  | 100.0% | 100.0% |
| mom_ewm_20d | B (Strong IC) | -0.435 | -0.431 | -0.479 | -0.065 | 52.6% | N | -107.7% |  | 100.0% | 100.0% |
| tech_close_to_low_20d | B (Strong IC) | -0.406 | -0.396 | -0.428 | -0.054 | 61.4% | N | -70.3% |  | 100.0% | 100.0% |
| liq_turnover_5d | B (Strong IC) | -0.403 | -0.469 | -0.532 | -0.069 | 64.8% | N | -119.8% |  | 100.0% | 100.0% |
| risk_vol_10d | B (Strong IC) | -0.402 | -0.468 | -0.507 | -0.064 | 59.0% | N | -69.7% |  | 100.0% | 100.0% |
| liq_turnover_f_20d | B (Strong IC) | -0.393 | -0.485 | -0.573 | -0.067 | 62.6% | N | -117.0% |  | 100.0% | 100.0% |
| liq_vol_ratio_ma5 | B (Strong IC) | -0.387 | -0.306 | -0.311 | -0.033 | 72.0% | N | -84.5% |  | 100.0% | 100.0% |
| risk_vol_5d | B (Strong IC) | -0.375 | -0.442 | -0.498 | -0.053 | 59.1% | N | -45.1% |  | 100.0% | 100.0% |
| liq_turnover_10d | B (Strong IC) | -0.373 | -0.447 | -0.511 | -0.065 | 62.3% | N | -113.5% |  | 100.0% | 100.0% |
| risk_vol_20d | B (Strong IC) | -0.372 | -0.433 | -0.481 | -0.065 | 57.6% | N | -74.4% |  | 100.0% | 100.0% |
| mom_return_20d | B (Strong IC) | -0.371 | -0.424 | -0.471 | -0.055 | 60.9% | N | -122.4% |  | 100.0% | 100.0% |
| tech_rsi_28 | B (Strong IC) | -0.370 | -0.391 | -0.415 | -0.051 | 53.0% | N | -80.9% |  | 100.0% | 100.0% |
| liq_spread_proxy_20d | B (Strong IC) | -0.367 | -0.426 | -0.482 | -0.067 | 57.0% | N | -76.1% |  | 100.0% | 100.0% |
| risk_range_ratio_20d | B (Strong IC) | -0.361 | -0.420 | -0.476 | -0.066 | 56.6% | N | -73.0% |  | 100.0% | 100.0% |
| flow_net_inflow_20d | B (Strong IC) | +0.357 | +0.487 | +0.590 | +0.033 | 63.5% | N | +85.7% |  | 100.0% | 100.0% |
| tech_price_to_ma20 | B (Strong IC) | -0.335 | -0.341 | -0.400 | -0.049 | 61.2% | N | -107.5% |  | 100.0% | 100.0% |
| tech_ma5_ma20_ratio | B (Strong IC) | -0.322 | -0.352 | -0.411 | -0.047 | 59.2% | N | -96.0% |  | 100.0% | 100.0% |
| north_hold_change_5d | B (Strong IC) | +0.309 | +0.307 | +0.302 | +0.013 | 60.5% | N | +73.3% | reduced_quantiles | 53.8% | 53.8% |
| comp_defensive | B (Strong IC) | +0.303 | +0.341 | +0.375 | +0.048 | 52.5% | N | +47.8% |  | 100.0% | 100.0% |
| mom_return_10d | B (Strong IC) | -0.302 | -0.300 | -0.362 | -0.043 | 61.1% | N | -88.7% |  | 100.0% | 100.0% |
| rev_return_10d | B (Strong IC) | +0.302 | +0.300 | +0.362 | +0.043 | 61.1% | N | +88.6% |  | 100.0% | 100.0% |

### C (Moderate)
| factor | grade | rank_icir_5d | rank_icir_10d | rank_icir_20d | mean_rank_ic_5d | ic_hit_rate_5d | monotonic | ls_ann_return | warning_flags | obs_coverage_primary | rankic_coverage_primary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mom_return_5d | C (Moderate) | -0.299 | -0.246 | -0.264 | -0.041 | 61.7% | N | -96.7% |  | 100.0% | 100.0% |
| rev_return_5d | C (Moderate) | +0.299 | +0.246 | +0.264 | +0.041 | 61.7% | N | +96.7% |  | 100.0% | 100.0% |
| tech_ma20_ma60_ratio | C (Moderate) | -0.296 | -0.361 | -0.390 | -0.045 | 57.8% | Y | -107.3% |  | 100.0% | 100.0% |
| risk_vol_60d | C (Moderate) | -0.294 | -0.358 | -0.429 | -0.057 | 54.5% | N | -54.9% |  | 100.0% | 100.0% |
| rev_return_3d | C (Moderate) | +0.291 | +0.205 | +0.207 | +0.038 | 61.3% | N | +95.1% |  | 100.0% | 100.0% |
| tech_rsi_14 | C (Moderate) | -0.290 | -0.280 | -0.322 | -0.039 | 51.3% | N | -43.9% |  | 100.0% | 100.0% |
| north_hold_change_20d | C (Moderate) | +0.283 | +0.297 | +0.272 | +0.012 | 57.3% | N | +86.3% | reduced_quantiles | 53.4% | 53.4% |
| val_relative_pe | C (Moderate) | -0.281 | -0.320 | -0.365 | -0.023 | 57.9% | Y | -53.6% |  | 100.0% | 100.0% |
| flow_large_small_ratio | C (Moderate) | +0.280 | +0.323 | +0.392 | +0.012 | 50.9% | N | +37.8% |  | 100.0% | 100.0% |
| north_accumulation_20d | C (Moderate) | +0.277 | +0.288 | +0.258 | +0.012 | 56.8% | N | +38.7% | reduced_quantiles | 55.1% | 55.1% |
| mom_return_120d | C (Moderate) | -0.276 | -0.322 | -0.342 | -0.042 | 57.0% | Y | -95.0% |  | 100.0% | 100.0% |
| tech_rsi_6 | C (Moderate) | -0.274 | -0.193 | -0.193 | -0.035 | 54.2% | N | -45.1% | reduced_quantiles | 100.0% | 100.0% |
| mom_acceleration_20d | C (Moderate) | -0.271 | -0.298 | -0.325 | -0.032 | 58.3% | N | -73.4% |  | 100.0% | 100.0% |
| risk_vol_120d | C (Moderate) | -0.250 | -0.306 | -0.374 | -0.049 | 53.3% | N | -37.5% |  | 100.0% | 100.0% |
| liq_turnover_60d | C (Moderate) | -0.249 | -0.313 | -0.381 | -0.045 | 57.0% | Y | -73.9% |  | 100.0% | 100.0% |
| margin_net_buy_20d | C (Moderate) | -0.245 | -0.292 | -0.309 | -0.017 | 58.2% | N | -14.3% | reduced_quantiles | 100.0% | 100.0% |
| comp_multi_6 | C (Moderate) | +0.240 | +0.287 | +0.357 | +0.032 | 56.0% | Y | +51.5% |  | 100.0% | 100.0% |
| tech_macd_signal | C (Moderate) | -0.232 | -0.191 | -0.239 | -0.031 | 53.9% | N | -45.8% |  | 100.0% | 100.0% |
| comp_low_vol_value | C (Moderate) | +0.232 | +0.277 | +0.329 | +0.046 | 51.3% | N | +43.6% |  | 100.0% | 100.0% |
| north_flow_momentum | C (Moderate) | +0.231 | +0.285 | +0.246 | +0.010 | 57.2% | N | +171.8% | reduced_quantiles | 57.2% | 57.2% |
| mom_low_moment_20d | C (Moderate) | +0.230 | +0.286 | +0.331 | +0.042 | 54.4% | N | +34.7% |  | 100.0% | 100.0% |
| grow_profit_acceleration | C (Moderate) | +0.226 | +0.193 | +0.222 | +0.004 | 53.7% | Y | -18.9% | reduced_quantiles | 44.2% | 44.2% |
| val_bp | C (Moderate) | +0.225 | +0.261 | +0.310 | +0.035 | 49.5% | Y | +54.7% |  | 100.0% | 100.0% |
| val_bps_to_price | C (Moderate) | +0.222 | +0.256 | +0.306 | +0.033 | 49.9% | Y | +52.9% |  | 100.0% | 100.0% |
| flow_net_inflow_5d | C (Moderate) | +0.220 | +0.385 | +0.456 | +0.021 | 58.5% | N | +43.7% |  | 100.0% | 100.0% |
| grow_roe_yoy | C (Moderate) | +0.215 | +0.243 | +0.275 | +0.015 | 54.2% | Y | +38.5% |  | 100.0% | 100.0% |
| liq_turnover_skew_20d | C (Moderate) | -0.208 | -0.162 | -0.056 | -0.012 | 60.2% | Y | -38.6% |  | 100.0% | 100.0% |
| comp_quality_value | C (Moderate) | +0.207 | +0.234 | +0.269 | +0.031 | 48.6% | Y | +33.7% |  | 100.0% | 100.0% |
| comp_growth_value | C (Moderate) | +0.202 | +0.237 | +0.278 | +0.022 | 51.4% | Y | +40.0% |  | 100.0% | 100.0% |
| size_ln_mcap | C (Moderate) | -0.199 | -0.243 | -0.287 | -0.034 | 61.0% | Y | -131.9% |  | 100.0% | 100.0% |
| size_ln_mcap_sq | C (Moderate) | -0.199 | -0.243 | -0.287 | -0.034 | 60.6% | Y | -131.9% |  | 100.0% | 100.0% |
| val_div_ratio | C (Moderate) | +0.197 | +0.227 | +0.270 | +0.021 | 47.4% | Y | -75.3% | reduced_quantiles | 100.0% | 100.0% |
| flow_large_buy_ratio_5d | C (Moderate) | -0.197 | -0.215 | -0.263 | -0.023 | 56.3% | N | -29.3% |  | 100.0% | 100.0% |
| risk_var_95_20d | C (Moderate) | +0.192 | +0.243 | +0.289 | +0.033 | 55.8% | N | +32.2% |  | 100.0% | 100.0% |
| mom_return_250d | C (Moderate) | -0.191 | -0.219 | -0.241 | -0.029 | 54.4% | N | -55.1% |  | 100.0% | 100.0% |
| mom_overnight_20d | C (Moderate) | +0.189 | +0.236 | +0.283 | +0.015 | 71.1% | N | +55.8% |  | 100.0% | 100.0% |
| risk_tail_60d | C (Moderate) | +0.188 | +0.237 | +0.307 | +0.036 | 56.1% | N | +30.7% |  | 100.0% | 100.0% |
| flow_inflow_surge | C (Moderate) | -0.187 | -0.318 | -0.331 | -0.011 | 50.2% | N | -31.5% |  | 100.0% | 100.0% |
| grow_rev_acceleration | C (Moderate) | +0.187 | +0.154 | +0.180 | +0.004 | 56.8% | Y | -49.8% | reduced_quantiles | 44.2% | 44.2% |
| rev_min_return_20d | C (Moderate) | +0.182 | +0.223 | +0.263 | +0.030 | 54.8% | N | +23.7% |  | 100.0% | 100.0% |
| grow_eps_yoy | C (Moderate) | +0.180 | +0.203 | +0.231 | +0.014 | 50.9% | Y | +34.1% |  | 100.0% | 100.0% |
| comp_52w_position | C (Moderate) | -0.177 | -0.136 | -0.179 | -0.023 | 53.1% | N | -40.5% |  | 100.0% | 100.0% |
| comp_momentum_quality | C (Moderate) | -0.171 | -0.196 | -0.200 | -0.025 | 55.6% | Y | -64.5% |  | 100.0% | 100.0% |
| risk_downvol_20d | C (Moderate) | -0.171 | -0.213 | -0.257 | -0.031 | 54.0% | N | -16.5% |  | 100.0% | 100.0% |
| grow_opprofit_yoy | C (Moderate) | +0.164 | +0.186 | +0.217 | +0.012 | 50.6% | Y | +36.3% |  | 100.0% | 100.0% |
| risk_downvol_60d | C (Moderate) | -0.164 | -0.206 | -0.275 | -0.032 | 53.4% | N | -17.4% |  | 100.0% | 100.0% |
| val_div_yield | C (Moderate) | +0.164 | +0.197 | +0.240 | +0.024 | 48.2% | Y | +25.7% |  | 100.0% | 100.0% |
| val_ep_ttm | C (Moderate) | +0.162 | +0.189 | +0.222 | +0.024 | 47.0% | N | +24.3% |  | 100.0% | 100.0% |
| earn_earnings_momentum | C (Moderate) | +0.162 | +0.184 | +0.213 | +0.012 | 55.1% | N | +136.0% | reduced_quantiles | 100.0% | 100.0% |
| val_sp_ttm | C (Moderate) | +0.160 | +0.185 | +0.221 | +0.022 | 48.5% | Y | +32.9% |  | 100.0% | 100.0% |
| grow_netprofit_yoy | C (Moderate) | +0.158 | +0.176 | +0.197 | +0.012 | 51.6% | Y | +33.4% |  | 100.0% | 100.0% |
| comp_cash_sheep | C (Moderate) | +0.156 | +0.187 | +0.227 | +0.022 | 49.8% | Y | +20.4% |  | 100.0% | 100.0% |
| rev_return_1d | C (Moderate) | +0.155 | +0.084 | +0.079 | +0.019 | 56.0% | N | +42.0% |  | 100.0% | 100.0% |
| val_ep | C (Moderate) | +0.155 | +0.179 | +0.206 | +0.021 | 54.1% | N | +13.6% |  | 100.0% | 100.0% |
| val_sp | C (Moderate) | +0.150 | +0.174 | +0.207 | +0.021 | 48.2% | N | +27.9% |  | 100.0% | 100.0% |
| tech_bb_pct | C (Moderate) | -0.148 | -0.115 | -0.165 | -0.020 | 52.8% | N | -40.1% |  | 100.0% | 100.0% |
| comp_garp | C (Moderate) | +0.137 | +0.157 | +0.180 | +0.017 | 48.6% | Y | +19.7% |  | 100.0% | 100.0% |
| grow_opprofit_qoq | C (Moderate) | +0.136 | +0.168 | +0.216 | +0.006 | 49.3% | Y | +15.6% |  | 100.0% | 100.0% |
| size_ln_circmv | C (Moderate) | -0.135 | -0.168 | -0.199 | -0.023 | 59.7% | Y | -101.5% |  | 100.0% | 100.0% |
| comp_magic_formula | C (Moderate) | +0.133 | +0.151 | +0.175 | +0.016 | 47.6% | N | +8.7% |  | 100.0% | 100.0% |
| qual_margin_trend | C (Moderate) | +0.132 | +0.124 | +0.151 | +0.003 | 55.3% | Y | -19.9% | reduced_quantiles | 52.7% | 52.7% |
| qual_margin_stability | C (Moderate) | +0.131 | +0.166 | +0.245 | +0.005 | 54.6% | N | +10.8% | reduced_quantiles | 100.0% | 100.0% |
| margin_sl_balance_change | C (Moderate) | -0.124 | -0.130 | -0.166 | -0.007 | 51.4% | N | -14.2% | reduced_quantiles | 100.0% | 100.0% |
| comp_val_qual | C (Moderate) | +0.117 | +0.134 | +0.155 | +0.016 | 47.5% | N | +6.5% |  | 100.0% | 100.0% |
| grow_roe_improvement | C (Moderate) | -0.112 | -0.118 | -0.075 | -0.004 | 55.0% | N | -127.9% | reduced_quantiles | 55.1% | 55.1% |
| val_cftp | C (Moderate) | +0.112 | +0.131 | +0.157 | +0.009 | 50.0% | N | -2.0% |  | 100.0% | 100.0% |
| flow_large_net_pct_20d | C (Moderate) | +0.111 | +0.168 | +0.187 | +0.009 | 54.7% | Y | +45.0% |  | 100.0% | 100.0% |
| earn_surprise_revenue | C (Moderate) | +0.105 | +0.123 | +0.143 | +0.009 | 45.8% | Y | +33.5% |  | 100.0% | 100.0% |
| grow_revenue_yoy | C (Moderate) | +0.105 | +0.123 | +0.143 | +0.009 | 45.8% | Y | +33.5% |  | 100.0% | 100.0% |
| tech_williams_r_14 | C (Moderate) | -0.105 | -0.050 | -0.100 | -0.014 | 51.9% | N | -32.9% |  | 100.0% | 100.0% |
| grow_consistency | C (Moderate) | +0.102 | +0.113 | +0.123 | +0.006 | 47.4% | N | -8.3% | reduced_quantiles | 100.0% | 100.0% |
| tech_close_to_high_20d | C (Moderate) | +0.100 | +0.150 | +0.139 | +0.016 | 55.9% | N | -12.9% |  | 100.0% | 100.0% |

### D (Weak)
| factor | grade | rank_icir_5d | rank_icir_10d | rank_icir_20d | mean_rank_ic_5d | ic_hit_rate_5d | monotonic | ls_ann_return | warning_flags | obs_coverage_primary | rankic_coverage_primary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| qual_accruals | D (Weak) | +0.098 | +0.133 | +0.177 | +0.005 | 52.5% | N | +5.9% | low_obs,reduced_quantiles,constant_xs | 7.1% | 100.0% |
| grow_peg | D (Weak) | -0.090 | -0.104 | -0.124 | -0.005 | 51.7% | N | -5.3% | reduced_quantiles,constant_xs | 97.8% | 100.0% |
| north_hold_pct | D (Weak) | +0.085 | +0.101 | +0.109 | +0.012 | 49.7% | N | +133.8% | reduced_quantiles | 54.7% | 54.7% |
| comp_val_mom | D (Weak) | -0.082 | -0.081 | -0.058 | -0.012 | 53.7% | Y | -43.0% |  | 100.0% | 100.0% |
| grow_gross_margin_chg | D (Weak) | +0.082 | +0.073 | +0.083 | +0.002 | 53.7% | Y | -45.0% | reduced_quantiles | 44.1% | 44.1% |
| comp_qual_grow | D (Weak) | +0.079 | +0.086 | +0.095 | +0.009 | 50.5% | Y | +18.6% |  | 100.0% | 100.0% |
| comp_quality_growth | D (Weak) | +0.079 | +0.086 | +0.095 | +0.009 | 50.5% | Y | +18.6% |  | 100.0% | 100.0% |
| qual_asset_turnover | D (Weak) | +0.078 | +0.084 | +0.100 | +0.005 | 50.2% | N | +12.2% |  | 100.0% | 100.0% |
| comp_relative_strength | D (Weak) | +0.072 | +0.106 | +0.132 | +0.012 | 49.1% | N | -21.8% |  | 100.0% | 100.0% |
| margin_balance_pct | D (Weak) | -0.070 | -0.104 | -0.139 | -0.007 | 56.2% | N | -11.4% | reduced_quantiles | 100.0% | 100.0% |
| qual_net_margin | D (Weak) | +0.067 | +0.063 | +0.060 | +0.007 | 53.0% | N | -5.1% |  | 100.0% | 100.0% |
| qual_roe_change | D (Weak) | -0.067 | -0.099 | -0.058 | -0.002 | 46.4% | Y | -71.4% | reduced_quantiles | 44.0% | 44.0% |
| risk_mdd_proxy_60d | D (Weak) | -0.065 | -0.051 | -0.045 | -0.011 | 49.5% | Y | -56.8% |  | 100.0% | 100.0% |
| tech_kurt_20d | D (Weak) | -0.060 | -0.045 | -0.011 | -0.004 | 58.4% | N | -11.1% |  | 100.0% | 100.0% |
| qual_roic | D (Weak) | +0.055 | +0.051 | +0.050 | +0.006 | 51.8% | N | -7.8% |  | 100.0% | 100.0% |
| qual_roa | D (Weak) | +0.055 | +0.050 | +0.045 | +0.006 | 46.1% | N | -8.9% |  | 100.0% | 100.0% |
| qual_roe | D (Weak) | +0.052 | +0.050 | +0.049 | +0.006 | 51.0% | N | -8.1% |  | 100.0% | 100.0% |
| comp_anti_risk | D (Weak) | +0.048 | +0.050 | +0.056 | +0.006 | 52.9% | Y | +24.9% |  | 100.0% | 100.0% |
| lev_debt_capacity | D (Weak) | +0.047 | +0.050 | +0.053 | +0.006 | 53.0% | Y | +25.8% |  | 100.0% | 100.0% |
| lev_debt_to_assets | D (Weak) | -0.047 | -0.050 | -0.053 | -0.006 | 53.0% | Y | -25.8% |  | 100.0% | 100.0% |
| qual_leverage | D (Weak) | -0.047 | -0.050 | -0.053 | -0.006 | 53.0% | Y | -25.8% |  | 100.0% | 100.0% |
| lev_current_ratio | D (Weak) | +0.040 | +0.041 | +0.048 | +0.005 | 50.5% | Y | +22.4% |  | 100.0% | 100.0% |
| qual_current_ratio | D (Weak) | +0.040 | +0.041 | +0.048 | +0.005 | 50.5% | Y | +22.4% |  | 100.0% | 100.0% |
| size_ln_free_float | D (Weak) | -0.037 | -0.049 | -0.061 | -0.006 | 56.8% | Y | -58.8% |  | 100.0% | 100.0% |
| mom_skip1m_252d | D (Weak) | -0.037 | -0.051 | -0.064 | -0.005 | 50.9% | N | +5.0% |  | 100.0% | 100.0% |
| lev_quick_ratio | D (Weak) | +0.035 | +0.034 | +0.036 | +0.004 | 50.5% | Y | +18.9% |  | 100.0% | 100.0% |
| qual_quick_ratio | D (Weak) | +0.035 | +0.034 | +0.036 | +0.004 | 50.5% | Y | +18.9% |  | 100.0% | 100.0% |
| qual_gross_margin | D (Weak) | +0.034 | +0.042 | +0.047 | +0.003 | 52.0% | N | +10.2% |  | 100.0% | 100.0% |
| flow_small_net_pct_20d | D (Weak) | -0.014 | -0.051 | -0.063 | -0.001 | 63.5% | Y | -54.2% |  | 100.0% | 100.0% |
| earn_surprise_eps | D (Weak) | -0.014 | -0.018 | +0.035 | -0.000 | 50.4% | N | +55.4% | reduced_quantiles,constant_xs | 44.4% | 55.2% |
| lev_deleverage | D (Weak) | -0.013 | +0.017 | +0.047 | -0.000 | 51.7% | Y | -15.9% | reduced_quantiles | 44.2% | 44.2% |
| comp_momentum_reversal | D (Weak) | +0.005 | -0.080 | -0.089 | +0.001 | 51.2% | N | +2.9% |  | 100.0% | 100.0% |
| qual_roe_stability | D (Weak) | +0.004 | +0.001 | +0.017 | +0.000 | 48.4% | N | +7.1% | reduced_quantiles | 100.0% | 100.0% |
| rev_up_down_ratio_20d | D (Weak) |  |  |  |  |  |  |  | low_obs | 0.0% | 0.0% |

## Artifacts
- `E:\量化系统\workspace\research\alpha_mining\latest_backend_screening_20260401_new_data\factor_screening_results.parquet` - present, 49719 bytes
- `E:\量化系统\workspace\research\alpha_mining\latest_backend_screening_20260401_new_data\factor_screening_report.csv` - present, 74247 bytes
- `E:\量化系统\workspace\research\alpha_mining\latest_backend_screening_20260401_new_data\factor_screening_summary.txt` - present, 2427 bytes
- `E:\量化系统\workspace\research\alpha_mining\latest_backend_screening_20260401_new_data\factor_screening_run_metadata.json` - present, 804 bytes
- `E:\量化系统\workspace\research\alpha_mining\latest_backend_screening_20260401_new_data\run_console.log` - present, 18108 bytes
- `E:\量化系统\workspace\research\alpha_mining\latest_backend_screening_20260401_new_data\factor_screening_review_summary.md` - missing
