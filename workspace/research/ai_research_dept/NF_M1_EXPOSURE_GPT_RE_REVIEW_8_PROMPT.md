# GPT Re-review #8 — Macro wave M1 — CONFIRMATION round 5 (narrow)

Confirming exactly the round-7 P1 fix. Scope: the one diff. **Tier-2**.

**Fold commit: `18d00d9`** (you reviewed `c399370`).

## Your P1 → the fold

> The string branch was type-allowed, not full-captured-timestamp-allowed: lenient `pd.Timestamp`
> parsed `"2025-01-27"` to midnight (the same insufficiency as the refused bare `date` — and it
> end-to-end selected a midnight snapshot writing `FUTURE.TI` into MS03), while `"today"`,
> `"now"`, `"12:00"` parse to the RUNTIME instant.

Folded exactly as prescribed: strings must **fullmatch the canonical explicit-time format**
`YYYY-MM-DD[T ]HH:MM:SS[.f…][Z|±HH:MM]` (`_FETCHED_AT_RE`) BEFORE any parsing — date-only,
compact-date, natural-language, relative and time-only strings all refuse as
`source_unavailable`; a form-valid but value-invalid string (month 13) refuses at the parse.
Shanghai normalization applies unchanged after the gate.

Regressions: all six of your probe strings (`"2025-01-27"`, `"20250127"`, `"Jan 27 2025"`,
`"today"`, `"now"`, `"12:00"`) refuse end-to-end with no `FUTURE.TI` anywhere; the
space-separated explicit-time canonical form (`"2025-01-01 07:30:00"`) still maps. Verified
**fail-pre-fix** by stashing (1 failed pre-fix). **26** M1 tests + full `ai_research_dept` suite
**942** green.

## Files (pin to `18d00d9`)

- https://raw.githubusercontent.com/henrydan111/quant-system/18d00d9/workspace/research/ai_research_dept/engine/macro_exposure.py
- https://raw.githubusercontent.com/henrydan111/quant-system/18d00d9/workspace/research/ai_research_dept/tests/test_macro_exposure.py

## Confirmation questions

1. Is `_FETCHED_AT_RE` the right canonical set — anything it wrongly admits (an ambiguous instant
   that matches the pattern) or wrongly refuses (a store shape the real ingester emits — note the
   actual `ths_ingest` writes full ISO strings with microseconds, which match)?
2. **Verdict:** SOUND-TO-PROCEED (M1 closed → M2, the macro flash section; mapping YAMLs still
   queued for the user's content pass) or a specific residual gap.
