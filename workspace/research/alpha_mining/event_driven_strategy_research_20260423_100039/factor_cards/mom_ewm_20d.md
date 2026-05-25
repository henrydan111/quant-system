# Factor Card: mom_ewm_20d

## Basic Info
- Category: `Momentum`
- Signal direction in strategy: `low_is_good`
- Raw expression: `EMA((Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 2) - 1), 20)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.385`
- 10d Rank ICIR: `-0.406`
- 20d Rank ICIR: `-0.468`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.604 | -0.553 | -0.582 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.612 | -0.486 | -0.606 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.522 | -0.594 | -0.446 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.492 | -0.524 | -0.431 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.544 | -0.425 | -0.877 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.056 | -0.385 | 59.63% | 2,948 |
| size_neutral | -0.058 | -0.439 | 61.09% | 2,948 |
| industry_neutral | -0.055 | -0.487 | 64.28% | 2,948 |
| size_industry_neutral | -0.057 | -0.572 | 65.57% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.062 | -0.671 | 62.04% | 245 |
| 2015.000 | -0.096 | -0.876 | 54.92% | 244 |
| 2016.000 | -0.079 | -0.712 | 73.36% | 244 |
| 2017.000 | -0.039 | -0.357 | 61.48% | 244 |
| 2018.000 | -0.050 | -0.464 | 66.67% | 243 |
| 2019.000 | -0.066 | -0.719 | 72.54% | 244 |
| 2020.000 | -0.037 | -0.400 | 57.20% | 243 |
| 2021.000 | -0.049 | -0.582 | 59.26% | 243 |
| 2022.000 | -0.047 | -0.606 | 75.21% | 242 |
| 2023.000 | -0.036 | -0.446 | 70.66% | 242 |
| 2024.000 | -0.055 | -0.431 | 69.01% | 242 |
| 2025.000 | -0.067 | -0.877 | 67.49% | 243 |
| 2026.000 | -0.023 | -0.358 | 41.38% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.065 | -0.853 |
| -0.066 | -0.857 |
| -0.066 | -0.857 |
| -0.066 | -0.857 |
| -0.065 | -0.849 |
| -0.065 | -0.842 |
| -0.064 | -0.830 |
| -0.063 | -0.822 |
| -0.062 | -0.815 |
| -0.061 | -0.795 |
| -0.060 | -0.790 |
| -0.060 | -0.782 |
| -0.060 | -0.787 |
| -0.060 | -0.794 |
| -0.061 | -0.799 |
| -0.060 | -0.796 |
| -0.061 | -0.799 |
| -0.060 | -0.796 |
| -0.060 | -0.794 |
| -0.059 | -0.798 |
| -0.058 | -0.803 |
| -0.058 | -0.802 |
| -0.057 | -0.803 |
| -0.056 | -0.798 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.563`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.044 | -0.419 | 2,952 |
| 2.000 | -0.049 | -0.474 | 2,951 |
| 3.000 | -0.054 | -0.526 | 2,950 |
| 5.000 | -0.057 | -0.572 | 2,948 |
| 10.000 | -0.059 | -0.612 | 2,943 |
| 20.000 | -0.063 | -0.686 | 2,933 |
| 40.000 | -0.057 | -0.654 | 2,913 |
| 60.000 | -0.052 | -0.617 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-75.88%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-5.027`
- Monotonic: `True`
- Monotonic Spearman: `-0.900`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.231 | 0.751 | 1.640 | 2,948 |
| 2.000 | 0.005 | 1.286 | 0.696 | 1.847 | 2,948 |
| 3.000 | 0.005 | 1.137 | 0.665 | 1.709 | 2,948 |
| 4.000 | 0.003 | 0.880 | 0.655 | 1.343 | 2,948 |
| 5.000 | -0.001 | -0.182 | 0.697 | -0.261 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.620 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.882 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.877 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.873 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.847 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 10 | 0.002 | 0.036 |
| fold_02_2022 | 10 | -0.015 | -0.204 |
| fold_03_2023 | 10 | -0.012 | -0.180 |
| fold_04_2024 | 10 | -0.011 | -0.185 |
| fold_05_2025 | 10 | -0.016 | -0.191 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
