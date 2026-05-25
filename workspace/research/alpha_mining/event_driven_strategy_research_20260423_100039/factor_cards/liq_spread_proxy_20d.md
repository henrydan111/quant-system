# Factor Card: liq_spread_proxy_20d

## Basic Info
- Category: `Liquidity`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean(Ref(($high - $low) / (($high + $low) / 2), 1), 20)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.367`
- 10d Rank ICIR: `-0.431`
- 20d Rank ICIR: `-0.508`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.510 | -0.522 | -0.662 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.504 | -0.553 | -0.657 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.520 | -0.660 | -0.756 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.523 | -0.703 | -0.459 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.548 | -0.576 | -0.642 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.067 | -0.367 | 55.87% | 2,948 |
| size_neutral | -0.070 | -0.419 | 57.09% | 2,948 |
| industry_neutral | -0.062 | -0.491 | 58.85% | 2,948 |
| size_industry_neutral | -0.064 | -0.555 | 60.31% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.073 | -0.605 | 65.71% | 245 |
| 2015.000 | -0.054 | -0.400 | 61.48% | 244 |
| 2016.000 | -0.080 | -0.618 | 66.80% | 244 |
| 2017.000 | -0.061 | -0.522 | 63.52% | 244 |
| 2018.000 | -0.054 | -0.422 | 63.37% | 243 |
| 2019.000 | -0.062 | -0.587 | 61.07% | 244 |
| 2020.000 | -0.056 | -0.466 | 51.44% | 243 |
| 2021.000 | -0.066 | -0.662 | 58.02% | 243 |
| 2022.000 | -0.069 | -0.657 | 59.92% | 242 |
| 2023.000 | -0.070 | -0.756 | 59.09% | 242 |
| 2024.000 | -0.059 | -0.459 | 61.98% | 242 |
| 2025.000 | -0.070 | -0.642 | 52.26% | 243 |
| 2026.000 | -0.064 | -0.832 | 51.72% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.069 | -0.640 |
| -0.069 | -0.639 |
| -0.070 | -0.642 |
| -0.070 | -0.647 |
| -0.070 | -0.651 |
| -0.071 | -0.659 |
| -0.072 | -0.664 |
| -0.072 | -0.677 |
| -0.073 | -0.684 |
| -0.074 | -0.690 |
| -0.074 | -0.697 |
| -0.075 | -0.710 |
| -0.075 | -0.708 |
| -0.074 | -0.704 |
| -0.074 | -0.700 |
| -0.073 | -0.692 |
| -0.073 | -0.691 |
| -0.073 | -0.691 |
| -0.072 | -0.689 |
| -0.073 | -0.696 |
| -0.074 | -0.707 |
| -0.075 | -0.726 |
| -0.075 | -0.746 |
| -0.076 | -0.757 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.827`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.045 | -0.384 | 2,952 |
| 2.000 | -0.052 | -0.443 | 2,951 |
| 3.000 | -0.057 | -0.485 | 2,950 |
| 5.000 | -0.064 | -0.555 | 2,948 |
| 10.000 | -0.075 | -0.653 | 2,943 |
| 20.000 | -0.088 | -0.764 | 2,933 |
| 40.000 | -0.103 | -0.967 | 2,913 |
| 60.000 | -0.113 | -1.181 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-61.73%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-2.985`
- Monotonic: `False`
- Monotonic Spearman: `-0.700`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 1.074 | 0.621 | 1.729 | 2,948 |
| 2.000 | 0.005 | 1.163 | 0.659 | 1.765 | 2,948 |
| 3.000 | 0.004 | 1.078 | 0.681 | 1.582 | 2,948 |
| 4.000 | 0.003 | 0.875 | 0.713 | 1.228 | 2,948 |
| 5.000 | 0.001 | 0.162 | 0.783 | 0.207 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.733 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.906 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.912 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.924 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.919 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 10 | -0.005 | -0.097 |
| fold_02_2022 | 10 | 0.004 | 0.061 |
| fold_03_2023 | 8 | -0.000 | -0.006 |
| fold_04_2024 | 8 | -0.003 | -0.041 |
| fold_05_2025 | 6 | 0.003 | 0.039 |

## Risks
- Quantile monotonicity is weak in the 5d strategy-horizon diagnostic.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
