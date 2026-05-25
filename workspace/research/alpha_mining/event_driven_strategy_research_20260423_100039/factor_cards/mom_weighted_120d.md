# Factor Card: mom_weighted_120d

## Basic Info
- Category: `Momentum`
- Signal direction in strategy: `low_is_good`
- Raw expression: `WMA((Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 2) - 1), 120)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.393`
- 10d Rank ICIR: `-0.461`
- 20d Rank ICIR: `-0.516`
- Monotonic: `True`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.590 | -0.438 | -0.505 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.568 | -0.417 | -0.601 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.433 | -0.550 | -0.311 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.397 | -0.450 | -0.409 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.453 | -0.358 | -0.785 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.060 | -0.393 | 58.07% | 2,948 |
| size_neutral | -0.059 | -0.427 | 58.68% | 2,948 |
| industry_neutral | -0.053 | -0.459 | 60.92% | 2,948 |
| size_industry_neutral | -0.052 | -0.516 | 61.26% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.060 | -0.673 | 62.04% | 245 |
| 2015.000 | -0.098 | -1.156 | 66.39% | 244 |
| 2016.000 | -0.063 | -0.737 | 65.98% | 244 |
| 2017.000 | -0.032 | -0.306 | 65.16% | 244 |
| 2018.000 | -0.033 | -0.314 | 56.38% | 243 |
| 2019.000 | -0.052 | -0.555 | 61.89% | 244 |
| 2020.000 | -0.034 | -0.333 | 53.50% | 243 |
| 2021.000 | -0.050 | -0.505 | 58.85% | 243 |
| 2022.000 | -0.053 | -0.601 | 69.83% | 242 |
| 2023.000 | -0.028 | -0.311 | 57.44% | 242 |
| 2024.000 | -0.063 | -0.409 | 63.64% | 242 |
| 2025.000 | -0.063 | -0.785 | 55.56% | 243 |
| 2026.000 | -0.019 | -0.352 | 48.28% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.062 | -0.784 |
| -0.062 | -0.783 |
| -0.062 | -0.782 |
| -0.062 | -0.783 |
| -0.062 | -0.781 |
| -0.062 | -0.787 |
| -0.062 | -0.780 |
| -0.062 | -0.784 |
| -0.062 | -0.789 |
| -0.062 | -0.788 |
| -0.062 | -0.789 |
| -0.062 | -0.795 |
| -0.062 | -0.791 |
| -0.062 | -0.786 |
| -0.061 | -0.781 |
| -0.061 | -0.772 |
| -0.060 | -0.771 |
| -0.060 | -0.773 |
| -0.060 | -0.771 |
| -0.060 | -0.770 |
| -0.059 | -0.769 |
| -0.059 | -0.771 |
| -0.059 | -0.772 |
| -0.059 | -0.763 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.500`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.035 | -0.347 | 2,952 |
| 2.000 | -0.040 | -0.394 | 2,951 |
| 3.000 | -0.045 | -0.443 | 2,950 |
| 5.000 | -0.052 | -0.516 | 2,948 |
| 10.000 | -0.060 | -0.599 | 2,943 |
| 20.000 | -0.065 | -0.659 | 2,933 |
| 40.000 | -0.064 | -0.694 | 2,913 |
| 60.000 | -0.060 | -0.715 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-70.89%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-4.097`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.257 | 0.745 | 1.687 | 2,948 |
| 2.000 | 0.005 | 1.166 | 0.678 | 1.720 | 2,948 |
| 3.000 | 0.004 | 1.054 | 0.656 | 1.606 | 2,948 |
| 4.000 | 0.003 | 0.800 | 0.662 | 1.209 | 2,948 |
| 5.000 | 0.000 | 0.072 | 0.723 | 0.100 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.482 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.623 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.608 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.634 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.604 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 10 | 0.009 | 0.125 |
| fold_02_2022 | 10 | 0.001 | 0.012 |
| fold_03_2023 | 10 | -0.001 | -0.007 |
| fold_04_2024 | 10 | 0.010 | 0.114 |
| fold_05_2025 | 10 | 0.008 | 0.077 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
