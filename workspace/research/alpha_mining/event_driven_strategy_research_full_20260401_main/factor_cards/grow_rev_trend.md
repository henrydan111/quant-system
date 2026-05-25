# Factor Card: grow_rev_trend

## Basic Info
- Category: `Growth`
- Signal direction in strategy: `high_is_good`
- Raw expression: `Slope($or_yoy, 4)`

## Screening Snapshot
- Grade: `A (Graduated)`
- 5d Rank ICIR: `0.302`
- 10d Rank ICIR: `0.255`
- 20d Rank ICIR: `0.271`
- Monotonic: `True`
- Warning flags: `reduced_quantiles`
- Primary coverage: `52.84%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | 0.159 | 0.310 | 0.304 | 1 | 1 | True | True | False |  |
| fold_02_2020 | 0.214 | 0.311 | -0.128 | 1 | 1 | True | True | False |  |
| fold_03_2021 | 0.276 | 0.056 | -0.195 | 1 | 1 | True | False | False |  |
| fold_04_2022 | 0.277 | -0.162 | -0.639 | 1 | -1 | False | False | False |  |
| fold_05_2023 | 0.180 | -0.413 | -0.032 | 1 | -1 | False | False | False |  |
| fold_06_2024 | 0.083 | -0.327 | -0.153 | 1 | -1 | False | False | False |  |
| fold_07_2025 | -0.118 | -0.080 | 0.084 | -1 | -1 | True | False | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | 0.009 | 0.401 | 65.96% | 984 |
| size_neutral | 0.004 | 0.034 | 65.55% | 984 |
| industry_neutral | 0.001 | 0.015 | 65.35% | 984 |
| size_industry_neutral | 0.002 | 0.029 | 65.85% | 984 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | 0.001 | 0.022 | 63.86% | 83 |
| 2013.000 | -0.003 | -0.082 | 65.38% | 78 |
| 2014.000 | 0.014 | 0.290 | 69.77% | 86 |
| 2015.000 | 0.015 | 0.277 | 62.50% | 80 |
| 2016.000 | 0.011 | 0.216 | 66.23% | 77 |
| 2017.000 | 0.013 | 0.304 | 64.47% | 76 |
| 2018.000 | 0.012 | 0.317 | 77.61% | 67 |
| 2019.000 | 0.013 | 0.304 | 71.01% | 69 |
| 2020.000 | -0.007 | -0.128 | 56.52% | 69 |
| 2021.000 | -0.011 | -0.195 | 58.21% | 67 |
| 2022.000 | -0.043 | -0.639 | 65.08% | 63 |
| 2023.000 | -0.002 | -0.032 | 58.62% | 58 |
| 2024.000 | -0.008 | -0.153 | 60.71% | 56 |
| 2025.000 | 0.005 | 0.084 | 83.64% | 55 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.016 | -0.248 |
| -0.015 | -0.244 |
| -0.015 | -0.242 |
| -0.015 | -0.230 |
| -0.015 | -0.226 |
| -0.015 | -0.229 |
| -0.015 | -0.230 |
| -0.015 | -0.230 |
| -0.015 | -0.230 |
| -0.015 | -0.232 |
| -0.015 | -0.232 |
| -0.015 | -0.232 |
| -0.014 | -0.220 |
| -0.014 | -0.222 |
| -0.014 | -0.219 |
| -0.014 | -0.210 |
| -0.013 | -0.203 |
| -0.013 | -0.197 |
| -0.012 | -0.196 |
| -0.012 | -0.195 |
| -0.013 | -0.199 |
| -0.013 | -0.199 |
| -0.013 | -0.198 |
| -0.012 | -0.192 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.474`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | 0.002 | 0.032 | 984 |
| 2.000 | 0.002 | 0.045 | 984 |
| 3.000 | 0.002 | 0.042 | 984 |
| 5.000 | 0.002 | 0.029 | 984 |
| 10.000 | -0.000 | -0.004 | 984 |
| 20.000 | 0.001 | 0.019 | 984 |
| 40.000 | -0.003 | -0.058 | 984 |
| 60.000 | -0.001 | -0.015 | 984 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `3.76%`
- Long-short total diagnostic return: `15.48%`
- Long-short Sharpe: `0.356`
- Monotonic: `False`
- Monotonic Spearman: `0.100`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.138 | 0.640 | 1.778 | 984 |
| 2.000 | 0.004 | 1.052 | 0.657 | 1.600 | 984 |
| 3.000 | 0.004 | 0.952 | 0.669 | 1.422 | 984 |
| 4.000 | 0.004 | 0.991 | 0.672 | 1.475 | 984 |
| 5.000 | 0.005 | 1.183 | 0.645 | 1.835 | 984 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.015 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.022 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.017 | 0.426 |
| fold_02_2020 | 10 | 0.017 | 0.399 |

## Risks
- Screening warning flags: reduced_quantiles
- Quantile monotonicity is weak in the 5d strategy-horizon diagnostic.
- Signal direction flips too often between train and validation windows.
- Primary coverage is below 70%, which raises implementation risk.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `2`
- Summary: Shows some predictive value, but not stable enough for the core book.
