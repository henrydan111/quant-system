# Factor Card: comp_defensive

## Basic Info
- Category: `Other`
- Signal direction in strategy: `high_is_good`
- Raw expression: `COMPOSITE(qual_roe, risk_vol_20d)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `0.300`
- 10d Rank ICIR: `0.339`
- 20d Rank ICIR: `0.382`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | 0.589 | 0.640 | 0.703 | 1 | 1 | True | True | True |  |
| fold_02_2022 | 0.587 | 0.730 | 0.602 | 1 | 1 | True | True | True |  |
| fold_03_2023 | 0.663 | 0.650 | 0.693 | 1 | 1 | True | True | True |  |
| fold_04_2024 | 0.669 | 0.647 | 0.349 | 1 | 1 | True | True | False |  |
| fold_05_2025 | 0.621 | 0.438 | 0.532 | 1 | 1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | 0.048 | 0.300 | 52.61% | 2,948 |
| size_neutral | 0.058 | 0.440 | 56.31% | 2,948 |
| industry_neutral | 0.045 | 0.364 | 55.09% | 2,948 |
| size_industry_neutral | 0.054 | 0.563 | 60.75% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | 0.044 | 0.571 | 56.33% | 245 |
| 2015.000 | 0.044 | 0.402 | 62.70% | 244 |
| 2016.000 | 0.061 | 0.644 | 65.57% | 244 |
| 2017.000 | 0.070 | 0.861 | 72.13% | 244 |
| 2018.000 | 0.050 | 0.560 | 65.02% | 243 |
| 2019.000 | 0.059 | 0.559 | 58.61% | 244 |
| 2020.000 | 0.061 | 0.761 | 67.90% | 243 |
| 2021.000 | 0.047 | 0.703 | 58.44% | 243 |
| 2022.000 | 0.046 | 0.602 | 55.79% | 242 |
| 2023.000 | 0.051 | 0.693 | 61.16% | 242 |
| 2024.000 | 0.052 | 0.349 | 53.72% | 242 |
| 2025.000 | 0.056 | 0.532 | 52.67% | 243 |
| 2026.000 | 0.062 | 0.616 | 51.72% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| 0.058 | 0.542 |
| 0.058 | 0.542 |
| 0.058 | 0.543 |
| 0.058 | 0.544 |
| 0.058 | 0.542 |
| 0.058 | 0.545 |
| 0.059 | 0.550 |
| 0.059 | 0.556 |
| 0.060 | 0.562 |
| 0.060 | 0.568 |
| 0.061 | 0.573 |
| 0.061 | 0.577 |
| 0.061 | 0.572 |
| 0.060 | 0.567 |
| 0.058 | 0.560 |
| 0.057 | 0.546 |
| 0.056 | 0.541 |
| 0.056 | 0.542 |
| 0.056 | 0.546 |
| 0.057 | 0.559 |
| 0.059 | 0.582 |
| 0.060 | 0.609 |
| 0.061 | 0.632 |
| 0.062 | 0.648 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.747`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | 0.036 | 0.395 | 2,952 |
| 2.000 | 0.043 | 0.463 | 2,951 |
| 3.000 | 0.047 | 0.503 | 2,950 |
| 5.000 | 0.054 | 0.563 | 2,948 |
| 10.000 | 0.062 | 0.641 | 2,943 |
| 20.000 | 0.073 | 0.740 | 2,933 |
| 40.000 | 0.084 | 0.910 | 2,913 |
| 60.000 | 0.091 | 1.014 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `133.74%`
- Long-short total diagnostic return: `2058231.25%`
- Long-short Sharpe: `3.616`
- Monotonic: `True`
- Monotonic Spearman: `1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.001 | 0.276 | 0.770 | 0.358 | 2,948 |
| 2.000 | 0.003 | 0.866 | 0.720 | 1.203 | 2,948 |
| 3.000 | 0.004 | 0.989 | 0.676 | 1.464 | 2,948 |
| 4.000 | 0.004 | 1.057 | 0.647 | 1.634 | 2,948 |
| 5.000 | 0.005 | 1.156 | 0.630 | 1.834 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.366 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.346 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.330 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.295 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.291 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 7 | 0.020 | 0.287 |
| fold_02_2022 | 4 | 0.018 | 0.306 |
| fold_03_2023 | 8 | -0.002 | -0.045 |
| fold_04_2024 | 9 | 0.001 | 0.013 |
| fold_05_2025 | 10 | 0.007 | 0.070 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `keep`
- Selected folds: `3`
- Validation-pass folds: `5`
- Summary: Repeatedly selected across OOS folds.
