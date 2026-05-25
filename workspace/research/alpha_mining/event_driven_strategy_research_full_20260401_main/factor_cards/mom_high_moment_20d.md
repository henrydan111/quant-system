# Factor Card: mom_high_moment_20d

## Basic Info
- Category: `Momentum`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean((($high * $adj_factor) - ($open * $adj_factor)) / ($open * $adj_factor), 20)`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `-0.456`
- 10d Rank ICIR: `-0.517`
- 20d Rank ICIR: `-0.580`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.635 | -0.660 | -0.853 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.665 | -0.733 | -0.573 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.711 | -0.702 | -0.823 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.731 | -0.684 | -0.925 | -1 | -1 | True | True | False |  |
| fold_05_2023 | -0.715 | -0.872 | -0.932 | -1 | -1 | True | True | False |  |
| fold_06_2024 | -0.705 | -0.929 | -0.641 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.744 | -0.754 | -0.877 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.073 | -0.456 | 58.94% | 3,429 |
| size_neutral | -0.076 | -0.504 | 59.70% | 3,429 |
| industry_neutral | -0.070 | -0.651 | 63.28% | 3,429 |
| size_industry_neutral | -0.072 | -0.707 | 64.42% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.053 | -0.537 | 67.08% | 243 |
| 2013.000 | -0.056 | -0.444 | 54.20% | 238 |
| 2014.000 | -0.075 | -0.733 | 67.35% | 245 |
| 2015.000 | -0.079 | -0.660 | 68.85% | 244 |
| 2016.000 | -0.093 | -0.855 | 67.21% | 244 |
| 2017.000 | -0.071 | -0.690 | 70.08% | 244 |
| 2018.000 | -0.066 | -0.629 | 68.31% | 243 |
| 2019.000 | -0.080 | -0.853 | 66.80% | 244 |
| 2020.000 | -0.060 | -0.573 | 56.38% | 243 |
| 2021.000 | -0.073 | -0.823 | 62.96% | 243 |
| 2022.000 | -0.076 | -0.925 | 64.46% | 242 |
| 2023.000 | -0.075 | -0.932 | 61.98% | 242 |
| 2024.000 | -0.072 | -0.641 | 68.60% | 242 |
| 2025.000 | -0.083 | -0.877 | 58.44% | 243 |
| 2026.000 | -0.069 | -0.922 | 55.17% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.082 | -0.869 |
| -0.082 | -0.869 |
| -0.082 | -0.871 |
| -0.083 | -0.878 |
| -0.083 | -0.880 |
| -0.083 | -0.886 |
| -0.083 | -0.887 |
| -0.084 | -0.893 |
| -0.084 | -0.895 |
| -0.084 | -0.897 |
| -0.085 | -0.900 |
| -0.085 | -0.909 |
| -0.085 | -0.909 |
| -0.085 | -0.907 |
| -0.084 | -0.903 |
| -0.084 | -0.893 |
| -0.083 | -0.893 |
| -0.083 | -0.894 |
| -0.083 | -0.891 |
| -0.083 | -0.894 |
| -0.084 | -0.901 |
| -0.084 | -0.914 |
| -0.085 | -0.932 |
| -0.085 | -0.940 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.852`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.051 | -0.487 | 3,433 |
| 2.000 | -0.058 | -0.558 | 3,432 |
| 3.000 | -0.064 | -0.615 | 3,431 |
| 5.000 | -0.072 | -0.707 | 3,429 |
| 10.000 | -0.082 | -0.816 | 3,424 |
| 20.000 | -0.092 | -0.918 | 3,414 |
| 40.000 | -0.102 | -1.053 | 3,394 |
| 60.000 | -0.109 | -1.224 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-70.55%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-4.376`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.237 | 0.636 | 1.946 | 3,429 |
| 2.000 | 0.005 | 1.176 | 0.643 | 1.830 | 3,429 |
| 3.000 | 0.004 | 1.078 | 0.652 | 1.653 | 3,429 |
| 4.000 | 0.003 | 0.861 | 0.677 | 1.272 | 3,429 |
| 5.000 | 0.000 | 0.014 | 0.750 | 0.019 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.710 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.684 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.726 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.748 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.752 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.761 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.611 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 6 | -0.013 | -0.141 |
| fold_02_2020 | 6 | -0.006 | -0.074 |
| fold_03_2021 | 5 | -0.006 | -0.085 |
| fold_04_2022 | 4 | -0.020 | -0.366 |
| fold_05_2023 | 3 | -0.030 | -0.563 |
| fold_06_2024 | 3 | -0.032 | -0.654 |
| fold_07_2025 | 1 | -0.035 | -0.417 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
