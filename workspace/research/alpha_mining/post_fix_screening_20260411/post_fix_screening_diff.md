# Factor Library Pre/Post Leakage Fix Diff Report

- **Baseline run**: `workspace\research\alpha_mining\latest_backend_screening_20260401_new_data`
- **Post-fix run**: `workspace\research\alpha_mining\post_fix_screening_20260411`
- **Factors compared**: 149
- **Factors flagged**: 31

## 1. Grade migration matrix (pre rows → post columns)

|         |   A |   B |   C |   D |   missing |
|:--------|----:|----:|----:|----:|----------:|
| A       |   1 |  15 |   2 |   0 |         0 |
| B       |   0 |  22 |   3 |   0 |         0 |
| C       |   0 |   0 |  70 |   2 |         0 |
| D       |   0 |   0 |   0 |  34 |         0 |
| missing |   0 |   0 |   0 |   0 |         0 |

## 2. Grade counts pre vs post

|    |   pre |   post |   delta |
|:---|------:|-------:|--------:|
| A  |    18 |      1 |     -17 |
| B  |    25 |     37 |      12 |
| C  |    72 |     75 |       3 |
| D  |    34 |     36 |       2 |

## 3. Top 20 factors by |rank_icir_5d|

### 3a. Baseline top 20
| factor                  |   _icir_5d_pre | _grade_pre   |
|:------------------------|---------------:|:-------------|
| liq_vol_cv_20d          |      -0.728823 | A            |
| liq_log_dollar_vol      |      -0.542467 | A            |
| rev_max_return_20d      |      -0.539251 | B            |
| comp_rev_low_turn       |       0.484252 | A            |
| mom_intraday_20d        |      -0.479017 | A            |
| liq_vol_surge           |      -0.473809 | B            |
| liq_turnover_f_5d       |      -0.472376 | B            |
| liq_turnover_ratio_5_60 |      -0.465624 | B            |
| mom_ewm_60d             |      -0.461017 | A            |
| risk_skew_60d           |      -0.459336 | A            |
| mom_high_moment_20d     |      -0.456252 | B            |
| tech_skew_20d           |      -0.451419 | A            |
| mom_ewm_20d             |      -0.434792 | B            |
| mom_weighted_120d       |      -0.407201 | A            |
| tech_close_to_low_20d   |      -0.405796 | B            |
| liq_turnover_5d         |      -0.403009 | B            |
| risk_vol_10d            |      -0.402356 | B            |
| liq_turnover_f_20d      |      -0.39302  | B            |
| liq_vol_ratio_ma5       |      -0.387131 | B            |
| tech_price_to_ma60      |      -0.386052 | A            |

### 3b. Post-fix top 20
| factor                  |   _icir_5d_post | _grade_post   |
|:------------------------|----------------:|:--------------|
| liq_vol_cv_20d          |       -0.644943 | A             |
| liq_log_dollar_vol      |       -0.515503 | B             |
| rev_max_return_20d      |       -0.513585 | B             |
| comp_rev_low_turn       |        0.47332  | B             |
| risk_skew_60d           |       -0.469305 | B             |
| tech_skew_20d           |       -0.469048 | B             |
| mom_intraday_20d        |       -0.438248 | B             |
| mom_ewm_60d             |       -0.427534 | B             |
| liq_turnover_f_5d       |       -0.421911 | B             |
| mom_high_moment_20d     |       -0.421421 | B             |
| tech_close_to_low_20d   |       -0.398168 | B             |
| liq_vol_surge           |       -0.394727 | B             |
| mom_ewm_20d             |       -0.391452 | B             |
| liq_turnover_ratio_5_60 |       -0.386757 | B             |
| tech_price_to_ma60      |       -0.384979 | B             |
| mom_weighted_120d       |       -0.381263 | B             |
| risk_vol_10d            |       -0.380999 | B             |
| mom_return_20d          |       -0.371134 | B             |
| liq_turnover_f_20d      |       -0.366886 | B             |
| risk_vol_5d             |       -0.361235 | B             |

## 4. HIGH-RISK: factors DOWNGRADED by >=1 bucket

These factors appeared stronger pre-fix than they actually are. Downstream research that selected them is at highest risk of contamination.

| factor                 | _grade_pre   | _grade_post   |   _icir_5d_pre |   _icir_5d_post |   icir_abs_delta |
|:-----------------------|:-------------|:--------------|---------------:|----------------:|-----------------:|
| grow_rev_trend         | A            | C             |       0.30228  |      0.222955   |      -0.0793254  |
| grow_profit_trend      | A            | C             |       0.344292 |      0.258555   |      -0.0857373  |
| comp_defensive         | B            | C             |       0.302722 |      0.287427   |      -0.0152948  |
| comp_rev_low_turn      | A            | B             |       0.484252 |      0.47332    |      -0.0109319  |
| comp_small_value       | A            | B             |       0.357776 |      0.357776   |       0          |
| comp_size_quality      | A            | B             |       0.340691 |      0.340691   |       0          |
| liq_amihud_20d         | A            | B             |       0.324511 |      0.313758   |      -0.0107531  |
| liq_log_dollar_vol     | A            | B             |      -0.542467 |     -0.515503   |       0.0269637  |
| liq_turnover_20d       | A            | B             |      -0.331717 |     -0.310062   |       0.0216551  |
| liq_vol_ratio_ma5      | B            | C             |      -0.387131 |     -0.25399    |       0.133141   |
| mom_ewm_60d            | A            | B             |      -0.461017 |     -0.427534   |       0.0334829  |
| mom_intraday_20d       | A            | B             |      -0.479017 |     -0.438248   |       0.040769   |
| mom_return_60d         | A            | B             |      -0.335903 |     -0.335903   |       0          |
| mom_weighted_120d      | A            | B             |      -0.407201 |     -0.381263   |       0.0259374  |
| qual_margin_trend      | C            | D             |       0.131971 |      0.0933786  |      -0.0385922  |
| risk_skew_60d          | A            | B             |      -0.459336 |     -0.469305   |      -0.00996843 |
| risk_vol_of_vol        | A            | B             |      -0.320636 |     -0.308827   |       0.0118088  |
| tech_close_to_high_20d | C            | D             |       0.100466 |      0.00818629 |      -0.09228    |
| tech_ma5_ma20_ratio    | B            | C             |      -0.321614 |     -0.286233   |       0.0353805  |
| tech_price_to_ma60     | A            | B             |      -0.386052 |     -0.384979   |       0.00107255 |
| tech_skew_20d          | A            | B             |      -0.451419 |     -0.469048   |      -0.0176289  |
| val_pb_change_60d      | A            | B             |      -0.356841 |     -0.356841   |       0          |

## 5. Factors UPGRADED by >=1 bucket

These factors were penalized by leakage-induced noise in the baseline screening and are actually better than reported.

_None._

## 6. Large |Δrank_icir_5d| changes (no grade crossing)

| factor                 | _grade_pre   | _grade_post   |   _icir_5d_pre |   _icir_5d_post |   icir_abs_delta |   icir_rel_delta |
|:-----------------------|:-------------|:--------------|---------------:|----------------:|-----------------:|-----------------:|
| tech_rsi_6             | C            | C             |     -0.274209  |      -0.202291  |        0.0719175 |        0.262273  |
| liq_turnover_skew_20d  | C            | C             |     -0.207697  |      -0.136851  |        0.0708455 |        0.341101  |
| tech_williams_r_14     | C            | C             |     -0.104622  |      -0.156966  |       -0.0523438 |        0.500312  |
| comp_52w_position      | C            | C             |     -0.176533  |      -0.227693  |       -0.0511598 |        0.289803  |
| tech_bb_pct            | C            | C             |     -0.148382  |      -0.186126  |       -0.0377436 |        0.254367  |
| risk_mdd_proxy_60d     | D            | D             |     -0.0651725 |      -0.0942781 |       -0.0291056 |        0.446593  |
| tech_kurt_20d          | D            | D             |     -0.0599671 |      -0.0317384 |        0.0282287 |        0.470736  |
| comp_relative_strength | D            | D             |      0.0720487 |       0.0542443 |       -0.0178045 |        0.247117  |
| liq_turnover_60d       | C            | C             |     -0.249256  |      -0.238712  |        0.0105441 |        0.0423022 |

---

Report generated by `workspace/research/alpha_mining/generate_post_fix_diff.py` as part of follow-up plan #1 (factor library same-day leakage fix).