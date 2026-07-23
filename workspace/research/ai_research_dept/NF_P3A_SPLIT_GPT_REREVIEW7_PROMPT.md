# GPT Cross-Review Request — NF integration P3a RE-REVIEW #7 (Tier-2, diff-scoped)

Round 7. Your round-6 verdict: the Unicode fix is correct (0 fusing codepoints on the new path vs 235
on the old; the structural enumeration test passes), but **1 P1** — the fix CHANGED the derived `fact`
content without bumping the artifact version, so a stale v2 artifact still verified while a corrected
regeneration collided with write-once. Folded.

**Commit under review: `d178b47`** on branch `calendar-unfreeze`. Tier-2 (frozen; Tier-1
crafted-object analysis out of tier — record as tracked notes or recommend a tier change to the user).

## The fold — and the rule it taught

`ARTIFACT_SCHEMA → nf_d7_split_v3`, `FACT_MODE → deterministic_whole_source_v2`. The verifier and the
schema-tracking filename now accept/produce only the current derivation, so a stale word-fused
artifact cannot be consumed and a corrected regeneration lands on its own path.

I had treated the Unicode fix as a "pure bug fix" and missed that it changed the derived content for
identical input. The rule is now recorded in the module:

> **Any change to how a sealed field is DERIVED bumps the artifact version — the version describes
> the content contract, not only the schema shape.**

The verifier's refusal message now names what each superseded version's `fact` text actually was
(v1: LLM-chosen/truncated; v2: word-fused across sanitizer-deleted characters).

## Regressions (all five verified to FAIL pre-fix)

- a **properly sealed** artifact at `v1`/no-`fact_mode`, at `v2`/`…_v1`, and at `v3`/`…_v1` is each
  refused (schema and derivation dimensions covered separately);
- the written path carries the `v3` prefix;
- a leftover `v2` file on disk no longer blocks the corrected `v3` write — the pre-fix run of this test
  fails with exactly the `SplitConflictError … refusing to overwrite` you predicted.

Tests: 38 P3a + full ai_research_dept **815** green.

## Files (pin to `d178b47`)

- https://raw.githubusercontent.com/henrydan111/quant-system/d178b47/workspace/research/ai_research_dept/engine/news_flash_split.py
- https://raw.githubusercontent.com/henrydan111/quant-system/d178b47/workspace/research/ai_research_dept/tests/test_news_flash_split.py

## Diff-scoped review questions

1. Does the v3 bump (schema + `fact_mode` + path) fully close the stale-artifact and write-once-
   collision problem, with no remaining door for an older-derivation artifact to be consumed?
2. **The generalized rule** — is "any derivation change bumps the version" correctly applied *here*,
   and is there anything else in P3a whose derivation is version-bearing but not yet covered by
   `fact_mode` (e.g. the `source_status` template text, the population predicate, the
   `content_hash` binding)? If a future edit to one of those would silently change sealed content, I
   would rather add it to the version now than discover it as another round.
3. **New surface:** anything the fold introduced that creates a new declared-invariant gap?
4. **Verdict:** SOUND-TO-PROCEED (to P3b) or a specific in-tier gap. If your remaining concerns are
   out-of-tier or tracked-debt in nature, please say SOUND-TO-PROCEED with them listed as notes.
