# Factor Card: risk_skew_60d

## Basic Info
- Category: `Volatility`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Skew((($close * $adj_factor) / Ref(($close * $adj_factor), 1) - 1), 60)`

## Screening Snapshot
- Grade: `A (Graduated)`
- 5d Rank ICIR: `-0.459`
- 10d Rank ICIR: `-0.522`
- 20d Rank ICIR: `-0.525`
- Monotonic: `True`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.538 | -0.713 | -0.670 | -1 | -1 | True | True | True |  |
| fold_02_2020 | -0.569 | -0.705 | -0.556 | -1 | -1 | True | True | True |  |
| fold_03_2021 | -0.586 | -0.610 | -0.777 | -1 | -1 | True | True | True |  |
| fold_04_2022 | -0.540 | -0.645 | -0.674 | -1 | -1 | True | True | True |  |
| fold_05_2023 | -0.629 | -0.713 | -0.796 | -1 | -1 | True | True | True |  |
| fold_06_2024 | -0.668 | -0.730 | -0.444 | -1 | -1 | True | True | True |  |
| fold_07_2025 | -0.672 | -0.525 | -0.711 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.039 | -0.459 | 62.93% | 3,429 |
| size_neutral | -0.036 | -0.488 | 61.36% | 3,429 |
| industry_neutral | -0.036 | -0.549 | 65.18% | 3,429 |
| size_industry_neutral | -0.034 | -0.596 | 63.87% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.033 | -0.509 | 60.08% | 243 |
| 2013.000 | -0.037 | -0.681 | 67.23% | 238 |
| 2014.000 | -0.040 | -1.127 | 71.43% | 245 |
| 2015.000 | -0.012 | -0.182 | 55.74% | 244 |
| 2016.000 | -0.042 | -0.573 | 70.49% | 244 |
| 2017.000 | -0.038 | -0.664 | 69.26% | 244 |
| 2018.000 | -0.045 | -0.761 | 71.60% | 243 |
| 2019.000 | -0.029 | -0.670 | 64.75% | 244 |
| 2020.000 | -0.027 | -0.556 | 56.79% | 243 |
| 2021.000 | -0.028 | -0.777 | 60.49% | 243 |
| 2022.000 | -0.031 | -0.674 | 63.22% | 242 |
| 2023.000 | -0.033 | -0.796 | 61.57% | 242 |
| 2024.000 | -0.038 | -0.444 | 65.70% | 242 |
| 2025.000 | -0.040 | -0.711 | 55.56% | 243 |
| 2026.000 | -0.049 | -1.144 | 65.52% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.040 | -0.703 |
| -0.040 | -0.706 |
| -0.040 | -0.708 |
| -0.041 | -0.714 |
| -0.041 | -0.724 |
| -0.042 | -0.732 |
| -0.042 | -0.738 |
| -0.042 | -0.753 |
| -0.043 | -0.763 |
| -0.043 | -0.771 |
| -0.043 | -0.781 |
| -0.044 | -0.788 |
| -0.044 | -0.787 |
| -0.044 | -0.787 |
| -0.043 | -0.783 |
| -0.043 | -0.776 |
| -0.043 | -0.775 |
| -0.042 | -0.776 |
| -0.042 | -0.774 |
| -0.042 | -0.777 |
| -0.043 | -0.784 |
| -0.043 | -0.804 |
| -0.044 | -0.831 |
| -0.044 | -0.850 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.519`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.019 | -0.349 | 3,433 |
| 2.000 | -0.024 | -0.438 | 3,432 |
| 3.000 | -0.028 | -0.502 | 3,431 |
| 5.000 | -0.034 | -0.596 | 3,429 |
| 10.000 | -0.040 | -0.701 | 3,424 |
| 20.000 | -0.043 | -0.758 | 3,414 |
| 40.000 | -0.043 | -0.790 | 3,394 |
| 60.000 | -0.045 | -0.837 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-40.24%`
- Long-short total diagnostic return: `-99.91%`
- Long-short Sharpe: `-3.404`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.004 | 1.087 | 0.651 | 1.670 | 3,429 |
| 2.000 | 0.004 | 1.039 | 0.666 | 1.560 | 3,429 |
| 3.000 | 0.003 | 0.867 | 0.674 | 1.287 | 3,429 |
| 4.000 | 0.003 | 0.774 | 0.676 | 1.144 | 3,429 |
| 5.000 | 0.002 | 0.583 | 0.669 | 0.872 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.396 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.384 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.351 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.348 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.382 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.393 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.444 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 3 | -0.009 | -0.173 |
| fold_02_2020 | 6 | -0.010 | -0.244 |
| fold_03_2021 | 9 | -0.007 | -0.206 |
| fold_04_2022 | 5 | -0.006 | -0.165 |
| fold_05_2023 | 7 | -0.005 | -0.160 |
| fold_06_2024 | 6 | -0.007 | -0.200 |
| fold_07_2025 | 10 | -0.009 | -0.208 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `keep`
- Selected folds: `6`
- Validation-pass folds: `7`
- Summary: Repeatedly selected across OOS folds.
