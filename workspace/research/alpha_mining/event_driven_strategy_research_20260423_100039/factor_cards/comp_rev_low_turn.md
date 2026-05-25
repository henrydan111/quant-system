# Factor Card: comp_rev_low_turn

## Basic Info
- Category: `Other`
- Signal direction in strategy: `high_is_good`
- Raw expression: `COMPOSITE(rev_return_5d, liq_turnover_20d)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `0.479`
- 10d Rank ICIR: `0.521`
- 20d Rank ICIR: `0.580`
- Monotonic: `True`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | 0.799 | 0.682 | 0.870 | 1 | 1 | True | True | True |  |
| fold_02_2022 | 0.762 | 0.743 | 0.841 | 1 | 1 | True | True | True |  |
| fold_03_2023 | 0.720 | 0.856 | 0.783 | 1 | 1 | True | True | True |  |
| fold_04_2024 | 0.689 | 0.812 | 0.711 | 1 | 1 | True | True | True |  |
| fold_05_2025 | 0.721 | 0.736 | 1.057 | 1 | 1 | True | True | True |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | 0.065 | 0.479 | 59.63% | 2,948 |
| size_neutral | 0.071 | 0.575 | 62.69% | 2,948 |
| industry_neutral | 0.062 | 0.653 | 64.38% | 2,948 |
| size_industry_neutral | 0.068 | 0.788 | 68.59% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | 0.078 | 0.917 | 70.61% | 245 |
| 2015.000 | 0.088 | 0.858 | 75.00% | 244 |
| 2016.000 | 0.096 | 1.018 | 77.05% | 244 |
| 2017.000 | 0.059 | 0.664 | 65.16% | 244 |
| 2018.000 | 0.057 | 0.594 | 68.31% | 243 |
| 2019.000 | 0.060 | 0.721 | 68.85% | 244 |
| 2020.000 | 0.060 | 0.647 | 59.67% | 243 |
| 2021.000 | 0.065 | 0.870 | 67.08% | 243 |
| 2022.000 | 0.064 | 0.841 | 71.07% | 242 |
| 2023.000 | 0.055 | 0.783 | 64.46% | 242 |
| 2024.000 | 0.064 | 0.711 | 69.42% | 242 |
| 2025.000 | 0.073 | 1.057 | 67.49% | 243 |
| 2026.000 | 0.057 | 0.718 | 58.62% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| 0.072 | 1.011 |
| 0.072 | 1.008 |
| 0.073 | 1.007 |
| 0.073 | 1.007 |
| 0.073 | 1.008 |
| 0.074 | 1.017 |
| 0.073 | 1.011 |
| 0.073 | 1.011 |
| 0.073 | 1.013 |
| 0.073 | 1.011 |
| 0.073 | 1.015 |
| 0.074 | 1.028 |
| 0.074 | 1.027 |
| 0.074 | 1.026 |
| 0.074 | 1.025 |
| 0.073 | 1.019 |
| 0.073 | 1.018 |
| 0.072 | 1.018 |
| 0.072 | 1.017 |
| 0.072 | 1.014 |
| 0.072 | 1.013 |
| 0.072 | 1.022 |
| 0.072 | 1.020 |
| 0.072 | 1.017 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `1.017`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | 0.052 | 0.567 | 2,952 |
| 2.000 | 0.059 | 0.671 | 2,951 |
| 3.000 | 0.064 | 0.737 | 2,950 |
| 5.000 | 0.068 | 0.788 | 2,948 |
| 10.000 | 0.075 | 0.862 | 2,943 |
| 20.000 | 0.088 | 0.989 | 2,933 |
| 40.000 | 0.099 | 1.189 | 2,913 |
| 60.000 | 0.105 | 1.380 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `361.29%`
- Long-short total diagnostic return: `5853443600.00%`
- Long-short Sharpe: `6.506`
- Monotonic: `True`
- Monotonic Spearman: `1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | -0.001 | -0.155 | 0.740 | -0.210 | 2,948 |
| 2.000 | 0.003 | 0.868 | 0.690 | 1.258 | 2,948 |
| 3.000 | 0.004 | 1.013 | 0.670 | 1.512 | 2,948 |
| 4.000 | 0.005 | 1.201 | 0.665 | 1.806 | 2,948 |
| 5.000 | 0.006 | 1.407 | 0.677 | 2.077 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.413 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.449 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.467 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.421 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.425 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 6 | 0.015 | 0.243 |
| fold_02_2022 | 3 | 0.025 | 0.412 |
| fold_03_2023 | 2 | 0.025 | 0.400 |
| fold_04_2024 | 4 | 0.019 | 0.303 |
| fold_05_2025 | 1 | 0.032 | 0.404 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `keep`
- Selected folds: `5`
- Validation-pass folds: `5`
- Summary: Repeatedly selected across OOS folds.
