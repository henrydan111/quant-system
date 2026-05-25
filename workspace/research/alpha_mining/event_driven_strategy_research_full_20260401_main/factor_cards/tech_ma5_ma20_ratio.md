# Factor Card: tech_ma5_ma20_ratio

## Basic Info
- Category: `Technical`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean(($close * $adj_factor), 5) / Mean(($close * $adj_factor), 20)`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `-0.322`
- 10d Rank ICIR: `-0.352`
- 20d Rank ICIR: `-0.411`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.545 | -0.381 | -0.786 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.529 | -0.602 | -0.328 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.510 | -0.545 | -0.496 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.574 | -0.409 | -0.538 | -1 | -1 | True | True | False |  |
| fold_05_2023 | -0.485 | -0.516 | -0.437 | -1 | -1 | True | True | False |  |
| fold_06_2024 | -0.461 | -0.485 | -0.318 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.510 | -0.353 | -0.777 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.047 | -0.322 | 58.73% | 3,429 |
| size_neutral | -0.049 | -0.369 | 60.22% | 3,429 |
| industry_neutral | -0.048 | -0.427 | 63.46% | 3,429 |
| size_industry_neutral | -0.049 | -0.491 | 64.92% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.052 | -0.411 | 66.26% | 243 |
| 2013.000 | -0.054 | -0.558 | 61.34% | 238 |
| 2014.000 | -0.037 | -0.403 | 60.82% | 245 |
| 2015.000 | -0.094 | -0.791 | 72.95% | 244 |
| 2016.000 | -0.067 | -0.597 | 68.85% | 244 |
| 2017.000 | -0.032 | -0.309 | 57.38% | 244 |
| 2018.000 | -0.047 | -0.454 | 68.31% | 243 |
| 2019.000 | -0.069 | -0.786 | 72.54% | 244 |
| 2020.000 | -0.028 | -0.328 | 55.97% | 243 |
| 2021.000 | -0.040 | -0.496 | 58.02% | 243 |
| 2022.000 | -0.040 | -0.538 | 69.83% | 242 |
| 2023.000 | -0.035 | -0.437 | 69.83% | 242 |
| 2024.000 | -0.042 | -0.318 | 61.16% | 242 |
| 2025.000 | -0.059 | -0.777 | 67.49% | 243 |
| 2026.000 | -0.012 | -0.215 | 51.72% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.057 | -0.755 |
| -0.057 | -0.760 |
| -0.058 | -0.761 |
| -0.057 | -0.760 |
| -0.057 | -0.752 |
| -0.056 | -0.742 |
| -0.055 | -0.730 |
| -0.054 | -0.724 |
| -0.053 | -0.717 |
| -0.052 | -0.699 |
| -0.051 | -0.690 |
| -0.051 | -0.681 |
| -0.051 | -0.685 |
| -0.051 | -0.692 |
| -0.051 | -0.697 |
| -0.051 | -0.695 |
| -0.051 | -0.694 |
| -0.051 | -0.690 |
| -0.051 | -0.688 |
| -0.050 | -0.687 |
| -0.050 | -0.684 |
| -0.049 | -0.682 |
| -0.049 | -0.680 |
| -0.048 | -0.676 |

## IC Decay
- Best horizon by |ICIR|: `20`
- Peak ICIR: `0.519`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.040 | -0.376 | 3,433 |
| 2.000 | -0.044 | -0.423 | 3,432 |
| 3.000 | -0.047 | -0.455 | 3,431 |
| 5.000 | -0.049 | -0.491 | 3,429 |
| 10.000 | -0.053 | -0.544 | 3,424 |
| 20.000 | -0.057 | -0.614 | 3,414 |
| 40.000 | -0.049 | -0.565 | 3,394 |
| 60.000 | -0.043 | -0.513 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `0.00%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-4.558`
- Monotonic: `True`
- Monotonic Spearman: `-0.900`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.208 | 0.728 | 1.660 | 3,429 |
| 2.000 | 0.005 | 1.222 | 0.678 | 1.802 | 3,429 |
| 3.000 | 0.004 | 1.111 | 0.646 | 1.719 | 3,429 |
| 4.000 | 0.003 | 0.871 | 0.637 | 1.367 | 3,429 |
| 5.000 | -0.000 | -0.046 | 0.674 | -0.068 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.668 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.650 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.707 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.734 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.665 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.649 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.649 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.013 | 0.209 |
| fold_02_2020 | 8 | -0.007 | -0.129 |
| fold_03_2021 | 10 | -0.008 | -0.169 |
| fold_04_2022 | 10 | -0.003 | -0.042 |
| fold_05_2023 | 10 | 0.010 | 0.236 |
| fold_06_2024 | 10 | -0.001 | -0.021 |
| fold_07_2025 | 10 | 0.000 | 0.007 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
