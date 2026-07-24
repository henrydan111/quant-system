# GPT Re-review #6 — Macro wave M1 — CONFIRMATION round 3 (narrow)

Confirming exactly the round-5 P1 fix. Scope: the one diff. **Tier-2**.

**Fold commit: `400c29c`** (you reviewed `4733683`).

## Your P1 → the fold

> Integer `fetched_at=20260709` (meant as 2026-07-09) parses as epoch-nanoseconds →
> `1970-01-01…`, passes the 2025 cutoff, and injects `FUTURE.TI` concepts into a 2025 decision —
> an actual no-lookahead hole via ordinary types.

Folded exactly as prescribed: **numeric `fetched_at` refuses BEFORE `pd.to_datetime`** — numeric
dtype, or any `int`/`float` (incl. `bool`) element in an object column, makes the whole source
`source_unavailable`; only datetime values and strings reach the parser (where the round-4
any-bad-row rule still applies).

Regressions pinned, per your prescription:
- int `20260709` → `source_unavailable`, no `FUTURE.TI` anywhere in the row;
- the SAME date as a legit ISO string `"2026-07-09T00:00:00"` → the legal M4 omission
  (`mapped` + `concepts_omitted` marker);
- mixed string+numeric frames → source failure in BOTH row orders.

Verified **fail-pre-fix** by stashing (1 failed pre-fix, passes post-fix). **23** M1 tests +
full `ai_research_dept` suite **939** green.

## Files (pin to `400c29c`)

- https://raw.githubusercontent.com/henrydan111/quant-system/400c29c/workspace/research/ai_research_dept/engine/macro_exposure.py
- https://raw.githubusercontent.com/henrydan111/quant-system/400c29c/workspace/research/ai_research_dept/tests/test_macro_exposure.py

## Confirmation questions

1. Does the pre-parse numeric refusal close the timestamp-form surface completely — any remaining
   ordinary value form (`fetched_at` as date objects, tz-aware strings, mixed tz…) that either
   slips a wrong instant past the cutoff gate or wrongly refuses a legitimate store shape?
2. **Verdict:** SOUND-TO-PROCEED (M1 closed → M2, the macro flash section; mapping YAMLs still
   queued for the user's content pass) or a specific residual gap.
