# Factor Card: liq_turnover_10d

## Basic Info
- Category: `Liquidity`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean($turnover_rate, 10)`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `-0.373`
- 10d Rank ICIR: `-0.447`
- 20d Rank ICIR: `-0.511`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.831 | -0.545 | -0.959 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.801 | -0.700 | -0.605 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.756 | -0.754 | -0.937 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.755 | -0.740 | -0.855 | -1 | -1 | True | True | False |  |
| fold_05_2023 | -0.693 | -0.896 | -0.931 | -1 | -1 | True | True | False |  |
| fold_06_2024 | -0.681 | -0.888 | -0.684 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.739 | -0.784 | -1.201 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.065 | -0.373 | 61.59% | 3,429 |
| size_neutral | -0.076 | -0.537 | 64.77% | 3,429 |
| industry_neutral | -0.059 | -0.612 | 66.08% | 3,429 |
| size_industry_neutral | -0.067 | -0.786 | 68.59% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.061 | -0.663 | 72.02% | 243 |
| 2013.000 | -0.066 | -0.702 | 62.61% | 238 |
| 2014.000 | -0.075 | -0.954 | 66.53% | 245 |
| 2015.000 | -0.075 | -0.961 | 77.46% | 244 |
| 2016.000 | -0.090 | -0.937 | 67.62% | 244 |
| 2017.000 | -0.053 | -0.549 | 70.49% | 244 |
| 2018.000 | -0.060 | -0.544 | 65.43% | 243 |
| 2019.000 | -0.072 | -0.959 | 72.13% | 244 |
| 2020.000 | -0.058 | -0.605 | 67.08% | 243 |
| 2021.000 | -0.068 | -0.937 | 66.67% | 243 |
| 2022.000 | -0.063 | -0.855 | 72.31% | 242 |
| 2023.000 | -0.059 | -0.931 | 63.22% | 242 |
| 2024.000 | -0.057 | -0.684 | 69.83% | 242 |
| 2025.000 | -0.084 | -1.201 | 68.31% | 243 |
| 2026.000 | -0.068 | -0.914 | 55.17% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.084 | -1.183 |
| -0.084 | -1.182 |
| -0.084 | -1.182 |
| -0.085 | -1.191 |
| -0.085 | -1.195 |
| -0.085 | -1.201 |
| -0.085 | -1.205 |
| -0.086 | -1.210 |
| -0.086 | -1.210 |
| -0.086 | -1.212 |
| -0.086 | -1.214 |
| -0.086 | -1.217 |
| -0.086 | -1.205 |
| -0.085 | -1.199 |
| -0.085 | -1.190 |
| -0.084 | -1.174 |
| -0.083 | -1.176 |
| -0.083 | -1.178 |
| -0.083 | -1.176 |
| -0.083 | -1.180 |
| -0.084 | -1.187 |
| -0.084 | -1.206 |
| -0.084 | -1.224 |
| -0.085 | -1.232 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `1.167`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.043 | -0.487 | 3,433 |
| 2.000 | -0.051 | -0.591 | 3,432 |
| 3.000 | -0.058 | -0.667 | 3,431 |
| 5.000 | -0.067 | -0.786 | 3,429 |
| 10.000 | -0.081 | -0.954 | 3,424 |
| 20.000 | -0.095 | -1.085 | 3,414 |
| 40.000 | -0.109 | -1.282 | 3,394 |
| 60.000 | -0.120 | -1.559 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `0.00%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-6.684`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.006 | 1.513 | 0.664 | 2.278 | 3,429 |
| 2.000 | 0.005 | 1.158 | 0.643 | 1.800 | 3,429 |
| 3.000 | 0.004 | 0.969 | 0.633 | 1.531 | 3,429 |
| 4.000 | 0.003 | 0.814 | 0.652 | 1.248 | 3,429 |
| 5.000 | -0.000 | -0.089 | 0.762 | -0.116 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.887 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.883 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.874 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.864 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.966 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.964 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.964 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.000 | 0.007 |
| fold_02_2020 | 7 | -0.013 | -0.261 |
| fold_03_2021 | 4 | 0.001 | 0.014 |
| fold_04_2022 | 4 | -0.009 | -0.208 |
| fold_05_2023 | 3 | 0.002 | 0.045 |
| fold_06_2024 | 3 | 0.006 | 0.152 |
| fold_07_2025 | 1 | 0.009 | 0.154 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
