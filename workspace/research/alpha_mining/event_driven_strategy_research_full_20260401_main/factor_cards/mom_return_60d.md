# Factor Card: mom_return_60d

## Basic Info
- Category: `Momentum`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Ref(($close * $adj_factor), 1) / Ref(($close * $adj_factor), 61) - 1`

## Screening Snapshot
- Grade: `A (Graduated)`
- 5d Rank ICIR: `-0.336`
- 10d Rank ICIR: `-0.399`
- 20d Rank ICIR: `-0.438`
- Monotonic: `True`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.601 | -0.275 | -0.458 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.552 | -0.380 | -0.315 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.558 | -0.386 | -0.489 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.506 | -0.400 | -0.417 | -1 | -1 | True | True | False |  |
| fold_05_2023 | -0.384 | -0.454 | -0.197 | -1 | -1 | True | True | False |  |
| fold_06_2024 | -0.355 | -0.307 | -0.312 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.395 | -0.258 | -0.703 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.052 | -0.336 | 59.26% | 3,429 |
| size_neutral | -0.050 | -0.356 | 59.76% | 3,429 |
| industry_neutral | -0.047 | -0.402 | 61.94% | 3,429 |
| size_industry_neutral | -0.045 | -0.441 | 62.12% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.055 | -0.459 | 69.55% | 243 |
| 2013.000 | -0.037 | -0.313 | 52.10% | 238 |
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
- Peak ICIR: `0.480`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.029 | -0.293 | 3,433 |
| 2.000 | -0.034 | -0.331 | 3,432 |
| 3.000 | -0.039 | -0.376 | 3,431 |
| 5.000 | -0.045 | -0.441 | 3,429 |
| 10.000 | -0.052 | -0.512 | 3,424 |
| 20.000 | -0.056 | -0.552 | 3,414 |
| 40.000 | -0.051 | -0.552 | 3,394 |
| 60.000 | -0.046 | -0.549 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-69.01%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-4.103`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.251 | 0.724 | 1.728 | 3,429 |
| 2.000 | 0.004 | 1.119 | 0.665 | 1.684 | 3,429 |
| 3.000 | 0.004 | 1.028 | 0.639 | 1.607 | 3,429 |
| 4.000 | 0.003 | 0.825 | 0.639 | 1.291 | 3,429 |
| 5.000 | 0.000 | 0.105 | 0.684 | 0.153 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.422 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.422 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.472 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.886 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.841 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.446 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.451 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.018 | 0.251 |
| fold_02_2020 | 10 | 0.009 | 0.127 |
| fold_03_2021 | 10 | 0.008 | 0.113 |
| fold_04_2022 | 10 | 0.004 | 0.076 |
| fold_05_2023 | 10 | 0.004 | 0.105 |
| fold_06_2024 | 10 | 0.017 | 0.233 |
| fold_07_2025 | 10 | 0.014 | 0.159 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
