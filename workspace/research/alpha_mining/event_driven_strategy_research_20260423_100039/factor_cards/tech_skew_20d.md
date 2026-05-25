# Factor Card: tech_skew_20d

## Basic Info
- Category: `Technical`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Skew((Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 2) - 1), 20)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.456`
- 10d Rank ICIR: `-0.498`
- 20d Rank ICIR: `-0.488`
- Monotonic: `True`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.629 | -0.564 | -0.747 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.567 | -0.572 | -0.746 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.656 | -0.728 | -0.789 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.655 | -0.758 | -0.492 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.653 | -0.558 | -0.899 | -1 | -1 | True | True | True |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.037 | -0.455 | 63.64% | 2,948 |
| size_neutral | -0.035 | -0.506 | 63.87% | 2,948 |
| industry_neutral | -0.035 | -0.554 | 67.23% | 2,948 |
| size_industry_neutral | -0.034 | -0.624 | 67.71% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.051 | -1.127 | 80.82% | 245 |
| 2015.000 | -0.018 | -0.229 | 68.03% | 244 |
| 2016.000 | -0.044 | -0.692 | 72.95% | 244 |
| 2017.000 | -0.043 | -0.768 | 76.23% | 244 |
| 2018.000 | -0.037 | -0.715 | 72.43% | 243 |
| 2019.000 | -0.033 | -0.679 | 65.98% | 244 |
| 2020.000 | -0.019 | -0.447 | 58.44% | 243 |
| 2021.000 | -0.024 | -0.747 | 56.79% | 243 |
| 2022.000 | -0.035 | -0.746 | 62.81% | 242 |
| 2023.000 | -0.029 | -0.789 | 64.88% | 242 |
| 2024.000 | -0.037 | -0.492 | 68.60% | 242 |
| 2025.000 | -0.034 | -0.899 | 67.49% | 243 |
| 2026.000 | -0.024 | -1.131 | 58.62% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.034 | -0.909 |
| -0.034 | -0.908 |
| -0.034 | -0.904 |
| -0.034 | -0.904 |
| -0.034 | -0.901 |
| -0.034 | -0.895 |
| -0.034 | -0.899 |
| -0.034 | -0.900 |
| -0.034 | -0.895 |
| -0.033 | -0.885 |
| -0.033 | -0.881 |
| -0.033 | -0.881 |
| -0.033 | -0.879 |
| -0.033 | -0.879 |
| -0.033 | -0.874 |
| -0.033 | -0.865 |
| -0.033 | -0.862 |
| -0.032 | -0.866 |
| -0.032 | -0.865 |
| -0.032 | -0.871 |
| -0.033 | -0.878 |
| -0.033 | -0.892 |
| -0.033 | -0.912 |
| -0.033 | -0.923 |

## IC Decay
- Best horizon by |ICIR|: `20`
- Peak ICIR: `0.506`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.023 | -0.434 | 2,952 |
| 2.000 | -0.027 | -0.506 | 2,951 |
| 3.000 | -0.030 | -0.555 | 2,950 |
| 5.000 | -0.034 | -0.624 | 2,948 |
| 10.000 | -0.037 | -0.692 | 2,943 |
| 20.000 | -0.038 | -0.721 | 2,933 |
| 40.000 | -0.034 | -0.708 | 2,913 |
| 60.000 | -0.033 | -0.695 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-46.53%`
- Long-short total diagnostic return: `-99.93%`
- Long-short Sharpe: `-4.231`
- Monotonic: `True`
- Monotonic Spearman: `-0.900`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 1.052 | 0.676 | 1.557 | 2,948 |
| 2.000 | 0.004 | 1.084 | 0.690 | 1.570 | 2,948 |
| 3.000 | 0.004 | 0.964 | 0.694 | 1.389 | 2,948 |
| 4.000 | 0.003 | 0.793 | 0.692 | 1.146 | 2,948 |
| 5.000 | 0.002 | 0.438 | 0.680 | 0.644 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.662 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.707 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.659 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.666 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.239 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 10 | -0.005 | -0.185 |
| fold_02_2022 | 10 | -0.008 | -0.248 |
| fold_03_2023 | 7 | -0.008 | -0.240 |
| fold_04_2024 | 6 | -0.012 | -0.387 |
| fold_05_2025 | 6 | -0.006 | -0.144 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `1`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
