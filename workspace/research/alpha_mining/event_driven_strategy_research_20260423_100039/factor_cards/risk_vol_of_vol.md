# Factor Card: risk_vol_of_vol

## Basic Info
- Category: `Volatility`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Std(Std((Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 2) - 1), 20), 60)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.321`
- 10d Rank ICIR: `-0.385`
- 20d Rank ICIR: `-0.464`
- Monotonic: `True`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.529 | -0.530 | -0.734 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.533 | -0.629 | -0.677 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.576 | -0.705 | -0.780 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.575 | -0.726 | -0.174 | -1 | -1 | True | True | True |  |
| fold_05_2025 | -0.580 | -0.384 | -0.418 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.039 | -0.321 | 57.39% | 2,948 |
| size_neutral | -0.042 | -0.418 | 59.19% | 2,948 |
| industry_neutral | -0.034 | -0.395 | 58.14% | 2,948 |
| size_industry_neutral | -0.036 | -0.511 | 60.62% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.033 | -0.482 | 58.78% | 245 |
| 2015.000 | -0.016 | -0.317 | 55.33% | 244 |
| 2016.000 | -0.042 | -0.762 | 59.84% | 244 |
| 2017.000 | -0.049 | -0.614 | 65.98% | 244 |
| 2018.000 | -0.032 | -0.507 | 62.14% | 243 |
| 2019.000 | -0.042 | -0.518 | 65.16% | 244 |
| 2020.000 | -0.039 | -0.546 | 67.49% | 243 |
| 2021.000 | -0.044 | -0.734 | 61.32% | 243 |
| 2022.000 | -0.036 | -0.677 | 62.40% | 242 |
| 2023.000 | -0.049 | -0.780 | 58.68% | 242 |
| 2024.000 | -0.018 | -0.174 | 53.31% | 242 |
| 2025.000 | -0.032 | -0.418 | 55.97% | 243 |
| 2026.000 | -0.064 | -0.965 | 68.97% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.032 | -0.422 |
| -0.032 | -0.425 |
| -0.033 | -0.430 |
| -0.033 | -0.436 |
| -0.034 | -0.442 |
| -0.034 | -0.444 |
| -0.034 | -0.444 |
| -0.034 | -0.451 |
| -0.035 | -0.456 |
| -0.035 | -0.464 |
| -0.036 | -0.475 |
| -0.036 | -0.480 |
| -0.036 | -0.475 |
| -0.036 | -0.472 |
| -0.035 | -0.465 |
| -0.034 | -0.455 |
| -0.034 | -0.454 |
| -0.034 | -0.454 |
| -0.034 | -0.458 |
| -0.035 | -0.473 |
| -0.036 | -0.492 |
| -0.037 | -0.517 |
| -0.038 | -0.552 |
| -0.039 | -0.580 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.769`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.023 | -0.335 | 2,952 |
| 2.000 | -0.028 | -0.399 | 2,951 |
| 3.000 | -0.032 | -0.438 | 2,950 |
| 5.000 | -0.036 | -0.511 | 2,948 |
| 10.000 | -0.044 | -0.623 | 2,943 |
| 20.000 | -0.052 | -0.749 | 2,933 |
| 40.000 | -0.064 | -0.967 | 2,913 |
| 60.000 | -0.072 | -1.216 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-44.32%`
- Long-short total diagnostic return: `-99.89%`
- Long-short Sharpe: `-2.964`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 1.119 | 0.685 | 1.633 | 2,948 |
| 2.000 | 0.004 | 1.040 | 0.668 | 1.558 | 2,948 |
| 3.000 | 0.003 | 0.871 | 0.661 | 1.318 | 2,948 |
| 4.000 | 0.003 | 0.757 | 0.678 | 1.116 | 2,948 |
| 5.000 | 0.002 | 0.553 | 0.749 | 0.738 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.544 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.456 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.472 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.482 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.490 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 10 | -0.007 | -0.166 |
| fold_02_2022 | 10 | -0.003 | -0.076 |
| fold_03_2023 | 8 | -0.000 | -0.008 |
| fold_04_2024 | 7 | -0.006 | -0.155 |
| fold_05_2025 | 10 | -0.004 | -0.056 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `1`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
