# Factor Card: risk_range_ratio_20d

## Basic Info
- Category: `Volatility`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean(Ref(($high - $low) / $close, 1), 20)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.361`
- 10d Rank ICIR: `-0.424`
- 20d Rank ICIR: `-0.501`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.497 | -0.517 | -0.656 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.490 | -0.548 | -0.650 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.512 | -0.653 | -0.752 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.517 | -0.697 | -0.450 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.541 | -0.569 | -0.636 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.066 | -0.361 | 55.63% | 2,948 |
| size_neutral | -0.070 | -0.413 | 56.89% | 2,948 |
| industry_neutral | -0.061 | -0.481 | 58.62% | 2,948 |
| size_industry_neutral | -0.064 | -0.545 | 59.97% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.072 | -0.599 | 65.31% | 245 |
| 2015.000 | -0.050 | -0.371 | 61.07% | 244 |
| 2016.000 | -0.079 | -0.606 | 66.80% | 244 |
| 2017.000 | -0.060 | -0.516 | 62.70% | 244 |
| 2018.000 | -0.053 | -0.413 | 63.37% | 243 |
| 2019.000 | -0.062 | -0.580 | 60.66% | 244 |
| 2020.000 | -0.055 | -0.462 | 50.62% | 243 |
| 2021.000 | -0.065 | -0.656 | 57.61% | 243 |
| 2022.000 | -0.068 | -0.650 | 59.92% | 242 |
| 2023.000 | -0.070 | -0.752 | 58.68% | 242 |
| 2024.000 | -0.058 | -0.450 | 61.57% | 242 |
| 2025.000 | -0.070 | -0.636 | 52.26% | 243 |
| 2026.000 | -0.064 | -0.833 | 51.72% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.069 | -0.634 |
| -0.069 | -0.633 |
| -0.069 | -0.636 |
| -0.070 | -0.642 |
| -0.070 | -0.646 |
| -0.071 | -0.653 |
| -0.071 | -0.659 |
| -0.072 | -0.671 |
| -0.073 | -0.679 |
| -0.073 | -0.685 |
| -0.074 | -0.693 |
| -0.075 | -0.705 |
| -0.075 | -0.703 |
| -0.074 | -0.700 |
| -0.074 | -0.695 |
| -0.073 | -0.687 |
| -0.072 | -0.687 |
| -0.072 | -0.686 |
| -0.072 | -0.685 |
| -0.073 | -0.691 |
| -0.073 | -0.703 |
| -0.074 | -0.721 |
| -0.075 | -0.742 |
| -0.076 | -0.753 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.818`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.044 | -0.377 | 2,952 |
| 2.000 | -0.051 | -0.435 | 2,951 |
| 3.000 | -0.056 | -0.477 | 2,950 |
| 5.000 | -0.064 | -0.545 | 2,948 |
| 10.000 | -0.074 | -0.643 | 2,943 |
| 20.000 | -0.087 | -0.752 | 2,933 |
| 40.000 | -0.102 | -0.958 | 2,913 |
| 60.000 | -0.112 | -1.170 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-60.55%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-2.864`
- Monotonic: `False`
- Monotonic Spearman: `-0.700`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 1.065 | 0.620 | 1.718 | 2,948 |
| 2.000 | 0.005 | 1.155 | 0.658 | 1.755 | 2,948 |
| 3.000 | 0.004 | 1.071 | 0.682 | 1.571 | 2,948 |
| 4.000 | 0.003 | 0.877 | 0.712 | 1.231 | 2,948 |
| 5.000 | 0.001 | 0.184 | 0.785 | 0.235 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.716 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.725 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.723 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.733 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.713 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 10 | 0.000 | 0.004 |
| fold_02_2022 | 8 | -0.014 | -0.208 |
| fold_03_2023 | 7 | -0.019 | -0.261 |
| fold_04_2024 | 7 | -0.023 | -0.318 |
| fold_05_2025 | 6 | -0.012 | -0.160 |

## Risks
- Quantile monotonicity is weak in the 5d strategy-horizon diagnostic.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
