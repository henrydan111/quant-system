# Strategy Improvement Master Review

## Benchmark Setup
- Formal benchmark is now `000001.SH`.
- Benchmark audit passed: `True`

## Baseline B0 vs New Benchmark
| stage | variant_id | description | benchmark | selection_mode | portfolio_weighting | universe_mode | topk | rebalance_days | slow_rebalance_days | liquidity_scenario | slippage_rate | stitched_total_return | stitched_benchmark_total_return | stitched_relative_excess_return | positive_excess_folds | test_fold_count | holdout_relative_excess_return | worst_max_drawdown | avg_turnover | avg_blocked_order_ratio | avg_holding_cash_ratio | promoted | gate_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 | B0_baseline_sse_benchmark | Frozen formal baseline, rerun against the SSE Composite benchmark. | 000001.SH | baseline | equal | all_market | 50 | 5 | 10 | adv_floor_plus_participation | 0.05% | 0.560 | 0.591 | -0.020 | 4 | 7 | 0.012 | -0.382 | 0.281 | 0.075 | 0.015 | False | stitched relative excess return < +10%; positive-excess test folds < 5; worst-fold max drawdown < -30% |

## Stage A: Parameter Sensitivity
| rank | variant_id | stitched_relative_excess_return | positive_excess_folds | holdout_relative_excess_return | worst_max_drawdown | avg_turnover | avg_blocked_order_ratio | promoted |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A_topk100_reb10_no_filter_slip0.0005 | 0.373 | 5 | 0.014 | -0.316 | 0.148 | 0.073 | False |
| 2 | A_topk50_reb10_no_filter_slip0.0005 | 0.329 | 5 | 0.016 | -0.326 | 0.160 | 0.038 | False |
| 3 | A_topk100_reb10_adv_floor_only_slip0.0005 | 0.323 | 5 | 0.014 | -0.316 | 0.148 | 0.073 | False |
| 4 | A_topk100_reb10_adv_floor_plus_participation_slip0.0005 | 0.323 | 5 | 0.014 | -0.316 | 0.148 | 0.073 | False |
| 5 | A_topk50_reb10_adv_floor_only_slip0.0005 | 0.269 | 5 | 0.016 | -0.326 | 0.160 | 0.037 | False |
| 6 | A_topk50_reb10_adv_floor_plus_participation_slip0.0005 | 0.269 | 5 | 0.016 | -0.326 | 0.160 | 0.037 | False |
| 7 | A_topk80_reb10_adv_floor_only_slip0.0005 | 0.238 | 5 | 0.017 | -0.311 | 0.152 | 0.060 | False |
| 8 | A_topk80_reb10_adv_floor_plus_participation_slip0.0005 | 0.238 | 5 | 0.017 | -0.311 | 0.152 | 0.060 | False |

## Stage B: Portfolio Expression
| rank | variant_id | portfolio_weighting | topk | stitched_relative_excess_return | holdout_relative_excess_return | worst_max_drawdown | promoted |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 49 | B_P1_equal_top50 | equal | 50 | 0.329 | 0.016 | -0.326 | False |
| 50 | B_P3_scoreprop_top80 | score_proportional | 80 | 0.297 | 0.021 | -0.330 | False |
| 51 | B_P2_tiered_top80 | tiered | 80 | 0.256 | 0.018 | -0.316 | False |

## Stage C: Selection / Tempo Upgrade
| rank | variant_id | selection_mode | stitched_relative_excess_return | positive_excess_folds | holdout_relative_excess_return | worst_max_drawdown | avg_turnover | avg_blocked_order_ratio | promoted | gate_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 52 | C_stability_fastslow | stability_score_fastslow | -0.003 | 5 | 0.025 | -0.341 | 0.169 | 0.045 | False | stitched relative excess return < +10%; worst-fold max drawdown < -30% |

## Best Variant
| variant_id | stage | selection_mode | portfolio_weighting | topk | rebalance_days | slow_rebalance_days | liquidity_scenario | slippage_rate | stitched_relative_excess_return | positive_excess_folds | holdout_relative_excess_return | worst_max_drawdown | avg_turnover | avg_blocked_order_ratio | promoted | gate_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C_stability_score | D | stability_score | equal | 50 | 10 | 10 | no_filter | 0.05% | 0.150 | 5 | 0.032 | -0.310 | 0.162 | 0.038 | False | worst-fold max drawdown < -30% |

## Interpretation
- Turnover and blocked-order ratio remain in the report because they matter for implementation style, but they are not promotion gates anymore.
- A candidate still needs to beat the SSE Composite on stitched OOS relative return, breadth across folds, holdout behavior, and worst-fold drawdown to count as a true upgrade.
