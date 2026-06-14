# CICC factor-logic cross-review brief (for GPT 5.5 Pro)

> 2026-06-14. This review is about **factor LOGIC + the changes made**, NOT the governance
> infrastructure (that was the P-GATE R1/R2 reviews). Scrutinize whether the factors built
> this session faithfully replicate the CICC definitions and whether the construction /
> registration decisions are sound. I have ALREADY self-caught one error (qual_aprd, below) —
> confirm it and hunt for others.
>
> GPT 5.5 Pro is web-based. Branch `report-rc-registration` (HEAD `a69ff3a`), repo
> `henrydan111/quant-system`.
>
> - Factor definitions: https://github.com/henrydan111/quant-system/blob/report-rc-registration/src/alpha_research/factor_library/catalog.py (CICC D5 block + the new D4a block + comp_cicc_profit in get_composite_defs)
> - Cohort manifest (tiers/handbook ids): https://github.com/henrydan111/quant-system/blob/report-rc-registration/config/replication/cicc_fundamental_cohort_v1.yaml
> - Field approvals: https://github.com/henrydan111/quant-system/tree/report-rc-registration/config/field_registry/approvals (2026-06-14_*)

## CICC truth (from the handbook, for fidelity checking)

D-suffix = first difference: **"当期 X_TTM − 上期 X_TTM"** where 上期 = prior QUARTER. The handbook rows:
CFOAD/ROAD/ROED = ΔCFOA/ΔROA/ΔROE_TTM · CCRD = Δ现金流动负债比率 · CURD = Δ流动比率 · DAD = Δ资产负债率 · DTED = Δ产权比率(debt/equity) · QRD = Δ速动比率 · CSRD = Δ现金比率(cash/cur-liab) · **APRD = 应计利润占比变动 (Δ accruals ratio)**. Composite Profit = CFOA + ROE + ROIC 等权.

## What was built (formulas as implemented)

`comp_cicc_profit` = equal-weight cross-sectional rank-combine of:
- `qual_cfoa_ttm` = OCF_TTM(q0..q3)/total_assets_q0  — **PIT single-quarter-slot TTM**
- `qual_roe` = `op.fundamental('roe')`  — **vendor fina_indicator ROE (cumulative YTD)**
- `qual_roic` = `op.fundamental('roic')`  — **vendor fina_indicator ROIC (cumulative YTD)**

D4a (10) — current-quarter TTM ratio minus prior-quarter TTM ratio; prior TTM uses the q1..q4 slots; every field `Ref(...,1)`-wrapped:
- `qual_cfoad` = OCF_TTM(q0..q3)/TA_q0 − OCF_TTM(q1..q4)/TA_q1
- `qual_road`  = NI_TTM(q0..q3)/TA_q0 − NI_TTM(q1..q4)/TA_q1
- `qual_roed`  = NI_TTM/equity_q0 − NI_TTM_prev/equity_q1, equity = **total_hldr_eqy_inc_min_int (incl minority)**
- `qual_ccrd`  = OCF_TTM/total_cur_liab_q0 − OCF_TTM_prev/total_cur_liab_q1
- `qual_csrd`  = money_cap_q0/total_cur_liab_q0 − money_cap_q1/total_cur_liab_q1
- `qual_dad`   = total_liab_q0/TA_q0 − total_liab_q1/TA_q1
- `qual_dted`  = total_liab_q0/equity_q0 − total_liab_q1/equity_q1 (incl-minority equity)
- `qual_curd`  = total_cur_assets_q0/total_cur_liab_q0 − (q1 version)
- `qual_qrd`   = (total_cur_assets_q0 − inventories_q0)/total_cur_liab_q0 − (q1 version)
- `qual_aprd`  = oper_cost_TTM/accounts_pay_q0 − oper_cost_TTM_prev/accounts_pay_q1   **← SELF-CAUGHT WRONG**

NI_TTM = Σ n_income_sq q0..q3 (incl minority — n_income_attr_p lacks q1..q3 slots). 9 new slot fields registered register-only (income n_income_sq_q4; cashflow n_cashflow_act_sq_q4; balancesheet money_cap/total_assets/total_cur_liab/total_liab/total_cur_assets/inventories q1, total_hldr_eqy_inc_min_int q0/q1, accounts_pay q0/q1), coverage 0.97–1.00 == approved q0 siblings.

## Self-caught error (confirm + advise)

**`qual_aprd` is misdefined.** I read "APR" as accounts-payable turnover and built Δ(COGS_TTM / accounts_payable). The handbook says **APRD = 应计利润占比变动 = Δ(accruals ratio)**. Proposed fix: APR = (NI_TTM − OCF_TTM)/total_assets (Sloan-style accruals/assets — I have NI_TTM, OCF_TTM, TA already), APRD = current − prior-quarter. Consequence: `accounts_pay_q0/q1` were registered for the wrong interpretation — harmless (unused) but should be removed or repurposed. Please confirm the fix AND the correct accruals-ratio denominator (assets vs NI vs revenue; the catalog's `qual_accruals` is `ocfps/eps`, a different cash-realization ratio — not the Sloan accruals ratio).

## Factor-logic questions to probe

1. **APRD fix** — confirm accruals = NI − OCF and the right denominator/sign.
2. **comp_cicc_profit basis mix** — it rank-combines a PIT-TTM CFOA with two **vendor-cumulative (YTD)** ROE/ROIC. Cross-sectional ranking partly absorbs scale, but cumulative-YTD ROE/ROIC have a seasonal sawtooth (Q1 vs Q4 magnitudes) that TTM CFOA does not. Is this a faithful CICC Profit, or should all three be on a TTM basis (ROE_TTM/ROIC_TTM aren't in the catalog)?
3. **ROED/DTED equity basis** — I used **incl-minority** equity to match the incl-minority NI_TTM (归母 NI_TTM is unbuildable: n_income_attr_p lacks q1..q3 slots). CICC ROE is 归母. Is the incl-minority deviation acceptable for a Δ factor, or does it distort? ROED came out the **strongest** D4a (IS heldout 0.48) — artifact of the basis, or genuine?
4. **Strong-factor redundancy** — the 4 "strong" D4a are ΔROE 0.48 / ΔROA 0.46 / ΔCFOA 0.26 / ΔCCR 0.18. ΔROE and ΔROA share the NI_TTM numerator; ΔCFOA and ΔCCR share OCF_TTM. Are these really ~2 distinct signals (net-income acceleration, cash-flow acceleration) repackaged across denominators? (Relevant to marginal-orthogonal-contribution selection — we don't want 4 near-duplicates counted as 4 wins.)
5. **Δ-TTM QoQ construction + slot alignment** — current TTM (numerator q0..q3) over the q0 period-end denominator; prior TTM (q1..q4) over the q1 denominator. Is pairing the q1..q4 TTM with the q1 (one-quarter-back) balance-sheet denominator the correct "上期" snapshot, or should the prior denominator be q1 vs q4? Any one-quarter misalignment that contaminates the difference?
6. **PIT** — every `$field` is `Ref(...,1)`-wrapped; the prior-TTM reaches back to q4 (4 quarters). Confirm no lookahead and that the difference is a genuine QoQ change (not a same-period artifact).
7. **Field registration** — the q1/q4 slots are claimed "same pit_backend derivation as the approved q0/q3/q4 siblings → parity by construction" (coverage measured 0.97–1.00). Is "same derivation" sufficient, or does each new slot warrant an independent value-parity check vs the source ledger?

## Requested verdict

Per the prior rounds: an overall verdict + numbered findings (blocking / non-blocking + the specific fix). Especially: (a) confirm the qual_aprd fix; (b) is the comp_cicc_profit basis mix or the ROED incl-minority basis a correctness problem; (c) is the strong-factor set actually redundant. Nothing has been promoted — all are drafts at candidate_ceiling.
