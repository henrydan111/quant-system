# Factor Card: mom_intraday_20d

## Basic Info
- Category: `Momentum`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean(($close * $adj_factor) / ($open * $adj_factor) - 1, 20)`

## Screening Snapshot
- Grade: `A (Graduated)`
- 5d Rank ICIR: `-0.479`
- 10d Rank ICIR: `-0.530`
- 20d Rank ICIR: `-0.602`
- Monotonic: `True`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.777 | -0.672 | -1.099 | -1 | -1 | True | True | True |  |
| fold_02_2020 | -0.784 | -0.928 | -0.542 | -1 | -1 | True | True | True |  |
| fold_03_2021 | -0.804 | -0.788 | -0.769 | -1 | -1 | True | True | True |  |
| fold_04_2022 | -0.868 | -0.649 | -0.859 | -1 | -1 | True | True | False |  |
| fold_05_2023 | -0.764 | -0.813 | -0.692 | -1 | -1 | True | True | True |  |
| fold_06_2024 | -0.728 | -0.773 | -0.584 | -1 | -1 | True | True | True |  |
| fold_07_2025 | -0.795 | -0.610 | -0.969 | -1 | -1 | True | True | True |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.064 | -0.479 | 63.69% | 3,429 |
| size_neutral | -0.067 | -0.547 | 65.79% | 3,429 |
| industry_neutral | -0.064 | -0.645 | 70.25% | 3,429 |
| size_industry_neutral | -0.066 | -0.744 | 72.15% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.061 | -0.555 | 72.84% | 243 |
| 2013.000 | -0.065 | -0.692 | 62.18% | 238 |
| 2014.000 | -0.059 | -0.722 | 69.80% | 245 |
| 2015.000 | -0.107 | -1.069 | 82.79% | 244 |
| 2016.000 | -0.085 | -0.946 | 79.92% | 244 |
| 2017.000 | -0.058 | -0.572 | 74.18% | 244 |
| 2018.000 | -0.071 | -0.792 | 78.60% | 243 |
| 2019.000 | -0.083 | -1.099 | 77.05% | 244 |
| 2020.000 | -0.043 | -0.542 | 62.96% | 243 |
| 2021.000 | -0.056 | -0.769 | 65.02% | 243 |
| 2022.000 | -0.060 | -0.859 | 77.69% | 242 |
| 2023.000 | -0.049 | -0.692 | 68.60% | 242 |
| 2024.000 | -0.064 | -0.584 | 72.31% | 242 |
| 2025.000 | -0.073 | -0.969 | 67.90% | 243 |
| 2026.000 | -0.030 | -0.558 | 55.17% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.072 | -0.961 |
| -0.072 | -0.960 |
| -0.072 | -0.960 |
| -0.072 | -0.961 |
| -0.072 | -0.952 |
| -0.072 | -0.949 |
| -0.071 | -0.939 |
| -0.070 | -0.934 |
| -0.069 | -0.931 |
| -0.069 | -0.928 |
| -0.068 | -0.922 |
| -0.068 | -0.911 |
| -0.068 | -0.923 |
| -0.068 | -0.940 |
| -0.069 | -0.950 |
| -0.069 | -0.945 |
| -0.069 | -0.952 |
| -0.069 | -0.952 |
| -0.068 | -0.953 |
| -0.068 | -0.957 |
| -0.067 | -0.955 |
| -0.066 | -0.951 |
| -0.066 | -0.941 |
| -0.065 | -0.929 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.827`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.048 | -0.512 | 3,433 |
| 2.000 | -0.054 | -0.588 | 3,432 |
| 3.000 | -0.059 | -0.653 | 3,431 |
| 5.000 | -0.066 | -0.744 | 3,429 |
| 10.000 | -0.072 | -0.825 | 3,424 |
| 20.000 | -0.078 | -0.921 | 3,414 |
| 40.000 | -0.076 | -0.937 | 3,394 |
| 60.000 | -0.076 | -0.961 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `0.00%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-6.687`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.006 | 1.484 | 0.723 | 2.053 | 3,429 |
| 2.000 | 0.005 | 1.240 | 0.666 | 1.862 | 3,429 |
| 3.000 | 0.004 | 1.078 | 0.637 | 1.692 | 3,429 |
| 4.000 | 0.003 | 0.804 | 0.641 | 1.255 | 3,429 |
| 5.000 | -0.001 | -0.239 | 0.692 | -0.346 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.450 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.329 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.441 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.635 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.465 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.464 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.426 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 4 | -0.042 | -0.473 |
| fold_02_2020 | 2 | -0.055 | -0.743 |
| fold_03_2021 | 3 | -0.028 | -0.372 |
| fold_04_2022 | 5 | -0.019 | -0.309 |
| fold_05_2023 | 3 | -0.024 | -0.318 |
| fold_06_2024 | 3 | -0.020 | -0.264 |
| fold_07_2025 | 5 | -0.020 | -0.228 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `keep`
- Selected folds: `6`
- Validation-pass folds: `7`
- Summary: Repeatedly selected across OOS folds.
