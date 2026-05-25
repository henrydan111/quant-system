# ML Factor Combination Review

## Executive Summary
- Best ML variant: `LightGBM direct-scoring model`
- Best ML stitched relative excess vs `000001.SH`: `16.01%`
- Best ML vs same-execution rule baseline: `False`
- Adoption recommendation: `reject`

## Variant Comparison
| rank | display_name | stitched_relative_excess_return | stitched_total_return | stitched_benchmark_total_return | positive_excess_folds | holdout_relative_excess_return | worst_max_drawdown | avg_turnover | avg_blocked_order_ratio | beats_benchmark | beats_rule_baseline | adoption_recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Rule baseline (C_stability_score, conservative 10d rerun) | 0.191 | 0.895 | 0.591 | 5 | 0.021 | -0.324 | 0.164 | 0.035 | True | False | reference_only |
| 2 | LightGBM direct-scoring model | 0.160 | 0.757 | 0.514 | 5 | -0.006 | -0.340 | 0.175 | 0.034 | True | False | reject |
| 3 | ElasticNet factor-weight model | 0.135 | 0.719 | 0.514 | 4 | -0.013 | -0.364 | 0.129 | 0.079 | True | False | reject |

## Same-Execution Rule Baseline
| stage | variant_id | description | benchmark | selection_mode | portfolio_weighting | universe_mode | topk | rebalance_days | slow_rebalance_days | liquidity_scenario | slippage_rate | stitched_total_return | stitched_benchmark_total_return | stitched_relative_excess_return | positive_excess_folds | test_fold_count | holdout_relative_excess_return | worst_max_drawdown | avg_turnover | avg_blocked_order_ratio | avg_holding_cash_ratio | promoted | gate_reason | display_name | model_kind | beats_benchmark | beats_rule_baseline | adoption_recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RULE | rule_baseline | Current best rule logic (C_stability_score) rerun with the same conservative 10-day execution settings as ML. | 000001.SH | stability_score | equal | all_market | 50 | 10 | 10 | adv_floor_plus_participation | 0.05% | 0.895 | 0.591 | 0.191 | 5 | 7 | 0.021 | -0.324 | 0.164 | 0.035 | 0.016 | False | worst-fold max drawdown < -30% | Rule baseline (C_stability_score, conservative 10d rerun) | rule | True | False | reference_only |

## ElasticNet Factor Highlights
| factor | avg_abs_weight_share | avg_coefficient | fold_count |
| --- | --- | --- | --- |
| liq_turnover_f_5d | 0.363 | 0.002 | 8 |
| mom_intraday_20d | 0.081 | 0.001 | 8 |
| liq_vol_cv_20d | 0.044 | 0.001 | 8 |
| liq_log_dollar_vol | 0.031 | 0.001 | 8 |
| tech_close_to_low_20d | 0.028 | -0.001 | 8 |
| tech_price_to_ma60 | 0.024 | 0.001 | 8 |
| liq_vol_ratio_ma5 | 0.022 | 0.001 | 8 |
| tech_rsi_28 | 0.020 | -0.001 | 8 |
| liq_amihud_20d | 0.018 | 0.000 | 8 |
| tech_price_to_ma20 | 0.018 | 0.001 | 8 |

## LightGBM Factor Highlights
| factor | avg_gain_share | avg_split_share | fold_count |
| --- | --- | --- | --- |
| north_hold_change_5d | 0.166 | 0.068 | 8 |
| liq_turnover_f_5d | 0.155 | 0.039 | 8 |
| grow_rev_trend | 0.079 | 0.086 | 8 |
| mom_ewm_20d | 0.060 | 0.035 | 8 |
| mom_intraday_20d | 0.051 | 0.049 | 8 |
| grow_profit_trend | 0.046 | 0.067 | 8 |
| flow_net_inflow_20d | 0.040 | 0.051 | 8 |
| liq_amihud_20d | 0.035 | 0.036 | 8 |
| liq_turnover_5d | 0.025 | 0.016 | 8 |
| tech_close_to_low_20d | 0.021 | 0.029 | 8 |

## Weakest Folds For Best ML Variant
| fold_id | cumulative_return | benchmark_total_return | relative_excess_return | max_drawdown | turnover_mean | blocked_order_ratio | window_start | window_end |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_02_2020 | -3.86% | 10.78% | -0.132 | -17.58% | 16.25% | 5.26% | 2020-01-02 | 2020-12-29 |
| fold_06_2024 | 2.03% | 14.53% | -0.109 | -33.97% | 18.36% | 1.91% | 2024-01-02 | 2024-12-30 |
| fold_03_2021 | 5.69% | 3.57% | 0.020 | -13.75% | 17.55% | 3.46% | 2021-01-04 | 2021-12-29 |
| fold_05_2023 | -2.29% | -4.36% | 0.022 | -18.44% | 18.12% | 2.27% | 2023-01-03 | 2023-12-28 |
| fold_01_2019 | 26.18% | 20.59% | 0.046 | -26.41% | 18.46% | 2.18% | 2019-01-02 | 2019-12-26 |

## Fold-Level Model Notes
| variant_id | fold_id | window_type | split | alpha | l1_ratio | best_iteration | validation_relative_excess_return | validation_prediction_rank_icir | test_relative_excess_return | test_prediction_rank_icir |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| elasticnet | fold_01_2019 | test | test | 0.002 | 0.800 |  | -0.059 | 0.975 | 0.141 | 1.204 |
| elasticnet | fold_02_2020 | test | test | 0.001 | 0.500 |  | 0.414 | 1.553 | -0.072 | 1.226 |
| elasticnet | fold_03_2021 | test | test | 0.002 | 0.500 |  | 0.146 | 1.071 | 0.006 | 1.783 |
| elasticnet | fold_04_2022 | test | test | 0.001 | 0.200 |  | 0.223 | 1.133 | -0.137 | 1.215 |
| elasticnet | fold_05_2023 | test | test | 0.010 | 0.500 |  | 0.100 | 1.331 | 0.144 | 0.981 |
| elasticnet | fold_06_2024 | test | test | 0.010 | 0.500 |  | 0.318 | 0.985 | -0.032 | 0.776 |
| elasticnet | fold_07_2025 | test | test | 0.010 | 0.800 |  | 0.290 |  | 0.115 |  |
| elasticnet | holdout | holdout | holdout | 0.010 | 0.800 |  | 0.331 |  | -0.013 |  |
| lightgbm | fold_01_2019 | test | validation |  |  | 7.000 | -0.430 | 0.757 |  |  |
| lightgbm | fold_01_2019 | test | test |  |  | 7.000 |  |  | 0.046 | 1.159 |
| lightgbm | fold_02_2020 | test | validation |  |  | 82.000 | 0.079 | 1.456 |  |  |
| lightgbm | fold_02_2020 | test | test |  |  | 82.000 |  |  | -0.132 | 1.306 |
| lightgbm | fold_03_2021 | test | validation |  |  | 1.000 | -0.203 | 0.741 |  |  |
| lightgbm | fold_03_2021 | test | test |  |  | 1.000 |  |  | 0.020 | 0.476 |
| lightgbm | fold_04_2022 | test | validation |  |  | 13.000 | 0.038 | 0.883 |  |  |
| lightgbm | fold_04_2022 | test | test |  |  | 13.000 |  |  | 0.266 | 1.222 |
| lightgbm | fold_05_2023 | test | validation |  |  | 48.000 | 0.046 | 1.034 |  |  |
| lightgbm | fold_05_2023 | test | test |  |  | 48.000 |  |  | 0.022 | 0.783 |
| lightgbm | fold_06_2024 | test | validation |  |  | 8.000 | 0.095 | 0.885 |  |  |
| lightgbm | fold_06_2024 | test | test |  |  | 8.000 |  |  | -0.109 | 1.024 |
| lightgbm | fold_07_2025 | test | validation |  |  | 3.000 | 0.208 | 0.740 |  |  |
| lightgbm | fold_07_2025 | test | test |  |  | 3.000 |  |  | 0.086 | 1.224 |
| lightgbm | holdout | holdout | validation |  |  | 73.000 | 0.596 | 0.973 |  |  |
| lightgbm | holdout | holdout | holdout |  |  | 73.000 |  |  | -0.006 | 2.196 |

## Interpretation
- Rule baseline is the current best non-ML selection logic (`C_stability_score`) rerun under the same conservative 10-day execution settings.
- ElasticNet exposes direct factor weights, so it is easier to explain when we want to see which factors the model is leaning on.
- LightGBM does not give a single clean weight vector, so we review it through feature importance instead.
- Turnover and blocked-order ratio are kept as execution diagnostics, not as hard promotion gates.
