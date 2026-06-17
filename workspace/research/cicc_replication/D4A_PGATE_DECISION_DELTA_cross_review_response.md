# D4a/P-GATE decision-delta cross-review — response & triage (GPT 5.5 Pro)

> 2026-06-17. GPT 5.5 Pro reviewed the decision-delta at `a43bd0e` and returned **CHANGES REQUIRED —
> narrow artifact fix, not a matrix/import rollback**. It accepted the core conclusion (the residual
> rebuild did not and could not move any formal P-GATE ceiling decision) and 4 of 5 findings; one
> blocking reproducibility gap. The blocking fix is folded in; expected post-fix verdict: APPROVE.

## Triage

| # | Finding | Verdict | Action |
|---|---|---|---|
| 1 | **Blocking** — builder checked only `approved_stable` + `style`; the artifact/prompt claimed `resid_ic_vs_approved_{stable,current}` incl. `current` was checked. `current` was NOT in `RESID_COLS`. | **ACCEPT — DONE** | Added `approved_current` → `resid_ic_vs_approved_current_signed` (persisted only in `unified_metrics_json`; no `_oriented` variant). New `_resid_value` reads top-level column else umj. Regenerated MD + JSON. |
| 2 | Structural independence dispositive for P-GATE ceilings | **ACCEPT (no action)** | Confirmed: resolver has no residual param; `_cohort_ceiling` reads only `coverage_tier`/`effective_ic_days`; ceiling-equality on the 10 persisted is confirmation, not primary proof. |
| 3 | 18 D5 base factors need no persisted new ceilings | **ACCEPT (clarified)** | Did NOT persist new ceilings (would create state for never-live-gated factors). Clarified in the MD that the JSON's `_cohort_ceiling` recompute for the 18 is a **non-persisted read-only diagnostic** (all `candidate_ceiling`). |
| 4 | `1e-3` tie floor defensible; no marginal-selection rerun required | **ACCEPT (no action)** | Kept. The lone swap is a 2.1e-5 co-equal tie; no live selection cut; both at `candidate_ceiling`. |
| 5 | Sub-universe residuals need not be tabulated, but wording must be precise | **ACCEPT — DONE** | Added a **Scope boundary** section: artifact closes landed `univ_all` decisions; old sub-universe residuals *were* changed (the fix's purpose) and are **superseded by the native matrix, not to be used**; no decision was adjudicated on them. |

## What the `approved_current` check revealed (stronger corroboration, not a problem)

Adding the current-book residual surfaced **3 near-zero sign-flips + 2 movers >0.01** on
`resid_ic_vs_approved_current_signed` — and they are the **contamination being corrected**:

- Under the corrected scope `current_signed` and `stable_signed` **COINCIDE exactly** for every cohort
  factor: max\|current − stable\| = **0.0** (new) vs **0.015** (contaminated). The fix made the two
  approved-book residuals consistent.
- The 3 flippers (`grow_total_assets_yoy`, `qual_cfoad`, `size_float_ratio`) had a small wrong-signed
  contaminated current residual now corrected to agree with the stable book (the old values are exactly
  the quarantined-contaminated ones).
- `approved_current` is **umj-only** — never a top-level column, never read by any gate, never on the
  dashboard. So the corrections are **non-decision-bearing**, and the structural proof (1)+(2) holds
  regardless of any residual value.

GPT acceptance criterion satisfied (current movers/flips **listed and shown non-decision-bearing**;
no ceiling changes; no material style-rank moves).

## Net (unchanged headline)

**0 ceiling decisions flipped · 0 consumed-residual (stable/style) flips · 0 material ranking moves ·
GPT flip-rules triggered: NONE.** No matrix rerun, import rollback, or P-GATE rerun was required.
Reviewed-commit for the fix: see the follow-up commit on `report-rc-registration`.
