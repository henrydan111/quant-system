# Factor Card: liq_vol_surge

## Basic Info
- Category: `Liquidity`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Mean($vol, 5) / Mean($vol, 60)`

## Screening Snapshot
- Grade: `B (Strong IC)`
- 5d Rank ICIR: `-0.474`
- 10d Rank ICIR: `-0.488`
- 20d Rank ICIR: `-0.509`
- Monotonic: `False`
- Warning flags: `nan`
- Primary coverage: `100.00%`

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | -0.699 | -0.665 | -1.058 | -1 | -1 | True | True | True |  |
| fold_02_2020 | -0.682 | -0.984 | -0.327 | -1 | -1 | True | True | True |  |
| fold_03_2021 | -0.686 | -0.628 | -0.616 | -1 | -1 | True | True | False |  |
| fold_04_2022 | -0.791 | -0.450 | -0.882 | -1 | -1 | True | True | False |  |
| fold_05_2023 | -0.680 | -0.736 | -0.473 | -1 | -1 | True | True | True |  |
| fold_06_2024 | -0.639 | -0.643 | -0.772 | -1 | -1 | True | True | True |  |
| fold_07_2025 | -0.713 | -0.616 | -0.989 | -1 | -1 | True | True | True |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.051 | -0.474 | 67.89% | 3,429 |
| size_neutral | -0.051 | -0.517 | 68.30% | 3,429 |
| industry_neutral | -0.049 | -0.633 | 72.44% | 3,429 |
| size_industry_neutral | -0.049 | -0.687 | 73.37% | 3,429 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2012.000 | -0.047 | -0.577 | 76.13% | 243 |
| 2013.000 | -0.059 | -0.837 | 69.33% | 238 |
| 2014.000 | -0.036 | -0.484 | 64.49% | 245 |
| 2015.000 | -0.072 | -0.831 | 77.87% | 244 |
| 2016.000 | -0.059 | -0.820 | 77.87% | 244 |
| 2017.000 | -0.040 | -0.500 | 73.77% | 244 |
| 2018.000 | -0.054 | -0.914 | 85.60% | 243 |
| 2019.000 | -0.065 | -1.058 | 85.66% | 244 |
| 2020.000 | -0.025 | -0.327 | 63.79% | 243 |
| 2021.000 | -0.036 | -0.616 | 63.37% | 243 |
| 2022.000 | -0.045 | -0.882 | 78.10% | 242 |
| 2023.000 | -0.031 | -0.473 | 66.12% | 242 |
| 2024.000 | -0.051 | -0.772 | 75.21% | 242 |
| 2025.000 | -0.062 | -0.989 | 73.25% | 243 |
| 2026.000 | -0.032 | -0.504 | 44.83% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.061 | -0.982 |
| -0.061 | -0.983 |
| -0.062 | -0.986 |
| -0.062 | -0.991 |
| -0.062 | -0.987 |
| -0.061 | -0.976 |
| -0.061 | -0.968 |
| -0.060 | -0.961 |
| -0.059 | -0.945 |
| -0.058 | -0.921 |
| -0.057 | -0.909 |
| -0.057 | -0.902 |
| -0.057 | -0.905 |
| -0.057 | -0.914 |
| -0.058 | -0.921 |
| -0.058 | -0.921 |
| -0.057 | -0.917 |
| -0.057 | -0.909 |
| -0.056 | -0.905 |
| -0.056 | -0.908 |
| -0.055 | -0.911 |
| -0.055 | -0.912 |
| -0.055 | -0.911 |
| -0.055 | -0.910 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.754`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.044 | -0.596 | 3,433 |
| 2.000 | -0.046 | -0.637 | 3,432 |
| 3.000 | -0.048 | -0.663 | 3,431 |
| 5.000 | -0.049 | -0.687 | 3,429 |
| 10.000 | -0.049 | -0.726 | 3,424 |
| 20.000 | -0.049 | -0.754 | 3,414 |
| 40.000 | -0.044 | -0.731 | 3,394 |
| 60.000 | -0.041 | -0.696 | 3,374 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `-67.39%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-5.726`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.157 | 0.684 | 1.690 | 3,429 |
| 2.000 | 0.004 | 1.104 | 0.666 | 1.657 | 3,429 |
| 3.000 | 0.004 | 1.069 | 0.654 | 1.634 | 3,429 |
| 4.000 | 0.004 | 0.988 | 0.654 | 1.510 | 3,429 |
| 5.000 | 0.000 | 0.049 | 0.686 | 0.071 | 3,429 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2019 | selected_cluster_peer | 0.355 | selected_cluster |
| fold_02_2020 | selected_cluster_peer | 0.256 | selected_cluster |
| fold_03_2021 | selected_cluster_peer | 0.977 | selected_cluster |
| fold_04_2022 | selected_cluster_peer | 0.477 | selected_cluster |
| fold_05_2023 | selected_cluster_peer | 0.448 | selected_cluster |
| fold_06_2024 | selected_cluster_peer | 0.453 | selected_cluster |
| fold_07_2025 | selected_cluster_peer | 0.390 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2019 | 5 | -0.010 | -0.206 |
| fold_02_2020 | 1 | -0.039 | -0.796 |
| fold_03_2021 | 9 | 0.013 | 0.282 |
| fold_04_2022 | 10 | 0.010 | 0.233 |
| fold_05_2023 | 5 | 0.010 | 0.235 |
| fold_06_2024 | 9 | 0.004 | 0.097 |
| fold_07_2025 | 4 | -0.004 | -0.064 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `keep`
- Selected folds: `5`
- Validation-pass folds: `7`
- Summary: Repeatedly selected across OOS folds.
