# Factor Card: risk_vol_20d

## Basic Info
- Category: `Volatility`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Std((($close * $adj_factor) / Ref(($close * $adj_factor), 1) - 1), 20)`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `-0.372`
- 10d Rank ICIR: `-0.433`
- 20d Rank ICIR: `-0.481`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.469 | -0.500 | -0.666 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.518 | -0.540 | -0.549 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.533 | -0.605 | -0.792 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.530 | -0.651 | -0.776 | -1 | -1 | True | True | False |  |
| fold_05_2023 | -0.574 | -0.785 | -0.840 | -1 | -1 | True | True | False |  |
| fold_06_2024 | -0.584 | -0.807 | -0.438 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.621 | -0.579 | -0.743 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.065 | -0.372 | 57.22% | 3,429 |
| size_neutral | -0.068 | -0.427 | 58.33% | 3,429 |
| industry_neutral | -0.060 | -0.495 | 61.50% | 3,429 |
| size_industry_neutral | -0.062 | -0.560 | 62.06% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.037 | -0.316 | 61.73% | 243 |
| 2013.000 | -0.046 | -0.372 | 52.10% | 238 |
| 2014.000 | -0.074 | -0.661 | 65.71% | 245 |
| 2015.000 | -0.047 | -0.363 | 56.97% | 244 |
| 2016.000 | -0.082 | -0.676 | 67.21% | 244 |
| 2017.000 | -0.064 | -0.563 | 66.80% | 244 |
| 2018.000 | -0.055 | -0.442 | 64.61% | 243 |
| 2019.000 | -0.067 | -0.666 | 66.80% | 244 |
| 2020.000 | -0.060 | -0.549 | 58.44% | 243 |
| 2021.000 | -0.068 | -0.792 | 61.32% | 243 |
| 2022.000 | -0.069 | -0.776 | 64.05% | 242 |
| 2023.000 | -0.069 | -0.840 | 61.57% | 242 |
| 2024.000 | -0.057 | -0.438 | 63.64% | 242 |
| 2025.000 | -0.077 | -0.743 | 58.02% | 243 |
| 2026.000 | -0.075 | -0.942 | 58.62% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.077 | -0.745 |
| -0.077 | -0.745 |
| -0.078 | -0.747 |
| -0.078 | -0.753 |
| -0.078 | -0.755 |
| -0.079 | -0.761 |
| -0.079 | -0.766 |
| -0.080 | -0.775 |
| -0.080 | -0.781 |
| -0.081 | -0.785 |
| -0.081 | -0.790 |
| -0.082 | -0.800 |
| -0.081 | -0.796 |
| -0.081 | -0.793 |
| -0.080 | -0.788 |
| -0.080 | -0.779 |
| -0.079 | -0.779 |
| -0.079 | -0.779 |
| -0.079 | -0.777 |
| -0.079 | -0.782 |
| -0.080 | -0.793 |
| -0.081 | -0.811 |
| -0.081 | -0.833 |
| -0.082 | -0.847 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.820`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.040 | -0.351 | 3,433 |
| 2.000 | -0.049 | -0.430 | 3,432 |
| 3.000 | -0.054 | -0.482 | 3,431 |
| 5.000 | -0.062 | -0.560 | 3,429 |
| 10.000 | -0.073 | -0.660 | 3,424 |
| 20.000 | -0.083 | -0.743 | 3,414 |
| 40.000 | -0.094 | -0.917 | 3,394 |
| 60.000 | -0.104 | -1.131 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-61.84%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-3.274`
- Monotonic: `True`
- Monotonic Spearman: `-0.900`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 1.106 | 0.613 | 1.804 | 3,429 |
| 2.000 | 0.004 | 1.111 | 0.642 | 1.730 | 3,429 |
| 3.000 | 0.004 | 1.071 | 0.657 | 1.629 | 3,429 |
| 4.000 | 0.003 | 0.881 | 0.689 | 1.278 | 3,429 |
| 5.000 | 0.001 | 0.185 | 0.753 | 0.245 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.813 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.818 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.843 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.850 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.852 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.861 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.847 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.017 | 0.245 |
| fold_02_2020 | 10 | 0.005 | 0.091 |
| fold_03_2021 | 10 | 0.006 | 0.105 |
| fold_04_2022 | 5 | -0.003 | -0.041 |
| fold_05_2023 | 5 | -0.007 | -0.116 |
| fold_06_2024 | 3 | -0.007 | -0.115 |
| fold_07_2025 | 7 | 0.003 | 0.039 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
