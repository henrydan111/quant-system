# Factor Card: risk_vol_20d

## Basic Info
- Category: `Volatility`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Std((Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 2) - 1), 20)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.381`
- 10d Rank ICIR: `-0.449`
- 20d Rank ICIR: `-0.517`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.505 | -0.569 | -0.764 | -1 | -1 | True | True | True |  |
| fold_02_2022 | -0.500 | -0.625 | -0.752 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.538 | -0.759 | -0.799 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.550 | -0.775 | -0.411 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.589 | -0.551 | -0.735 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.066 | -0.381 | 57.73% | 2,948 |
| size_neutral | -0.069 | -0.437 | 59.09% | 2,948 |
| industry_neutral | -0.061 | -0.504 | 61.74% | 2,948 |
| size_industry_neutral | -0.063 | -0.573 | 62.35% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.071 | -0.628 | 65.71% | 245 |
| 2015.000 | -0.046 | -0.356 | 57.79% | 244 |
| 2016.000 | -0.078 | -0.637 | 65.98% | 244 |
| 2017.000 | -0.061 | -0.522 | 65.16% | 244 |
| 2018.000 | -0.051 | -0.410 | 64.61% | 243 |
| 2019.000 | -0.062 | -0.620 | 65.98% | 244 |
| 2020.000 | -0.057 | -0.523 | 56.79% | 243 |
| 2021.000 | -0.066 | -0.764 | 60.91% | 243 |
| 2022.000 | -0.066 | -0.752 | 63.22% | 242 |
| 2023.000 | -0.066 | -0.799 | 61.16% | 242 |
| 2024.000 | -0.053 | -0.411 | 64.05% | 242 |
| 2025.000 | -0.074 | -0.735 | 57.20% | 243 |
| 2026.000 | -0.071 | -0.903 | 58.62% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.074 | -0.734 |
| -0.073 | -0.734 |
| -0.074 | -0.737 |
| -0.074 | -0.743 |
| -0.075 | -0.746 |
| -0.075 | -0.753 |
| -0.075 | -0.759 |
| -0.076 | -0.769 |
| -0.077 | -0.776 |
| -0.077 | -0.780 |
| -0.078 | -0.786 |
| -0.078 | -0.797 |
| -0.078 | -0.794 |
| -0.078 | -0.790 |
| -0.077 | -0.785 |
| -0.076 | -0.776 |
| -0.076 | -0.776 |
| -0.076 | -0.776 |
| -0.075 | -0.774 |
| -0.076 | -0.780 |
| -0.077 | -0.791 |
| -0.077 | -0.810 |
| -0.078 | -0.833 |
| -0.079 | -0.846 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.881`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.041 | -0.365 | 2,952 |
| 2.000 | -0.050 | -0.444 | 2,951 |
| 3.000 | -0.055 | -0.495 | 2,950 |
| 5.000 | -0.063 | -0.573 | 2,948 |
| 10.000 | -0.073 | -0.680 | 2,943 |
| 20.000 | -0.085 | -0.784 | 2,933 |
| 40.000 | -0.099 | -0.984 | 2,913 |
| 60.000 | -0.109 | -1.198 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-63.98%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-3.447`
- Monotonic: `True`
- Monotonic Spearman: `-0.900`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 1.105 | 0.633 | 1.746 | 2,948 |
| 2.000 | 0.005 | 1.135 | 0.660 | 1.719 | 2,948 |
| 3.000 | 0.004 | 1.089 | 0.676 | 1.611 | 2,948 |
| 4.000 | 0.003 | 0.877 | 0.709 | 1.237 | 2,948 |
| 5.000 | 0.001 | 0.127 | 0.775 | 0.164 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.565 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.705 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.715 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.719 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.723 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 9 | 0.015 | 0.267 |
| fold_02_2022 | 10 | 0.009 | 0.168 |
| fold_03_2023 | 7 | 0.008 | 0.171 |
| fold_04_2024 | 6 | 0.011 | 0.198 |
| fold_05_2025 | 8 | 0.016 | 0.292 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `1`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
