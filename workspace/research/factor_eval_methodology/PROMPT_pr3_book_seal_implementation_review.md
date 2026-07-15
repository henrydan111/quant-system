# PR3 (book-level promotion machinery) — GPT §10 implementation review prompt (ROUND 7)

R1..R5 REWORK → all folded. R6 REWORK (3B/1M/1m — system-wide caller-selectable sealed worlds via
engine run_context + HoldoutContext.seal_store_dir + backstops + verify-seal --seal-dir; resolver not
fully fail-closed [empty yaml / falsey section] nor process-pinned [one command read two roots];
completed OOS re-judgeable by NEW CODE constants [verdict not persisted, bar not in any hash]; same-run
resume unreachable via CLI; execution lock 30s timeout) → **all folded**. Branch: `calendar-unfreeze`.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. ROUND-7 re-review of PR3: verify each R6 finding is genuinely closed (re-run your probes) and surface anything new. Do not rubber-stamp. Top invariants: (1) ONE canonical sealed world — no orchestration entry accepts a caller store path; (2) one seal/request executes OOS at most once; (3) the pre-declared judgment is immutable after observation — not even a code deploy can re-judge.

REPO (public) https://github.com/henrydan111/quant-system  (branch: calendar-unfreeze)
Raw form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>

FETCH (authoritative):
- src/research_orchestrator/holdout_seal.py            (strict resolver + lru_cache pin + uncached testable body)
- src/research_orchestrator/engine.py                  (_canonical_holdout_seal_dir: conflict → error)
- src/research_orchestrator/sealed_backtest_runner.py  (HoldoutContext: NO seal_store_dir)
- src/research_orchestrator/steps.py                   (HoldoutContext construction)
- src/backtest_engine/event_driven/__init__.py + vectorized/__init__.py   (backstops → canonical)
- src/research_orchestrator/promotion_evidence.py      (bar verdict computed+persisted in the locked span; bar_hash in request)
- src/alpha_research/factor_eval_skill/sealed_oos.py   (REGISTRATION_BAR canonical spec; persisted-verdict-only wrapper)
- src/alpha_research/factor_eval_skill/identity.py     (EvalProtocolSpec.registration_bar_hash)
- src/alpha_research/factor_eval_skill/orchestration.py (resume_same_run preflight exemption)
- src/research_orchestrator/file_lock.py               (timeout_seconds=None)
- workspace/scripts/hypothesis_cli.py                  (--seal-dir REMOVED)
- workspace/scripts/factor_eval_cli.py                 (--resume-same-run)
- tests/conftest.py                                    (global canonical-root quarantine fixture)
- tests/alpha_research/test_pr3_book_seal.py           (R1..R6 probes pinned)

YOUR R6 FINDINGS — how each was closed (verify in code; probes pinned as named tests):
B1 (system-wide caller-selectable sealed worlds) →
   * engine._resolve_registry_dirs: holdout_seal_dir comes UNCONDITIONALLY from the canonical resolver
     (_canonical_holdout_seal_dir); a run_context that supplies a DIFFERENT dir raises ValueError ("not
     caller-selectable"), never adopted. Pinned: test_engine_registry_dirs_holdout_is_canonical_and_conflict_refused.
   * HoldoutContext.seal_store_dir REMOVED (dataclass field gone — pinned by
     test_holdout_context_has_no_seal_store_dir); the runner's _claim_if_oos and BOTH engine backstops
     (event-driven + vectorized) construct HoldoutSealStore(resolve_configured_global_holdout_root()).
   * hypothesis_cli verify-seal --seal-dir REMOVED; the command reads the canonical root.
   * The book runner's live-mode refusal stands (S6 must not lift it before its entries are canonical);
     its DRYRUN run-local stores remain intentionally isolated (they never touch the canonical world).
B2 (resolver not fail-closed / not pinned) →
   * strict semantics (all pinned in TestCanonicalRootResolver): config.yaml missing / section absent /
     key absent → canonical default; EMPTY yaml or non-mapping top level → HoldoutRootResolutionError;
     research_governance present-but-non-mapping (null/[]/''/scalar) → typed error (no more bare
     AttributeError); holdout_seal_root present-but-blank/non-string (incl. explicit null) → typed
     error; relative paths anchor on the PROJECT ROOT (pinned with a foreign chdir).
   * the public resolver is @functools.lru_cache(maxsize=1) — ONE process = ONE sealed world; a mid-run
     config edit can never split a command across two roots (your ledger-from-A/seals-from-B probe).
     Root changes require explicit migration + process restart (documented in the docstring). The
     uncached body (_resolve_configured_global_holdout_root_uncached) is the unit-test seam.
B3 (completed OOS re-judged by new code) →
   * REGISTRATION_BAR (sealed_oos.py) is the CANONICAL bar-as-data (bar_id, direction-alignment rule,
     rank_icir rule, ls_sharpe rule + floor, nan rule, sides source); registration_bar_hash() is its
     identity.
   * the bar hash is identity material in: EvalProtocolSpec.registration_bar_hash (→ protocol_hash →
     frozen_set_hash; pinned: test_registration_bar_hash_in_protocol_identity) AND the a5_request_hash.
   * the VERDICT is computed INSIDE reproduce_sealed_oos's locked span (same execution_lock that covers
     the compute) and PERSISTED in the completion record (bar_json + bar_hash + verdict_json); loading a
     `complete` record returns the persisted verdict; run_sealed_oos ONLY reads it back (sides/floor are
     not parameters and it never calls the bar function on persisted data).
   * a record WITHOUT a persisted verdict (pre-R6) is QUARANTINED (run_sealed_oos raises "must be
     explicitly migrated"), never silently re-judged. Pinned: test_missing_persisted_verdict_is_quarantined.
   * your floor-flip probe now refuses even harder: changing the bar constants changes the recipe
     identity, so the call REFUSES as a changed recipe (cannot even resume the completed record) — the
     persisted verdict stands. Pinned inside test_completed_a5_reproduction_is_never_recomputed.
Major (same-run resume unreachable via CLI) → --resume-same-run flows CLI → cmd_seal → run_sealed_oos
   (allow_same_run) → reproduce; the cmd_seal preflight exempts ONLY when every spent event for the key
   is the EXACT canonical key (alias hits still refuse) from the IDENTICAL run_dir + step_id (the shared
   A5_REPRODUCTION_STEP_ID constant). No lease/timeout was added; claimed records are never deleted.
   Pinned: TestSameRunResumePath (exempt path + foreign-run refusal).
Minor (execution lock 30s) → file_lock supports timeout_seconds=None (infinite); the A5 execution_lock
   uses it — a second contender waits for completion and loads the persisted result. The lock still
   covers the full claim→compute→complete span.

INCIDENT DISCLOSED (found + fixed during this fold): while updating the A8 runner tests, one burned-
window test claim landed in the REAL data/holdout_seals (the canonical store) — the polluting row
(seal_key=dh_a8_runner, a pytest tmp run_dir) was surgically removed with a .bak backup, restoring the
6 historical spends. Root cause: tests + a now-canonical claim path. Permanent guard: tests/conftest.py
now has a GLOBAL autouse fixture patching the resolver to a per-test scratch dir, so NO test can ever
reach the real sealed world (a test needing a specific root re-patches locally). Please review the
fixture as part of B1.

TEST STATE: 571 passed across the full affected suite (serial), incl. the R6 probe pins + the resolver
matrix + pr8d. Subsets fitting a 124s budget:
  pytest tests/alpha_research/test_pr3_book_seal.py tests/research_orchestrator/test_promotion_evidence.py tests/research_orchestrator/test_r4_wall_hardening.py -q   (~15s)
  pytest tests/alpha_research/test_v14_book_level_promotion.py tests/alpha_research/test_factor_eval_skill_orchestration.py tests/research_orchestrator/test_frozen_selection_set.py -q   (~15s)
Clean-checkout data-dependent failures (gitignored provider_build.json etc.) remain environment, not code.

SELF-REVIEW PREFLIGHT — VERDICT: clean for GPT round 7.
RESIDUAL CONCERNS (honest list):
(a) Stub StepExecutionContexts in tests still hand registry_dirs dicts directly to steps helpers —
    the ENGINE path is canonical+conflict-refusing; hand-built contexts are in-process Python trust
    (same class as constructing a store object directly).
(b) The lru_cache pin means a process that legitimately migrates the root must restart — accepted and
    documented per your prescription.
(c) EvalProtocolSpec gained registration_bar_hash as hash material → NEW protocol hashes differ from
    pre-R6 ones for the same economic recipe. No live spend has passed through cmd_seal's protocol yet
    (live went through the historical drivers keyed by their own frozen-set hashes), and the
    FrozenSealAliasStore exists for legacy-hash equivalence if ever needed — flagging for your call.
(d) The bar-constants change refusing (rather than returning the persisted verdict) means a bar
    evolution requires a migration path for still-unread completed records — consistent with your
    point 5 (quarantine/migrate, never silent).

REVIEW QUESTIONS
1. Re-run your R6 probes (two-world seal claim via engine/runner; empty-yaml + falsey-section resolver;
   two-roots-in-one-command; floor re-judge on a completed reproduction; CLI same-run resume; 30s lock).
   Any still land?
2. Is the conftest global quarantine fixture the right permanent guard for the test/live boundary, or do
   you require a store-level guard (e.g. the store refusing to open the real root under pytest)?
3. Residual (c): accept the protocol-hash evolution (no live spends through this protocol yet), or
   require pre-emptive alias rows?
4. Anything else blocking SHIP for the machinery layer (S6 governed runner + real-data burned-window
   pilot remain future PRs; live promotion is unreachable until a verifier registers).

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested
  replacement. Map every Blocker to the principle or invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
