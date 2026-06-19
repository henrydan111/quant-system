# CICC Wave E1f — capital flow (chart 64) IS-gate cross-review brief

> GPT 5.5 Pro cross-review packet for the E1f draft→candidate IS-gate, BEFORE the live status
> mutation (mirrors the APPROVED E1a/E1b/E1c/E1d IS-gate reviews). Permalinks pinned at commit `026e989`.

## GPT verdict (2026-06-20): **APPROVE — GO for `promote_e1f_is_candidates.py --live`**

Narrowly scoped: 3 `flow_act_buy_*` draft→candidate (`shift_dist_xl` inverse, `prop_l` + `shift_dist_l`
positive); the 6 EXPECTED_BLOCKED stay draft; **no sealed-OOS spend; 2021+ sealed; no approved/deployment/
independence claim**. All 4 points adjudicated: (1) selectivity 3/9 "exactly what the IS gate is supposed to
do" — keep the 6 at draft (the 2 totals plausibly degenerate, medium/small fail the formal rule, not
judgment); (2) large(+)/extra-large(−) "economically coherent enough for candidate status" — `shift_dist_xl`
−0.49 a "yellow flag for downstream validation, not a blocker" (component-net, not opaque `$net_mf_amount`);
(3) promote both large variants resolve-but-label (IS gate ≠ marginal-contribution gate; downstream picks ~1
+ xl); (4) cross-wave caveat accepted + recorded. Hardening confirmed intact. Non-blocking: clean the stale
"18" wording in the factor-logic doc (done).

**Post-live verified GREEN:** backup `backup_e1f_isgate_20260620_011444`; tree unchanged @ `026e989`; 3/3
draft→candidate; expected_direction `shift_dist_xl`=inverse / `prop_l`,`shift_dist_l`=positive; 6 remain
draft; record_lifecycle_evidence attached=3 / drift=[] / unknown=[]; P-GATE preflight 3 `candidate_ceiling`;
3 formal_evidence_eligible; 0 approved; 0 OOS spend, evidence_class a_priori, 2021+ sealed; registry
159→162 candidate / 130→127 draft / 7 approved (296); parity + governance 89 tests pass.
Provenance [e1f_is_promotion_provenance.json](e1f_is_promotion/e1f_is_promotion_provenance.json).

## What is being decided

Promote **3 of the 9** faithful E1f active-family capital-flow factors `draft → candidate` via the
`factor_lifecycle` IS gate (matrix-reuse, bit-identical to the orchestrator candidate gate). **E1f is
SELECTIVE** — unlike E1c/E1d where everything passed, the univ_all gate stops 6 of 9.

Upstream done (live): factor logic GPT CHANGES REQUIRED → path-A APPROVE (9 faithful, buy family deferred
as affine-alias/proxy, empirically confirmed Pearson 1.0); 9 registered draft; 7-domain matrix (**63 cells,
0 err**) imported; **P-GATE → 9 `candidate_ceiling`**; manifest corrected (drop `shift_distance_ratio`).

## The univ_all IS verdict — 3 PASS / 6 BLOCK

Rule: `assign_candidate_status(field_ok ∧ |heldout_icir|≥0.10 ∧ sign_consistency≥0.70)`; all field_ok=True.

**PASS (3) — the order-size signal:**

| factor | ICIR | sign | dir | reading |
|---|---|---|---|---|
| flow_act_buy_shift_dist_xl_20d | **−0.492** | 1.00 | inverse | extra-large net-buy displacement → lower returns (distribution / 拉高出货) |
| flow_act_buy_prop_l_20d | **+0.226** | 0.82 | positive | large net-buy proportion → higher returns (institutional accumulation) |
| flow_act_buy_shift_dist_l_20d | +0.124 | 0.82 | positive | large net-buy displacement → higher returns |

**BLOCK (6) — EXPECTED_BLOCKED:**
- **2 degenerate totals**: `flow_act_buy_prop_20d` (+0.070, sign 0.55), `flow_act_buy_shift_dist_20d`
  (+0.070, sign 0.64) — the aggregate net flow ≈ 0 (the same near-constancy the alias check surfaced), so
  the total carries no cross-sectional signal.
- **4 borderline medium/small**: `_prop_m`/`_shift_dist_m` (sign 0.64 < 0.70), `_prop_s` (|ICIR| 0.015),
  `_shift_dist_s` (|ICIR| 0.090) — just under the bar.

The 6 stay `draft` (resolve-but-label). This is the gate stopping weak factors — a healthier outcome than
the suspiciously-all-pass prior waves.

## Cross-universe (the passers are robust)

`flow_act_buy_prop_l` positive across all 7 (strong in liquid +0.43, growth +0.35); `flow_act_buy_shift_dist_xl`
negative across most (microcap −0.73 strongest, csi300 +0.04 the one exception). The order-size sign split
(large +, extra-large −) is consistent.

## Points to scrutinize

1. **The selectivity (3/9).** Is the gate correctly stopping the 6? Confirm the 2 totals are genuinely
   degenerate (aggregate net flow ≈ 0) rather than a construction error, and that the borderline medium/small
   are correctly held at draft (not a too-strict bar).
2. **Economic coherence of the sign split.** Large-order active net-buy positive (institutional accumulation)
   vs extra-large negative (distribution). Coherent for A-shares, or a red flag? Is `shift_dist_xl` −0.49
   suspiciously strong?
3. **Cohort redundancy among the 3.** `prop_l` and `shift_dist_l` are both large-order net-buy intensity
   (prop = net/turnover, shift_dist = net/gross) — likely highly correlated. Promote both resolve-but-label
   (downstream picks ~1 large-order representative + the xl), or collapse to one?
4. **Cross-wave redundancy.** The active-net-flow factors are conceptually related to the existing `flow_*`
   family (mean-of-ratios `net_pct`) and E1c liquidity/turnover. The prop ratio-of-sums is a distinct
   estimator (you confirmed in the factor-logic review). Flag for downstream marginal-contribution? (recorded
   as `cross_wave_redundancy_caveat`.)

## Hardening (reused from the APPROVED E1a/b/c/d gates)

real `assign_candidate_status(field_ok)`; ALL-OR-NONE attach + `promoted==requested`; ESTU_STYLE_V1 matrix-row
identity; pre-status==draft; P-GATE-ceiling preflight; set-integrity guard (matrix-9 == catalog-9, rule-
blockers == the 6 EXPECTED_BLOCKED, passer == family − blocked). Membership = bare `flow_act_buy_` prefix
(uniquely E1f). a_priori; **2021+ sealed**. Dry-run clean (3/3 → candidate, attached=3, 0 drift/unknown,
P-GATE preflight passed).

## Files (permalinks @ `026e989`)

- IS-gate driver: `workspace/scripts/promote_e1f_is_candidates.py`
- factor logic (path A): `workspace/research/cicc_replication/E1f_factor_logic.md`
- E1f operators (`flow_act_buy_prop`, `flow_act_buy_shift_dist`): `src/alpha_research/factor_library/operators.py`
- manifest: `config/replication/cicc_price_volume_cohort_v2.yaml`; expander: `workspace/scripts/expand_e1f_manifest.py`

## Ask

Adjudicate **APPROVE / CHANGES REQUIRED** for `promote_e1f_is_candidates.py --live` (3 flow_act_buy_*
draft→candidate). Focus on the selectivity (#1) and the order-size economic story (#2).
