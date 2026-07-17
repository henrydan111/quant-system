# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #4 (archive boundary, re-review#3 folded)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat.
Re-review #3 returned **FIX-FIRST: 1 Blocker (P0) + 1 Major (P1)**. Both folded; your
probes replayed as regressions against the fix. Commit under review: `5b74954` on
branch `calendar-unfreeze`.

Your P0 prescription, folded: "A real fix needs a commitment authority that cannot be
invoked with arbitrary terminal/outcome hashes." Your P1 prescription, folded:
"Require commitment.entry_hash to be on the ancestry path ending at
ledger_head_at_seal; add a regression for an earlier-but-valid decision-row anchor."

## Files (embedded text authoritative; links for live cross-check)

- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_executors.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/engine/news_decision.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/tests/test_news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/workspace/research/ai_research_dept/tests/test_news_executors.py

Unchanged context: `news_legs.py`, `news_horizon.py`, `news_cards.py`,
`news_evidence.py`, `news_seal.py` on the same branch.

## How P0 was folded

**The naked-hash door no longer exists.** `record_execution_commitment` is deleted
(`test_naked_hash_commitment_api_is_gone`). The low-level chain append is
module-private (`_append_commitment_row` in `news_decision.py`), and the only
sanctioned door is the **deriving commitment authority**
`news_executors.commit_execution(ledger_dir, prov_dir, *, decision_id, execution_id,
outcome, artifact, contract)` — its public surface accepts NO hashes. It re-verifies
the artifact (`verify_d7_artifact`), rebuilds the canonical leg payloads (ledger gate
included), re-runs `verify_outcome_for_binding`, resolves the unique
state-machine-connected terminals from the on-disk provenance file
(`_resolve_terminal`), and fully checks each resolved row via the SHARED
`_check_terminal_row` — row schema, entry_hash recompute, leg binding, identity,
contract schema, verdict↔status semantics, payload-hash equality against the rebuilt
payload, and the deterministic_zero population biconditional. The archive verification
now calls the SAME `_check_terminal_row` (plus bundle-row == resolved-row equality),
so the authority and the archive can never diverge semantically. Only after all of
that does the authority append the hashes IT resolved. A caller chooses WHICH
execution gets verified; it cannot choose WHAT gets committed.

**New ledger invariant — one canonical success execution per decision.** Commitment
rows now carry `news_status` (`success` | `hard_failed`); at most ONE success
commitment may exist per decision, enforced both at append (`_append_commitment_row`)
and at chain read (`_read_chain` fails closed on a chain carrying two). `hard_failed`
commitments remain unlimited (crash/retry audit trail), so hard-fail → success retry
keeps working (`test_hard_fail_then_success_retry_recovers`,
`test_retry_after_hard_fail_binds_own_attempt`).

**Your probe, replayed against the fix**
(`test_gpt_probe_forged_fresh_execution_cannot_commit`): fresh
`d1:api_forged_0001`, state-machine-valid fake terminals written through the callable
writer, then the commitment authority — refused by the unique-success rule, because
the REAL execution already committed this decision's one success. Downstream
consequences pinned: a second success execution of a committed decision is refused at
the ledger before it ever reaches the archive
(`test_second_success_execution_refused_at_commitment`); archives require
`commitment.news_status == outcome.news_status`; a sealed hard-fail archive is
SUPERSEDED (refuses to load) once the decision's unique success commitment lands
(`test_sealed_hard_fail_archive_superseded_by_success`) — fabricated records can no
longer reach any load return value through the P0 path.

**Stated trust boundary** (consistent with your R2 answer 1, not hidden): in-process
Python has no privilege boundary — underscore-private is convention, and an attacker
who runs the FULL pipeline first (e.g. `execute_news_decision` with a mock LLM
`call_fn`, or hand-built terminals + the authority BEFORE the real execution ever
runs) wins the first-write race. That is the same trust model as `record_decision`
itself: the hash chain is the arbiter of what happened first, and the process that
executes decisions is trusted. What the fold guarantees: no API accepts unverified
hashes; everything committed is derived from verified on-disk + rebuilt state; and
once the real execution has committed, no forged execution can displace or shadow it.

## How P1 was folded

`load_and_verify_decision_archive` now locates the anchored head ROW in the current
chain (membership, genesis still impossible) and additionally requires this
execution's commitment row to lie on the ancestry path ending at the anchor — on a
validated linear chain (physical seq + prev_hash + per-row seal), ancestry ⟺
`commitment.seq <= anchor.seq`. Your earlier-but-valid decision-row anchor probe is
pinned (`test_anchor_downgrade_to_earlier_chain_member_refused`); genesis downgrade
remains pinned separately.

## Self-review (completed before this request)

Verdict: **clean for GPT**. Naked-hash-door class sweep across the NF engine: no
remaining public function accepts caller hashes into an authoritative store
(`record_decision` derives from the artifact object; `NewsLegOutcome` self-validates +
is re-verified against rebuilt payloads; `seal_decision_archive` re-derives
everything). Membership-vs-ancestry class sweep: the payloads' `ledger_entry_hash` is
full-field-compared via `require_recorded` (not membership), the commitment is a key
lookup + now ancestry-bound; no other membership-only anchor remains. Suites: 767
green (NF 666 + ai_layer 50 + text/harness 51).

## Review questions

1. Is P0 closed to the achievable in-process standard — i.e., does any API path
   remain by which a caller can influence WHAT hashes get committed (rather than
   which verified execution gets committed), and is the unique-success-per-decision
   invariant sound (append-time + read-time) against interleavings you can construct?
2. The supersession rule (hard-fail archive refuses to load once a success
   commitment exists) and the retry path (hard_failed commitments unlimited) — any
   exploitable gap between them, e.g. an attacker parking a forged hard_failed
   commitment/archive to grief a decision, or a legitimate flow that is now
   wrongly bricked?
3. Is the ancestry check complete (seq-based ancestry on a validated linear chain),
   or can an anchor still be moved to any point that misrepresents the seal-time
   chain state in a way that matters?
4. The stated trust boundary (first-write race + trusted executor process) — is it
   the correct residual boundary for this unit, with the outer archive-root pinning
   and immutable sealing layer deferred to the four-seat integration as agreed?
5. Verdict: SOUND-TO-PROCEED (to the four-seat session-archive embedding) or further
   findings — with reproduced probes for anything you flag.
