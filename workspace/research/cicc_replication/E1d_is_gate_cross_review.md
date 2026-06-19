# CICC Wave E1d — price-volume correlation (chart 40) IS-gate cross-review brief

> GPT 5.5 Pro cross-review packet for the E1d draft→candidate IS-gate, BEFORE the live status
> mutation (mirrors the APPROVED E1a/E1b/E1c IS-gate reviews). Permalinks pinned at commit `50ff7c2`.

## GPT verdict (2026-06-19): **APPROVE — GO for `promote_e1d_is_candidates.py --live`**

Narrowly scoped: 8 `corr_*` draft→candidate; `formal_evidence_eligible` rows; `expected_direction`
per-factor (7 inverse + 1 positive); **no sealed-OOS spend; 2021+ sealed/unburned; no independence
claim; no deployment claim; no approved status**.

All 5 E1d-specific points adjudicated: (1) ICIR −0.78/−0.68 = "a yellow flag, not a blocker" — strong but
economically plausible for A-share 量价背离/exhaustion, compute-verified, IS-only; (2) mixed direction
"economically coherent and correctly handled per factor" (turnover-leads-return positive = informed
accumulation; contemporaneous/price-leading comovement negative = crowded chase/exhaustion); (3)
universe-invariance "both" — robustness boost AND broad liquidity/attention-exposure warning; (4)
cross-wave redundancy vs E1c — "flag it durably" (the ONE requested addition, text-only, non-blocking);
(5) near-bar `corr_ret_turnd_prior_20d` — "promote resolve-but-label" (clears the univ_all rule; sub-
universe weakness is a downstream-selection warning, not an IS-gate override). Hardening confirmed intact.

**Requested addition folded (text-only, no re-dry-run required per GPT):** the driver provenance now carries
`cross_wave_redundancy_caveat` (E1d may overlap with E1c liquidity/turnover + reversal controls → must
clear downstream marginal-contribution + residual-vs-book selection before counting as independent) +
`high_icir_caveat`.

**Post-live verified GREEN:** backup `backup_e1d_isgate_20260619_182328`; 8/8 draft→candidate;
expected_direction `corr_ret_turn_post_20d`=positive / other 7=inverse; record_lifecycle_evidence
attached=8 / drift=[] / unknown=[]; P-GATE preflight all 8 `candidate_ceiling`; 8 formal_evidence_eligible;
0 approved (candidate≠approved); 0 OOS spend, evidence_class a_priori, 2021+ sealed; registry
151→159 candidate / 129→121 draft / 7 approved (287); parity + governance + golden 92 tests pass.
Provenance [e1d_is_promotion_provenance.json](e1d_is_promotion/e1d_is_promotion_provenance.json).

## What is being decided

Promote **8 chart-40 price-volume-correlation factors** `draft → candidate` via the `factor_lifecycle`
IS gate, re-using the 2010-2020 `univ_all` walk-forward the `unified_eval` matrix already computed
(matrix-reuse, documented bit-identical to the orchestrator candidate gate). Writing the
`formal_evidence_eligible` rows + `set_status('candidate')` IS the human gate.

Upstream done (live): factor logic GPT-approved (no operator; lead/lag PIT-safe by shifting the leader
back); 8 inline `Corr`+`Ref` factors registered draft; **golden lead/lag direction test added** (GPT
factor-logic-review requirement); 7-domain matrix (**56 cells, 0 err**) imported live (286 rows/universe,
0 contaminated/dup); **P-GATE adjudicated → 8 `candidate_ceiling`** (cap `short_oos_power_floor_fail`);
manifest corrected to 8 factor-level rows (drop `lead_lag_corr`, sha `c8b7369b→3e3eb0aa`).

## The 8 factors and their univ_all IS verdict (all PASS)

Rule: `assign_candidate_status(field_ok ∧ |heldout_icir|≥0.10 ∧ sign_consistency≥0.70)`; all field_ok=True.

| factor | heldout ICIR | sign | dir | construction |
|---|---|---|---|---|
| corr_ret_turnd_20d | **−0.782** | 1.00 | inverse | corr(Δturnover, ret) sync |
| corr_price_turn_20d | **−0.681** | 1.00 | inverse | corr(turnover, adj-close level) sync |
| corr_ret_turn_prior_20d | −0.577 | 1.00 | inverse | corr(turnover, ret) ret-leads |
| corr_price_turn_post_20d | −0.517 | 1.00 | inverse | corr(turnover, close) turnover-leads |
| corr_ret_turn_20d | −0.463 | 1.00 | inverse | corr(turnover, ret) sync |
| corr_price_turn_prior_20d | −0.394 | 0.91 | inverse | corr(turnover, close) price-leads |
| corr_ret_turnd_prior_20d | −0.131 | 0.73 | inverse | corr(Δturnover, ret) ret-leads (near-bar) |
| **corr_ret_turn_post_20d** | **+0.427** | 1.00 | **positive** | corr(turnover, ret) **turnover-leads** |

`EXPECTED_BLOCKED = {}` (empty — all 8 pass).

## E1d-specific points to scrutinize

1. **Unusually strong ICIR magnitude (−0.78 / −0.68).** These exceed E1b (max 0.59) and E1c (max 0.53).
   Price-volume comovement is a documented strong A-share predictor (量价背离/exhaustion), and the
   factors are compute-verified (real-data spot-check: corr∈[−1,1], inf=0, Qlib≈numpy to 3e-8). **Is a
   −0.78 RankICIR a red flag here, or expected for this factor class? Any concern the magnitude is
   inflated by a mechanical link to turnover/liquidity?**

2. **Mixed expected_direction with a clean lead/lag asymmetry (1 positive / 7 inverse).** For the
   return-turnover family, **turnover-LEADS-return (`post`, +0.43) flips sign** vs sync (−0.46) and
   return-leads-turnover (`prior`, −0.58). Direction is derived per-factor from `sign(ICIR)`. **Is the
   asymmetry economically coherent (turnover leading price = informed accumulation → positive; contemporaneous/
   price-leading comovement = exhaustion → negative), and is per-factor direction the correct handling?**

3. **Universe-invariance.** The sign pattern holds across ALL 7 matrix universes (the 7 inverse are
   inverse everywhere; `corr_ret_turn_post` positive everywhere +0.23..+0.56). **Does universe-invariance
   strengthen confidence, or could a uniformly-strong effect indicate a common confound (e.g. size/liquidity)?**

4. **Cross-wave redundancy vs E1c.** `corr_ret_turnd` (Δturnover↔return) and the turnover-based corr
   factors may overlap with the already-candidate E1c turnover/liquidity factors (turn_std, vstd, amihud).
   The within-E1d cohort caveat is recorded; **should the brief also flag potential cross-wave redundancy
   for the downstream marginal-contribution selection?** (No promotion claims independence.)

5. **All-8-pass + the near-bar `corr_ret_turnd_prior_20d` (−0.131 / 0.73).** It clears the univ_all bar
   but is weak in csi300 (−0.08) and microcap (−0.07). The IS-gate uses univ_all (where it passes).
   **Block it as too-weak, or promote it resolve-but-label and let marginal-contribution drop it downstream?**

## Hardening reused from the APPROVED E1a/E1b/E1c gates

real `assign_candidate_status(field_ok)`; ALL-OR-NONE attach + `promoted==requested`; matrix-row identity
(ESTU_STYLE_V1 native 2010-2020); pre-status==draft; P-GATE-ceiling preflight; set-integrity guard
(matrix-8 == catalog-8, rule-blockers == EXPECTED_BLOCKED, passer == family−blocked). Membership is the
**bare `corr_` prefix** (uniquely E1d — no pre-existing `corr_` catalog factor, unlike E1c's `liq_` subset).

## PIT / golden-test / provenance

Lead/lag is PIT-safe by construction (shift the LEADING series back, never a forward `Ref`; latest pair
`< T`). The **golden lead/lag regression test** (`test_e1d_corr_lead_lag.py`) locks: no-forward-Ref,
shift-direction exact string match, numpy semantic direction (post peaks when turnover leads, prior when
price leads). `a_priori` IS-selection on 2010-2020; **2021+ UNBURNED/sealed**. Dry-run clean (8/8 →
candidate, attached=8, 0 drift/unknown, P-GATE preflight passed).

## Files (permalinks @ `50ff7c2`)

- IS-gate driver: `workspace/scripts/promote_e1d_is_candidates.py`
- golden test: `tests/alpha_research/test_e1d_corr_lead_lag.py`
- factor logic (GPT-approved): `workspace/research/cicc_replication/E1d_factor_logic.md`
- E1d operators: `src/alpha_research/factor_library/operators.py` (`corr_price_turn*`, `corr_ret_turn*`,
  `corr_ret_turnd*`); manifest: `config/replication/cicc_price_volume_cohort_v2.yaml`; expander:
  `workspace/scripts/expand_e1d_manifest.py`

## Ask

Adjudicate **APPROVE / CHANGES REQUIRED** for `promote_e1d_is_candidates.py --live` (8 corr_ draft→
candidate). The matrix-reuse path + hardening are unchanged from the approved E1a/E1b/E1c gates — focus on
the 5 E1d-specific points, especially the ICIR magnitude (#1) and the lead/lag asymmetry (#2).
