# Factor Card: comp_small_value

## Basic Info
- Category: `Other`
- Signal direction in strategy: `high_is_good`
- Raw expression: `COMPOSITE(size_ln_mcap, val_bp)`

## Screening Snapshot
- Grade: `A (Graduated)`
- 5d Rank ICIR: `0.358`
- 10d Rank ICIR: `0.422`
- 20d Rank ICIR: `0.498`
- Monotonic: `True`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | 0.446 | 0.384 | 0.379 | 1 | 1 | True | True | False |  |
| fold_02_2020 | 0.449 | 0.361 | 0.166 | 1 | 1 | True | True | False |  |
| fold_03_2021 | 0.485 | 0.252 | 0.470 | 1 | 1 | True | True | False |  |
| fold_04_2022 | 0.442 | 0.309 | 0.469 | 1 | 1 | True | True | False |  |
| fold_05_2023 | 0.388 | 0.470 | 0.890 | 1 | 1 | True | True | False |  |
| fold_06_2024 | 0.349 | 0.648 | 0.585 | 1 | 1 | True | True | True |  |
| fold_07_2025 | 0.359 | 0.724 | 0.557 | 1 | 1 | True | True | True |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | 0.050 | 0.358 | 61.01% | 3,429 |
| size_neutral | 0.042 | 0.290 | 54.21% | 3,429 |
| industry_neutral | 0.047 | 0.403 | 65.12% | 3,429 |
| size_industry_neutral | 0.041 | 0.456 | 59.26% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | 0.027 | 0.433 | 61.32% | 243 |
| 2013.000 | 0.013 | 0.155 | 57.98% | 238 |
| 2014.000 | 0.057 | 0.600 | 66.12% | 245 |
| 2015.000 | 0.042 | 0.402 | 58.20% | 244 |
| 2016.000 | 0.065 | 0.673 | 71.31% | 244 |
| 2017.000 | 0.035 | 0.425 | 60.25% | 244 |
| 2018.000 | 0.035 | 0.353 | 58.85% | 243 |
| 2019.000 | 0.029 | 0.379 | 58.20% | 244 |
| 2020.000 | 0.017 | 0.166 | 48.15% | 243 |
| 2021.000 | 0.045 | 0.470 | 54.32% | 243 |
| 2022.000 | 0.043 | 0.469 | 53.72% | 242 |
| 2023.000 | 0.067 | 0.890 | 71.49% | 242 |
| 2024.000 | 0.049 | 0.585 | 69.42% | 242 |
| 2025.000 | 0.047 | 0.557 | 54.32% | 243 |
| 2026.000 | 0.076 | 1.192 | 72.41% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| 0.047 | 0.558 |
| 0.047 | 0.558 |
| 0.047 | 0.560 |
| 0.048 | 0.564 |
| 0.049 | 0.572 |
| 0.049 | 0.581 |
| 0.050 | 0.588 |
| 0.051 | 0.602 |
| 0.051 | 0.609 |
| 0.052 | 0.616 |
| 0.053 | 0.623 |
| 0.053 | 0.630 |
| 0.053 | 0.635 |
| 0.054 | 0.638 |
| 0.054 | 0.639 |
| 0.054 | 0.640 |
| 0.054 | 0.639 |
| 0.054 | 0.638 |
| 0.054 | 0.638 |
| 0.054 | 0.639 |
| 0.054 | 0.644 |
| 0.054 | 0.653 |
| 0.055 | 0.661 |
| 0.055 | 0.662 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.630`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | 0.029 | 0.351 | 3,433 |
| 2.000 | 0.033 | 0.383 | 3,432 |
| 3.000 | 0.036 | 0.412 | 3,431 |
| 5.000 | 0.041 | 0.456 | 3,429 |
| 10.000 | 0.050 | 0.526 | 3,424 |
| 20.000 | 0.062 | 0.620 | 3,414 |
| 40.000 | 0.076 | 0.754 | 3,394 |
| 60.000 | 0.087 | 0.890 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `132.68%`
- Long-short total diagnostic return: `9782701.56%`
- Long-short Sharpe: `4.227`
- Monotonic: `True`
- Monotonic Spearman: `1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.001 | 0.363 | 0.691 | 0.526 | 3,429 |
| 2.000 | 0.003 | 0.715 | 0.697 | 1.027 | 3,429 |
| 3.000 | 0.004 | 0.950 | 0.662 | 1.436 | 3,429 |
| 4.000 | 0.004 | 1.116 | 0.650 | 1.716 | 3,429 |
| 5.000 | 0.005 | 1.230 | 0.647 | 1.900 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.259 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.280 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.282 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.268 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.280 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.274 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.188 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.012 | 0.186 |
| fold_02_2020 | 10 | 0.009 | 0.140 |
| fold_03_2021 | 10 | 0.004 | 0.061 |
| fold_04_2022 | 10 | 0.010 | 0.124 |
| fold_05_2023 | 10 | 0.022 | 0.283 |
| fold_06_2024 | 8 | 0.034 | 0.472 |
| fold_07_2025 | 2 | 0.041 | 0.565 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `2`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
