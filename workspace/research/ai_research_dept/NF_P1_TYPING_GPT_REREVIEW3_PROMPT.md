# GPT Cross-Review Request — NF integration P1 RE-REVIEW #3 (Tier-2, diff-scoped, budget ceiling)

Round 3 (final budgeted Tier-2 round) of the P1 news-flash typing driver review. Your round-2 verdict
was **REVISE — 1 declared-invariant gap** (the artifact path stamped only to the second, collapsing
sub-second and tz-offset cutoffs onto one identity). Folded. **This is the Tier-2 2-re-review-round
ceiling** — if a same-class gap remains, per protocol it goes to user arbitration rather than another
fold; a clean/only-out-of-scope verdict is SOUND-TO-PROCEED to P2.

**Commit under review: `750fcf3`** on branch `calendar-unfreeze`. Diff-scoped: does the fold close the
identity gap, and does it introduce new surface?

## The gap — FOLDED

`_artifact_path` stamped only `%Y%m%dT%H%M%S`, so `09:30:00.100000` and `09:30:00.900000` collapsed to
`...093000`, and `18:00+08:00` vs `18:00+09:00` collapsed to `...180000` — two distinct cutoffs sharing
one artifact identity (write-once then spuriously conflicts), violating "P2 reads by (cutoff,
ingest_class)".

Fix, per your recommendation:
1. **Canonicalize the cutoff ONCE at entry**, `text_store.to_cn_naive` (Shanghai wall-time, naive) —
   the same normalization `text_store` uses. That single `cut` drives `load_text`, the PIT re-assert,
   `cutoff_iso` (`cut.isoformat()`), and the path.
2. **Full-precision path**: `_artifact_path` canonicalizes and stamps
   `%Y%m%dT%H%M%S%f` (microseconds), so sub-second cutoffs stay distinct and tz-aware cutoffs resolve
   to their true Shanghai identity before formatting.

This also fixes a latent crash: a tz-aware cutoff previously made the PIT re-assert compare tz-naive
`datetime64` against a tz-aware `Timestamp` (`TypeError`); canonicalization resolves it.

Regressions (both verified to FAIL on the pre-fix module):
- `test_subsecond_cutoffs_do_not_collide` — `.100000` and `.900000` → distinct files;
- `test_tz_offset_cutoff_canonicalized_to_shanghai_identity` — `18:00+08:00` → `cutoff_iso
  2025-01-27T18:00:00` == naive `18:00` (idempotent, same file); `18:00+09:00` → `17:00:00`
  (distinct file).

## Files (pin to `750fcf3`)

- https://raw.githubusercontent.com/henrydan111/quant-system/750fcf3/workspace/research/ai_research_dept/engine/news_flash_typing.py
- https://raw.githubusercontent.com/henrydan111/quant-system/750fcf3/workspace/research/ai_research_dept/tests/test_news_flash_typing.py
- to_cn_naive: https://raw.githubusercontent.com/henrydan111/quant-system/750fcf3/src/data_infra/text_store.py (line ~127)

## Diff-scoped review questions

1. Does canonicalize-once + microsecond-precision path fully close the identity gap — any remaining
   pair of distinct cutoffs that map to one artifact path, or one cutoff that maps to two?
2. Is `cutoff_iso` (the canonical value stored in the artifact and consumed by P2) now the single
   source of identity, consistent with the path derivation, so P2 can key on it unambiguously?
3. **New surface from the fix:** does canonicalization or the `%f` stamp introduce any new
   declared-invariant issue (e.g. a naive-vs-aware edge, a DST/wall-time ambiguity in `to_cn_naive`
   that matters here, or a path that is no longer human-legible in a way that breaks an operator
   assumption)?
4. Verdict: SOUND-TO-PROCEED (to P2) or a specific remaining Tier-2 gap (which, at this ceiling, routes
   to user arbitration).
