# Factor Card: mom_ewm_20d

## Basic Info
- Category: `Momentum`
- Signal direction in strategy: `low_is_good`
- Raw expression: `EMA((($close * $adj_factor) / Ref(($close * $adj_factor), 1) - 1), 20)`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `-0.435`
- 10d Rank ICIR: `-0.431`
- 20d Rank ICIR: `-0.479`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.761 | -0.473 | -0.816 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.719 | -0.669 | -0.414 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.671 | -0.602 | -0.679 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.668 | -0.535 | -0.689 | -1 | -1 | True | True | False |  |
| fold_05_2023 | -0.580 | -0.684 | -0.553 | -1 | -1 | True | True | False |  |
| fold_06_2024 | -0.554 | -0.619 | -0.474 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.615 | -0.493 | -0.971 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.065 | -0.435 | 59.17% | 3,429 |
| size_neutral | -0.067 | -0.494 | 60.19% | 3,429 |
| industry_neutral | -0.066 | -0.559 | 63.78% | 3,429 |
| size_industry_neutral | -0.067 | -0.645 | 64.60% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.079 | -0.593 | 75.72% | 243 |
| 2013.000 | -0.082 | -0.793 | 64.71% | 238 |
| 2014.000 | -0.079 | -0.831 | 60.82% | 245 |
| 2015.000 | -0.096 | -0.874 | 56.56% | 244 |
| 2016.000 | -0.089 | -0.785 | 72.95% | 244 |
| 2017.000 | -0.047 | -0.399 | 58.61% | 244 |
| 2018.000 | -0.062 | -0.552 | 66.67% | 243 |
| 2019.000 | -0.077 | -0.816 | 68.44% | 244 |
| 2020.000 | -0.040 | -0.414 | 56.79% | 243 |
| 2021.000 | -0.058 | -0.679 | 60.91% | 243 |
| 2022.000 | -0.055 | -0.689 | 73.55% | 242 |
| 2023.000 | -0.046 | -0.553 | 68.18% | 242 |
| 2024.000 | -0.060 | -0.474 | 67.77% | 242 |
| 2025.000 | -0.077 | -0.971 | 67.90% | 243 |
| 2026.000 | -0.035 | -0.538 | 48.28% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.075 | -0.949 |
| -0.076 | -0.954 |
| -0.076 | -0.955 |
| -0.076 | -0.955 |
| -0.076 | -0.949 |
| -0.075 | -0.939 |
| -0.074 | -0.929 |
| -0.073 | -0.920 |
| -0.072 | -0.909 |
| -0.071 | -0.899 |
| -0.071 | -0.892 |
| -0.070 | -0.883 |
| -0.070 | -0.888 |
| -0.070 | -0.891 |
| -0.070 | -0.890 |
| -0.070 | -0.889 |
| -0.070 | -0.894 |
| -0.070 | -0.891 |
| -0.070 | -0.892 |
| -0.069 | -0.896 |
| -0.068 | -0.898 |
| -0.068 | -0.903 |
| -0.067 | -0.899 |
| -0.067 | -0.892 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.524`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.052 | -0.460 | 3,433 |
| 2.000 | -0.058 | -0.521 | 3,432 |
| 3.000 | -0.062 | -0.572 | 3,431 |
| 5.000 | -0.067 | -0.645 | 3,429 |
| 10.000 | -0.065 | -0.661 | 3,424 |
| 20.000 | -0.068 | -0.728 | 3,414 |
| 40.000 | -0.060 | -0.684 | 3,394 |
| 60.000 | -0.054 | -0.639 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `0.00%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-5.141`
- Monotonic: `True`
- Monotonic Spearman: `-0.900`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.294 | 0.738 | 1.755 | 3,429 |
| 2.000 | 0.005 | 1.304 | 0.683 | 1.910 | 3,429 |
| 3.000 | 0.004 | 1.086 | 0.648 | 1.677 | 3,429 |
| 4.000 | 0.003 | 0.801 | 0.631 | 1.268 | 3,429 |
| 5.000 | -0.000 | -0.120 | 0.664 | -0.180 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.673 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.637 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.669 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.698 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.687 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.676 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.663 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | -0.015 | -0.188 |
| fold_02_2020 | 7 | -0.013 | -0.176 |
| fold_03_2021 | 10 | -0.019 | -0.308 |
| fold_04_2022 | 7 | -0.022 | -0.279 |
| fold_05_2023 | 8 | -0.015 | -0.259 |
| fold_06_2024 | 10 | -0.017 | -0.299 |
| fold_07_2025 | 10 | -0.015 | -0.225 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
