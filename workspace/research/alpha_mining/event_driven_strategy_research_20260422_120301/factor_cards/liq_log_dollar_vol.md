# Factor Card: liq_log_dollar_vol

## Basic Info
- Category: `Liquidity`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Log(Mean(Ref($amount, 1) * 1000, 20))`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.507`
- 10d Rank ICIR: `-0.604`
- 20d Rank ICIR: `-0.693`
- Monotonic: `True`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.647 | -0.467 | -0.611 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.618 | -0.503 | -0.543 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.573 | -0.575 | -0.589 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.530 | -0.566 | -0.434 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.517 | -0.502 | -0.568 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.071 | -0.508 | 64.69% | 2,948 |
| size_neutral | -0.066 | -0.454 | 61.43% | 2,948 |
| industry_neutral | -0.064 | -0.580 | 67.91% | 2,948 |
| size_industry_neutral | -0.059 | -0.570 | 64.48% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.061 | -0.632 | 67.35% | 245 |
| 2015.000 | -0.059 | -0.659 | 74.59% | 244 |
| 2016.000 | -0.087 | -0.824 | 73.36% | 244 |
| 2017.000 | -0.059 | -0.616 | 71.72% | 244 |
| 2018.000 | -0.065 | -0.542 | 66.67% | 243 |
| 2019.000 | -0.058 | -0.502 | 62.70% | 244 |
| 2020.000 | -0.051 | -0.433 | 59.26% | 243 |
| 2021.000 | -0.053 | -0.611 | 58.02% | 243 |
| 2022.000 | -0.053 | -0.543 | 60.74% | 242 |
| 2023.000 | -0.055 | -0.589 | 64.88% | 242 |
| 2024.000 | -0.049 | -0.434 | 57.02% | 242 |
| 2025.000 | -0.061 | -0.568 | 59.26% | 243 |
| 2026.000 | -0.053 | -0.561 | 48.28% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.062 | -0.571 |
| -0.062 | -0.571 |
| -0.061 | -0.571 |
| -0.062 | -0.573 |
| -0.062 | -0.572 |
| -0.062 | -0.579 |
| -0.063 | -0.584 |
| -0.063 | -0.593 |
| -0.064 | -0.602 |
| -0.065 | -0.610 |
| -0.066 | -0.620 |
| -0.067 | -0.633 |
| -0.067 | -0.633 |
| -0.067 | -0.633 |
| -0.066 | -0.629 |
| -0.066 | -0.621 |
| -0.065 | -0.619 |
| -0.065 | -0.619 |
| -0.065 | -0.617 |
| -0.065 | -0.622 |
| -0.066 | -0.630 |
| -0.067 | -0.645 |
| -0.067 | -0.660 |
| -0.067 | -0.665 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `1.106`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.036 | -0.327 | 2,952 |
| 2.000 | -0.044 | -0.414 | 2,951 |
| 3.000 | -0.050 | -0.472 | 2,950 |
| 5.000 | -0.059 | -0.570 | 2,948 |
| 10.000 | -0.073 | -0.719 | 2,943 |
| 20.000 | -0.090 | -0.893 | 2,933 |
| 40.000 | -0.109 | -1.166 | 2,913 |
| 60.000 | -0.121 | -1.443 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-73.50%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-4.923`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.289 | 0.627 | 2.056 | 2,948 |
| 2.000 | 0.005 | 1.207 | 0.664 | 1.817 | 2,948 |
| 3.000 | 0.004 | 1.063 | 0.681 | 1.561 | 2,948 |
| 4.000 | 0.003 | 0.801 | 0.705 | 1.137 | 2,948 |
| 5.000 | -0.000 | -0.008 | 0.768 | -0.010 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.677 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.677 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.654 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.632 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.623 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 10 | 0.002 | 0.025 |
| fold_02_2022 | 8 | 0.001 | 0.008 |
| fold_03_2023 | 8 | -0.006 | -0.094 |
| fold_04_2024 | 9 | -0.004 | -0.056 |
| fold_05_2025 | 10 | 0.005 | 0.072 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
