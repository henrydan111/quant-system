# GPT Cross-Review Request — NF integration P2 RE-REVIEW #3 (Tier-2, diff-scoped, budget ceiling)

Round 3 (the Tier-2 2-re-review-round ceiling) of the P2 review. Your round-2 verdict was
**CHANGES-REQUIRED — 1 P0 + 1 P1**, both folded. Diff-scoped: does the fold close both, and does it
introduce new surface? **This is the budget ceiling** — if a same-class gap remains, per protocol it
goes to user arbitration, not another self-initiated fold. A clean / only-out-of-scope verdict is
SOUND-TO-PROCEED to P3.

**Commit under review: `21e2c97`** on branch `calendar-unfreeze`. Tier-2 — declared invariants, not
adversarial-caller analysis.

## P0 — registry not fully as-of. FOLDED (two sub-parts).

**(a) PIT names.** `build_alias_registry` used the CURRENT `stock_basic.name`, so a post-cutoff rename
resolved at a past cutoff (000558.SZ '天府文旅' effective 2025-02-14 resolving a 2025-01-27 flash). P2
now computes `_as_of_names(stock_basic, namechange, cut)` — the name valid at `cut` from `namechange`
history (name valid on `[start_date, end_date]`, end null = current) — and passes it to a new
`as_of_names` param on `build_alias_registry`. The resolved-name basis is bound as
`routing_reference.as_of_names_hash`. Regression: a flash mentioning the FUTURE name '天府文旅' does not
resolve at the 2025-01-27 cutoff; the as-of name '莱茵体育' does.

**(b) fail-closed dates.** `build_alias_registry` under a cutoff now REFUSES a stock with a
missing/unparseable `list_date` (or a non-null unparseable `delist_date`) instead of coercing to NaT
and admitting it. Regression: an unparseable `list_date` raises.

`build_alias_registry`'s change is backward-compatible (`as_of_names=None` keeps the old behavior; the
fail-closed dates only apply under a cutoff); the existing `news_routing` tests are unaffected.

## P1 — cross-fact typing wash. FOLDED.

The 120-char cluster key can group DISTINCT facts. P2 now refuses a cluster whose members'
evidence-identity typings (event_type / verification_status / content_kind / direction / is_rumor)
disagree — no laundering one fact's evidence class onto another's stock. (Routing already unions all
members' mentions.) Regression: an official-bullish flash and a rumor-bearish flash sharing a
>120-char prefix are refused, not merged.

## Disclosed residual (one, honest — please rule)

A stock that was renamed but is ENTIRELY ABSENT from `namechange` falls back to `stock_basic.name`
(treated as never-renamed). Distinguishing "never renamed" from "renamed but missing from namechange"
is impossible without external data; your 000558 repro IS in namechange and is handled. Is this
namechange-completeness residual acceptable to record, or must P2 fail-closed on any stock absent from
namechange (which would refuse routing for every stock the namechange reference doesn't cover)?

## Files (pin to `21e2c97`)

- https://raw.githubusercontent.com/henrydan111/quant-system/21e2c97/workspace/research/ai_research_dept/engine/news_flash_assess.py
- https://raw.githubusercontent.com/henrydan111/quant-system/21e2c97/workspace/research/ai_research_dept/engine/news_routing.py
- https://raw.githubusercontent.com/henrydan111/quant-system/21e2c97/workspace/research/ai_research_dept/tests/test_news_flash_assess.py

## Diff-scoped review questions

1. **P0(a):** does resolving `_as_of_names` from namechange and binding `as_of_names_hash` fully close
   the future-alias leak? Is the as-of window `start_date <= cut <= (end_date|∞)` correct, and does the
   omit-on-gap policy (P2 omits a code with no covering name; `build_alias_registry` fail-closes only
   for a code that IS listed at cutoff) behave correctly for listed vs unlisted stocks?
2. **P0(b):** are the fail-closed date checks complete (missing/unparseable list_date; non-null
   unparseable delist_date), with no residual coerce-and-admit path under a cutoff?
3. **P1:** is refusing a cluster on typing-identity disagreement the right fail-closed fix, and is
   using the (now-consistent) representative typing sound?
4. **New surface:** does anything the fold introduced (the `as_of_names` param on the shared
   `build_alias_registry`; `_as_of_names`; the typing-identity gate) create a new declared-invariant
   gap or affect other `build_alias_registry` callers?
5. **Verdict:** SOUND-TO-PROCEED (to P3), or a specific remaining Tier-2 gap (which, at this ceiling,
   routes to user arbitration).
