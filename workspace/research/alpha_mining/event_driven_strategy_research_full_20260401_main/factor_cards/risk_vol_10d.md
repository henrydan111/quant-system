# Factor Card: risk_vol_10d

## Basic Info
- Category: `Volatility`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Std((($close * $adj_factor) / Ref(($close * $adj_factor), 1) - 1), 10)`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `-0.402`
- 10d Rank ICIR: `-0.468`
- 20d Rank ICIR: `-0.507`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.484 | -0.536 | -0.807 | -1 | -1 | True | True | False |  |
| fold_02_2020 | -0.535 | -0.623 | -0.631 | -1 | -1 | True | True | False |  |
| fold_03_2021 | -0.552 | -0.715 | -0.832 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.576 | -0.715 | -0.803 | -1 | -1 | True | True | False |  |
| fold_05_2023 | -0.638 | -0.817 | -0.845 | -1 | -1 | True | True | False |  |
| fold_06_2024 | -0.648 | -0.824 | -0.523 | -1 | -1 | True | True | False |  |
| fold_07_2025 | -0.688 | -0.632 | -0.875 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.064 | -0.402 | 58.53% | 3,429 |
| size_neutral | -0.067 | -0.459 | 59.49% | 3,429 |
| industry_neutral | -0.058 | -0.537 | 62.55% | 3,429 |
| size_industry_neutral | -0.060 | -0.605 | 63.20% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.034 | -0.335 | 62.55% | 243 |
| 2013.000 | -0.043 | -0.399 | 51.68% | 238 |
| 2014.000 | -0.062 | -0.647 | 62.04% | 245 |
| 2015.000 | -0.043 | -0.367 | 58.20% | 244 |
| 2016.000 | -0.076 | -0.717 | 66.80% | 244 |
| 2017.000 | -0.061 | -0.594 | 68.44% | 244 |
| 2018.000 | -0.053 | -0.482 | 64.61% | 243 |
| 2019.000 | -0.072 | -0.807 | 71.72% | 244 |
| 2020.000 | -0.060 | -0.631 | 61.32% | 243 |
| 2021.000 | -0.063 | -0.832 | 62.14% | 243 |
| 2022.000 | -0.065 | -0.803 | 62.40% | 242 |
| 2023.000 | -0.065 | -0.845 | 63.22% | 242 |
| 2024.000 | -0.064 | -0.523 | 68.18% | 242 |
| 2025.000 | -0.080 | -0.875 | 62.55% | 243 |
| 2026.000 | -0.067 | -0.904 | 51.72% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.081 | -0.876 |
| -0.080 | -0.877 |
| -0.081 | -0.879 |
| -0.081 | -0.884 |
| -0.081 | -0.885 |
| -0.082 | -0.891 |
| -0.082 | -0.892 |
| -0.082 | -0.897 |
| -0.082 | -0.900 |
| -0.083 | -0.903 |
| -0.083 | -0.907 |
| -0.083 | -0.914 |
| -0.083 | -0.910 |
| -0.082 | -0.905 |
| -0.082 | -0.899 |
| -0.081 | -0.888 |
| -0.080 | -0.889 |
| -0.080 | -0.890 |
| -0.080 | -0.888 |
| -0.080 | -0.894 |
| -0.081 | -0.902 |
| -0.081 | -0.921 |
| -0.082 | -0.934 |
| -0.082 | -0.947 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.826`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.040 | -0.382 | 3,433 |
| 2.000 | -0.047 | -0.464 | 3,432 |
| 3.000 | -0.053 | -0.521 | 3,431 |
| 5.000 | -0.060 | -0.605 | 3,429 |
| 10.000 | -0.070 | -0.710 | 3,424 |
| 20.000 | -0.078 | -0.781 | 3,414 |
| 40.000 | -0.087 | -0.943 | 3,394 |
| 60.000 | -0.095 | -1.126 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-58.46%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-3.301`
- Monotonic: `False`
- Monotonic Spearman: `-0.700`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 1.045 | 0.623 | 1.678 | 3,429 |
| 2.000 | 0.004 | 1.121 | 0.647 | 1.732 | 3,429 |
| 3.000 | 0.004 | 1.084 | 0.658 | 1.647 | 3,429 |
| 4.000 | 0.004 | 0.903 | 0.684 | 1.319 | 3,429 |
| 5.000 | 0.001 | 0.201 | 0.741 | 0.271 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.687 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.674 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.773 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.784 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.722 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.720 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.701 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 10 | 0.011 | 0.207 |
| fold_02_2020 | 8 | -0.002 | -0.040 |
| fold_03_2021 | 5 | 0.006 | 0.128 |
| fold_04_2022 | 4 | 0.004 | 0.090 |
| fold_05_2023 | 3 | -0.009 | -0.178 |
| fold_06_2024 | 3 | -0.010 | -0.200 |
| fold_07_2025 | 4 | -0.006 | -0.088 |

## Risks
- Quantile monotonicity is weak in the 5d strategy-horizon diagnostic.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `7`
- Summary: Shows some predictive value, but not stable enough for the core book.
