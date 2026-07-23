# GPT Cross-Review Request — NF integration P3a RE-REVIEW #3 (Tier-2, diff-scoped)

Round 3 of the Tier-2 P3a review. Your round-2 verdict: **P0 CLOSED** (recompute-bound source; the
CLI's `load_text` accepted as-is), **1 P1 open** — verbatim substring does not preserve context.
Folded. Diff-scoped: does the fold close it, and does it introduce new surface?

**Commit under review: `a6d1186`** on branch `calendar-unfreeze`. Tier-2 (frozen; Tier-1 crafted-object
analysis remains out of tier — record such findings as tracked notes, or recommend a tier change to the
user).

## The P1 fold — the model points, the system decides the text

Your probe: `"It is false that ACME signed a $12bn contract."` → the span
`"ACME signed a $12bn contract"` is literally present but its meaning is inverted, and the cut would
flow into `factor_positive / event_materiality`.

The model no longer chooses the text at all. It returns a `fact_span` (still required to occur
literally in the hash-bound source, and to be substantive itself), and P3a then **deterministically
expands that span to its enclosing sentence(s)** and uses THAT as the attribute:

```python
def _enclosing_sentence(source: str, span: str) -> str:
    start = source.find(span); end = start + len(span)
    i = start
    while i > 0:
        if source[i-1] in _TERMINATORS or _is_period_boundary(source, i-1): break
        i -= 1
    j, n = end, len(source)
    while j < n:
        ch = source[j]; j += 1
        if ch in _TERMINATORS or _is_period_boundary(source, j-1): break
    return source[i:j].strip()
```

- `_TERMINATORS = "。！？；…!?;\n\r"`; an ASCII `.` is a boundary **except between digits**, so
  `12.5` stays one number.
- **No reliable boundary → the expansion degrades to the whole source** (the conservative direction).
- The span must itself be substantive — otherwise a whitespace pointer would be "rescued" into a valid
  fact by the expansion.
- The prompt now states the expansion explicitly, so truncation is not a usable strategy.

## Regressions

- English negation preserved (`"It is false that …"` survives into `fact`);
- Chinese attribution preserved (`"有传闻称…"` survives);
- multi-sentence source expands to the **enclosing sentence only** (neighbouring sentences excluded);
- a decimal is not a boundary;
- whitespace-only span refused; ungrounded / paraphrased / non-`str` spans still refused.

**Fail-pre-fix verified, and the failure message IS the hole:** on the pre-fix module the emitted fact
was literally `'贵州茅台签订 12 亿元大单'` with `'有传闻称'` stripped.

**Two test-construction errors of my own, disclosed:** two probes used nameless English sources, which
route to `macro` and are therefore never split — they were failing for the wrong reason. Corrected by
including the subject name so the flash routes to a stock (POSITIVE class).

Tests: 24 P3a + full ai_research_dept **801** green.

## Files (pin to `a6d1186`)

- https://raw.githubusercontent.com/henrydan111/quant-system/a6d1186/workspace/research/ai_research_dept/engine/news_flash_split.py
- https://raw.githubusercontent.com/henrydan111/quant-system/a6d1186/workspace/research/ai_research_dept/tests/test_news_flash_split.py

## Diff-scoped review questions

1. Does deterministic sentence expansion close the context-truncation class, or is there a residual
   shape (e.g. a claim whose qualifier sits in a *neighbouring* sentence — "The company denied the
   report. 贵州茅台签订 12 亿元大单。") that sentence-level expansion still splits apart? If so, is
   whole-source the right answer for `fact`, or does that belong to a later grounding scheme?
2. Are the boundary rules right for CN/EN news (terminator set, the digit-guarded `.`, newline), and
   is degrading to whole-source on no-boundary the correct conservative direction?
3. Is requiring the span itself to be substantive (before expansion) sound, and does the expansion
   introduce any new way for the model to influence the emitted text beyond choosing a sentence?
4. **New surface:** anything the fold introduced that creates a new declared-invariant gap?
5. **Verdict:** SOUND-TO-PROCEED (to P3b) or a specific in-tier gap.
