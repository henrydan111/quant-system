# CICC price-volume replication (E-wave) — PROGRAM-LEVEL cross-review packet

> A meta-review of the whole E-wave arc (not a single gate). For GPT 5.5 Pro. Permalinks @ `89c3702`.

## What this effort is

A faithful, wave-by-wave replication of the CICC 价量因子 handbook (8 charts), each chart run through a
fixed pipeline: **operator/factor logic → GPT factor-logic review → register `draft` → 7-universe IS matrix
(2010-2020) → import → P-GATE (replication-governance ceiling) → IS-gate (`factor_lifecycle`, draft→candidate)
→ GPT IS-gate review → live**. Every live registry mutation is GPT-cross-reviewed + registry-backed-up.
Discipline: **resolve-but-label** (evidence never auto-drives status), candidate ≠ approved ≠ deployable,
2021+ OOS sealed (a_priori IS-only selection on 2010-2020).

## Cumulative state (registry: 162 candidate / 131 draft / 7 approved = 300)

| wave | chart | outcome | candidate | draft |
|---|---|---|---|---|
| E1a | momentum/reversal | 3 reversal promoted (prior session) | 4* | 3 |
| E1b | volatility | 35 promoted (low-vol anomaly, inverse) | 35 | 1 |
| E1c | liquidity | 19 promoted (illiquidity premium + turnover anomaly) | 19 | 0 |
| E1d | price-volume correlation | 8 promoted (量价背离, mostly inverse) | 8 | 0 |
| E1f | capital flow | 3 promoted (SELECTIVE 3/9; large-order net-buy) | 3 | 6 |
| E1g | northbound | **EVIDENCE-ONLY — governance refused promotion** | 0 | 4 |
| **E-wave total** | | | **69** | 14 |
| E1e | chip distribution | **DEFERRED** (needs `cyq_chips`, not ingested) | — | — |

(*E1a count includes the pre-existing `rev_up_down_ratio_20d`.) **0 of the 69 E-wave candidates are
approved/deployable.** The 7 approved are all pre-E-wave (Round-6 winners + `earn_sue_ni_assets`).

## The data-availability honesty (what was NOT registered, and why)

- **E1e (chip distribution) deferred** — 10 full-distribution factors (skew/kurt/buckets) need `cyq_chips`
  (per-price-level distribution); our `cyq_perf` is summary-only → only 1 faithful. Not registered.
- **E1f buy family deferred** — `buy_shift_dist` = rank-identical AFFINE ALIAS of `act_buy_shift_dist`
  (Pearson 1.0 empirically); "total buy incl. passive" unbuildable from active-only moneyflow. Open/close
  family deferred (no intraday split). Registered 9 of an originally-proposed 18; promoted 3.
- **E1g sub-universe cap** — strong IS (+0.69) but P-GATE capped all 4 at `evidence_only` (`coverage_tier=
  sub` → `availability_floor_fail`); reinforced by spent-OOS reversal (same family sign-flipped 2021+) +
  short window (2017-2020). NO promotion.
- Across E1e+E1f+E1g, ~24 handbook factors were deferred/blocked as unfaithful / duplicate / unbuildable /
  not-candidate-eligible rather than registered.

## The redundancy reality (the central concern)

The 69 candidates are **NOT 69 independent discoveries**. They are a handful of correlated families:
- E1b = one low-volatility family (35 shadow/range variants × {20,60,120}d).
- E1c = two sub-families (illiquidity: amihud/shortcut; turnover anomaly).
- E1d = one price-volume-correlation family (8 sync/lead/lag).
- E1f = one large-order net-buy family (3).
Every wave's provenance records a **cohort-redundancy caveat** ("downstream marginal-contribution selection
picks ~2-6 representatives") and the later waves add a **cross-wave caveat** (E1d/E1f overlap E1c liquidity/
turnover). **No marginal-contribution selection has been run** — the 69 are an unselected pool.

## Questions for the program-level review

1. **Methodology soundness.** Is the wave pipeline (operator→factor→matrix→P-GATE→IS-gate, GPT-gated, resolve-
   but-label, a_priori IS-only with 2021+ sealed) a sound way to replicate a factor handbook at scale? Any
   structural weakness?
2. **Register-all vs select-at-registration.** Registering every IS-valid factor (69, resolve-but-label) and
   deferring selection downstream — is this the right discipline, or is it inflationary / risk-laden (a large
   correlated candidate pool that could be mis-read as 69 discoveries)? How should the downstream marginal-
   contribution / residual-vs-book selection be structured to collapse 69 → the genuine handful?
3. **Governance.** candidate ≠ approved, 2021+ sealed, the P-GATE ceilings, and the E1g `evidence_only` catch
   (sub-universe + spent-OOS). Is the governance catching the right things? Gaps? Was the E1g non-promotion
   correct, or too strict (it stopped a +0.69-IS factor)?
4. **Data-availability calls.** Were the E1e defer, E1f buy/open-close defer + alias catch, and E1g sub-
   universe evidence-only the right calls? Anything to reconsider (e.g., is deferring E1e correct vs a
   `cyq_chips` ingestion now)?
5. **Deployability gap.** 0 of 69 E-wave candidates are approved/deployable. What is the correct path to turn
   this IS-validated candidate pool into deployable signal — marginal-contribution selection → a single
   sealed-OOS on the selected representative set → deployment gate? What would make that OOS spend valid given
   the candidates were a_priori-selected on 2010-2020?
6. **Anything unsound, over-claimed, or missed** across the arc?

## Files (permalinks @ `89c3702`)

- Full E-wave history + invariants: `CLAUDE.md` (§3.5 "Live registry state" + factor-lifecycle gates)
- Per-wave detail: `project_state.md` (top entries, 2026-06-17 → 2026-06-20)
- Gate design: `src/alpha_research/factor_lifecycle/README.md`
- Cohort manifest (the frozen replication contract): `config/replication/cicc_price_volume_cohort_v2.yaml`
- A representative IS-gate driver (the SELECTIVE one): `workspace/scripts/promote_e1f_is_candidates.py`
- Factor-logic specs: `workspace/research/cicc_replication/E1{c,d,f,g}_factor_logic.md`
- IS-gate briefs (per-wave GPT verdicts): `workspace/research/cicc_replication/E1{c,d,f}_is_gate_cross_review.md`

## Ask

A candid program-level assessment: is the E-wave replication on sound footing, is the 69-candidate pool
being handled with the right discipline, and what is the correct next step toward a deployable result (vs
continuing to add more correlated candidate families)?

## GPT verdict (2026-06-20): **qualified APPROVE — stop expanding, pivot to family-aware selection**

- **Methodology sound** (no structural leak; "much steadier than batch-promoting from formulas"). **Governance
  is the strongest part** — the E1g `evidence_only` non-promotion was "correct and important" (stopped a
  +0.69-IS factor whose family already reversed OOS). **Data-availability deferrals were right** — don't rush
  `cyq_chips`.
- **Core directive:** the 69 candidates are **~5 correlated families, NOT 69 discoveries**; the biggest risk
  is the *narrative*. Register-all was the right discipline, but it must now enter **family-aware
  marginal-contribution selection** → **~4-9 frozen reps** (caps: vol ≤2, liquidity ≤2, correlation ≤2,
  flow ≤2, reversal ≤1) → **ONE sealed OOS** on the frozen set (NOT 69 individual OOS = "an OOS lottery") →
  deployment gate. 6 deliverables: PoolManifest → FamilyMap → SelectionProtocol → SelectedSet →
  FrozenSelectionSet → (OOS pass) deployment gate.
- **Reporting guards:** "69 variants across ~5 families, 0 deployable" (never "69 discoveries");
  `formula_equivalent_pending` ≠ exact-certified; 7-domain evidence stays evidence, not per-universe approval.
- Answers: Q1 sound-with-caveat · Q2 register-all right, now select · Q3 governance strong, E1g correct ·
  Q4 data calls correct · Q5 select→one-sealed-OOS→deployment-gate · Q6 no blocking flaw, guard the narrative.

**User decision (2026-06-20):** finish the replication FIRST (E1h margin chart-88 + chart-100 composite),
THEN run the selection over the complete pool. The selection is REQUIRED before any E-wave OOS/deployment.
See memory `project_e_wave_selection_mandate`.
