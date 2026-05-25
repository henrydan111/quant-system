# Factor Card: tech_rsi_28

## Basic Info
- Category: `Technical`
- Signal direction in strategy: `low_is_good`
- Raw expression: `100 - 100 / (1 + Mean(If((Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 2) - 1) > 0, (Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 2) - 1), 0), 28) / Mean(If((Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 2) - 1) < 0, 0 - (Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 2) - 1), 0), 28))`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.346`
- 10d Rank ICIR: `-0.376`
- 20d Rank ICIR: `-0.417`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.507 | -0.448 | -0.470 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.541 | -0.369 | -0.703 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.438 | -0.573 | -0.217 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.421 | -0.435 | -0.435 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.491 | -0.334 | -0.633 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.047 | -0.346 | 54.31% | 2,948 |
| size_neutral | -0.047 | -0.391 | 55.12% | 2,948 |
| industry_neutral | -0.043 | -0.412 | 57.12% | 2,948 |
| size_industry_neutral | -0.043 | -0.481 | 58.58% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.037 | -0.462 | 53.06% | 245 |
| 2015.000 | -0.076 | -0.817 | 58.61% | 244 |
| 2016.000 | -0.051 | -0.549 | 65.57% | 244 |
| 2017.000 | -0.035 | -0.332 | 57.38% | 244 |
| 2018.000 | -0.041 | -0.433 | 61.32% | 243 |
| 2019.000 | -0.053 | -0.651 | 68.03% | 244 |
| 2020.000 | -0.024 | -0.274 | 49.38% | 243 |
| 2021.000 | -0.041 | -0.470 | 53.09% | 243 |
| 2022.000 | -0.051 | -0.703 | 69.01% | 242 |
| 2023.000 | -0.018 | -0.217 | 55.37% | 242 |
| 2024.000 | -0.047 | -0.435 | 62.81% | 242 |
| 2025.000 | -0.050 | -0.633 | 52.26% | 243 |
| 2026.000 | -0.010 | -0.226 | 65.52% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.050 | -0.632 |
| -0.049 | -0.629 |
| -0.049 | -0.627 |
| -0.049 | -0.629 |
| -0.049 | -0.624 |
| -0.049 | -0.625 |
| -0.049 | -0.619 |
| -0.048 | -0.612 |
| -0.048 | -0.605 |
| -0.047 | -0.591 |
| -0.046 | -0.584 |
| -0.046 | -0.583 |
| -0.047 | -0.590 |
| -0.047 | -0.605 |
| -0.048 | -0.617 |
| -0.048 | -0.620 |
| -0.048 | -0.623 |
| -0.048 | -0.621 |
| -0.047 | -0.615 |
| -0.046 | -0.612 |
| -0.045 | -0.610 |
| -0.045 | -0.606 |
| -0.044 | -0.599 |
| -0.043 | -0.590 |

## IC Decay
- Best horizon by |ICIR|: `40`
- Peak ICIR: `0.303`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.031 | -0.332 | 2,952 |
| 2.000 | -0.035 | -0.379 | 2,951 |
| 3.000 | -0.039 | -0.428 | 2,950 |
| 5.000 | -0.043 | -0.481 | 2,948 |
| 10.000 | -0.047 | -0.513 | 2,943 |
| 20.000 | -0.049 | -0.539 | 2,933 |
| 40.000 | -0.047 | -0.529 | 2,913 |
| 60.000 | -0.043 | -0.498 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-61.01%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-3.736`
- Monotonic: `False`
- Monotonic Spearman: `-0.700`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 1.065 | 0.715 | 1.489 | 2,948 |
| 2.000 | 0.005 | 1.176 | 0.694 | 1.693 | 2,948 |
| 3.000 | 0.004 | 1.082 | 0.681 | 1.588 | 2,948 |
| 4.000 | 0.003 | 0.861 | 0.678 | 1.269 | 2,948 |
| 5.000 | 0.001 | 0.155 | 0.683 | 0.227 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.594 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.723 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.713 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.712 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.679 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 10 | 0.008 | 0.150 |
| fold_02_2022 | 10 | 0.002 | 0.031 |
| fold_03_2023 | 10 | -0.003 | -0.046 |
| fold_04_2024 | 10 | 0.006 | 0.095 |
| fold_05_2025 | 10 | 0.014 | 0.188 |

## Risks
- Quantile monotonicity is weak in the 5d strategy-horizon diagnostic.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
