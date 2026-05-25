# Factor Card: liq_log_dollar_vol

## Basic Info
- Category: `Liquidity`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Log(Mean($amount * 1000, 20))`

## Screening Snapshot
- Grade: `A (Graduated)`
- 5d Rank ICIR: `-0.542`
- 10d Rank ICIR: `-0.646`
- 20d Rank ICIR: `-0.738`
- Monotonic: `True`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.677 | -0.619 | -0.552 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.719 | -0.573 | -0.462 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.701 | -0.507 | -0.641 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.672 | -0.533 | -0.577 | -1 | -1 | True | True | False |  |
| fold_05_2023 | -0.617 | -0.607 | -0.631 | -1 | -1 | True | True | False |  |
| fold_06_2024 | -0.571 | -0.604 | -0.474 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.556 | -0.542 | -0.617 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.074 | -0.542 | 65.82% | 3,429 |
| size_neutral | -0.069 | -0.481 | 62.41% | 3,429 |
| industry_neutral | -0.068 | -0.619 | 69.47% | 3,429 |
| size_industry_neutral | -0.063 | -0.607 | 65.88% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.056 | -0.493 | 70.37% | 243 |
| 2013.000 | -0.066 | -0.647 | 65.55% | 238 |
| 2014.000 | -0.065 | -0.676 | 70.61% | 245 |
| 2015.000 | -0.066 | -0.742 | 76.23% | 244 |
| 2016.000 | -0.092 | -0.877 | 74.59% | 244 |
| 2017.000 | -0.063 | -0.661 | 72.13% | 244 |
| 2018.000 | -0.070 | -0.592 | 67.90% | 243 |
| 2019.000 | -0.064 | -0.552 | 64.34% | 244 |
| 2020.000 | -0.054 | -0.462 | 60.08% | 243 |
| 2021.000 | -0.056 | -0.641 | 58.02% | 243 |
| 2022.000 | -0.056 | -0.577 | 61.16% | 242 |
| 2023.000 | -0.058 | -0.631 | 64.88% | 242 |
| 2024.000 | -0.053 | -0.474 | 58.68% | 242 |
| 2025.000 | -0.066 | -0.617 | 59.67% | 243 |
| 2026.000 | -0.056 | -0.583 | 48.28% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.067 | -0.619 |
| -0.067 | -0.619 |
| -0.067 | -0.619 |
| -0.067 | -0.621 |
| -0.067 | -0.620 |
| -0.067 | -0.627 |
| -0.068 | -0.632 |
| -0.068 | -0.641 |
| -0.069 | -0.648 |
| -0.070 | -0.656 |
| -0.071 | -0.666 |
| -0.072 | -0.679 |
| -0.072 | -0.679 |
| -0.072 | -0.679 |
| -0.071 | -0.675 |
| -0.070 | -0.667 |
| -0.070 | -0.665 |
| -0.070 | -0.665 |
| -0.070 | -0.662 |
| -0.070 | -0.667 |
| -0.071 | -0.676 |
| -0.071 | -0.691 |
| -0.072 | -0.707 |
| -0.072 | -0.711 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `1.141`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.038 | -0.352 | 3,433 |
| 2.000 | -0.047 | -0.441 | 3,432 |
| 3.000 | -0.054 | -0.503 | 3,431 |
| 5.000 | -0.063 | -0.607 | 3,429 |
| 10.000 | -0.078 | -0.765 | 3,424 |
| 20.000 | -0.094 | -0.927 | 3,414 |
| 40.000 | -0.111 | -1.193 | 3,394 |
| 60.000 | -0.123 | -1.492 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `0.00%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-5.484`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.351 | 0.607 | 2.226 | 3,429 |
| 2.000 | 0.005 | 1.222 | 0.645 | 1.894 | 3,429 |
| 3.000 | 0.004 | 1.063 | 0.662 | 1.605 | 3,429 |
| 4.000 | 0.003 | 0.793 | 0.685 | 1.158 | 3,429 |
| 5.000 | -0.000 | -0.063 | 0.747 | -0.084 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.662 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.676 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.678 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.678 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.655 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.633 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.624 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 8 | -0.009 | -0.123 |
| fold_02_2020 | 10 | -0.017 | -0.252 |
| fold_03_2021 | 10 | -0.006 | -0.086 |
| fold_04_2022 | 7 | -0.004 | -0.057 |
| fold_05_2023 | 8 | -0.007 | -0.107 |
| fold_06_2024 | 10 | -0.004 | -0.066 |
| fold_07_2025 | 8 | -0.008 | -0.109 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
