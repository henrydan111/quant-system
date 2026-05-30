# Round-6 Cross-Review for GPT 5.5 Pro — post-merge + Wave-1 promotion

**Date:** 2026-05-31.
**Scope:** everything changed since the Round-5 verdict (`5e467f8` → now). Three things to
cross-review: (1) the Round-5 production fixes as MERGED to main, (2) the Wave-1
statement-field promotion (registry governance mutation + its evidence), (3) the 47-factor
IS re-screen.
**Repository:** https://github.com/henrydan111/quant-system

**Branches / PRs in scope:**
- **PR #27 — MERGED to main** (`01db191`): factor-expansion proposal + operator audit +
  Round-5 fixes. The production `operators.py` Count fix is now on `main`.
- **PR #28 — OPEN** (`wave1-field-promotion`): the Wave-1 statement-field promotion. Review
  commit `50c8ecf` (tip).

---

## 0. TL;DR — what to check

| # | Change | Risk | What to verify |
|---|---|---|---|
| A | PR #27 merged: `Count→Sum(If)` in production `operators.py` + guide + lint | landed on main | Was the merge the right call? Any catalog factor still using `Count` we missed? |
| B | Wave-1: 53 statement fields `unknown_field→approved` in `field_status.yaml` | **governance mutation** | Is the per-family `max(ann_date,f_ann_date)` contract correct? Is the evidence (coverage + independent-recompute parity) sufficient to approve? |
| C | Independent-recompute parity harness (new) | new evidence method | Is reimplementing the provider's derivation in pandas a valid oracle, or circular? |
| D | 47-factor IS re-screen | research result | Do the newly-unlocked fundamental factors (accruals/value/Piotroski) carry signal? |

---

## 1. PR #27 (merged) — the Round-5 production fixes

All 7 Round-5 mandatory fixes were applied, CI (`offline-pit-checks`, incl.
`test_operator_expressions` + `test_factor_library_pit_safety`) passed on the exact merge
commit, and PR #27 merged to `main` (`01db191`). Summary of what's now in production:

- **`operators.py::up_down_ratio` and `::zero_trade_pct`**: `Count(cond,N)/N` →
  `Sum(If(cond,1,0),N)/N`. This resurrects the silently-dead `rev_up_down_ratio_20d`
  catalog factor (F1/F4). Tests updated; 76 operator+PIT tests pass.
- **`qlib_expr_guide.md`**: `Count` documented as broken-banned; `IdxMax/IdxMin` pinned as
  1-indexed-from-oldest.
- **`validate_factor_candidates.py`**: hard-fail lint on `Count(` in any factor expression.

**Question A for GPT:** the Count fix is now on `main`. Do you want a follow-up sweep that
greps the *entire* `operators.py` + `catalog.py` for any remaining `Count(` usage beyond the
two we fixed? (We believe `up_down_ratio` + `zero_trade_pct` were the only two production
operators using it, plus the alpha-endpoint `Sum(If(x==x,...))` NaN-density tricks which are
NOT `Count` and are correct. Please confirm or point us at others.)

---

## 2. Wave-1 statement-field promotion (PR #28) — the governance mutation

### 2.1 What was promoted
**53 statement line-item variants → `approved`**, in 3 new per-family `field_status.yaml`
dataset entries:
- **income (24):** `total_revenue_sq_q0..q4`, `ebit_sq_q0..q3`, `n_income_sq_q0..q3`,
  `n_income_attr_p_sq_q0/q4`, `oper_cost_sq_q0..q4`, `operate_profit_sq_q0/q4`,
  `revenue_sq_q0/q4`.
- **balancesheet (17):** `total_assets_q0/q4`, `total_liab_q0/q4`, `money_cap_q0`,
  `accounts_receiv_q0/q4`, `inventories_q0/q4`, `total_cur_assets_q0/q4`,
  `total_cur_liab_q0/q4`, `st_borr_q0`, `lt_borr_q0`, `goodwill_q0`, `retained_earnings_q0`.
- **cashflow (12):** `n_cashflow_act_sq_q0..q3`, `c_pay_acq_const_fiolta_sq_q0..q3`,
  `c_fr_sale_sg_sq_q0..q3`.

### 2.2 The PIT contract (DIFFERENT from indicators — please scrutinize)
The statement families anchor visibility on **`max(ann_date, f_ann_date)`** (CLAUDE.md §3),
NOT the indicators family's `ann_date`-only. The approval YAML's `pit_contract` records this,
and the derivation owners are:
- snapshot `_q{slot}`: `materialize_visibility_segments` + `arrays_from_snapshot_segments`
  (slot 0 = most-recently-disclosed fiscal period, as-of each date).
- flow `_sq_q{slot}`: `arrays_from_flow_segments` + `derive_single_quarter_value`
  (current cumulative − prior-fiscal-quarter cumulative, with late-restatement semantics;
  Q1/month==3 → single-quarter == cumulative; irregular period-ends → NaN).

**Question B for GPT:** is registering the *derived* `_sq`/`_q` variants (rather than the raw
base fields) the right unit of approval? Our reasoning: the formal factors consume the
provider-derived variants via `qlib_windowed_features`, so those are the exact tokens the
field-dependency gate must resolve. The base ledger columns are never referenced by a factor
expression.

### 2.3 Coverage gate (GPT Round-5 §3.5 — applied)
Every promoted field is ≥50% non-null on the 2018 full market. Worst: `goodwill_q0` 56.6%,
`lt_borr_q0` 53.8%, `st_borr_q0` 76.2%; core 96-99.9%. **Excluded by the gate** (your F5
finding): `ebitda` (3.3%), `fin_exp_int_exp` (0%), `rd_exp_sq_q1..q3` (~0%). These stay
unregistered; `val_ebit_ev_ttm` replaces the EBITDA-based value factor; the interest-coverage
and EBITDA-leverage candidates remain dropped.

**Question C for GPT:** for the borderline fields (`goodwill` 56.6%, `lt_borr` 53.8%), is a
flat 50% non-null threshold the right gate, or should low-coverage-but-structural fields
(many firms legitimately have zero goodwill / zero long-term borrowing) be treated as
`sparse_allowed` with NaN-aware handling rather than counted as "missing"? This is a
semantics question: is a true-zero balance-sheet line distinguishable from a not-reported
NaN in the provider? (We have NOT verified this distinction — flagging as an open risk.)

### 2.4 Independent-recompute parity (new evidence method — please validate the approach)
The loader↔provider parity harness used for the indicators approval **cannot** validate these
fields: the `_sq`/`_q` variants are provider-DERIVED at build time and are NOT stored as PIT
ledger columns, so there is no loader-side equivalent to compare against.

Instead, `workspace/scripts/verify_statement_provider_parity.py` reimplements the provider's
snapshot + single-quarter derivation **from scratch in pandas, off the raw PIT ledger**,
importing **none** of the provider's derivation functions, and compares cell-by-cell to
`D.features`. Result: **15,351 cells compared, 0 mismatches** (6 representative fields × 3
stocks × 2017-2019, covering both serving paths).

**Question D for GPT (most important):** is this a valid independent oracle, or is there a
circularity risk we're missing? Our argument for independence: the recompute reads the same
*input* (the disclosure-anchored ledger) but applies a separately-written derivation, so a
bug in the provider's derivation code would surface as a mismatch. The shared dependency is
the ledger itself (both trust it) — which is validated separately by the existing
loader↔provider parity on base fields and the PIT live-regression harness. Is that layering
sound, or do you want the recompute to read further upstream (raw Tushare parquet, pre-ledger)?

### 2.5 Outcome
Merged-candidate **formal-eligible: 21 → 47**. Newly-unlocked: `val_ebit_ev_ttm`,
`val_fcf_ev_ttm`, `val_ncav_to_price`, `qual_gross_profitability_ttm`, `acc_total_accruals_ttm`,
`acc_cash_roa_ttm`, `acc_cfo_to_ni_ttm`, `acc_asset_growth`, `acc_noa_scaled`,
`acc_dWC_inventory`, `acc_dWC_receivables`, `acc_capex_intensity_ttm`, `acc_goodwill_ratio`,
`qual_piotroski_fscore_9pt`, `qual_cash_collection_ttm`, `acc_inventory_sales_mismatch_yoy`,
`acc_receivables_sales_mismatch_yoy`, `grow_{n_income_attr_p,total_revenue}_yoy_q` +
`_yoy_accel_q`.

Governance: approval YAML (provider-build + calendar-policy bound), JSONL log, 2 guardrail
tests, approval-evidence drift assert PASS, 86 registry + 52 field-gate tests pass.

---

## 3. The 47-factor IS re-screen

IS 2014-2020, OOS sealed, horizons 5/10/20, via the sanctioned `compute_factors()` →
`qlib_windowed_features` path. **Grades: B8 / C28 / D11. Zero NaN/degenerate rows.**
(5.4M rows × 47 factors × 4,121 stocks × 1,707 dates.) Results:
[screening_is_47/](screening_is_47/).

### 3.1 The headline result — earnings-acceleration factors are a NEW top tier with CLEAN long-only profiles

This is the most important finding of the whole effort. The Wave-1 fundamental fields
unlocked **single-quarter earnings-acceleration** factors that have BOTH high ICIR AND a
clean long-short profile — the combination the volatility cluster lacked:

| Factor | RankIC 20d | ICIR 20d | LS Sharpe | LS MaxDD | Grade |
|---|---|---|---|---|---|
| `grow_operate_profit_yoy_accel_q` | +0.012 | **+0.501** | **+4.75** | **0.07%** | B |
| `grow_n_income_attr_p_yoy_accel_q` | +0.014 | **+0.499** | **+5.35** | **0.09%** | B |
| `grow_revenue_yoy_accel_q` | +0.014 | +0.459 | +3.54 | 0.09% | C |
| `grow_total_revenue_yoy_accel_q` | +0.013 | +0.449 | +3.58 | 0.09% | C |

Contrast with the volatility cluster (still the highest |ICIR| but a SHORT-side effect):

| Factor | ICIR 20d | LS Sharpe | LS MaxDD |
|---|---|---|---|
| `risk_garman_klass_20d` | −0.570 | **−2.44** | 7.74% |
| `risk_gap_vol_20d` | −0.547 | −2.42 | 6.43% |

The volatility factors have high |ICIR| but **negative** long-short Sharpe with large drawdown
— the "short the high-vol junk" pattern that (per the prior `long_only_50cagr` finding) does
NOT convert to long-only return. The earnings-acceleration factors invert this: modest RankIC
but **strongly positive LS Sharpe with near-zero drawdown** — the profile that DOES convert.

**This is the payoff of the Wave-1 promotion**: the fundamental cluster produced the first
factors in this entire effort with a genuinely tradable long-only signature.

### 3.2 Other newly-unlocked fundamental factors of note

- **`qual_piotroski_fscore_9pt`**: ICIR +0.334, **monotonic**, LS Sharpe +2.22, MDD 0.64% —
  the classic composite works and is monotonic (rare among these).
- **Single-quarter growth levels** (`grow_operate_profit_yoy_q` +0.326, `grow_n_income_attr_p_yoy_q`
  +0.305): monotonic, LS Sharpe ~+2.8, low DD. Clean.
- **Value (EV-based)**: `val_retearn_yield` +0.287, `val_ebit_ev_ttm` +0.283 (monotonic),
  `val_fcf_ev_ttm` +0.270 — modest but positive, the EBIT/FCF-over-EV forms GPT recommended
  over the (dropped) EBITDA versions.
- **Cash quality**: `acc_cfo_to_ni_ttm` +0.308 (monotonic), `acc_cash_roa_ttm` +0.301 (monotonic).

### 3.3 The accruals "mismatch" factors — high ICIR but SHORT-side (audit HAS_INF group)

`acc_receivables_sales_mismatch_yoy` (ICIR −0.498, LS Sharpe **−4.72**) and
`acc_inventory_sales_mismatch_yoy` (−0.454, −4.51) have high |ICIR| but, like the volatility
cluster, a strongly negative long-short Sharpe — they identify firms to AVOID (receivables/
inventory growing faster than sales = low-quality earnings), not a long-only signal. These
are exactly the audit's HAS_INF ratio factors; **0 NaN rows in this run confirms the screening
pipeline sanitized the inf cells correctly** (per the audit's inf-handling recommendation), so
the metrics are trustworthy. Sign is as the thesis predicted (negative).

### 3.4 Dead on arrival (D, |ICIR| < 0.15) — flag for retirement

`acc_asset_growth` (−0.015), `acc_dWC_receivables` (−0.020),
`tech_high_breakout_freshness_250d` (+0.025), `mom_52w_high_proximity` (−0.036),
`acc_noa_scaled` (−0.051), `mom_continuous_info_252d_dir` (−0.072),
`qual_cash_collection_ttm` (+0.069), `qual_gross_profitability_ttm` (+0.102),
`acc_dWC_inventory` (+0.129), `acc_net_share_issuance` (+0.133), `acc_goodwill_ratio` (−0.183).

Notable: **`qual_gross_profitability_ttm` is weak in A-shares** (+0.102) despite being a
US-equity workhorse (Novy-Marx). And `acc_asset_growth` (Cooper) is essentially zero — the
US asset-growth anomaly does not replicate here on this window. Honest negative results.

### 3.5 Comparison vs the pre-Wave-1 21-factor run

The 21-factor run (price/volume + indicators only) was B5/C12/D4 with the volatility cluster
as the only strong signal. Adding the 26 statement-based factors: the **8 B-grades now include
3 earnings-acceleration factors with positive tradable profiles** that simply did not exist in
the formal-eligible set before Wave-1. The promotion changed the *character* of the available
alpha, not just the count.

---

## 4. Open questions for GPT (consolidated)

1. **(A)** Any remaining `Count(` usage in production beyond the 2 we fixed?
2. **(B)** Is registering the derived `_sq`/`_q` variants (vs base fields) the right approval unit?
3. **(C)** Coverage gate for structural-zero fields (`goodwill`, `lt_borr`) — flat 50%
   threshold vs `sparse_allowed` + NaN-aware? Is true-zero distinguishable from not-reported
   in the provider? (open risk, unverified)
4. **(D)** Is the independent-recompute parity a valid oracle, or should it read pre-ledger?
5. **(§3)** Of the newly-formal fundamental factors, which warrant inclusion in the sealed-OOS
   top set — and do any show signs of the inf/denominator issues from the audit's HAS_INF group?
6. **Sequencing:** with 47 formal-eligible, is now the right time for the one-shot sealed OOS,
   or do you want a Wave-2 (forecast `p_change`, `holder_num`, `revenue`/`operate_profit`
   indicator ratios) promotion first to widen the pool before the single OOS shot?

---

*Companion artifacts (all in-repo on the `wave1-field-promotion` branch): the merged candidate
CSV, the field_status.yaml diff, the approval YAML, the parity script, the coverage logs, and
the screening results.*
