# Factor Card: north_hold_change_5d

## Basic Info
- Category: `Northbound`
- Signal direction in strategy: `high_is_good`
- Raw expression: `Ref($ratio, 1) - Ref($ratio, 6)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `0.309`
- 10d Rank ICIR: `0.307`
- 20d Rank ICIR: `0.302`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | 0.270 | 0.114 | 0.114 | 1 | 1 | True | False | False |  |
| fold_02_2022 | 0.282 | 0.026 | -0.053 | 1 | 1 | True | False | False |  |
| fold_03_2023 | 0.196 | 0.031 | 0.270 | 1 | 1 | True | False | False |  |
| fold_04_2024 | 0.179 | 0.103 | 0.224 | 1 | 1 | True | False | False |  |
| fold_05_2025 | 0.134 | 0.254 |  | 1 | 1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | 0.013 | 0.309 | 61.71% | 1,844 |
| size_neutral | 0.012 | 0.206 | 63.29% | 1,844 |
| industry_neutral | 0.005 | 0.152 | 60.20% | 1,844 |
| size_industry_neutral | 0.005 | 0.162 | 60.90% | 1,844 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2017.000 | 0.006 | 0.161 | 66.24% | 234 |
| 2018.000 | 0.013 | 0.382 | 71.19% | 243 |
| 2019.000 | 0.009 | 0.315 | 67.62% | 244 |
| 2020.000 | -0.002 | -0.074 | 65.02% | 243 |
| 2021.000 | 0.004 | 0.114 | 53.09% | 243 |
| 2022.000 | -0.002 | -0.053 | 56.61% | 242 |
| 2023.000 | 0.009 | 0.270 | 68.18% | 242 |
| 2024.000 | 0.006 | 0.224 | 57.52% | 153 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| 0.007 | 0.255 |
| 0.007 | 0.258 |
| 0.007 | 0.254 |
| 0.007 | 0.247 |
| 0.007 | 0.242 |
| 0.007 | 0.236 |
| 0.007 | 0.234 |
| 0.007 | 0.225 |
| 0.007 | 0.224 |
| 0.006 | 0.217 |
| 0.006 | 0.215 |
| 0.006 | 0.224 |
| 0.007 | 0.230 |
| 0.007 | 0.231 |
| 0.007 | 0.242 |
| 0.007 | 0.246 |
| 0.007 | 0.245 |
| 0.007 | 0.243 |
| 0.007 | 0.241 |
| 0.006 | 0.235 |
| 0.006 | 0.236 |
| 0.007 | 0.241 |
| 0.007 | 0.243 |
| 0.007 | 0.250 |

## IC Decay
- Best horizon by |ICIR|: `40`
- Peak ICIR: `0.364`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | 0.005 | 0.164 | 1,844 |
| 2.000 | 0.006 | 0.173 | 1,844 |
| 3.000 | 0.006 | 0.177 | 1,844 |
| 5.000 | 0.005 | 0.162 | 1,844 |
| 10.000 | 0.004 | 0.125 | 1,844 |
| 20.000 | 0.004 | 0.105 | 1,844 |
| 40.000 | 0.004 | 0.120 | 1,844 |
| 60.000 | 0.004 | 0.120 | 1,844 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `17.88%`
- Long-short total diagnostic return: `233.34%`
- Long-short Sharpe: `2.329`
- Monotonic: `False`
- Monotonic Spearman: `0.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | -0.000 | -0.021 | 0.503 | -0.043 | 1,844 |
| 2.000 | 0.001 | 0.180 | 0.554 | 0.325 | 1,844 |
| 3.000 | 0.000 | 0.064 | 0.572 | 0.112 | 1,844 |
| 4.000 | -0.000 | -0.038 | 0.557 | -0.069 | 1,844 |
| 5.000 | 0.001 | 0.146 | 0.507 | 0.287 | 1,844 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_05_2025 | selected_cluster_peer | 0.021 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_05_2025 | 10 | 0.004 | 0.113 |

## Risks
- Quantile monotonicity is weak in the 5d strategy-horizon diagnostic.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `1`
- Summary: Shows some predictive value, but not stable enough for the core book.
