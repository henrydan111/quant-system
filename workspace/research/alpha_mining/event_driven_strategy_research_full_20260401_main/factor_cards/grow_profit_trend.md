# Factor Card: grow_profit_trend

## Basic Info
- Category: `Growth`
- Signal direction in strategy: `high_is_good`
- Raw expression: `Slope($netprofit_yoy, 4)`

## Screening Snapshot
- Grade: `A (Graduated)`
- 5d Rank ICIR: `0.344`
- 10d Rank ICIR: `0.301`
- 20d Rank ICIR: `0.334`
- Monotonic: `True`
- Warning flags: `reduced_quantiles`
- Primary coverage: `52.99%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | 0.167 | 0.271 | -0.135 | 1 | 1 | True | True | False |  |
| fold_02_2020 | 0.177 | 0.038 | -0.161 | 1 | 1 | True | False | False |  |
| fold_03_2021 | 0.225 | -0.149 | -0.084 | 1 | -1 | False | False | False |  |
| fold_04_2022 | 0.126 | -0.115 | -0.219 | 1 | -1 | False | False | False |  |
| fold_05_2023 | 0.086 | -0.148 | -0.150 | 1 | -1 | False | False | False |  |
| fold_06_2024 | 0.030 | -0.189 | 0.214 | 1 | -1 | False | False | False |  |
| fold_07_2025 | -0.082 | 0.038 | -0.230 | -1 | 1 | False | False | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | 0.011 | 0.468 | 65.60% | 971 |
| size_neutral | 0.002 | 0.012 | 65.71% | 971 |
| industry_neutral | 0.001 | 0.030 | 64.26% | 971 |
| size_industry_neutral | 0.002 | 0.044 | 64.06% | 971 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | 0.010 | 0.317 | 55.42% | 83 |
| 2013.000 | -0.003 | -0.106 | 58.97% | 78 |
| 2014.000 | 0.017 | 0.370 | 69.88% | 83 |
| 2015.000 | 0.003 | 0.067 | 64.10% | 78 |
| 2016.000 | 0.007 | 0.141 | 56.41% | 78 |
| 2017.000 | 0.015 | 0.339 | 73.97% | 73 |
| 2018.000 | 0.009 | 0.200 | 74.29% | 70 |
| 2019.000 | -0.006 | -0.135 | 63.77% | 69 |
| 2020.000 | -0.008 | -0.161 | 65.08% | 63 |
| 2021.000 | -0.005 | -0.084 | 54.55% | 66 |
| 2022.000 | -0.013 | -0.219 | 69.35% | 62 |
| 2023.000 | -0.007 | -0.150 | 63.79% | 58 |
| 2024.000 | 0.011 | 0.214 | 62.50% | 56 |
| 2025.000 | -0.012 | -0.230 | 66.67% | 54 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.004 | -0.070 |
| -0.003 | -0.063 |
| -0.003 | -0.060 |
| -0.004 | -0.065 |
| -0.004 | -0.071 |
| -0.004 | -0.073 |
| -0.004 | -0.073 |
| -0.004 | -0.072 |
| -0.004 | -0.068 |
| -0.004 | -0.067 |
| -0.004 | -0.077 |
| -0.004 | -0.081 |
| -0.004 | -0.080 |
| -0.006 | -0.097 |
| -0.006 | -0.101 |
| -0.006 | -0.097 |
| -0.005 | -0.090 |
| -0.005 | -0.084 |
| -0.004 | -0.075 |
| -0.004 | -0.067 |
| -0.004 | -0.064 |
| -0.004 | -0.068 |
| -0.004 | -0.078 |
| -0.004 | -0.081 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.526`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | 0.003 | 0.064 | 971 |
| 2.000 | 0.005 | 0.100 | 971 |
| 3.000 | 0.004 | 0.077 | 971 |
| 5.000 | 0.002 | 0.044 | 971 |
| 10.000 | 0.002 | 0.033 | 971 |
| 20.000 | 0.003 | 0.057 | 971 |
| 40.000 | 0.000 | 0.009 | 971 |
| 60.000 | 0.005 | 0.084 | 971 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `7.50%`
- Long-short total diagnostic return: `32.12%`
- Long-short Sharpe: `0.688`
- Monotonic: `False`
- Monotonic Spearman: `0.100`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 1.052 | 0.651 | 1.616 | 971 |
| 2.000 | 0.004 | 1.100 | 0.659 | 1.669 | 971 |
| 3.000 | 0.004 | 1.041 | 0.669 | 1.556 | 971 |
| 4.000 | 0.004 | 0.990 | 0.674 | 1.469 | 971 |
| 5.000 | 0.004 | 1.131 | 0.645 | 1.753 | 971 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.018 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.016 | 0.400 |

## Risks
- Screening warning flags: reduced_quantiles
- Quantile monotonicity is weak in the 5d strategy-horizon diagnostic.
- Signal direction flips too often between train and validation windows.
- Primary coverage is below 70%, which raises implementation risk.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `1`
- Summary: Shows some predictive value, but not stable enough for the core book.
