# GPT Cross-Review Request — NF integration P2 RE-REVIEW #4 (FINAL confirmation of the user-arbitrated fold)

Your re-review#3 hit the Tier-2 budget ceiling on name-PIT completeness and (correctly) routed P0 to
**user arbitration**. The user chose **fail-closed omit** (over "build a sealed PIT-complete name
reference" or "tracked debt"). This round is a **final confirmation** that the arbitrated decision is
implemented correctly and introduces no new gap — NOT a re-opening of the arbitrated scope. The
name-recall trade-off (a stock without a clean announced unique as-of name is not name-resolvable) is
the user's accepted decision; do **not** re-litigate it. Verdict options: CONFIRMED (proceed to P3),
or a specific IMPLEMENTATION defect in the arbitrated fold.

**Commit under review: `497016f`** on branch `calendar-unfreeze`. Tier-2, diff-scoped to the fold.

## The arbitrated decision (fixed scope — implement-correctly check only)

Name aliasing is **fail-closed omit**: a ts_code gets an as-of name ONLY if `namechange` yields
exactly ONE name that at `cut` is both IN EFFECT (`start_date <= cut <= end_date|∞`) AND ANNOUNCED
(`ann_date <= cut`, the PIT visibility anchor). 0 / >1 (gap/overlap) / unannounced / absent from
namechange → **no name alias** (the code still resolves by numeric A/H code). **No fallback to
`stock_basic.name`.** Reduced name recall is accepted; full recall (a sealed PIT-complete name
reference) is a pre-forward item, not built here.

## How it was implemented

- `_as_of_names(namechange, cut)` (news_flash_assess.py): groups namechange by ts_code; a code is
  included ONLY if `{name : start<=cut<=(end|∞) and ann_date<=cut}` has exactly one element. No
  stock_basic fallback.
- `build_alias_registry(..., as_of_names=…)` (news_routing.py): with `as_of_names`, a listed code
  missing from it is OMITTED from the name map (no longer raises) but stays in `a_universe` for
  numeric resolution. Under a cutoff, BOTH `list_date` and `delist_date` columns must exist; `list_date`
  must parse; a non-null `delist_date` must parse. Backward-compatible: `as_of_names=None` keeps the
  old current-name behavior (used only by the pre-existing routing tests, no cutoff-name-PIT claim).
- P1 fold (unchanged decision): after the identity gate, `importance` is the MAX over cluster members.

## Regressions (news_flash_assess tests)

- `test_p0_post_cutoff_rename_does_not_resolve` — 000558.SZ '莱茵体育' (as-of) resolves; future '天府文旅' does not.
- `test_p0_name_in_effect_but_unannounced_does_not_resolve` — a name with `ann_date > cut` does not resolve.
- `test_p1_conflicting_member_typings_refused` — mixed-typing cluster refused.
- `test_p1_importance_is_max_over_members` — importance is the member max, not the representative's.
- `test_p0_missing_delist_date_column_fail_closed` / `test_p0_unparseable_list_date_fail_closed`.

## Files (pin to `497016f`)

- https://raw.githubusercontent.com/henrydan111/quant-system/497016f/workspace/research/ai_research_dept/engine/news_flash_assess.py
- https://raw.githubusercontent.com/henrydan111/quant-system/497016f/workspace/research/ai_research_dept/engine/news_routing.py
- https://raw.githubusercontent.com/henrydan111/quant-system/497016f/workspace/research/ai_research_dept/tests/test_news_flash_assess.py

## Confirmation questions (implementation-correctness only, within the fixed arbitrated scope)

1. Is the as-of predicate correct — `start_date <= cut <= (end_date|∞)` AND `ann_date <= cut`, exactly
   one covering name, else omit — with no residual path that admits a future/unannounced name or falls
   back to `stock_basic.name`?
2. Does `build_alias_registry`'s omit-on-missing (keep in `a_universe`, drop the name) behave correctly
   for listed vs unlisted codes, and are the `list_date`/`delist_date` column + parse checks complete
   under a cutoff with no coerce-and-admit residual?
3. Is `importance = max(members)` applied after the identity gate without disturbing the other typing
   fields, and does it flow into the sealed artifact?
4. Any NEW gap introduced by the fold (the `as_of_names` param on the shared `build_alias_registry`;
   the ann_date logic; the omit policy) — including effects on other `build_alias_registry` callers?
5. **Verdict:** CONFIRMED — SOUND-TO-PROCEED to P3, or a specific implementation defect in the
   arbitrated fold (not a re-litigation of the name-recall trade-off, which is the user's decision).
