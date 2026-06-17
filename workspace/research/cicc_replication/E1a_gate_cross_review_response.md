# CICC Wave E1a — gate cross-review response & triage (GPT 5.5 Pro)

> 2026-06-17. GPT 5.5 Pro reviewed the E1a 7-domain gate brief at `58cc13c` and returned **CHANGES
> REQUIRED before `--live`** — 3 blocking, all governance/audit hygiene (no matrix rerun). All 3 are
> folded in + verified; the 4 non-blocking points are accepted. Expected post-fix verdict: APPROVE.

## Triage

| # | Finding | Verdict | Action |
|---|---|---|---|
| 1 | **Blocking** — `gate_cohort_factors.py` hard-codes `hypothesis_id="cicc_d4a"` + D4a governance notes → pollutes E1a's durable claim/governance history | **DONE** | `--hypothesis-id` is now **required** (no default — the d4a footgun is gone); `--governance-notes` optional (derived from the id). Verified on a temp copy: the 6 E1a claims carry `cicc_e1a_momentum_reversal`, zero `cicc_d4a` pollution. |
| 2 | **Blocking** — `certify_e1a_operators.py --live` persisted only `W=250` in the structured field (W=20 buried in a notes string) | **DONE** | Added a first-class `per_window_results_json` column to `OperatorCertification` (Option A); `certify` takes `per_window_results=`; the script persists `{"W20": {4 tests}, "W250": {4 tests}}`. Status still resolves from the flat `test_results` (deepest window). Re-ran `--live`: all 4 operators now carry both windows, all 8 cells pass. `records()` reindexes to the schema so pre-existing rows read back clean. |
| 3 | **Blocking** — live batch silently skips unresolved factors → 5-of-6 partial write on a typo/dropped link | **DONE** | `gate_cohort_factors.py` rewritten two-phase: PHASE 1 resolves every requested factor read-only; if ANY is unresolved, `--live` **raises before any write**. PHASE 2 registers claims; PHASE 3 adjudicates + persists; a post-write `written == requested` assert. Verified on a temp copy: 5-real+1-bogus `--live` → refused (exit 1), governance unchanged (zero partial write). |

## Non-blocking — accepted (no further change)

- **Warmup-via-runway** accepted in lieu of a row-drop (490d runway ≥ 271d deepest window; start-date invariance max|diff|=0.0; structural pytest guard).
- **Gate all 6** (ceiling = governance bound, not an IS verdict) — the 3 IS-failers still get governance records showing why they cap; the downstream `factor_lifecycle` IS gate filters.
- **Short-OOS cap** (`2022-07-01` truth window → `short_oos_power_floor_fail` → `candidate_ceiling`, not `eligible_for_oos`) — confirmed expected for all 6.
- **`mmt_discrete_20d` near-dup of `rev_up_down_ratio_20d`** — gate normally with the dedup recorded; do NOT count as an independent discovery / marginal-contribution win unless it later clears a residual test against the approved book.

## Verification (all on temp copies / unit tests — ZERO live writes to production)

- **TEST_A (happy path):** `--live` on a temp registry copy for the 6 → all 6 `candidate_ceiling`, governance 10→16 (+6), 6 claims under `cicc_e1a_momentum_reversal`, `written=6 requested=6`. (GPT checklist items 4 + 5.)
- **TEST_B (fail-closed):** 5 real + 1 bogus `--live` → **refused (exit 1)**, governance 10→10 (no partial write).
- **TEST_C:** missing `--hypothesis-id` → argparse exit 2.
- **Unit:** new `test_per_window_results_persisted_and_status_unaffected` (per-window round-trip + back-compat default `{}`). Full sweep of the touched files — `test_operator_certification` + `test_factor_lifecycle_steps` + `test_replication_governance` + `test_factor_registry` + `test_e1a_warmup_runway` — **125 passed**.

## Final pre-live checklist (GPT) — status

1. E1a-specific `hypothesis_id` + notes — **DONE** (required arg; temp-copy verified).
2. Both `W=20` + `W=250` persisted — **DONE** (`per_window_results_json`; re-certified).
3. `<6` resolve → fail before write — **DONE** (two-phase; temp-copy verified).
4. Dry/temp run shows all 6 → `candidate_ceiling` after claim registration — **DONE** (TEST_A).
5. Live writes exactly 6 claims/governance/linkage, no status promotions — **DONE** (TEST_A; resolve-but-label, `gate_cohort_factors` never calls `set_status`).

## Final verdict (GPT 5.5 Pro, 2026-06-17): APPROVE — GO for real `--live`

GPT approved the production adjudication (P-GATE ceiling only; no status promotion, no sealed-OOS
spend). **Executed + verified** (registry backed up to `data/factor_registry.backup_e1a_20260617_203834`
first, per GPT's guardrail):

```
resolve 6/6 → all 6 candidate_ceiling (blocking=short_oos_power_floor_fail) → written=6 requested=6
```

Post-write verification on a fresh read of the live registry — every GPT checklist item GREEN:
governance 10→16 (+6 E1a, all `candidate_ceiling`, E1a notes) · 6 claims under
`cicc_e1a_momentum_reversal` (0 `cicc_d4a` pollution) · F11 linkage 6 · F3 cohort stamp 6 ·
factor_master status all `draft` (**0 promotions** — resolve-but-label) · unresolved 0. The cap is the
expected truth-observed/short-OOS path, NOT operator/coverage failure. **#34 + #38 closed.** The
downstream `factor_lifecycle` IS gate (which would pass mmt_route_20d/_250d/discrete_20d and stop the
other 3) remains a separate human-gated step — NOT run here.
