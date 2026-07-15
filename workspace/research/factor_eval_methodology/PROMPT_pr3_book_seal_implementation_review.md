# PR3 (book-level promotion machinery) — GPT §10 implementation review prompt (ROUND 6)

R1..R4 REWORK → all folded. R5 REWORK (4B/1M/1m — public entry can still override the seal store +
budget ledger [B1 incomplete]; "project-root relative" root resolves by CWD + silent fallback on config
error; `claimed` state has no exclusive lock over the compute + no same-run binding [concurrent double
read]; completed OOS re-judged with a new floor/direction; new-frozen-set stage swallows registry↔catalog
drift; A5 consume same-request retry stranded) → **all folded**. Branch: `calendar-unfreeze`.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. ROUND-6 re-review of PR3: verify each R5 finding is genuinely closed (re-run your probes) and surface anything new. Do not rubber-stamp. Top invariants: (1) EVERY live seal event / budget ledger row / authorization / completion record / alias belongs to ONE canonical sealed world the caller cannot choose; (2) one seal/request executes the OOS at most once, concurrently-safe.

REPO (public) https://github.com/henrydan111/quant-system  (branch: calendar-unfreeze)
Raw form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>

FETCH (authoritative):
- src/research_orchestrator/holdout_seal.py                 (resolve_configured_global_holdout_root — fail-closed, project-root-relative)
- src/research_orchestrator/promotion_evidence.py           (no seal_store param; execution_lock over claim→compute→complete)
- src/alpha_research/factor_eval_skill/book_seal_stores.py  (A5ReproductionStore: run_dir/step_id + execution_lock; idempotent consume)
- src/alpha_research/factor_eval_skill/sealed_oos.py        (no sides/ls_floor)
- src/alpha_research/factor_eval_skill/orchestration.py     (FactorEvalContext: no holdout_seal_root; ALL governance stores canonical; resolve_factor drift)
- workspace/scripts/factor_eval_cli.py                      (no DEFAULT_HOLDOUT / holdout_seal_root)
- config.yaml                                               (research_governance.holdout_seal_root)
- tests/alpha_research/test_pr3_book_seal.py
- tests/alpha_research/test_factor_eval_skill_orchestration.py  (autouse canonical-root isolation)
- tests/research_orchestrator/test_promotion_evidence.py, test_r4_wall_hardening.py

YOUR R5 FINDINGS — how each was closed (verify in code):
B1 (public entry still forks the seal store + budget ledger) → the `seal_store` parameter is REMOVED
   from reproduce_sealed_oos; the seal store is UNCONDITIONALLY HoldoutSealStore(resolve_configured_
   global_holdout_root()). FactorEvalContext.holdout_seal_root is REMOVED (create() ignores it); the
   orchestration helper `_canonical_root()` resolves the configured root and cmd_seal uses it for the
   HoldoutSealStore (_seal_store), the OosWindowLedgerStore (both show and live, burned AND virgin — the
   burned-window denominator no longer reads ctx.store_root), the OverrideAuthorizationStore, and the
   FrozenSealAliasStore (_assert_not_already_spent). ctx.store_root now holds ONLY non-governance run
   artifacts (provenance/roles/stage-3 quality/the per-run envelope). The CLI --holdout-seal-root and
   DEFAULT_HOLDOUT are gone. Tests monkeypatch the RESOLVER (an autouse fixture isolates it per
   orchestration test; the r4 boom is injected by monkeypatching HoldoutSealStore, not a param).
B2 (CWD-relative + silent fallback) → resolve_configured_global_holdout_root now: anchors every relative
   config path on the PROJECT ROOT (not CWD); returns the canonical default only when the key is ABSENT
   or config.yaml is missing; and RAISES HoldoutRootResolutionError on unreadable/malformed config, a
   non-mapping top level, or a present-but-blank/non-string value — a misconfigured governance root fails
   closed instead of silently switching to a blank sealed world.
B3 (claimed state: no exclusive lock, no same-run binding) → A5ReproductionStore gains run_dir + step_id
   columns and an execution_lock(seal_key) (per-seal-key OS file mutex, same mechanism as the accepted
   BookSealArtifactStore.run_or_load_verdict). reproduce_sealed_oos holds it across read-state →
   consume/reserve/claim → compute → complete, so two runs can NEVER both enter the OOS computation: a
   concurrent run blocks, then sees the `complete` record and returns the persisted result. A still-
   `claimed` record resumes ONLY under the identical request AND allow_same_run=True AND the exact
   run_dir/step_id — a foreign run refuses (fail closed).
B4 (completed OOS re-judged with new floor/direction) → run_sealed_oos's `sides` and `ls_floor` public
   parameters are REMOVED; sides derive from the frozen set and the floor is the fixed module constant
   DEFAULT_LS_SHARPE_FLOOR. A caller who has seen the OOS metrics cannot re-judge a completed
   reproduction with a laxer floor or a flipped direction.
Major (new-frozen-set stage swallows drift) → the default resolver's resolve() now compares the REGISTRY
   row's stored definition_hash against the catalog hash; a drift or a blank stored hash raises
   FactorEvalError "definition drift ... record an explicit migration before creating a new frozen set",
   so a stale registry row can no longer be silently re-stamped with the live catalog hash to trivially
   satisfy the later reproduction definition-binding gate.
Minor (A5 consume same-request retry stranded) → consume_authorization is now idempotent-by-request: a
   retry of the SAME request that already consumed the authorization returns the prior record instead of
   raising; a DIFFERENT request is still refused. This closes the R4 residual-(a) crash window.

TEST STATE: 548 passed across the full affected suite (serial). Subsets fitting a 124s budget:
  pytest tests/alpha_research/test_pr3_book_seal.py tests/research_orchestrator/test_promotion_evidence.py tests/research_orchestrator/test_r4_wall_hardening.py -q   (~10s)
  pytest tests/alpha_research/test_factor_eval_skill_orchestration.py -q   (~3s)
A clean checkout without the gitignored data/ tree still fails a handful of data-dependent tests
(provider_build.json, screening metadata) — environment, not code.

SELF-REVIEW PREFLIGHT — VERDICT: clean for GPT round 6.
RESIDUAL CONCERNS (honest list):
(a) The execution_lock is held across the (minutes-long) OOS compute — intentional (one seal = one
    recipe = one computation), so a same-seal_key concurrent run blocks for the whole compute rather
    than racing. Different seal_keys never contend (per-key lock).
(b) A run that crashes while holding a `claimed` (not-complete) A5 record strands THAT seal_key until the
    SAME run_dir/step_id resumes with allow_same_run=True (crash recovery), or a human clears the record.
    Fail-closed (a foreign run can never re-execute) — the correct governance posture, at the cost of a
    manual step if the original run is truly dead.
(c) ctx.store_root still holds the per-run FrozenSelectionEnvelope (the sealed-selection identity record)
    and the provenance/role/stage-3 artifacts. The envelope is a run artifact retrieved for THIS run's
    output; it is NOT read by any budget / already-spent / multiplicity decision (those use the canonical
    seal store + alias store), so it is not a fork vector — but flagging the classification for your call.
(d) resolve_configured_global_holdout_root reads config.yaml on every call (no cache) — cheap, and keeps
    a monkeypatch seam simple; a process that rewrites config mid-run would see the new root on the next
    claim (not expected in practice).

REVIEW QUESTIONS
1. Re-run your R5 probes (new-root fork → canonical vs fork events; CWD-relative root; two concurrent
   resumers double-compute; completed-OOS re-judge with a new floor/direction; registry↔catalog drift at
   new-frozen-set creation; same-request consume retry). Any still land?
2. Is holding the execution_lock across the compute acceptable, or do you want the lock only around the
   state transitions with a separate "in-progress" guard for the compute?
3. Residual (b): is fail-closed manual recovery of a crash-orphaned claimed record acceptable, or must
   there be an automatic lease/timeout?
4. Residual (c): should the FrozenSelectionEnvelope also move to the canonical root, or is per-run
   storage correct since no governance decision reads it?
5. Anything else blocking SHIP for the machinery layer (the S6 governed runner + real-data burned-window
   pilot remain future PRs; live promotion is unreachable until a verifier registers).

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested
  replacement. Map every Blocker to the principle or invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
