# Factor Card: liq_turnover_5d

## Basic Info
- Category: `Liquidity`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean(Ref($turnover_rate, 1), 5)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.383`
- 10d Rank ICIR: `-0.462`
- 20d Rank ICIR: `-0.544`
- Monotonic: `False`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.738 | -0.763 | -0.932 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.737 | -0.746 | -0.841 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.688 | -0.886 | -0.906 | -1 | -1 | True | True | True |  |
| fold_04_2024 | -0.672 | -0.868 | -0.655 | -1 | -1 | True | True | True |  |
| fold_05_2025 | -0.734 | -0.757 | -1.255 | -1 | -1 | True | True | True |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.065 | -0.383 | 62.72% | 2,948 |
| size_neutral | -0.076 | -0.548 | 65.40% | 2,948 |
| industry_neutral | -0.058 | -0.608 | 66.42% | 2,948 |
| size_industry_neutral | -0.066 | -0.794 | 69.20% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.072 | -0.954 | 66.94% | 245 |
| 2015.000 | -0.072 | -0.891 | 75.00% | 244 |
| 2016.000 | -0.088 | -0.958 | 68.85% | 244 |
| 2017.000 | -0.050 | -0.528 | 70.08% | 244 |
| 2018.000 | -0.057 | -0.522 | 66.67% | 243 |
| 2019.000 | -0.071 | -0.965 | 72.54% | 244 |
| 2020.000 | -0.057 | -0.616 | 68.31% | 243 |
| 2021.000 | -0.066 | -0.932 | 66.67% | 243 |
| 2022.000 | -0.062 | -0.841 | 74.38% | 242 |
| 2023.000 | -0.057 | -0.906 | 65.29% | 242 |
| 2024.000 | -0.054 | -0.655 | 68.18% | 242 |
| 2025.000 | -0.083 | -1.255 | 69.55% | 243 |
| 2026.000 | -0.064 | -0.918 | 51.72% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.082 | -1.233 |
| -0.082 | -1.233 |
| -0.083 | -1.232 |
| -0.083 | -1.241 |
| -0.083 | -1.244 |
| -0.084 | -1.249 |
| -0.084 | -1.250 |
| -0.084 | -1.254 |
| -0.084 | -1.253 |
| -0.084 | -1.255 |
| -0.084 | -1.254 |
| -0.084 | -1.257 |
| -0.083 | -1.244 |
| -0.083 | -1.238 |
| -0.082 | -1.228 |
| -0.082 | -1.209 |
| -0.081 | -1.212 |
| -0.081 | -1.216 |
| -0.080 | -1.214 |
| -0.081 | -1.216 |
| -0.081 | -1.221 |
| -0.081 | -1.239 |
| -0.082 | -1.255 |
| -0.082 | -1.265 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `1.265`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.043 | -0.508 | 2,952 |
| 2.000 | -0.051 | -0.613 | 2,951 |
| 3.000 | -0.057 | -0.683 | 2,950 |
| 5.000 | -0.066 | -0.794 | 2,948 |
| 10.000 | -0.079 | -0.971 | 2,943 |
| 20.000 | -0.094 | -1.119 | 2,933 |
| 40.000 | -0.109 | -1.326 | 2,913 |
| 60.000 | -0.120 | -1.603 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `0.00%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-6.484`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.006 | 1.473 | 0.688 | 2.141 | 2,948 |
| 2.000 | 0.005 | 1.154 | 0.662 | 1.742 | 2,948 |
| 3.000 | 0.004 | 0.976 | 0.651 | 1.498 | 2,948 |
| 4.000 | 0.003 | 0.843 | 0.672 | 1.255 | 2,948 |
| 5.000 | -0.000 | -0.093 | 0.781 | -0.120 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.917 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.905 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.381 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.359 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.000 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 3 | -0.005 | -0.131 |
| fold_02_2022 | 3 | -0.007 | -0.193 |
| fold_03_2023 | 1 | -0.032 | -0.674 |
| fold_04_2024 | 2 | -0.027 | -0.631 |
| fold_05_2025 | 0 |  |  |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `keep`
- Selected folds: `3`
- Validation-pass folds: `5`
- Summary: Repeatedly selected across OOS folds.
