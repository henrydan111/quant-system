# Factor Card: val_pb_change_60d

## Basic Info
- Category: `Value`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Ref($pb, 1) / Ref($pb, 61) - 1`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.361`
- 10d Rank ICIR: `-0.437`
- 20d Rank ICIR: `-0.500`
- Monotonic: `True`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.602 | -0.512 | -0.502 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.574 | -0.472 | -0.425 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.464 | -0.464 | -0.229 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.432 | -0.326 | -0.333 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.458 | -0.281 | -0.723 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.052 | -0.361 | 59.06% | 2,948 |
| size_neutral | -0.052 | -0.412 | 60.79% | 2,948 |
| industry_neutral | -0.045 | -0.420 | 62.21% | 2,948 |
| size_industry_neutral | -0.045 | -0.496 | 64.21% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
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
- Peak ICIR: `0.601`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.029 | -0.326 | 2,952 |
| 2.000 | -0.034 | -0.371 | 2,951 |
| 3.000 | -0.039 | -0.419 | 2,950 |
| 5.000 | -0.045 | -0.496 | 2,948 |
| 10.000 | -0.053 | -0.587 | 2,943 |
| 20.000 | -0.058 | -0.653 | 2,933 |
| 40.000 | -0.055 | -0.667 | 2,913 |
| 60.000 | -0.050 | -0.657 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-70.17%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-4.436`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.223 | 0.739 | 1.655 | 2,948 |
| 2.000 | 0.005 | 1.189 | 0.688 | 1.728 | 2,948 |
| 3.000 | 0.004 | 1.059 | 0.658 | 1.608 | 2,948 |
| 4.000 | 0.003 | 0.808 | 0.659 | 1.226 | 2,948 |
| 5.000 | 0.000 | 0.048 | 0.703 | 0.069 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.396 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.507 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.497 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.533 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.509 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 10 | 0.009 | 0.130 |
| fold_02_2022 | 10 | -0.001 | -0.022 |
| fold_03_2023 | 10 | 0.004 | 0.050 |
| fold_04_2024 | 10 | 0.013 | 0.183 |
| fold_05_2025 | 10 | 0.014 | 0.148 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
