# Factor Card: liq_spread_proxy_20d

## Basic Info
- Category: `Liquidity`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean(($high - $low) / (($high + $low) / 2), 20)`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `-0.367`
- 10d Rank ICIR: `-0.426`
- 20d Rank ICIR: `-0.482`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.489 | -0.511 | -0.638 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.524 | -0.541 | -0.493 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.554 | -0.560 | -0.692 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.550 | -0.581 | -0.693 | -1 | -1 | True | True | False |  |
| fold_05_2023 | -0.560 | -0.693 | -0.792 | -1 | -1 | True | True | False |  |
| fold_06_2024 | -0.561 | -0.739 | -0.487 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.585 | -0.605 | -0.680 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.067 | -0.367 | 56.31% | 3,429 |
| size_neutral | -0.070 | -0.415 | 57.31% | 3,429 |
| industry_neutral | -0.064 | -0.499 | 60.02% | 3,429 |
| size_industry_neutral | -0.066 | -0.555 | 61.13% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.046 | -0.382 | 65.02% | 243 |
| 2013.000 | -0.047 | -0.336 | 50.84% | 238 |
| 2014.000 | -0.077 | -0.644 | 67.35% | 245 |
| 2015.000 | -0.060 | -0.454 | 63.11% | 244 |
| 2016.000 | -0.086 | -0.662 | 67.62% | 244 |
| 2017.000 | -0.065 | -0.564 | 66.39% | 244 |
| 2018.000 | -0.059 | -0.463 | 64.61% | 243 |
| 2019.000 | -0.068 | -0.638 | 62.30% | 244 |
| 2020.000 | -0.059 | -0.493 | 53.50% | 243 |
| 2021.000 | -0.069 | -0.692 | 58.85% | 243 |
| 2022.000 | -0.072 | -0.693 | 60.74% | 242 |
| 2023.000 | -0.073 | -0.792 | 59.50% | 242 |
| 2024.000 | -0.063 | -0.487 | 62.81% | 242 |
| 2025.000 | -0.075 | -0.680 | 53.91% | 243 |
| 2026.000 | -0.067 | -0.860 | 51.72% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.074 | -0.677 |
| -0.074 | -0.677 |
| -0.074 | -0.680 |
| -0.075 | -0.685 |
| -0.075 | -0.689 |
| -0.076 | -0.696 |
| -0.076 | -0.701 |
| -0.077 | -0.713 |
| -0.078 | -0.720 |
| -0.078 | -0.725 |
| -0.079 | -0.733 |
| -0.080 | -0.745 |
| -0.079 | -0.742 |
| -0.079 | -0.739 |
| -0.078 | -0.735 |
| -0.078 | -0.727 |
| -0.077 | -0.726 |
| -0.077 | -0.726 |
| -0.077 | -0.724 |
| -0.077 | -0.730 |
| -0.078 | -0.742 |
| -0.079 | -0.761 |
| -0.080 | -0.781 |
| -0.080 | -0.792 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.766`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.046 | -0.396 | 3,433 |
| 2.000 | -0.053 | -0.447 | 3,432 |
| 3.000 | -0.058 | -0.487 | 3,431 |
| 5.000 | -0.066 | -0.555 | 3,429 |
| 10.000 | -0.076 | -0.650 | 3,424 |
| 20.000 | -0.086 | -0.741 | 3,414 |
| 40.000 | -0.099 | -0.909 | 3,394 |
| 60.000 | -0.109 | -1.113 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-63.30%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-3.147`
- Monotonic: `True`
- Monotonic Spearman: `-0.900`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 1.115 | 0.603 | 1.848 | 3,429 |
| 2.000 | 0.005 | 1.155 | 0.641 | 1.801 | 3,429 |
| 3.000 | 0.004 | 1.073 | 0.662 | 1.622 | 3,429 |
| 4.000 | 0.003 | 0.863 | 0.691 | 1.249 | 3,429 |
| 5.000 | 0.001 | 0.160 | 0.761 | 0.211 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.697 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.686 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.720 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.729 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.728 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.737 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.716 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.003 | 0.037 |
| fold_02_2020 | 10 | -0.011 | -0.165 |
| fold_03_2021 | 10 | -0.009 | -0.146 |
| fold_04_2022 | 7 | -0.017 | -0.243 |
| fold_05_2023 | 8 | -0.022 | -0.308 |
| fold_06_2024 | 5 | -0.027 | -0.368 |
| fold_07_2025 | 7 | -0.014 | -0.181 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
