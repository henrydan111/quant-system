# Factor Card: tech_price_to_ma60

## Basic Info
- Category: `Technical`
- Signal direction in strategy: `low_is_good`
- Raw expression: `Ref(($close * $adj_factor), 1) / Mean(Ref(($close * $adj_factor), 1), 60) - 1`

## Screening Snapshot
- Grade: `B`
- 5d Rank ICIR: `-0.383`
- 10d Rank ICIR: `-0.440`
- 20d Rank ICIR: `-0.497`
- Monotonic: `True`
- Warning flags: ``
- Primary coverage: ``

## Fold Metrics
| fold_id | train_icir | val_icir | test_icir | train_direction | val_direction | direction_consistent | validation_pass | selected | selection_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | -0.587 | -0.467 | -0.551 | -1 | -1 | True | True | False |  |
| fold_02_2022 | -0.573 | -0.438 | -0.590 | -1 | -1 | True | True | False |  |
| fold_03_2023 | -0.448 | -0.570 | -0.286 | -1 | -1 | True | True | False |  |
| fold_04_2024 | -0.429 | -0.434 | -0.400 | -1 | -1 | True | True | False |  |
| fold_05_2025 | -0.489 | -0.345 | -0.718 | -1 | -1 | True | True | False |  |

## Neutralization Comparison
| variant | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| raw | -0.061 | -0.383 | 60.69% | 2,948 |
| size_neutral | -0.060 | -0.428 | 61.16% | 2,948 |
| industry_neutral | -0.056 | -0.455 | 63.53% | 2,948 |
| size_industry_neutral | -0.056 | -0.524 | 65.23% | 2,948 |

## Yearly IC
| year | mean_rank_ic | rank_icir | ic_hit_rate | n_days |
| --- | --- | --- | --- | --- |
| 2014.000 | -0.064 | -0.700 | 67.76% | 245 |
| 2015.000 | -0.118 | -1.024 | 80.74% | 244 |
| 2016.000 | -0.071 | -0.636 | 68.85% | 244 |
| 2017.000 | -0.036 | -0.302 | 60.25% | 244 |
| 2018.000 | -0.046 | -0.402 | 66.67% | 243 |
| 2019.000 | -0.060 | -0.609 | 67.62% | 244 |
| 2020.000 | -0.032 | -0.331 | 55.14% | 243 |
| 2021.000 | -0.052 | -0.551 | 59.26% | 243 |
| 2022.000 | -0.053 | -0.590 | 72.73% | 242 |
| 2023.000 | -0.025 | -0.286 | 61.16% | 242 |
| 2024.000 | -0.056 | -0.400 | 65.29% | 242 |
| 2025.000 | -0.062 | -0.718 | 59.67% | 243 |
| 2026.000 | -0.024 | -0.506 | 44.83% | 29 |

## Rolling IC Tail
| roll_mean_rank_ic | rolling_rank_icir |
| --- | --- |
| -0.062 | -0.716 |
| -0.062 | -0.716 |
| -0.061 | -0.715 |
| -0.061 | -0.715 |
| -0.061 | -0.709 |
| -0.061 | -0.708 |
| -0.060 | -0.699 |
| -0.060 | -0.692 |
| -0.059 | -0.687 |
| -0.058 | -0.679 |
| -0.058 | -0.673 |
| -0.058 | -0.668 |
| -0.058 | -0.680 |
| -0.059 | -0.699 |
| -0.060 | -0.716 |
| -0.060 | -0.722 |
| -0.061 | -0.736 |
| -0.061 | -0.735 |
| -0.060 | -0.732 |
| -0.059 | -0.735 |
| -0.058 | -0.741 |
| -0.057 | -0.739 |
| -0.056 | -0.735 |
| -0.055 | -0.728 |

## IC Decay
- Best horizon by |ICIR|: `60`
- Peak ICIR: `0.544`
- Half-life estimate: `None`
| horizon | mean_rank_ic | rank_icir | n_days |
| --- | --- | --- | --- |
| 1.000 | -0.039 | -0.368 | 2,952 |
| 2.000 | -0.045 | -0.416 | 2,951 |
| 3.000 | -0.050 | -0.464 | 2,950 |
| 5.000 | -0.056 | -0.524 | 2,948 |
| 10.000 | -0.063 | -0.588 | 2,943 |
| 20.000 | -0.066 | -0.641 | 2,933 |
| 40.000 | -0.060 | -0.635 | 2,913 |
| 60.000 | -0.054 | -0.606 | 2,893 |

## Quantile Diagnostic
- Long-short annualized diagnostic return: `0.00%`
- Long-short total diagnostic return: `-100.00%`
- Long-short Sharpe: `-4.881`
- Monotonic: `True`
- Monotonic Spearman: `-1.000`
| quantile | mean_daily_return | annualized_return | volatility | sharpe | n_days |
| --- | --- | --- | --- | --- | --- |
| 1.000 | 0.005 | 1.354 | 0.759 | 1.784 | 2,948 |
| 2.000 | 0.005 | 1.238 | 0.695 | 1.782 | 2,948 |
| 3.000 | 0.004 | 1.073 | 0.664 | 1.617 | 2,948 |
| 4.000 | 0.003 | 0.834 | 0.655 | 1.273 | 2,948 |
| 5.000 | -0.001 | -0.147 | 0.696 | -0.211 | 2,948 |

## Correlation And Redundancy
| fold_id | peer_factor | abs_corr | cluster_id |
| --- | --- | --- | --- |
| fold_01_2021 | selected_cluster_peer | 0.610 | selected_cluster |
| fold_02_2022 | selected_cluster_peer | 0.798 | selected_cluster |
| fold_03_2023 | selected_cluster_peer | 0.797 | selected_cluster |
| fold_04_2024 | selected_cluster_peer | 0.802 | selected_cluster |
| fold_05_2025 | selected_cluster_peer | 0.743 | selected_cluster |

## Marginal IC
| fold_id | base_factor_count | marginal_mean_rank_ic | marginal_rank_icir |
| --- | --- | --- | --- |
| fold_01_2021 | 10 | 0.011 | 0.152 |
| fold_02_2022 | 10 | -0.005 | -0.059 |
| fold_03_2023 | 10 | -0.008 | -0.091 |
| fold_04_2024 | 10 | 0.002 | 0.029 |
| fold_05_2025 | 10 | 0.008 | 0.085 |

## Risks
- No dominant implementation red flag, but stability still needs OOS confirmation.

## Conclusion
- Final decision: `reserve`
- Selected folds: `0`
- Validation-pass folds: `5`
- Summary: Shows some predictive value, but not stable enough for the core book.
