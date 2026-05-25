# Factor Card: comp_small_value

## Basic Info
- Category: `Other`
- Signal direction in strategy: `high_is_good`
- Raw expression: `COMPOSITE(size_ln_mcap, val_bp)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `0.362`
- 10d Rank ICIR: `0.426`
- 20d Rank ICIR: `0.503`
- Monotonic: `True`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | 0.485 | 0.252 | 0.470 | 1 | 1 | True | True | False |  |
| fold_02_2022 | 0.442 | 0.309 | 0.469 | 1 | 1 | True | True | False |  |
| fold_03_2023 | 0.388 | 0.470 | 0.890 | 1 | 1 | True | True | False |  |
| fold_04_2024 | 0.349 | 0.648 | 0.585 | 1 | 1 | True | True | True |  |
| fold_05_2025 | 0.359 | 0.724 | 0.557 | 1 | 1 | True | True | True |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | 0.053 | 0.362 | 61.23% | 2,948 |
| size_neutral | 0.047 | 0.311 | 55.02% | 2,948 |
| industry_neutral | 0.049 | 0.407 | 65.50% | 2,948 |
| size_industry_neutral | 0.045 | 0.484 | 60.48% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
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
- Peak ICIR: `0.743`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | 0.030 | 0.364 | 2,952 |
| 2.000 | 0.035 | 0.406 | 2,951 |
| 3.000 | 0.039 | 0.437 | 2,950 |
| 5.000 | 0.045 | 0.484 | 2,948 |
| 10.000 | 0.055 | 0.560 | 2,943 |
| 20.000 | 0.068 | 0.668 | 2,933 |
| 40.000 | 0.085 | 0.849 | 2,913 |
| 60.000 | 0.097 | 1.016 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `157.70%`
- Long-short total diagnostic return: `6448696.09%`
- Long-short Sharpe: `4.591`
- Monotonic: `True`
- Monotonic Spearman: `1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.001 | 0.292 | 0.714 | 0.410 | 2,948 |
| 2.000 | 0.003 | 0.697 | 0.720 | 0.969 | 2,948 |
| 3.000 | 0.004 | 0.978 | 0.680 | 1.437 | 2,948 |
| 4.000 | 0.005 | 1.138 | 0.667 | 1.707 | 2,948 |
| 5.000 | 0.005 | 1.263 | 0.666 | 1.896 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.273 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.301 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.315 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.315 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.226 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 10 | 0.002 | 0.027 |
| fold_02_2022 | 10 | 0.010 | 0.130 |
| fold_03_2023 | 10 | 0.020 | 0.258 |
| fold_04_2024 | 8 | 0.031 | 0.437 |
| fold_05_2025 | 2 | 0.040 | 0.556 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `keep`
- Selected folds: `2`
- Validation-pass folds: `5`
- Summary: Repeatedly selected across OOS folds.
