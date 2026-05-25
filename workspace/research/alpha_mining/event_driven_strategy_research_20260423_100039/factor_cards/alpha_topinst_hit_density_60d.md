# Factor Card: alpha_topinst_hit_density_60d

## Basic Info
- Category: `Other`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Sum(If(Ref($top_inst__net_buy, 1) == Ref($top_inst__net_buy, 1), 1, 0), 60)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.541`
- 10d Rank ICIR: `-0.655`
- 20d Rank ICIR: `-0.796`
- Monotonic: `True`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.701 | -0.865 | -0.751 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.703 | -0.804 | -0.541 | -1 | -1 | True | True | True |  |
| fold_03_2023 | -0.764 | -0.639 | -0.568 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.722 | -0.544 | -0.406 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.718 | -0.475 | -0.743 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.053 | -0.541 | 63.16% | 2,948 |
| size_neutral | -0.052 | -0.520 | 64.28% | 2,948 |
| industry_neutral | -0.036 | -0.632 | 65.26% | 2,948 |
| size_industry_neutral | -0.037 | -0.663 | 65.84% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.041 | -0.855 | 63.67% | 245 |
| 2015.000 | -0.039 | -0.590 | 56.97% | 244 |
| 2016.000 | -0.051 | -0.927 | 63.93% | 244 |
| 2017.000 | -0.027 | -0.565 | 63.52% | 244 |
| 2018.000 | -0.041 | -0.657 | 66.26% | 243 |
| 2019.000 | -0.043 | -0.857 | 69.67% | 244 |
| 2020.000 | -0.043 | -0.873 | 74.49% | 243 |
| 2021.000 | -0.029 | -0.751 | 62.55% | 243 |
| 2022.000 | -0.023 | -0.541 | 68.18% | 242 |
| 2023.000 | -0.036 | -0.568 | 70.25% | 242 |
| 2024.000 | -0.032 | -0.406 | 68.60% | 242 |
| 2025.000 | -0.041 | -0.743 | 62.55% | 243 |
| 2026.000 | -0.047 | -0.904 | 62.07% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.040 | -0.738 |
| -0.041 | -0.744 |
| -0.041 | -0.756 |
| -0.042 | -0.767 |
| -0.042 | -0.776 |
| -0.042 | -0.780 |
| -0.042 | -0.778 |
| -0.043 | -0.783 |
| -0.043 | -0.784 |
| -0.043 | -0.787 |
| -0.043 | -0.784 |
| -0.042 | -0.781 |
| -0.042 | -0.771 |
| -0.041 | -0.762 |
| -0.040 | -0.752 |
| -0.040 | -0.747 |
| -0.039 | -0.749 |
| -0.039 | -0.750 |
| -0.039 | -0.750 |
| -0.039 | -0.750 |
| -0.040 | -0.755 |
| -0.040 | -0.760 |
| -0.040 | -0.768 |
| -0.040 | -0.778 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `1.102`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.023 | -0.426 | 2,952 |
| 2.000 | -0.028 | -0.499 | 2,951 |
| 3.000 | -0.032 | -0.558 | 2,950 |
| 5.000 | -0.037 | -0.663 | 2,948 |
| 10.000 | -0.045 | -0.798 | 2,943 |
| 20.000 | -0.054 | -0.952 | 2,933 |
| 40.000 | -0.063 | -1.088 | 2,913 |
| 60.000 | -0.070 | -1.189 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-63.22%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-6.155`
- Monotonic: `True`
- Monotonic Spearman: `-0.900`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.150 | 0.720 | 1.597 | 2,948 |
| 2.000 | 0.005 | 1.153 | 0.686 | 1.682 | 2,948 |
| 3.000 | 0.004 | 1.013 | 0.656 | 1.543 | 2,948 |
| 4.000 | 0.003 | 0.877 | 0.649 | 1.353 | 2,948 |
| 5.000 | 0.001 | 0.165 | 0.751 | 0.220 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 1.000 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.000 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.389 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.461 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.987 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 1 | 0.005 | 0.047 |
| fold_02_2022 | 0 |  |  |
| fold_03_2023 | 10 | 0.014 | 0.293 |
| fold_04_2024 | 10 | 0.018 | 0.356 |
| fold_05_2025 | 9 | 0.032 | 0.331 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `1`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
