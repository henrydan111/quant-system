# Factor Card: rev_max_return_20d

## Basic Info
- Category: `Reversal`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Max((($close * $adj_factor) / Ref(($close * $adj_factor), 1) - 1), 20)`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `-0.539`
- 10d Rank ICIR: `-0.621`
- 20d Rank ICIR: `-0.671`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.725 | -0.827 | -0.964 | -1 | -1 | True | True | True |  |
| fold_02_2020 | -0.782 | -0.881 | -0.657 | -1 | -1 | True | True | True |  |
| fold_03_2021 | -0.810 | -0.799 | -0.980 | -1 | -1 | True | True | True |  |
| fold_04_2022 | -0.815 | -0.795 | -1.002 | -1 | -1 | True | True | True |  |
| fold_05_2023 | -0.863 | -0.991 | -0.930 | -1 | -1 | True | True | True |  |
| fold_06_2024 | -0.840 | -0.965 | -0.568 | -1 | -1 | True | True | True |  |
| fold_07_2025 | -0.865 | -0.699 | -1.071 | -1 | -1 | True | True | True |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.069 | -0.539 | 60.13% | 3,429 |
| size_neutral | -0.071 | -0.586 | 60.98% | 3,429 |
| industry_neutral | -0.064 | -0.752 | 64.28% | 3,429 |
| size_industry_neutral | -0.065 | -0.796 | 64.74% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.049 | -0.567 | 69.96% | 243 |
| 2013.000 | -0.062 | -0.670 | 60.08% | 238 |
| 2014.000 | -0.076 | -0.923 | 65.31% | 245 |
| 2015.000 | -0.045 | -0.487 | 46.31% | 244 |
| 2016.000 | -0.090 | -1.088 | 71.31% | 244 |
| 2017.000 | -0.068 | -0.851 | 71.31% | 244 |
| 2018.000 | -0.062 | -0.802 | 70.78% | 243 |
| 2019.000 | -0.072 | -0.964 | 70.90% | 244 |
| 2020.000 | -0.053 | -0.657 | 58.85% | 243 |
| 2021.000 | -0.064 | -0.980 | 62.96% | 243 |
| 2022.000 | -0.064 | -1.002 | 64.05% | 242 |
| 2023.000 | -0.063 | -0.930 | 61.57% | 242 |
| 2024.000 | -0.058 | -0.568 | 66.12% | 242 |
| 2025.000 | -0.080 | -1.071 | 60.08% | 243 |
| 2026.000 | -0.067 | -1.043 | 58.62% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.080 | -1.070 |
| -0.080 | -1.070 |
| -0.081 | -1.071 |
| -0.081 | -1.075 |
| -0.081 | -1.073 |
| -0.081 | -1.077 |
| -0.081 | -1.077 |
| -0.081 | -1.080 |
| -0.081 | -1.079 |
| -0.081 | -1.079 |
| -0.081 | -1.079 |
| -0.081 | -1.083 |
| -0.081 | -1.079 |
| -0.081 | -1.076 |
| -0.080 | -1.071 |
| -0.080 | -1.058 |
| -0.079 | -1.060 |
| -0.079 | -1.063 |
| -0.079 | -1.060 |
| -0.079 | -1.066 |
| -0.080 | -1.076 |
| -0.080 | -1.102 |
| -0.081 | -1.140 |
| -0.081 | -1.160 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.865`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.040 | -0.466 | 3,433 |
| 2.000 | -0.049 | -0.585 | 3,432 |
| 3.000 | -0.056 | -0.669 | 3,431 |
| 5.000 | -0.065 | -0.796 | 3,429 |
| 10.000 | -0.075 | -0.941 | 3,424 |
| 20.000 | -0.082 | -1.037 | 3,414 |
| 40.000 | -0.087 | -1.137 | 3,394 |
| 60.000 | -0.092 | -1.277 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-62.10%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-4.457`
- Monotonic: `True`
- Monotonic Spearman: `-0.900`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.149 | 0.645 | 1.782 | 3,429 |
| 2.000 | 0.005 | 1.213 | 0.651 | 1.862 | 3,429 |
| 3.000 | 0.004 | 1.032 | 0.658 | 1.569 | 3,429 |
| 4.000 | 0.003 | 0.770 | 0.677 | 1.138 | 3,429 |
| 5.000 | 0.001 | 0.203 | 0.720 | 0.282 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.419 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.419 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.540 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.562 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.000 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.000 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.519 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 1 | -0.047 | -0.575 |
| fold_02_2020 | 3 | -0.021 | -0.245 |
| fold_03_2021 | 2 | -0.008 | -0.152 |
| fold_04_2022 | 1 | -0.018 | -0.362 |
| fold_05_2023 | 0 |  |  |
| fold_06_2024 | 0 |  |  |
| fold_07_2025 | 3 | -0.004 | -0.061 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `keep`
- Selected folds: `7`
- Validation-pass folds: `7`
- Summary: Repeatedly selected across OOS folds.
