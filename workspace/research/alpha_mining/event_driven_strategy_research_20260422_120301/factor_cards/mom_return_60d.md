# Factor Card: mom_return_60d

## Basic Info
- Category: `Momentum`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 61) - 1`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.345`
- 10d Rank ICIR: `-0.415`
- 20d Rank ICIR: `-0.466`
- Monotonic: `True`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.558 | -0.386 | -0.489 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.506 | -0.400 | -0.417 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.384 | -0.454 | -0.197 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.355 | -0.307 | -0.312 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.395 | -0.258 | -0.703 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.053 | -0.345 | 59.19% | 2,948 |
| size_neutral | -0.051 | -0.378 | 59.91% | 2,948 |
| industry_neutral | -0.046 | -0.398 | 61.80% | 2,948 |
| size_industry_neutral | -0.045 | -0.452 | 62.31% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.064 | -0.768 | 71.43% | 245 |
| 2015.000 | -0.097 | -1.019 | 75.41% | 244 |
| 2016.000 | -0.060 | -0.648 | 66.39% | 244 |
| 2017.000 | -0.026 | -0.241 | 56.97% | 244 |
| 2018.000 | -0.032 | -0.311 | 64.61% | 243 |
| 2019.000 | -0.042 | -0.458 | 61.89% | 244 |
| 2020.000 | -0.029 | -0.315 | 54.32% | 243 |
| 2021.000 | -0.043 | -0.489 | 58.44% | 243 |
| 2022.000 | -0.036 | -0.417 | 66.12% | 242 |
| 2023.000 | -0.017 | -0.197 | 55.37% | 242 |
| 2024.000 | -0.048 | -0.312 | 60.33% | 242 |
| 2025.000 | -0.050 | -0.703 | 57.61% | 243 |
| 2026.000 | -0.012 | -0.235 | 51.72% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.049 | -0.700 |
| -0.049 | -0.700 |
| -0.049 | -0.702 |
| -0.049 | -0.705 |
| -0.049 | -0.703 |
| -0.050 | -0.709 |
| -0.049 | -0.702 |
| -0.049 | -0.703 |
| -0.049 | -0.703 |
| -0.049 | -0.699 |
| -0.049 | -0.693 |
| -0.049 | -0.690 |
| -0.049 | -0.684 |
| -0.048 | -0.680 |
| -0.048 | -0.678 |
| -0.048 | -0.672 |
| -0.048 | -0.675 |
| -0.048 | -0.674 |
| -0.048 | -0.671 |
| -0.047 | -0.671 |
| -0.046 | -0.671 |
| -0.046 | -0.668 |
| -0.045 | -0.660 |
| -0.045 | -0.649 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.529`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.029 | -0.298 | 2,952 |
| 2.000 | -0.034 | -0.339 | 2,951 |
| 3.000 | -0.039 | -0.383 | 2,950 |
| 5.000 | -0.045 | -0.452 | 2,948 |
| 10.000 | -0.053 | -0.532 | 2,943 |
| 20.000 | -0.057 | -0.582 | 2,933 |
| 40.000 | -0.054 | -0.597 | 2,913 |
| 60.000 | -0.049 | -0.587 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-70.39%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-4.123`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.231 | 0.744 | 1.654 | 2,948 |
| 2.000 | 0.004 | 1.131 | 0.684 | 1.653 | 2,948 |
| 3.000 | 0.004 | 1.053 | 0.659 | 1.599 | 2,948 |
| 4.000 | 0.003 | 0.837 | 0.658 | 1.273 | 2,948 |
| 5.000 | 0.000 | 0.061 | 0.704 | 0.087 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.439 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.886 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.854 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.445 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.472 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 10 | 0.013 | 0.178 |
| fold_02_2022 | 9 | 0.006 | 0.117 |
| fold_03_2023 | 10 | -0.003 | -0.073 |
| fold_04_2024 | 10 | 0.011 | 0.145 |
| fold_05_2025 | 10 | 0.016 | 0.176 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
