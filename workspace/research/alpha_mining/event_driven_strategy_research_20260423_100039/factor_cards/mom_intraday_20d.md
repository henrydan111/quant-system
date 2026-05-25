# Factor Card: mom_intraday_20d

## Basic Info
- Category: `Momentum`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean(Ref(($close * $adj_factor), 1) / Ref(($open * $adj_factor), 1) - 1, 20)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.454`
- 10d Rank ICIR: `-0.526`
- 20d Rank ICIR: `-0.615`
- Monotonic: `True`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.733 | -0.738 | -0.676 | -1 | -1 | True | True | True |  |
| fold_02_2022 | -0.797 | -0.596 | -0.796 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.706 | -0.734 | -0.596 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.670 | -0.693 | -0.554 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.732 | -0.557 | -0.848 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.060 | -0.454 | 63.33% | 2,948 |
| size_neutral | -0.062 | -0.518 | 65.37% | 2,948 |
| industry_neutral | -0.058 | -0.600 | 69.37% | 2,948 |
| size_industry_neutral | -0.060 | -0.703 | 71.37% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.050 | -0.626 | 68.16% | 245 |
| 2015.000 | -0.097 | -0.985 | 79.92% | 244 |
| 2016.000 | -0.075 | -0.856 | 75.82% | 244 |
| 2017.000 | -0.053 | -0.529 | 72.54% | 244 |
| 2018.000 | -0.063 | -0.728 | 79.84% | 243 |
| 2019.000 | -0.073 | -1.004 | 76.64% | 244 |
| 2020.000 | -0.040 | -0.519 | 62.96% | 243 |
| 2021.000 | -0.050 | -0.676 | 62.14% | 243 |
| 2022.000 | -0.055 | -0.796 | 76.86% | 242 |
| 2023.000 | -0.042 | -0.596 | 66.94% | 242 |
| 2024.000 | -0.060 | -0.554 | 72.31% | 242 |
| 2025.000 | -0.065 | -0.848 | 64.61% | 243 |
| 2026.000 | -0.027 | -0.521 | 51.72% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.065 | -0.844 |
| -0.064 | -0.843 |
| -0.064 | -0.842 |
| -0.064 | -0.843 |
| -0.064 | -0.835 |
| -0.064 | -0.834 |
| -0.063 | -0.824 |
| -0.063 | -0.819 |
| -0.062 | -0.817 |
| -0.061 | -0.813 |
| -0.060 | -0.808 |
| -0.060 | -0.801 |
| -0.060 | -0.807 |
| -0.061 | -0.829 |
| -0.062 | -0.843 |
| -0.061 | -0.840 |
| -0.062 | -0.845 |
| -0.061 | -0.845 |
| -0.061 | -0.845 |
| -0.060 | -0.849 |
| -0.060 | -0.850 |
| -0.059 | -0.844 |
| -0.058 | -0.837 |
| -0.058 | -0.823 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.874`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.042 | -0.481 | 2,952 |
| 2.000 | -0.048 | -0.556 | 2,951 |
| 3.000 | -0.054 | -0.622 | 2,950 |
| 5.000 | -0.060 | -0.703 | 2,948 |
| 10.000 | -0.068 | -0.806 | 2,943 |
| 20.000 | -0.075 | -0.912 | 2,933 |
| 40.000 | -0.075 | -0.950 | 2,913 |
| 60.000 | -0.075 | -0.969 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `0.00%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-6.425`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.006 | 1.433 | 0.739 | 1.939 | 2,948 |
| 2.000 | 0.005 | 1.224 | 0.682 | 1.795 | 2,948 |
| 3.000 | 0.004 | 1.107 | 0.655 | 1.689 | 2,948 |
| 4.000 | 0.003 | 0.823 | 0.662 | 1.243 | 2,948 |
| 5.000 | -0.001 | -0.234 | 0.719 | -0.326 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.411 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.715 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.710 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.734 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.736 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 4 | -0.025 | -0.358 |
| fold_02_2022 | 10 | -0.011 | -0.162 |
| fold_03_2023 | 7 | -0.007 | -0.100 |
| fold_04_2024 | 8 | -0.002 | -0.023 |
| fold_05_2025 | 8 | -0.003 | -0.042 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `1`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
