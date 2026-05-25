# Factor Card: risk_vol_60d

## Basic Info
- Category: `Volatility`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Std((Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 2) - 1), 60)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.306`
- 10d Rank ICIR: `-0.371`
- 20d Rank ICIR: `-0.454`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.395 | -0.501 | -0.596 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.398 | -0.537 | -0.566 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.457 | -0.580 | -0.744 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.468 | -0.649 | -0.416 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.490 | -0.543 | -0.506 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.059 | -0.306 | 55.12% | 2,948 |
| size_neutral | -0.063 | -0.358 | 56.11% | 2,948 |
| industry_neutral | -0.055 | -0.402 | 57.63% | 2,948 |
| size_industry_neutral | -0.058 | -0.469 | 58.92% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.060 | -0.470 | 61.63% | 245 |
| 2015.000 | -0.031 | -0.219 | 56.15% | 244 |
| 2016.000 | -0.071 | -0.499 | 63.11% | 244 |
| 2017.000 | -0.055 | -0.442 | 57.38% | 244 |
| 2018.000 | -0.051 | -0.360 | 58.85% | 243 |
| 2019.000 | -0.059 | -0.503 | 59.43% | 244 |
| 2020.000 | -0.062 | -0.498 | 62.14% | 243 |
| 2021.000 | -0.058 | -0.596 | 54.32% | 243 |
| 2022.000 | -0.060 | -0.566 | 59.50% | 242 |
| 2023.000 | -0.071 | -0.744 | 59.09% | 242 |
| 2024.000 | -0.057 | -0.416 | 61.57% | 242 |
| 2025.000 | -0.061 | -0.506 | 54.73% | 243 |
| 2026.000 | -0.067 | -0.838 | 51.72% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.061 | -0.509 |
| -0.060 | -0.508 |
| -0.061 | -0.510 |
| -0.061 | -0.514 |
| -0.062 | -0.518 |
| -0.062 | -0.524 |
| -0.063 | -0.529 |
| -0.064 | -0.541 |
| -0.065 | -0.551 |
| -0.066 | -0.559 |
| -0.066 | -0.567 |
| -0.067 | -0.575 |
| -0.066 | -0.571 |
| -0.066 | -0.566 |
| -0.065 | -0.560 |
| -0.064 | -0.551 |
| -0.063 | -0.550 |
| -0.063 | -0.549 |
| -0.063 | -0.552 |
| -0.064 | -0.564 |
| -0.065 | -0.581 |
| -0.066 | -0.604 |
| -0.067 | -0.630 |
| -0.068 | -0.647 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.842`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.038 | -0.305 | 2,952 |
| 2.000 | -0.045 | -0.365 | 2,951 |
| 3.000 | -0.050 | -0.403 | 2,950 |
| 5.000 | -0.058 | -0.469 | 2,948 |
| 10.000 | -0.070 | -0.576 | 2,943 |
| 20.000 | -0.086 | -0.708 | 2,933 |
| 40.000 | -0.105 | -0.950 | 2,913 |
| 60.000 | -0.119 | -1.199 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-56.74%`
- Long-short total diagnostic return: `-99.99%`
- Long-short Sharpe: `-2.505`
- Monotonic: `True`
- Monotonic Spearman: `-0.900`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 1.095 | 0.619 | 1.769 | 2,948 |
| 2.000 | 0.004 | 1.098 | 0.656 | 1.674 | 2,948 |
| 3.000 | 0.004 | 1.019 | 0.676 | 1.507 | 2,948 |
| 4.000 | 0.003 | 0.814 | 0.710 | 1.147 | 2,948 |
| 5.000 | 0.001 | 0.308 | 0.795 | 0.387 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.711 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.625 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.641 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.654 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.679 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 10 | -0.015 | -0.247 |
| fold_02_2022 | 10 | -0.005 | -0.077 |
| fold_03_2023 | 10 | -0.004 | -0.085 |
| fold_04_2024 | 8 | -0.012 | -0.178 |
| fold_05_2025 | 8 | -0.011 | -0.153 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
