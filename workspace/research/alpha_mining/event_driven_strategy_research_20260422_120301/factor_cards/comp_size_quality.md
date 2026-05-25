# Factor Card: comp_size_quality

## Basic Info
- Category: `Other`
- Signal direction in strategy: `high_is_good`
- Raw expression: `COMPOSITE(size_ln_mcap, qual_roe)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `0.328`
- 10d Rank ICIR: `0.391`
- 20d Rank ICIR: `0.458`
- Monotonic: `True`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | 0.307 | 0.422 | 0.088 | 1 | 1 | True | True | False |  |
| fold_02_2022 | 0.356 | 0.292 | 0.037 | 1 | 1 | True | True | False |  |
| fold_03_2023 | 0.385 | 0.065 | 0.289 | 1 | 1 | True | False | False |  |
| fold_04_2024 | 0.331 | 0.179 | 0.211 | 1 | 1 | True | True | False |  |
| fold_05_2025 | 0.266 | 0.235 | 0.269 | 1 | 1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | 0.034 | 0.328 | 62.58% | 2,948 |
| size_neutral | 0.024 | 0.251 | 55.87% | 2,948 |
| industry_neutral | 0.031 | 0.365 | 65.74% | 2,948 |
| size_industry_neutral | 0.021 | 0.276 | 58.38% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
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
- Peak ICIR: `0.472`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | 0.014 | 0.203 | 2,952 |
| 2.000 | 0.016 | 0.233 | 2,951 |
| 3.000 | 0.018 | 0.252 | 2,950 |
| 5.000 | 0.021 | 0.276 | 2,948 |
| 10.000 | 0.025 | 0.308 | 2,943 |
| 20.000 | 0.030 | 0.353 | 2,933 |
| 40.000 | 0.035 | 0.419 | 2,913 |
| 60.000 | 0.036 | 0.446 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `79.21%`
- Long-short total diagnostic return: `91946.15%`
- Long-short Sharpe: `3.282`
- Monotonic: `True`
- Monotonic Spearman: `0.900`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.002 | 0.530 | 0.722 | 0.735 | 2,948 |
| 2.000 | 0.003 | 0.863 | 0.711 | 1.214 | 2,948 |
| 3.000 | 0.004 | 0.930 | 0.683 | 1.361 | 2,948 |
| 4.000 | 0.004 | 0.911 | 0.655 | 1.390 | 2,948 |
| 5.000 | 0.004 | 1.131 | 0.670 | 1.689 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.662 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.075 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.638 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.059 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 10 | 0.013 | 0.254 |
| fold_02_2022 | 10 | 0.016 | 0.250 |
| fold_04_2024 | 10 | 0.008 | 0.119 |
| fold_05_2025 | 10 | 0.018 | 0.218 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `4`
- Summary: Shows some predictive value, but not stable enough for the core book.
