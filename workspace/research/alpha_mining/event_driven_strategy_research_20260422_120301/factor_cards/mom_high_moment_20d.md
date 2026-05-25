# Factor Card: mom_high_moment_20d

## Basic Info
- Category: `Momentum`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean((Ref(($high * $adj_factor), 1) - Ref(($open * $adj_factor), 1)) / Ref(($open * $adj_factor), 1), 20)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.451`
- 10d Rank ICIR: `-0.520`
- 20d Rank ICIR: `-0.604`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.646 | -0.651 | -0.772 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.663 | -0.645 | -0.866 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.654 | -0.818 | -0.868 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.649 | -0.868 | -0.600 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.689 | -0.705 | -0.805 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.072 | -0.451 | 58.51% | 2,948 |
| size_neutral | -0.075 | -0.500 | 59.91% | 2,948 |
| industry_neutral | -0.067 | -0.632 | 62.42% | 2,948 |
| size_industry_neutral | -0.070 | -0.693 | 63.84% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.069 | -0.671 | 65.71% | 245 |
| 2015.000 | -0.071 | -0.595 | 68.85% | 244 |
| 2016.000 | -0.086 | -0.780 | 67.62% | 244 |
| 2017.000 | -0.065 | -0.630 | 68.44% | 244 |
| 2018.000 | -0.060 | -0.565 | 67.90% | 243 |
| 2019.000 | -0.073 | -0.778 | 64.34% | 244 |
| 2020.000 | -0.057 | -0.542 | 54.73% | 243 |
| 2021.000 | -0.069 | -0.772 | 62.55% | 243 |
| 2022.000 | -0.072 | -0.866 | 62.40% | 242 |
| 2023.000 | -0.070 | -0.868 | 60.33% | 242 |
| 2024.000 | -0.067 | -0.600 | 67.77% | 242 |
| 2025.000 | -0.077 | -0.805 | 56.38% | 243 |
| 2026.000 | -0.066 | -0.896 | 55.17% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.076 | -0.798 |
| -0.076 | -0.798 |
| -0.076 | -0.800 |
| -0.077 | -0.807 |
| -0.077 | -0.809 |
| -0.077 | -0.816 |
| -0.078 | -0.817 |
| -0.078 | -0.824 |
| -0.078 | -0.827 |
| -0.079 | -0.829 |
| -0.079 | -0.833 |
| -0.079 | -0.844 |
| -0.079 | -0.842 |
| -0.079 | -0.842 |
| -0.079 | -0.838 |
| -0.078 | -0.829 |
| -0.078 | -0.829 |
| -0.078 | -0.830 |
| -0.077 | -0.826 |
| -0.077 | -0.829 |
| -0.078 | -0.835 |
| -0.079 | -0.849 |
| -0.079 | -0.865 |
| -0.079 | -0.872 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.912`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.049 | -0.472 | 2,952 |
| 2.000 | -0.056 | -0.547 | 2,951 |
| 3.000 | -0.062 | -0.604 | 2,950 |
| 5.000 | -0.070 | -0.693 | 2,948 |
| 10.000 | -0.080 | -0.810 | 2,943 |
| 20.000 | -0.093 | -0.930 | 2,933 |
| 40.000 | -0.104 | -1.103 | 2,913 |
| 60.000 | -0.112 | -1.289 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-70.39%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-4.180`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.195 | 0.652 | 1.831 | 2,948 |
| 2.000 | 0.005 | 1.177 | 0.659 | 1.788 | 2,948 |
| 3.000 | 0.004 | 1.100 | 0.671 | 1.640 | 2,948 |
| 4.000 | 0.003 | 0.863 | 0.699 | 1.236 | 2,948 |
| 5.000 | 0.000 | 0.017 | 0.775 | 0.022 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.726 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.748 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.752 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.761 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.611 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 6 | -0.006 | -0.083 |
| fold_02_2022 | 7 | -0.017 | -0.333 |
| fold_03_2023 | 3 | -0.027 | -0.508 |
| fold_04_2024 | 3 | -0.030 | -0.606 |
| fold_05_2025 | 3 | -0.017 | -0.243 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
