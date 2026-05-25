# Factor Card: rev_return_10d

## Basic Info
- Category: `Reversal`
- Signal direction in strategy: `high_is_good`
- Raw expression: `0 - (Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 11) - 1)`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `0.302`
- 10d Rank ICIR: `0.300`
- 20d Rank ICIR: `0.362`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | 0.563 | 0.306 | 0.680 | 1 | 1 | True | True | False |  |
| fold_02_2020 | 0.537 | 0.496 | 0.327 | 1 | 1 | True | True | False |  |
| fold_03_2021 | 0.499 | 0.498 | 0.488 | 1 | 1 | True | True | False |  |
| fold_04_2022 | 0.528 | 0.401 | 0.493 | 1 | 1 | True | True | False |  |
| fold_05_2023 | 0.434 | 0.491 | 0.432 | 1 | 1 | True | True | False |  |
| fold_06_2024 | 0.405 | 0.460 | 0.256 | 1 | 1 | True | True | False |  |
| fold_07_2025 | 0.455 | 0.313 | 0.820 | 1 | 1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | 0.043 | 0.302 | 60.08% | 3,429 |
| size_neutral | 0.044 | 0.350 | 61.53% | 3,429 |
| industry_neutral | 0.044 | 0.406 | 64.16% | 3,429 |
| size_industry_neutral | 0.045 | 0.469 | 65.56% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | 0.049 | 0.407 | 66.67% | 243 |
| 2013.000 | 0.050 | 0.544 | 61.76% | 238 |
| 2014.000 | 0.043 | 0.503 | 63.27% | 245 |
| 2015.000 | 0.092 | 0.815 | 71.72% | 244 |
| 2016.000 | 0.064 | 0.595 | 66.80% | 244 |
| 2017.000 | 0.025 | 0.254 | 59.84% | 244 |
| 2018.000 | 0.037 | 0.356 | 65.02% | 243 |
| 2019.000 | 0.057 | 0.680 | 72.54% | 244 |
| 2020.000 | 0.027 | 0.327 | 57.61% | 243 |
| 2021.000 | 0.035 | 0.488 | 60.91% | 243 |
| 2022.000 | 0.034 | 0.493 | 71.49% | 242 |
| 2023.000 | 0.034 | 0.432 | 73.97% | 242 |
| 2024.000 | 0.033 | 0.256 | 62.40% | 242 |
| 2025.000 | 0.054 | 0.820 | 66.26% | 243 |
| 2026.000 | 0.016 | 0.220 | 44.83% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| 0.053 | 0.796 |
| 0.054 | 0.807 |
| 0.054 | 0.808 |
| 0.054 | 0.808 |
| 0.053 | 0.799 |
| 0.053 | 0.789 |
| 0.052 | 0.777 |
| 0.051 | 0.772 |
| 0.050 | 0.762 |
| 0.049 | 0.732 |
| 0.048 | 0.721 |
| 0.047 | 0.709 |
| 0.047 | 0.707 |
| 0.047 | 0.701 |
| 0.047 | 0.699 |
| 0.046 | 0.693 |
| 0.046 | 0.688 |
| 0.046 | 0.685 |
| 0.046 | 0.688 |
| 0.046 | 0.689 |
| 0.045 | 0.685 |
| 0.045 | 0.685 |
| 0.045 | 0.685 |
| 0.045 | 0.683 |

## IC Decay
- Best horizon by |ICIR|: `20`
- Peak ICIR: `0.522`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | 0.038 | 0.385 | 3,433 |
| 2.000 | 0.041 | 0.416 | 3,432 |
| 3.000 | 0.044 | 0.448 | 3,431 |
| 5.000 | 0.045 | 0.469 | 3,429 |
| 10.000 | 0.045 | 0.493 | 3,424 |
| 20.000 | 0.050 | 0.572 | 3,414 |
| 40.000 | 0.043 | 0.540 | 3,394 |
| 60.000 | 0.038 | 0.487 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `213.60%`
- Long-short total diagnostic return: `567822350.00%`
- Long-short Sharpe: `4.555`
- Monotonic: `False`
- Monotonic Spearman: `0.700`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | -0.000 | -0.053 | 0.669 | -0.079 | 3,429 |
| 2.000 | 0.004 | 0.921 | 0.639 | 1.441 | 3,429 |
| 3.000 | 0.005 | 1.141 | 0.649 | 1.759 | 3,429 |
| 4.000 | 0.005 | 1.256 | 0.677 | 1.857 | 3,429 |
| 5.000 | 0.004 | 1.126 | 0.721 | 1.560 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.515 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.610 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.654 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.675 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.512 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.499 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.607 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | -0.011 | -0.169 |
| fold_02_2020 | 10 | 0.015 | 0.315 |
| fold_03_2021 | 10 | 0.016 | 0.333 |
| fold_04_2022 | 10 | 0.008 | 0.152 |
| fold_05_2023 | 10 | -0.006 | -0.138 |
| fold_06_2024 | 10 | 0.004 | 0.086 |
| fold_07_2025 | 10 | 0.006 | 0.090 |

## Risks
- Quantile monotonicity is weak in the 5d strategy-horizon diagnostic.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
