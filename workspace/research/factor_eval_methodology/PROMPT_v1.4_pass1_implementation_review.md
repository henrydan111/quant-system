# GPT 5.5 Pro cross-review prompt — v1.4 implementation pass 1 (code + docs)

> The design SHIPPED after 4 rounds (2026-07-03). This is the IMPLEMENTATION review of pass 1
> (commit `91b4a99` on `calendar-unfreeze`, pushed). Copy the block below into GPT 5.5 Pro verbatim.

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. You SHIPPED the v1.4 book-level-promotion design after 4 rounds (your findings B1-B3/M1-M6/m1-m3, N1-N3, R3-M1/M2/m1 are all folded). This is the IMPLEMENTATION review of pass 1. Verify the code faithfully implements the amendment's A1-A8 (within the declared pass-1 scope), hunt for gate bypasses and silent traps, and check the §5 acceptance tests actually pin the behavior. Do not rubber-stamp.

REPO (public — fetch any file; the review commit is 91b4a99)
https://github.com/henrydan111/quant-system   (branch: calendar-unfreeze)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>
Commit diff: https://github.com/henrydan111/quant-system/commit/91b4a99

THE AMENDMENT (the normative contract this implements):
https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/factor_eval_methodology/FACTOR_EVAL_V1.4_AMENDMENT_book_level_promotion.md

CHANGED FILES (all on the branch):
- src/research_orchestrator/release_gate.py            (+ FactorLevelApprovedRetiredError)
- src/alpha_research/factor_registry/store.py          (A3: set_status refusal at ~L1505; _apply_status_write extraction; legacy_factor_approval_override ~L1575; revalidate_legacy_approved ~L1660; set_approval_validity message repointed)
- src/alpha_research/factor_eval_skill/candidate_scope.py   (NEW — A7: UniverseSpec->TUD adapter, alias equality, assert_candidates_on_declared_target)
- src/alpha_research/factor_eval_skill/identity.py     (A2/N2: BookSealIdentity + book_seal_key)
- src/alpha_research/factor_eval_skill/stores.py       (A6: ledger columns spend_unit_type/book_seal_key/override_id; record_book_spend idempotent on (window, book_seal_key); record_study_spend; distinct_spend_keys; TudEquivalenceAliasStore)
- src/alpha_research/factor_eval_skill/multiplicity.py (A6: ACTION_REFUSE, VIRGIN_WARN=3/VIRGIN_HARD=5, is_virgin_window, virgin_window_multiplicity)
- src/research_orchestrator/validation_steps.py        (A7 wiring after definition-binding, before dataset build; candidate_scope_report on the artifact)
- tests: tests/alpha_research/test_v14_book_level_promotion.py (NEW), test_factor_registry.py (A3 matrix + override + revalidate), tests/research_orchestrator/test_pr9_validation_field_gate.py (TestCandidateScopeGate + updated positive-flag test), test_factor_selection.py (derived composite count — fixes a pre-existing guorn-broken hard-coded 20)
- docs: CLAUDE.md §3.5 (4 bullets rewritten) + §3.4 seal-identity clause; AGENTS.md §2a mirrored same pass; factor_status_ladder.md + factor_lifecycle/README.md; STRATEGY_LAYER_BUILD_PLAN_v1.md §1.1; FACTOR_EVAL_METHODOLOGY_v1.4.md (NEW consolidated — v1.3 copied verbatim then surgically amended; v1.3 header marked SUPERSEDED)
- workspace/scripts/rederive_marginal_vs_standalone.py (NEW — B3 residual; full run NOT yet executed: the greedy 1.02-vs-0.70 figures remain unquotable)

DECLARED PASS-1 SCOPE (per the amendment §5 — verify nothing OUT of scope was skipped): the book-seal CLAIM path, run_component_diagnostics_in_book_context + its two context tests, and the burned-window dry-run pilot land with PR3; A8 (no virgin spend before the strategy-registry promotion path exists) makes that safe. The A6 budget function exists but its ENFORCEMENT call site (refusing at spend time) is the PR3 seal caller.

TEST EVIDENCE (full driving files, not just new tests): test_v14_book_level_promotion 7 passed; test_factor_registry 32 passed (163s); test_pr9_validation_field_gate 56 passed; test_promotion_gate + 6 factor_eval_skill files 117 passed; test_factor_selection 11 passed; architecture + d7 acceptance green. Combined re-run of v14+pr9: 63 passed.

SELF-REVIEW PREFLIGHT — completed before this request: verdict "clean for GPT". Checked §3 invariants + the nine quantitative-research principles: no data-path/PIT change anywhere (candidate_scope reads only skill parquet stores); OOS protection strengthened (nothing claims seals in this pass); §3.5/§3.4 edits mirrored into AGENTS.md in the same pass (§11.2). Items verified during self-review: (1) downgrade semantics preserved — _apply_status_write(fresh_approval=False) reproduces the old non-privileged body exactly, approval_validity untouched on downgrades; (2) the A7 gate only fires when the allow-set actually admitted candidates (flag=False paths reject earlier; pinned by test_formal_entries_do_not_trigger_the_gate); (3) blank definition_hash on a resolver entry fails closed (no Stage-3 match possible); (4) AppendOnlyStore._load back-fills the three new ledger columns on pre-v1.4 parquet. Known judgment calls FLAGGED FOR YOU below (questions 3-6).

REVIEW QUESTIONS
1. Gate integrity (A3) — can any call path still mint factor-level 'approved' outside legacy_factor_approval_override? Check: _apply_status_write is private but Python-reachable (is that acceptable given the repo's convention that gates guard the public API?); the override's payload validation (is `scope` + `not_a_new_research_promotion is True` sufficient, or should expiration be REQUIRED not optional?); revalidate_legacy_approved's status!=approved refusal ordering vs its evidence gate.
2. Scope-gate correctness (A7) — the wiring point in handle_validation_object_resolver (after definition-binding, before the field gate): is anything able to reach dataset build or holdout access on a path that bypasses this handler? The canonical adapter (tud_from_prescription_universe: theme->theme_universe_candidate_id id, broad->payload-hash id, full normalized_dict as filters, policy strings 'orchestrator_prescription_v1'): sound and stable, or does the broad-filters payload include anything non-deterministic? The Stage-3 lookup deliberately RELAXES layer1_methodology_hash at the ADMISSION gate (documented in the module docstring; the strict form remains in cmd_select) — acceptable, or a hole?
3. Seal identity (A2/N2) — BookSealIdentity.from_plan computes pre_declared_bar_hash from the plan's own bar (redundant with plan_hash by design, per your round-2 replacement text). Field check vs the live DeploymentFrozenPlan payload: anything spend-differentiating still missing from the key?
4. D6 extension (A6) — record_book_spend idempotent on (window, book_seal_key) while record_spend/record_study_spend stay idempotent on (window, frozen_set_hash): any double-count or under-count seam between the three row types in distinct_spend_keys (book rows fall back to... verify the where-clause)? virgin_window_multiplicity has NO caller yet (PR3) — acceptable under A8, or does pass 1 need a guard elsewhere?
5. Test sufficiency — do the acceptance tests actually pin the failure modes you care about (esp. test_book_seal_key_distinctness's six-way distinctness and the alias universe-id-only refusal)? Name any missing test you would require before PR3 starts.
6. Docs fidelity — spot-check CLAUDE.md §3.5's four rewritten bullets and FACTOR_EVAL_METHODOLOGY_v1.4.md's amended sections (Stage 7/8 rows, §5 display, §8 verbs, §10 bindings, §11.3) against the amendment. Any stale normative statement left (the M6 grep list was run — verify)?
7. The B3 residual — the rederive script is committed but NOT yet run (figures stay unquotable). Its label construction (per-instrument shift(-h) on adjusted close from the same sandbox panel; the label may look forward) and IS-only window: any integrity concern before it is executed?

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested replacement. Map every Blocker to the principle or invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk to carry into PR3.
```
