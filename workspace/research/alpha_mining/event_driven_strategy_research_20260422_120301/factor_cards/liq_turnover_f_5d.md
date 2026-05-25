# Factor Card: liq_turnover_f_5d

## Basic Info
- Category: `Liquidity`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean(Ref($turnover_rate_f, 1), 5)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.438`
- 10d Rank ICIR: `-0.531`
- 20d Rank ICIR: `-0.627`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.778 | -0.772 | -0.944 | -1 | -1 | True | True | True |  |
| fold_02_2022 | -0.783 | -0.754 | -0.799 | -1 | -1 | True | True | True |  |
| fold_03_2023 | -0.726 | -0.869 | -0.859 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.709 | -0.823 | -0.645 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.743 | -0.726 | -1.171 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.071 | -0.437 | 64.89% | 2,948 |
| size_neutral | -0.080 | -0.584 | 67.06% | 2,948 |
| industry_neutral | -0.063 | -0.648 | 68.18% | 2,948 |
| size_industry_neutral | -0.070 | -0.803 | 70.12% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.076 | -0.918 | 71.84% | 245 |
| 2015.000 | -0.084 | -0.920 | 75.82% | 244 |
| 2016.000 | -0.096 | -0.975 | 70.90% | 244 |
| 2017.000 | -0.059 | -0.619 | 71.72% | 244 |
| 2018.000 | -0.061 | -0.558 | 68.31% | 243 |
| 2019.000 | -0.076 | -0.962 | 71.72% | 244 |
| 2020.000 | -0.062 | -0.630 | 67.08% | 243 |
| 2021.000 | -0.068 | -0.944 | 66.26% | 243 |
| 2022.000 | -0.061 | -0.799 | 72.31% | 242 |
| 2023.000 | -0.055 | -0.859 | 66.53% | 242 |
| 2024.000 | -0.057 | -0.645 | 71.07% | 242 |
| 2025.000 | -0.086 | -1.171 | 69.14% | 243 |
| 2026.000 | -0.070 | -0.966 | 58.62% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.085 | -1.154 |
| -0.085 | -1.155 |
| -0.086 | -1.154 |
| -0.086 | -1.161 |
| -0.086 | -1.165 |
| -0.087 | -1.170 |
| -0.087 | -1.171 |
| -0.087 | -1.176 |
| -0.087 | -1.178 |
| -0.087 | -1.179 |
| -0.087 | -1.179 |
| -0.087 | -1.181 |
| -0.087 | -1.170 |
| -0.087 | -1.165 |
| -0.086 | -1.157 |
| -0.085 | -1.143 |
| -0.085 | -1.145 |
| -0.085 | -1.148 |
| -0.084 | -1.146 |
| -0.085 | -1.148 |
| -0.085 | -1.152 |
| -0.085 | -1.167 |
| -0.086 | -1.184 |
| -0.086 | -1.192 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `1.354`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.047 | -0.513 | 2,952 |
| 2.000 | -0.055 | -0.620 | 2,951 |
| 3.000 | -0.061 | -0.691 | 2,950 |
| 5.000 | -0.070 | -0.803 | 2,948 |
| 10.000 | -0.084 | -0.979 | 2,943 |
| 20.000 | -0.098 | -1.121 | 2,933 |
| 40.000 | -0.112 | -1.315 | 2,913 |
| 60.000 | -0.121 | -1.574 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `0.00%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-6.332`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.386 | 0.671 | 2.066 | 2,948 |
| 2.000 | 0.005 | 1.179 | 0.661 | 1.782 | 2,948 |
| 3.000 | 0.004 | 1.046 | 0.661 | 1.584 | 2,948 |
| 4.000 | 0.004 | 0.938 | 0.683 | 1.373 | 2,948 |
| 5.000 | -0.001 | -0.196 | 0.779 | -0.252 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.188 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.562 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.903 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.906 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.902 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 1 | -0.057 | -0.638 |
| fold_02_2022 | 1 | -0.039 | -0.679 |
| fold_03_2023 | 2 | -0.001 | -0.014 |
| fold_04_2024 | 3 | 0.007 | 0.212 |
| fold_05_2025 | 2 | -0.007 | -0.214 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `keep`
- Selected folds: `2`
- Validation-pass folds: `5`
- Summary: Repeatedly selected across OOS folds.
