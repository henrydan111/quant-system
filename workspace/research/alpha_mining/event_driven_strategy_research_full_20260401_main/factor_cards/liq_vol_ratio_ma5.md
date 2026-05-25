# Factor Card: liq_vol_ratio_ma5

## Basic Info
- Category: `Liquidity`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean($volume_ratio, 5)`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `-0.387`
- 10d Rank ICIR: `-0.306`
- 20d Rank ICIR: `-0.311`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.622 | -0.480 | -0.926 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.588 | -0.748 | -0.466 | -1 | -1 | True | True | True |  |
| fold_03_2021 | -0.563 | -0.661 | -0.464 | -1 | -1 | True | True | True |  |
| fold_04_2022 | -0.607 | -0.462 | -0.618 | -1 | -1 | True | True | True |  |
| fold_05_2023 | -0.605 | -0.531 | -0.630 | -1 | -1 | True | True | True |  |
| fold_06_2024 | -0.545 | -0.618 | -0.466 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.596 | -0.532 | -0.763 | -1 | -1 | True | True | True |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.033 | -0.387 | 70.05% | 3,429 |
| size_neutral | -0.035 | -0.427 | 70.55% | 3,429 |
| industry_neutral | -0.035 | -0.546 | 74.39% | 3,429 |
| size_industry_neutral | -0.035 | -0.582 | 74.45% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.042 | -0.544 | 74.49% | 243 |
| 2013.000 | -0.047 | -0.738 | 77.31% | 238 |
| 2014.000 | -0.036 | -0.601 | 73.47% | 245 |
| 2015.000 | -0.049 | -0.562 | 74.59% | 244 |
| 2016.000 | -0.043 | -0.777 | 77.87% | 244 |
| 2017.000 | -0.022 | -0.364 | 75.00% | 244 |
| 2018.000 | -0.035 | -0.608 | 83.95% | 243 |
| 2019.000 | -0.045 | -0.926 | 85.66% | 244 |
| 2020.000 | -0.028 | -0.466 | 70.78% | 243 |
| 2021.000 | -0.022 | -0.464 | 61.73% | 243 |
| 2022.000 | -0.024 | -0.618 | 71.07% | 242 |
| 2023.000 | -0.032 | -0.630 | 69.42% | 242 |
| 2024.000 | -0.031 | -0.466 | 74.38% | 242 |
| 2025.000 | -0.039 | -0.763 | 74.90% | 243 |
| 2026.000 | -0.033 | -0.517 | 55.17% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.038 | -0.746 |
| -0.039 | -0.749 |
| -0.039 | -0.753 |
| -0.039 | -0.754 |
| -0.039 | -0.751 |
| -0.038 | -0.735 |
| -0.038 | -0.732 |
| -0.037 | -0.726 |
| -0.037 | -0.714 |
| -0.036 | -0.687 |
| -0.036 | -0.683 |
| -0.036 | -0.681 |
| -0.035 | -0.680 |
| -0.035 | -0.681 |
| -0.035 | -0.679 |
| -0.034 | -0.675 |
| -0.034 | -0.667 |
| -0.034 | -0.663 |
| -0.034 | -0.662 |
| -0.033 | -0.663 |
| -0.034 | -0.662 |
| -0.034 | -0.662 |
| -0.034 | -0.661 |
| -0.034 | -0.662 |

## IC Decay
- Best horizon by |ICIR|: `20`
- Peak ICIR: `0.613`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.041 | -0.617 | 3,433 |
| 2.000 | -0.040 | -0.611 | 3,432 |
| 3.000 | -0.039 | -0.605 | 3,431 |
| 5.000 | -0.035 | -0.582 | 3,429 |
| 10.000 | -0.028 | -0.515 | 3,424 |
| 20.000 | -0.027 | -0.536 | 3,414 |
| 40.000 | -0.024 | -0.492 | 3,394 |
| 60.000 | -0.021 | -0.435 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-61.60%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-5.628`
- Monotonic: `False`
- Monotonic Spearman: `-0.700`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 1.073 | 0.685 | 1.565 | 3,429 |
| 2.000 | 0.004 | 1.128 | 0.674 | 1.673 | 3,429 |
| 3.000 | 0.004 | 1.095 | 0.661 | 1.656 | 3,429 |
| 4.000 | 0.004 | 0.940 | 0.655 | 1.434 | 3,429 |
| 5.000 | 0.001 | 0.131 | 0.664 | 0.197 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.438 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.448 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.327 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.331 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.425 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.426 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.426 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | -0.012 | -0.271 |
| fold_02_2020 | 5 | -0.017 | -0.432 |
| fold_03_2021 | 7 | -0.017 | -0.380 |
| fold_04_2022 | 9 | -0.007 | -0.180 |
| fold_05_2023 | 9 | -0.005 | -0.145 |
| fold_06_2024 | 10 | -0.012 | -0.320 |
| fold_07_2025 | 9 | -0.014 | -0.321 |

## Risks
- Quantile monotonicity is weak in the 5d strategy-horizon diagnostic.

## Conclusion
- Final decision: `keep`
- Selected folds: `5`
- Validation-pass folds: `7`
- Summary: Repeatedly selected across OOS folds.
