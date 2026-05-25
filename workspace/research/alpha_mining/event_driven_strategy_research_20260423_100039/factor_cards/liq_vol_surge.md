# Factor Card: liq_vol_surge

## Basic Info
- Category: `Liquidity`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean(Ref($vol, 1), 5) / Mean(Ref($vol, 1), 60)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.389`
- 10d Rank ICIR: `-0.424`
- 20d Rank ICIR: `-0.453`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.577 | -0.530 | -0.543 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.669 | -0.381 | -0.775 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.572 | -0.649 | -0.363 | -1 | -1 | True | True | True |  |
| fold_04_2024 | -0.539 | -0.537 | -0.661 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.610 | -0.507 | -0.844 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.041 | -0.389 | 64.79% | 2,948 |
| size_neutral | -0.043 | -0.438 | 66.42% | 2,948 |
| industry_neutral | -0.038 | -0.521 | 69.20% | 2,948 |
| size_industry_neutral | -0.039 | -0.582 | 70.59% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.027 | -0.392 | 64.49% | 245 |
| 2015.000 | -0.059 | -0.710 | 74.59% | 244 |
| 2016.000 | -0.049 | -0.703 | 75.00% | 244 |
| 2017.000 | -0.032 | -0.420 | 72.13% | 244 |
| 2018.000 | -0.041 | -0.746 | 81.07% | 243 |
| 2019.000 | -0.053 | -0.900 | 81.15% | 244 |
| 2020.000 | -0.018 | -0.255 | 61.73% | 243 |
| 2021.000 | -0.031 | -0.543 | 63.37% | 243 |
| 2022.000 | -0.039 | -0.775 | 75.62% | 242 |
| 2023.000 | -0.023 | -0.363 | 65.70% | 242 |
| 2024.000 | -0.042 | -0.661 | 71.49% | 242 |
| 2025.000 | -0.054 | -0.844 | 64.20% | 243 |
| 2026.000 | -0.021 | -0.363 | 41.38% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.053 | -0.840 |
| -0.053 | -0.840 |
| -0.053 | -0.843 |
| -0.054 | -0.848 |
| -0.053 | -0.844 |
| -0.053 | -0.837 |
| -0.053 | -0.829 |
| -0.052 | -0.821 |
| -0.051 | -0.808 |
| -0.050 | -0.785 |
| -0.049 | -0.771 |
| -0.049 | -0.764 |
| -0.049 | -0.768 |
| -0.049 | -0.781 |
| -0.050 | -0.789 |
| -0.050 | -0.793 |
| -0.050 | -0.789 |
| -0.049 | -0.781 |
| -0.048 | -0.774 |
| -0.048 | -0.774 |
| -0.047 | -0.774 |
| -0.047 | -0.773 |
| -0.047 | -0.773 |
| -0.047 | -0.772 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.674`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.032 | -0.474 | 2,952 |
| 2.000 | -0.035 | -0.526 | 2,951 |
| 3.000 | -0.038 | -0.560 | 2,950 |
| 5.000 | -0.039 | -0.582 | 2,948 |
| 10.000 | -0.042 | -0.644 | 2,943 |
| 20.000 | -0.043 | -0.671 | 2,933 |
| 40.000 | -0.040 | -0.652 | 2,913 |
| 60.000 | -0.036 | -0.608 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-59.12%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-4.659`
- Monotonic: `False`
- Monotonic Spearman: `-0.700`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 1.057 | 0.700 | 1.510 | 2,948 |
| 2.000 | 0.004 | 1.079 | 0.683 | 1.578 | 2,948 |
| 3.000 | 0.004 | 1.058 | 0.673 | 1.573 | 2,948 |
| 4.000 | 0.004 | 0.977 | 0.675 | 1.447 | 2,948 |
| 5.000 | 0.001 | 0.182 | 0.712 | 0.255 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.561 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.540 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.565 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.611 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.620 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 10 | 0.005 | 0.110 |
| fold_02_2022 | 10 | 0.007 | 0.152 |
| fold_03_2023 | 9 | 0.005 | 0.112 |
| fold_04_2024 | 10 | 0.004 | 0.118 |
| fold_05_2025 | 8 | 0.004 | 0.074 |

## Risks
- Quantile monotonicity is weak in the 5d strategy-horizon diagnostic.

## Conclusion
- Final decision: `reserve`
- Selected folds: `1`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
