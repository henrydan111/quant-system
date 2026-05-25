# Factor Card: liq_vol_cv_20d

## Basic Info
- Category: `Liquidity`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Std($vol, 20) / Mean($vol, 20)`

## Screening Snapshot
- Grade: `A (Graduated)`
- 5d Rank ICIR: `-0.729`
- 10d Rank ICIR: `-0.768`
- 20d Rank ICIR: `-0.713`
- Monotonic: `True`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.999 | -0.927 | -1.149 | -1 | -1 | True | True | True |  |
| fold_02_2020 | -1.027 | -0.986 | -0.799 | -1 | -1 | True | True | True |  |
| fold_03_2021 | -0.946 | -0.961 | -0.696 | -1 | -1 | True | True | True |  |
| fold_04_2022 | -0.986 | -0.747 | -1.189 | -1 | -1 | True | True | True |  |
| fold_05_2023 | -0.993 | -0.914 | -0.782 | -1 | -1 | True | True | True |  |
| fold_06_2024 | -0.878 | -0.945 | -0.677 | -1 | -1 | True | True | True |  |
| fold_07_2025 | -0.910 | -0.726 | -1.398 | -1 | -1 | True | True | True |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.052 | -0.729 | 72.50% | 3,429 |
| size_neutral | -0.057 | -0.820 | 75.04% | 3,429 |
| industry_neutral | -0.048 | -0.855 | 74.07% | 3,429 |
| size_industry_neutral | -0.052 | -0.936 | 77.60% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.055 | -0.860 | 83.95% | 243 |
| 2013.000 | -0.064 | -1.378 | 88.24% | 238 |
| 2014.000 | -0.051 | -0.909 | 68.57% | 245 |
| 2015.000 | -0.056 | -0.800 | 60.25% | 244 |
| 2016.000 | -0.061 | -1.326 | 81.15% | 244 |
| 2017.000 | -0.062 | -0.985 | 82.38% | 244 |
| 2018.000 | -0.055 | -0.871 | 87.65% | 243 |
| 2019.000 | -0.057 | -1.149 | 88.93% | 244 |
| 2020.000 | -0.038 | -0.799 | 75.72% | 243 |
| 2021.000 | -0.031 | -0.696 | 62.14% | 243 |
| 2022.000 | -0.051 | -1.189 | 79.75% | 242 |
| 2023.000 | -0.045 | -0.782 | 71.07% | 242 |
| 2024.000 | -0.044 | -0.677 | 79.75% | 242 |
| 2025.000 | -0.057 | -1.398 | 79.01% | 243 |
| 2026.000 | -0.050 | -1.005 | 62.07% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.057 | -1.391 |
| -0.057 | -1.390 |
| -0.058 | -1.386 |
| -0.058 | -1.389 |
| -0.058 | -1.395 |
| -0.058 | -1.402 |
| -0.059 | -1.407 |
| -0.058 | -1.403 |
| -0.058 | -1.371 |
| -0.058 | -1.365 |
| -0.058 | -1.359 |
| -0.058 | -1.358 |
| -0.057 | -1.356 |
| -0.058 | -1.361 |
| -0.057 | -1.355 |
| -0.057 | -1.350 |
| -0.057 | -1.350 |
| -0.057 | -1.354 |
| -0.057 | -1.354 |
| -0.057 | -1.353 |
| -0.057 | -1.353 |
| -0.057 | -1.350 |
| -0.057 | -1.358 |
| -0.057 | -1.374 |

## IC Decay
- Best horizon by |ICIR|: `10`
- Peak ICIR: `0.763`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.037 | -0.686 | 3,433 |
| 2.000 | -0.043 | -0.782 | 3,432 |
| 3.000 | -0.047 | -0.848 | 3,431 |
| 5.000 | -0.052 | -0.936 | 3,429 |
| 10.000 | -0.055 | -1.038 | 3,424 |
| 20.000 | -0.053 | -1.057 | 3,414 |
| 40.000 | -0.048 | -1.109 | 3,394 |
| 60.000 | -0.046 | -1.063 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-70.55%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-8.682`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.006 | 1.390 | 0.697 | 1.995 | 3,429 |
| 2.000 | 0.005 | 1.146 | 0.671 | 1.709 | 3,429 |
| 3.000 | 0.004 | 0.944 | 0.658 | 1.433 | 3,429 |
| 4.000 | 0.003 | 0.751 | 0.649 | 1.158 | 3,429 |
| 5.000 | 0.001 | 0.135 | 0.662 | 0.204 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.000 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.000 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.000 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.397 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.430 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.482 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.302 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 0 |  |  |
| fold_02_2020 | 0 |  |  |
| fold_03_2021 | 0 |  |  |
| fold_04_2022 | 3 | -0.011 | -0.198 |
| fold_05_2023 | 2 | -0.014 | -0.257 |
| fold_06_2024 | 1 | -0.020 | -0.359 |
| fold_07_2025 | 1 | -0.026 | -0.444 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `keep`
- Selected folds: `7`
- Validation-pass folds: `7`
- Summary: Repeatedly selected across OOS folds.
