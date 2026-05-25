# Factor Card: comp_rev_low_turn

## Basic Info
- Category: `Other`
- Signal direction in strategy: `high_is_good`
- Raw expression: `COMPOSITE(rev_return_5d, liq_turnover_20d)`

## Screening Snapshot
- Grade: `A (Graduated)`
- 5d Rank ICIR: `0.484`
- 10d Rank ICIR: `0.505`
- 20d Rank ICIR: `0.550`
- Monotonic: `True`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | 0.855 | 0.646 | 0.747 | 1 | 1 | True | True | True |  |
| fold_02_2020 | 0.828 | 0.675 | 0.656 | 1 | 1 | True | True | False |  |
| fold_03_2021 | 0.815 | 0.699 | 0.880 | 1 | 1 | True | True | False |  |
| fold_04_2022 | 0.780 | 0.752 | 0.856 | 1 | 1 | True | True | False |  |
| fold_05_2023 | 0.738 | 0.869 | 0.800 | 1 | 1 | True | True | False |  |
| fold_06_2024 | 0.706 | 0.828 | 0.728 | 1 | 1 | True | True | False |  |
| fold_07_2025 | 0.737 | 0.752 | 1.087 | 1 | 1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | 0.066 | 0.484 | 60.28% | 3,429 |
| size_neutral | 0.073 | 0.578 | 63.78% | 3,429 |
| industry_neutral | 0.065 | 0.670 | 64.98% | 3,429 |
| size_industry_neutral | 0.070 | 0.792 | 69.12% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | 0.077 | 0.803 | 76.54% | 243 |
| 2013.000 | 0.075 | 0.685 | 65.55% | 238 |
| 2014.000 | 0.079 | 0.930 | 71.84% | 245 |
| 2015.000 | 0.090 | 0.871 | 75.82% | 244 |
| 2016.000 | 0.097 | 1.037 | 77.05% | 244 |
| 2017.000 | 0.061 | 0.678 | 65.16% | 244 |
| 2018.000 | 0.059 | 0.615 | 68.72% | 243 |
| 2019.000 | 0.063 | 0.747 | 70.08% | 244 |
| 2020.000 | 0.061 | 0.656 | 59.26% | 243 |
| 2021.000 | 0.066 | 0.880 | 66.67% | 243 |
| 2022.000 | 0.065 | 0.856 | 71.07% | 242 |
| 2023.000 | 0.056 | 0.800 | 64.05% | 242 |
| 2024.000 | 0.066 | 0.728 | 69.42% | 242 |
| 2025.000 | 0.075 | 1.087 | 67.49% | 243 |
| 2026.000 | 0.058 | 0.724 | 58.62% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| 0.074 | 1.038 |
| 0.074 | 1.035 |
| 0.074 | 1.034 |
| 0.075 | 1.034 |
| 0.075 | 1.035 |
| 0.075 | 1.044 |
| 0.075 | 1.037 |
| 0.075 | 1.037 |
| 0.075 | 1.038 |
| 0.075 | 1.036 |
| 0.075 | 1.040 |
| 0.075 | 1.053 |
| 0.075 | 1.051 |
| 0.075 | 1.051 |
| 0.075 | 1.050 |
| 0.075 | 1.044 |
| 0.074 | 1.043 |
| 0.074 | 1.043 |
| 0.074 | 1.041 |
| 0.073 | 1.039 |
| 0.073 | 1.038 |
| 0.073 | 1.047 |
| 0.073 | 1.045 |
| 0.073 | 1.042 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.923`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | 0.055 | 0.581 | 3,433 |
| 2.000 | 0.062 | 0.683 | 3,432 |
| 3.000 | 0.067 | 0.751 | 3,431 |
| 5.000 | 0.070 | 0.792 | 3,429 |
| 10.000 | 0.075 | 0.839 | 3,424 |
| 20.000 | 0.086 | 0.945 | 3,414 |
| 40.000 | 0.094 | 1.107 | 3,394 |
| 60.000 | 0.099 | 1.269 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `375.91%`
- Long-short total diagnostic return: `165622169600.00%`
- Long-short Sharpe: `6.726`
- Monotonic: `True`
- Monotonic Spearman: `1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | -0.001 | -0.173 | 0.717 | -0.241 | 3,429 |
| 2.000 | 0.003 | 0.866 | 0.671 | 1.291 | 3,429 |
| 3.000 | 0.004 | 1.022 | 0.652 | 1.568 | 3,429 |
| 4.000 | 0.005 | 1.214 | 0.647 | 1.875 | 3,429 |
| 5.000 | 0.006 | 1.420 | 0.657 | 2.160 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.577 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.569 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.600 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.621 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.668 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.630 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.601 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 7 | 0.011 | 0.182 |
| fold_02_2020 | 7 | 0.001 | 0.011 |
| fold_03_2021 | 5 | 0.008 | 0.133 |
| fold_04_2022 | 3 | 0.018 | 0.311 |
| fold_05_2023 | 3 | 0.021 | 0.333 |
| fold_06_2024 | 3 | 0.018 | 0.291 |
| fold_07_2025 | 1 | 0.026 | 0.334 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `1`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
