# Factor Card: val_pb_change_60d

## Basic Info
- Category: `Value`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Ref($pb, 1) / Ref($pb, 61) - 1`

## Screening Snapshot
- Grade: `A (Graduated)`
- 5d Rank ICIR: `-0.357`
- 10d Rank ICIR: `-0.429`
- 20d Rank ICIR: `-0.482`
- Monotonic: `True`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.647 | -0.337 | -0.585 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.605 | -0.459 | -0.441 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.602 | -0.512 | -0.502 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.574 | -0.472 | -0.425 | -1 | -1 | True | True | True |  |
| fold_05_2023 | -0.464 | -0.464 | -0.229 | -1 | -1 | True | True | False |  |
| fold_06_2024 | -0.432 | -0.326 | -0.333 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.458 | -0.281 | -0.723 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.052 | -0.357 | 59.29% | 3,429 |
| size_neutral | -0.052 | -0.394 | 60.69% | 3,429 |
| industry_neutral | -0.046 | -0.429 | 62.53% | 3,429 |
| size_industry_neutral | -0.046 | -0.488 | 64.19% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.058 | -0.516 | 72.02% | 243 |
| 2013.000 | -0.042 | -0.392 | 55.88% | 238 |
| 2014.000 | -0.058 | -0.756 | 68.57% | 245 |
| 2015.000 | -0.093 | -1.084 | 78.28% | 244 |
| 2016.000 | -0.055 | -0.696 | 68.44% | 244 |
| 2017.000 | -0.032 | -0.320 | 61.89% | 244 |
| 2018.000 | -0.034 | -0.355 | 64.20% | 243 |
| 2019.000 | -0.048 | -0.585 | 68.85% | 244 |
| 2020.000 | -0.036 | -0.441 | 58.44% | 243 |
| 2021.000 | -0.043 | -0.502 | 61.73% | 243 |
| 2022.000 | -0.033 | -0.425 | 67.77% | 242 |
| 2023.000 | -0.018 | -0.229 | 56.20% | 242 |
| 2024.000 | -0.050 | -0.333 | 63.22% | 242 |
| 2025.000 | -0.049 | -0.723 | 54.73% | 243 |
| 2026.000 | -0.018 | -0.332 | 48.28% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.049 | -0.730 |
| -0.049 | -0.730 |
| -0.049 | -0.732 |
| -0.050 | -0.735 |
| -0.049 | -0.733 |
| -0.050 | -0.737 |
| -0.049 | -0.729 |
| -0.049 | -0.730 |
| -0.049 | -0.729 |
| -0.049 | -0.725 |
| -0.049 | -0.719 |
| -0.049 | -0.715 |
| -0.048 | -0.705 |
| -0.048 | -0.699 |
| -0.048 | -0.694 |
| -0.047 | -0.687 |
| -0.047 | -0.688 |
| -0.047 | -0.687 |
| -0.047 | -0.684 |
| -0.046 | -0.684 |
| -0.046 | -0.685 |
| -0.045 | -0.681 |
| -0.045 | -0.673 |
| -0.044 | -0.662 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.577`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.030 | -0.323 | 3,433 |
| 2.000 | -0.035 | -0.366 | 3,432 |
| 3.000 | -0.040 | -0.415 | 3,431 |
| 5.000 | -0.046 | -0.488 | 3,429 |
| 10.000 | -0.054 | -0.572 | 3,424 |
| 20.000 | -0.059 | -0.632 | 3,414 |
| 40.000 | -0.055 | -0.642 | 3,394 |
| 60.000 | -0.050 | -0.650 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-70.55%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-4.478`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.248 | 0.718 | 1.738 | 3,429 |
| 2.000 | 0.005 | 1.175 | 0.669 | 1.757 | 3,429 |
| 3.000 | 0.004 | 1.032 | 0.640 | 1.613 | 3,429 |
| 4.000 | 0.003 | 0.796 | 0.640 | 1.244 | 3,429 |
| 5.000 | 0.000 | 0.084 | 0.683 | 0.123 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.378 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.387 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.434 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.452 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.747 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.417 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.421 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.014 | 0.210 |
| fold_02_2020 | 10 | 0.008 | 0.112 |
| fold_03_2021 | 10 | 0.007 | 0.103 |
| fold_04_2022 | 8 | -0.005 | -0.084 |
| fold_05_2023 | 10 | 0.005 | 0.128 |
| fold_06_2024 | 10 | 0.018 | 0.255 |
| fold_07_2025 | 10 | 0.013 | 0.163 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `1`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
