# GPT Cross-Review Request — NF integration P1 RE-REVIEW #2 (Tier-2, diff-scoped)

Round 2 of the Tier-2 review of the P1 news-flash typing driver. Your round-1 verdict was
**CHANGES-REQUIRED — 2 blockers**, both folded. Per our convergence protocol, from round 2 the review
is **diff-scoped**: (a) does the fold close the two blockers, and (b) does the fix introduce new
surface of its own? (This is the P1 unit's round budget; a clean/only-out-of-scope verdict here is
SOUND-TO-PROCEED to P2.)

**Commit under review: `<HEAD>`** on branch `calendar-unfreeze` — the raw links below pin to the
pushed commit; the working commit is the one whose SHA the assistant reports on push (fold of the two
blockers + a comment correction). **Tier-2** — declared-invariant review, not adversarial-caller
analysis.

## Blocker 1 — missing forward store silently → zero-news. FOLDED.

`type_day_flashes` now passes `require_exists` to `load_text`, and the **forward panel is always
fail-closed**: `req = ingest_class == "forward" or bool(require_exists)`. A missing forward store
raises `TextStoreError`, never a valid NON_EVIDENTIARY empty artifact. `history_bulk` replay stays
tolerant by default (opt-in `require_exists`) because a never-backfilled bulk day is legitimately
empty. An EXISTING forward panel with no rows before `cutoff` still yields a real empty artifact.

Regressions: `test_missing_forward_store_raises` (no typer call, raises),
`test_existing_forward_panel_empty_before_cutoff` (exists + empty → empty artifact, no LLM),
`test_missing_history_bulk_store_tolerated`.

## Blocker 2 — artifact not immutable + collided across cutoffs. FOLDED.

`_artifact_path` now carries the **full cutoff timestamp** (`YYYYmmddTHHMMSS`), so 09:30 and 18:00 on
the same day are distinct files. `write_typed_flash_artifact` is **write-once / first-write-wins**
under a `file_lock` (same pattern as `seal_decision_archive`): an identical re-write is idempotent; a
re-typing with different valid content is refused with `TypedFlashConflictError` instead of silently
overwriting a possibly-consumed version. The docstring records the downstream contract: **P2 reads by
(cutoff, ingest_class) and binds the verified `artifact_sha256`; P4 binds the consumed SHA into the
sealed decision.**

Regressions: `test_different_cutoffs_same_day_distinct_files`,
`test_write_once_refuses_different_content` (idempotent identical; refuse different).

All three blocker regressions were verified to **FAIL on the pre-fix module**. The inaccurate
"syndicated copies share one type" comment you flagged was corrected (the store's content basis is
`[src, datetime, title, content, channels]`, so same wording at a different time/outlet is a distinct
`content_hash`).

## Files (pin raw links to the pushed commit `68e96cf` for the fold; the comment fix is one commit later)

- https://raw.githubusercontent.com/henrydan111/quant-system/68e96cf/workspace/research/ai_research_dept/engine/news_flash_typing.py
- https://raw.githubusercontent.com/henrydan111/quant-system/68e96cf/workspace/research/ai_research_dept/tests/test_news_flash_typing.py
- PIT gate (require_exists semantics): https://raw.githubusercontent.com/henrydan111/quant-system/68e96cf/src/data_infra/text_store.py

## Diff-scoped review questions

1. Does forward's hard `require_exists=True` fully close Blocker 1, and does the forward-vs-bulk split
   leave any path where a missing/unavailable forward source is still read as empty?
2. Does full-cutoff pathing + write-once/first-write-wins fully close Blocker 2? Is the file_lock the
   right serialization, and does the equality check (`existing == artifact`) correctly distinguish
   idempotent from conflicting writes?
3. **New surface from the fix:** does anything the fold introduced (require_exists branch, conflict
   error, lock, full-cutoff filename) create a new declared-invariant gap — e.g. a cutoff whose
   `strftime` is ambiguous, a lock left behind, or a history_bulk path that should also be fail-closed?
4. Verdict: SOUND-TO-PROCEED (to P2) or a specific remaining Tier-2 gap.
