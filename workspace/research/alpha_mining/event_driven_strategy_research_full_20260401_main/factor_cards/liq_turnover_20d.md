# Factor Card: liq_turnover_20d

## Basic Info
- Category: `Liquidity`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean($turnover_rate, 20)`

## Screening Snapshot
- Grade: `A (Graduated)`
- 5d Rank ICIR: `-0.332`
- 10d Rank ICIR: `-0.405`
- 20d Rank ICIR: `-0.473`
- Monotonic: `True`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.731 | -0.488 | -0.808 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.706 | -0.602 | -0.540 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.677 | -0.652 | -0.871 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.664 | -0.675 | -0.801 | -1 | -1 | True | True | False |  |
| fold_05_2023 | -0.611 | -0.836 | -0.874 | -1 | -1 | True | True | False |  |
| fold_06_2024 | -0.608 | -0.833 | -0.587 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.662 | -0.706 | -0.989 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.059 | -0.332 | 59.84% | 3,429 |
| size_neutral | -0.069 | -0.479 | 62.20% | 3,429 |
| industry_neutral | -0.054 | -0.535 | 63.37% | 3,429 |
| size_industry_neutral | -0.061 | -0.698 | 65.68% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.056 | -0.604 | 69.96% | 243 |
| 2013.000 | -0.056 | -0.571 | 59.66% | 238 |
| 2014.000 | -0.072 | -0.875 | 67.35% | 245 |
| 2015.000 | -0.066 | -0.858 | 74.18% | 244 |
| 2016.000 | -0.083 | -0.818 | 65.16% | 244 |
| 2017.000 | -0.050 | -0.503 | 67.21% | 244 |
| 2018.000 | -0.053 | -0.476 | 62.96% | 243 |
| 2019.000 | -0.062 | -0.808 | 68.03% | 244 |
| 2020.000 | -0.054 | -0.540 | 64.61% | 243 |
| 2021.000 | -0.066 | -0.871 | 65.84% | 243 |
| 2022.000 | -0.059 | -0.801 | 69.83% | 242 |
| 2023.000 | -0.056 | -0.874 | 57.85% | 242 |
| 2024.000 | -0.049 | -0.587 | 65.29% | 242 |
| 2025.000 | -0.075 | -0.989 | 62.14% | 243 |
| 2026.000 | -0.068 | -0.871 | 58.62% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.075 | -0.979 |
| -0.075 | -0.979 |
| -0.075 | -0.980 |
| -0.075 | -0.987 |
| -0.076 | -0.994 |
| -0.076 | -1.002 |
| -0.077 | -1.008 |
| -0.077 | -1.019 |
| -0.077 | -1.024 |
| -0.078 | -1.028 |
| -0.078 | -1.034 |
| -0.078 | -1.041 |
| -0.078 | -1.033 |
| -0.078 | -1.028 |
| -0.077 | -1.020 |
| -0.076 | -1.007 |
| -0.076 | -1.008 |
| -0.076 | -1.009 |
| -0.076 | -1.007 |
| -0.076 | -1.012 |
| -0.076 | -1.020 |
| -0.077 | -1.037 |
| -0.077 | -1.053 |
| -0.078 | -1.061 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `1.096`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.037 | -0.413 | 3,433 |
| 2.000 | -0.045 | -0.511 | 3,432 |
| 3.000 | -0.052 | -0.583 | 3,431 |
| 5.000 | -0.061 | -0.698 | 3,429 |
| 10.000 | -0.075 | -0.862 | 3,424 |
| 20.000 | -0.090 | -1.007 | 3,414 |
| 40.000 | -0.105 | -1.225 | 3,394 |
| 60.000 | -0.117 | -1.522 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `0.00%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-5.952`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.006 | 1.471 | 0.665 | 2.214 | 3,429 |
| 2.000 | 0.005 | 1.137 | 0.641 | 1.774 | 3,429 |
| 3.000 | 0.004 | 0.943 | 0.631 | 1.495 | 3,429 |
| 4.000 | 0.003 | 0.779 | 0.653 | 1.194 | 3,429 |
| 5.000 | 0.000 | 0.035 | 0.766 | 0.045 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.831 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.827 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.812 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.802 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.910 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.903 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.903 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.003 | 0.054 |
| fold_02_2020 | 8 | -0.007 | -0.146 |
| fold_03_2021 | 8 | -0.007 | -0.174 |
| fold_04_2022 | 4 | -0.010 | -0.202 |
| fold_05_2023 | 3 | -0.004 | -0.105 |
| fold_06_2024 | 3 | 0.001 | 0.013 |
| fold_07_2025 | 3 | 0.009 | 0.141 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
