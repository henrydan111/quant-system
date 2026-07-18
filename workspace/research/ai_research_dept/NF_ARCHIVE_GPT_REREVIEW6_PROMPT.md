# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #6 (archive boundary, re-review#5 folded)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat.
Re-review #5 returned **FIX-FIRST: 1 × P0 (contract not bound into the commitment) +
1 × P2 (recovery not idempotent under chain growth)**, with the per-execution
archive / canonical-success / single-snapshot fixes from #4 confirmed effective.
Both findings folded per your prescriptions. Commit under review: `770bce1` on
branch `calendar-unfreeze`.

## Files (embedded text authoritative; links for live cross-check)

- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_executors.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_decision.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/tests/test_news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/tests/test_news_executors.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/NF_SEAL_HARDENING.md

Unchanged context: `news_legs.py`, `news_horizon.py`, `news_cards.py`,
`news_evidence.py`, `news_seal.py` on the same branch.

## How P0 was folded — the contract is hash-bound into the commitment

Your root cause: the commitment bound only `factor_entry_hash / penalty_entry_hash /
outcome_hash / news_status`, and `outcome_hash` does not cover
`primary_decision_horizon` — so a same-schema/same-mode/different-primary contract
could legally seal or recover a different primary score (your 49.0 → 69.0 probe)
and permanently occupy the execution's write-once archive slot. Folded exactly as
prescribed:

- **Commitment rows now embed the FULL immutable contract payload +
  `contract_hash`** (`_append_commitment_row` requires the pair; pair
  self-consistency `seal_hash(contract) == contract_hash` is validated at append
  AND at every `_read_chain` — a hand-written chain row with an inconsistent pair
  fails the whole chain read; both fields participate in first-write-wins
  idempotency comparison). Persisting the payload (not just the hash) means
  pure-disk recovery can self-certify the committed contract rather than merely
  validate a caller-supplied one.
- **Every door requires supplied-contract == committed-contract byte-for-byte**:
  `commit_execution` writes its own contract; `verify_execution_bundle` — the one
  verification shared by `seal_decision_archive` and BOTH loaders — refuses on
  `contract_hash` or payload mismatch; `recover_and_seal_success_archive`
  pre-checks the same equality at entry, BEFORE resolving terminals or touching
  any file.
- **Your two required regressions, plus one**:
  `test_seal_with_different_primary_horizon_refused` (direct-seal form, evaluation
  consistently recomputed under the substitute contract so the binding is the
  kill; asserts the archive dir stays EMPTY),
  `test_recovery_with_different_primary_horizon_refused` (refuses before writing;
  recovery under the committed contract still succeeds afterwards),
  `test_load_requires_committed_contract` (the substitute contract cannot read the
  canonical archive either).

## How P2 was folded — recovery is idempotent under legitimate chain growth

`recover_and_seal_success_archive` now: (1) finds the unique success commitment on
its single chain snapshot, (2) checks the contract equality (P0), then (3) **if the
execution's archive file exists → load, fully verify, and return it** — no rebuild,
so a later `ledger_head_at_seal` can never trigger a write-once refusal; only a
missing archive is rebuilt and sealed. Pinned:
`test_recovery_idempotent_after_chain_growth` (seal → append unrelated decision →
recover returns the existing archive verbatim).

## Also folded

Your answer-4 convention is now a BINDING requirement in NF_SEAL_HARDENING.md's
final-integration list (#7): decision consumers use ONLY
`load_and_verify_decision_archive`; `load_and_verify_execution_archive` is
audit-display only (scope=execution_audit) and must never feed the four-seat
session archive as the decision's outcome.

## Self-review (completed before this request)

Verdict: **clean for GPT**. Unbound-archive-field sweep: every archive field is now
anchored by at least one of {ledger commitment (ids, terminal hashes, outcome_hash,
news_status, contract), artifact identity chain (artifact/bundle/registry hashes,
which the decision registration row binds via `require_recorded`), outcome_hash
(outcome payload incl. output_mode), deterministic recomputation (evaluation, from
committed contract + bound records + bound registry), ancestry anchor
(ledger_head_at_seal)} — no field can vary while all anchors hold. Check order
verified: a substitute contract with consistently recomputed evaluation passes the
evaluation compare and dies at the commitment-contract equality (pinned). Suites:
776 green (NF 675 + ai_layer 50 + text/harness 51).

## Review questions

1. Is P0 closed — does any path remain by which the effective scoring semantics
   (contract fields, or anything else `outcome_hash` does not cover) can differ
   between what was committed at execution time and what a sealed/loaded archive
   presents?
2. Is the commitment's anchor set now complete, or can you name an archive-visible
   fact that is still bound by nothing (commitment / artifact chain / outcome_hash
   / recomputation / ancestry)?
3. Recovery: with the committed contract persisted in-chain and the
   archive-exists → load-and-return short-circuit, is recovery now (a) idempotent
   in all legitimate orderings and (b) still incapable of sealing an archive that
   diverges from what the crashed execution would have sealed?
4. Any regression introduced by the new checks themselves (e.g. legitimate flows
   now wrongly refused — contract evolution across a chain version bump would mint
   a NEW decision under the new frozen manifest, so committed-contract equality
   should never block a legitimate load; do you agree)?
5. Verdict: SOUND-TO-PROCEED (to the four-seat session-archive embedding) or
   further findings — with reproduced probes for anything you flag.
