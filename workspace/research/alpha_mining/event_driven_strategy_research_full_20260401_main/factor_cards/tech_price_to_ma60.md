# Factor Card: tech_price_to_ma60

## Basic Info
- Category: `Technical`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Ref(($close * $adj_factor), 1) / Mean(($close * $adj_factor), 60) - 1`

## Screening Snapshot
- Grade: `A (Graduated)`
- 5d Rank ICIR: `-0.386`
- 10d Rank ICIR: `-0.437`
- 20d Rank ICIR: `-0.481`
- Monotonic: `True`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.661 | -0.355 | -0.611 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.611 | -0.501 | -0.330 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.590 | -0.468 | -0.550 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.578 | -0.437 | -0.592 | -1 | -1 | True | True | False |  |
| fold_05_2023 | -0.451 | -0.571 | -0.287 | -1 | -1 | True | True | False |  |
| fold_06_2024 | -0.431 | -0.436 | -0.401 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.491 | -0.345 | -0.713 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.062 | -0.386 | 60.83% | 3,429 |
| size_neutral | -0.060 | -0.419 | 61.39% | 3,429 |
| industry_neutral | -0.058 | -0.469 | 64.16% | 3,429 |
| size_industry_neutral | -0.057 | -0.523 | 65.24% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.071 | -0.535 | 72.02% | 243 |
| 2013.000 | -0.057 | -0.503 | 57.98% | 238 |
| 2014.000 | -0.064 | -0.698 | 67.76% | 245 |
| 2015.000 | -0.119 | -1.035 | 81.56% | 244 |
| 2016.000 | -0.071 | -0.636 | 68.85% | 244 |
| 2017.000 | -0.036 | -0.305 | 60.25% | 244 |
| 2018.000 | -0.046 | -0.408 | 66.67% | 243 |
| 2019.000 | -0.060 | -0.611 | 67.62% | 244 |
| 2020.000 | -0.032 | -0.330 | 54.73% | 243 |
| 2021.000 | -0.052 | -0.550 | 59.26% | 243 |
| 2022.000 | -0.053 | -0.592 | 73.14% | 242 |
| 2023.000 | -0.025 | -0.287 | 61.57% | 242 |
| 2024.000 | -0.056 | -0.401 | 64.46% | 242 |
| 2025.000 | -0.062 | -0.713 | 59.67% | 243 |
| 2026.000 | -0.024 | -0.510 | 44.83% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.061 | -0.710 |
| -0.061 | -0.710 |
| -0.061 | -0.710 |
| -0.061 | -0.709 |
| -0.061 | -0.703 |
| -0.061 | -0.703 |
| -0.060 | -0.694 |
| -0.060 | -0.687 |
| -0.059 | -0.682 |
| -0.058 | -0.673 |
| -0.058 | -0.667 |
| -0.057 | -0.663 |
| -0.058 | -0.675 |
| -0.059 | -0.694 |
| -0.060 | -0.712 |
| -0.060 | -0.718 |
| -0.061 | -0.733 |
| -0.061 | -0.732 |
| -0.060 | -0.728 |
| -0.059 | -0.731 |
| -0.058 | -0.737 |
| -0.057 | -0.735 |
| -0.056 | -0.731 |
| -0.055 | -0.724 |

## IC Decay
- Best horizon by |ICIR|: `20`
- Peak ICIR: `0.504`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.041 | -0.373 | 3,433 |
| 2.000 | -0.046 | -0.417 | 3,432 |
| 3.000 | -0.052 | -0.467 | 3,431 |
| 5.000 | -0.057 | -0.523 | 3,429 |
| 10.000 | -0.063 | -0.580 | 3,424 |
| 20.000 | -0.066 | -0.623 | 3,414 |
| 40.000 | -0.058 | -0.599 | 3,394 |
| 60.000 | -0.052 | -0.573 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `0.00%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-5.020`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.006 | 1.396 | 0.738 | 1.891 | 3,429 |
| 2.000 | 0.005 | 1.229 | 0.675 | 1.822 | 3,429 |
| 3.000 | 0.004 | 1.042 | 0.644 | 1.617 | 3,429 |
| 4.000 | 0.003 | 0.812 | 0.635 | 1.278 | 3,429 |
| 5.000 | -0.000 | -0.113 | 0.676 | -0.168 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.644 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.622 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.656 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.711 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.781 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.652 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.645 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.018 | 0.234 |
| fold_02_2020 | 10 | 0.005 | 0.073 |
| fold_03_2021 | 10 | 0.006 | 0.091 |
| fold_04_2022 | 10 | -0.006 | -0.098 |
| fold_05_2023 | 9 | 0.002 | 0.040 |
| fold_06_2024 | 10 | 0.011 | 0.157 |
| fold_07_2025 | 10 | 0.016 | 0.186 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
