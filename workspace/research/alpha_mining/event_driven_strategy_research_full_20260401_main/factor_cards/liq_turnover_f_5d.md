# Factor Card: liq_turnover_f_5d

## Basic Info
- Category: `Liquidity`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean($turnover_rate_f, 5)`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `-0.472`
- 10d Rank ICIR: `-0.554`
- 20d Rank ICIR: `-0.631`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.955 | -0.654 | -1.056 | -1 | -1 | True | True | True |  |
| fold_02_2020 | -0.927 | -0.799 | -0.677 | -1 | -1 | True | True | True |  |
| fold_03_2021 | -0.867 | -0.839 | -1.010 | -1 | -1 | True | True | True |  |
| fold_04_2022 | -0.869 | -0.807 | -0.860 | -1 | -1 | True | True | True |  |
| fold_05_2023 | -0.799 | -0.932 | -0.950 | -1 | -1 | True | True | False |  |
| fold_06_2024 | -0.776 | -0.898 | -0.714 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.809 | -0.801 | -1.266 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.076 | -0.472 | 66.32% | 3,429 |
| size_neutral | -0.086 | -0.628 | 68.71% | 3,429 |
| industry_neutral | -0.071 | -0.725 | 70.75% | 3,429 |
| size_industry_neutral | -0.078 | -0.873 | 72.62% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.074 | -0.797 | 76.13% | 243 |
| 2013.000 | -0.084 | -0.869 | 68.07% | 238 |
| 2014.000 | -0.085 | -1.036 | 74.29% | 245 |
| 2015.000 | -0.096 | -1.037 | 79.51% | 244 |
| 2016.000 | -0.105 | -1.071 | 72.95% | 244 |
| 2017.000 | -0.064 | -0.682 | 74.18% | 244 |
| 2018.000 | -0.070 | -0.633 | 72.43% | 243 |
| 2019.000 | -0.084 | -1.056 | 75.00% | 244 |
| 2020.000 | -0.067 | -0.677 | 71.60% | 243 |
| 2021.000 | -0.072 | -1.010 | 67.08% | 243 |
| 2022.000 | -0.066 | -0.860 | 74.79% | 242 |
| 2023.000 | -0.061 | -0.950 | 67.77% | 242 |
| 2024.000 | -0.064 | -0.714 | 73.14% | 242 |
| 2025.000 | -0.093 | -1.266 | 71.60% | 243 |
| 2026.000 | -0.080 | -1.054 | 55.17% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.092 | -1.246 |
| -0.092 | -1.246 |
| -0.093 | -1.244 |
| -0.093 | -1.252 |
| -0.093 | -1.256 |
| -0.094 | -1.261 |
| -0.094 | -1.261 |
| -0.094 | -1.267 |
| -0.094 | -1.268 |
| -0.094 | -1.269 |
| -0.094 | -1.268 |
| -0.094 | -1.269 |
| -0.094 | -1.258 |
| -0.093 | -1.253 |
| -0.093 | -1.245 |
| -0.092 | -1.231 |
| -0.092 | -1.234 |
| -0.091 | -1.237 |
| -0.091 | -1.235 |
| -0.091 | -1.237 |
| -0.092 | -1.241 |
| -0.092 | -1.258 |
| -0.093 | -1.275 |
| -0.093 | -1.286 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `1.336`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.054 | -0.590 | 3,433 |
| 2.000 | -0.062 | -0.696 | 3,432 |
| 3.000 | -0.069 | -0.766 | 3,431 |
| 5.000 | -0.078 | -0.873 | 3,429 |
| 10.000 | -0.091 | -1.033 | 3,424 |
| 20.000 | -0.104 | -1.161 | 3,414 |
| 40.000 | -0.116 | -1.340 | 3,394 |
| 60.000 | -0.124 | -1.593 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `0.00%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-7.066`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.006 | 1.484 | 0.651 | 2.279 | 3,429 |
| 2.000 | 0.005 | 1.205 | 0.645 | 1.869 | 3,429 |
| 3.000 | 0.004 | 1.044 | 0.642 | 1.626 | 3,429 |
| 4.000 | 0.004 | 0.913 | 0.662 | 1.379 | 3,429 |
| 5.000 | -0.001 | -0.280 | 0.757 | -0.369 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.524 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.498 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.188 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.000 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.903 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.906 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.902 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 6 | -0.022 | -0.283 |
| fold_02_2020 | 4 | -0.028 | -0.376 |
| fold_03_2021 | 1 | -0.062 | -0.682 |
| fold_04_2022 | 0 |  |  |
| fold_05_2023 | 2 | -0.002 | -0.053 |
| fold_06_2024 | 3 | 0.006 | 0.176 |
| fold_07_2025 | 1 | -0.011 | -0.296 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `keep`
- Selected folds: `4`
- Validation-pass folds: `7`
- Summary: Repeatedly selected across OOS folds.
