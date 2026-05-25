# Factor Card: risk_vol_10d

## Basic Info
- Category: `Volatility`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Std((Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 2) - 1), 10)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.413`
- 10d Rank ICIR: `-0.490`
- 20d Rank ICIR: `-0.546`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.524 | -0.673 | -0.795 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.549 | -0.682 | -0.785 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.599 | -0.790 | -0.819 | -1 | -1 | True | True | True |  |
| fold_04_2024 | -0.612 | -0.802 | -0.510 | -1 | -1 | True | True | True |  |
| fold_05_2025 | -0.655 | -0.616 | -0.886 | -1 | -1 | True | True | True |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.065 | -0.413 | 59.40% | 2,948 |
| size_neutral | -0.068 | -0.470 | 60.38% | 2,948 |
| industry_neutral | -0.059 | -0.550 | 63.06% | 2,948 |
| size_industry_neutral | -0.060 | -0.624 | 63.87% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.058 | -0.591 | 61.22% | 245 |
| 2015.000 | -0.042 | -0.374 | 59.02% | 244 |
| 2016.000 | -0.071 | -0.669 | 66.39% | 244 |
| 2017.000 | -0.057 | -0.557 | 70.08% | 244 |
| 2018.000 | -0.049 | -0.454 | 65.02% | 243 |
| 2019.000 | -0.067 | -0.752 | 70.08% | 244 |
| 2020.000 | -0.058 | -0.600 | 61.73% | 243 |
| 2021.000 | -0.060 | -0.795 | 62.55% | 243 |
| 2022.000 | -0.063 | -0.785 | 61.98% | 242 |
| 2023.000 | -0.062 | -0.819 | 62.81% | 242 |
| 2024.000 | -0.061 | -0.510 | 65.70% | 242 |
| 2025.000 | -0.077 | -0.886 | 61.32% | 243 |
| 2026.000 | -0.063 | -0.888 | 51.72% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.077 | -0.885 |
| -0.076 | -0.886 |
| -0.077 | -0.887 |
| -0.077 | -0.894 |
| -0.077 | -0.895 |
| -0.078 | -0.902 |
| -0.078 | -0.908 |
| -0.078 | -0.914 |
| -0.078 | -0.918 |
| -0.079 | -0.921 |
| -0.079 | -0.926 |
| -0.080 | -0.937 |
| -0.079 | -0.931 |
| -0.079 | -0.927 |
| -0.078 | -0.921 |
| -0.077 | -0.909 |
| -0.077 | -0.911 |
| -0.076 | -0.912 |
| -0.076 | -0.909 |
| -0.077 | -0.917 |
| -0.077 | -0.929 |
| -0.078 | -0.947 |
| -0.079 | -0.977 |
| -0.079 | -0.986 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.899`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.040 | -0.389 | 2,952 |
| 2.000 | -0.048 | -0.479 | 2,951 |
| 3.000 | -0.054 | -0.538 | 2,950 |
| 5.000 | -0.060 | -0.624 | 2,948 |
| 10.000 | -0.071 | -0.744 | 2,943 |
| 20.000 | -0.081 | -0.834 | 2,933 |
| 40.000 | -0.092 | -1.026 | 2,913 |
| 60.000 | -0.099 | -1.202 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-62.07%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-3.681`
- Monotonic: `False`
- Monotonic Spearman: `-0.700`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 1.048 | 0.644 | 1.627 | 2,948 |
| 2.000 | 0.005 | 1.155 | 0.665 | 1.736 | 2,948 |
| 3.000 | 0.004 | 1.115 | 0.675 | 1.652 | 2,948 |
| 4.000 | 0.004 | 0.904 | 0.704 | 1.284 | 2,948 |
| 5.000 | 0.000 | 0.113 | 0.762 | 0.148 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.702 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.710 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.581 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.591 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.588 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 7 | 0.002 | 0.056 |
| fold_02_2022 | 6 | 0.004 | 0.105 |
| fold_03_2023 | 5 | -0.003 | -0.068 |
| fold_04_2024 | 5 | -0.004 | -0.096 |
| fold_05_2025 | 5 | -0.002 | -0.038 |

## Risks
- Quantile monotonicity is weak in the 5d strategy-horizon diagnostic.

## Conclusion
- Final decision: `keep`
- Selected folds: `3`
- Validation-pass folds: `5`
- Summary: Repeatedly selected across OOS folds.
