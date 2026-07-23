# GPT Cross-Review Request — NF integration P2 RE-REVIEW #6 (confirm strict PIT name visibility)

Your re-review#5 confirmed the `end_date` day-boundary and importance-coercion fixes, and ruled the
one semantic I flagged: **`ann_date` must be STRICTLY visible** — same-day announcement must not
resolve; visibility starts at `strictly_next_open_trade_day(ann_date, calendar)` per the repo's hard
PIT contract (CLAUDE.md §3.2, `effective_date > disclosure_date`). Implemented. This round is a narrow
confirmation of that one fix.

**Commit under review: `4ba5971`** on branch `calendar-unfreeze`. Tier-2, diff-scoped.

## The fix

`_as_of_names(namechange, cut, open_calendar)` — `open_calendar` is now **REQUIRED** (no fail-open
fallback to a day-inclusive `ann_date <= cut`). Visibility uses the same load-bearing anchor the PIT
ledger is built on:

```python
ann = pd.to_datetime(nc_df.get("ann_date"), errors="coerce")
visible_from = strictly_next_open_trade_day(ann, open_calendar)   # data_infra.pit_backend
...
covering = {nm for (s, e, v, nm) in rows
            if pd.notna(s) and s <= cut_d                      # in effect (inclusive day)
            and (e is None or (pd.notna(e) and cut_d <= e))
            and pd.notna(v) and v <= cut_d}                    # STRICTLY-next-open visible
```

`start_date`/`end_date` keep the inclusive DAY bounds from your re-review#4 fix. `assess_day_flashes`
and the CLI seam thread `open_calendar` through (the CLI will load
`data/reference/trade_cal.parquet`). A NaT `ann_date`, or an announcement with no open day after it,
yields NaT → the name is omitted (fail-closed).

## Regressions

- `test_p0_same_day_announcement_is_not_visible` — a rename announced ON the 2025-01-27 cutoff day
  does NOT resolve.
- `test_p0_visible_from_strictly_next_open_day` — the SAME rename announced on the previous open
  trading day (Fri 2025-01-24) DOES resolve at the Monday 2025-01-27 cutoff.

**Self-review catch worth flagging:** both tests initially passed for the WRONG reason — I used a
2-character test name, which is below `resolve_codes`' 4-character Chinese-name link threshold, so the
name could never resolve regardless of visibility. Corrected to a 4-character name so the tests
actually exercise the visibility rule. (The reviewer's own probe established the pre-fix behaviour;
the new `open_calendar` argument makes a local stash-diff not apples-to-apples, so I am not claiming
one.)

## Files (pin to `4ba5971`)

- https://raw.githubusercontent.com/henrydan111/quant-system/4ba5971/workspace/research/ai_research_dept/engine/news_flash_assess.py
- https://raw.githubusercontent.com/henrydan111/quant-system/4ba5971/workspace/research/ai_research_dept/tests/test_news_flash_assess.py
- anchor: https://raw.githubusercontent.com/henrydan111/quant-system/4ba5971/src/data_infra/pit_backend.py (`strictly_next_open_trade_day`, line ~962)

Tests: 24 P2 + full ai_research_dept **771** green.

## Confirmation questions

1. Is `visible_from = strictly_next_open_trade_day(ann_date, open_calendar)` with
   `visible_from <= cutoff_day` the correct strict-visibility implementation you prescribed, with no
   residual same-day path?
2. Is making `open_calendar` required (rather than defaulting to `ann_day < cut_day`) the right
   fail-closed choice, and are the NaT cases (missing/unparseable ann_date; no open day after the
   announcement) correctly omitted?
3. Does the interaction with the inclusive `start_date`/`end_date` day bounds remain correct — i.e. a
   name can be in effect but not yet visible, and visible but no longer in effect?
4. Any new gap introduced by this fix?
5. **Verdict:** CONFIRMED — SOUND-TO-PROCEED to P3, or a specific defect in this fix.
