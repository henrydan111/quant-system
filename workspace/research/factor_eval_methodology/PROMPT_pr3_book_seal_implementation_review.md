# PR3 (book-level promotion machinery) — GPT §10 implementation review prompt (ROUND 4)

R1 REWORK (5B/3M/1m) → folded. R2 REWORK (5B/3M) → folded. R3 REWORK (3B/1M/1m — A6 off-by-one,
A5 budget bypass + ledger forking, changed-recipe A5 resume, S6-registration forgeability, diagnostic
duplication) → **all folded**. R3 confirmed 6/8 prior findings closed. This round asks you to verify
the A5/A6 closure and re-probe. Branch: `calendar-unfreeze`.

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. ROUND-4 re-review of PR3: verify each R3 finding is genuinely closed (re-run your probes) and surface anything new. Do not rubber-stamp.

REPO (public) https://github.com/henrydan111/quant-system  (branch: calendar-unfreeze)
Raw form: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>

FETCH (authoritative):
- src/alpha_research/factor_eval_skill/stores.py            (inclusive boundaries; A6 inside reserve_a5)
- src/research_orchestrator/promotion_evidence.py           (canonical ledger; mandatory A5 request_hash)
- src/alpha_research/factor_eval_skill/book_seal_stores.py  (idempotent batch append_rows)
- src/research_orchestrator/registries/strategy_registry.py (profile resolution + verifier registry)
- src/alpha_research/factor_eval_skill/orchestration.py     (canonical virgin ledger in cmd_seal)
- src/alpha_research/factor_eval_skill/sealed_oos.py        (passthroughs; ledger_root REMOVED)
- tests/alpha_research/test_pr3_book_seal.py                (your R1+R2+R3 probes pinned)
- tests/research_orchestrator/test_r4_wall_hardening.py

YOUR R3 FINDINGS — how each was closed (verify in code; probes pinned as named tests):
B1 (A6 off-by-one) → BOTH comparisons are now INCLUSIVE (n_would_be >= hard / >= warn), matching
   virgin_window_multiplicity exactly, in reserve_book_spend AND the new A5 budget. Your two boundary
   probes are pinned: test_a6_boundaries_are_inclusive (2 existing -> 3rd needs ack; 4 existing -> 5th
   needs a consumed a6 authorization).
B2 (direct A5 bypasses budget + forks ledger) → the public ledger_root parameter is REMOVED from
   reproduce_sealed_oos / run_sealed_oos / cmd_seal: the A5 reservation goes to the CANONICAL ledger
   DERIVED from seal_root (OosWindowLedgerStore(seal_root) — colocated with the holdout store, so claims
   and budget rows cannot be split), and the A6 warn/hard bands are enforced INSIDE
   reserve_a5_study_spend under its lock (hard band requires a consumed a6_multiplicity authorization
   verified from the OverrideAuthorizationStore via require_consumed — the A5 access authorization never
   replaces A6's control). cmd_seal's virgin GOVERNING reports (pre-spend + final) now read the canonical
   ledger at holdout_seal_root. Pinned: test_direct_a5_hard_band_enforced_inside_reservation (your probe:
   4 prior spends + a valid A5 authorization -> the 5th direct claim refuses with no seal written) +
   test_reproduce_sealed_oos_virgin_authorizes_ledgers_then_claims (asserts the spend lands in the
   canonical ledger at seal_root; also pins that no ledger_root parameter exists).
B3 (changed-recipe A5 resume) → reproduce_sealed_oos computes a MANDATORY a5_request_hash over
   {frozen_set_hash, sorted factor_exprs, oos window, provider ids, horizon, n_quantiles, hypothesis_id}
   and binds it to: the authorization consumption (consumed_by_request_hash), the A5 reservation
   (request_hash now mandatory non-blank; blank legacy rows quarantined), the holdout claim
   (request_hash column; allow_same_run resume verifies persisted equality — the persisted-state
   machine you asked for), and the ResearchAccessContext. Your probe is pinned:
   test_direct_a5_changed_recipe_cannot_reuse_the_spend ($close/$open then $high/$low on the same
   seal -> the second recipe refuses at the reservation BEFORE any claim/compute; the identical recipe
   resumes). allow_same_run is retained but is inert for changed recipes (the persisted request_hash
   refuses); factor_exprs remain caller-supplied at this layer but are BOUND into the request hash —
   the full sealed-catalog derivation is disclosed as residual (b).
M1 (S6 registration forgeability) → the name-set is replaced by REGISTERED_GOVERNED_RUNNER_VERIFIERS
   (id -> VERIFIER CALLABLE, still empty); and INDEPENDENT of the verifier, the gate now resolves the
   attested profile against the REAL execution-profile registry: get_profile(execution_profile_id)
   (unknown id refuses), allowed_for_formal must be True, execution_profile_hash must equal the live
   profile_hash. Your probe (temporarily registering the runner name with profile 'exec_jq_daily'/hash
   'eph') now refuses at profile resolution. Pinned:
   test_fully_consistent_live_artifact_fails_closed_at_governed_runner (3 layers: forged profile ->
   "does not resolve"; REAL profile+hash -> "no REGISTERED governed-runner VERIFIER"; no attestation ->
   refused) + test_registered_verifier_with_real_profile_completes_the_chain (the S6 simulation:
   registering a VERIFIER + a real profile passes the full chain — what the S6 PR will do).
m1 (diagnostic duplication) → StrategyComponentDiagnosticStore.append_rows is BATCH-ATOMIC (one lock,
   one write) and IDEMPOTENT by (book_seal_key, request_hash, component_factor_id): replay returns the
   SAME ids with no duplicates; a divergent payload for the same key refuses. Pinned:
   test_append_rows_batch_idempotent_and_divergence_refused.

TEST STATE: 544 passed across the full affected suite (102 in the core trio + 442 across the wider set).
Your R3 clean-checkout notes: the 5 R4 failures need data/qlib_data/metadata/provider_build.json and the
1 factor-registry failure needs local screening metadata — both are LOCAL DATA prerequisites (gitignored
data/ tree), present on the operator machine; they are not code regressions. Subsets that fit a 124s
budget:
  pytest tests/alpha_research/test_pr3_book_seal.py tests/research_orchestrator/test_promotion_gate.py tests/research_orchestrator/test_r4_wall_hardening.py -q   (~35s)
  pytest tests/alpha_research/test_factor_eval_skill_orchestration.py tests/alpha_research/test_v14_book_level_promotion.py -q   (~50s)

SELF-REVIEW PREFLIGHT — VERDICT: clean for GPT round 4.
RESIDUAL CONCERNS (honest list):
(a) Authorization consumption precedes the reservation/enforcement checks — a refused attempt (changed
    recipe, budget band) WASTES the consumed authorization (conservative: re-record to retry). This also
    means an identical-recipe crash-resume consumes a fresh A5 authorization (the reservation itself is
    idempotent; only the consume-once record is spent). Acceptable, or should consumption move after the
    reservation inside one compound operation?
(b) factor_exprs at the reproduce layer are caller-supplied but recipe-bound (in the request hash and
    therefore in the seal/reservation/authorization). Deriving them from a sealed catalog manifest
    (definition-hash-verified) at THIS layer is not implemented — the catalog binding lives in the
    formal resolver path (definition-binding gate) upstream; cmd_seal resolves exprs from the catalog.
(c) The canonical A5/A6 ledger is colocated with the holdout seal root; a caller who forks seal_root
    forks BOTH stores together (claims + budget stay consistent within the fork) — the global-root
    configuration is the remaining trust anchor, same class as every store path in the repo.
(d) The A5 hard band uses require_consumed WITHOUT request binding (the a6 authorization for an A5 study
    is consumed by cmd_seal or manually before the reservation; binding it to the A5 request hash would
    require the consumer to know the hash pre-run). Scope+window binding is enforced.
(e) Book-runner diagnostics rows and A5 spends live in DIFFERENT ledgers when a dryrun book uses
    run-local stores (by design — dryrun isolation); live books + A5 studies share the canonical root.

REVIEW QUESTIONS
1. Re-run your R3 probes (5th-spend boundary / six-authorized-A5 sweep / forked ledger_root / changed-
   recipe resume / registered-name-only promotion / crash-duplicated diagnostics). Any probe still lands?
2. Is the canonical-ledger derivation (seal_root colocation) the right binding, or do you require a
   config-resolved global root independent of the seal_root argument?
3. Residuals (a)-(e): acceptable for the machinery layer, or does any block SHIP?
4. Anything else blocking SHIP (the S6 governed runner + real-data burned-window pilot remain explicitly
   future PRs; live promotion is unreachable until a verifier is registered).

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested
  replacement. Map every Blocker to the principle or invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
