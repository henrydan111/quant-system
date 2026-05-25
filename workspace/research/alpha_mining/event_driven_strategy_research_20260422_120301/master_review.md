# Event-Driven Strategy Research Review

## Research Design
- Screening input: `E:\量化系统\workspace\research\alpha_mining\revalidation_screening_20260421`
- Candidate scope: `39` A/B factors
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
| rev_max_return_20d | Reversal | B | 0.535 | keep | 5 | 5 |
| liq_log_dollar_vol | Liquidity | B | 0.507 | reserve | 0 | 5 |
| comp_rev_low_turn | Other | B | 0.479 | keep | 3 | 5 |
| risk_skew_60d | Volatility | B | 0.468 | keep | 5 | 5 |
| tech_skew_20d | Technical | B | 0.456 | keep | 2 | 5 |
| mom_intraday_20d | Momentum | B | 0.454 | keep | 2 | 5 |
| mom_high_moment_20d | Momentum | B | 0.451 | reserve | 0 | 5 |
| liq_turnover_f_5d | Liquidity | B | 0.438 | keep | 2 | 5 |
| mom_ewm_60d | Momentum | B | 0.434 | reserve | 0 | 5 |
| risk_vol_10d | Volatility | B | 0.413 | reserve | 0 | 5 |
| tech_close_to_low_20d | Technical | B | 0.407 | keep | 3 | 5 |
| mom_weighted_120d | Momentum | B | 0.393 | reserve | 1 | 5 |
| risk_vol_5d | Volatility | B | 0.391 | keep | 5 | 5 |
| liq_vol_surge | Liquidity | B | 0.389 | keep | 3 | 5 |
| liq_turnover_f_20d | Liquidity | B | 0.385 | reserve | 0 | 5 |
| mom_ewm_20d | Momentum | B | 0.385 | reserve | 0 | 5 |
| tech_price_to_ma60 | Technical | B | 0.383 | reserve | 0 | 5 |
| liq_turnover_5d | Liquidity | B | 0.383 | keep | 3 | 5 |
| risk_vol_20d | Volatility | B | 0.381 | reserve | 0 | 5 |
| flow_net_inflow_20d | Capital Flow | B | 0.378 | reserve | 0 | 5 |
| liq_turnover_ratio_5_60 | Liquidity | B | 0.377 | reserve | 1 | 5 |
| liq_spread_proxy_20d | Liquidity | B | 0.367 | reserve | 0 | 5 |
| mom_return_20d | Momentum | B | 0.366 | reserve | 0 | 5 |
| liq_turnover_10d | Liquidity | B | 0.366 | reserve | 0 | 5 |
| comp_small_value | Other | B | 0.362 | keep | 3 | 5 |
| val_pb_change_60d | Value | B | 0.361 | reserve | 1 | 5 |
| risk_range_ratio_20d | Volatility | B | 0.361 | reserve | 0 | 5 |
| tech_rsi_28 | Technical | B | 0.346 | reserve | 0 | 5 |
| mom_return_60d | Momentum | B | 0.345 | reserve | 0 | 5 |
| liq_turnover_20d | Liquidity | B | 0.333 | reserve | 0 | 5 |
| tech_price_to_ma20 | Technical | B | 0.333 | reserve | 0 | 5 |
| comp_size_quality | Other | B | 0.328 | reserve | 0 | 4 |
| risk_vol_of_vol | Volatility | B | 0.321 | keep | 3 | 5 |
| north_hold_change_5d | Northbound | B | 0.309 | reserve | 0 | 1 |
| risk_vol_60d | Volatility | B | 0.306 | reserve | 1 | 5 |
| mom_return_10d | Momentum | B | 0.301 | reserve | 0 | 5 |
| rev_return_10d | Reversal | B | 0.301 | reserve | 0 | 5 |
| comp_defensive | Other | B | 0.300 | keep | 2 | 5 |

## Fold Selection Logic
| fold_id | train_start | train_end | validation_start | validation_end | test_start | test_end | qualified_count | selected_count | downgraded |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2021 | 2014-01-01 | 2018-12-31 | 2019-01-01 | 2020-12-31 | 2021-01-01 | 2021-12-31 | 38 | 10 | False |
| fold_02_2022 | 2015-01-01 | 2019-12-31 | 2020-01-01 | 2021-12-31 | 2022-01-01 | 2022-12-31 | 38 | 10 | False |
| fold_03_2023 | 2016-01-01 | 2020-12-31 | 2021-01-01 | 2022-12-31 | 2023-01-01 | 2023-12-31 | 37 | 10 | False |
| fold_04_2024 | 2017-01-01 | 2021-12-31 | 2022-01-01 | 2023-12-31 | 2024-01-01 | 2024-12-31 | 38 | 10 | False |
| fold_05_2025 | 2018-01-01 | 2022-12-31 | 2023-01-01 | 2024-12-31 | 2025-01-01 | 2025-12-31 | 39 | 10 | False |

## Selected Core Factors By Fold
| fold_id | selection_rank | factor | validation_rank_icir | marginal_rank_icir | cluster_id |
| --- | --- | --- | --- | --- | --- |
| fold_01_2021 | 1 | liq_vol_cv_20d | -0.829 |  | cluster_01 |
| fold_01_2021 | 2 | liq_turnover_f_5d | -0.772 | -0.638 | cluster_02 |
| fold_01_2021 | 3 | rev_max_return_20d | -0.741 | -0.194 | cluster_02 |
| fold_01_2021 | 4 | mom_intraday_20d | -0.738 | -0.336 | cluster_02 |
| fold_01_2021 | 5 | risk_vol_5d | -0.706 | -0.183 | cluster_02 |
| fold_01_2021 | 6 | comp_rev_low_turn | 0.682 | 0.228 | cluster_02 |
| fold_01_2021 | 7 | comp_defensive | 0.640 | 0.313 | cluster_02 |
| fold_01_2021 | 8 | risk_skew_60d | -0.626 | -0.247 | cluster_03 |
| fold_01_2021 | 9 | tech_skew_20d | -0.564 | -0.219 | cluster_04 |
| fold_01_2021 | 10 | liq_turnover_ratio_5_60 | -0.533 | 0.171 | cluster_05 |
| fold_02_2022 | 1 | rev_max_return_20d | -0.756 |  | cluster_02 |
| fold_02_2022 | 2 | liq_turnover_f_5d | -0.754 | -0.679 | cluster_02 |
| fold_02_2022 | 3 | comp_rev_low_turn | 0.743 | 0.398 | cluster_02 |
| fold_02_2022 | 4 | risk_vol_5d | -0.725 | -0.129 | cluster_02 |
| fold_02_2022 | 5 | risk_skew_60d | -0.666 | -0.236 | cluster_03 |
| fold_02_2022 | 6 | liq_vol_cv_20d | -0.660 | -0.101 | cluster_01 |
| fold_02_2022 | 7 | tech_close_to_low_20d | -0.649 | 0.206 | cluster_02 |
| fold_02_2022 | 8 | risk_vol_of_vol | -0.629 | -0.188 | cluster_02 |
| fold_02_2022 | 9 | val_pb_change_60d | -0.472 | -0.080 | cluster_02 |
| fold_02_2022 | 10 | liq_vol_surge | -0.381 | 0.194 | cluster_05 |
| fold_03_2023 | 1 | rev_max_return_20d | -0.945 |  | cluster_02 |
| fold_03_2023 | 2 | liq_turnover_5d | -0.886 | -0.674 | cluster_02 |
| fold_03_2023 | 3 | liq_vol_cv_20d | -0.851 | -0.189 | cluster_01 |
| fold_03_2023 | 4 | risk_vol_5d | -0.789 | -0.273 | cluster_02 |
| fold_03_2023 | 5 | tech_close_to_low_20d | -0.785 | -0.057 | cluster_04 |
| fold_03_2023 | 6 | risk_skew_60d | -0.716 | -0.185 | cluster_03 |
| fold_03_2023 | 7 | risk_vol_of_vol | -0.705 | -0.193 | cluster_02 |
| fold_03_2023 | 8 | liq_vol_surge | -0.649 | 0.231 | cluster_05 |
| fold_03_2023 | 9 | mom_weighted_120d | -0.550 | -0.092 | cluster_04 |
| fold_03_2023 | 10 | comp_small_value | 0.470 | 0.272 | cluster_07 |
| fold_04_2024 | 1 | rev_max_return_20d | -0.916 |  | cluster_02 |
| fold_04_2024 | 2 | liq_vol_cv_20d | -0.874 | -0.285 | cluster_01 |
| fold_04_2024 | 3 | liq_turnover_5d | -0.868 | -0.631 | cluster_02 |
| fold_04_2024 | 4 | risk_vol_5d | -0.732 | -0.236 | cluster_02 |
| fold_04_2024 | 5 | tech_close_to_low_20d | -0.730 | -0.079 | cluster_04 |
| fold_04_2024 | 6 | risk_vol_of_vol | -0.726 | -0.327 | cluster_02 |
| fold_04_2024 | 7 | risk_skew_60d | -0.722 | -0.190 | cluster_03 |
| fold_04_2024 | 8 | comp_small_value | 0.648 | 0.454 | cluster_07 |
| fold_04_2024 | 9 | comp_defensive | 0.647 | 0.096 | cluster_02 |
| fold_04_2024 | 10 | liq_vol_surge | -0.537 | 0.194 | cluster_05 |
| fold_05_2025 | 1 | liq_turnover_5d | -0.757 |  | cluster_02 |
| fold_05_2025 | 2 | comp_rev_low_turn | 0.736 | 0.404 | cluster_03 |
| fold_05_2025 | 3 | comp_small_value | 0.724 | 0.556 | cluster_09 |
| fold_05_2025 | 4 | rev_max_return_20d | -0.672 | -0.180 | cluster_02 |
| fold_05_2025 | 5 | liq_vol_cv_20d | -0.660 | -0.251 | cluster_01 |
| fold_05_2025 | 6 | risk_vol_5d | -0.580 | -0.070 | cluster_02 |
| fold_05_2025 | 7 | tech_skew_20d | -0.558 | -0.127 | cluster_05 |
| fold_05_2025 | 8 | mom_intraday_20d | -0.557 | -0.135 | cluster_06 |
| fold_05_2025 | 9 | risk_vol_60d | -0.543 | -0.239 | cluster_02 |
| fold_05_2025 | 10 | risk_skew_60d | -0.531 | -0.094 | cluster_04 |

## Final Factor Conclusions
| factor | overall_decision | selected_count | validation_pass_count | avg_validation_rank_icir | max_abs_corr |
| --- | --- | --- | --- | --- | --- |
| liq_vol_cv_20d | keep | 5 | 5 | -0.775 | 0.482 |
| rev_max_return_20d | keep | 5 | 5 | -0.806 | 0.540 |
| liq_log_dollar_vol | reserve | 0 | 5 | -0.523 | 0.677 |
| comp_rev_low_turn | keep | 3 | 5 | 0.766 | 0.649 |
| risk_skew_60d | keep | 5 | 5 | -0.653 | 0.444 |
| tech_skew_20d | keep | 2 | 5 | -0.636 | 0.636 |
| mom_intraday_20d | keep | 2 | 5 | -0.663 | 0.670 |
| mom_high_moment_20d | reserve | 0 | 5 | -0.737 | 0.761 |
| liq_turnover_f_5d | keep | 2 | 5 | -0.789 | 0.906 |
| mom_ewm_60d | reserve | 0 | 5 | -0.517 | 0.755 |
| risk_vol_10d | reserve | 0 | 5 | -0.713 | 0.784 |
| tech_close_to_low_20d | keep | 3 | 5 | -0.678 | 0.630 |
| mom_weighted_120d | reserve | 1 | 5 | -0.442 | 0.757 |
| risk_vol_5d | keep | 5 | 5 | -0.706 | 0.599 |
| liq_vol_surge | keep | 3 | 5 | -0.521 | 0.977 |
| liq_turnover_f_20d | reserve | 0 | 5 | -0.697 | 0.891 |
| mom_ewm_20d | reserve | 0 | 5 | -0.516 | 0.821 |
| tech_price_to_ma60 | reserve | 0 | 5 | -0.451 | 0.719 |
| liq_turnover_5d | keep | 3 | 5 | -0.804 | 0.912 |
| risk_vol_20d | reserve | 0 | 5 | -0.656 | 0.861 |
| flow_net_inflow_20d | reserve | 0 | 5 | 0.358 | 0.266 |
| liq_turnover_ratio_5_60 | reserve | 1 | 5 | -0.510 | 0.979 |
| liq_spread_proxy_20d | reserve | 0 | 5 | -0.603 | 0.736 |
| mom_return_20d | reserve | 0 | 5 | -0.480 | 0.798 |
| liq_turnover_10d | reserve | 0 | 5 | -0.766 | 0.966 |
| comp_small_value | keep | 3 | 5 | 0.481 | 0.283 |
| val_pb_change_60d | reserve | 1 | 5 | -0.411 | 0.758 |
| risk_range_ratio_20d | reserve | 0 | 5 | -0.597 | 0.733 |
| tech_rsi_28 | reserve | 0 | 5 | -0.432 | 0.632 |
| mom_return_60d | reserve | 0 | 5 | -0.361 | 0.886 |
| liq_turnover_20d | reserve | 0 | 5 | -0.706 | 0.910 |
| tech_price_to_ma20 | reserve | 0 | 5 | -0.465 | 0.786 |
| comp_size_quality | reserve | 0 | 4 | 0.239 | 0.662 |
| risk_vol_of_vol | keep | 3 | 5 | -0.595 | 0.682 |
| north_hold_change_5d | reserve | 0 | 1 | 0.105 | 0.021 |
| risk_vol_60d | reserve | 1 | 5 | -0.562 | 0.676 |
| mom_return_10d | reserve | 0 | 5 | -0.433 | 0.683 |
| rev_return_10d | reserve | 0 | 5 | 0.433 | 0.683 |
| comp_defensive | keep | 2 | 5 | 0.621 | 0.613 |

## OOS Event-Driven Performance
| scenario | window_type | cumulative_return | cagr | max_drawdown | turnover_mean | blocked_order_ratio | trade_count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| adv_floor_plus_participation | test | 42.90% | 44.81% | -9.16% | 25.37% | 7.95% | 3,601 |
| adv_floor_plus_participation | test | -6.35% | -6.60% | -26.11% | 24.67% | 10.32% | 3,415 |
| adv_floor_plus_participation | test | -2.86% | -2.98% | -18.27% | 21.94% | 11.89% | 3,150 |
| adv_floor_plus_participation | test | -0.29% | -0.30% | -34.57% | 24.94% | 10.82% | 3,428 |
| adv_floor_plus_participation | test | 37.85% | 39.50% | -16.85% | 21.49% | 13.35% | 3,128 |
| adv_floor_plus_participation | holdout | 9.50% | 95.96% | -4.42% | 26.46% | 8.03% | 504 |

## Liquidity Sensitivity
| scenario | cumulative_return | cagr | max_drawdown | turnover_mean | blocked_order_ratio |
| --- | --- | --- | --- | --- | --- |
| adv_floor_plus_participation | 78.69% | 14.88% | -34.57% | 23.68% | 10.87% |
| no_filter | 85.75% | 15.67% | -33.47% | 23.66% | 10.38% |
| adv_floor_only | 78.69% | 14.88% | -34.57% | 23.68% | 10.87% |
| bottom_20pct_filter | 40.47% | 8.90% | -34.50% | 23.47% | 10.11% |

## Topk / Rebalance / Slippage Sensitivity
| scenario | topk | rebalance_days | slippage_rate | cumulative_return | cagr | max_drawdown | blocked_order_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| topk_30 | 30 | 5 | 0.05% | 66.04% | 12.62% | -37.13% | 6.86% |
| topk_50 | 50 | 5 | 0.05% | 78.69% | 14.88% | -34.57% | 10.87% |
| topk_100 | 100 | 5 | 0.05% | 89.13% | 15.80% | -34.04% | 18.62% |
| rebalance_10d | 50 | 10 | 0.05% | 99.35% | 17.22% | -30.47% | 5.15% |
| slippage_stress | 50 | 5 | 0.10% | 54.55% | 11.48% | -36.07% | 10.97% |

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
