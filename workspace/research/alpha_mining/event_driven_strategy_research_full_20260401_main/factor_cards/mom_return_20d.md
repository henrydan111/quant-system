# Factor Card: mom_return_20d

## Basic Info
- Category: `Momentum`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 21) - 1`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `-0.371`
- 10d Rank ICIR: `-0.424`
- 20d Rank ICIR: `-0.471`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.638 | -0.495 | -0.772 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.632 | -0.672 | -0.366 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.619 | -0.562 | -0.517 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.659 | -0.441 | -0.565 | -1 | -1 | True | True | False |  |
| fold_05_2023 | -0.554 | -0.541 | -0.348 | -1 | -1 | True | True | False |  |
| fold_06_2024 | -0.522 | -0.455 | -0.454 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.558 | -0.399 | -0.705 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.055 | -0.371 | 60.45% | 3,429 |
| size_neutral | -0.056 | -0.417 | 61.71% | 3,429 |
| industry_neutral | -0.054 | -0.485 | 64.74% | 3,429 |
| size_industry_neutral | -0.055 | -0.554 | 66.11% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.058 | -0.463 | 68.31% | 243 |
| 2013.000 | -0.061 | -0.668 | 60.92% | 238 |
| 2014.000 | -0.048 | -0.542 | 61.22% | 245 |
| 2015.000 | -0.104 | -0.917 | 75.82% | 244 |
| 2016.000 | -0.071 | -0.671 | 68.03% | 244 |
| 2017.000 | -0.044 | -0.411 | 60.66% | 244 |
| 2018.000 | -0.058 | -0.588 | 75.72% | 243 |
| 2019.000 | -0.067 | -0.772 | 72.54% | 244 |
| 2020.000 | -0.030 | -0.366 | 58.02% | 243 |
| 2021.000 | -0.042 | -0.517 | 57.20% | 243 |
| 2022.000 | -0.044 | -0.565 | 71.49% | 242 |
| 2023.000 | -0.027 | -0.348 | 66.94% | 242 |
| 2024.000 | -0.056 | -0.454 | 69.42% | 242 |
| 2025.000 | -0.058 | -0.705 | 62.55% | 243 |
| 2026.000 | -0.007 | -0.152 | 62.07% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.057 | -0.687 |
| -0.056 | -0.686 |
| -0.056 | -0.684 |
| -0.056 | -0.683 |
| -0.056 | -0.674 |
| -0.055 | -0.669 |
| -0.054 | -0.658 |
| -0.053 | -0.652 |
| -0.052 | -0.646 |
| -0.051 | -0.639 |
| -0.051 | -0.634 |
| -0.050 | -0.628 |
| -0.051 | -0.638 |
| -0.052 | -0.664 |
| -0.053 | -0.685 |
| -0.053 | -0.689 |
| -0.053 | -0.701 |
| -0.053 | -0.699 |
| -0.053 | -0.695 |
| -0.052 | -0.696 |
| -0.051 | -0.692 |
| -0.050 | -0.687 |
| -0.049 | -0.680 |
| -0.049 | -0.670 |

## IC Decay
- Best horizon by |ICIR|: `20`
- Peak ICIR: `0.552`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.039 | -0.390 | 3,433 |
| 2.000 | -0.044 | -0.445 | 3,432 |
| 3.000 | -0.050 | -0.498 | 3,431 |
| 5.000 | -0.055 | -0.554 | 3,429 |
| 10.000 | -0.059 | -0.618 | 3,424 |
| 20.000 | -0.063 | -0.660 | 3,414 |
| 40.000 | -0.053 | -0.598 | 3,394 |
| 60.000 | -0.048 | -0.554 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `0.00%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-5.340`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.318 | 0.724 | 1.821 | 3,429 |
| 2.000 | 0.005 | 1.246 | 0.672 | 1.856 | 3,429 |
| 3.000 | 0.004 | 1.104 | 0.645 | 1.712 | 3,429 |
| 4.000 | 0.003 | 0.821 | 0.639 | 1.285 | 3,429 |
| 5.000 | -0.000 | -0.126 | 0.680 | -0.185 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.772 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.737 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.743 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.727 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.774 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.763 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.753 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.007 | 0.143 |
| fold_02_2020 | 7 | 0.008 | 0.140 |
| fold_03_2021 | 10 | 0.001 | 0.028 |
| fold_04_2022 | 10 | -0.003 | -0.058 |
| fold_05_2023 | 9 | 0.015 | 0.377 |
| fold_06_2024 | 10 | 0.013 | 0.306 |
| fold_07_2025 | 10 | 0.012 | 0.201 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
