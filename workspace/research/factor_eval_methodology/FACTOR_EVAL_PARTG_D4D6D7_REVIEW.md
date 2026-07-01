# Part-G integration layer (D4/D6/D7) — self-review + GPT cross-review packet

> Part-G is COMPLETE (D1-D7). The FOUNDATION (D1/D2/D5/D3) was already GPT-cross-reviewed +
> re-verified (8 fixes folded, all green). This packet asks for a cross-review of the INTEGRATION
> layer that has NOT been externally reviewed: **D4** (the two CLIs + orchestration), **D6** (OOS-window
> multiplicity), **D7** (the non-E-wave acceptance gate). Repo PUBLIC; links pinned per the cover note.
> Skill suite: **135 tests green** (81 skill + 54 §0 guard).

## 1. What the integration layer is

Two thin fail-closed CLIs over the foundation; handlers in `orchestration.py`:
```
factor-eval   register | declare_target | characterize | gate | select | seal
strategy-build deploy
```
- **Forbidden-verb invariant is STRUCTURAL**: disjoint verb sets (factor-eval can't deploy; strategy-build can't seal); a test asserts it.
- **Identity chain**: `cmd_seal` + `cmd_deploy` run `assert_identity_chain` before any persist/run.
- **Governance**: `resolve_governance` enforces native vs cohort from registry membership; a declared cohort with no `replication_cohort_id` FAILS (never a native fallback).
- **D6**: `OosWindowLedgerStore` (seal-layer count, window-tagged) + `oos_window_multiplicity` (approval-layer action). The per-set bar is NEVER changed by the count.
- **D7**: `mom_overnight_20d` (native, non-cohort) runs the GENERIC pipeline end-to-end (production resolver + live matrix, temp store, seal **show**, no live OOS), reproduces a hand-run `stage3_caps`, and the skill path imports ZERO E-wave/cicc code.

## 2. Self-review findings — FIXED (committed)

1. **`cmd_select` silently did no-redundancy selection for multi-factor pools** (a zero correlation
   matrix → the v1 marginal-vs-ICIR defect). Now fail-closed: a multi-factor pool REQUIRES a precomputed
   exposure correlation (`corr_path` / `--corr`); single-factor is unaffected.
2. **`cmd_seal` live wrote to a run-local `seals_live/` dir, not the global `data/holdout_seals`** — a
   "live" skill seal would NOT enforce the cross-run single-shot OOS budget. Live now requires a global
   `holdout_seal_root` and is refused without it, checked BEFORE any spend (a refused live leaves no ledger entry).
3. **D6 multiplicity undercounted** — the skill ledger started empty, ignoring the ~historical seals
   (E-wave/GP/arXiv/eps_diffusion) in `HoldoutSealStore`, resetting the FDR denominator to zero.
   `oos_window_multiplicity` now folds in the seal store's distinct `seal_key` count;
   `n_spent = max(window-tagged, system-recorded)`.

## 3. Open judgment calls for GPT (NOT changed)

- **3.1 (PRIMARY) `frozen_set_hash` canonicality across tools / re-spend risk.** `cmd_seal` builds the
  `FrozenSelectionSet` with `eval_protocol_hash = payload_hash({horizon, n_quantiles, oos_window, metric})`
  and `selection_rule_hash = sel["selection_code_hash"]` (default `"select_marginal_v1"`). So the skill's
  `frozen_set_hash` for a given economic selection DIFFERS from the E-wave script's hash (which used a richer
  `eval_protocol` + a different `selection_rule` string) — and `HoldoutSealStore` keys by `frozen_set_hash`.
  **Question:** does this open a re-spend hole (the same economic OOS test sealed under a NEW hash because a
  tool's protocol/selection-rule STRING differs, so the holdout store doesn't see it as spent)? Should the
  skill's `eval_protocol_hash` capture the FULL protocol (winsor/rank/label/cost/missing/tie-break/universe-filter,
  per the FrozenSelectionSet docstring) to be canonical, or is a thinner protocol acceptable because the
  selection-rule + pool already individuate the set? Is the D6 cross-tool denominator (fix #3) sufficient
  mitigation, or is canonicalization required?
- **3.2 Cohort governance is caller-supplied, not auto-resolved.** `characterize` requires the caller to pass
  `replication_tier`/`claim_class`/`oos_eligibility` for a cohort factor (fail-closed if missing via
  `.cohort()`), but does NOT auto-read them from the cohort manifest / `FactorDomainClaim`. Acceptable as a
  caller contract, or should `characterize` auto-resolve them from the manifest when `factor_class=cohort`?
- **3.3 `cmd_seal` hardcodes `portfolio_side="long_short"`** (the per-factor held side IS carried correctly via
  `SelectedFactor.expected_direction`). For a single-factor long-only intent the book-level side is mislabeled
  in the hash. Parameterize, or leave (the held sides are authoritative for the OOS bar)?
- **3.4 D6 combiner + thresholds.** `n_spent = max(window-tagged, system-recorded)` with default
  `warn=5 / hard=10`. Is `max` right (vs a union that also counts skill dryruns not in the seal store), and are
  the thresholds reasonable defaults given the project already has ~9 distinct sets on 2021-2026?
- **3.5 `gate` trusts the matrix.** `cmd_gate` composes `target_universe_pass` (the matrix's
  `assign_candidate_status` result) + the P-GATE ceiling; it does NOT independently re-run the IS walk-forward.
  Correct (the matrix IS the IS evaluation), or should the gate re-run?

## 4. Questions
1. **#3.1 is load-bearing** — `frozen_set_hash` canonicality / re-spend risk: is the thin `eval_protocol_hash`
   a hole, and is fix #3 (cross-tool denominator) enough, or must the protocol hash be made canonical?
2. Do the three self-review fixes correctly resolve their issues (any incomplete / new issue)?
3. #3.2–#3.5 — each: acceptable as-is, or change before first live use?
4. Any correctness/seam issue NOT caught here in `orchestration.py` (artifact-chaining, the equality checks at
   seal/deploy, the exploratory-mode default-TUD), `multiplicity.py`, or the D7 acceptance rigor?
5. The skill is COMPLETE but not yet exercised in a live OOS spend — is it safe to run one (on a chosen factor)
   given the above, or fix #3.1 first?

## 5. Decision requested
"Integration layer sound — safe to run a live OOS spend" (optionally after fixing #3.1), or specific changes first.
