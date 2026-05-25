# Event-Driven Strategy Research Review

## Research Design
- Screening input: `E:\量化系统\workspace\research\alpha_mining\latest_backend_screening_20260401_new_data`
- Candidate scope: `43` A/B factors
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
| liq_vol_cv_20d | Liquidity | A (Graduated) | 0.729 | keep | 7 | 7 |
| liq_log_dollar_vol | Liquidity | A (Graduated) | 0.542 | reserve | 0 | 7 |
| comp_rev_low_turn | Other | A (Graduated) | 0.484 | reserve | 1 | 7 |
| mom_intraday_20d | Momentum | A (Graduated) | 0.479 | keep | 6 | 7 |
| mom_ewm_60d | Momentum | A (Graduated) | 0.461 | reserve | 0 | 7 |
| risk_skew_60d | Volatility | A (Graduated) | 0.459 | keep | 6 | 7 |
| tech_skew_20d | Technical | A (Graduated) | 0.451 | reserve | 2 | 7 |
| mom_weighted_120d | Momentum | A (Graduated) | 0.407 | reserve | 1 | 7 |
| tech_price_to_ma60 | Technical | A (Graduated) | 0.386 | reserve | 0 | 7 |
| comp_small_value | Other | A (Graduated) | 0.358 | reserve | 2 | 7 |
| val_pb_change_60d | Value | A (Graduated) | 0.357 | reserve | 1 | 7 |
| grow_profit_trend | Growth | A (Graduated) | 0.344 | reserve | 0 | 1 |
| comp_size_quality | Other | A (Graduated) | 0.341 | reserve | 0 | 6 |
| mom_return_60d | Momentum | A (Graduated) | 0.336 | reserve | 0 | 7 |
| liq_turnover_20d | Liquidity | A (Graduated) | 0.332 | reserve | 0 | 7 |
| liq_amihud_20d | Liquidity | A (Graduated) | 0.325 | reserve | 1 | 4 |
| risk_vol_of_vol | Volatility | A (Graduated) | 0.321 | keep | 4 | 7 |
| grow_rev_trend | Growth | A (Graduated) | 0.302 | reserve | 0 | 2 |
| rev_max_return_20d | Reversal | B (Strong IC) | 0.539 | keep | 7 | 7 |
| liq_vol_surge | Liquidity | B (Strong IC) | 0.474 | keep | 5 | 7 |
| liq_turnover_f_5d | Liquidity | B (Strong IC) | 0.472 | keep | 4 | 7 |
| liq_turnover_ratio_5_60 | Liquidity | B (Strong IC) | 0.466 | reserve | 1 | 7 |
| mom_high_moment_20d | Momentum | B (Strong IC) | 0.456 | reserve | 0 | 7 |
| mom_ewm_20d | Momentum | B (Strong IC) | 0.435 | reserve | 0 | 7 |
| tech_close_to_low_20d | Technical | B (Strong IC) | 0.406 | keep | 4 | 7 |
| liq_turnover_5d | Liquidity | B (Strong IC) | 0.403 | keep | 3 | 7 |
| risk_vol_10d | Volatility | B (Strong IC) | 0.402 | reserve | 0 | 7 |
| liq_turnover_f_20d | Liquidity | B (Strong IC) | 0.393 | reserve | 0 | 7 |
| liq_vol_ratio_ma5 | Liquidity | B (Strong IC) | 0.387 | keep | 5 | 7 |
| risk_vol_5d | Volatility | B (Strong IC) | 0.375 | keep | 6 | 7 |
| liq_turnover_10d | Liquidity | B (Strong IC) | 0.373 | reserve | 0 | 7 |
| risk_vol_20d | Volatility | B (Strong IC) | 0.372 | reserve | 0 | 7 |
| mom_return_20d | Momentum | B (Strong IC) | 0.371 | reserve | 0 | 7 |
| tech_rsi_28 | Technical | B (Strong IC) | 0.370 | reserve | 0 | 7 |
| liq_spread_proxy_20d | Liquidity | B (Strong IC) | 0.367 | reserve | 0 | 7 |
| risk_range_ratio_20d | Volatility | B (Strong IC) | 0.361 | reserve | 0 | 7 |
| flow_net_inflow_20d | Capital Flow | B (Strong IC) | 0.357 | reserve | 0 | 7 |
| tech_price_to_ma20 | Technical | B (Strong IC) | 0.335 | reserve | 0 | 7 |
| tech_ma5_ma20_ratio | Technical | B (Strong IC) | 0.322 | reserve | 0 | 7 |
| north_hold_change_5d | Northbound | B (Strong IC) | 0.309 | reserve | 0 | 3 |
| comp_defensive | Other | B (Strong IC) | 0.303 | keep | 4 | 7 |
| mom_return_10d | Momentum | B (Strong IC) | 0.302 | reserve | 0 | 7 |
| rev_return_10d | Reversal | B (Strong IC) | 0.302 | reserve | 0 | 7 |

## Fold Selection Logic
| fold_id | train_start | train_end | validation_start | validation_end | test_start | test_end | qualified_count | selected_count | downgraded |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | 2012-01-01 | 2016-12-31 | 2017-01-01 | 2018-12-31 | 2019-01-01 | 2019-12-31 | 43 | 10 | False |
| fold_02_2020 | 2013-01-01 | 2017-12-31 | 2018-01-01 | 2019-12-31 | 2020-01-01 | 2020-12-31 | 42 | 10 | False |
| fold_03_2021 | 2014-01-01 | 2018-12-31 | 2019-01-01 | 2020-12-31 | 2021-01-01 | 2021-12-31 | 40 | 10 | False |
| fold_04_2022 | 2015-01-01 | 2019-12-31 | 2020-01-01 | 2021-12-31 | 2022-01-01 | 2022-12-31 | 40 | 10 | False |
| fold_05_2023 | 2016-01-01 | 2020-12-31 | 2021-01-01 | 2022-12-31 | 2023-01-01 | 2023-12-31 | 38 | 10 | False |
| fold_06_2024 | 2017-01-01 | 2021-12-31 | 2022-01-01 | 2023-12-31 | 2024-01-01 | 2024-12-31 | 39 | 10 | False |
| fold_07_2025 | 2018-01-01 | 2022-12-31 | 2023-01-01 | 2024-12-31 | 2025-01-01 | 2025-12-31 | 40 | 10 | False |

## Selected Core Factors By Fold
| fold_id | selection_rank | factor | validation_rank_icir | marginal_rank_icir | cluster_id |
| --- | --- | --- | --- | --- | --- |
| fold_01_2019 | 1 | liq_vol_cv_20d | -0.927 |  | cluster_01 |
| fold_01_2019 | 2 | rev_max_return_20d | -0.827 | -0.575 | cluster_02 |
| fold_01_2019 | 3 | comp_defensive | 0.742 | 0.331 | cluster_02 |
| fold_01_2019 | 4 | risk_skew_60d | -0.713 | -0.173 | cluster_03 |
| fold_01_2019 | 5 | mom_intraday_20d | -0.672 | -0.473 | cluster_02 |
| fold_01_2019 | 6 | liq_vol_surge | -0.665 | -0.206 | cluster_09 |
| fold_01_2019 | 7 | liq_turnover_f_5d | -0.654 | -0.283 | cluster_02 |
| fold_01_2019 | 8 | comp_rev_low_turn | 0.646 | 0.182 | cluster_02 |
| fold_01_2019 | 9 | risk_vol_of_vol | -0.575 | -0.136 | cluster_07 |
| fold_01_2019 | 10 | liq_amihud_20d | 0.560 | 0.208 | cluster_02 |
| fold_02_2020 | 1 | liq_vol_cv_20d | -0.986 |  | cluster_01 |
| fold_02_2020 | 2 | liq_vol_surge | -0.984 | -0.796 | cluster_08 |
| fold_02_2020 | 3 | mom_intraday_20d | -0.928 | -0.743 | cluster_02 |
| fold_02_2020 | 4 | rev_max_return_20d | -0.881 | -0.245 | cluster_02 |
| fold_02_2020 | 5 | liq_turnover_f_5d | -0.799 | -0.376 | cluster_02 |
| fold_02_2020 | 6 | liq_vol_ratio_ma5 | -0.748 | -0.432 | cluster_09 |
| fold_02_2020 | 7 | risk_skew_60d | -0.705 | -0.244 | cluster_04 |
| fold_02_2020 | 8 | tech_close_to_low_20d | -0.664 | 0.412 | cluster_02 |
| fold_02_2020 | 9 | comp_defensive | 0.593 | 0.252 | cluster_02 |
| fold_02_2020 | 10 | risk_vol_5d | -0.582 | 0.251 | cluster_02 |
| fold_03_2021 | 1 | liq_vol_cv_20d | -0.961 |  | cluster_01 |
| fold_03_2021 | 2 | liq_turnover_f_5d | -0.839 | -0.682 | cluster_02 |
| fold_03_2021 | 3 | rev_max_return_20d | -0.799 | -0.152 | cluster_02 |
| fold_03_2021 | 4 | mom_intraday_20d | -0.788 | -0.372 | cluster_02 |
| fold_03_2021 | 5 | risk_vol_5d | -0.746 | -0.096 | cluster_02 |
| fold_03_2021 | 6 | tech_close_to_low_20d | -0.679 | 0.424 | cluster_02 |
| fold_03_2021 | 7 | comp_defensive | 0.670 | 0.297 | cluster_02 |
| fold_03_2021 | 8 | liq_vol_ratio_ma5 | -0.661 | -0.380 | cluster_08 |
| fold_03_2021 | 9 | liq_turnover_ratio_5_60 | -0.632 | 0.221 | cluster_07 |
| fold_03_2021 | 10 | risk_skew_60d | -0.610 | -0.206 | cluster_03 |
| fold_04_2022 | 1 | liq_turnover_f_5d | -0.807 |  | cluster_02 |
| fold_04_2022 | 2 | rev_max_return_20d | -0.795 | -0.362 | cluster_02 |
| fold_04_2022 | 3 | risk_vol_5d | -0.761 | -0.168 | cluster_02 |
| fold_04_2022 | 4 | liq_vol_cv_20d | -0.747 | -0.198 | cluster_01 |
| fold_04_2022 | 5 | tech_close_to_low_20d | -0.664 | 0.109 | cluster_02 |
| fold_04_2022 | 6 | risk_skew_60d | -0.645 | -0.165 | cluster_03 |
| fold_04_2022 | 7 | risk_vol_of_vol | -0.644 | -0.203 | cluster_06 |
| fold_04_2022 | 8 | tech_skew_20d | -0.522 | 0.053 | cluster_04 |
| fold_04_2022 | 9 | val_pb_change_60d | -0.472 | -0.084 | cluster_02 |
| fold_04_2022 | 10 | liq_vol_ratio_ma5 | -0.462 | -0.180 | cluster_08 |
| fold_05_2023 | 1 | rev_max_return_20d | -0.991 |  | cluster_02 |
| fold_05_2023 | 2 | liq_turnover_5d | -0.945 | -0.737 | cluster_02 |
| fold_05_2023 | 3 | liq_vol_cv_20d | -0.914 | -0.257 | cluster_01 |
| fold_05_2023 | 4 | mom_intraday_20d | -0.813 | -0.318 | cluster_02 |
| fold_05_2023 | 5 | risk_vol_5d | -0.805 | -0.221 | cluster_02 |
| fold_05_2023 | 6 | liq_vol_surge | -0.736 | 0.235 | cluster_06 |
| fold_05_2023 | 7 | risk_vol_of_vol | -0.717 | -0.316 | cluster_05 |
| fold_05_2023 | 8 | risk_skew_60d | -0.713 | -0.160 | cluster_03 |
| fold_05_2023 | 9 | mom_weighted_120d | -0.597 | -0.094 | cluster_02 |
| fold_05_2023 | 10 | liq_vol_ratio_ma5 | -0.531 | -0.145 | cluster_07 |
| fold_06_2024 | 1 | rev_max_return_20d | -0.965 |  | cluster_02 |
| fold_06_2024 | 2 | liq_vol_cv_20d | -0.945 | -0.359 | cluster_01 |
| fold_06_2024 | 3 | liq_turnover_5d | -0.940 | -0.722 | cluster_02 |
| fold_06_2024 | 4 | mom_intraday_20d | -0.773 | -0.264 | cluster_03 |
| fold_06_2024 | 5 | risk_vol_5d | -0.770 | -0.239 | cluster_02 |
| fold_06_2024 | 6 | risk_vol_of_vol | -0.736 | -0.325 | cluster_06 |
| fold_06_2024 | 7 | risk_skew_60d | -0.730 | -0.200 | cluster_04 |
| fold_06_2024 | 8 | comp_defensive | 0.675 | 0.120 | cluster_02 |
| fold_06_2024 | 9 | comp_small_value | 0.648 | 0.472 | cluster_05 |
| fold_06_2024 | 10 | liq_vol_surge | -0.643 | 0.097 | cluster_07 |
| fold_07_2025 | 1 | liq_turnover_5d | -0.833 |  | cluster_02 |
| fold_07_2025 | 2 | liq_vol_cv_20d | -0.726 | -0.444 | cluster_01 |
| fold_07_2025 | 3 | comp_small_value | 0.724 | 0.565 | cluster_06 |
| fold_07_2025 | 4 | rev_max_return_20d | -0.699 | -0.061 | cluster_02 |
| fold_07_2025 | 5 | liq_vol_surge | -0.616 | -0.064 | cluster_08 |
| fold_07_2025 | 6 | mom_intraday_20d | -0.610 | -0.228 | cluster_03 |
| fold_07_2025 | 7 | risk_vol_5d | -0.610 | -0.175 | cluster_02 |
| fold_07_2025 | 8 | tech_close_to_low_20d | -0.559 | 0.097 | cluster_03 |
| fold_07_2025 | 9 | tech_skew_20d | -0.540 | -0.092 | cluster_05 |
| fold_07_2025 | 10 | liq_vol_ratio_ma5 | -0.532 | -0.321 | cluster_09 |

## Final Factor Conclusions
| factor | overall_decision | selected_count | validation_pass_count | avg_validation_rank_icir | max_abs_corr |
| --- | --- | --- | --- | --- | --- |
| liq_vol_cv_20d | keep | 7 | 7 | -0.886 | 0.482 |
| liq_log_dollar_vol | reserve | 0 | 7 | -0.569 | 0.678 |
| comp_rev_low_turn | reserve | 1 | 7 | 0.746 | 0.668 |
| mom_intraday_20d | keep | 6 | 7 | -0.748 | 0.635 |
| mom_ewm_60d | reserve | 0 | 7 | -0.555 | 0.696 |
| risk_skew_60d | keep | 6 | 7 | -0.663 | 0.444 |
| tech_skew_20d | reserve | 2 | 7 | -0.644 | 0.636 |
| mom_weighted_120d | reserve | 1 | 7 | -0.463 | 0.746 |
| tech_price_to_ma60 | reserve | 0 | 7 | -0.445 | 0.781 |
| comp_small_value | reserve | 2 | 7 | 0.450 | 0.282 |
| val_pb_change_60d | reserve | 1 | 7 | -0.408 | 0.747 |
| grow_profit_trend | reserve | 0 | 1 | -0.036 | 0.018 |
| comp_size_quality | reserve | 0 | 6 | 0.267 | 0.663 |
| mom_return_60d | reserve | 0 | 7 | -0.351 | 0.886 |
| liq_turnover_20d | reserve | 0 | 7 | -0.685 | 0.910 |
| liq_amihud_20d | reserve | 1 | 4 | 0.248 | 0.383 |
| risk_vol_of_vol | keep | 4 | 7 | -0.592 | 0.403 |
| grow_rev_trend | reserve | 0 | 2 | -0.044 | 0.022 |
| rev_max_return_20d | keep | 7 | 7 | -0.851 | 0.562 |
| liq_vol_surge | keep | 5 | 7 | -0.674 | 0.977 |
| liq_turnover_f_5d | keep | 4 | 7 | -0.819 | 0.906 |
| liq_turnover_ratio_5_60 | reserve | 1 | 7 | -0.659 | 0.980 |
| mom_high_moment_20d | reserve | 0 | 7 | -0.762 | 0.761 |
| mom_ewm_20d | reserve | 0 | 7 | -0.582 | 0.698 |
| tech_close_to_low_20d | keep | 4 | 7 | -0.656 | 0.616 |
| liq_turnover_5d | keep | 3 | 7 | -0.812 | 0.924 |
| risk_vol_10d | reserve | 0 | 7 | -0.695 | 0.784 |
| liq_turnover_f_20d | reserve | 0 | 7 | -0.693 | 0.897 |
| liq_vol_ratio_ma5 | keep | 5 | 7 | -0.576 | 0.448 |
| risk_vol_5d | keep | 6 | 7 | -0.677 | 0.599 |
| liq_turnover_10d | reserve | 0 | 7 | -0.758 | 0.966 |
| risk_vol_20d | reserve | 0 | 7 | -0.638 | 0.861 |
| mom_return_20d | reserve | 0 | 7 | -0.509 | 0.774 |
| tech_rsi_28 | reserve | 0 | 7 | -0.485 | 0.674 |
| liq_spread_proxy_20d | reserve | 0 | 7 | -0.604 | 0.737 |
| risk_range_ratio_20d | reserve | 0 | 7 | -0.597 | 0.733 |
| flow_net_inflow_20d | reserve | 0 | 7 | 0.349 | 0.318 |
| tech_price_to_ma20 | reserve | 0 | 7 | -0.457 | 0.764 |
| tech_ma5_ma20_ratio | reserve | 0 | 7 | -0.470 | 0.734 |
| north_hold_change_5d | reserve | 0 | 3 | 0.164 | 0.030 |
| comp_defensive | keep | 4 | 7 | 0.652 | 0.614 |
| mom_return_10d | reserve | 0 | 7 | -0.424 | 0.675 |
| rev_return_10d | reserve | 0 | 7 | 0.424 | 0.675 |

## OOS Event-Driven Performance
| scenario | window_type | cumulative_return | cagr | max_drawdown | turnover_mean | blocked_order_ratio | trade_count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| adv_floor_plus_participation | test | 32.25% | 33.46% | -15.27% | 22.40% | 9.42% | 3,318 |
| adv_floor_plus_participation | test | 4.05% | 4.21% | -14.71% | 30.32% | 5.97% | 3,972 |
| adv_floor_plus_participation | test | 13.61% | 14.15% | -12.13% | 30.27% | 5.30% | 4,003 |
| adv_floor_plus_participation | test | -13.18% | -13.69% | -27.77% | 28.79% | 7.19% | 3,784 |
| adv_floor_plus_participation | test | -3.87% | -4.02% | -18.24% | 29.66% | 6.12% | 3,894 |
| adv_floor_plus_participation | test | -8.65% | -8.99% | -38.42% | 24.04% | 12.30% | 3,314 |
| adv_floor_plus_participation | test | 30.88% | 32.20% | -18.03% | 31.03% | 5.94% | 4,041 |
| adv_floor_plus_participation | holdout | 6.12% | 55.34% | -5.45% | 30.49% | 6.31% | 549 |

## Liquidity Sensitivity
_No rows._

## Topk / Rebalance / Slippage Sensitivity
_No rows._

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
