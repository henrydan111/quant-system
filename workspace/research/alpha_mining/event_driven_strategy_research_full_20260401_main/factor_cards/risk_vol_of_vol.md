# Factor Card: risk_vol_of_vol

## Basic Info
- Category: `Volatility`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Std(Std((($close * $adj_factor) / Ref(($close * $adj_factor), 1) - 1), 20), 60)`

## Screening Snapshot
- Grade: `A (Graduated)`
- 5d Rank ICIR: `-0.321`
- 10d Rank ICIR: `-0.388`
- 20d Rank ICIR: `-0.460`
- Monotonic: `True`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.485 | -0.575 | -0.534 | -1 | -1 | True | True | True |  |
| fold_02_2020 | -0.551 | -0.528 | -0.559 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.547 | -0.546 | -0.751 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.550 | -0.644 | -0.683 | -1 | -1 | True | True | True |  |
| fold_05_2023 | -0.592 | -0.717 | -0.794 | -1 | -1 | True | True | True |  |
| fold_06_2024 | -0.590 | -0.736 | -0.185 | -1 | -1 | True | True | True |  |
| fold_07_2025 | -0.596 | -0.397 | -0.432 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.038 | -0.321 | 57.95% | 3,429 |
| size_neutral | -0.041 | -0.417 | 59.76% | 3,429 |
| industry_neutral | -0.034 | -0.400 | 59.06% | 3,429 |
| size_industry_neutral | -0.037 | -0.513 | 61.39% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.028 | -0.346 | 62.96% | 243 |
| 2013.000 | -0.033 | -0.556 | 60.92% | 238 |
| 2014.000 | -0.035 | -0.503 | 58.78% | 245 |
| 2015.000 | -0.018 | -0.341 | 57.38% | 244 |
| 2016.000 | -0.044 | -0.780 | 60.25% | 244 |
| 2017.000 | -0.049 | -0.621 | 65.57% | 244 |
| 2018.000 | -0.034 | -0.532 | 62.55% | 243 |
| 2019.000 | -0.044 | -0.534 | 65.57% | 244 |
| 2020.000 | -0.040 | -0.559 | 67.90% | 243 |
| 2021.000 | -0.045 | -0.751 | 62.96% | 243 |
| 2022.000 | -0.037 | -0.683 | 62.40% | 242 |
| 2023.000 | -0.051 | -0.794 | 60.33% | 242 |
| 2024.000 | -0.019 | -0.185 | 54.13% | 242 |
| 2025.000 | -0.033 | -0.432 | 56.79% | 243 |
| 2026.000 | -0.065 | -0.955 | 68.97% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.033 | -0.436 |
| -0.034 | -0.440 |
| -0.034 | -0.445 |
| -0.035 | -0.450 |
| -0.035 | -0.456 |
| -0.035 | -0.458 |
| -0.035 | -0.458 |
| -0.036 | -0.465 |
| -0.036 | -0.470 |
| -0.037 | -0.478 |
| -0.038 | -0.489 |
| -0.038 | -0.494 |
| -0.037 | -0.489 |
| -0.037 | -0.485 |
| -0.036 | -0.478 |
| -0.035 | -0.469 |
| -0.035 | -0.467 |
| -0.035 | -0.467 |
| -0.035 | -0.472 |
| -0.036 | -0.486 |
| -0.037 | -0.505 |
| -0.038 | -0.531 |
| -0.039 | -0.566 |
| -0.040 | -0.595 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.766`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.023 | -0.332 | 3,433 |
| 2.000 | -0.028 | -0.395 | 3,432 |
| 3.000 | -0.031 | -0.437 | 3,431 |
| 5.000 | -0.037 | -0.513 | 3,429 |
| 10.000 | -0.044 | -0.636 | 3,424 |
| 20.000 | -0.053 | -0.766 | 3,414 |
| 40.000 | -0.063 | -0.982 | 3,394 |
| 60.000 | -0.070 | -1.230 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-45.42%`
- Long-short total diagnostic return: `-99.97%`
- Long-short Sharpe: `-3.170`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 1.131 | 0.662 | 1.709 | 3,429 |
| 2.000 | 0.004 | 1.031 | 0.647 | 1.592 | 3,429 |
| 3.000 | 0.003 | 0.879 | 0.643 | 1.365 | 3,429 |
| 4.000 | 0.003 | 0.774 | 0.660 | 1.172 | 3,429 |
| 5.000 | 0.002 | 0.544 | 0.729 | 0.746 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.345 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.371 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.343 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.378 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.384 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.403 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.382 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 8 | -0.005 | -0.136 |
| fold_02_2020 | 10 | -0.011 | -0.274 |
| fold_03_2021 | 10 | -0.012 | -0.304 |
| fold_04_2022 | 6 | -0.008 | -0.203 |
| fold_05_2023 | 6 | -0.009 | -0.316 |
| fold_06_2024 | 5 | -0.012 | -0.325 |
| fold_07_2025 | 10 | -0.008 | -0.165 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `keep`
- Selected folds: `4`
- Validation-pass folds: `7`
- Summary: Repeatedly selected across OOS folds.
