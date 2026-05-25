# Factor Card: tech_close_to_low_20d

## Basic Info
- Category: `Technical`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Ref(($close * $adj_factor), 1) / Min(Ref(($low * $adj_factor), 1), 20) - 1`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.407`
- 10d Rank ICIR: `-0.426`
- 20d Rank ICIR: `-0.482`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.641 | -0.671 | -0.799 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.654 | -0.649 | -0.771 | -1 | -1 | True | True | True |  |
| fold_03_2023 | -0.622 | -0.785 | -0.696 | -1 | -1 | True | True | True |  |
| fold_04_2024 | -0.597 | -0.730 | -0.472 | -1 | -1 | True | True | True |  |
| fold_05_2025 | -0.658 | -0.557 | -1.015 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.053 | -0.407 | 59.91% | 2,948 |
| size_neutral | -0.057 | -0.462 | 61.30% | 2,948 |
| industry_neutral | -0.052 | -0.590 | 65.16% | 2,948 |
| size_industry_neutral | -0.054 | -0.667 | 66.42% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.063 | -0.742 | 67.76% | 245 |
| 2015.000 | -0.069 | -0.691 | 65.16% | 244 |
| 2016.000 | -0.079 | -0.888 | 73.36% | 244 |
| 2017.000 | -0.041 | -0.464 | 63.11% | 244 |
| 2018.000 | -0.037 | -0.457 | 65.84% | 243 |
| 2019.000 | -0.065 | -0.827 | 70.49% | 244 |
| 2020.000 | -0.040 | -0.526 | 55.97% | 243 |
| 2021.000 | -0.053 | -0.799 | 61.32% | 243 |
| 2022.000 | -0.047 | -0.771 | 72.31% | 242 |
| 2023.000 | -0.049 | -0.696 | 70.66% | 242 |
| 2024.000 | -0.047 | -0.472 | 71.07% | 242 |
| 2025.000 | -0.065 | -1.015 | 62.14% | 243 |
| 2026.000 | -0.033 | -0.571 | 48.28% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.063 | -0.985 |
| -0.064 | -0.985 |
| -0.064 | -0.990 |
| -0.064 | -0.994 |
| -0.064 | -0.987 |
| -0.064 | -0.984 |
| -0.063 | -0.971 |
| -0.063 | -0.965 |
| -0.063 | -0.963 |
| -0.062 | -0.955 |
| -0.062 | -0.954 |
| -0.062 | -0.946 |
| -0.062 | -0.936 |
| -0.061 | -0.933 |
| -0.061 | -0.930 |
| -0.060 | -0.922 |
| -0.060 | -0.919 |
| -0.059 | -0.917 |
| -0.060 | -0.918 |
| -0.060 | -0.918 |
| -0.059 | -0.918 |
| -0.059 | -0.919 |
| -0.059 | -0.919 |
| -0.059 | -0.912 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.737`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.043 | -0.502 | 2,952 |
| 2.000 | -0.048 | -0.564 | 2,951 |
| 3.000 | -0.052 | -0.623 | 2,950 |
| 5.000 | -0.054 | -0.667 | 2,948 |
| 10.000 | -0.058 | -0.697 | 2,943 |
| 20.000 | -0.063 | -0.778 | 2,933 |
| 40.000 | -0.064 | -0.789 | 2,913 |
| 60.000 | -0.066 | -0.854 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-66.80%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-4.567`
- Monotonic: `False`
- Monotonic Spearman: `-0.700`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 1.065 | 0.701 | 1.518 | 2,948 |
| 2.000 | 0.005 | 1.156 | 0.684 | 1.690 | 2,948 |
| 3.000 | 0.004 | 1.114 | 0.674 | 1.654 | 2,948 |
| 4.000 | 0.004 | 1.025 | 0.677 | 1.513 | 2,948 |
| 5.000 | -0.000 | -0.008 | 0.720 | -0.011 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.630 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.579 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.550 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.556 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.544 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 6 | 0.016 | 0.347 |
| fold_02_2022 | 6 | 0.014 | 0.206 |
| fold_03_2023 | 4 | -0.004 | -0.057 |
| fold_04_2024 | 4 | -0.005 | -0.079 |
| fold_05_2025 | 7 | 0.000 | 0.003 |

## Risks
- Quantile monotonicity is weak in the 5d strategy-horizon diagnostic.

## Conclusion
- Final decision: `keep`
- Selected folds: `3`
- Validation-pass folds: `5`
- Summary: Repeatedly selected across OOS folds.
