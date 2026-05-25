# Factor Card: liq_amihud_20d

## Basic Info
- Category: `Liquidity`
- Signal direction in strategy: `high_is_good`
- Raw expression: `Mean(Abs((($close * $adj_factor) / Ref(($close * $adj_factor), 1) - 1)) / $amount, 20)`

## Screening Snapshot
- Grade: `A (Graduated)`
- 5d Rank ICIR: `0.325`
- 10d Rank ICIR: `0.408`
- 20d Rank ICIR: `0.494`
- Monotonic: `True`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | 0.380 | 0.560 | 0.413 | 1 | 1 | True | True | True |  |
| fold_02_2020 | 0.399 | 0.492 | 0.425 | 1 | 1 | True | True | False |  |
| fold_03_2021 | 0.397 | 0.420 | 0.205 | 1 | 1 | True | True | False |  |
| fold_04_2022 | 0.391 | 0.320 | 0.045 | 1 | 1 | True | True | False |  |
| fold_05_2023 | 0.535 | 0.111 | -0.232 | 1 | 1 | True | False | False |  |
| fold_06_2024 | 0.424 | -0.105 | 0.104 | 1 | -1 | False | False | False |  |
| fold_07_2025 | 0.314 | -0.060 | 0.255 | 1 | -1 | False | False | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | 0.045 | 0.325 | 60.54% | 3,429 |
| size_neutral | 0.027 | 0.242 | 56.52% | 3,429 |
| industry_neutral | 0.035 | 0.365 | 60.89% | 3,429 |
| size_industry_neutral | 0.023 | 0.258 | 58.33% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | 0.038 | 0.403 | 67.08% | 243 |
| 2013.000 | 0.041 | 0.631 | 69.75% | 238 |
| 2014.000 | 0.031 | 0.455 | 71.84% | 245 |
| 2015.000 | -0.006 | -0.060 | 75.00% | 244 |
| 2016.000 | 0.053 | 0.800 | 75.82% | 244 |
| 2017.000 | 0.033 | 0.536 | 65.16% | 244 |
| 2018.000 | 0.042 | 0.586 | 56.79% | 243 |
| 2019.000 | 0.034 | 0.413 | 52.05% | 244 |
| 2020.000 | 0.036 | 0.425 | 49.79% | 243 |
| 2021.000 | 0.015 | 0.205 | 52.26% | 243 |
| 2022.000 | 0.004 | 0.045 | 65.29% | 242 |
| 2023.000 | -0.028 | -0.232 | 45.87% | 242 |
| 2024.000 | 0.013 | 0.104 | 47.11% | 242 |
| 2025.000 | 0.018 | 0.255 | 58.02% | 243 |
| 2026.000 | -0.004 | -0.075 | 86.21% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| 0.020 | 0.277 |
| 0.019 | 0.270 |
| 0.018 | 0.264 |
| 0.018 | 0.258 |
| 0.017 | 0.251 |
| 0.018 | 0.253 |
| 0.018 | 0.256 |
| 0.018 | 0.260 |
| 0.018 | 0.266 |
| 0.019 | 0.274 |
| 0.019 | 0.283 |
| 0.020 | 0.292 |
| 0.020 | 0.293 |
| 0.020 | 0.293 |
| 0.020 | 0.287 |
| 0.019 | 0.281 |
| 0.019 | 0.273 |
| 0.019 | 0.271 |
| 0.019 | 0.271 |
| 0.019 | 0.274 |
| 0.019 | 0.277 |
| 0.019 | 0.284 |
| 0.019 | 0.287 |
| 0.019 | 0.282 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.648`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | 0.013 | 0.141 | 3,433 |
| 2.000 | 0.016 | 0.181 | 3,432 |
| 3.000 | 0.019 | 0.210 | 3,431 |
| 5.000 | 0.023 | 0.258 | 3,429 |
| 10.000 | 0.031 | 0.341 | 3,424 |
| 20.000 | 0.039 | 0.421 | 3,414 |
| 40.000 | 0.053 | 0.559 | 3,394 |
| 60.000 | 0.062 | 0.652 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `82.19%`
- Long-short total diagnostic return: `350543.97%`
- Long-short Sharpe: `2.777`
- Monotonic: `True`
- Monotonic Spearman: `1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.002 | 0.547 | 0.738 | 0.741 | 3,429 |
| 2.000 | 0.003 | 0.840 | 0.697 | 1.205 | 3,429 |
| 3.000 | 0.004 | 0.886 | 0.667 | 1.329 | 3,429 |
| 4.000 | 0.004 | 0.920 | 0.631 | 1.457 | 3,429 |
| 5.000 | 0.005 | 1.173 | 0.611 | 1.922 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.328 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.378 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.383 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.352 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 9 | 0.013 | 0.208 |
| fold_02_2020 | 10 | 0.018 | 0.335 |
| fold_03_2021 | 10 | 0.011 | 0.200 |
| fold_04_2022 | 10 | -0.000 | -0.006 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `1`
- Validation-pass folds: `4`
- Summary: Shows some predictive value, but not stable enough for the core book.
