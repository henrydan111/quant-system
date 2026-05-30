# Sealed-OOS Top-Set Selection Rule (PREDEFINED — frozen before Wave-2 screen)

**Date:** 2026-05-31. **Status:** predefined per GPT 5.5 Pro Round-6 condition #4
("Predefine top-set selection rules BEFORE seeing any new results"). This file is
committed BEFORE the Wave-2 IS screen is run, so the selection cannot be retrofit to
the results. The one-shot sealed OOS will run exactly once on the frozen set.

## Why predefine
OOS is scarce (one shot per strategy variant, per CLAUDE.md §7.3). If the top set is
chosen after seeing OOS-adjacent results it stops being OOS. The rule below is
mechanical so the frozen set is a deterministic function of the IS screen + these
thresholds, not a judgment call made post-hoc.

## Eligibility filter (all must hold)
A factor is OOS-eligible only if:
1. `formal_eligible == yes` in `factor_candidates_merged.csv` (all referenced fields
   `approved` in the registry).
2. NOT in the structural-zero-pending exclusion set: `acc_goodwill_ratio`,
   `acc_noa_scaled` (GPT Round-6 condition #2 — biased toward reporting firms until a
   zero-vs-NaN policy is set).
3. NOT a confirmed short-side / avoidance signal: a factor with |ICIR_20d| ≥ 0.30 but
   **opposite-signed** long-short Sharpe (i.e. high IC but LS Sharpe < 0) is excluded
   from the LONG-ONLY top set (it belongs to a future short/underweight sleeve).
   This removes `risk_garman_klass_20d`, `risk_gap_vol_20d`,
   `risk_parkinson_logrange_*`, `acc_receivables_sales_mismatch_yoy`,
   `acc_inventory_sales_mismatch_yoy`, `rev_gap_reversal_1d`, `mom_volscaled_*`.

## Selection (mechanical, applied to the post-Wave-2 IS screen)
From the eligible set, rank by **IS RankICIR_20d sign-aligned with LS Sharpe sign**
(a factor "scores" only if IC direction and tradable LS direction agree). Then:

- **Tier 1 (always include):** eligible factors with `rank_icir_20d ≥ 0.30` AND
  `ls_sharpe ≥ +1.5` AND `ls_max_dd ≤ 2%`. (Positive IC + clean tradable long-short.)
- **Tier 2 (include up to a total cap of 15):** eligible factors with
  `rank_icir_20d ≥ 0.25` AND `ls_sharpe ≥ +0.8`, added in descending `ls_sharpe`
  order until the combined Tier1+Tier2 set reaches 15 factors.
- **Redundancy prune:** within the selected set, if two factors are near-duplicates
  (same economic concept, e.g. `grow_revenue_yoy_accel_q` vs
  `grow_total_revenue_yoy_accel_q`), keep the higher `ls_sharpe` one and drop the other.
  This is the ONLY discretionary step and must be logged.
- **Hard cap: 15 factors.** If more than 15 pass, keep the top 15 by `ls_sharpe`.

## Expected Tier-1 from the current (pre-Wave-2) 47-factor IS screen
For transparency (this is the prediction, not the post-hoc selection):
`grow_operate_profit_yoy_accel_q` (ICIR +0.50, LS +4.75), `grow_n_income_attr_p_yoy_accel_q`
(+0.50, +5.35), `grow_revenue_yoy_accel_q` (+0.46, +3.54),
`grow_total_revenue_yoy_accel_q` (+0.45, +3.58 — likely pruned vs revenue accel),
`qual_piotroski_fscore_9pt` (+0.33, +2.22, monotonic), `grow_operate_profit_yoy_q`
(+0.33, +2.88), `grow_n_income_attr_p_yoy_q` (+0.31, +2.83). Tier-2 candidates:
`val_ebit_ev_ttm`, `val_fcf_ev_ttm`, `acc_cfo_to_ni_ttm`, `acc_cash_roa_ttm`,
`val_retearn_yield`. Wave-2 may add `op_of_gr`/`ebit_of_gr`/`profit_to_gr`-based factors
if any are constructed and screen well.

## Post-freeze protocol
1. Run Wave-2 IS screen.
2. Apply the rule above mechanically → frozen top set (logged with the exact ICIR/LS
   values that selected each).
3. Run the sealed OOS ONCE on the frozen set (stage='oos_test'), no post-OOS tuning.
4. Whatever the OOS shows is the result — no re-selection.
