# ML Factor Combination Review

## Executive Summary
- Best ML variant: `ElasticNet factor-weight model`
- Best ML stitched relative excess vs `000001.SH`: `42.63%`
- Best ML vs same-execution rule baseline: `False`
- Adoption recommendation: `reject`

## Variant Comparison
| rank | display_name | stitched_relative_excess_return | stitched_total_return | stitched_benchmark_total_return | positive_excess_folds | holdout_relative_excess_return | worst_max_drawdown | avg_turnover | avg_blocked_order_ratio | beats_benchmark | beats_rule_baseline | adoption_recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Rule baseline (C_stability_score, conservative 10d rerun) | 0.949 | 1.227 | 0.143 | 4 | 0.042 | -0.344 | 0.134 | 0.064 | True | False | reference_only |
| 2 | ElasticNet factor-weight model | 0.426 | 0.617 | 0.133 | 4 | -0.013 | -0.349 | 0.123 | 0.082 | True | False | reject |
| 3 | LightGBM direct-scoring model | -0.140 | -0.026 | 0.133 | 2 | 0.038 | -0.460 | 0.175 | 0.031 | False | False | reject |

## Same-Execution Rule Baseline
| stage | variant_id | description | benchmark | selection_mode | portfolio_weighting | universe_mode | topk | rebalance_days | slow_rebalance_days | liquidity_scenario | slippage_rate | stitched_total_return | stitched_benchmark_total_return | stitched_relative_excess_return | positive_excess_folds | test_fold_count | holdout_relative_excess_return | worst_max_drawdown | avg_turnover | avg_blocked_order_ratio | avg_holding_cash_ratio | promoted | gate_reason | display_name | model_kind | beats_benchmark | beats_rule_baseline | adoption_recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RULE | rule_baseline | Current best rule logic (C_stability_score) rerun with the same conservative 10-day execution settings as ML. | 000001.SH | stability_score | equal | all_market | 50 | 10 | 10 | adv_floor_plus_participation | 0.05% | 1.227 | 0.143 | 0.949 | 4 | 5 | 0.042 | -0.344 | 0.134 | 0.064 | 0.013 | False | positive-excess test folds < 5; worst-fold max drawdown < -30% | Rule baseline (C_stability_score, conservative 10d rerun) | rule | True | False | reference_only |

## ElasticNet Factor Highlights
| factor | avg_abs_weight_share | avg_coefficient | fold_count |
| --- | --- | --- | --- |
| liq_turnover_f_5d | 0.439 | 0.001 | 6 |
| mom_intraday_20d | 0.048 | 0.001 | 6 |
| liq_turnover_5d | 0.040 | 0.000 | 6 |
| tech_close_to_low_20d | 0.014 | -0.000 | 6 |
| tech_rsi_28 | 0.013 | -0.000 | 6 |
| liq_vol_cv_20d | 0.012 | 0.000 | 6 |
| mom_return_10d | 0.011 | 0.000 | 6 |
| comp_size_quality | 0.011 | 0.000 | 6 |
| mom_high_moment_20d | 0.010 | -0.000 | 6 |
| mom_ewm_20d | 0.009 | 0.000 | 6 |

## LightGBM Factor Highlights
| factor | avg_gain_share | avg_split_share | fold_count |
| --- | --- | --- | --- |
| liq_turnover_f_5d | 0.228 | 0.052 | 6 |
| flow_net_inflow_20d | 0.080 | 0.089 | 6 |
| north_hold_change_5d | 0.077 | 0.030 | 6 |
| mom_intraday_20d | 0.076 | 0.045 | 6 |
| mom_ewm_20d | 0.064 | 0.049 | 6 |
| tech_price_to_ma20 | 0.047 | 0.050 | 6 |
| tech_close_to_low_20d | 0.033 | 0.045 | 6 |
| comp_small_value | 0.033 | 0.052 | 6 |
| comp_rev_low_turn | 0.032 | 0.037 | 6 |
| tech_rsi_28 | 0.025 | 0.033 | 6 |

## Weakest Folds For Best ML Variant
| fold_id | cumulative_return | benchmark_total_return | relative_excess_return | max_drawdown | turnover_mean | blocked_order_ratio | window_start | window_end |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_04_2024 | 3.84% | 14.53% | -0.093 | -34.94% | 14.95% | 5.60% | 2024-01-02 | 2024-12-30 |
| fold_02_2022 | -14.80% | -15.55% | 0.009 | -28.55% | 14.13% | 6.80% | 2022-01-04 | 2022-12-29 |
| fold_05_2025 | 31.53% | 18.30% | 0.112 | -19.73% | 4.30% | 17.05% | 2025-01-02 | 2025-12-29 |
| fold_01_2021 | 22.49% | 3.57% | 0.183 | -11.46% | 13.00% | 6.49% | 2021-01-04 | 2021-12-29 |
| fold_03_2023 | 13.42% | -4.36% | 0.186 | -16.91% | 15.29% | 4.82% | 2023-01-03 | 2023-12-28 |

## Fold-Level Model Notes
| variant_id | fold_id | window_type | split | alpha | l1_ratio | best_iteration | validation_relative_excess_return | validation_prediction_rank_icir | test_relative_excess_return | test_prediction_rank_icir |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| elasticnet | fold_01_2021 | test | test | 0.010 | 0.500 |  | 0.256 | 0.954 | 0.183 | 1.645 |
| elasticnet | fold_02_2022 | test | test | 0.010 | 0.500 |  | 0.239 | 0.959 | 0.009 | 0.904 |
| elasticnet | fold_03_2023 | test | test | 0.001 | 0.200 |  | 0.147 | 1.436 | 0.186 | 1.133 |
| elasticnet | fold_04_2024 | test | test | 0.002 | 0.800 |  | 0.329 | 1.027 | -0.093 | 0.912 |
| elasticnet | fold_05_2025 | test | test | 0.010 | 0.800 |  | 0.259 |  | 0.112 |  |
| elasticnet | holdout | holdout | holdout | 0.010 | 0.800 |  | 0.326 |  | -0.013 |  |
| lightgbm | fold_01_2021 | test | validation |  |  | 1.000 | 0.090 | 0.941 |  |  |
| lightgbm | fold_01_2021 | test | test |  |  | 1.000 |  |  | 0.163 | 1.679 |
| lightgbm | fold_02_2022 | test | validation |  |  | 1.000 | 0.134 | 0.899 |  |  |
| lightgbm | fold_02_2022 | test | test |  |  | 1.000 |  |  | -0.090 | 1.414 |
| lightgbm | fold_03_2023 | test | validation |  |  | 45.000 | 0.165 | 1.229 |  |  |
| lightgbm | fold_03_2023 | test | test |  |  | 45.000 |  |  | 0.180 | 0.867 |
| lightgbm | fold_04_2024 | test | validation |  |  | 30.000 | 0.326 | 1.049 |  |  |
| lightgbm | fold_04_2024 | test | test |  |  | 30.000 |  |  | -0.289 | 0.934 |
| lightgbm | fold_05_2025 | test | validation |  |  | 1.000 | -0.137 | 0.864 |  |  |
| lightgbm | fold_05_2025 | test | test |  |  | 1.000 |  |  | -0.032 | 1.006 |
| lightgbm | holdout | holdout | validation |  |  | 45.000 | 0.028 | 1.011 |  |  |
| lightgbm | holdout | holdout | holdout |  |  | 45.000 |  |  | 0.038 | 1.121 |

## Interpretation
- Rule baseline is the current best non-ML selection logic (`C_stability_score`) rerun under the same conservative 10-day execution settings.
- ElasticNet exposes direct factor weights, so it is easier to explain when we want to see which factors the model is leaning on.
- LightGBM does not give a single clean weight vector, so we review it through feature importance instead.
- Turnover and blocked-order ratio are kept as execution diagnostics, not as hard promotion gates.
