# GPT Cross-Review Request — NF Final-Integration Unit 1 RE-REVIEW #15 (archive boundary, assert-before-read + independent verified snapshot)

You are re-reviewing the **decision-archive boundary** of the news-flash (NF) seat. Your
previous verdict (on `e0a1dcb`) was **REVISE — 1 P1**: the archive boundary still verified a
live object and then wrote from the live object. Folded. **Commit under review: `15318c6`** on
branch `calendar-unfreeze`.

Your finding, verbatim intent:
- `verify_execution_bundle()` called `_rebuild_leg_payloads()` (reading
  `outcome.penalty_leg_status`) BEFORE `assert_base_outcome_fields()` ran. A malicious outcome
  could, in that read, (1) restore its own fields to plain str so the later assert passes, and
  (2) swap `bundle["outcome"]` to a self-consistent `vector_only` outcome; `seal_decision_
  archive()` then re-read the outcome from the live `bundle` and wrote the swapped one →
  archive `vector_only`, reload rejected, correct re-seal blocked by write-once.
  `commit_execution()` had the same read-then-assert ordering. Both prescriptions:
  (a) assert immediately after the exact-type check, before any field read;
  (b) verify produces an independent type-closed snapshot; the serialization consumes only it
  (restricting `bundle` to a plain dict is not enough).

## Files (embedded text authoritative; links pin to `15318c6`)

- https://raw.githubusercontent.com/henrydan111/quant-system/15318c6/workspace/research/ai_research_dept/engine/news_archive.py
- https://raw.githubusercontent.com/henrydan111/quant-system/15318c6/workspace/research/ai_research_dept/engine/news_executors.py
- https://raw.githubusercontent.com/henrydan111/quant-system/15318c6/workspace/research/ai_research_dept/engine/news_legs.py
- https://raw.githubusercontent.com/henrydan111/quant-system/15318c6/workspace/research/ai_research_dept/engine/news_evidence.py
- https://raw.githubusercontent.com/henrydan111/quant-system/15318c6/workspace/research/ai_research_dept/engine/news_cards.py
- https://raw.githubusercontent.com/henrydan111/quant-system/15318c6/workspace/research/ai_research_dept/tests/test_news_archive.py

## How it was folded

**(a) assert-before-read.** `assert_base_outcome_fields(outcome)` now runs IMMEDIATELY after the
`type(outcome) is not NewsLegOutcome` check in both `verify_execution_bundle` and
`commit_execution`, before `verify_d7_artifact` / `_rebuild_leg_payloads` or any outcome field
read. The assert uses `type(getattr(outcome, f)) is not str` / `is not bool` / `is not int`,
which never invokes the field value's methods — so an evil field is refused before its
comparison/canon side effect can fire (pinned: an evil `penalty_leg_status` with a
side-effecting `__eq__` is refused and its `__eq__` is never called).

**(b) independent verified snapshot.** `verify_execution_bundle` now returns a `"verified"`
snapshot that seal consumes exclusively:
- `outcome`: RECONSTRUCTED as a fresh `NewsLegOutcome(**canonical fields)` — de-aliased from
  `bundle["outcome"]`; its `__post_init__` re-derives the M3⁴ matrix and re-verifies
  `outcome_hash`.
- `execution_id`: the validated local str.
- `evaluation`: the RECOMPUTED value (M2⁴), not `bundle["evaluation"]`.
- `records`: a JSON deep-snapshot (de-aliased).
- `selected_provenance`: the disk-RESOLVED terminal rows (`_resolve_terminal`), not the
  bundle-supplied ones.
`seal_decision_archive` now reads `verify_execution_bundle(...)["verified"]` and builds the
archive payload from it — it never re-reads `bundle["outcome"]` / `["evaluation"]` /
`["records"]` / `["selected_provenance"]` / `["execution_id"]`. `load_and_verify_decision_
archive` still uses `["commitment"]` from the same return, unchanged.

## Regressions pinned

- `test_evil_outcome_field_refused_before_any_field_read`: an evil `penalty_leg_status` (side-
  effecting `__eq__`) is refused at the top of `verify_execution_bundle`, and its `__eq__` is
  never invoked (the swap side effect cannot fire).
- `test_seal_consumes_independent_verified_snapshot`: the `verified` outcome is a distinct
  object from `bundle["outcome"]` with the same `outcome_hash`; seal writes the snapshot and the
  archive reloads cleanly under the contract.

## Self-review (completed before this request)

Verdict: **clean for GPT**. Verify-live-write-live sweep: `seal_decision_archive` and
`recover_and_seal_success_archive` are the archive writers; seal now consumes only the verified
snapshot; recovery already rebuilds the bundle from pure on-disk state + the ledger commitment
(never the caller's live bundle). Assert-before-read: both `verify_execution_bundle` and
`commit_execution` assert outcome fields before any read; `verify_outcome_for_binding` keeps its
own assert as defense-in-depth. Full suite: 800 green (NF 699 + ai_layer 50 + text/harness 51).
This self-review does NOT substitute for your gate.

## Review questions

1. Is the verify-live/write-live class now closed — does any archive writer still read a
   security-relevant value from the live `bundle` (or any caller-held mutable) rather than from
   the independent verified snapshot / on-disk resolved state?
2. Is the assert-before-read ordering complete — is there any outcome (or other sealed-object)
   field read in `verify_execution_bundle` / `commit_execution` that still precedes its
   consume-time base-type assert?
3. Is the reconstructed `verified["outcome"]` genuinely independent and faithful — can the
   reconstruction itself be steered (its inputs are read from the same live outcome after the
   assert; the assert guarantees plain fields, and the reconstruction re-derives the matrix +
   re-verifies outcome_hash — do you agree that closes it)?
4. Any regression from routing seal through the snapshot (evaluation now the recomputed value;
   selected_provenance now the disk-resolved rows; records JSON round-tripped) — the full suite
   is green, including the normal/zero/hard-fail round trips.
5. Verdict: SOUND-TO-PROCEED (to the four-seat session-archive embedding) or further findings —
   with reproduced probes for anything you flag.
