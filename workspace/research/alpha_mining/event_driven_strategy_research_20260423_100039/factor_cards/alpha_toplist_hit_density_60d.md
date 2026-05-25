# Factor Card: alpha_toplist_hit_density_60d

## Basic Info
- Category: `Other`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Sum(If(Ref($top_list__l_amount, 1) == Ref($top_list__l_amount, 1), 1, 0), 60)`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.529`
- 10d Rank ICIR: `-0.640`
- 20d Rank ICIR: `-0.779`
- Monotonic: `True`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.703 | -0.868 | -0.743 | -1 | -1 | True | True | True |  |
| fold_02_2022 | -0.705 | -0.801 | -0.561 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.763 | -0.645 | -0.578 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.719 | -0.558 | -0.389 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.720 | -0.479 | -0.731 | -1 | -1 | True | True | True |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.053 | -0.529 | 63.09% | 2,948 |
| size_neutral | -0.051 | -0.508 | 64.18% | 2,948 |
| industry_neutral | -0.035 | -0.617 | 65.13% | 2,948 |
| size_industry_neutral | -0.037 | -0.670 | 65.64% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.041 | -0.854 | 63.67% | 245 |
| 2015.000 | -0.040 | -0.601 | 56.97% | 244 |
| 2016.000 | -0.051 | -0.935 | 63.93% | 244 |
| 2017.000 | -0.027 | -0.560 | 63.52% | 244 |
| 2018.000 | -0.041 | -0.651 | 66.26% | 243 |
| 2019.000 | -0.043 | -0.862 | 69.67% | 244 |
| 2020.000 | -0.043 | -0.872 | 74.49% | 243 |
| 2021.000 | -0.029 | -0.743 | 62.96% | 243 |
| 2022.000 | -0.025 | -0.561 | 66.53% | 242 |
| 2023.000 | -0.038 | -0.578 | 70.25% | 242 |
| 2024.000 | -0.027 | -0.389 | 66.53% | 242 |
| 2025.000 | -0.038 | -0.731 | 63.37% | 243 |
| 2026.000 | -0.055 | -1.048 | 62.07% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.038 | -0.738 |
| -0.038 | -0.741 |
| -0.039 | -0.747 |
| -0.039 | -0.755 |
| -0.040 | -0.762 |
| -0.040 | -0.770 |
| -0.040 | -0.773 |
| -0.040 | -0.779 |
| -0.040 | -0.779 |
| -0.040 | -0.782 |
| -0.040 | -0.779 |
| -0.040 | -0.775 |
| -0.040 | -0.767 |
| -0.039 | -0.760 |
| -0.038 | -0.751 |
| -0.038 | -0.746 |
| -0.038 | -0.747 |
| -0.037 | -0.748 |
| -0.038 | -0.747 |
| -0.038 | -0.746 |
| -0.038 | -0.749 |
| -0.038 | -0.752 |
| -0.039 | -0.755 |
| -0.039 | -0.763 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `1.098`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.023 | -0.427 | 2,952 |
| 2.000 | -0.028 | -0.505 | 2,951 |
| 3.000 | -0.032 | -0.565 | 2,950 |
| 5.000 | -0.037 | -0.670 | 2,948 |
| 10.000 | -0.045 | -0.805 | 2,943 |
| 20.000 | -0.053 | -0.963 | 2,933 |
| 40.000 | -0.063 | -1.111 | 2,913 |
| 60.000 | -0.069 | -1.199 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-63.18%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-6.348`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.145 | 0.715 | 1.601 | 2,948 |
| 2.000 | 0.005 | 1.143 | 0.684 | 1.670 | 2,948 |
| 3.000 | 0.004 | 0.991 | 0.655 | 1.513 | 2,948 |
| 4.000 | 0.003 | 0.863 | 0.645 | 1.337 | 2,948 |
| 5.000 | 0.001 | 0.160 | 0.751 | 0.213 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.000 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.997 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.389 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.456 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.392 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 0 |  |  |
| fold_02_2022 | 1 | -0.002 | -0.019 |
| fold_03_2023 | 10 | 0.014 | 0.291 |
| fold_04_2024 | 10 | 0.018 | 0.343 |
| fold_05_2025 | 8 | 0.010 | 0.168 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `keep`
- Selected folds: `2`
- Validation-pass folds: `5`
- Summary: Repeatedly selected across OOS folds.
