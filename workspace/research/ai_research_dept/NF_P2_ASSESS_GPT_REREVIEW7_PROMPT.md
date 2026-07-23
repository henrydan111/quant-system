# GPT Cross-Review Request — NF integration P2 RE-REVIEW #7 (confirm canonical-calendar validation)

Your re-review#6 found the last same-day path: the strict-visibility guarantee only holds for a
canonical day-granular calendar, and an intra-day entry (`2025-01-27 09:30`) made a same-day rename
visible again. Fixed. Narrow confirmation of this one fix.

**Commit under review: `eb19e2c`** on branch `calendar-unfreeze`. Tier-2, diff-scoped.

## The fix

Two parts — the validation you prescribed, **and removing the thing that masked the hole**:

```python
def _require_open_calendar(cal) -> pd.DatetimeIndex:
    if not isinstance(cal, pd.DatetimeIndex): raise ValueError(...)   # exact type
    if cal.tz is not None:                    raise ValueError(...)   # CN-naive
    if len(cal) == 0:                         raise ValueError(...)   # non-empty
    if cal.hasnans:                           raise ValueError(...)   # no NaT
    if not cal.is_monotonic_increasing:       raise ValueError(...)   # sorted
    if cal.has_duplicates:                    raise ValueError(...)   # unique
    if (cal.normalize() != cal).any():        raise ValueError(...)   # EVERY entry midnight
    return cal
```

Called at the top of `_as_of_names`, **before the anchor and before the empty-namechange early
return**. Nothing is silently normalized or coerced.

**The masking `.normalize()` is removed.** Previously the anchor's output was `.normalize()`-d, which
is exactly what pulled a same-day `09:30` calendar entry back to the same day. With a validated
calendar the anchor's result IS the visible day, so no post-processing is applied:

```python
v = visible_from.iloc[i]          # was: pd.Timestamp(v).normalize()
v = pd.Timestamp(v) if pd.notna(v) else pd.NaT
```

## Regression (parametrized — all 5 verified to FAIL on the pre-fix module)

Your exact probe plus the other non-canonical shapes: `['2025-01-27 09:30', '2025-01-28']` (intra-day),
unsorted, duplicated, empty, NaT — each refused with a distinct message. On the pre-fix module the
intra-day case resolved the same-day name (and the others produced anchor errors/NaT), so the guard is
load-bearing.

## Files (pin to `eb19e2c`)

- https://raw.githubusercontent.com/henrydan111/quant-system/eb19e2c/workspace/research/ai_research_dept/engine/news_flash_assess.py
- https://raw.githubusercontent.com/henrydan111/quant-system/eb19e2c/workspace/research/ai_research_dept/tests/test_news_flash_assess.py

Tests: 29 P2 + full ai_research_dept **776** green.

## Confirmation questions

1. Is the calendar validation complete for the strict-visibility guarantee (type, tz, non-empty, NaT,
   sorted, unique, midnight) — any other calendar shape that could still yield a same-day
   `visible_from`?
2. Is removing the post-anchor `.normalize()` correct now that the calendar is validated, and does any
   other place still normalize the anchor's output?
3. Is validating inside `_as_of_names` (before the anchor and before the empty-namechange early
   return) the right placement, or must it move to the `assess_day_flashes` entry?
4. Any new gap introduced by this fix?
5. **Verdict:** CONFIRMED — SOUND-TO-PROCEED to P3, or a specific defect in this fix.
