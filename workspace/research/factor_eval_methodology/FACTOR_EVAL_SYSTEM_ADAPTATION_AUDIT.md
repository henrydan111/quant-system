# Factor-Eval Methodology v1.3 — system adaptation & clarity audit (pre-codification)

> A read-only audit (4 parallel sweeps) of v1.3 against the real machinery: qlib layer / operators /
> data dictionary / field registry / factor catalog / orchestrator / existing eval scripts / registry
> schema. Goal: before codifying the skill, find every **ambiguity**, every **reinvention risk**, and
> every **genuine gap**, so the skill executes unambiguously, reuses (never rebuilds), and produces the
> expected result.

## Verdict

**The factor-CERTIFICATION core is real, reusable, and works end-to-end** (the E-wave ran the full
define→matrix→IS-gate→select→seal→deploy path this session). A skill can CALL it with zero reinvention.
**But:** (1) ~**9 concrete ambiguities** in v1.3 would make a fresh executor stumble or guess; (2) the
entire v1.3 **identity / role / provenance / deployment superstructure** (TUD, `SelectedSet` schema,
`DeploymentFrozenPlan`, role/filter contracts, `evidence_tier`, `quality_flags`, `interaction_check`,
`CapacityContract`, `RevalidationCadence`) **has no `src/` implementation**; (3) every existing
orchestration wrapper is a **per-cohort one-off** (clone-and-edit). → **Not yet turn-key.** Resolve the
ambiguities in v1.3, then codify in two layers (runnable-now orchestration of the core + a Part-G build
for the superstructure).

---

## §1 — Reuse map (CALL these; do NOT rebuild)

| Stage | What | Exact machinery |
|---|---|---|
| 1 define→draft | add factor + register | edit `factor_library/catalog.py` `get_factor_catalog`; `ADJ_*_T1` PIT constants in `operators.py`; `sync_catalog_to_registry()` (`factor_library/selection.py`) → `FactorRegistryStore.sync_catalog()` writes `status="draft"` |
| 1 PIT | safety (TWO checks) | `tests/alpha_research/test_factor_library_pit_safety.py` (expression Ref-wrapping) **and** `scripts/lint_no_unsafe_pit_dates.py` (ledger/date) |
| 1 fields | eligibility | `data_infra/field_registry.py` `FieldStatusRegistry.resolve_field/validate_expression` + `config/field_registry/field_status.yaml` (auto in the orchestrator resolver step) |
| 1 hash | definition binding | `FactorRegistryStore.current_catalog_definition_hashes()` |
| 2 matrix | 7-universe IS eval | `venv/Scripts/python.exe workspace/scripts/unified_eval_universe_matrix.py` → `workspace/outputs/unified_eval_matrix/results.jsonl` (54 keys). 7 universes in `factor_eval/universes.py`. **`resid_ic_vs_style_controls_v1_*` + `resid_ic_vs_approved_stable_*` + `decay_icir_*` + `turnover_ann` all EXIST.** |
| 3 caps | status-ceiling lattice | `factor_registry/replication_governance.py` `resolve_replication_ceiling` (+ `factor_lifecycle_steps.py:_cohort_ceiling`, `gate_cohort_factors.py`). `coverage_sub` ≈ `coverage_tier=='sub'` → `availability_floor_fail`. **Map `status_effect` onto `STATUS_CEILINGS`; do NOT build a parallel status universe.** |
| 4 marginal | algorithm + book-marginality | greedy `|icir|×(1−maxρ)` in `select_e_wave_marginal.py` (extract); **`book_marginality` = the matrix `resid_ic_vs_approved_stable_*` fields** (reference, don't recompute); primitive `ic_analysis.py:compute_marginal_ic` |
| 5 IS gate | the rule | `factor_lifecycle/status_rules.py:assign_candidate_status` (`|icir|≥0.10 ∧ sign≥0.70`, fail-closed) on `factor_lifecycle/walk_forward_validation.py:run_is_walk_forward`. `set_status("candidate")` is ungated. |
| 7 seal/OOS | the spine | `frozen_selection_set.py:FrozenSelectionSet` · `holdout_seal.py:HoldoutSealStore.claim_holdout_access` · `promotion_evidence.py:reproduce_sealed_oos` + `produce_promotion_evidence` · `store.py:set_status("approved", promotion_evidence=, current_git_sha=)` (gated) — **all GENERIC** |
| 8 deploy | primitives | `backtest_engine/event_driven` `EventDrivenBacktester` · `CostConfig.realistic_china()` · `strategies.py:RankedFallbackStrategy` · `long_only_50cagr/research_utils.py` (`monthly_rebalance_dates`/`st_codes_on`/`goal_metrics`) |
| qlib | compute (mandated path) | `operators.py:compute_factors(catalog, start, end, …, stage="is_only"|"oos_test")` → internally `qlib_windowed_features` (the formal door). **Bare `D.features` is lint-banned (`lint_no_bare_qlib_features.py`).** |
| provider | formal pre-flight | `data_infra/provider_manifest.py:load_provider_manifest` + `validate_provider_manifest_against_qlib`; `data/qlib_data/metadata/provider_build.json` (`indicators_fields_20260609`, calendar_end `2026-02-27`); `config/calendar_policies/frozen_20260227_system_build.yaml` |
| registry | 8 fields ALREADY EXIST | `validation_scope`, `approved_uses`, `long_only_viable_provisional`, `latest_oos_rank_icir`, `latest_lo_sharpe_gross`, `expected_direction`, `replication_cohort_id`, `family` |

---

## §2 — Ambiguities to RESOLVE in v1.3 before codifying (so the skill has no guesswork)

1. **Stage-5 invocation path is undefined.** Two real paths terminate in the same rule: (a) the
   `factor_lifecycle` orchestrator (`research_orchestrator_cli.py run` + `phase6_setup_request.py` +
   `phase6_drive_gates.py`) — from-scratch, recomputes the IS panel; (b) the matrix-reuse
   `promote_e1*_is_candidates.py` — replays `assign_candidate_status` on existing `results.jsonl` rows,
   **presupposes a matrix run**, and is **cloned per cohort**. **Decision rule to write in:** new factor →
   run the matrix (Stage 2) then a *generalized* promote (path b on the matrix); **never hand-clone
   `promote_e1x`**; use the orchestrator (a) when no matrix exists.
2. **"PIT-safety check" = two distinct checks** — name both (the expression test *and* the ledger/date lint).
3. **PIT anchor for statement-fundamental factors is NOT in the data dictionary** (income/balancesheet/
   cashflow lack inline anchor notes) — the skill must point to CLAUDE.md §3.2 / `pit_backend.py` for the
   `max(ann_date,f_ann_date)+shift(1)` rule.
4. **`n_quantiles` 5 vs 10 has no single source of truth** (e_wave driver uses 10, arxiv uses 5).
   **Pin decile (10) for all post-2026-06-11 evaluation** and disclose; a wrong value silently mis-scores LS-Sharpe.
5. **`select_*` (provenance-only) vs `promote_*_sealed_oos` (registry-writing)** are the same Stage-7 with
   different side-effects — standardize one (the methodology should state OOS spend ≠ auto-promote).
6. **The pass/fail bar (`ls_sharpe>1.0`, sign-aligned) is a script literal** duplicated in each driver, not a
   contract object — centralize it (C5 `pass_fail_bar` needs a code home).
7. **Stage-0 "register" has no home.** `hypothesis_cli register` is a *strategy+OOS-bound* `Hypothesis`
   object — it cannot hold `role` or `evidence_tier`, and mandates a universe + sealed window. There is **no
   store for a strategy-agnostic Stage-0 factor pre-registration** (direction+role+tier). New code.
8. **"Turnover-normalized IC" / "cost-drag-by-universe" are derivable but not emitted.** `turnover_ann` and
   `heldout_rank_icir` exist as separate fields; the ratio and the isolated `turnover_ann×cost_bps` are not
   columns. The skill must define the exact formula (and that the existing `long_leg_excess_ann_*` are net,
   CSI300/500-only, not per-universe own-benchmark).
9. **`compute_factors` default `CacheContext()` ≠ a sealed `ResearchAccessContext`.** A sealed OOS leg must
   route through the orchestrator / `qlib_windowed_features` with a real seal-claimed context, **not** the
   convenience `compute_factors` default. An invariant the skill author must encode (v1.3 doesn't spell it out).

---

## §3 — Gaps (new "Part-G" code) + the collision traps

**Build (specified in v1.3, absent in `src/`):**
1. **Stage-0 provenance objects** — `CohortHypothesis`, `RoleDeclaration` (role enum + pre-Stage-6 freeze),
   `Stage0EvidenceProvenance_v1` / `evidence_tier` + the 4 wiring points + `multiplicity_scope_id`, and a
   **Stage-0 pre-registration store** (no home today).
2. **5 NEW registry fields** — `evidence_tier`, `quality_flags`, `target_universe_declaration_hash`,
   `universe_profile`, `may_cite_is_as_confirmation` (add to `_FACTOR_MASTER_COLUMNS` + dtype + dataclass +
   migration, or a sidecar table).
3. **Stage-3 reader** — `results.jsonl` (7 rows/factor) → `quality_flags`. `coverage_sub` maps to the
   existing `coverage_tier`; but **`sign_flip_across_core_universes` / `liquid_fail` / `illiquidity_bound`
   are genuinely new** (the existing ceiling lattice is single-universe). Emit `status_effect` mapped onto
   `STATUS_CEILINGS`.
4. **Stage-2 metrics** — limit-up/down tradeability-hit proxy (**genuine gap**; limit logic lives only in the
   universe-exclusion mask); isolated cost-drag-by-universe; turnover-normalized-IC.
5. **Generalized marginal-selection tool** — parameterize `select_e_wave_marginal.py` (cohort/caps/
   references/pool are hard-wired to E-wave).
6. **`SelectedSet` schema + builder + the §2.1 identity chain** (`TargetUniverseDeclaration` +
   `target_universe_declaration_hash` + the "no equality, no run" assertion). Only `FrozenSelectionSet` exists.
7. **`interaction_check`** (§6.2 remove-one/add-one/pair) — absent.
8. **Generic sealed-OOS driver** — parameterize the 5 cloned drivers; centralize the bar + `n_quantiles`.
9. **Stage 8** — `DeploymentFrozenPlan` assembler + `CapacityContract_v1` + the two filter contracts
   (`FilterCharacterization_v1` factor-eval / `FilterDeploymentGate_v1` strategy-build, incl. the
   with/without-filter **A/B harness** — today the deploy scripts do long-only top-K only).
10. **`RevalidationCadence`** engine (§6.1) — the eps_diffusion revoke was done by hand.

**⚠ Collision traps (the biggest reinvention risk — `evidence_tier`/role must NOT reuse these):**
- `evidence_tier` ≠ `replication_tier_planned` (replication fidelity) ≠ `evidence_class`/`formal_evidence_eligible`
  (trust labeling) ≠ cohort `oos_eligibility` (OOS-budget state). Four adjacent-but-distinct fields exist; the
  new `evidence_tier` must be a **new** field, not an overload of any of them.
- `RoleDeclaration` must EXTEND the existing `signal_role`/`expected_direction` columns, not parallel-invent a
  second direction field. (Note: three direction encodings already disagree — `Hypothesis.expected_sign:int`
  vs `factor_master.expected_direction:str` vs `ComponentDirection` enum — reconcile, don't add a fourth.)
- Stage-3 `status_effect` must map onto the existing `STATUS_CEILINGS`/`CEILING_CAP_REASONS` lattice, not a
  new parallel status universe.

---

## §4 — Recommendation

1. **First: a clarity pass on v1.3** resolving the 9 ambiguities in §2 (name the exact command/function/source
   at each step; pin `n_quantiles=10`; state the Stage-5 path decision rule; state the seal-context invariant).
   This is what makes the skill instructions unambiguous.
2. **Then codify in TWO layers:**
   - **Layer 1 — runnable now (orchestration, ~no new core):** the factor-certification path by CALLING the
     existing tools (matrix → `assign_candidate_status` → `FrozenSelectionSet`/seal/`reproduce_sealed_oos` →
     deploy templates), with the §2 ambiguities resolved. This works today (the E-wave proved it).
   - **Layer 2 — Part-G build (the superstructure):** the §3 list. Sequence by leverage: (i) the generic
     **SelectedSet + identity-chain** + the **generalized IS-promote** and **sealed-OOS** drivers (kills the
     clone-per-cohort one-offs); (ii) the **Stage-3 reader** + the 5 registry fields; (iii) **Stage-8**
     assembler + capacity + filter A/B; (iv) Stage-0 provenance + roles + revalidation.
3. **Honesty:** until Layer 2 lands, the skill is an *assisted, governed orchestration of the existing core*,
   not a fully-automated pipeline. That is still a large improvement over today's clone-and-edit, and it
   reuses every certified primitive.

---

## §5 — Independent GPT 5.5 Pro cross-check (converges ~95%)

A second inspection was run **independently** — GPT inspected the public repo code directly with NO
access to §1–§4 — and reached the **same verdict and substance**, which de-risks the conclusion:

- **Same verdict:** "not turn-key; do NOT reinvent the engine; build a thin orchestration/contracts
  layer around existing machinery." GPT estimates the existing code = **~70% of the engine substrate**.
- **Same reuse core:** catalog, PIT linters, field registry, 7-universe matrix + reference-invariant
  residuals, P-GATE ceiling lattice, IS candidate gate, `FrozenSelectionSet`, `HoldoutSealStore`,
  event-driven backtester, provider-manifest checks.
- **Same gaps:** TUD, SelectedSet, DeploymentFrozenPlan, evidence_tier/Stage0EvidenceProvenance, generic
  Stage-3 caps, RoleDeclaration, Filter{Characterization,DeploymentGate}, generalized marginal tool,
  role-aware display, RevalidationCadence; `FrozenSelectionSet` lacks `target_universe_declaration_hash`.
- **Same collision traps:** don't rebuild catalog / PIT linter / seal / backtester; CohortManifest ≠
  CohortHypothesis; bare status enum ≠ role-scoped status.
- **Same ambiguities:** no single skill entrypoint; Stage-0 object choice; universe-identity unification;
  filter handling; Stage-3 general-vs-CICC; Stage-8 storage.

**Complementary catches (no contradictions):**
- *This audit additionally flagged* (data-layer/operational — GPT couldn't fetch `data/`/`workspace/outputs/`):
  the **`n_quantiles` 5-vs-10 silent mis-scoring**, the **two distinct PIT checks**, the **PIT anchor
  missing from the data dictionary**, the **sealed-OOS-context vs `compute_factors`-default-cache
  invariant**, the **limit-hit Stage-2 gap**, the `coverage_sub`↔`coverage_tier` mapping, the 3
  disagreeing direction encodings.
- *GPT additionally emphasized*: an explicit **two-CLI entrypoint** (factor-eval:
  `register/declare_target/characterize/gate/select/seal`; strategy-build: `deploy`), and the existing
  registry field **`approval_validity` {valid, requires_revalidation, stale}** as the reuse hook for the
  RevalidationCadence runner.

**Net:** two independent audits agree → the build plan (§4 + GPT's matching "minimum build" list) is the
cross-checked, reliable basis for codification.
