# Factor Card: risk_vol_5d

## Basic Info
- Category: `Volatility`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Std((Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 2) - 1), 5)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.391`
- 10d Rank ICIR: `-0.473`
- 20d Rank ICIR: `-0.538`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.464 | -0.706 | -0.857 | -1 | -1 | True | True | True |  |
| fold_02_2022 | -0.491 | -0.725 | -0.737 | -1 | -1 | True | True | True |  |
| fold_03_2023 | -0.579 | -0.789 | -0.730 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.602 | -0.732 | -0.508 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.653 | -0.580 | -0.943 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.055 | -0.391 | 59.40% | 2,948 |
| size_neutral | -0.058 | -0.450 | 60.99% | 2,948 |
| industry_neutral | -0.050 | -0.524 | 64.04% | 2,948 |
| size_industry_neutral | -0.051 | -0.599 | 65.30% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.049 | -0.595 | 62.04% | 245 |
| 2015.000 | -0.026 | -0.250 | 56.97% | 244 |
| 2016.000 | -0.058 | -0.662 | 66.80% | 244 |
| 2017.000 | -0.043 | -0.488 | 69.67% | 244 |
| 2018.000 | -0.038 | -0.392 | 64.61% | 243 |
| 2019.000 | -0.059 | -0.793 | 73.36% | 244 |
| 2020.000 | -0.053 | -0.631 | 62.96% | 243 |
| 2021.000 | -0.055 | -0.857 | 65.43% | 243 |
| 2022.000 | -0.057 | -0.737 | 64.05% | 242 |
| 2023.000 | -0.050 | -0.730 | 64.05% | 242 |
| 2024.000 | -0.055 | -0.508 | 71.49% | 242 |
| 2025.000 | -0.071 | -0.943 | 64.20% | 243 |
| 2026.000 | -0.055 | -0.973 | 48.28% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.071 | -0.936 |
| -0.070 | -0.939 |
| -0.071 | -0.939 |
| -0.071 | -0.949 |
| -0.072 | -0.951 |
| -0.072 | -0.956 |
| -0.072 | -0.956 |
| -0.072 | -0.956 |
| -0.072 | -0.964 |
| -0.072 | -0.966 |
| -0.073 | -0.971 |
| -0.073 | -0.986 |
| -0.073 | -0.981 |
| -0.072 | -0.977 |
| -0.071 | -0.973 |
| -0.071 | -0.962 |
| -0.070 | -0.962 |
| -0.070 | -0.963 |
| -0.069 | -0.955 |
| -0.069 | -0.956 |
| -0.069 | -0.956 |
| -0.069 | -0.963 |
| -0.070 | -0.979 |
| -0.070 | -0.997 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.872`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.034 | -0.380 | 2,952 |
| 2.000 | -0.041 | -0.463 | 2,951 |
| 3.000 | -0.045 | -0.519 | 2,950 |
| 5.000 | -0.051 | -0.599 | 2,948 |
| 10.000 | -0.060 | -0.728 | 2,943 |
| 20.000 | -0.069 | -0.830 | 2,933 |
| 40.000 | -0.078 | -1.001 | 2,913 |
| 60.000 | -0.083 | -1.158 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-55.72%`
- Long-short total diagnostic return: `-99.99%`
- Long-short Sharpe: `-3.405`
- Monotonic: `False`
- Monotonic Spearman: `-0.600`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 0.973 | 0.654 | 1.488 | 2,948 |
| 2.000 | 0.004 | 1.092 | 0.666 | 1.641 | 2,948 |
| 3.000 | 0.004 | 1.104 | 0.675 | 1.636 | 2,948 |
| 4.000 | 0.004 | 0.967 | 0.698 | 1.387 | 2,948 |
| 5.000 | 0.001 | 0.186 | 0.752 | 0.248 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.553 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.560 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.708 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.715 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.720 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 5 | -0.008 | -0.192 |
| fold_02_2022 | 5 | -0.002 | -0.053 |
| fold_03_2023 | 6 | -0.009 | -0.263 |
| fold_04_2024 | 6 | -0.007 | -0.190 |
| fold_05_2025 | 6 | -0.009 | -0.178 |

## Risks
- Quantile monotonicity is weak in the 5d strategy-horizon diagnostic.

## Conclusion
- Final decision: `keep`
- Selected folds: `2`
- Validation-pass folds: `5`
- Summary: Repeatedly selected across OOS folds.
