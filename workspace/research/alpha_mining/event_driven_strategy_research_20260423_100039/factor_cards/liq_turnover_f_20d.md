# Factor Card: liq_turnover_f_20d

## Basic Info
- Category: `Liquidity`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean(Ref($turnover_rate_f, 1), 20)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.385`
- 10d Rank ICIR: `-0.479`
- 20d Rank ICIR: `-0.584`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.673 | -0.626 | -0.865 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.662 | -0.661 | -0.737 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.608 | -0.800 | -0.764 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.609 | -0.748 | -0.570 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.640 | -0.651 | -0.872 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.065 | -0.385 | 61.53% | 2,948 |
| size_neutral | -0.073 | -0.510 | 63.60% | 2,948 |
| industry_neutral | -0.057 | -0.547 | 64.04% | 2,948 |
| size_industry_neutral | -0.064 | -0.690 | 66.15% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.073 | -0.807 | 66.94% | 245 |
| 2015.000 | -0.072 | -0.823 | 77.05% | 244 |
| 2016.000 | -0.087 | -0.789 | 68.03% | 244 |
| 2017.000 | -0.055 | -0.554 | 68.85% | 244 |
| 2018.000 | -0.053 | -0.472 | 63.79% | 243 |
| 2019.000 | -0.064 | -0.758 | 67.21% | 244 |
| 2020.000 | -0.056 | -0.529 | 67.08% | 243 |
| 2021.000 | -0.066 | -0.865 | 64.20% | 243 |
| 2022.000 | -0.057 | -0.737 | 67.36% | 242 |
| 2023.000 | -0.052 | -0.764 | 58.68% | 242 |
| 2024.000 | -0.050 | -0.570 | 64.88% | 242 |
| 2025.000 | -0.074 | -0.872 | 60.91% | 243 |
| 2026.000 | -0.073 | -0.923 | 55.17% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.074 | -0.868 |
| -0.074 | -0.869 |
| -0.075 | -0.869 |
| -0.075 | -0.876 |
| -0.075 | -0.881 |
| -0.076 | -0.890 |
| -0.076 | -0.896 |
| -0.077 | -0.907 |
| -0.077 | -0.915 |
| -0.078 | -0.919 |
| -0.078 | -0.925 |
| -0.079 | -0.934 |
| -0.078 | -0.929 |
| -0.078 | -0.925 |
| -0.078 | -0.918 |
| -0.077 | -0.910 |
| -0.077 | -0.910 |
| -0.077 | -0.910 |
| -0.077 | -0.909 |
| -0.077 | -0.913 |
| -0.077 | -0.919 |
| -0.078 | -0.936 |
| -0.078 | -0.952 |
| -0.079 | -0.960 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `1.267`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.039 | -0.403 | 2,952 |
| 2.000 | -0.048 | -0.504 | 2,951 |
| 3.000 | -0.054 | -0.574 | 2,950 |
| 5.000 | -0.064 | -0.690 | 2,948 |
| 10.000 | -0.078 | -0.858 | 2,943 |
| 20.000 | -0.094 | -1.019 | 2,933 |
| 40.000 | -0.110 | -1.253 | 2,913 |
| 60.000 | -0.121 | -1.576 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-75.88%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-5.742`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.360 | 0.670 | 2.031 | 2,948 |
| 2.000 | 0.005 | 1.152 | 0.658 | 1.749 | 2,948 |
| 3.000 | 0.004 | 1.015 | 0.658 | 1.542 | 2,948 |
| 4.000 | 0.004 | 0.897 | 0.685 | 1.310 | 2,948 |
| 5.000 | -0.000 | -0.072 | 0.783 | -0.092 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.804 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.820 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.746 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.731 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.741 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 9 | 0.007 | 0.137 |
| fold_02_2022 | 7 | -0.003 | -0.045 |
| fold_03_2023 | 5 | 0.002 | 0.044 |
| fold_04_2024 | 6 | 0.012 | 0.256 |
| fold_05_2025 | 5 | 0.015 | 0.301 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
