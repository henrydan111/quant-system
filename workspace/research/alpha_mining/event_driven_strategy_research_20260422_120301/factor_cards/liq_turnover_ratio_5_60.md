# Factor Card: liq_turnover_ratio_5_60

## Basic Info
- Category: `Liquidity`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean(Ref($turnover_rate, 1), 5) / Mean(Ref($turnover_rate, 1), 60)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.377`
- 10d Rank ICIR: `-0.410`
- 20d Rank ICIR: `-0.443`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.544 | -0.533 | -0.511 | -1 | -1 | True | True | True |  |
| fold_02_2022 | -0.638 | -0.371 | -0.774 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.544 | -0.629 | -0.342 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.521 | -0.522 | -0.657 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.599 | -0.492 | -0.838 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.040 | -0.377 | 64.86% | 2,948 |
| size_neutral | -0.041 | -0.428 | 66.35% | 2,948 |
| industry_neutral | -0.037 | -0.501 | 68.76% | 2,948 |
| size_industry_neutral | -0.038 | -0.562 | 70.52% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.026 | -0.370 | 65.71% | 245 |
| 2015.000 | -0.058 | -0.701 | 77.05% | 244 |
| 2016.000 | -0.045 | -0.623 | 72.13% | 244 |
| 2017.000 | -0.030 | -0.389 | 70.08% | 244 |
| 2018.000 | -0.040 | -0.716 | 79.84% | 243 |
| 2019.000 | -0.053 | -0.902 | 81.97% | 244 |
| 2020.000 | -0.018 | -0.258 | 61.32% | 243 |
| 2021.000 | -0.030 | -0.511 | 63.79% | 243 |
| 2022.000 | -0.039 | -0.774 | 76.86% | 242 |
| 2023.000 | -0.022 | -0.342 | 64.88% | 242 |
| 2024.000 | -0.041 | -0.657 | 70.25% | 242 |
| 2025.000 | -0.053 | -0.838 | 65.84% | 243 |
| 2026.000 | -0.020 | -0.346 | 41.38% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.053 | -0.834 |
| -0.053 | -0.834 |
| -0.053 | -0.837 |
| -0.053 | -0.842 |
| -0.053 | -0.838 |
| -0.053 | -0.830 |
| -0.052 | -0.821 |
| -0.051 | -0.813 |
| -0.050 | -0.800 |
| -0.049 | -0.777 |
| -0.049 | -0.763 |
| -0.048 | -0.758 |
| -0.048 | -0.762 |
| -0.049 | -0.777 |
| -0.049 | -0.786 |
| -0.049 | -0.789 |
| -0.049 | -0.786 |
| -0.049 | -0.778 |
| -0.048 | -0.770 |
| -0.047 | -0.770 |
| -0.047 | -0.770 |
| -0.046 | -0.770 |
| -0.046 | -0.770 |
| -0.046 | -0.768 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.653`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.031 | -0.460 | 2,952 |
| 2.000 | -0.034 | -0.510 | 2,951 |
| 3.000 | -0.036 | -0.542 | 2,950 |
| 5.000 | -0.038 | -0.562 | 2,948 |
| 10.000 | -0.041 | -0.620 | 2,943 |
| 20.000 | -0.042 | -0.651 | 2,933 |
| 40.000 | -0.039 | -0.633 | 2,913 |
| 60.000 | -0.035 | -0.576 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-58.68%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-4.622`
- Monotonic: `False`
- Monotonic Spearman: `-0.700`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 1.053 | 0.703 | 1.498 | 2,948 |
| 2.000 | 0.004 | 1.068 | 0.683 | 1.563 | 2,948 |
| 3.000 | 0.004 | 1.055 | 0.671 | 1.572 | 2,948 |
| 4.000 | 0.004 | 0.988 | 0.673 | 1.468 | 2,948 |
| 5.000 | 0.001 | 0.188 | 0.712 | 0.264 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.437 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.977 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.979 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.979 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.436 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 9 | 0.008 | 0.171 |
| fold_02_2022 | 10 | -0.004 | -0.077 |
| fold_03_2023 | 8 | -0.007 | -0.126 |
| fold_04_2024 | 10 | -0.009 | -0.147 |
| fold_05_2025 | 10 | -0.005 | -0.130 |

## Risks
- Quantile monotonicity is weak in the 5d strategy-horizon diagnostic.

## Conclusion
- Final decision: `reserve`
- Selected folds: `1`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
