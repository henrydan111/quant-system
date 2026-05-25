# Factor Card: liq_vol_cv_20d

## Basic Info
- Category: `Liquidity`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Std(Ref($vol, 1), 20) / Mean(Ref($vol, 1), 20)`

## Screening Snapshot
- Grade: `A`
- 5d Rank ICIR: `-0.636`
- 10d Rank ICIR: `-0.675`
- 20d Rank ICIR: `-0.640`
- Monotonic: `True`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.852 | -0.829 | -0.630 | -1 | -1 | True | True | True |  |
| fold_02_2022 | -0.878 | -0.660 | -1.128 | -1 | -1 | True | True | True |  |
| fold_03_2023 | -0.870 | -0.851 | -0.712 | -1 | -1 | True | True | True |  |
| fold_04_2024 | -0.769 | -0.874 | -0.613 | -1 | -1 | True | True | True |  |
| fold_05_2025 | -0.797 | -0.660 | -1.247 | -1 | -1 | True | True | True |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.045 | -0.636 | 69.81% | 2,948 |
| size_neutral | -0.048 | -0.731 | 72.69% | 2,948 |
| industry_neutral | -0.041 | -0.736 | 72.29% | 2,948 |
| size_industry_neutral | -0.044 | -0.827 | 74.69% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.045 | -0.822 | 68.98% | 245 |
| 2015.000 | -0.051 | -0.763 | 64.34% | 244 |
| 2016.000 | -0.053 | -1.212 | 81.56% | 244 |
| 2017.000 | -0.055 | -0.924 | 81.97% | 244 |
| 2018.000 | -0.041 | -0.694 | 80.66% | 243 |
| 2019.000 | -0.046 | -0.986 | 84.43% | 244 |
| 2020.000 | -0.032 | -0.688 | 74.07% | 243 |
| 2021.000 | -0.027 | -0.630 | 59.67% | 243 |
| 2022.000 | -0.046 | -1.128 | 79.34% | 242 |
| 2023.000 | -0.040 | -0.712 | 69.83% | 242 |
| 2024.000 | -0.038 | -0.613 | 76.45% | 242 |
| 2025.000 | -0.050 | -1.247 | 76.54% | 243 |
| 2026.000 | -0.045 | -0.969 | 62.07% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.050 | -1.242 |
| -0.050 | -1.242 |
| -0.051 | -1.242 |
| -0.051 | -1.246 |
| -0.051 | -1.255 |
| -0.051 | -1.261 |
| -0.051 | -1.264 |
| -0.051 | -1.260 |
| -0.051 | -1.235 |
| -0.051 | -1.228 |
| -0.051 | -1.220 |
| -0.051 | -1.218 |
| -0.051 | -1.218 |
| -0.051 | -1.225 |
| -0.051 | -1.220 |
| -0.051 | -1.216 |
| -0.050 | -1.216 |
| -0.050 | -1.216 |
| -0.050 | -1.215 |
| -0.050 | -1.214 |
| -0.050 | -1.214 |
| -0.050 | -1.215 |
| -0.050 | -1.221 |
| -0.050 | -1.236 |

## IC Decay
- Best horizon by |ICIR|: `10`
- Peak ICIR: `0.658`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.031 | -0.605 | 2,952 |
| 2.000 | -0.036 | -0.692 | 2,951 |
| 3.000 | -0.040 | -0.760 | 2,950 |
| 5.000 | -0.044 | -0.827 | 2,948 |
| 10.000 | -0.047 | -0.918 | 2,943 |
| 20.000 | -0.047 | -0.940 | 2,933 |
| 40.000 | -0.044 | -1.016 | 2,913 |
| 60.000 | -0.042 | -0.969 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-65.27%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-7.420`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.293 | 0.717 | 1.804 | 2,948 |
| 2.000 | 0.004 | 1.106 | 0.689 | 1.605 | 2,948 |
| 3.000 | 0.004 | 0.932 | 0.678 | 1.375 | 2,948 |
| 4.000 | 0.003 | 0.760 | 0.669 | 1.137 | 2,948 |
| 5.000 | 0.001 | 0.247 | 0.682 | 0.362 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.000 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.397 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.430 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.482 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.464 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 0 |  |  |
| fold_02_2022 | 5 | -0.005 | -0.101 |
| fold_03_2023 | 2 | -0.010 | -0.189 |
| fold_04_2024 | 1 | -0.016 | -0.285 |
| fold_05_2025 | 4 | -0.014 | -0.251 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `keep`
- Selected folds: `5`
- Validation-pass folds: `5`
- Summary: Repeatedly selected across OOS folds.
