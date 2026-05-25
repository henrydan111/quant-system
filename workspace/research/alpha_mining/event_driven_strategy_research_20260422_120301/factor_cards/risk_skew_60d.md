# Factor Card: risk_skew_60d

## Basic Info
- Category: `Volatility`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Skew((Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 2) - 1), 60)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.468`
- 10d Rank ICIR: `-0.516`
- 20d Rank ICIR: `-0.515`
- Monotonic: `True`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.619 | -0.626 | -0.796 | -1 | -1 | True | True | True |  |
| fold_02_2022 | -0.567 | -0.666 | -0.666 | -1 | -1 | True | True | True |  |
| fold_03_2023 | -0.643 | -0.716 | -0.790 | -1 | -1 | True | True | True |  |
| fold_04_2024 | -0.686 | -0.722 | -0.450 | -1 | -1 | True | True | True |  |
| fold_05_2025 | -0.682 | -0.531 | -0.688 | -1 | -1 | True | True | True |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.039 | -0.468 | 63.98% | 2,948 |
| size_neutral | -0.037 | -0.510 | 63.53% | 2,948 |
| industry_neutral | -0.035 | -0.550 | 66.99% | 2,948 |
| size_industry_neutral | -0.034 | -0.616 | 65.88% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.041 | -1.177 | 74.69% | 245 |
| 2015.000 | -0.016 | -0.259 | 59.43% | 244 |
| 2016.000 | -0.042 | -0.580 | 69.67% | 244 |
| 2017.000 | -0.037 | -0.694 | 71.31% | 244 |
| 2018.000 | -0.045 | -0.768 | 71.60% | 243 |
| 2019.000 | -0.028 | -0.679 | 69.67% | 244 |
| 2020.000 | -0.028 | -0.581 | 59.26% | 243 |
| 2021.000 | -0.028 | -0.796 | 63.79% | 243 |
| 2022.000 | -0.031 | -0.666 | 62.81% | 242 |
| 2023.000 | -0.032 | -0.790 | 62.81% | 242 |
| 2024.000 | -0.037 | -0.450 | 66.53% | 242 |
| 2025.000 | -0.039 | -0.688 | 58.85% | 243 |
| 2026.000 | -0.048 | -1.128 | 65.52% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.039 | -0.681 |
| -0.039 | -0.685 |
| -0.040 | -0.688 |
| -0.040 | -0.690 |
| -0.040 | -0.699 |
| -0.040 | -0.706 |
| -0.041 | -0.711 |
| -0.041 | -0.728 |
| -0.042 | -0.737 |
| -0.042 | -0.745 |
| -0.042 | -0.753 |
| -0.043 | -0.760 |
| -0.043 | -0.759 |
| -0.042 | -0.758 |
| -0.042 | -0.756 |
| -0.042 | -0.750 |
| -0.042 | -0.749 |
| -0.041 | -0.749 |
| -0.041 | -0.747 |
| -0.041 | -0.750 |
| -0.042 | -0.757 |
| -0.042 | -0.771 |
| -0.043 | -0.799 |
| -0.043 | -0.818 |

## IC Decay
- Best horizon by |ICIR|: `20`
- Peak ICIR: `0.465`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.023 | -0.440 | 2,952 |
| 2.000 | -0.027 | -0.503 | 2,951 |
| 3.000 | -0.030 | -0.545 | 2,950 |
| 5.000 | -0.034 | -0.616 | 2,948 |
| 10.000 | -0.039 | -0.697 | 2,943 |
| 20.000 | -0.042 | -0.755 | 2,933 |
| 40.000 | -0.041 | -0.752 | 2,913 |
| 60.000 | -0.042 | -0.783 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-44.42%`
- Long-short total diagnostic return: `-99.90%`
- Long-short Sharpe: `-3.942`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 1.125 | 0.667 | 1.686 | 2,948 |
| 2.000 | 0.004 | 1.052 | 0.685 | 1.535 | 2,948 |
| 3.000 | 0.003 | 0.862 | 0.694 | 1.241 | 2,948 |
| 4.000 | 0.003 | 0.742 | 0.696 | 1.066 | 2,948 |
| 5.000 | 0.002 | 0.549 | 0.691 | 0.795 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.351 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.348 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.381 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.393 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.444 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 7 | -0.009 | -0.247 |
| fold_02_2022 | 4 | -0.009 | -0.236 |
| fold_03_2023 | 5 | -0.006 | -0.185 |
| fold_04_2024 | 6 | -0.006 | -0.190 |
| fold_05_2025 | 9 | -0.004 | -0.094 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `keep`
- Selected folds: `5`
- Validation-pass folds: `5`
- Summary: Repeatedly selected across OOS folds.
