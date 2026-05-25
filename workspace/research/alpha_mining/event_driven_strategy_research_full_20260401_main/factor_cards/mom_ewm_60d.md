# Factor Card: mom_ewm_60d

## Basic Info
- Category: `Momentum`
- Signal direction in strategy: `low_is_good`
- Raw expression: `EMA((($close * $adj_factor) / Ref(($close * $adj_factor), 1) - 1), 60)`

## Screening Snapshot
- Grade: `A (Graduated)`
- 5d Rank ICIR: `-0.461`
- 10d Rank ICIR: `-0.506`
- 20d Rank ICIR: `-0.552`
- Monotonic: `True`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.760 | -0.429 | -0.764 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.713 | -0.601 | -0.427 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.690 | -0.588 | -0.650 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.674 | -0.535 | -0.743 | -1 | -1 | True | True | False |  |
| fold_05_2023 | -0.562 | -0.693 | -0.455 | -1 | -1 | True | True | False |  |
| fold_06_2024 | -0.527 | -0.592 | -0.475 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.597 | -0.450 | -1.059 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.073 | -0.461 | 59.52% | 3,429 |
| size_neutral | -0.072 | -0.503 | 59.90% | 3,429 |
| industry_neutral | -0.069 | -0.561 | 62.90% | 3,429 |
| size_industry_neutral | -0.068 | -0.630 | 62.99% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.082 | -0.603 | 74.07% | 243 |
| 2013.000 | -0.068 | -0.571 | 57.14% | 238 |
| 2014.000 | -0.080 | -0.875 | 62.04% | 245 |
| 2015.000 | -0.106 | -1.064 | 49.18% | 244 |
| 2016.000 | -0.087 | -0.843 | 71.72% | 244 |
| 2017.000 | -0.046 | -0.388 | 62.70% | 244 |
| 2018.000 | -0.055 | -0.471 | 61.32% | 243 |
| 2019.000 | -0.075 | -0.764 | 67.62% | 244 |
| 2020.000 | -0.042 | -0.427 | 55.97% | 243 |
| 2021.000 | -0.064 | -0.650 | 58.85% | 243 |
| 2022.000 | -0.064 | -0.743 | 71.07% | 242 |
| 2023.000 | -0.040 | -0.455 | 61.16% | 242 |
| 2024.000 | -0.071 | -0.475 | 68.18% | 242 |
| 2025.000 | -0.079 | -1.059 | 61.73% | 243 |
| 2026.000 | -0.033 | -0.627 | 55.17% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.079 | -1.053 |
| -0.078 | -1.052 |
| -0.078 | -1.052 |
| -0.078 | -1.053 |
| -0.078 | -1.049 |
| -0.078 | -1.047 |
| -0.078 | -1.032 |
| -0.077 | -1.025 |
| -0.077 | -1.020 |
| -0.077 | -1.015 |
| -0.076 | -1.008 |
| -0.076 | -1.002 |
| -0.076 | -1.009 |
| -0.076 | -1.012 |
| -0.076 | -1.011 |
| -0.076 | -1.005 |
| -0.076 | -1.008 |
| -0.076 | -1.010 |
| -0.075 | -1.011 |
| -0.075 | -1.014 |
| -0.074 | -1.016 |
| -0.073 | -1.012 |
| -0.073 | -1.003 |
| -0.072 | -0.988 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.521`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.047 | -0.428 | 3,433 |
| 2.000 | -0.054 | -0.490 | 3,432 |
| 3.000 | -0.060 | -0.544 | 3,431 |
| 5.000 | -0.068 | -0.630 | 3,429 |
| 10.000 | -0.073 | -0.687 | 3,424 |
| 20.000 | -0.077 | -0.746 | 3,414 |
| 40.000 | -0.070 | -0.729 | 3,394 |
| 60.000 | -0.064 | -0.717 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `0.00%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-4.761`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.343 | 0.737 | 1.823 | 3,429 |
| 2.000 | 0.005 | 1.258 | 0.673 | 1.868 | 3,429 |
| 3.000 | 0.004 | 1.041 | 0.641 | 1.623 | 3,429 |
| 4.000 | 0.003 | 0.779 | 0.632 | 1.232 | 3,429 |
| 5.000 | -0.000 | -0.055 | 0.683 | -0.081 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.682 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.652 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.662 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.696 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.695 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.691 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.683 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.005 | 0.062 |
| fold_02_2020 | 8 | -0.008 | -0.087 |
| fold_03_2021 | 10 | -0.005 | -0.064 |
| fold_04_2022 | 7 | -0.015 | -0.180 |
| fold_05_2023 | 8 | -0.011 | -0.150 |
| fold_06_2024 | 10 | -0.000 | -0.001 |
| fold_07_2025 | 10 | -0.000 | -0.001 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
