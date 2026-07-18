# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #7 (archive boundary, re-review#6 folded)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat.
Re-review #6 returned **FIX-FIRST: 1 × P0 (subclass `_payload()` override decouples
the committed contract from the fields the evaluator reads) + 1 × P2 (recovery race
window)**, with the #5 contract-binding and serial-idempotency fixes confirmed
effective. Both folded per your prescriptions, and the invariant class was swept to
the outcome side. Commit under review: `1527f7f` on branch `calendar-unfreeze`.

## Files (embedded text authoritative; links for live cross-check)

- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_executors.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_legs.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_decision.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/tests/test_news_archive.py

Unchanged context: `news_horizon.py`, `news_cards.py`, `news_evidence.py`,
`news_seal.py` on the same branch.

## How P0 was folded — exact-type boundaries + non-virtual canonical payloads

Your prescriptions, folded in full:

1. **All public doors are exact-type.** `require_exact_contract` enforces
   `type(contract) is NewsScoringContract` at `execute_news_decision` (the runner),
   `commit_execution`, `verify_execution_bundle` (which seal and BOTH loaders run),
   and `recover_and_seal_success_archive`. The same invariant class on the outcome
   side is closed too: `type(outcome) is NewsLegOutcome` at
   `verify_execution_bundle`, `commit_execution`, and
   `news_legs.verify_outcome_for_binding` (an `_EvilOutcome` subclass whose
   overridden payload flips `news_status` is refused at the joint verification —
   pinned).
2. **Security-boundary payloads never go through a virtual method.** Module-level,
   non-overridable canonical helpers read the actual fields:
   `contract_canonical_payload` (news_executors) and `outcome_canonical_payload`
   (news_legs). Every boundary `._payload()` call is replaced — the commitment
   write, the commitment equality in `verify_execution_bundle`, the archive seal
   payload, the archive load contract/outcome equalities, the recovery pre-check,
   and the `outcome_hash` verification in `verify_outcome_for_binding`. A repo grep
   for `contract._payload()` / `outcome._payload()` returns zero hits; the only
   remaining `self._payload()` calls are the classes' own `__post_init__`
   self-seals, which the exact-type doors make trustworthy (only genuine instances
   can reach any door).
3. **Your subclass regression, pinned at every door**: an `_EvilContract` with
   fields `1-3d` and an overridden payload claiming `next_open` is refused at the
   runner BEFORE anything is written (asserted: no provenance file exists, the
   ledger contains only decision rows), at seal and at recovery (asserted: the
   archive dir stays empty), and at the commit authority
   (`TestExactTypeBoundaries`, 4 tests + the outcome probe).

## How P2 was folded — race-safe recovery

The write-once conflict inside `seal_decision_archive` is now the typed
`ArchiveWriteOnceConflictError` (a `RegistryError` subclass, distinct from
verification failures — only the content-differs branch raises it).
`recover_and_seal_success_archive` catches exactly that error after its rebuild and
**returns the existing archive after a full `load_and_verify_execution_archive`** —
first-writer-wins, the losing recovery converges to the winner's archive instead of
erroring. Your interleaving is replayed deterministically:
`test_recovery_race_loser_returns_existing_archive` injects a competitor seal plus
unrelated ledger growth between recovery's entry exists-check and its rebuild (via
a self-disarming hook on the provenance read), and asserts the losing recovery
returns the competitor's archive verbatim. The serial-growth idempotency regression
from #5 still passes unchanged.

## Self-review (completed before this request)

Verdict: **clean for GPT**. Virtual-call-across-boundary sweep: zero
`contract._payload()` / `outcome._payload()` call sites remain in the engine;
`isinstance(contract, …)` / `isinstance(outcome, …)` no longer appears at any door
(all exact-type). Other sealed classes (D7 artifact family, registry, card) are not
archived via their `_payload()` across this unit's boundary — the archive stores
only their HASHES, which `verify_d7_artifact`'s full reconstruction re-derives from
base data on every load, so a subclass faking attributes there fails hash
reconstruction rather than smuggling content; noted as the reasoned scope limit.
Suites: 781 green (NF 680 + ai_layer 50 + text/harness 51).

## Review questions

1. Is P0 closed — can any object whose virtual behavior a caller controls still
   influence what gets hashed into the commitment or archive versus what the
   evaluator/verifier actually reads (contract, outcome, or any other type crossing
   these doors)?
2. Is the reasoned scope limit for the artifact family sound (hashes +
   full-reconstruction verification instead of exact-type doors), or can you
   construct a D7/registry/card subclass that survives `verify_d7_artifact` while
   presenting different archived content?
3. Is the P2 convergence correct — the losing recovery returns the winner's
   verified archive in all orderings you can construct, and the typed conflict
   cannot mask a genuine verification failure (only the content-differs write-once
   branch raises it)?
4. Any regression introduced by the exact-type doors themselves (legitimate flows
   that previously passed real instances still pass — the full suite is green; do
   you see a legitimate polymorphic use these doors now block)?
5. Verdict: SOUND-TO-PROCEED (to the four-seat session-archive embedding) or
   further findings — with reproduced probes for anything you flag.
