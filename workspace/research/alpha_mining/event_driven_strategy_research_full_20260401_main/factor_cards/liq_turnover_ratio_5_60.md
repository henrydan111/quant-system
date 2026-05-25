# Factor Card: liq_turnover_ratio_5_60

## Basic Info
- Category: `Liquidity`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean($turnover_rate, 5) / Mean($turnover_rate, 60)`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `-0.466`
- 10d Rank ICIR: `-0.479`
- 20d Rank ICIR: `-0.505`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.682 | -0.630 | -1.061 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.659 | -0.969 | -0.331 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.652 | -0.632 | -0.581 | -1 | -1 | True | True | True |  |
| fold_04_2022 | -0.759 | -0.440 | -0.883 | -1 | -1 | True | True | False |  |
| fold_05_2023 | -0.653 | -0.714 | -0.452 | -1 | -1 | True | True | False |  |
| fold_06_2024 | -0.620 | -0.628 | -0.770 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.702 | -0.603 | -0.984 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.050 | -0.466 | 68.27% | 3,429 |
| size_neutral | -0.051 | -0.510 | 68.77% | 3,429 |
| industry_neutral | -0.047 | -0.618 | 72.47% | 3,429 |
| size_industry_neutral | -0.048 | -0.671 | 73.29% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.047 | -0.568 | 77.37% | 243 |
| 2013.000 | -0.060 | -0.875 | 72.69% | 238 |
| 2014.000 | -0.035 | -0.461 | 64.49% | 245 |
| 2015.000 | -0.071 | -0.823 | 77.87% | 244 |
| 2016.000 | -0.056 | -0.740 | 74.59% | 244 |
| 2017.000 | -0.038 | -0.467 | 73.36% | 244 |
| 2018.000 | -0.052 | -0.882 | 85.19% | 243 |
| 2019.000 | -0.065 | -1.061 | 84.84% | 244 |
| 2020.000 | -0.025 | -0.331 | 64.61% | 243 |
| 2021.000 | -0.035 | -0.581 | 62.96% | 243 |
| 2022.000 | -0.044 | -0.883 | 78.93% | 242 |
| 2023.000 | -0.030 | -0.452 | 65.29% | 242 |
| 2024.000 | -0.050 | -0.770 | 74.38% | 242 |
| 2025.000 | -0.061 | -0.984 | 72.84% | 243 |
| 2026.000 | -0.031 | -0.486 | 44.83% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.061 | -0.978 |
| -0.061 | -0.978 |
| -0.061 | -0.982 |
| -0.062 | -0.986 |
| -0.061 | -0.982 |
| -0.061 | -0.969 |
| -0.060 | -0.961 |
| -0.059 | -0.954 |
| -0.058 | -0.938 |
| -0.057 | -0.913 |
| -0.057 | -0.902 |
| -0.056 | -0.896 |
| -0.057 | -0.900 |
| -0.057 | -0.910 |
| -0.057 | -0.917 |
| -0.057 | -0.918 |
| -0.057 | -0.914 |
| -0.056 | -0.906 |
| -0.056 | -0.902 |
| -0.055 | -0.905 |
| -0.055 | -0.908 |
| -0.054 | -0.908 |
| -0.054 | -0.908 |
| -0.054 | -0.906 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.747`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.043 | -0.582 | 3,433 |
| 2.000 | -0.045 | -0.623 | 3,432 |
| 3.000 | -0.047 | -0.648 | 3,431 |
| 5.000 | -0.048 | -0.671 | 3,429 |
| 10.000 | -0.048 | -0.709 | 3,424 |
| 20.000 | -0.048 | -0.743 | 3,414 |
| 40.000 | -0.044 | -0.724 | 3,394 |
| 60.000 | -0.041 | -0.678 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-67.39%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-5.711`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.152 | 0.686 | 1.679 | 3,429 |
| 2.000 | 0.004 | 1.094 | 0.666 | 1.641 | 3,429 |
| 3.000 | 0.004 | 1.077 | 0.654 | 1.647 | 3,429 |
| 4.000 | 0.004 | 0.989 | 0.652 | 1.515 | 3,429 |
| 5.000 | 0.000 | 0.055 | 0.686 | 0.080 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.979 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.980 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.456 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.468 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.979 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.979 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.980 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 8 | -0.007 | -0.172 |
| fold_02_2020 | 2 | -0.018 | -0.422 |
| fold_03_2021 | 8 | 0.010 | 0.221 |
| fold_04_2022 | 10 | 0.010 | 0.222 |
| fold_05_2023 | 7 | -0.006 | -0.118 |
| fold_06_2024 | 10 | -0.010 | -0.166 |
| fold_07_2025 | 7 | -0.010 | -0.137 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `1`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
