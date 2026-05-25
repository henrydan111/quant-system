# Factor Card: risk_range_ratio_20d

## Basic Info
- Category: `Volatility`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean(($high - $low) / $close, 20)`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `-0.361`
- 10d Rank ICIR: `-0.420`
- 20d Rank ICIR: `-0.476`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.476 | -0.503 | -0.630 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.511 | -0.532 | -0.489 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.540 | -0.555 | -0.685 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.536 | -0.575 | -0.685 | -1 | -1 | True | True | False |  |
| fold_05_2023 | -0.552 | -0.686 | -0.787 | -1 | -1 | True | True | False |  |
| fold_06_2024 | -0.554 | -0.732 | -0.477 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.577 | -0.598 | -0.672 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.066 | -0.361 | 56.23% | 3,429 |
| size_neutral | -0.069 | -0.409 | 56.96% | 3,429 |
| industry_neutral | -0.063 | -0.489 | 59.70% | 3,429 |
| size_industry_neutral | -0.065 | -0.546 | 60.92% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.045 | -0.374 | 64.61% | 243 |
| 2013.000 | -0.046 | -0.330 | 50.84% | 238 |
| 2014.000 | -0.076 | -0.637 | 67.35% | 245 |
| 2015.000 | -0.057 | -0.422 | 62.70% | 244 |
| 2016.000 | -0.085 | -0.648 | 67.21% | 244 |
| 2017.000 | -0.065 | -0.558 | 66.39% | 244 |
| 2018.000 | -0.058 | -0.453 | 64.20% | 243 |
| 2019.000 | -0.068 | -0.630 | 62.30% | 244 |
| 2020.000 | -0.059 | -0.489 | 53.09% | 243 |
| 2021.000 | -0.068 | -0.685 | 58.44% | 243 |
| 2022.000 | -0.072 | -0.685 | 60.74% | 242 |
| 2023.000 | -0.073 | -0.787 | 59.50% | 242 |
| 2024.000 | -0.062 | -0.477 | 62.40% | 242 |
| 2025.000 | -0.074 | -0.672 | 53.91% | 243 |
| 2026.000 | -0.067 | -0.860 | 51.72% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.074 | -0.670 |
| -0.074 | -0.670 |
| -0.074 | -0.672 |
| -0.074 | -0.678 |
| -0.075 | -0.682 |
| -0.075 | -0.689 |
| -0.076 | -0.694 |
| -0.077 | -0.706 |
| -0.077 | -0.714 |
| -0.078 | -0.719 |
| -0.078 | -0.726 |
| -0.079 | -0.738 |
| -0.079 | -0.736 |
| -0.079 | -0.733 |
| -0.078 | -0.729 |
| -0.077 | -0.720 |
| -0.077 | -0.720 |
| -0.077 | -0.720 |
| -0.076 | -0.718 |
| -0.077 | -0.724 |
| -0.078 | -0.736 |
| -0.079 | -0.755 |
| -0.079 | -0.775 |
| -0.080 | -0.786 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.757`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.046 | -0.390 | 3,433 |
| 2.000 | -0.053 | -0.439 | 3,432 |
| 3.000 | -0.058 | -0.479 | 3,431 |
| 5.000 | -0.065 | -0.546 | 3,429 |
| 10.000 | -0.075 | -0.640 | 3,424 |
| 20.000 | -0.086 | -0.730 | 3,414 |
| 40.000 | -0.098 | -0.900 | 3,394 |
| 60.000 | -0.108 | -1.102 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-62.10%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-3.024`
- Monotonic: `True`
- Monotonic Spearman: `-0.900`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 1.104 | 0.602 | 1.834 | 3,429 |
| 2.000 | 0.005 | 1.148 | 0.641 | 1.792 | 3,429 |
| 3.000 | 0.004 | 1.069 | 0.662 | 1.615 | 3,429 |
| 4.000 | 0.003 | 0.862 | 0.691 | 1.248 | 3,429 |
| 5.000 | 0.001 | 0.183 | 0.763 | 0.239 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.693 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.683 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.716 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.725 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.723 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.733 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.713 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.003 | 0.041 |
| fold_02_2020 | 10 | -0.011 | -0.162 |
| fold_03_2021 | 10 | -0.009 | -0.144 |
| fold_04_2022 | 7 | -0.016 | -0.234 |
| fold_05_2023 | 8 | -0.022 | -0.307 |
| fold_06_2024 | 6 | -0.025 | -0.351 |
| fold_07_2025 | 7 | -0.013 | -0.177 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
