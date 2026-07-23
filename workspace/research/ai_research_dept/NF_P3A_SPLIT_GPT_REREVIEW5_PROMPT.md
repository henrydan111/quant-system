# GPT Cross-Review Request — NF integration P3a RE-REVIEW #5 (Tier-2, diff-scoped)

Round 5 of the Tier-2 P3a review. Your round-4 verdict: the whole-source + no-LLM direction is right
and the downstream contract accepts it, but **1 P1 + 1 P2** — the new contract was not enforced at the
read boundary, and the sanitizer fused words across newlines. Both folded.

**Commit under review: `bcd7d40`** on branch `calendar-unfreeze`. Tier-2 (frozen; Tier-1
crafted-object analysis out of tier — record as tracked notes or recommend a tier change to the user).

## P1 — the contract is now ENFORCED, not merely recorded

You were right that this was the load-bearing gap: everything the arc eliminated could still flow into
P3b through an old artifact.

- `ARTIFACT_SCHEMA` bumped to **`nf_d7_split_v2`** — the CONTRACT changed, so the name must.
- `verify_split_artifact` now **requires the exact `fact_mode == "deterministic_whole_source_v1"`**;
  any other mode (or a missing one) is refused with a distinct message.
- The artifact **filename tracks the schema** (`nf_d7_split_v2_{class}_{stamp}.json`), so a stale v1
  file cannot occupy a v2 path (and cannot collide with write-once).

Regressions: a genuine v1-shaped artifact **properly re-sealed** (schema `v1`, no `fact_mode`) is
refused; a properly re-sealed artifact claiming `fact_mode="llm_span_v0"` is refused; the path carries
the `v2` prefix.

## P2 — newlines no longer fuse words

`_LINE_SEP_RE = re.compile(r"[\r\n  ]+")` replaces line separators with a **space BEFORE**
the frozen sanitizer runs (the sanitizer deletes control characters, which is what fused
`"does\nnot"` into `"doesnot"`). Regression: an English newline yields `"does not"`, never
`"doesnot"`; the existing CN headline/body newline case still keeps both halves.

All three new regressions were verified to **FAIL on the pre-fix module**. Tests: 22 P3a + full
ai_research_dept **799** green.

## Files (pin to `bcd7d40`)

- https://raw.githubusercontent.com/henrydan111/quant-system/bcd7d40/workspace/research/ai_research_dept/engine/news_flash_split.py
- https://raw.githubusercontent.com/henrydan111/quant-system/bcd7d40/workspace/research/ai_research_dept/tests/test_news_flash_split.py

## Diff-scoped review questions

1. Is the read-boundary enforcement complete — schema v2 + exact `fact_mode` + schema-tracking
   filename? Any other door through which a v1/other-mode artifact could reach a consumer (e.g. a
   consumer that reads the JSON without calling `verify_split_artifact`)?
2. Is replacing line separators with a space before sanitizing the right normalization, and is the
   separator set adequate (CR, LF, U+2028, U+2029) — anything else the sanitizer deletes that would
   fuse tokens (e.g. U+0085 NEL, tabs, zero-width joiners)?
3. **New surface:** anything the fold introduced that creates a new declared-invariant gap?
4. **Verdict:** SOUND-TO-PROCEED (to P3b) or a specific in-tier gap.

## Note on the arc

This is round 5. Each round has found a *different* real defect and the unit has converged toward
strictly simpler and safer (free-written text → verbatim span → sentence expansion → whole source +
no LLM → contract enforced at the read boundary). If your remaining concerns are only out-of-tier or
tracked-debt in nature, please say SOUND-TO-PROCEED with them listed as notes so P3b can start.
