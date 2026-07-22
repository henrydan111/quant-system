# GPT Cross-Review Request — NF integration P2 RE-REVIEW #2 (Tier-2, diff-scoped)

Round 2 of the Tier-2 P2 review. Your round-1 verdict was **CHANGES-REQUIRED — 1 P0 + 2 P1**, all
folded. Per the convergence protocol, from round 2 the review is **diff-scoped**: (a) does the fold
close the three findings + the representative-member routing risk, and (b) does the fix introduce new
surface? (Tier-2 2-round budget; a clean/only-out-of-scope verdict is SOUND-TO-PROCEED to P3.)

**Commit under review: `dd07919`** on branch `calendar-unfreeze`.

## Findings — all folded

**P0 — as-of registry PIT leak.** P2 no longer accepts a pre-built `AliasRegistry` whose build-cutoff
it couldn't verify. It now takes raw `stock_basic` and **builds the registry itself AS-OF the
canonical cutoff** (`build_alias_registry(stock_basic, …, cutoff=cut)`), so a future-listed stock can
never resolve. The as-of routing basis is recorded in `routing_reference`
(`as_of_cutoff_iso`, `alias_registry_version`, `alias_registry_hash`, `industry_terms_hash`,
`concept_terms_hash`). Regression: a stock with `list_date > cutoff` never routes to stock, and
`routing_reference.as_of_cutoff_iso == cutoff`.

**P1-#2 — dict artifact bypassed the seal.** Extracted `verify_typed_flash_artifact(dict)` in P1
(schema + `artifact_sha256` + `population_hash` + content_hash uniqueness + `n_flashes` count). P2
verifies the P1 artifact for BOTH dict and path inputs. Regression: a hand-built dict with a bogus
`artifact_sha256` is refused.

**P1-#3 — coverage only checked the representative.** P2 now asserts the raw content-hash set EQUALS
the P1-typed set exactly (`seal_hash(sorted(set(df.content_hash))) == P1.population_hash`) BEFORE
clustering. Regression: dropping any flash from the P1 artifact (re-sealed) is refused.

**Representative-member routing (you flagged it as a real routing-semantics risk).** RESOLVED IN P2,
not deferred: routing now **unions every cluster member's mentions** (`_union_route` routes each
member and unions subject_codes/industry/concept). Regression: two flashes sharing a >120-char prefix
but mentioning different stocks cluster together and BOTH stocks appear in `subject_codes`.
**coordination** is now recorded as `coordination_evaluated: False` (unassessed), not a bare `False`.

## Note on fail-pre-fix

The core signature changed (`registry` → `stock_basic`), so a local stash-diff of the new tests
against the pre-fix module isn't apples-to-apples. You reproduced all three findings on `9ec365a`
(pre-fix); the new regressions lock the corrected behavior. `verify_typed_flash_artifact`'s stronger
count check also required updating one existing P1 test's expectation (an added-flash forgery now
trips the `n_flashes` check first unless `n_flashes` is also bumped, in which case it trips
`population_hash` as before — intent preserved).

## Files (pin to `dd07919`)

- https://raw.githubusercontent.com/henrydan111/quant-system/dd07919/workspace/research/ai_research_dept/engine/news_flash_assess.py
- https://raw.githubusercontent.com/henrydan111/quant-system/dd07919/workspace/research/ai_research_dept/engine/news_flash_typing.py
- https://raw.githubusercontent.com/henrydan111/quant-system/dd07919/workspace/research/ai_research_dept/tests/test_news_flash_assess.py
- news_routing.py (`build_alias_registry`, as-of `list_date`/`delist_date` filter): https://raw.githubusercontent.com/henrydan111/quant-system/dd07919/workspace/research/ai_research_dept/engine/news_routing.py

## Diff-scoped review questions

1. **P0:** does P2-builds-registry-as-of-cutoff fully close the PIT leak — any residual path where a
   future-listed or delisted alias could resolve, or where the recorded `routing_reference` doesn't
   actually bind the routing that was executed?
2. **P1-#2 / P1-#3:** is verifying dict+path via one `verify_typed_flash_artifact`, plus the exact
   `population_hash` set-equality gate, sufficient to guarantee P2 assesses exactly the verified
   P1-typed population? Any way a mismatch slips through?
3. **Union routing:** does unioning all members' mentions correctly close the representative-member
   risk? Is using the representative's TYPING (while unioning routes) still sound given the population
   gate guarantees every member is P1-typed?
4. **New surface:** does anything the fold introduced (P2 building the registry; the population gate;
   `_union_route`; the `routing_reference` block; the P1 verify refactor) create a new declared-
   invariant gap?
5. **Verdict:** SOUND-TO-PROCEED (to P3) or a specific remaining Tier-2 gap.
