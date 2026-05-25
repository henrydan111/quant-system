# Factor Card: liq_turnover_f_20d

## Basic Info
- Category: `Liquidity`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean($turnover_rate_f, 20)`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `-0.393`
- 10d Rank ICIR: `-0.485`
- 20d Rank ICIR: `-0.573`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.769 | -0.547 | -0.811 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.751 | -0.633 | -0.557 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.719 | -0.665 | -0.895 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.710 | -0.689 | -0.770 | -1 | -1 | True | True | False |  |
| fold_05_2023 | -0.648 | -0.832 | -0.813 | -1 | -1 | True | True | False |  |
| fold_06_2024 | -0.645 | -0.789 | -0.613 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.676 | -0.695 | -0.930 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.067 | -0.393 | 61.91% | 3,429 |
| size_neutral | -0.075 | -0.525 | 64.36% | 3,429 |
| industry_neutral | -0.061 | -0.581 | 65.56% | 3,429 |
| size_industry_neutral | -0.067 | -0.720 | 67.34% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.064 | -0.667 | 71.19% | 243 |
| 2013.000 | -0.067 | -0.631 | 62.18% | 238 |
| 2014.000 | -0.077 | -0.853 | 68.57% | 245 |
| 2015.000 | -0.079 | -0.898 | 79.51% | 244 |
| 2016.000 | -0.092 | -0.838 | 69.26% | 244 |
| 2017.000 | -0.059 | -0.588 | 70.08% | 244 |
| 2018.000 | -0.058 | -0.512 | 64.20% | 243 |
| 2019.000 | -0.069 | -0.811 | 68.85% | 244 |
| 2020.000 | -0.059 | -0.557 | 67.08% | 243 |
| 2021.000 | -0.069 | -0.895 | 65.43% | 243 |
| 2022.000 | -0.060 | -0.770 | 69.42% | 242 |
| 2023.000 | -0.055 | -0.813 | 59.09% | 242 |
| 2024.000 | -0.054 | -0.613 | 66.12% | 242 |
| 2025.000 | -0.079 | -0.930 | 62.96% | 243 |
| 2026.000 | -0.076 | -0.940 | 55.17% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.079 | -0.924 |
| -0.079 | -0.925 |
| -0.079 | -0.925 |
| -0.080 | -0.931 |
| -0.080 | -0.937 |
| -0.081 | -0.945 |
| -0.081 | -0.951 |
| -0.081 | -0.962 |
| -0.082 | -0.969 |
| -0.082 | -0.973 |
| -0.083 | -0.978 |
| -0.083 | -0.986 |
| -0.083 | -0.981 |
| -0.082 | -0.977 |
| -0.082 | -0.969 |
| -0.081 | -0.960 |
| -0.081 | -0.961 |
| -0.081 | -0.961 |
| -0.081 | -0.960 |
| -0.081 | -0.963 |
| -0.081 | -0.970 |
| -0.082 | -0.987 |
| -0.083 | -1.004 |
| -0.083 | -1.012 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `1.226`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.041 | -0.424 | 3,433 |
| 2.000 | -0.050 | -0.526 | 3,432 |
| 3.000 | -0.057 | -0.600 | 3,431 |
| 5.000 | -0.067 | -0.720 | 3,429 |
| 10.000 | -0.082 | -0.891 | 3,424 |
| 20.000 | -0.097 | -1.040 | 3,414 |
| 40.000 | -0.111 | -1.254 | 3,394 |
| 60.000 | -0.121 | -1.566 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `0.00%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-6.147`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.006 | 1.425 | 0.648 | 2.198 | 3,429 |
| 2.000 | 0.005 | 1.172 | 0.640 | 1.831 | 3,429 |
| 3.000 | 0.004 | 1.007 | 0.639 | 1.577 | 3,429 |
| 4.000 | 0.003 | 0.863 | 0.665 | 1.298 | 3,429 |
| 5.000 | -0.000 | -0.100 | 0.763 | -0.132 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.896 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.897 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.891 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.891 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.816 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.811 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.806 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.002 | 0.039 |
| fold_02_2020 | 8 | -0.009 | -0.207 |
| fold_03_2021 | 7 | 0.008 | 0.144 |
| fold_04_2022 | 4 | -0.009 | -0.161 |
| fold_05_2023 | 3 | -0.007 | -0.180 |
| fold_06_2024 | 3 | 0.002 | 0.049 |
| fold_07_2025 | 4 | 0.011 | 0.229 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
