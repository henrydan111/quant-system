# Factor-Eval Part-G build design (for GPT design review — BEFORE coding)

> Two independent audits converged: ~70% of the engine exists + is reusable; build a **thin
> orchestration/contracts layer** (no engine reinvention). v1.3 §10 binds each step to `call` (reuse) vs
> `build` (this design). This doc is the **design of the `build` half** — review it before any code is
> written. Goal: confirm the storage model, the identity-chain backward-compat decision, the CLI altitude,
> the system-level OOS-FDR handling, and the non-E-wave acceptance test; flag over-engineering or missed seams.

## Scope: what is built vs reused-untouched

**Reuse verbatim (do NOT modify):** catalog/`sync_catalog_to_registry`, PIT linters, `FieldStatusRegistry`,
`unified_eval_universe_matrix`, `replication_governance.resolve_replication_ceiling`,
`assign_candidate_status`/`run_is_walk_forward`, `FrozenSelectionSet`/`HoldoutSealStore`,
`reproduce_sealed_oos`/`produce_promotion_evidence`/`set_status`, `EventDrivenBacktester`,
`compute_factors`→`qlib_windowed_features`, `provider_manifest`.

**Build (this design) — a new package `src/alpha_research/factor_eval_skill/`** + 2 CLIs.

## D1 — Storage model (the foundational decision)

Split by lifetime, NOT one big table:

```
per-FACTOR provenance  → NEW columns on factor_master OR a sidecar `factor_provenance.parquet`:
    evidence_tier, direction_source, may_cite_is_as_confirmation, fresh_oos_eligible,
    multiplicity_scope_id, role (ranking|filter|both), filter_role_subtype,
    quality_flags(json), universe_profile(json), target_universe_declaration_hash
per-SET / per-RUN objects → dedicated hash-keyed stores (like HoldoutSealStore), NOT factor columns:
    TargetUniverseDeclarationStore, SelectedSetStore, DeploymentFrozenPlanStore
    (each = append-only parquet keyed by the object's hash; file-locked)
```

**Proposal:** per-factor provenance = a **sidecar `factor_provenance.parquet`** (keyed by
`factor_id`+`version`), NOT new `factor_master` columns — keeps `factor_master`'s 44-col schema + its
parity tests stable, and isolates the new provenance so it can evolve without a master migration.
*Q for GPT: sidecar vs master columns?*

## D2 — Identity spine + the FrozenSelectionSet backward-compat wrinkle (the trickiest)

`TargetUniverseDeclaration` (TUD) = a new frozen dataclass mirroring `FrozenSelectionSet`'s style
(`target_universe_id`, `universe_definition_filters`, `eligibility_policy`, `asof_policy` →
`target_universe_declaration_hash` = sha256 over the strict payload). `SelectedSet` = frozen dataclass
(`tud_hash`, `pool_hash`, `selected_representatives`, `selection_code_hash`).

**The wrinkle:** §2.1 wants all four objects to share `target_universe_declaration_hash`, but
`FrozenSelectionSet.frozen_set_hash` already hashes a `universe` *string* and the **E-wave seal is already
spent** under that hash. Adding `tud_hash` to FrozenSelectionSet's hash **payload** would change
`frozen_set_hash` and **orphan the existing seal**.
**Proposal:** carry `target_universe_declaration_hash` on FrozenSelectionSet as a **non-payload
provenance field** (NOT in the hashed payload — preserves all existing `frozen_set_hash` values), and
enforce §2.1 via an explicit `assert_identity_chain(tud, selected_set, frozen_set, plan)` checker that all
four hashes match at seal-time and deploy-time. The hash chain is enforced by the **checker**, not by
nesting hashes. *Q for GPT: non-payload field + explicit checker (back-compat) vs schema_version bump that
embeds tud_hash in the payload for new sets only?*

## D3 — Parameterize the E-wave scripts into library functions

Extract, do NOT re-author, into `factor_eval_skill/`:
- `marginal.py`: `select_marginal(pool, matrix, caps, references, floor, universe) → SelectedSet`
  (the greedy from `select_e_wave_marginal.py`, all E-wave constants → parameters).
- `sealed_oos.py`: `run_sealed_oos(frozen_set, n_quantiles=10, bar=BAR) → verdict` (from
  `select_e_wave_sealed_oos.py`; the bar = a single module constant, `n_quantiles=10` pinned).
- `deployment.py`: `run_deployment(plan: DeploymentFrozenPlan) → metrics` (from
  `eval_e_wave_v2_deployment.py`; the liquid-universe + composite construction become plan parameters).
The 3 E-wave scripts become ~10-line callers of these (proving the extraction is faithful).

## D4 — The two CLIs (the missing single entrypoint)

```
factor-eval   register | declare_target | characterize | gate | select | seal
strategy-build deploy
```
Thin orchestrators: enforce the **mode** (deployment_bound vs exploratory_research), the **equality chain**
(D2), the **evidence_tier** reads, and call the reused engine + D3 library functions. They own
*sequencing + invariants*, not computation. *Q for GPT: is "own mode+equality+tier, delegate compute" the
right altitude, or too thick?*

## D5 — Stage-3 reader

`stage3_caps(factor_id) → Stage3QualityRecord`: reads the 7 `results.jsonl` rows → emits `quality_flags`
(`sign_flip_across_core_universes`, `liquid_fail`, `illiquidity_bound` = NEW cross-universe logic;
`coverage_sub` = `call` existing `coverage_tier=='sub'`) + `status_effect` **mapped onto the existing
`STATUS_CEILINGS`** (no parallel status universe). Gate/select MUST read it.

## D6 — System-level OOS-window FDR disclosure (the §11 self-review gap)

`oos_window_multiplicity(oos_window) → {n_distinct_frozen_sets_spent, fdr_context}`: reads
`HoldoutSealStore`'s append-only event log, counts **distinct `frozen_set_hash`es that have spent the same
OOS window**, and stamps it on every new sealed-OOS report ("this is the Nth frozen set to spend
2021-2026"). **Proposal:** start with **disclosure only** (the denominator + a Benjamini-Hochberg context
line), NOT an automatic bar change — the per-set bar stays fixed; the system-level count is surfaced for
human judgment + the `multiplicity_scope_id` record. *Q for GPT: disclosure-only sufficient, or does the
accumulating cross-factor FDR require an actual bar adjustment once N exceeds a threshold?*

## D7 — Non-E-wave acceptance test (the future-applicability gate, §11.1)

Pick a **non-E-wave** factor already in the system (candidate: `overnight_momentum`-family or an OSAP/arXiv
draft) and run it **end-to-end through the new generic CLI** — register→characterize→gate→(select)→seal(dryrun)
→deploy — touching **zero E-wave hard-codes**. **Pass criterion:** the generic path reproduces a hand-run
result for that factor AND no `cicc_*`/E-wave constant is referenced. This test is the build's definition of
done; it gates merge. *Q for GPT: which factor, and is "reproduces hand-run + no cohort constant" the right bar?*

## Sequencing (by leverage)

1. **D1 storage + D2 identity spine + `assert_identity_chain`** (everything hangs off this).
2. **D3 library extraction** (kills clone-per-cohort; immediately reused by the E-wave scripts as a regression check).
3. **D4 CLIs** wiring 1–3 + the reused engine.
4. **D5 Stage-3 reader** + per-factor provenance writes.
5. **D6 system-FDR disclosure.**
6. **D7 non-E-wave acceptance test** — gates the whole layer as future-applicable.

## Open design questions for GPT

1. **D1** sidecar `factor_provenance.parquet` vs new `factor_master` columns?
2. **D2** non-payload `tud_hash` + explicit checker (back-compat with spent seals) vs payload schema-bump?
3. **D6** OOS-window cross-factor FDR — disclosure-only vs an actual bar adjustment past a threshold; seal-layer vs report-layer?
4. **D4** CLI altitude — own mode+equality+tier, delegate compute: right, or too thick / too thin?
5. **Over-engineering check:** do all 8 contract objects need to be code classes, or can some (TUD, DeploymentFrozenPlan) stay validated-YAML artifacts loaded at runtime (cheaper, fewer migrations)?
6. **D7** acceptance factor + pass criterion.
7. **Sequencing** — anything mis-ordered, or a dependency that should move earlier?
8. **Missed seams / collision traps** not already caught by the two audits.

## Decision requested

"Build plan sound — proceed with sequencing D1→D7" (optionally with amendments), or a revised design before
any code is written.
