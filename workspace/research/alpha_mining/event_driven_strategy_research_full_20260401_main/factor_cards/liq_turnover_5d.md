# Factor Card: liq_turnover_5d

## Basic Info
- Category: `Liquidity`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean($turnover_rate, 5)`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `-0.403`
- 10d Rank ICIR: `-0.469`
- 20d Rank ICIR: `-0.532`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.917 | -0.583 | -1.052 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.877 | -0.758 | -0.663 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.816 | -0.827 | -0.992 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.813 | -0.796 | -0.899 | -1 | -1 | True | True | False |  |
| fold_05_2023 | -0.753 | -0.945 | -0.992 | -1 | -1 | True | True | True |  |
| fold_06_2024 | -0.733 | -0.940 | -0.728 | -1 | -1 | True | True | True |  |
| fold_07_2025 | -0.794 | -0.833 | -1.349 | -1 | -1 | True | True | True |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.068 | -0.403 | 63.95% | 3,429 |
| size_neutral | -0.081 | -0.580 | 66.64% | 3,429 |
| industry_neutral | -0.064 | -0.674 | 68.65% | 3,429 |
| size_industry_neutral | -0.072 | -0.852 | 70.69% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.066 | -0.735 | 70.78% | 243 |
| 2013.000 | -0.073 | -0.801 | 65.13% | 238 |
| 2014.000 | -0.080 | -1.072 | 69.80% | 245 |
| 2015.000 | -0.082 | -0.992 | 77.05% | 244 |
| 2016.000 | -0.096 | -1.046 | 69.67% | 244 |
| 2017.000 | -0.055 | -0.584 | 71.31% | 244 |
| 2018.000 | -0.064 | -0.584 | 68.31% | 243 |
| 2019.000 | -0.078 | -1.052 | 75.00% | 244 |
| 2020.000 | -0.062 | -0.663 | 69.14% | 243 |
| 2021.000 | -0.070 | -0.992 | 66.67% | 243 |
| 2022.000 | -0.066 | -0.899 | 75.62% | 242 |
| 2023.000 | -0.062 | -0.992 | 67.77% | 242 |
| 2024.000 | -0.061 | -0.728 | 72.73% | 242 |
| 2025.000 | -0.089 | -1.349 | 72.43% | 243 |
| 2026.000 | -0.072 | -0.990 | 55.17% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.088 | -1.324 |
| -0.088 | -1.322 |
| -0.089 | -1.321 |
| -0.089 | -1.330 |
| -0.090 | -1.335 |
| -0.090 | -1.339 |
| -0.090 | -1.340 |
| -0.090 | -1.344 |
| -0.090 | -1.343 |
| -0.090 | -1.344 |
| -0.090 | -1.343 |
| -0.090 | -1.344 |
| -0.090 | -1.331 |
| -0.089 | -1.325 |
| -0.088 | -1.316 |
| -0.088 | -1.296 |
| -0.087 | -1.300 |
| -0.087 | -1.304 |
| -0.087 | -1.302 |
| -0.087 | -1.304 |
| -0.087 | -1.310 |
| -0.088 | -1.329 |
| -0.088 | -1.347 |
| -0.088 | -1.360 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `1.214`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.049 | -0.574 | 3,433 |
| 2.000 | -0.057 | -0.677 | 3,432 |
| 3.000 | -0.063 | -0.747 | 3,431 |
| 5.000 | -0.072 | -0.852 | 3,429 |
| 10.000 | -0.085 | -1.009 | 3,424 |
| 20.000 | -0.098 | -1.137 | 3,414 |
| 40.000 | -0.111 | -1.319 | 3,394 |
| 60.000 | -0.121 | -1.582 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `0.00%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-6.996`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.006 | 1.544 | 0.666 | 2.319 | 3,429 |
| 2.000 | 0.005 | 1.186 | 0.646 | 1.836 | 3,429 |
| 3.000 | 0.004 | 0.970 | 0.634 | 1.531 | 3,429 |
| 4.000 | 0.003 | 0.815 | 0.651 | 1.251 | 3,429 |
| 5.000 | -0.001 | -0.149 | 0.759 | -0.196 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.924 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.922 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.912 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.903 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.517 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.533 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.000 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 8 | -0.008 | -0.127 |
| fold_02_2020 | 5 | -0.008 | -0.145 |
| fold_03_2021 | 2 | -0.006 | -0.165 |
| fold_04_2022 | 1 | -0.010 | -0.257 |
| fold_05_2023 | 1 | -0.036 | -0.737 |
| fold_06_2024 | 2 | -0.031 | -0.722 |
| fold_07_2025 | 0 |  |  |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `keep`
- Selected folds: `3`
- Validation-pass folds: `7`
- Summary: Repeatedly selected across OOS folds.
