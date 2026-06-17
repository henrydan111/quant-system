# CICC Wave E1a — draft→candidate IS-gate promotion cross-review brief (for GPT 5.5 Pro)

**Gate:** APPROVE to run the `--live` draft→candidate promotion of the 3 E1a reversal IS-passers
(formal IS evidence + `set_status('candidate')` + `expected_direction`) / CHANGES REQUIRED. This is
the downstream factor-lifecycle IS gate (separate from the P-GATE ceiling, which is already done).
`candidate ≠ approved`; NO sealed-OOS spend; 2021+ stays sealed.

**Repo:** https://github.com/henrydan111/quant-system  **Reviewed commit:** `d59eab4` on `report-rc-registration`

## What's being promoted

| factor | heldout ICIR (2010-2020) | sign-consist | expected_direction | candidate bar |
|---|---|---|---|---|
| `mmt_route_20d` | **−0.354** | 1.00 | inverse | PASS (strong reversal; neutralized −0.514) |
| `mmt_route_250d` | −0.189 | 0.73 | inverse | PASS |
| `mmt_discrete_20d` | −0.143 | 0.82 | inverse | PASS — **near-dup of `rev_up_down_ratio_20d`** (already candidate) |

Bar = `abs(heldout_rank_icir) ≥ 0.10 ∧ sign_consistency ≥ 0.70` ([status_rules.py](https://github.com/henrydan111/quant-system/blob/d59eab4/src/alpha_research/factor_lifecycle/status_rules.py)). All negative-ICIR → `expected_direction='inverse'` via [`_expected_direction`](https://github.com/henrydan111/quant-system/blob/d59eab4/src/alpha_research/factor_lifecycle/walk_forward_validation.py#L164-L170) (the bar uses |ICIR|; the sign is recorded as the deployable direction).

## Mechanism — matrix-reuse (resign pattern), user-chosen

The driver ([promote_e1a_is_candidates.py](https://github.com/henrydan111/quant-system/blob/d59eab4/workspace/scripts/promote_e1a_is_candidates.py)) re-uses the **2010-2020 univ_all** `run_is_walk_forward(factor_origin='a_priori')` numbers the unified_eval matrix already computed — documented **bit-identical to the orchestrator candidate gate** (reproduced to 1e-15, 2026-06-10), the same lean path [`resign_candidates_2010_2020.py`](https://github.com/henrydan111/quant-system/blob/d59eab4/workspace/scripts/resign_candidates_2010_2020.py) used for the 87. Sequence (mirrors the orchestrator's `registry_publish`):

1. `record_lifecycle_evidence(evidence_class='a_priori')` — formal `formal_evidence_eligible=True` IS rows, **fail-closed on definition drift** (a drifted factor is skipped, never promoted).
2. `set_status('candidate')` (non-privileged; no git-SHA) — only for drift-clean attached factors.
3. `set_expected_direction('inverse')`.

**Human gate** = the user's explicit "promote all 3 IS-passers" (AskUserQuestion 2026-06-17), exactly as writing the signed rows was the gate for the 87.

**Provenance: `a_priori`** — CICC-handbook-defined, IS-selected on 2010-2020 only. **NOT `oos_informed_backfill`**, so 2021+ is a genuinely **unburned/sealed** window for any future `candidate→approved` step. (Better than the 87 backfill candidates.)

## Temp-copy verification (zero live writes)

```
candidate-bar passers: 3/3
record_lifecycle_evidence: attached=[all 3]  skipped_drift=[]  skipped_unknown=[]
status: mmt_route_20d/250d, mmt_discrete_20d  draft -> candidate
expected_direction: inverse (all 3)
```

## Specific questions

1. **Is the matrix-reuse path acceptable** for a fresh draft→candidate promotion (vs a fresh orchestrator `factor_lifecycle` run)? It is documented bit-identical to the gate (1e-15) and is the established 2010-2020 path; the user chose it. Any objection for *new* (not re-signed) factors?
2. **`mmt_discrete_20d`** passes the IS bar but is a near-duplicate of `rev_up_down_ratio_20d` (already a candidate). The user chose "promote all 3" with the non-independence caveat recorded (it must not count as an independent discovery/marginal win unless it later clears a residual test). Acceptable, or hold it at draft?
3. **`expected_direction='inverse'`** for all 3 (A-share reversal) — correct to admit inverse predictors as candidates (they're cross-sectional alpha; deployment-side long/short handling is a later gate)?
4. **Anything else** before the live status change (e.g. the `mmt_route_250d` sign-consistency 0.73, only just above the 0.70 floor)?

On APPROVE I run `promote_e1a_is_candidates.py --live`, verify the 3 transitions on the live registry, and record the live provenance.
