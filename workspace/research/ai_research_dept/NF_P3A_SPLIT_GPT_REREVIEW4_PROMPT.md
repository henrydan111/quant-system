# GPT Cross-Review Request — NF integration P3a RE-REVIEW #4 (Tier-2, diff-scoped)

Round 4 of the Tier-2 P3a review. Your round-3 verdict: **1 P1 open** — "full sentence" is still not a
reliable fact-context boundary (neighbouring-sentence qualifier, headline/body newline, `U.S.`
abbreviation), with the recommendation to either use the **whole hash-bound source** for `fact` or
defer the scoring attribute pending a formal grounding scheme. Folded — I took the whole-source
option, and it had a consequence worth your attention.

**Commit under review: `f83ddca`** on branch `calendar-unfreeze`. Tier-2 (frozen; Tier-1
crafted-object analysis remains out of tier — record such findings as tracked notes, or recommend a
tier change to the user).

## The fold — and why P3a v1 is now DETERMINISTIC (no LLM at all)

`fact` is now the **whole hash-bound source, sanitized**. Nothing is truncated, so no qualifier —
same-sentence, neighbouring-sentence, across a newline, or before an abbreviation — can be lost. The
sentence-expansion machinery (`_enclosing_sentence`, `_TERMINATORS`, `_is_period_boundary`) is deleted.

The consequence: with `fact` = whole source, `economic_linkage` and `timing` deferred, and
`source_status` derived from the verified typing, **the model has nothing left to contribute**. So the
LLM is removed entirely:

- `split_day_flashes(cutoff, *, ingest_class, assessed_artifact, source_rows)` — **no `call_fn`, no
  `batch`**; `_extract_batch` and the prompt are gone.
- A meta-test asserts the API accepts no `call_fn`/`batch` and that `_extract_batch` no longer exists,
  so an extraction step cannot quietly reappear.
- The artifact records `fact_mode = "deterministic_whole_source_v1"` so audit/downstream knows the
  attribute's provenance without re-deriving it.
- Zero hallucination surface, zero LLM cost, and `artifact_sha256` reproducible by construction.

This also corrects a cost estimate I had given: P3a contributes **0** LLM calls, not one per
`importance>=4` flash.

## What is unchanged (and was confirmed in your earlier rounds)

- **P0 binding** — `_bind_source_rows` recomputes each row's canonical `content_hash`
  (`text_store.content_hash_for`) and binds only rows matching a P2 population hash; substituted/future
  text refuses. CLI `load_text` + recomputation accepted (no sealed snapshot required).
- **Population derived** — `{evidence_class ∈ {NFD,NFI,NFA}} × {importance >= D7 floor}`, exactly what
  `verify_d7_artifact`'s coverage gate will demand.
- **`source_status` derived** from `verification_status`/`is_rumor` (PENALTY path, never model-authored).
- **Write-once immutable artifact** on the canonical microsecond-cutoff path; full verifier for dict or
  path.

## Regressions

Neighbouring-sentence qualifier ("公司否认该报道。…"), same-sentence negation ("It is false that …"),
headline/body newline, and an `U.S.` abbreviation case are all preserved in `fact`; plus the
population, binding, identity, source_status, persistence and empty-population tests. 19 P3a + full
ai_research_dept **796** green.

## Files (pin to `f83ddca`)

- https://raw.githubusercontent.com/henrydan111/quant-system/f83ddca/workspace/research/ai_research_dept/engine/news_flash_split.py
- https://raw.githubusercontent.com/henrydan111/quant-system/f83ddca/workspace/research/ai_research_dept/tests/test_news_flash_split.py

## Diff-scoped review questions

1. Does `fact` = whole sanitized hash-bound source close the de-contextualization class **by
   construction** (nothing truncated ⇒ nothing to lose), or is there a residual — e.g. does
   `sanitize_text` itself remove anything semantically load-bearing?
2. Is removing the LLM the right consequence, or do you see a reason to keep an extraction step in v1?
   (The D7 rebuild makes `fact` mandatory, so it could not simply be deferred like `economic_linkage`.)
3. Is a whole-flash `fact` acceptable to the downstream contract — `_build_attribute_records` /
   `verify_d7_artifact` / the factor-leg payload — or does any consumer assume a short attribute text?
4. **New surface:** anything the fold introduced (whole-source attribute, deleted machinery, the
   `fact_mode` field, the no-LLM meta-test) that creates a new declared-invariant gap?
5. **Verdict:** SOUND-TO-PROCEED (to P3b) or a specific in-tier gap.
