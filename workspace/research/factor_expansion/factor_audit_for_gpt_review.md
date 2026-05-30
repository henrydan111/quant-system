# Factor Construction Audit — for GPT 5.5 Pro cross-review

**Date:** 2026-05-30.
**Scope:** every factor the system builds — the 171-factor production catalog
([catalog.py](../../../src/alpha_research/factor_library/catalog.py)), the Layer-1 operators
([operators.py](../../../src/alpha_research/factor_library/operators.py)), and the 70
factor-expansion candidates ([factor_candidates_merged.csv](factor_candidates_merged.csv)).
**Method:** self-review of construction logic + **data-grounded operator parity tests**
(Qlib vs independent pandas) + a **full-catalog degeneracy sweep**. Every defect below is
backed by the data that proves it, not by inspection alone.
**Why now:** the IS screening of the 21 formal-eligible candidates surfaced 4 factors with
*zero valid cross-sectional days*. Root-causing that exposed a **silent Qlib operator bug**
(`Count` ignores its condition) that affects the production catalog too — so a full operator-
level audit was warranted before trusting any IC number.

---

## 0. Headline findings (data-confirmed)

| # | Finding | Evidence | Affected factors | Severity |
|---|---|---|---|---|
| **F1** | **`Count(cond, N)` ignores the condition and returns `N`** (count of non-NaN obs). | `Count(Ref($close,1)>0,5)` ≡ 5.0 for every stock; `Sum(If(>0,1,0),5)` correctly returns 0–5. corr(qlib,pandas)=NaN (constant). | candidates: `liq_zero_ret_days_*`, `mom_continuous_info_252d_dir` (FIXED → `Sum(If())`); **catalog: `rev_up_down_ratio_20d` (`up_down_ratio`), `zero_trade_pct`, and the `alpha_*_hit_density_*` / event-density NaN-equality tricks** (NOT yet fixed). | **HIGH** — silently degenerate factors; `qlib_expr_guide.md` documents `Count` as working (wrong). |
| **F2** | **`IdxMax/IdxMin(x,N)` is 1-indexed from the OLDEST bar** (N = extreme is today; 1 = N-1 days ago). "Days since extreme" = `N − IdxMax`. | Direct readout: a window whose max is the latest bar returns `IdxMax=5` (for N=5); corr=−1.0 vs the "days-since (0=today)" assumption. | candidate `tech_high_breakout_age_250d` = `0 - IdxMax(...)` → **sign-inverted vs thesis** (fresh high ranks LOW). Catalog has no IdxMax/IdxMin user (operators define none). | **MEDIUM** — one candidate mis-signed (dead IS anyway); convention must be documented. |
| **F3** | `Skew`, `EMA`, `WMA`, `Std(ddof)` differ from naive pandas by a **scale/parameterization constant** (corr=1.0, rank-preserving). | parity probe: corr=1.00000, maxRelDiff up to 0.8 but monotone. | informational — `EMA`/`WMA`/`Skew`-based factors rank correctly; magnitudes are not comparable across factors without standardization. | LOW (rank-screening safe). |
| **F4** | **Production catalog factor `rev_up_down_ratio_20d` is silently dead** (constant cross-section). | degeneracy sweep: `disp=0.000, null%=0.0` over 2018 full market. | Direct consequence of F1: `up_down_ratio` operator uses `Count`. **Fix in operators.py: `Count → Sum(If(...,1,0))`.** | **HIGH** — confirmed dead production factor. |
| **F5** | **Some indicators fields are materialized as bin files but contain ~0% non-null data**, so factors that reference them are all-NaN despite passing static field-existence validation. | direct read: `fin_exp_int_exp` = 0.0% non-null (202k samples); `ebitda` = 3.3%; `ebitda_sq_q0..q3` all 100% NaN. | 3 candidates rendered unusable: `val_ebitda_ev_ttm`, `lev_net_debt_to_ebitda_ttm`, `lev_interest_coverage_ttm`. | **HIGH** — validator blind spot; new defect class. |

**Operators that PASSED parity exactly** (corr=1.0, relDiff<1e-3): `Mean`, `Sum`, `Max`,
`Min`, `Med`, `Std` (ddof=1), `Quantile`, `Delta`, `Kurt`, `Corr`, `Cov`, `Slope`. These
are trustworthy.

---

## 1. Operator parity test — method & full results

For each operator, the same formula was computed two ways over 3 stocks × ~1.5y
(2018-01→2019-06): (a) via the sanctioned `compute_factors()` → `qlib_windowed_features`
path; (b) re-derived in pandas on the identical `Ref($field,1)` input series. Parity =
Pearson corr > 0.9999 AND max relative diff < 1e-3.

| Operator | corr | maxRelDiff | Verdict | Note |
|---|---|---|---|---|
| `Mean(x,5)` | 1.00000 | 6e-8 | **PASS** | |
| `Std(x,5)` ddof=1 | 1.00000 | 6e-8 | **PASS** | qlib uses sample std (ddof=1) |
| `Sum(x,5)` | 1.00000 | 6e-8 | **PASS** | |
| `Max/Min/Med(x,5)` | 1.00000 | 0 | **PASS** | |
| `Skew(x,10)` | 1.00000 | 0.74 | PASS-rank | scale/bias-correction differs; rank-preserving |
| `Kurt(x,10)` | 1.00000 | 4e-4 | **PASS** | |
| `Quantile(x,5,0.5)` | 1.00000 | 0 | **PASS** | |
| `Delta(x,3)` | 1.00000 | 0 | **PASS** | |
| `EMA(x,5)` | 1.00000 | 0.15 | PASS-rank | span/adjust convention differs; rank-preserving |
| `WMA(x,5)` | 1.00000 | 0.80 | PASS-rank | weighting differs from naive linear; rank-preserving |
| `IdxMax/IdxMin(x,5)` | **−1.00000** | — | **CONVENTION** | 1-indexed from oldest (see F2) |
| `Count(cond,5)` | **NaN** | — | **FAIL** | ignores condition; constant N (see F1) |
| `Sum(If(cond,1,0),5)` | 1.00000 | 0 | **PASS** | the correct conditional-count idiom |
| `Corr(x,y,5)` | 1.00000 | 6e-8 | **PASS** | |
| `Cov(x,y,5)` | 1.00000 | 6e-8 | **PASS** | |
| `Slope(x,5)` | 1.00000 | 1e-5 | **PASS** | OLS slope vs time |

Reproduce: [`workspace/scripts/_audit_operator_parity.py`](../../scripts/_audit_operator_parity.py).

---

## 2. Construction logic — Layer-1 operators (self-review)

Each operator returns a Qlib expression string; PIT-safety = every `$field` inside a
`Ref(...,1)` frame (or the `ADJ_*_T1` atoms). Price basis per `qlib_expr_guide.md`:
adjusted for cross-day comparisons, raw for point-in-time ratios.

### Momentum / reversal
- `momentum(w)` = `Ref(ADJ,1)/Ref(ADJ,w+1) − 1` — w-day return ending t-1. **Logic OK.**
- `skip_momentum(skip,total)` = `Ref(ADJ,skip+1)/Ref(ADJ,total+1) − 1` — classic skip-month. OK.
- `ema_return/wma_return` — EMA/WMA of `DAILY_RET`. Rank-OK (F3 scale caveat).
- `overnight/intraday/high_moment/low_moment` — gap, intraday, H-O, L-O over window. OK.
- `return_acceleration` — mom(now) − mom(prev window). OK.
- `short_reversal(w)` = `0 − momentum`. OK.
- `max_single_return/min_single_return` = `Max/Min(DAILY_RET,w)`. OK.
- `up_down_ratio(w)` = **`Count(DAILY_RET>0,w)/w`** → **F1 BUG: constant 1.0.** Catalog
  factor `rev_up_down_ratio_20d` is degenerate. Fix: `Sum(If(DAILY_RET>0,1,0),w)/w`.

### Value
- `earnings_yield/book_yield/sales_yield` = `1/Ref($pe_ttm|$pb|$ps,1)` — inverse multiples. OK.
- `dividend_yield/ratio` = `Ref($dv_ttm|$dv_ratio,1)/100`. OK.
- `ocf_yield` = `Ref($ocfps,1)/Ref($close,1)` — same adjustment basis, raw OK.
- `bps_to_price`, `valuation_change`, `relative_valuation` — OK.

### Quality / growth (fundamental)
- `fundamental(f)` = `Ref($f,1)`; `fundamental_delta/slope/stability/ratio` — OK; rely on
  PIT-anchored indicator fields (ann_date). **`fundamental_stability` = `0 − Std(...)`** OK.

### Volatility / risk
- `rolling_vol/downside_vol/vol_of_vol/rolling_skew/rolling_kurt/tail_risk` — OK (Skew
  scale caveat F3). `max_drawdown_proxy`, `range_ratio`, `price_slope_normalized` — OK.

### Liquidity
- `avg_turnover/turnover_ratio/amihud/volume_cv/log_dollar_volume/volume_surge/`
  `volume_ratio_smoothed/turnover_skew/spread_proxy` — OK.
- **`zero_trade_pct(w)` = `Count(Ref($vol,1)<1,w)/w`** → **F1 BUG: constant.** (Not in the
  111/147 default catalog list — verify if referenced anywhere.)

### Technical
- `rsi` (Mean of gain/loss via `If`), `price_to_ma`, `ma_ratio`, `macd_dif/hist`,
  `distance_from_high/low`, `range_position`, `atr_normalized`, `bb_width`, `williams_r`,
  `price_vol_corr`, `intraday_intensity` — OK. **`obv_slope` uses `If(...,vol,−vol)` + `Sum`
  + `Slope`** — OK (no Count). RSI uses `Mean(If(...))` not Count — OK.

### Size / leverage / label
- `log_size`, `log_size_squared`, `leverage_field`, `deleverage` — OK.
- `forward_return` — the ONE allowed unshifted (label, not signal). OK.

---

## 3. Construction logic — the 70 candidates

Status + per-row expression in [factor_candidates_merged.csv](factor_candidates_merged.csv).
Round 1-3 review already fixed: PIT wrapping, `_cum_q0`→TTM `_sq`, unit scales (万元/千元/元),
DuPont dedup, true log-range Parkinson, `mom_continuous_info` sign. **This audit adds:**
- `liq_zero_ret_days_{5,10,20}d`, `mom_continuous_info_252d_dir` — **F1-fixed** to `Sum(If())`;
  re-screened, now produce real metrics (ICIR ~+0.29 / −0.07).
- `tech_high_breakout_age_250d` — **F2: sign-inverted** vs its "fresh breakout ranks high"
  thesis (`0 - IdxMax`, but IdxMax is high-when-fresh). Recommend `IdxMax(...) ` without the
  negation, OR redefine as `250 - IdxMax(...)` for "days since high". Dead IS (ICIR −0.025)
  regardless — flag for GPT.

---

## 4. Degeneracy sweep — full catalog + candidates

Computed 214 factor expressions (171 catalog incl. new-data + 70 candidates, minus the
4 stk_limit candidates that crash the whole-catalog call on index instruments) over
2018 full market via the sanctioned `compute_factors` path. Per factor: null%,
cross-sectional dispersion (fraction of dates with **any** stock-level std > 1e-12),
inf count, value range. A factor with `xs_dispersion < 0.05` cannot rank — the F1
signature. Report: [factor_audit_degeneracy.csv](factor_audit_degeneracy.csv).

**Headline: 13 flagged / 214 total (94% clean).**

| Flag | Count | Factors |
|---|---|---|
| `ALL_NAN` (and `HIGH_NULL`) | **3** | **CAND** `val_ebitda_ev_ttm`, `lev_net_debt_to_ebitda_ttm`, `lev_interest_coverage_ttm` — F5 (sparse base coverage: `ebitda` 3.3%, `fin_exp_int_exp` 0%). |
| `DEGENERATE_XS` | **1** | **CATALOG** `rev_up_down_ratio_20d` — F1 (Count bug). Production factor silently dead. |
| `HIGH_NULL` (only) | **1** | **CAND** `acc_rd_intensity_ttm` — `rd_exp` is sparse for non-tech firms (100% null in the 2018 sample; expected for most stocks). |
| `HAS_INF` | **8** | **CATALOG**: `qual_accruals` (1,319 infs — `ocfps/eps` blows up at eps≈0), `earn_surprise_eps` (72 infs); **CAND**: `grow_{revenue,total_revenue}_yoy_q` (233 each), `grow_{revenue,total_revenue}_yoy_accel_q` (303 each), `acc_inventory_sales_mismatch_yoy` (345), `acc_receivables_sales_mismatch_yoy` (173). All are ratios where the denominator (`eps`, prior-period revenue/AR/inventory) can be ≈0. Not "broken" — needs cross-sectional winsorization / clipping at screening time. |

**Recommended dispositions (each flagged):**

| Factor | Disposition | Action |
|---|---|---|
| `rev_up_down_ratio_20d` (catalog) | **Fix in production** | edit `operators.py::up_down_ratio` from `Count(cond, w)/w` → `Sum(If(cond, 1, 0), w)/w`. Re-run formal screening on it after the fix. |
| `val_ebitda_ev_ttm`, `lev_net_debt_to_ebitda_ttm` (cand) | **Drop or replace** | `ebitda` is 3.3%-covered indicator-family. Replace EBITDA with `ebit + depreciation+amort` from statement line-items (Wave-1 promotion), OR drop and rely on EBIT-yield variants which DO work (`ebit_sq_q0..q3` has 98% coverage). |
| `lev_interest_coverage_ttm` (cand) | **Replace numerator field** | `fin_exp_int_exp` is 0%-covered. Use income-statement `int_exp` directly once promoted (Wave-1 already includes `fin_exp_int_exp` — re-check on a different sample window before promoting). |
| `acc_rd_intensity_ttm` (cand) | **Keep, with sparsity flag** | R&D is structurally null for most A-share names. Useful within tech/manufacturing segments after industry-conditional null handling. |
| `qual_accruals` (catalog), `earn_surprise_eps` (catalog) | **Keep, add winsorization** | Inf-prone but conceptually valid. Add explicit `Abs(denominator) > eps` guard or clip outputs at screening time. |
| `grow_*_yoy_q`, `acc_*_mismatch_yoy` (cand) | **Keep, add winsorization** | Same as above. |

---

## 5. IS screening result of the 21 formal-eligible candidates (context)

After the F1 fix, IS (2014-2020, OOS sealed) grades: **5 B / 12 C / 4 D**. Strongest:
volatility cluster with NEGATIVE RankIC (low-vol premium) — `risk_garman_klass_20d`
(ICIR −0.57), `risk_gap_vol_20d` (−0.55), `risk_parkinson_logrange_20d` (−0.54). One clean
positive: `rev_turnover_spike_5d` (hit-rate 0.72, LS Sharpe +2.6, MDD 0.5%). Caveat: IS only,
not OOS-validated; per the project's prior `long_only_50cagr` finding, cross-sectional IC does
NOT convert directly to long-only top-K return in A-shares.

---

## 6. Questions for GPT 5.5 Pro

1. **`Count` bug (F1):** do you concur it's a real Qlib-build defect (vs our usage)? Should we
   (a) fix all catalog `Count` users to `Sum(If())` in `operators.py`, (b) add a parser lint
   banning `Count`, (c) correct `qlib_expr_guide.md`? Any `Count` semantics where it IS correct?
2. **`IdxMax` convention (F2):** confirm the 1-indexed-from-oldest reading; advise the
   canonical "days-since-high" expression and the correct sign for breakout-age.
3. **Scale operators (F3):** any factor where the `EMA`/`WMA`/`Skew` scale difference matters
   beyond ranking (e.g. when used inside a ratio or threshold, not just ranked)?
4. **F4 production fix:** edit `operators.py::up_down_ratio` to use `Sum(If(...,1,0))` — concur?
   And: should the validator add a Count-detection lint that fails any new factor using `Count`?
5. **F5 (sparse-coverage validator blind spot):** should the validator be extended to flag any
   `$field` token whose live coverage is below some threshold (e.g. <50% non-null)? This would
   have caught the 3 ALL_NAN candidates statically.
6. **Wave-1 implications of F5:** `fin_exp_int_exp` is on the GPT Wave-1 promotion list but is
   **0% non-null in the current materialized provider**. Should it be dropped from Wave-1 until
   the provider rematerializes it correctly, OR replaced with the income-statement `int_exp`
   field (which we have not yet coverage-checked)?
7. **Inf-prone ratios (§4 HAS_INF group):** preferred A-share practice — winsorize at screening
   (current default), inline `If(Abs(denom)>eps, num/denom, NaN)` guard, or both?
8. **`tech_high_breakout_age_250d` (F2 sign-inversion):** with the IdxMax convention pinned, is
   the right form `IdxMax(Ref(ADJ_HIGH,1), 250)` (high IdxMax = fresh high → ranks high), or
   `250 - IdxMax(...)` to express "days since high" (low value = recent breakout → ranks high
   after sign flip)? Both encode the same monotone signal but the rationale text needs to match.
9. **Anything mis-specified** in the §2/§3 construction logic that the parity tests would not
   catch (economic-meaning errors, wrong price basis, PIT-subtle leakage)?
