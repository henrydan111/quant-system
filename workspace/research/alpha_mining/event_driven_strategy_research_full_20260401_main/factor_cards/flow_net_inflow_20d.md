# Factor Card: flow_net_inflow_20d

## Basic Info
- Category: `Capital Flow`
- Signal direction in strategy: `high_is_good`
- Raw expression: `Mean(Ref($net_mf_amount, 1), 20)`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `0.357`
- 10d Rank ICIR: `0.487`
- 20d Rank ICIR: `0.590`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | 0.117 | 0.320 | 0.345 | 1 | 1 | True | True | False |  |
| fold_02_2020 | 0.153 | 0.335 | 0.371 | 1 | 1 | True | True | False |  |
| fold_03_2021 | 0.187 | 0.355 | 0.160 | 1 | 1 | True | True | False |  |
| fold_04_2022 | 0.223 | 0.273 | 0.334 | 1 | 1 | True | True | False |  |
| fold_05_2023 | 0.303 | 0.244 | 0.570 | 1 | 1 | True | True | False |  |
| fold_06_2024 | 0.306 | 0.448 | 0.442 | 1 | 1 | True | True | False |  |
| fold_07_2025 | 0.304 | 0.471 | 0.536 | 1 | 1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | 0.033 | 0.357 | 64.25% | 3,429 |
| size_neutral | 0.025 | 0.252 | 62.06% | 3,429 |
| industry_neutral | 0.025 | 0.386 | 65.35% | 3,429 |
| size_industry_neutral | 0.019 | 0.270 | 62.15% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | 0.016 | 0.157 | 55.56% | 243 |
| 2013.000 | 0.011 | 0.204 | 57.56% | 238 |
| 2014.000 | 0.011 | 0.165 | 60.41% | 245 |
| 2015.000 | -0.008 | -0.143 | 55.74% | 244 |
| 2016.000 | 0.013 | 0.172 | 61.07% | 244 |
| 2017.000 | 0.025 | 0.313 | 59.43% | 244 |
| 2018.000 | 0.031 | 0.328 | 55.14% | 243 |
| 2019.000 | 0.028 | 0.345 | 62.30% | 244 |
| 2020.000 | 0.024 | 0.371 | 66.26% | 243 |
| 2021.000 | 0.008 | 0.160 | 60.49% | 243 |
| 2022.000 | 0.016 | 0.334 | 68.18% | 242 |
| 2023.000 | 0.027 | 0.570 | 67.36% | 242 |
| 2024.000 | 0.036 | 0.442 | 69.01% | 242 |
| 2025.000 | 0.030 | 0.536 | 70.37% | 243 |
| 2026.000 | 0.020 | 0.290 | 72.41% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| 0.031 | 0.550 |
| 0.031 | 0.550 |
| 0.031 | 0.550 |
| 0.031 | 0.552 |
| 0.031 | 0.556 |
| 0.032 | 0.560 |
| 0.032 | 0.565 |
| 0.032 | 0.575 |
| 0.033 | 0.589 |
| 0.034 | 0.604 |
| 0.034 | 0.613 |
| 0.034 | 0.623 |
| 0.034 | 0.613 |
| 0.033 | 0.600 |
| 0.032 | 0.580 |
| 0.032 | 0.572 |
| 0.031 | 0.563 |
| 0.031 | 0.557 |
| 0.031 | 0.563 |
| 0.032 | 0.575 |
| 0.032 | 0.589 |
| 0.032 | 0.608 |
| 0.033 | 0.632 |
| 0.033 | 0.645 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.764`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | 0.005 | 0.076 | 3,433 |
| 2.000 | 0.010 | 0.145 | 3,432 |
| 3.000 | 0.013 | 0.187 | 3,431 |
| 5.000 | 0.019 | 0.270 | 3,429 |
| 10.000 | 0.027 | 0.397 | 3,424 |
| 20.000 | 0.034 | 0.517 | 3,414 |
| 40.000 | 0.042 | 0.663 | 3,394 |
| 60.000 | 0.048 | 0.817 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `61.88%`
- Long-short total diagnostic return: `70113.98%`
- Long-short Sharpe: `2.951`
- Monotonic: `False`
- Monotonic Spearman: `0.300`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.001 | 0.138 | 0.688 | 0.201 | 3,429 |
| 2.000 | 0.004 | 1.051 | 0.688 | 1.527 | 3,429 |
| 3.000 | 0.005 | 1.271 | 0.680 | 1.869 | 3,429 |
| 4.000 | 0.005 | 1.194 | 0.670 | 1.781 | 3,429 |
| 5.000 | 0.003 | 0.634 | 0.615 | 1.031 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.318 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.290 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.238 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.219 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.200 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.224 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.257 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.017 | 0.458 |
| fold_02_2020 | 10 | 0.018 | 0.439 |
| fold_03_2021 | 10 | 0.010 | 0.256 |
| fold_04_2022 | 10 | 0.001 | 0.022 |
| fold_05_2023 | 10 | 0.008 | 0.203 |
| fold_06_2024 | 10 | 0.009 | 0.218 |
| fold_07_2025 | 10 | 0.012 | 0.232 |

## Risks
- Quantile monotonicity is weak in the 5d strategy-horizon diagnostic.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
