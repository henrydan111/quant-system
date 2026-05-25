# Strategy Gap Attribution

## Benchmark Audit
- Benchmark: `000001.SH`
- Audit passed: `True`
- Covered dates: `2008-01-02` to `2026-02-27`
- Missing trade days vs calendar: `0`
- Duplicate trade_date rows: `0`

## Baseline B0 Summary
- Stitched total return: `56.03%`
- Stitched benchmark total return: `59.14%`
- Stitched relative excess return: `-1.95%`
- Positive-excess test folds: `4` / `7`
- Holdout relative excess return: `1.18%`
- Worst-fold max drawdown: `-38.21%`
- Turnover and blocked-order ratio are kept as diagnostics, not promotion gates.

## Year / Regime Diagnostics
| fold_id | window_type | cumulative_return | benchmark_total_return | relative_excess_return | max_drawdown | turnover_mean | blocked_order_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| holdout | holdout | 6.12% | 4.89% | 0.012 | -5.45% | 30.49% | 6.31% |
| fold_01_2019 | test | 32.29% | 22.30% | 0.082 | -15.27% | 22.36% | 9.44% |
| fold_02_2020 | test | 4.11% | 13.87% | -0.086 | -14.73% | 30.32% | 6.04% |
| fold_03_2021 | test | 13.61% | 4.80% | 0.084 | -12.13% | 30.27% | 5.30% |
| fold_04_2022 | test | -12.96% | -15.13% | 0.026 | -27.77% | 28.78% | 7.07% |
| fold_05_2023 | test | -3.87% | -3.70% | -0.002 | -18.24% | 29.66% | 6.12% |
| fold_06_2024 | test | -8.88% | 12.67% | -0.191 | -38.21% | 24.03% | 12.33% |
| fold_07_2025 | test | 30.78% | 18.41% | 0.104 | -18.03% | 31.00% | 6.08% |

## Portfolio Expression Diagnostics
| fold_id | avg_selected | avg_score_range | equal_hhi | tiered_hhi | score_prop_hhi | equal_top10_share | tiered_top10_share | score_prop_top10_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01_2019 | 50.000 | 0.114 | 0.020 | 0.021 | 0.026 | 0.200 | 0.258 | 0.300 |
| fold_02_2020 | 50.000 | 0.105 | 0.020 | 0.021 | 0.026 | 0.200 | 0.258 | 0.300 |
| fold_03_2021 | 50.000 | 0.100 | 0.020 | 0.021 | 0.026 | 0.200 | 0.258 | 0.300 |
| fold_04_2022 | 50.000 | 0.102 | 0.020 | 0.021 | 0.026 | 0.200 | 0.258 | 0.300 |
| fold_05_2023 | 50.000 | 0.098 | 0.020 | 0.021 | 0.026 | 0.200 | 0.258 | 0.300 |
| fold_06_2024 | 50.000 | 0.095 | 0.020 | 0.021 | 0.026 | 0.200 | 0.258 | 0.300 |
| fold_07_2025 | 50.000 | 0.090 | 0.020 | 0.021 | 0.026 | 0.200 | 0.258 | 0.300 |
| holdout | 50.000 | 0.098 | 0.020 | 0.021 | 0.026 | 0.200 | 0.258 | 0.300 |

## Repeated Factor Mix
| factor | category | selected_folds | mean_abs_val_icir |
| --- | --- | --- | --- |
| liq_vol_cv_20d | Liquidity | 7 | 0.886 |
| rev_max_return_20d | Reversal | 7 | 0.851 |
| mom_intraday_20d | Momentum | 6 | 0.748 |
| risk_vol_5d | Volatility | 6 | 0.677 |
| risk_skew_60d | Volatility | 6 | 0.663 |
| liq_vol_surge | Liquidity | 5 | 0.674 |
| liq_vol_ratio_ma5 | Liquidity | 5 | 0.576 |
| liq_turnover_f_5d | Liquidity | 4 | 0.819 |
| tech_close_to_low_20d | Technical | 4 | 0.656 |
| comp_defensive | Other | 4 | 0.652 |
| risk_vol_of_vol | Volatility | 4 | 0.592 |
| liq_turnover_5d | Liquidity | 3 | 0.812 |

## Slow-Signal Mismatch Diagnostic
| factor | category | best_decay_horizon | selected_folds | is_slow_signal |
| --- | --- | --- | --- | --- |
| rev_max_return_20d | Reversal | 60 | 7 | True |
| liq_vol_cv_20d | Liquidity | 10 | 7 | False |
| mom_intraday_20d | Momentum | 60 | 6 | True |
| risk_skew_60d | Volatility | 60 | 6 | True |
| risk_vol_5d | Volatility | 60 | 6 | True |
| liq_vol_surge | Liquidity | 60 | 5 | True |
| liq_vol_ratio_ma5 | Liquidity | 20 | 5 | False |
| comp_defensive | Other | 60 | 4 | True |
| liq_turnover_f_5d | Liquidity | 60 | 4 | True |
| risk_vol_of_vol | Volatility | 60 | 4 | True |
| tech_close_to_low_20d | Technical | 60 | 4 | True |
| liq_turnover_5d | Liquidity | 60 | 3 | True |

## Benchmark-Relative Exposure
| avg_portfolio_sh_weight | avg_portfolio_sz_weight | avg_portfolio_market_cap | avg_market_market_cap | avg_portfolio_adv20 | avg_market_adv20 | avg_market_sh_share_by_count |
| --- | --- | --- | --- | --- | --- | --- |
| 0.481 | 0.507 | 1520780.957 | 1863418.724 | 98470821.580 | 361752002.034 | 0.423 |

- Local monthly index_weights snapshots currently cover CSI families but do not provide a direct 000001.SH constituent-weight history, so this exposure file is a broad style / exchange diagnostic instead of an exact constituent-level attribution.

## Key Findings
- Equal-weight `top50` holdings visibly flatten score differences. The expression diagnostics compare the same selected names under equal, tiered, and score-proportional weights so this effect is easy to review.
- The core book is concentrated in a small set of liquidity / short-horizon reversal / volatility ideas, so many high-ICIR factors are overlapping instead of additive.
- A visible share of repeatedly selected factors have `best_decay_horizon > 20`, which suggests a mismatch between slow signals and the current 5-day rebalance rhythm.
- Execution friction is meaningful, but it is treated here as implementation context rather than a hard factor-quality gate.
- Relative to the SSE Composite benchmark, the current all-market portfolio still carries a large SZ allocation and only a rough broad-style exposure match because local 000001.SH constituent weights are not available.
