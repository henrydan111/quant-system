# Factor Card: alpha_toplist_amount_over_mv_20d

## Basic Info
- Category: `Other`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean(Ref($top_list__l_amount, 1) / Ref($total_mv, 1), 20)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.318`
- 10d Rank ICIR: `-0.392`
- 20d Rank ICIR: `-0.441`
- Monotonic: `True`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.460 | -0.251 | -0.610 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.464 | -0.346 | -0.433 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.377 | -0.520 | -0.362 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.374 | -0.395 | -0.202 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.350 | -0.281 | -0.245 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.032 | -0.319 | 57.84% | 2,948 |
| size_neutral | -0.037 | -0.371 | 59.36% | 2,948 |
| industry_neutral | -0.023 | -0.297 | 58.41% | 2,948 |
| size_industry_neutral | -0.028 | -0.379 | 60.21% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.029 | -0.376 | 65.71% | 245 |
| 2015.000 | -0.031 | -0.536 | 73.36% | 244 |
| 2016.000 | -0.042 | -0.640 | 69.26% | 244 |
| 2017.000 | -0.040 | -0.567 | 72.13% | 244 |
| 2018.000 | -0.018 | -0.250 | 58.02% | 243 |
| 2019.000 | -0.027 | -0.382 | 52.46% | 244 |
| 2020.000 | -0.012 | -0.145 | 49.38% | 243 |
| 2021.000 | -0.043 | -0.610 | 56.79% | 243 |
| 2022.000 | -0.030 | -0.433 | 59.09% | 242 |
| 2023.000 | -0.028 | -0.362 | 57.02% | 242 |
| 2024.000 | -0.016 | -0.202 | 60.74% | 242 |
| 2025.000 | -0.016 | -0.245 | 51.85% | 243 |
| 2026.000 | -0.013 | -0.165 | 51.72% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.016 | -0.234 |
| -0.016 | -0.243 |
| -0.017 | -0.255 |
| -0.018 | -0.258 |
| -0.017 | -0.254 |
| -0.017 | -0.255 |
| -0.018 | -0.259 |
| -0.018 | -0.264 |
| -0.018 | -0.262 |
| -0.018 | -0.265 |
| -0.018 | -0.267 |
| -0.018 | -0.268 |
| -0.018 | -0.265 |
| -0.018 | -0.262 |
| -0.018 | -0.259 |
| -0.017 | -0.257 |
| -0.018 | -0.258 |
| -0.018 | -0.263 |
| -0.018 | -0.270 |
| -0.019 | -0.278 |
| -0.019 | -0.284 |
| -0.020 | -0.289 |
| -0.020 | -0.290 |
| -0.020 | -0.293 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.622`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.013 | -0.185 | 2,952 |
| 2.000 | -0.018 | -0.245 | 2,951 |
| 3.000 | -0.022 | -0.298 | 2,950 |
| 5.000 | -0.028 | -0.379 | 2,948 |
| 10.000 | -0.036 | -0.495 | 2,943 |
| 20.000 | -0.043 | -0.621 | 2,933 |
| 40.000 | -0.048 | -0.782 | 2,913 |
| 60.000 | -0.053 | -0.860 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-60.09%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-2.986`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | -0.001 | -0.131 | 0.774 | -0.169 | 2,948 |
| 2.000 | -0.001 | -0.198 | 0.774 | -0.256 | 2,948 |
| 3.000 | -0.002 | -0.458 | 0.755 | -0.606 | 2,948 |
| 4.000 | -0.003 | -0.700 | 0.785 | -0.892 | 2,948 |
| 5.000 | -0.004 | -1.005 | 0.844 | -1.190 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.316 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.349 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.359 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.511 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.347 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 10 | 0.018 | 0.339 |
| fold_02_2022 | 10 | 0.011 | 0.213 |
| fold_03_2023 | 10 | 0.008 | 0.143 |
| fold_04_2024 | 10 | 0.018 | 0.276 |
| fold_05_2025 | 10 | 0.042 | 0.565 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
