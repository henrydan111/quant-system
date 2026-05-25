# Factor Card: comp_size_quality

## Basic Info
- Category: `Other`
- Signal direction in strategy: `high_is_good`
- Raw expression: `COMPOSITE(size_ln_mcap, qual_roe)`

## Screening Snapshot
- Grade: `A (Graduated)`
- 5d Rank ICIR: `0.341`
- 10d Rank ICIR: `0.410`
- 20d Rank ICIR: `0.492`
- Monotonic: `True`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | 0.320 | 0.345 | 0.376 | 1 | 1 | True | True | False |  |
| fold_02_2020 | 0.349 | 0.328 | 0.484 | 1 | 1 | True | True | False |  |
| fold_03_2021 | 0.307 | 0.422 | 0.088 | 1 | 1 | True | True | False |  |
| fold_04_2022 | 0.356 | 0.292 | 0.037 | 1 | 1 | True | True | False |  |
| fold_05_2023 | 0.385 | 0.065 | 0.289 | 1 | 1 | True | False | False |  |
| fold_06_2024 | 0.331 | 0.179 | 0.211 | 1 | 1 | True | True | False |  |
| fold_07_2025 | 0.266 | 0.235 | 0.269 | 1 | 1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | 0.035 | 0.341 | 63.31% | 3,429 |
| size_neutral | 0.025 | 0.267 | 56.55% | 3,429 |
| industry_neutral | 0.032 | 0.379 | 66.29% | 3,429 |
| size_industry_neutral | 0.022 | 0.290 | 58.65% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | 0.026 | 0.295 | 58.02% | 243 |
| 2013.000 | 0.033 | 0.489 | 62.61% | 238 |
| 2014.000 | 0.003 | 0.073 | 53.06% | 245 |
| 2015.000 | 0.028 | 0.321 | 63.93% | 244 |
| 2016.000 | 0.025 | 0.434 | 65.16% | 244 |
| 2017.000 | 0.035 | 0.414 | 59.84% | 244 |
| 2018.000 | 0.026 | 0.283 | 62.14% | 243 |
| 2019.000 | 0.032 | 0.376 | 64.34% | 244 |
| 2020.000 | 0.033 | 0.484 | 67.08% | 243 |
| 2021.000 | 0.005 | 0.088 | 48.97% | 243 |
| 2022.000 | 0.002 | 0.037 | 54.96% | 242 |
| 2023.000 | 0.020 | 0.289 | 61.98% | 242 |
| 2024.000 | 0.023 | 0.211 | 54.55% | 242 |
| 2025.000 | 0.020 | 0.269 | 59.26% | 243 |
| 2026.000 | 0.032 | 0.350 | 51.72% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| 0.024 | 0.298 |
| 0.024 | 0.298 |
| 0.023 | 0.297 |
| 0.023 | 0.295 |
| 0.022 | 0.287 |
| 0.022 | 0.283 |
| 0.022 | 0.281 |
| 0.022 | 0.278 |
| 0.022 | 0.276 |
| 0.022 | 0.281 |
| 0.022 | 0.285 |
| 0.022 | 0.283 |
| 0.021 | 0.275 |
| 0.021 | 0.269 |
| 0.019 | 0.258 |
| 0.018 | 0.241 |
| 0.017 | 0.229 |
| 0.017 | 0.233 |
| 0.018 | 0.241 |
| 0.019 | 0.255 |
| 0.020 | 0.277 |
| 0.021 | 0.295 |
| 0.021 | 0.306 |
| 0.022 | 0.317 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.521`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | 0.014 | 0.214 | 3,433 |
| 2.000 | 0.017 | 0.243 | 3,432 |
| 3.000 | 0.019 | 0.264 | 3,431 |
| 5.000 | 0.022 | 0.290 | 3,429 |
| 10.000 | 0.027 | 0.331 | 3,424 |
| 20.000 | 0.033 | 0.387 | 3,414 |
| 40.000 | 0.039 | 0.462 | 3,394 |
| 60.000 | 0.041 | 0.496 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `83.04%`
- Long-short total diagnostic return: `373591.28%`
- Long-short Sharpe: `3.478`
- Monotonic: `True`
- Monotonic Spearman: `1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.002 | 0.513 | 0.699 | 0.733 | 3,429 |
| 2.000 | 0.003 | 0.860 | 0.689 | 1.249 | 3,429 |
| 3.000 | 0.004 | 0.931 | 0.664 | 1.402 | 3,429 |
| 4.000 | 0.004 | 0.933 | 0.639 | 1.460 | 3,429 |
| 5.000 | 0.004 | 1.134 | 0.652 | 1.739 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.598 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.635 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.663 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.075 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.638 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.059 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.013 | 0.160 |
| fold_02_2020 | 10 | 0.015 | 0.221 |
| fold_03_2021 | 10 | 0.009 | 0.168 |
| fold_04_2022 | 10 | 0.014 | 0.222 |
| fold_06_2024 | 10 | 0.006 | 0.091 |
| fold_07_2025 | 10 | 0.019 | 0.226 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `6`
- Summary: Shows some predictive value, but not stable enough for the core book.
