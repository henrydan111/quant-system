# GPT Cross-Review Request — NF integration P3a RE-REVIEW #2 (Tier-2, diff-scoped)

Round 2 of the Tier-2 P3a review. Your round-1 verdict was **REVISE — 1 P0 + 1 P1**, both folded.
Diff-scoped: does the fold close both, and does the fix introduce new surface?

**Commit under review: `c569dbc`** on branch `calendar-unfreeze`.

## ⚠ FROZEN REVIEW TIER — Tier-2 (unchanged)

Declared-invariant review against ordinary well-formed in-process inputs. **Tier-1 analysis is OUT OF
TIER** (crafted objects, subclass overrides, dunder/metaclass, adversarial in-process callers) —
reserved by user decision for seal spend / holdout / PIT kernels / the sealed-archive commitment. Such
a finding should be an **OUT-OF-TIER note** (tracked, not gating); if you believe P3a warrants Tier-1,
raise it as a **recommendation to the user**, whose decision the tier is. (Both round-1 findings were
correctly in-tier — ordinary dicts/strings and a normal LLM output path.)

## P0 — injected text was not bound to P2. FOLDED by RECOMPUTATION, not trust.

You were right that adding a content hash to P3a's output would only record what P3a read. The fix
uses the fact that `content_hash` **is a canonical function of the raw row**:

```python
def _bind_source_rows(rows, needed: set) -> dict:
    ...
    for _, r in rows.iterrows():
        h = content_hash_for("news", r, cols)   # RECOMPUTED, never taken from the row
        if h in needed and h not in bound:
            bound[h] = str(r["content"])
    missing = sorted(needed - set(bound))
    if missing:
        raise ValueError(...)                   # no hash-verified source → hard error
```

`split_day_flashes(..., source_rows=…)` replaces the `contents` mapping. A substituted or edited
(e.g. future) text produces a **different** hash, so the row stops matching and its population member
has no verified source → refused. Your probe (`future_text_accepted_under_original_hash=True`) is now
a regression that refuses.

**On the CLI contradiction you flagged:** the CLI still calls `load_text` to OBTAIN the rows, but that
read is no longer *trusted* — the recomputation is what binds them. I removed the overclaimed
invariant "P3a opens no dated source" and restated it honestly as *"the extraction source is bound to
P2 by recomputation; the CLI's read is not trusted"*. **Please rule on whether that is acceptable, or
whether the CLI must instead receive a sealed row snapshot** (i.e. whether obtaining rows from
text_store at all is the objection, or only trusting them).

## P1 — no source grounding for LLM text. FOLDED by verbatim-span grounding + deferral.

The model no longer WRITES the attribute; it SELECTS a span:

```python
span = results[j].get("fact_span")
if type(span) is not str: raise ...
if not span or span not in source: raise ...      # LITERAL occurrence in the bound source
attrs = {"fact": _require_attr_text(span, ...)}   # then the frozen substantive predicate
```

A paraphrase, a summary, or an invented number cannot pass. The prompt was rewritten to demand a
verbatim span and to state it will be checked literally.

**`economic_linkage` is DEFERRED in v1** (alongside `timing`), taking your second option: it becomes a
`factor_positive` `fundamental_link` attribute — a SCORING input — and a causal-transmission claim
cannot be grounded by quotation the way a fact can. It returns only with a proper grounding scheme.
So P3a v1 emits exactly two attributes: `fact` (grounded span) and `source_status` (derived).

## Regressions

Substituted future text under P2's hash refused; non-DataFrame rows refused; population-uncovered rows
refused; ungrounded span (invented number / paraphrase / empty) refused; non-`str` span refused;
whitespace-only span refused (grounded but not substantive); verbatim span accepted. The signature
change (`contents` → `source_rows`) makes a local stash-diff not apples-to-apples, so I am not claiming
one — your runtime probes established the pre-fix behaviour.

Tests: 20 P3a + full ai_research_dept **797** green.

## Files (pin to `c569dbc`)

- https://raw.githubusercontent.com/henrydan111/quant-system/c569dbc/workspace/research/ai_research_dept/engine/news_flash_split.py
- https://raw.githubusercontent.com/henrydan111/quant-system/c569dbc/workspace/research/ai_research_dept/tests/test_news_flash_split.py
- binding primitive: https://raw.githubusercontent.com/henrydan111/quant-system/c569dbc/src/data_infra/text_store.py (`content_hash_for`, line ~185)

## Diff-scoped review questions

1. **P0:** does recompute-and-bind actually prove the extraction source is P2's text — any residual
   path where an unverified text reaches the model? Is `content_hash_for("news", row, cols)` the right
   recomputation (correct source name and basis) for rows loaded from the store?
2. **The CLI question above** — is obtaining rows via `load_text` acceptable given the recomputation,
   or is a sealed snapshot required?
3. **P1:** is verbatim-span grounding sufficient for `fact` in a NON_EVIDENTIARY replay, and is
   deferring `economic_linkage` the right call rather than shipping a weakly-grounded scoring input?
4. **New surface:** anything the fold introduced (the `source_rows` contract, `_bind_source_rows`, the
   span check, the rewritten prompt) that creates a new declared-invariant gap?
5. **Verdict:** SOUND-TO-PROCEED (to P3b) or a specific in-tier gap.
