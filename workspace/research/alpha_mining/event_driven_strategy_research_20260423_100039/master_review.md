# Event-Driven Strategy Research Review

## Research Design
- Screening input: `E:\量化系统\workspace\research\alpha_mining\expanded_screening_20260423`
- Candidate scope: `42` A/B factors
- Rolling split: `5y train / 2y validation / 1y test`, step `1y`
- Strategy style: `all-market long-only`
- Benchmark: `000905.SH`
- Capital: `2,000,000` RMB

## Anti-Lookahead Controls
- Factor directions are locked from the train window only.
- Factor admission and redundancy removal use train/validation only.
- Each fold's event-driven backtest runs only on its own test window.
- The 2026 partial window is held out as a diagnostic and does not feed factor admission.

## Candidate Pool Overview
| factor | category | grade | abs_icir | overall_decision | selected_count | validation_pass_count |
| --- | --- | --- | --- | --- | --- | --- |
| liq_vol_cv_20d | Liquidity | A | 0.636 | keep | 5 | 5 |
| alpha_topinst_hit_density_60d | Other | B | 0.541 | reserve | 1 | 5 |
| rev_max_return_20d | Reversal | B | 0.535 | keep | 4 | 5 |
| alpha_toplist_hit_density_60d | Other | B | 0.529 | keep | 2 | 5 |
| liq_log_dollar_vol | Liquidity | B | 0.507 | reserve | 1 | 5 |
| comp_rev_low_turn | Other | B | 0.479 | keep | 5 | 5 |
| risk_skew_60d | Volatility | B | 0.468 | keep | 3 | 5 |
| tech_skew_20d | Technical | B | 0.456 | reserve | 1 | 5 |
| mom_intraday_20d | Momentum | B | 0.454 | reserve | 1 | 5 |
| mom_high_moment_20d | Momentum | B | 0.451 | keep | 4 | 5 |
| liq_turnover_f_5d | Liquidity | B | 0.438 | keep | 2 | 5 |
| mom_ewm_60d | Momentum | B | 0.434 | reserve | 0 | 5 |
| risk_vol_10d | Volatility | B | 0.413 | keep | 3 | 5 |
| tech_close_to_low_20d | Technical | B | 0.407 | keep | 4 | 5 |
| mom_weighted_120d | Momentum | B | 0.393 | reserve | 0 | 5 |
| risk_vol_5d | Volatility | B | 0.391 | keep | 2 | 5 |
| liq_vol_surge | Liquidity | B | 0.389 | reserve | 1 | 5 |
| liq_turnover_f_20d | Liquidity | B | 0.385 | reserve | 0 | 5 |
| mom_ewm_20d | Momentum | B | 0.385 | reserve | 0 | 5 |
| tech_price_to_ma60 | Technical | B | 0.383 | reserve | 0 | 5 |
| liq_turnover_5d | Liquidity | B | 0.383 | keep | 3 | 5 |
| risk_vol_20d | Volatility | B | 0.381 | reserve | 1 | 5 |
| flow_net_inflow_20d | Capital Flow | B | 0.378 | reserve | 1 | 5 |
| liq_turnover_ratio_5_60 | Liquidity | B | 0.377 | reserve | 0 | 5 |
| liq_spread_proxy_20d | Liquidity | B | 0.367 | reserve | 0 | 5 |
| mom_return_20d | Momentum | B | 0.366 | reserve | 0 | 5 |
| liq_turnover_10d | Liquidity | B | 0.366 | reserve | 0 | 5 |
| comp_small_value | Other | B | 0.362 | keep | 2 | 5 |
| val_pb_change_60d | Value | B | 0.361 | reserve | 0 | 5 |
| risk_range_ratio_20d | Volatility | B | 0.361 | reserve | 0 | 5 |
| tech_rsi_28 | Technical | B | 0.346 | reserve | 0 | 5 |
| mom_return_60d | Momentum | B | 0.345 | reserve | 0 | 5 |
| liq_turnover_20d | Liquidity | B | 0.333 | reserve | 0 | 5 |
| tech_price_to_ma20 | Technical | B | 0.333 | reserve | 0 | 5 |
| comp_size_quality | Other | B | 0.328 | reserve | 0 | 4 |
| risk_vol_of_vol | Volatility | B | 0.321 | reserve | 1 | 5 |
| alpha_toplist_amount_over_mv_20d | Other | B | 0.318 | reserve | 0 | 5 |
| north_hold_change_5d | Northbound | B | 0.309 | reserve | 0 | 1 |
| risk_vol_60d | Volatility | B | 0.306 | reserve | 0 | 5 |
| mom_return_10d | Momentum | B | 0.301 | reserve | 0 | 5 |
| rev_return_10d | Reversal | B | 0.301 | reserve | 0 | 5 |
| comp_defensive | Other | B | 0.300 | keep | 3 | 5 |

## Fold Selection Logic
| fold_id | train_start | train_end | validation_start | validation_end | test_start | test_end | qualified_count | selected_count | downgraded |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | 2014-01-01 | 2018-12-31 | 2019-01-01 | 2020-12-31 | 2021-01-01 | 2021-12-31 | 41 | 10 | False |
| fold_02_2022 | 2015-01-01 | 2019-12-31 | 2020-01-01 | 2021-12-31 | 2022-01-01 | 2022-12-31 | 41 | 10 | False |
| fold_03_2023 | 2016-01-01 | 2020-12-31 | 2021-01-01 | 2022-12-31 | 2023-01-01 | 2023-12-31 | 40 | 10 | False |
| fold_04_2024 | 2017-01-01 | 2021-12-31 | 2022-01-01 | 2023-12-31 | 2024-01-01 | 2024-12-31 | 41 | 10 | False |
| fold_05_2025 | 2018-01-01 | 2022-12-31 | 2023-01-01 | 2024-12-31 | 2025-01-01 | 2025-12-31 | 42 | 10 | False |

## Selected Core Factors By Fold
| fold_id | selection_rank | factor | validation_rank_icir | marginal_rank_icir | cluster_id |
| --- | --- | --- | --- | --- | --- |
| fold_01_2021 | 1 | alpha_toplist_hit_density_60d | -0.868 |  | cluster_02 |
| fold_01_2021 | 2 | liq_vol_cv_20d | -0.829 | -0.704 | cluster_01 |
| fold_01_2021 | 3 | liq_turnover_f_5d | -0.772 | -0.568 | cluster_02 |
| fold_01_2021 | 4 | rev_max_return_20d | -0.741 | -0.178 | cluster_03 |
| fold_01_2021 | 5 | mom_intraday_20d | -0.738 | -0.358 | cluster_02 |
| fold_01_2021 | 6 | risk_vol_5d | -0.706 | -0.192 | cluster_02 |
| fold_01_2021 | 7 | comp_rev_low_turn | 0.682 | 0.243 | cluster_02 |
| fold_01_2021 | 8 | comp_defensive | 0.640 | 0.287 | cluster_08 |
| fold_01_2021 | 9 | risk_skew_60d | -0.626 | -0.250 | cluster_04 |
| fold_01_2021 | 10 | risk_vol_20d | -0.569 | 0.267 | cluster_02 |
| fold_02_2022 | 1 | alpha_topinst_hit_density_60d | -0.804 |  | cluster_02 |
| fold_02_2022 | 2 | rev_max_return_20d | -0.756 | -0.668 | cluster_02 |
| fold_02_2022 | 3 | liq_turnover_f_5d | -0.754 | -0.625 | cluster_02 |
| fold_02_2022 | 4 | comp_rev_low_turn | 0.743 | 0.412 | cluster_02 |
| fold_02_2022 | 5 | comp_defensive | 0.730 | 0.306 | cluster_07 |
| fold_02_2022 | 6 | risk_vol_5d | -0.725 | -0.053 | cluster_02 |
| fold_02_2022 | 7 | risk_skew_60d | -0.666 | -0.249 | cluster_03 |
| fold_02_2022 | 8 | liq_vol_cv_20d | -0.660 | -0.091 | cluster_01 |
| fold_02_2022 | 9 | tech_close_to_low_20d | -0.649 | 0.201 | cluster_02 |
| fold_02_2022 | 10 | mom_high_moment_20d | -0.645 | -0.222 | cluster_02 |
| fold_03_2023 | 1 | rev_max_return_20d | -0.945 |  | cluster_02 |
| fold_03_2023 | 2 | liq_turnover_5d | -0.886 | -0.674 | cluster_02 |
| fold_03_2023 | 3 | comp_rev_low_turn | 0.856 | 0.400 | cluster_02 |
| fold_03_2023 | 4 | liq_vol_cv_20d | -0.851 | -0.171 | cluster_01 |
| fold_03_2023 | 5 | mom_high_moment_20d | -0.818 | -0.458 | cluster_02 |
| fold_03_2023 | 6 | risk_vol_10d | -0.790 | -0.068 | cluster_02 |
| fold_03_2023 | 7 | tech_close_to_low_20d | -0.785 | 0.182 | cluster_02 |
| fold_03_2023 | 8 | risk_skew_60d | -0.716 | -0.201 | cluster_02 |
| fold_03_2023 | 9 | comp_defensive | 0.650 | -0.045 | cluster_07 |
| fold_03_2023 | 10 | liq_vol_surge | -0.649 | 0.112 | cluster_03 |
| fold_04_2024 | 1 | rev_max_return_20d | -0.916 |  | cluster_03 |
| fold_04_2024 | 2 | liq_vol_cv_20d | -0.874 | -0.285 | cluster_01 |
| fold_04_2024 | 3 | liq_turnover_5d | -0.868 | -0.631 | cluster_03 |
| fold_04_2024 | 4 | mom_high_moment_20d | -0.868 | -0.606 | cluster_03 |
| fold_04_2024 | 5 | comp_rev_low_turn | 0.812 | 0.303 | cluster_03 |
| fold_04_2024 | 6 | risk_vol_10d | -0.802 | -0.096 | cluster_03 |
| fold_04_2024 | 7 | tech_close_to_low_20d | -0.730 | 0.114 | cluster_03 |
| fold_04_2024 | 8 | risk_vol_of_vol | -0.726 | -0.155 | cluster_03 |
| fold_04_2024 | 9 | comp_small_value | 0.648 | 0.437 | cluster_05 |
| fold_04_2024 | 10 | liq_log_dollar_vol | -0.566 | 0.061 | cluster_03 |
| fold_05_2025 | 1 | liq_turnover_5d | -0.757 |  | cluster_03 |
| fold_05_2025 | 2 | comp_rev_low_turn | 0.736 | 0.404 | cluster_03 |
| fold_05_2025 | 3 | comp_small_value | 0.724 | 0.556 | cluster_05 |
| fold_05_2025 | 4 | mom_high_moment_20d | -0.705 | -0.243 | cluster_03 |
| fold_05_2025 | 5 | liq_vol_cv_20d | -0.660 | -0.294 | cluster_01 |
| fold_05_2025 | 6 | risk_vol_10d | -0.616 | -0.038 | cluster_03 |
| fold_05_2025 | 7 | tech_skew_20d | -0.558 | -0.144 | cluster_03 |
| fold_05_2025 | 8 | tech_close_to_low_20d | -0.557 | 0.074 | cluster_03 |
| fold_05_2025 | 9 | alpha_toplist_hit_density_60d | -0.479 | 0.168 | cluster_02 |
| fold_05_2025 | 10 | flow_net_inflow_20d | 0.471 | 0.163 | cluster_04 |

## Final Factor Conclusions
| factor | overall_decision | selected_count | validation_pass_count | avg_validation_rank_icir | max_abs_corr |
| --- | --- | --- | --- | --- | --- |
| liq_vol_cv_20d | keep | 5 | 5 | -0.775 | 0.306 |
| alpha_topinst_hit_density_60d | reserve | 1 | 5 | -0.665 | 1.000 |
| rev_max_return_20d | keep | 4 | 5 | -0.806 | 0.527 |
| alpha_toplist_hit_density_60d | keep | 2 | 5 | -0.670 | 0.997 |
| liq_log_dollar_vol | reserve | 1 | 5 | -0.523 | 0.609 |
| comp_rev_low_turn | keep | 5 | 5 | 0.766 | 0.467 |
| risk_skew_60d | keep | 3 | 5 | -0.653 | 0.770 |
| tech_skew_20d | reserve | 1 | 5 | -0.636 | 0.707 |
| mom_intraday_20d | reserve | 1 | 5 | -0.663 | 0.736 |
| mom_high_moment_20d | keep | 4 | 5 | -0.737 | 0.726 |
| liq_turnover_f_5d | keep | 2 | 5 | -0.789 | 0.913 |
| mom_ewm_60d | reserve | 0 | 5 | -0.517 | 0.817 |
| risk_vol_10d | keep | 3 | 5 | -0.713 | 0.710 |
| tech_close_to_low_20d | keep | 4 | 5 | -0.678 | 0.628 |
| mom_weighted_120d | reserve | 0 | 5 | -0.442 | 0.634 |
| risk_vol_5d | keep | 2 | 5 | -0.706 | 0.720 |
| liq_vol_surge | reserve | 1 | 5 | -0.521 | 0.620 |
| liq_turnover_f_20d | reserve | 0 | 5 | -0.697 | 0.820 |
| mom_ewm_20d | reserve | 0 | 5 | -0.516 | 0.882 |
| tech_price_to_ma60 | reserve | 0 | 5 | -0.451 | 0.802 |
| liq_turnover_5d | keep | 3 | 5 | -0.804 | 0.917 |
| risk_vol_20d | reserve | 1 | 5 | -0.656 | 0.723 |
| flow_net_inflow_20d | reserve | 1 | 5 | 0.358 | 0.457 |
| liq_turnover_ratio_5_60 | reserve | 0 | 5 | -0.510 | 0.988 |
| liq_spread_proxy_20d | reserve | 0 | 5 | -0.603 | 0.924 |
| mom_return_20d | reserve | 0 | 5 | -0.480 | 0.869 |
| liq_turnover_10d | reserve | 0 | 5 | -0.766 | 0.949 |
| comp_small_value | keep | 2 | 5 | 0.481 | 0.315 |
| val_pb_change_60d | reserve | 0 | 5 | -0.411 | 0.533 |
| risk_range_ratio_20d | reserve | 0 | 5 | -0.597 | 0.918 |
| tech_rsi_28 | reserve | 0 | 5 | -0.432 | 0.723 |
| mom_return_60d | reserve | 0 | 5 | -0.361 | 0.563 |
| liq_turnover_20d | reserve | 0 | 5 | -0.706 | 0.846 |
| tech_price_to_ma20 | reserve | 0 | 5 | -0.465 | 0.853 |
| comp_size_quality | reserve | 0 | 4 | 0.239 | 0.832 |
| risk_vol_of_vol | reserve | 1 | 5 | -0.595 | 0.544 |
| alpha_toplist_amount_over_mv_20d | reserve | 0 | 5 | -0.359 | 0.511 |
| north_hold_change_5d | reserve | 0 | 1 | 0.105 | 0.049 |
| risk_vol_60d | reserve | 0 | 5 | -0.562 | 0.711 |
| mom_return_10d | reserve | 0 | 5 | -0.433 | 0.716 |
| rev_return_10d | reserve | 0 | 5 | 0.433 | 0.716 |
| comp_defensive | keep | 3 | 5 | 0.621 | 0.366 |

## OOS Event-Driven Performance
| scenario | window_type | cumulative_return | cagr | max_drawdown | turnover_mean | blocked_order_ratio | trade_count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| adv_floor_plus_participation | test | 33.22% | 34.65% | -10.78% | 22.57% | 10.26% | 3,316 |
| adv_floor_plus_participation | test | -1.99% | -2.07% | -25.03% | 22.06% | 11.48% | 3,214 |
| adv_floor_plus_participation | test | -2.72% | -2.83% | -17.80% | 23.61% | 11.18% | 3,296 |
| adv_floor_plus_participation | test | -8.77% | -9.12% | -36.96% | 21.11% | 13.86% | 3,089 |
| adv_floor_plus_participation | test | 30.78% | 32.09% | -18.89% | 21.02% | 13.38% | 3,102 |
| adv_floor_plus_participation | holdout | 9.11% | 90.77% | -4.09% | 25.42% | 11.32% | 478 |

## Liquidity Sensitivity
| scenario | cumulative_return | cagr | max_drawdown | turnover_mean | blocked_order_ratio |
| --- | --- | --- | --- | --- | --- |
| adv_floor_plus_participation | 51.56% | 10.55% | -36.96% | 22.07% | 12.03% |
| no_filter | 64.83% | 12.25% | -34.91% | 22.12% | 11.80% |
| adv_floor_only | 51.56% | 10.55% | -36.96% | 22.07% | 12.03% |
| bottom_20pct_filter | 29.28% | 6.84% | -32.06% | 21.95% | 11.31% |

## Topk / Rebalance / Slippage Sensitivity
| scenario | topk | rebalance_days | slippage_rate | cumulative_return | cagr | max_drawdown | blocked_order_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| topk_30 | 30 | 5 | 0.05% | 47.65% | 9.90% | -35.78% | 7.41% |
| topk_50 | 50 | 5 | 0.05% | 51.56% | 10.55% | -36.96% | 12.03% |
| topk_100 | 100 | 5 | 0.05% | 62.81% | 12.12% | -34.92% | 20.55% |
| rebalance_10d | 50 | 10 | 0.05% | 55.78% | 11.37% | -35.77% | 5.95% |
| slippage_stress | 50 | 5 | 0.10% | 32.79% | 7.55% | -37.98% | 12.43% |

## Warnings And Caveats
- Signal admission is locked to the 5d horizon because the formal strategy rebalances every 5 trading days.
- Long-short quantile returns in factor cards are diagnostics only, not tradable strategy returns.
- Industry neutralization uses the static stock_basic.industry field because a full time-varying SW membership map is not yet published in the local provider.
- Default liquidity control for the 2,000,000 RMB account uses adv20 median >= 5,000,000 RMB and participation <= 2.00%.

## Artifacts
- master_review.md
- factor_cards/
- factor_research_metrics.csv
- factor_selection_decisions.csv
- selected_core_factors_by_fold.csv
- signal_diagnostics.csv
- strategy_signal.parquet
- event_driven_report.csv
- event_driven_trades.csv
- event_driven_order_log.csv
- event_driven_daily_holdings.csv
- event_driven_corporate_actions.csv
- oos_fold_performance.csv
- sensitivity_liquidity.csv
- sensitivity_topk_rebalance.csv
- strategy_backtest_report.html
- run_metadata.json
- run_console.log
