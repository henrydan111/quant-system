# Factor Card: flow_net_inflow_20d

## Basic Info
- Category: `Capital Flow`
- Signal direction in strategy: `high_is_good`
- Raw expression: `Mean(Ref($net_mf_amount, 1), 20)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `0.378`
- 10d Rank ICIR: `0.501`
- 20d Rank ICIR: `0.593`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | 0.187 | 0.355 | 0.160 | 1 | 1 | True | True | False |  |
| fold_02_2022 | 0.223 | 0.273 | 0.334 | 1 | 1 | True | True | False |  |
| fold_03_2023 | 0.303 | 0.244 | 0.570 | 1 | 1 | True | True | False |  |
| fold_04_2024 | 0.306 | 0.448 | 0.442 | 1 | 1 | True | True | False |  |
| fold_05_2025 | 0.304 | 0.471 | 0.536 | 1 | 1 | True | True | True |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | 0.035 | 0.378 | 65.43% | 2,948 |
| size_neutral | 0.027 | 0.265 | 63.13% | 2,948 |
| industry_neutral | 0.026 | 0.414 | 66.28% | 2,948 |
| size_industry_neutral | 0.020 | 0.290 | 63.06% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | 0.011 | 0.165 | 60.41% | 245 |
| 2015.000 | -0.008 | -0.143 | 55.74% | 244 |
| 2016.000 | 0.013 | 0.172 | 61.07% | 244 |
| 2017.000 | 0.025 | 0.313 | 59.43% | 244 |
| 2018.000 | 0.031 | 0.328 | 55.14% | 243 |
| 2019.000 | 0.028 | 0.345 | 62.30% | 244 |
| 2020.000 | 0.024 | 0.371 | 66.26% | 243 |
| 2021.000 | 0.008 | 0.160 | 60.49% | 243 |
| 2022.000 | 0.016 | 0.334 | 68.18% | 242 |
| 2023.000 | 0.027 | 0.570 | 67.36% | 242 |
| 2024.000 | 0.036 | 0.442 | 69.01% | 242 |
| 2025.000 | 0.030 | 0.536 | 70.37% | 243 |
| 2026.000 | 0.020 | 0.290 | 72.41% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| 0.031 | 0.550 |
| 0.031 | 0.550 |
| 0.031 | 0.550 |
| 0.031 | 0.552 |
| 0.031 | 0.556 |
| 0.032 | 0.560 |
| 0.032 | 0.565 |
| 0.032 | 0.575 |
| 0.033 | 0.589 |
| 0.034 | 0.604 |
| 0.034 | 0.613 |
| 0.034 | 0.623 |
| 0.034 | 0.613 |
| 0.033 | 0.600 |
| 0.032 | 0.580 |
| 0.032 | 0.572 |
| 0.031 | 0.563 |
| 0.031 | 0.557 |
| 0.031 | 0.563 |
| 0.032 | 0.575 |
| 0.032 | 0.589 |
| 0.032 | 0.608 |
| 0.033 | 0.632 |
| 0.033 | 0.645 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.787`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | 0.006 | 0.093 | 2,952 |
| 2.000 | 0.011 | 0.165 | 2,951 |
| 3.000 | 0.014 | 0.206 | 2,950 |
| 5.000 | 0.020 | 0.290 | 2,948 |
| 10.000 | 0.028 | 0.412 | 2,943 |
| 20.000 | 0.035 | 0.540 | 2,933 |
| 40.000 | 0.042 | 0.677 | 2,913 |
| 60.000 | 0.048 | 0.822 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `68.86%`
- Long-short total diagnostic return: `45772.71%`
- Long-short Sharpe: `3.168`
- Monotonic: `False`
- Monotonic Spearman: `0.300`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.000 | 0.107 | 0.705 | 0.152 | 2,948 |
| 2.000 | 0.004 | 1.052 | 0.707 | 1.488 | 2,948 |
| 3.000 | 0.005 | 1.268 | 0.701 | 1.809 | 2,948 |
| 4.000 | 0.005 | 1.188 | 0.692 | 1.715 | 2,948 |
| 5.000 | 0.003 | 0.646 | 0.636 | 1.017 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.330 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.239 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.232 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.457 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.304 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 10 | 0.011 | 0.261 |
| fold_02_2022 | 10 | 0.002 | 0.061 |
| fold_03_2023 | 10 | 0.002 | 0.070 |
| fold_04_2024 | 10 | 0.013 | 0.344 |
| fold_05_2025 | 9 | 0.008 | 0.163 |

## Risks
- Quantile monotonicity is weak in the 5d strategy-horizon diagnostic.

## Conclusion
- Final decision: `reserve`
- Selected folds: `1`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
