# Factor Card: rev_return_10d

## Basic Info
- Category: `Reversal`
- Signal direction in strategy: `high_is_good`
- Raw expression: `0 - (Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 11) - 1)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `0.301`
- 10d Rank ICIR: `0.302`
- 20d Rank ICIR: `0.370`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | 0.499 | 0.498 | 0.488 | 1 | 1 | True | True | False |  |
| fold_02_2022 | 0.528 | 0.401 | 0.493 | 1 | 1 | True | True | False |  |
| fold_03_2023 | 0.434 | 0.491 | 0.432 | 1 | 1 | True | True | False |  |
| fold_04_2024 | 0.405 | 0.460 | 0.256 | 1 | 1 | True | True | False |  |
| fold_05_2025 | 0.455 | 0.313 | 0.820 | 1 | 1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | 0.042 | 0.301 | 59.91% | 2,948 |
| size_neutral | 0.044 | 0.355 | 61.50% | 2,948 |
| industry_neutral | 0.043 | 0.398 | 64.18% | 2,948 |
| size_industry_neutral | 0.044 | 0.471 | 65.77% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | 0.043 | 0.503 | 63.27% | 245 |
| 2015.000 | 0.092 | 0.815 | 71.72% | 244 |
| 2016.000 | 0.064 | 0.595 | 66.80% | 244 |
| 2017.000 | 0.025 | 0.254 | 59.84% | 244 |
| 2018.000 | 0.037 | 0.356 | 65.02% | 243 |
| 2019.000 | 0.057 | 0.680 | 72.54% | 244 |
| 2020.000 | 0.027 | 0.327 | 57.61% | 243 |
| 2021.000 | 0.035 | 0.488 | 60.91% | 243 |
| 2022.000 | 0.034 | 0.493 | 71.49% | 242 |
| 2023.000 | 0.034 | 0.432 | 73.97% | 242 |
| 2024.000 | 0.033 | 0.256 | 62.40% | 242 |
| 2025.000 | 0.054 | 0.820 | 66.26% | 243 |
| 2026.000 | 0.016 | 0.220 | 44.83% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| 0.053 | 0.796 |
| 0.054 | 0.807 |
| 0.054 | 0.808 |
| 0.054 | 0.808 |
| 0.053 | 0.799 |
| 0.053 | 0.789 |
| 0.052 | 0.777 |
| 0.051 | 0.772 |
| 0.050 | 0.762 |
| 0.049 | 0.732 |
| 0.048 | 0.721 |
| 0.047 | 0.709 |
| 0.047 | 0.707 |
| 0.047 | 0.701 |
| 0.047 | 0.699 |
| 0.046 | 0.693 |
| 0.046 | 0.688 |
| 0.046 | 0.685 |
| 0.046 | 0.688 |
| 0.046 | 0.689 |
| 0.045 | 0.685 |
| 0.045 | 0.685 |
| 0.045 | 0.685 |
| 0.045 | 0.683 |

## IC Decay
- Best horizon by |ICIR|: `20`
- Peak ICIR: `0.534`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | 0.036 | 0.372 | 2,952 |
| 2.000 | 0.040 | 0.410 | 2,951 |
| 3.000 | 0.043 | 0.443 | 2,950 |
| 5.000 | 0.044 | 0.471 | 2,948 |
| 10.000 | 0.046 | 0.504 | 2,943 |
| 20.000 | 0.051 | 0.585 | 2,933 |
| 40.000 | 0.045 | 0.558 | 2,913 |
| 60.000 | 0.040 | 0.511 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `220.56%`
- Long-short total diagnostic return: `82870043.75%`
- Long-short Sharpe: `4.534`
- Monotonic: `False`
- Monotonic Spearman: `0.700`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | -0.000 | -0.091 | 0.689 | -0.132 | 2,948 |
| 2.000 | 0.004 | 0.931 | 0.658 | 1.415 | 2,948 |
| 3.000 | 0.005 | 1.158 | 0.668 | 1.734 | 2,948 |
| 4.000 | 0.005 | 1.270 | 0.697 | 1.823 | 2,948 |
| 5.000 | 0.004 | 1.111 | 0.742 | 1.497 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.491 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.683 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.665 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.649 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.489 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 10 | 0.002 | 0.033 |
| fold_02_2022 | 9 | 0.005 | 0.095 |
| fold_03_2023 | 9 | 0.009 | 0.190 |
| fold_04_2024 | 10 | 0.017 | 0.351 |
| fold_05_2025 | 10 | 0.007 | 0.110 |

## Risks
- Quantile monotonicity is weak in the 5d strategy-horizon diagnostic.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
