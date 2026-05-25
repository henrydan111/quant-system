# Factor Card: mom_weighted_120d

## Basic Info
- Category: `Momentum`
- Signal direction in strategy: `low_is_good`
- Raw expression: `WMA((($close * $adj_factor) / Ref(($close * $adj_factor), 1) - 1), 120)`

## Screening Snapshot
- Grade: `A (Graduated)`
- 5d Rank ICIR: `-0.407`
- 10d Rank ICIR: `-0.465`
- 20d Rank ICIR: `-0.505`
- Monotonic: `True`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.673 | -0.346 | -0.616 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.621 | -0.474 | -0.362 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.630 | -0.482 | -0.551 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.604 | -0.454 | -0.650 | -1 | -1 | True | True | False |  |
| fold_05_2023 | -0.472 | -0.597 | -0.362 | -1 | -1 | True | True | True |  |
| fold_06_2024 | -0.437 | -0.500 | -0.434 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.497 | -0.391 | -0.873 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.064 | -0.407 | 58.15% | 3,429 |
| size_neutral | -0.062 | -0.436 | 58.06% | 3,429 |
| industry_neutral | -0.059 | -0.492 | 60.95% | 3,429 |
| size_industry_neutral | -0.057 | -0.542 | 61.42% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.074 | -0.581 | 73.66% | 243 |
| 2013.000 | -0.048 | -0.370 | 52.10% | 238 |
| 2014.000 | -0.068 | -0.765 | 61.22% | 245 |
| 2015.000 | -0.099 | -1.181 | 61.48% | 244 |
| 2016.000 | -0.069 | -0.780 | 65.98% | 244 |
| 2017.000 | -0.036 | -0.335 | 65.16% | 244 |
| 2018.000 | -0.038 | -0.356 | 56.79% | 243 |
| 2019.000 | -0.058 | -0.616 | 63.52% | 244 |
| 2020.000 | -0.037 | -0.362 | 53.50% | 243 |
| 2021.000 | -0.055 | -0.551 | 58.85% | 243 |
| 2022.000 | -0.057 | -0.650 | 69.83% | 242 |
| 2023.000 | -0.033 | -0.362 | 56.61% | 242 |
| 2024.000 | -0.068 | -0.434 | 65.29% | 242 |
| 2025.000 | -0.068 | -0.873 | 56.38% | 243 |
| 2026.000 | -0.024 | -0.444 | 55.17% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.068 | -0.873 |
| -0.067 | -0.872 |
| -0.067 | -0.871 |
| -0.067 | -0.873 |
| -0.067 | -0.874 |
| -0.068 | -0.878 |
| -0.067 | -0.869 |
| -0.068 | -0.877 |
| -0.068 | -0.880 |
| -0.068 | -0.881 |
| -0.068 | -0.880 |
| -0.068 | -0.884 |
| -0.068 | -0.882 |
| -0.067 | -0.875 |
| -0.067 | -0.869 |
| -0.066 | -0.859 |
| -0.066 | -0.859 |
| -0.065 | -0.862 |
| -0.065 | -0.860 |
| -0.065 | -0.860 |
| -0.065 | -0.858 |
| -0.065 | -0.857 |
| -0.065 | -0.862 |
| -0.065 | -0.854 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.447`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.037 | -0.357 | 3,433 |
| 2.000 | -0.044 | -0.409 | 3,432 |
| 3.000 | -0.049 | -0.459 | 3,431 |
| 5.000 | -0.057 | -0.542 | 3,429 |
| 10.000 | -0.064 | -0.611 | 3,424 |
| 20.000 | -0.068 | -0.659 | 3,414 |
| 40.000 | -0.064 | -0.665 | 3,394 |
| 60.000 | -0.058 | -0.675 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-70.55%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-4.111`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.301 | 0.729 | 1.784 | 3,429 |
| 2.000 | 0.005 | 1.169 | 0.662 | 1.765 | 3,429 |
| 3.000 | 0.004 | 1.012 | 0.638 | 1.587 | 3,429 |
| 4.000 | 0.003 | 0.770 | 0.639 | 1.205 | 3,429 |
| 5.000 | 0.000 | 0.115 | 0.698 | 0.165 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.511 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.499 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.536 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.746 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.524 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.528 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.531 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.011 | 0.141 |
| fold_02_2020 | 10 | -0.002 | -0.029 |
| fold_03_2021 | 10 | 0.001 | 0.013 |
| fold_04_2022 | 10 | -0.002 | -0.025 |
| fold_05_2023 | 8 | -0.008 | -0.094 |
| fold_06_2024 | 10 | 0.006 | 0.071 |
| fold_07_2025 | 10 | 0.003 | 0.026 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `1`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
