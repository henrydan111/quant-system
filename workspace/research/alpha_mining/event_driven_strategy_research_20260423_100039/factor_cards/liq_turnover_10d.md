# Factor Card: liq_turnover_10d

## Basic Info
- Category: `Liquidity`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean(Ref($turnover_rate, 1), 10)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.366`
- 10d Rank ICIR: `-0.446`
- 20d Rank ICIR: `-0.529`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.701 | -0.702 | -0.895 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.698 | -0.703 | -0.811 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.644 | -0.853 | -0.877 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.636 | -0.840 | -0.632 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.693 | -0.732 | -1.121 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.063 | -0.366 | 61.13% | 2,948 |
| size_neutral | -0.074 | -0.520 | 63.53% | 2,948 |
| industry_neutral | -0.056 | -0.571 | 64.28% | 2,948 |
| size_industry_neutral | -0.063 | -0.752 | 67.30% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.070 | -0.888 | 65.31% | 245 |
| 2015.000 | -0.068 | -0.883 | 73.77% | 244 |
| 2016.000 | -0.084 | -0.872 | 65.57% | 244 |
| 2017.000 | -0.049 | -0.512 | 68.44% | 244 |
| 2018.000 | -0.054 | -0.498 | 64.61% | 243 |
| 2019.000 | -0.066 | -0.882 | 70.90% | 244 |
| 2020.000 | -0.054 | -0.570 | 67.08% | 243 |
| 2021.000 | -0.065 | -0.895 | 65.84% | 243 |
| 2022.000 | -0.060 | -0.811 | 70.25% | 242 |
| 2023.000 | -0.056 | -0.877 | 62.40% | 242 |
| 2024.000 | -0.052 | -0.632 | 68.18% | 242 |
| 2025.000 | -0.079 | -1.121 | 66.67% | 243 |
| 2026.000 | -0.065 | -0.889 | 55.17% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.079 | -1.106 |
| -0.079 | -1.105 |
| -0.079 | -1.106 |
| -0.079 | -1.114 |
| -0.080 | -1.118 |
| -0.080 | -1.125 |
| -0.080 | -1.128 |
| -0.080 | -1.134 |
| -0.080 | -1.135 |
| -0.081 | -1.138 |
| -0.081 | -1.140 |
| -0.081 | -1.144 |
| -0.081 | -1.134 |
| -0.080 | -1.128 |
| -0.080 | -1.119 |
| -0.079 | -1.104 |
| -0.079 | -1.106 |
| -0.078 | -1.108 |
| -0.078 | -1.106 |
| -0.078 | -1.110 |
| -0.079 | -1.117 |
| -0.079 | -1.135 |
| -0.080 | -1.153 |
| -0.080 | -1.161 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `1.228`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.039 | -0.453 | 2,952 |
| 2.000 | -0.048 | -0.559 | 2,951 |
| 3.000 | -0.054 | -0.633 | 2,950 |
| 5.000 | -0.063 | -0.752 | 2,948 |
| 10.000 | -0.077 | -0.924 | 2,943 |
| 20.000 | -0.092 | -1.075 | 2,933 |
| 40.000 | -0.109 | -1.299 | 2,913 |
| 60.000 | -0.120 | -1.593 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `0.00%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-6.300`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.006 | 1.453 | 0.686 | 2.119 | 2,948 |
| 2.000 | 0.005 | 1.145 | 0.662 | 1.731 | 2,948 |
| 3.000 | 0.004 | 0.981 | 0.651 | 1.507 | 2,948 |
| 4.000 | 0.003 | 0.827 | 0.673 | 1.229 | 2,948 |
| 5.000 | -0.000 | -0.055 | 0.782 | -0.070 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.849 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.844 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.949 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.945 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.947 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 6 | -0.001 | -0.033 |
| fold_02_2022 | 6 | 0.002 | 0.043 |
| fold_03_2023 | 3 | -0.004 | -0.098 |
| fold_04_2024 | 4 | 0.012 | 0.291 |
| fold_05_2025 | 2 | -0.002 | -0.037 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
