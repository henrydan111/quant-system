# CICC Wave E1a — IS-promotion cross-review response & triage (GPT 5.5 Pro)

> 2026-06-17. GPT reviewed the IS-candidate promotion driver at `d59eab4`: **CHANGES REQUIRED before
> `--live`** — 3 blocking + 2 non-blocking, all live-script hardening (no objection to the 3-factor
> promotion). All folded in + re-verified on a temp copy. Expected post-fix verdict: APPROVE.

## Triage

| # | Finding | Verdict | Action |
|---|---|---|---|
| 1 | **Blocking** — script used a local `_passes()` that ignored the `field_ok` arm of the formal candidate rule | **DONE** | Replaced with the real `assign_candidate_status(field_ok, heldout_rank_icir, sign_consistency, evidence_kind)`; `field_ok` from the canonical `per_factor_field_eligible(stage='formal_validation')`. The status reason now cites the rule output. Dry-run: 3/3 `field_ok=True`. |
| 2 | **Blocking** — live write could partially promote if evidence attach skipped one factor | **DONE** | After `record_lifecycle_evidence`: **all-or-none** — raise unless `attached == requested` AND `skipped_drift`/`skipped_unknown` empty; `assert set(promoted) == expected` after the status loop; and the hardened gate refuses live unless all 3 admit. |
| 3 | **Blocking** — matrix-reuse accepted any `univ_all` row in results.jsonl (stale/legacy/smoke risk after the residual rebuild) | **DONE** | Reuse the import-side validators: `_assert_scope_and_reference_consistency(methods)` (proves `residual_preprocess_scope==ESTU_STYLE_V1` + reference consistency, with code_commit re-pin) + `_validate_row(row, univ_method)` per row (schema + `layer1_methodology_hash` + reference hashes + metric-key presence). Plus `effective_end <= 2020-12-31`, finite metrics, and **exactly-once** per factor (>1 → fail-closed). The layer1-hash match mechanically proves the corrected native 2010-2020 Layer-1 row. |
| 4 | Non-blocking — assert starting status is `draft` | **DONE** | Pre-status guard: raise if any requested factor is not `draft` (no candidate→candidate spam / silent overwrite). |
| 5 | Non-blocking — backup before live | **WILL DO** | Registry backup taken immediately before `--live` (operational, as with the P-GATE live run). |

## Hardened temp-copy dry-run (zero live writes)

```
scope+reference assertions PASSED: residual_preprocess_scope=ESTU_STYLE_V1, reference identical across 7 universes
hardened candidate gate: 3/3 pass
  mmt_route_20d     ICIR=-0.3543 sign=1.00 dir=inverse field_ok=True
  mmt_route_250d    ICIR=-0.1891 sign=0.73 dir=inverse field_ok=True
  mmt_discrete_20d  ICIR=-0.1432 sign=0.82 dir=inverse field_ok=True  [NEAR-DUP of rev_up_down_ratio_20d]
record_lifecycle_evidence: attached=[all 3]  skipped_drift=[]  skipped_unknown=[]
status: all 3  draft -> candidate
```

## Accepted (GPT direct answers)

- Matrix-reuse acceptable **with row-identity validation** (now added). ✓
- Promote `mmt_discrete_20d` with the durable non-independence caveat (not an independent discovery / marginal win until a residual test clears it). ✓
- `expected_direction='inverse'` correct (admit reversal predictors; long/short is a later gate). ✓
- `mmt_route_250d` sign-consistency 0.73 — above the 0.70 floor, no ad-hoc override; recorded as borderline in provenance. ✓

Awaiting APPROVE → backup → `promote_e1a_is_candidates.py --live` → verify the 3 transitions on the live registry → live provenance.
