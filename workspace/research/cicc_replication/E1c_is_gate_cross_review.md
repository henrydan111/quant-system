# CICC Wave E1c — liquidity (chart 28) IS-gate cross-review brief

> GPT 5.5 Pro cross-review packet for the E1c draft→candidate IS-gate, BEFORE the live status
> mutation (mirrors the E1a/E1b IS-gate reviews). Permalinks pinned at commit `9a49cf9`.

## GPT verdict (2026-06-18): **APPROVE — GO for `promote_e1c_is_candidates.py --live`**

Narrowly scoped: 19 guarded E1c `liq_*` draft→candidate; `formal_evidence_eligible` rows attached;
`expected_direction` mixed/per-factor; `evidence_class=a_priori`; **2021+ remains sealed / 0 OOS spend**;
**candidate ≠ approved**; **NOT 19 independent discoveries**. No sealed-OOS spend / approved status /
deployment / independent-discovery count is approved by this verdict.

All 5 E1c-specific choices reviewed **OK**: (1) explicit-19-id membership correctly excludes the older
`liq_` factors — "the prior E1b 'all vol_' pattern would have been unsafe here; this avoids that footgun";
(2) mixed direction sound because `expected_direction` is per-factor, not per-cohort — "preferable to
forcing two artificial waves"; (3) all-19-pass NOT a blocker — near-bar names (sign 0.73 > 0.70) must not
be hand-blocked, the control is the redundancy label + downstream marginal-contribution selection, not a
higher IS bar; (4) guarded denominators do not contaminate IS (NaN-not-inf, dropped not zero-filled);
(5) cohort-redundancy caveat "OK and mandatory". Hardening confirmed intact. **Post-live verified GREEN**
(see below). docs: this file; provenance [e1c_is_promotion_provenance.json](e1c_is_promotion/e1c_is_promotion_provenance.json).

**Post-live checklist (all confirmed):** registry backup `backup_e1c_isgate_20260618_210607`; tree
unchanged @ `9a49cf9`; 19 still draft pre-run; record_lifecycle_evidence attached=19 / drift=[] /
unknown=[]; 19 draft→candidate; expected_direction 12 positive / 7 inverse; P-GATE preflight all 19
`candidate_ceiling`; 0 OOS spend, evidence_class a_priori, 2021+ sealed; cohort-redundancy caveat present,
independent_discoveries_counted 0; registry 132→151 candidate / 140→121 draft / 7 approved (279);
catalog↔registry parity + governance 89 tests pass.

## What is being decided

Promote **19 chart-28 liquidity factors** `draft → candidate` via the `factor_lifecycle` IS gate,
re-using the 2010-2020 `univ_all` walk-forward numbers the `unified_eval` matrix already computed
(the proven matrix-reuse path, documented bit-identical to the orchestrator candidate gate, 1e-15).
Writing `formal_evidence_eligible=True` rows + `set_status('candidate')` IS the human gate.

Upstream already done (live): factor logic GPT-approved (B1–B4), 19 guarded `liq_*` factors registered
draft (`d89c0b6`), 7-domain matrix (133 cells, 0 err), matrix evidence imported, **P-GATE adjudicated
live → 19 `candidate_ceiling` records** (cap `short_oos_power_floor_fail`, truth-observed 2022-07),
manifest corrected to 19 factor-level rows (sha `66098014→c8b7369b`).

## The 19 factors and their IS verdict (all PASS the candidate rule)

Candidate rule: `assign_candidate_status(field_ok ∧ |heldout_icir|≥0.10 ∧ sign_consistency≥0.70)`.
Direction `_expected_direction(icir)` = positive(>0) / inverse(<0). **All 19 field_ok=True.**

**Illiquidity premium — 12 factors, expected_direction=positive (illiquid → higher return):**

| factor | heldout ICIR | sign | factor | heldout ICIR | sign |
|---|---|---|---|---|---|
| liq_shortcut_avg_20d | +0.5284 | 1.00 | liq_shortcut_std_60d | +0.3799 | 0.82 |
| liq_amihud_avg_20d | +0.5009 | 0.91 | liq_shortcut_avg_120d | +0.3764 | 0.82 |
| liq_amihud_std_20d | +0.4724 | 0.82 | liq_amihud_std_60d | +0.3559 | 0.82 |
| liq_shortcut_avg_60d | +0.4474 | 1.00 | liq_amihud_avg_120d | +0.3365 | 0.82 |
| liq_shortcut_std_20d | +0.4395 | 0.91 | liq_shortcut_std_120d | +0.3173 | 0.91 |
| liq_amihud_avg_60d | +0.4089 | 0.82 | liq_amihud_std_120d | +0.2651 | 0.73 |

**Turnover anomaly — 7 factors, expected_direction=inverse (high turnover → lower return):**

| factor | heldout ICIR | sign | factor | heldout ICIR | sign |
|---|---|---|---|---|---|
| liq_turn_std_20d | −0.5705 | 1.00 | liq_vstd_120d | −0.4143 | 0.91 |
| liq_vstd_20d | −0.5569 | 0.91 | liq_turn_std_120d | −0.3317 | 0.82 |
| liq_vstd_60d | −0.4768 | 0.91 | liq_turn_avg_120d | −0.2802 | 0.73 |
| liq_turn_std_60d | −0.4235 | 0.91 | | | |

So `EXPECTED_BLOCKED = {}` (empty) — unlike E1b where `vol_down_std_20d` failed sign (0.64<0.70).

## E1c-specific design choices to scrutinize

1. **Explicit-19-id membership (NOT a bare `liq_` prefix).** Unlike E1b (where ALL `vol_` catalog
   factors WERE the 36-strong family), the `liq_` namespace ALSO holds pre-existing non-E1c factors
   (`liq_turnover_*`, `liq_amihud_20d`, `liq_vol_cv_*`, `liq_zero_ret_days_10d`, `liq_spread_proxy_20d`,
   `liq_turnover_skew_20d`). The driver derives the exact 19 from the catalog via `E1C_PREFIXES`
   (`liq_turn_avg_120`, `liq_turn_std`, `liq_vstd`, `liq_amihud_avg`, `liq_amihud_std`, `liq_shortcut`)
   and the set-integrity guard fails closed if `set(matrix rows) != catalog-19`. **Is this membership
   basis sound, and does it correctly exclude the older liquidity factors from the promotion set?**

2. **Mixed expected_direction (12 positive / 7 inverse).** The two sub-families have OPPOSITE signs
   (illiquidity-premium positive vs turnover-anomaly negative). Direction is derived per-factor from
   `sign(ICIR)`. **Any concern that promoting a single cohort with two opposite-signed sub-families
   under one hypothesis-id is unsound, or is per-factor direction the correct handling?**

3. **All-19-pass (EXPECTED_BLOCKED empty) — too clean?** Both the illiquidity premium (Amihud/Datar-
   Naik) and the turnover anomaly are well-documented strong A-share anomalies, so a clean pass on
   2010-2020 IS is a-priori plausible. **Is an all-pass cohort a red flag here, or expected given the
   strength of these effects? Should any near-bar factor (e.g. `liq_amihud_std_120d` sign 0.73,
   `liq_turn_avg_120d` sign 0.73) get extra scrutiny?**

4. **Guarded denominators.** The IS numbers use the GPT-approved guarded forms (`If(amt>0, …, NaN)`
   on all amount denominators + the vstd return-std denominator; NaN-not-inf). `liq_amihud_avg_20d`
   is registered NEW (guarded) — distinct from the unguarded `liq_amihud_20d` (B3). **Confirm the
   guard does not contaminate the IS evaluation (NaN on non-positive denom is dropped, not zero-filled).**

5. **Cohort-redundancy caveat.** The 19 are 2 correlated sub-families; promoted resolve-but-label, NOT
   19 independent discoveries; downstream marginal-contribution selection picks ~2-4 orthogonal
   representatives. **Is this caveat correctly scoped and recorded?**

## Hardening guards reused from the E1a/E1b IS-gate reviews

- real `assign_candidate_status(field_ok=…)` from `per_factor_field_eligible(stage='formal_validation')`
- ALL-OR-NONE evidence attach + `promoted == requested` (refuse partial)
- matrix-row identity validation (`_validate_row` + `_assert_scope_and_reference_consistency` →
  ESTU_STYLE_V1 native 2010-2020, schema+layer1_hash+scope+window, finite, exactly-once)
- pre-status==draft guard (refuse if any passer not at draft)
- P-GATE-ceiling preflight (every promoted factor must already carry `candidate_ceiling`)
- set-integrity guard (matrix-19 == catalog-19, rule-blockers == EXPECTED_BLOCKED, passer==family−blocked)

## Provenance / sealing

`a_priori` IS-selection on 2010-2020 only; **2021+ UNBURNED/sealed**. Dry-run on a temp registry copy
is clean (19/19 → candidate, attached=19, 0 drift/unknown, P-GATE preflight passed).

## Files (permalinks @ `9a49cf9`)

- IS-gate driver: `workspace/scripts/promote_e1c_is_candidates.py`
- manifest expander: `workspace/scripts/expand_e1c_manifest.py`
- corrected manifest: `config/replication/cicc_price_volume_cohort_v2.yaml`
- factor logic (B1–B4): `workspace/research/cicc_replication/E1c_factor_logic.md`
- E1c operators: `src/alpha_research/factor_library/operators.py` (`turnover_std`, `amihud_illiquidity_*`,
  `liq_vstd`, `shortcut_illiquidity_*`, `_nan_if_nonpos`); catalog wiring: `catalog.py`

## Ask

Adjudicate **APPROVE / CHANGES REQUIRED** for running `promote_e1c_is_candidates.py --live` (19 liq_*
draft→candidate). Focus on the 5 E1c-specific choices above; the matrix-reuse path + hardening are
unchanged from the APPROVED E1a/E1b gates.
