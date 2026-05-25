# Factor Card: risk_vol_5d

## Basic Info
- Category: `Volatility`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Std((($close * $adj_factor) / Ref(($close * $adj_factor), 1) - 1), 5)`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `-0.375`
- 10d Rank ICIR: `-0.442`
- 20d Rank ICIR: `-0.498`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.411 | -0.464 | -0.834 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.470 | -0.582 | -0.666 | -1 | -1 | True | True | True |  |
| fold_03_2021 | -0.472 | -0.746 | -0.887 | -1 | -1 | True | True | True |  |
| fold_04_2022 | -0.494 | -0.761 | -0.741 | -1 | -1 | True | True | True |  |
| fold_05_2023 | -0.603 | -0.805 | -0.803 | -1 | -1 | True | True | True |  |
| fold_06_2024 | -0.633 | -0.770 | -0.519 | -1 | -1 | True | True | True |  |
| fold_07_2025 | -0.677 | -0.610 | -0.870 | -1 | -1 | True | True | True |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.053 | -0.375 | 58.30% | 3,429 |
| size_neutral | -0.056 | -0.431 | 59.78% | 3,429 |
| industry_neutral | -0.048 | -0.499 | 62.70% | 3,429 |
| size_industry_neutral | -0.050 | -0.566 | 63.78% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.020 | -0.228 | 58.44% | 243 |
| 2013.000 | -0.035 | -0.393 | 54.20% | 238 |
| 2014.000 | -0.053 | -0.662 | 64.08% | 245 |
| 2015.000 | -0.024 | -0.217 | 55.74% | 244 |
| 2016.000 | -0.060 | -0.659 | 68.44% | 244 |
| 2017.000 | -0.047 | -0.531 | 66.39% | 244 |
| 2018.000 | -0.039 | -0.405 | 62.55% | 243 |
| 2019.000 | -0.062 | -0.834 | 72.54% | 244 |
| 2020.000 | -0.054 | -0.666 | 64.20% | 243 |
| 2021.000 | -0.058 | -0.887 | 62.55% | 243 |
| 2022.000 | -0.059 | -0.741 | 66.12% | 242 |
| 2023.000 | -0.056 | -0.803 | 64.05% | 242 |
| 2024.000 | -0.059 | -0.519 | 70.25% | 242 |
| 2025.000 | -0.073 | -0.870 | 64.20% | 243 |
| 2026.000 | -0.068 | -1.084 | 55.17% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.073 | -0.866 |
| -0.073 | -0.867 |
| -0.074 | -0.873 |
| -0.074 | -0.878 |
| -0.074 | -0.878 |
| -0.075 | -0.880 |
| -0.074 | -0.875 |
| -0.075 | -0.884 |
| -0.075 | -0.888 |
| -0.075 | -0.892 |
| -0.075 | -0.896 |
| -0.076 | -0.906 |
| -0.076 | -0.902 |
| -0.075 | -0.899 |
| -0.074 | -0.896 |
| -0.074 | -0.889 |
| -0.073 | -0.889 |
| -0.073 | -0.889 |
| -0.072 | -0.883 |
| -0.072 | -0.882 |
| -0.073 | -0.886 |
| -0.073 | -0.895 |
| -0.074 | -0.917 |
| -0.074 | -0.934 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.791`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.035 | -0.376 | 3,433 |
| 2.000 | -0.040 | -0.441 | 3,432 |
| 3.000 | -0.044 | -0.486 | 3,431 |
| 5.000 | -0.050 | -0.566 | 3,429 |
| 10.000 | -0.058 | -0.673 | 3,424 |
| 20.000 | -0.066 | -0.767 | 3,414 |
| 40.000 | -0.073 | -0.912 | 3,394 |
| 60.000 | -0.079 | -1.073 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-48.13%`
- Long-short total diagnostic return: `-99.99%`
- Long-short Sharpe: `-2.694`
- Monotonic: `False`
- Monotonic Spearman: `-0.300`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 0.939 | 0.633 | 1.483 | 3,429 |
| 2.000 | 0.004 | 1.058 | 0.648 | 1.633 | 3,429 |
| 3.000 | 0.004 | 1.079 | 0.657 | 1.641 | 3,429 |
| 4.000 | 0.004 | 0.962 | 0.681 | 1.412 | 3,429 |
| 5.000 | 0.001 | 0.311 | 0.728 | 0.427 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.583 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.559 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.579 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.599 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.564 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.559 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.537 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.012 | 0.265 |
| fold_02_2020 | 9 | 0.011 | 0.251 |
| fold_03_2021 | 4 | -0.004 | -0.096 |
| fold_04_2022 | 2 | -0.007 | -0.168 |
| fold_05_2023 | 4 | -0.010 | -0.221 |
| fold_06_2024 | 4 | -0.011 | -0.239 |
| fold_07_2025 | 6 | -0.010 | -0.175 |

## Risks
- Quantile monotonicity is weak in the 5d strategy-horizon diagnostic.

## Conclusion
- Final decision: `keep`
- Selected folds: `6`
- Validation-pass folds: `7`
- Summary: Repeatedly selected across OOS folds.
