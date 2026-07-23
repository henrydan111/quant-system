# GPT Cross-Review Request — NF integration P2 RE-REVIEW #5 (confirmation of the two implementation fixes)

Your re-review#4 confirmed the arbitrated fail-closed-omit decision was correctly scoped but found
**2 P1 implementation defects** in the fold. Both fixed. This round is a **narrow confirmation of
those two fixes** — the arbitrated name-recall trade-off remains the user's fixed decision, not for
re-litigation. Verdict: CONFIRMED (proceed to P3) or a specific defect in these two fixes.

**Commit under review: `ca3d269`** on branch `calendar-unfreeze`. Tier-2, diff-scoped.

## Fix 1 — `end_date` day boundary

namechange dates are `YYYYMMDD` (parse to `00:00:00`) while `cut` is a wall-clock timestamp, so a raw
`cut <= end_date` wrongly omitted a name whose `end_date` IS the cutoff day (`18:00 <= 00:00` is
False). `_as_of_names` now normalizes **all four** dates (`cut`, `start_date`, `end_date`, `ann_date`)
to DAY granularity, with inclusive bounds:

```python
cut_d = pd.Timestamp(cut).normalize()
covering = {nm for (s, e, a, nm) in rows
            if pd.notna(s) and s <= cut_d                    # in effect (inclusive)
            and (e is None or (pd.notna(e) and cut_d <= e))
            and pd.notna(a) and a <= cut_d}                  # announced (PIT anchor)
```

Regression: `start=20240101, end=20250127, ann=20240101` resolves at cutoff `2025-01-27 18:00`.

**One semantic I want you to rule on explicitly:** `ann_date` uses INCLUSIVE day comparison
(`ann_day <= cut_day`), i.e. a name announced ON the cutoff day is usable. A stricter, §3.2-style
reading ("effective strictly later than disclosure") would be `ann_day < cut_day` — usable only from
the next day — which is more fail-closed but costs a day of recall on every rename. I implemented the
inclusive form because that is what your fix prescribed (normalize and compare by day) and I did not
want to legislate a stricter rule unasked. **Confirm inclusive is right, or say strict is required.**

## Fix 2 — no importance coercion

`int()` silently turned `5.9` / `"5"` / `True` into a valid-looking importance that `assess_flash`'s
exact-type gate would have REJECTED, letting a tampered-but-hash-consistent P1 artifact move the D7
`importance >= 4` gate. Each member's importance is now validated with the same rule as
`_validate_typing` (`type(v) is int and 0 <= v <= 5`; bool excluded because `type(True) is bool`) and
the RAW values are maxed — no coercion:

```python
for h in member_hashes:
    v = typing_index[h]["importance"]
    if type(v) is not int or not 0 <= v <= 5:
        raise ValueError(... "not a literal int in [0,5] — refusing (no coercion)")
    imps.append(v)
rep_typing["importance"] = max(imps)
```

Regression (parametrized `5.9` / `"5"` / `True`): each refused. All four new regressions were verified
to FAIL on the pre-fix module.

## Files (pin to `ca3d269`)

- https://raw.githubusercontent.com/henrydan111/quant-system/ca3d269/workspace/research/ai_research_dept/engine/news_flash_assess.py
- https://raw.githubusercontent.com/henrydan111/quant-system/ca3d269/workspace/research/ai_research_dept/tests/test_news_flash_assess.py

Tests: 22 P2 + full ai_research_dept **769** green.

## Confirmation questions

1. Is the day-normalized as-of predicate now correct at every boundary (start day, end day, ann day,
   `end_date` null), with no residual off-by-one or timezone/normalize interaction?
2. **The `ann_date` inclusive-vs-strict question above** — please rule.
3. Is the importance validation exactly equivalent to `_validate_typing`'s gate (literal int in [0,5],
   bool rejected), applied to every member before the max, with no coercion path left?
4. Any new gap introduced by these two fixes?
5. **Verdict:** CONFIRMED — SOUND-TO-PROCEED to P3, or a specific defect in these two fixes.
