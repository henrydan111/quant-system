# Factor Card: rev_max_return_20d

## Basic Info
- Category: `Reversal`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Max((Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 2) - 1), 20)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.535`
- 10d Rank ICIR: `-0.625`
- 20d Rank ICIR: `-0.691`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.786 | -0.741 | -0.932 | -1 | -1 | True | True | True |  |
| fold_02_2022 | -0.782 | -0.756 | -0.956 | -1 | -1 | True | True | True |  |
| fold_03_2023 | -0.804 | -0.945 | -0.878 | -1 | -1 | True | True | True |  |
| fold_04_2024 | -0.782 | -0.916 | -0.553 | -1 | -1 | True | True | True |  |
| fold_05_2025 | -0.809 | -0.672 | -0.987 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.069 | -0.535 | 61.16% | 2,948 |
| size_neutral | -0.071 | -0.585 | 61.47% | 2,948 |
| industry_neutral | -0.063 | -0.743 | 65.40% | 2,948 |
| size_industry_neutral | -0.063 | -0.793 | 65.64% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.074 | -0.885 | 68.16% | 245 |
| 2015.000 | -0.048 | -0.545 | 56.97% | 244 |
| 2016.000 | -0.086 | -1.028 | 73.36% | 244 |
| 2017.000 | -0.065 | -0.795 | 72.54% | 244 |
| 2018.000 | -0.057 | -0.734 | 69.14% | 243 |
| 2019.000 | -0.065 | -0.874 | 70.08% | 244 |
| 2020.000 | -0.051 | -0.625 | 58.85% | 243 |
| 2021.000 | -0.061 | -0.932 | 65.02% | 243 |
| 2022.000 | -0.062 | -0.956 | 64.46% | 242 |
| 2023.000 | -0.060 | -0.878 | 62.40% | 242 |
| 2024.000 | -0.056 | -0.553 | 67.36% | 242 |
| 2025.000 | -0.075 | -0.987 | 59.67% | 243 |
| 2026.000 | -0.063 | -0.995 | 62.07% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.075 | -0.985 |
| -0.075 | -0.986 |
| -0.075 | -0.987 |
| -0.075 | -0.992 |
| -0.075 | -0.989 |
| -0.075 | -0.994 |
| -0.076 | -0.995 |
| -0.076 | -0.998 |
| -0.076 | -0.998 |
| -0.076 | -0.999 |
| -0.076 | -1.000 |
| -0.076 | -1.006 |
| -0.076 | -1.001 |
| -0.076 | -0.999 |
| -0.075 | -0.994 |
| -0.074 | -0.981 |
| -0.074 | -0.983 |
| -0.074 | -0.985 |
| -0.074 | -0.983 |
| -0.074 | -0.989 |
| -0.075 | -1.000 |
| -0.075 | -1.023 |
| -0.076 | -1.055 |
| -0.076 | -1.074 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.919`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.042 | -0.503 | 2,952 |
| 2.000 | -0.050 | -0.610 | 2,951 |
| 3.000 | -0.056 | -0.682 | 2,950 |
| 5.000 | -0.063 | -0.793 | 2,948 |
| 10.000 | -0.073 | -0.948 | 2,943 |
| 20.000 | -0.082 | -1.056 | 2,933 |
| 40.000 | -0.089 | -1.172 | 2,913 |
| 60.000 | -0.095 | -1.335 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-65.58%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-4.865`
- Monotonic: `True`
- Monotonic Spearman: `-0.900`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.176 | 0.662 | 1.777 | 2,948 |
| 2.000 | 0.005 | 1.227 | 0.670 | 1.831 | 2,948 |
| 3.000 | 0.004 | 1.041 | 0.678 | 1.535 | 2,948 |
| 4.000 | 0.003 | 0.762 | 0.698 | 1.092 | 2,948 |
| 5.000 | 0.001 | 0.134 | 0.742 | 0.180 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.329 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.077 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.000 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.000 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.527 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 3 | -0.010 | -0.178 |
| fold_02_2022 | 1 | -0.044 | -0.668 |
| fold_03_2023 | 0 |  |  |
| fold_04_2024 | 0 |  |  |
| fold_05_2025 | 4 | 0.000 | 0.008 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `keep`
- Selected folds: `4`
- Validation-pass folds: `5`
- Summary: Repeatedly selected across OOS folds.
