# Factor Card: tech_price_to_ma20

## Basic Info
- Category: `Technical`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Ref(($close * $adj_factor), 1) / Mean(Ref(($close * $adj_factor), 1), 20) - 1`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.333`
- 10d Rank ICIR: `-0.350`
- 20d Rank ICIR: `-0.412`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.543 | -0.534 | -0.509 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.577 | -0.430 | -0.513 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.488 | -0.511 | -0.431 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.461 | -0.471 | -0.362 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.503 | -0.378 | -0.798 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.049 | -0.333 | 60.11% | 2,948 |
| size_neutral | -0.051 | -0.390 | 61.74% | 2,948 |
| industry_neutral | -0.049 | -0.435 | 64.69% | 2,948 |
| size_industry_neutral | -0.051 | -0.514 | 66.15% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.048 | -0.518 | 60.41% | 245 |
| 2015.000 | -0.099 | -0.817 | 70.49% | 244 |
| 2016.000 | -0.072 | -0.628 | 69.26% | 244 |
| 2017.000 | -0.034 | -0.320 | 59.43% | 244 |
| 2018.000 | -0.048 | -0.452 | 68.31% | 243 |
| 2019.000 | -0.065 | -0.724 | 72.54% | 244 |
| 2020.000 | -0.032 | -0.360 | 58.44% | 243 |
| 2021.000 | -0.041 | -0.509 | 60.49% | 243 |
| 2022.000 | -0.039 | -0.513 | 73.14% | 242 |
| 2023.000 | -0.035 | -0.431 | 70.25% | 242 |
| 2024.000 | -0.047 | -0.362 | 64.05% | 242 |
| 2025.000 | -0.060 | -0.798 | 69.14% | 243 |
| 2026.000 | -0.013 | -0.199 | 48.28% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.058 | -0.771 |
| -0.059 | -0.777 |
| -0.059 | -0.777 |
| -0.059 | -0.776 |
| -0.058 | -0.768 |
| -0.058 | -0.759 |
| -0.056 | -0.747 |
| -0.055 | -0.741 |
| -0.054 | -0.733 |
| -0.053 | -0.710 |
| -0.052 | -0.704 |
| -0.052 | -0.696 |
| -0.052 | -0.699 |
| -0.052 | -0.707 |
| -0.053 | -0.711 |
| -0.052 | -0.707 |
| -0.052 | -0.707 |
| -0.052 | -0.702 |
| -0.052 | -0.700 |
| -0.051 | -0.701 |
| -0.050 | -0.699 |
| -0.050 | -0.697 |
| -0.049 | -0.697 |
| -0.049 | -0.692 |

## IC Decay
- Best horizon by |ICIR|: `20`
- Peak ICIR: `0.548`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.041 | -0.389 | 2,952 |
| 2.000 | -0.045 | -0.434 | 2,951 |
| 3.000 | -0.049 | -0.477 | 2,950 |
| 5.000 | -0.051 | -0.514 | 2,948 |
| 10.000 | -0.054 | -0.554 | 2,943 |
| 20.000 | -0.058 | -0.623 | 2,933 |
| 40.000 | -0.050 | -0.575 | 2,913 |
| 60.000 | -0.044 | -0.528 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-75.88%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-4.851`
- Monotonic: `True`
- Monotonic Spearman: `-0.900`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.218 | 0.752 | 1.619 | 2,948 |
| 2.000 | 0.005 | 1.268 | 0.698 | 1.816 | 2,948 |
| 3.000 | 0.005 | 1.134 | 0.668 | 1.698 | 2,948 |
| 4.000 | 0.004 | 0.902 | 0.657 | 1.373 | 2,948 |
| 5.000 | -0.001 | -0.170 | 0.689 | -0.247 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.569 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.853 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.848 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.840 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.813 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 10 | 0.000 | 0.009 |
| fold_02_2022 | 10 | -0.017 | -0.267 |
| fold_03_2023 | 10 | -0.013 | -0.239 |
| fold_04_2024 | 10 | -0.018 | -0.338 |
| fold_05_2025 | 10 | -0.024 | -0.319 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
