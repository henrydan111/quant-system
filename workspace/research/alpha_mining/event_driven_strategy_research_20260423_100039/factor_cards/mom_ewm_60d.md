# Factor Card: mom_ewm_60d

## Basic Info
- Category: `Momentum`
- Signal direction in strategy: `low_is_good`
- Raw expression: `EMA((Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 2) - 1), 60)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.434`
- 10d Rank ICIR: `-0.497`
- 20d Rank ICIR: `-0.558`
- Monotonic: `True`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.642 | -0.538 | -0.585 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.630 | -0.490 | -0.676 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.516 | -0.627 | -0.382 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.479 | -0.522 | -0.444 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.542 | -0.406 | -0.945 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.067 | -0.434 | 59.84% | 2,948 |
| size_neutral | -0.066 | -0.480 | 60.85% | 2,948 |
| industry_neutral | -0.061 | -0.514 | 63.43% | 2,948 |
| size_industry_neutral | -0.061 | -0.588 | 63.84% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.069 | -0.770 | 63.67% | 245 |
| 2015.000 | -0.105 | -1.039 | 62.70% | 244 |
| 2016.000 | -0.079 | -0.795 | 72.13% | 244 |
| 2017.000 | -0.040 | -0.353 | 62.70% | 244 |
| 2018.000 | -0.047 | -0.417 | 62.14% | 243 |
| 2019.000 | -0.066 | -0.687 | 68.44% | 244 |
| 2020.000 | -0.039 | -0.399 | 54.73% | 243 |
| 2021.000 | -0.057 | -0.585 | 58.02% | 243 |
| 2022.000 | -0.058 | -0.676 | 72.73% | 242 |
| 2023.000 | -0.034 | -0.382 | 62.81% | 242 |
| 2024.000 | -0.065 | -0.444 | 66.53% | 242 |
| 2025.000 | -0.072 | -0.945 | 61.73% | 243 |
| 2026.000 | -0.026 | -0.504 | 44.83% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.071 | -0.939 |
| -0.070 | -0.939 |
| -0.070 | -0.938 |
| -0.070 | -0.938 |
| -0.070 | -0.931 |
| -0.070 | -0.932 |
| -0.070 | -0.919 |
| -0.069 | -0.911 |
| -0.069 | -0.907 |
| -0.068 | -0.898 |
| -0.068 | -0.893 |
| -0.068 | -0.892 |
| -0.068 | -0.898 |
| -0.068 | -0.903 |
| -0.068 | -0.906 |
| -0.068 | -0.900 |
| -0.068 | -0.902 |
| -0.068 | -0.903 |
| -0.067 | -0.901 |
| -0.067 | -0.903 |
| -0.066 | -0.905 |
| -0.066 | -0.900 |
| -0.065 | -0.892 |
| -0.064 | -0.878 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.571`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.042 | -0.406 | 2,952 |
| 2.000 | -0.048 | -0.463 | 2,951 |
| 3.000 | -0.054 | -0.517 | 2,950 |
| 5.000 | -0.061 | -0.588 | 2,948 |
| 10.000 | -0.068 | -0.667 | 2,943 |
| 20.000 | -0.073 | -0.736 | 2,933 |
| 40.000 | -0.069 | -0.742 | 2,913 |
| 60.000 | -0.064 | -0.735 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-75.88%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-4.737`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.301 | 0.752 | 1.732 | 2,948 |
| 2.000 | 0.005 | 1.247 | 0.687 | 1.815 | 2,948 |
| 3.000 | 0.004 | 1.076 | 0.660 | 1.632 | 2,948 |
| 4.000 | 0.003 | 0.844 | 0.656 | 1.285 | 2,948 |
| 5.000 | -0.000 | -0.117 | 0.712 | -0.164 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.611 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.817 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.815 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.816 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.767 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 10 | 0.009 | 0.119 |
| fold_02_2022 | 10 | -0.003 | -0.041 |
| fold_03_2023 | 10 | -0.005 | -0.058 |
| fold_04_2024 | 10 | 0.005 | 0.053 |
| fold_05_2025 | 10 | 0.005 | 0.049 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
