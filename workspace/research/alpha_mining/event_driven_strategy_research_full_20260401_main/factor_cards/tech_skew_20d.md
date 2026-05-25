# Factor Card: tech_skew_20d

## Basic Info
- Category: `Technical`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Skew((($close * $adj_factor) / Ref(($close * $adj_factor), 1) - 1), 20)`

## Screening Snapshot
- Grade: `A (Graduated)`
- 5d Rank ICIR: `-0.451`
- 10d Rank ICIR: `-0.517`
- 20d Rank ICIR: `-0.525`
- Monotonic: `True`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.561 | -0.718 | -0.746 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.602 | -0.726 | -0.379 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.591 | -0.561 | -0.707 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.544 | -0.522 | -0.720 | -1 | -1 | True | True | True |  |
| fold_05_2023 | -0.643 | -0.700 | -0.783 | -1 | -1 | True | True | False |  |
| fold_06_2024 | -0.639 | -0.742 | -0.468 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.641 | -0.540 | -0.976 | -1 | -1 | True | True | True |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.037 | -0.451 | 62.96% | 3,429 |
| size_neutral | -0.035 | -0.492 | 62.79% | 3,429 |
| industry_neutral | -0.036 | -0.549 | 65.88% | 3,429 |
| size_industry_neutral | -0.034 | -0.604 | 66.40% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.032 | -0.503 | 69.14% | 243 |
| 2013.000 | -0.041 | -0.782 | 73.11% | 238 |
| 2014.000 | -0.051 | -1.111 | 75.51% | 245 |
| 2015.000 | -0.014 | -0.167 | 65.16% | 244 |
| 2016.000 | -0.044 | -0.680 | 72.13% | 244 |
| 2017.000 | -0.043 | -0.728 | 76.23% | 244 |
| 2018.000 | -0.037 | -0.708 | 68.72% | 243 |
| 2019.000 | -0.036 | -0.746 | 67.21% | 244 |
| 2020.000 | -0.016 | -0.379 | 53.91% | 243 |
| 2021.000 | -0.024 | -0.707 | 56.79% | 243 |
| 2022.000 | -0.034 | -0.720 | 61.98% | 242 |
| 2023.000 | -0.029 | -0.783 | 63.22% | 242 |
| 2024.000 | -0.036 | -0.468 | 65.70% | 242 |
| 2025.000 | -0.037 | -0.976 | 63.79% | 243 |
| 2026.000 | -0.023 | -0.994 | 58.62% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.037 | -0.985 |
| -0.037 | -0.983 |
| -0.037 | -0.978 |
| -0.037 | -0.974 |
| -0.037 | -0.970 |
| -0.036 | -0.968 |
| -0.037 | -0.970 |
| -0.037 | -0.971 |
| -0.036 | -0.963 |
| -0.036 | -0.953 |
| -0.036 | -0.950 |
| -0.036 | -0.948 |
| -0.036 | -0.948 |
| -0.036 | -0.948 |
| -0.035 | -0.941 |
| -0.035 | -0.928 |
| -0.035 | -0.925 |
| -0.035 | -0.925 |
| -0.035 | -0.927 |
| -0.035 | -0.932 |
| -0.035 | -0.937 |
| -0.035 | -0.958 |
| -0.036 | -0.979 |
| -0.036 | -0.988 |

## IC Decay
- Best horizon by |ICIR|: `20`
- Peak ICIR: `0.522`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.018 | -0.323 | 3,433 |
| 2.000 | -0.024 | -0.417 | 3,432 |
| 3.000 | -0.028 | -0.497 | 3,431 |
| 5.000 | -0.034 | -0.604 | 3,429 |
| 10.000 | -0.039 | -0.709 | 3,424 |
| 20.000 | -0.040 | -0.755 | 3,414 |
| 40.000 | -0.036 | -0.735 | 3,394 |
| 60.000 | -0.033 | -0.694 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-42.05%`
- Long-short total diagnostic return: `-99.94%`
- Long-short Sharpe: `-3.634`
- Monotonic: `True`
- Monotonic Spearman: `-0.900`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 1.015 | 0.660 | 1.539 | 3,429 |
| 2.000 | 0.004 | 1.067 | 0.671 | 1.590 | 3,429 |
| 3.000 | 0.004 | 0.968 | 0.674 | 1.436 | 3,429 |
| 4.000 | 0.003 | 0.818 | 0.671 | 1.218 | 3,429 |
| 5.000 | 0.002 | 0.481 | 0.659 | 0.730 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.615 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.626 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.595 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.588 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.632 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.636 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.599 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 3 | 0.007 | 0.102 |
| fold_02_2020 | 6 | -0.000 | -0.001 |
| fold_03_2021 | 10 | -0.002 | -0.061 |
| fold_04_2022 | 7 | 0.002 | 0.053 |
| fold_05_2023 | 8 | -0.000 | -0.008 |
| fold_06_2024 | 5 | -0.004 | -0.097 |
| fold_07_2025 | 8 | -0.005 | -0.092 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `2`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
