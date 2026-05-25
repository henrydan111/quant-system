# Factor Card: tech_rsi_28

## Basic Info
- Category: `Technical`
- Signal direction in strategy: `low_is_good`
- Raw expression: `100 - 100 / (1 + Mean(If((($close * $adj_factor) / Ref(($close * $adj_factor), 1) - 1) > 0, (($close * $adj_factor) / Ref(($close * $adj_factor), 1) - 1), 0), 28) / Mean(If((($close * $adj_factor) / Ref(($close * $adj_factor), 1) - 1) < 0, 0 - (($close * $adj_factor) / Ref(($close * $adj_factor), 1) - 1), 0), 28))`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `-0.370`
- 10d Rank ICIR: `-0.391`
- 20d Rank ICIR: `-0.415`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.583 | -0.419 | -0.725 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.559 | -0.590 | -0.287 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.557 | -0.489 | -0.507 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.588 | -0.393 | -0.757 | -1 | -1 | True | True | False |  |
| fold_05_2023 | -0.482 | -0.618 | -0.286 | -1 | -1 | True | True | False |  |
| fold_06_2024 | -0.461 | -0.498 | -0.478 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.533 | -0.388 | -0.693 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.051 | -0.370 | 54.13% | 3,429 |
| size_neutral | -0.051 | -0.411 | 54.77% | 3,429 |
| industry_neutral | -0.048 | -0.456 | 57.13% | 3,429 |
| size_industry_neutral | -0.049 | -0.521 | 57.92% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.051 | -0.466 | 62.96% | 243 |
| 2013.000 | -0.048 | -0.489 | 56.30% | 238 |
| 2014.000 | -0.045 | -0.549 | 53.06% | 245 |
| 2015.000 | -0.078 | -0.850 | 47.95% | 244 |
| 2016.000 | -0.058 | -0.610 | 64.75% | 244 |
| 2017.000 | -0.040 | -0.370 | 57.79% | 244 |
| 2018.000 | -0.046 | -0.476 | 60.91% | 243 |
| 2019.000 | -0.062 | -0.725 | 67.62% | 244 |
| 2020.000 | -0.026 | -0.287 | 49.38% | 243 |
| 2021.000 | -0.045 | -0.507 | 53.50% | 243 |
| 2022.000 | -0.056 | -0.757 | 68.60% | 242 |
| 2023.000 | -0.023 | -0.286 | 54.13% | 242 |
| 2024.000 | -0.053 | -0.478 | 63.22% | 242 |
| 2025.000 | -0.055 | -0.693 | 51.85% | 243 |
| 2026.000 | -0.013 | -0.281 | 62.07% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.055 | -0.694 |
| -0.054 | -0.691 |
| -0.054 | -0.691 |
| -0.054 | -0.692 |
| -0.054 | -0.688 |
| -0.054 | -0.686 |
| -0.054 | -0.680 |
| -0.053 | -0.673 |
| -0.053 | -0.663 |
| -0.052 | -0.649 |
| -0.051 | -0.641 |
| -0.051 | -0.639 |
| -0.051 | -0.650 |
| -0.052 | -0.665 |
| -0.053 | -0.674 |
| -0.053 | -0.674 |
| -0.053 | -0.678 |
| -0.052 | -0.676 |
| -0.052 | -0.673 |
| -0.051 | -0.671 |
| -0.050 | -0.668 |
| -0.049 | -0.664 |
| -0.048 | -0.656 |
| -0.048 | -0.647 |

## IC Decay
- Best horizon by |ICIR|: `20`
- Peak ICIR: `0.294`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.035 | -0.357 | 3,433 |
| 2.000 | -0.039 | -0.408 | 3,432 |
| 3.000 | -0.043 | -0.456 | 3,431 |
| 5.000 | -0.049 | -0.521 | 3,429 |
| 10.000 | -0.051 | -0.543 | 3,424 |
| 20.000 | -0.052 | -0.557 | 3,414 |
| 40.000 | -0.047 | -0.519 | 3,394 |
| 60.000 | -0.043 | -0.488 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-60.63%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-3.737`
- Monotonic: `True`
- Monotonic Spearman: `-0.900`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 1.091 | 0.701 | 1.557 | 3,429 |
| 2.000 | 0.005 | 1.175 | 0.678 | 1.733 | 3,429 |
| 3.000 | 0.004 | 1.071 | 0.662 | 1.619 | 3,429 |
| 4.000 | 0.003 | 0.839 | 0.656 | 1.280 | 3,429 |
| 5.000 | 0.001 | 0.190 | 0.657 | 0.289 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.674 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.641 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.629 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.594 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.660 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.637 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.630 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.006 | 0.105 |
| fold_02_2020 | 9 | -0.001 | -0.020 |
| fold_03_2021 | 10 | 0.003 | 0.048 |
| fold_04_2022 | 10 | -0.004 | -0.060 |
| fold_05_2023 | 8 | -0.006 | -0.110 |
| fold_06_2024 | 10 | 0.003 | 0.060 |
| fold_07_2025 | 10 | 0.013 | 0.194 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
