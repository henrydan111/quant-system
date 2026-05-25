# Factor Card: comp_defensive

## Basic Info
- Category: `Other`
- Signal direction in strategy: `high_is_good`
- Raw expression: `COMPOSITE(qual_roe, risk_vol_20d)`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `0.303`
- 10d Rank ICIR: `0.341`
- 20d Rank ICIR: `0.375`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | 0.536 | 0.742 | 0.592 | 1 | 1 | True | True | True |  |
| fold_02_2020 | 0.638 | 0.593 | 0.785 | 1 | 1 | True | True | True |  |
| fold_03_2021 | 0.618 | 0.670 | 0.728 | 1 | 1 | True | True | True |  |
| fold_04_2022 | 0.616 | 0.753 | 0.623 | 1 | 1 | True | True | False |  |
| fold_05_2023 | 0.700 | 0.672 | 0.730 | 1 | 1 | True | True | False |  |
| fold_06_2024 | 0.702 | 0.675 | 0.364 | 1 | 1 | True | True | True |  |
| fold_07_2025 | 0.649 | 0.456 | 0.548 | 1 | 1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | 0.048 | 0.303 | 52.52% | 3,429 |
| size_neutral | 0.058 | 0.448 | 56.78% | 3,429 |
| industry_neutral | 0.045 | 0.376 | 55.35% | 3,429 |
| size_industry_neutral | 0.055 | 0.578 | 61.33% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | 0.040 | 0.384 | 60.91% | 243 |
| 2013.000 | 0.054 | 0.725 | 60.92% | 238 |
| 2014.000 | 0.047 | 0.607 | 56.73% | 245 |
| 2015.000 | 0.045 | 0.410 | 64.34% | 244 |
| 2016.000 | 0.064 | 0.684 | 65.57% | 244 |
| 2017.000 | 0.073 | 0.910 | 74.18% | 244 |
| 2018.000 | 0.053 | 0.600 | 65.84% | 243 |
| 2019.000 | 0.063 | 0.592 | 60.66% | 244 |
| 2020.000 | 0.063 | 0.785 | 67.90% | 243 |
| 2021.000 | 0.049 | 0.728 | 57.20% | 243 |
| 2022.000 | 0.047 | 0.623 | 55.37% | 242 |
| 2023.000 | 0.053 | 0.730 | 61.98% | 242 |
| 2024.000 | 0.054 | 0.364 | 54.13% | 242 |
| 2025.000 | 0.059 | 0.548 | 53.91% | 243 |
| 2026.000 | 0.065 | 0.632 | 51.72% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| 0.061 | 0.558 |
| 0.061 | 0.558 |
| 0.061 | 0.559 |
| 0.061 | 0.560 |
| 0.061 | 0.558 |
| 0.061 | 0.561 |
| 0.061 | 0.565 |
| 0.062 | 0.571 |
| 0.062 | 0.576 |
| 0.063 | 0.581 |
| 0.064 | 0.587 |
| 0.064 | 0.590 |
| 0.063 | 0.585 |
| 0.062 | 0.580 |
| 0.061 | 0.573 |
| 0.060 | 0.559 |
| 0.059 | 0.555 |
| 0.059 | 0.555 |
| 0.059 | 0.559 |
| 0.060 | 0.571 |
| 0.061 | 0.594 |
| 0.062 | 0.621 |
| 0.063 | 0.644 |
| 0.064 | 0.660 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.762`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | 0.036 | 0.402 | 3,433 |
| 2.000 | 0.043 | 0.471 | 3,432 |
| 3.000 | 0.048 | 0.513 | 3,431 |
| 5.000 | 0.055 | 0.578 | 3,429 |
| 10.000 | 0.064 | 0.661 | 3,424 |
| 20.000 | 0.074 | 0.754 | 3,414 |
| 40.000 | 0.084 | 0.928 | 3,394 |
| 60.000 | 0.091 | 1.042 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `134.72%`
- Long-short total diagnostic return: `11017878.91%`
- Long-short Sharpe: `3.709`
- Monotonic: `True`
- Monotonic Spearman: `1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.001 | 0.283 | 0.746 | 0.379 | 3,429 |
| 2.000 | 0.003 | 0.867 | 0.699 | 1.241 | 3,429 |
| 3.000 | 0.004 | 0.981 | 0.657 | 1.493 | 3,429 |
| 4.000 | 0.004 | 1.061 | 0.629 | 1.685 | 3,429 |
| 5.000 | 0.005 | 1.166 | 0.613 | 1.902 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.542 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.569 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.595 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.604 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.614 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.594 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.549 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 2 | 0.026 | 0.331 |
| fold_02_2020 | 8 | 0.020 | 0.252 |
| fold_03_2021 | 6 | 0.022 | 0.297 |
| fold_04_2022 | 3 | 0.018 | 0.307 |
| fold_05_2023 | 8 | 0.003 | 0.065 |
| fold_06_2024 | 7 | 0.007 | 0.120 |
| fold_07_2025 | 10 | 0.021 | 0.214 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `keep`
- Selected folds: `4`
- Validation-pass folds: `7`
- Summary: Repeatedly selected across OOS folds.
