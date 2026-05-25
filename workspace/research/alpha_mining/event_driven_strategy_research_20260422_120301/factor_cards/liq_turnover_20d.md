# Factor Card: liq_turnover_20d

## Basic Info
- Category: `Liquidity`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean(Ref($turnover_rate, 1), 20)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.333`
- 10d Rank ICIR: `-0.412`
- 20d Rank ICIR: `-0.497`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.636 | -0.615 | -0.844 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.621 | -0.649 | -0.768 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.575 | -0.807 | -0.831 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.575 | -0.796 | -0.544 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.629 | -0.663 | -0.930 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.059 | -0.333 | 59.43% | 2,948 |
| size_neutral | -0.068 | -0.473 | 61.70% | 2,948 |
| industry_neutral | -0.051 | -0.508 | 62.55% | 2,948 |
| size_industry_neutral | -0.059 | -0.679 | 65.16% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.068 | -0.830 | 66.53% | 245 |
| 2015.000 | -0.061 | -0.791 | 74.18% | 244 |
| 2016.000 | -0.079 | -0.774 | 63.52% | 244 |
| 2017.000 | -0.047 | -0.474 | 65.98% | 244 |
| 2018.000 | -0.049 | -0.442 | 62.14% | 243 |
| 2019.000 | -0.058 | -0.757 | 68.03% | 244 |
| 2020.000 | -0.051 | -0.514 | 64.61% | 243 |
| 2021.000 | -0.064 | -0.844 | 65.84% | 243 |
| 2022.000 | -0.057 | -0.768 | 69.01% | 242 |
| 2023.000 | -0.054 | -0.831 | 57.02% | 242 |
| 2024.000 | -0.045 | -0.544 | 64.05% | 242 |
| 2025.000 | -0.071 | -0.930 | 61.32% | 243 |
| 2026.000 | -0.065 | -0.852 | 62.07% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.070 | -0.922 |
| -0.071 | -0.922 |
| -0.071 | -0.923 |
| -0.071 | -0.931 |
| -0.072 | -0.937 |
| -0.072 | -0.946 |
| -0.073 | -0.952 |
| -0.073 | -0.963 |
| -0.073 | -0.970 |
| -0.074 | -0.975 |
| -0.074 | -0.980 |
| -0.075 | -0.989 |
| -0.074 | -0.981 |
| -0.074 | -0.976 |
| -0.073 | -0.968 |
| -0.073 | -0.956 |
| -0.072 | -0.957 |
| -0.072 | -0.957 |
| -0.072 | -0.956 |
| -0.072 | -0.961 |
| -0.073 | -0.969 |
| -0.073 | -0.986 |
| -0.074 | -1.001 |
| -0.074 | -1.008 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `1.170`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.035 | -0.398 | 2,952 |
| 2.000 | -0.044 | -0.497 | 2,951 |
| 3.000 | -0.050 | -0.566 | 2,950 |
| 5.000 | -0.059 | -0.679 | 2,948 |
| 10.000 | -0.073 | -0.844 | 2,943 |
| 20.000 | -0.088 | -1.008 | 2,933 |
| 40.000 | -0.106 | -1.259 | 2,913 |
| 60.000 | -0.119 | -1.581 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-75.88%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-5.691`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.006 | 1.431 | 0.687 | 2.083 | 2,948 |
| 2.000 | 0.004 | 1.119 | 0.660 | 1.696 | 2,948 |
| 3.000 | 0.004 | 0.954 | 0.649 | 1.470 | 2,948 |
| 4.000 | 0.003 | 0.798 | 0.672 | 1.187 | 2,948 |
| 5.000 | 0.000 | 0.050 | 0.786 | 0.063 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.812 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.802 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.910 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.903 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.903 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 8 | 0.005 | 0.104 |
| fold_02_2022 | 6 | -0.004 | -0.082 |
| fold_03_2023 | 3 | -0.007 | -0.179 |
| fold_04_2024 | 3 | -0.003 | -0.066 |
| fold_05_2025 | 4 | 0.016 | 0.262 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
