# Factor Card: tech_price_to_ma20

## Basic Info
- Category: `Technical`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Ref(($close * $adj_factor), 1) / Mean(($close * $adj_factor), 20) - 1`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `-0.335`
- 10d Rank ICIR: `-0.341`
- 20d Rank ICIR: `-0.400`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.602 | -0.376 | -0.705 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.573 | -0.555 | -0.356 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.537 | -0.522 | -0.497 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.568 | -0.422 | -0.500 | -1 | -1 | True | True | False |  |
| fold_05_2023 | -0.478 | -0.499 | -0.424 | -1 | -1 | True | True | False |  |
| fold_06_2024 | -0.450 | -0.461 | -0.347 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.490 | -0.366 | -0.784 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.049 | -0.335 | 60.95% | 3,429 |
| size_neutral | -0.051 | -0.384 | 62.20% | 3,429 |
| industry_neutral | -0.050 | -0.443 | 65.35% | 3,429 |
| size_industry_neutral | -0.052 | -0.508 | 66.99% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.060 | -0.470 | 72.02% | 243 |
| 2013.000 | -0.062 | -0.628 | 63.87% | 238 |
| 2014.000 | -0.047 | -0.514 | 63.27% | 245 |
| 2015.000 | -0.099 | -0.819 | 72.54% | 244 |
| 2016.000 | -0.071 | -0.619 | 70.08% | 244 |
| 2017.000 | -0.033 | -0.315 | 60.66% | 244 |
| 2018.000 | -0.046 | -0.437 | 69.55% | 243 |
| 2019.000 | -0.062 | -0.705 | 72.54% | 244 |
| 2020.000 | -0.032 | -0.356 | 57.61% | 243 |
| 2021.000 | -0.040 | -0.497 | 59.26% | 243 |
| 2022.000 | -0.037 | -0.500 | 73.55% | 242 |
| 2023.000 | -0.034 | -0.424 | 71.49% | 242 |
| 2024.000 | -0.045 | -0.347 | 63.64% | 242 |
| 2025.000 | -0.058 | -0.784 | 69.96% | 243 |
| 2026.000 | -0.013 | -0.194 | 48.28% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.056 | -0.758 |
| -0.057 | -0.764 |
| -0.057 | -0.764 |
| -0.057 | -0.763 |
| -0.056 | -0.755 |
| -0.056 | -0.746 |
| -0.055 | -0.734 |
| -0.054 | -0.728 |
| -0.053 | -0.720 |
| -0.051 | -0.694 |
| -0.051 | -0.689 |
| -0.050 | -0.681 |
| -0.050 | -0.682 |
| -0.050 | -0.688 |
| -0.051 | -0.692 |
| -0.050 | -0.688 |
| -0.050 | -0.686 |
| -0.050 | -0.681 |
| -0.050 | -0.679 |
| -0.049 | -0.680 |
| -0.048 | -0.678 |
| -0.048 | -0.677 |
| -0.048 | -0.677 |
| -0.047 | -0.673 |

## IC Decay
- Best horizon by |ICIR|: `20`
- Peak ICIR: `0.544`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.043 | -0.403 | 3,433 |
| 2.000 | -0.047 | -0.441 | 3,432 |
| 3.000 | -0.051 | -0.482 | 3,431 |
| 5.000 | -0.052 | -0.508 | 3,429 |
| 10.000 | -0.052 | -0.536 | 3,424 |
| 20.000 | -0.056 | -0.605 | 3,414 |
| 40.000 | -0.048 | -0.554 | 3,394 |
| 60.000 | -0.041 | -0.501 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `0.00%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-5.050`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.256 | 0.730 | 1.720 | 3,429 |
| 2.000 | 0.005 | 1.256 | 0.678 | 1.851 | 3,429 |
| 3.000 | 0.004 | 1.119 | 0.649 | 1.726 | 3,429 |
| 4.000 | 0.003 | 0.880 | 0.639 | 1.378 | 3,429 |
| 5.000 | -0.001 | -0.145 | 0.668 | -0.217 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.627 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.693 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.741 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.764 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.624 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.609 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.693 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.009 | 0.134 |
| fold_02_2020 | 10 | -0.015 | -0.302 |
| fold_03_2021 | 10 | -0.015 | -0.307 |
| fold_04_2022 | 10 | -0.011 | -0.182 |
| fold_05_2023 | 10 | 0.008 | 0.194 |
| fold_06_2024 | 10 | -0.003 | -0.049 |
| fold_07_2025 | 10 | -0.005 | -0.075 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
