# Factor Card: tech_close_to_low_20d

## Basic Info
- Category: `Technical`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Ref(($close * $adj_factor), 1) / Min(($low * $adj_factor), 20) - 1`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `-0.406`
- 10d Rank ICIR: `-0.396`
- 20d Rank ICIR: `-0.428`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.689 | -0.513 | -0.825 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.696 | -0.664 | -0.543 | -1 | -1 | True | True | True |  |
| fold_03_2021 | -0.668 | -0.679 | -0.815 | -1 | -1 | True | True | True |  |
| fold_04_2022 | -0.682 | -0.664 | -0.742 | -1 | -1 | True | True | True |  |
| fold_05_2023 | -0.654 | -0.779 | -0.725 | -1 | -1 | True | True | False |  |
| fold_06_2024 | -0.626 | -0.731 | -0.458 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.673 | -0.559 | -0.824 | -1 | -1 | True | True | True |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.054 | -0.406 | 60.69% | 3,429 |
| size_neutral | -0.057 | -0.450 | 62.06% | 3,429 |
| industry_neutral | -0.053 | -0.597 | 65.73% | 3,429 |
| size_industry_neutral | -0.055 | -0.652 | 66.75% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.050 | -0.490 | 68.31% | 243 |
| 2013.000 | -0.062 | -0.659 | 57.14% | 238 |
| 2014.000 | -0.062 | -0.733 | 67.76% | 245 |
| 2015.000 | -0.072 | -0.698 | 66.80% | 244 |
| 2016.000 | -0.081 | -0.925 | 74.18% | 244 |
| 2017.000 | -0.045 | -0.509 | 63.93% | 244 |
| 2018.000 | -0.042 | -0.519 | 70.78% | 243 |
| 2019.000 | -0.065 | -0.825 | 71.72% | 244 |
| 2020.000 | -0.041 | -0.543 | 58.02% | 243 |
| 2021.000 | -0.052 | -0.815 | 60.91% | 243 |
| 2022.000 | -0.045 | -0.742 | 73.55% | 242 |
| 2023.000 | -0.051 | -0.725 | 70.66% | 242 |
| 2024.000 | -0.046 | -0.458 | 69.42% | 242 |
| 2025.000 | -0.062 | -0.824 | 63.79% | 243 |
| 2026.000 | -0.032 | -0.560 | 44.83% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.060 | -0.801 |
| -0.060 | -0.802 |
| -0.060 | -0.811 |
| -0.061 | -0.813 |
| -0.060 | -0.807 |
| -0.060 | -0.811 |
| -0.060 | -0.810 |
| -0.060 | -0.804 |
| -0.060 | -0.802 |
| -0.059 | -0.794 |
| -0.059 | -0.792 |
| -0.059 | -0.788 |
| -0.059 | -0.780 |
| -0.058 | -0.776 |
| -0.058 | -0.773 |
| -0.057 | -0.767 |
| -0.057 | -0.762 |
| -0.057 | -0.761 |
| -0.057 | -0.761 |
| -0.057 | -0.761 |
| -0.056 | -0.760 |
| -0.057 | -0.762 |
| -0.056 | -0.761 |
| -0.056 | -0.756 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.657`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.048 | -0.543 | 3,433 |
| 2.000 | -0.051 | -0.586 | 3,432 |
| 3.000 | -0.054 | -0.632 | 3,431 |
| 5.000 | -0.055 | -0.652 | 3,429 |
| 10.000 | -0.055 | -0.661 | 3,424 |
| 20.000 | -0.058 | -0.721 | 3,414 |
| 40.000 | -0.059 | -0.723 | 3,394 |
| 60.000 | -0.061 | -0.788 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-69.01%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-4.867`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.148 | 0.671 | 1.712 | 3,429 |
| 2.000 | 0.005 | 1.147 | 0.666 | 1.723 | 3,429 |
| 3.000 | 0.004 | 1.076 | 0.657 | 1.638 | 3,429 |
| 4.000 | 0.004 | 0.984 | 0.664 | 1.482 | 3,429 |
| 5.000 | 0.000 | 0.010 | 0.701 | 0.015 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.585 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.551 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.597 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.557 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.616 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.602 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.561 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.027 | 0.538 |
| fold_02_2020 | 7 | 0.020 | 0.412 |
| fold_03_2021 | 5 | 0.021 | 0.424 |
| fold_04_2022 | 4 | 0.007 | 0.109 |
| fold_05_2023 | 5 | 0.012 | 0.278 |
| fold_06_2024 | 6 | 0.005 | 0.103 |
| fold_07_2025 | 7 | 0.005 | 0.097 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `keep`
- Selected folds: `4`
- Validation-pass folds: `7`
- Summary: Repeatedly selected across OOS folds.
