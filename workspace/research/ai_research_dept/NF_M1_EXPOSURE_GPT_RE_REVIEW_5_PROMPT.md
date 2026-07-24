# GPT Re-review #5 — Macro wave M1 — CONFIRMATION round 2 (narrow)

Round-4 confirmation caught a real gap in my round-3 fold; this round confirms exactly that fix.
Scope: the two diffs only. **Tier-2**.

**Fold commit: `4733683`** (you reviewed `75cc2c4`).

## Your P1 → the fold

> The round-3 fix only refused frames where ALL timestamps were unparseable — a mixed frame (one
> valid `2025-01-01` row + one `not-a-date` row) silently dropped the bad row and reported
> `selected`: neither `source_unavailable` nor a provably complete snapshot.

Folded exactly as prescribed: **ANY** row with an unparseable `fetched_at` → the whole source is
`source_unavailable`; likewise any empty/NaN `ts_code` or `con_code` (your suggested per-row
non-emptiness check, adopted). Bad rows are never silently dropped. Your probe is pinned in both
row orders, plus the empty-`con_code` and `None`-`ts_code` shapes — verified **fail-pre-fix** by
stashing (1 failed pre-fix, passes post-fix).

## Your P2 → the fold

The module docstring's M3 input contract now states both rules the design doc already carried:
`pool_metrics` whole-frame `ts_code` uniqueness (fail-closed, no silent dedup) and the
`ths_members` per-row source-integrity rule (any bad row = `source_unavailable`).

## Verification

**22** M1 tests + full `ai_research_dept` suite **938** green. (One benign pandas
mixed-format-parsing warning on the coerce path in the new probe — the coercion is exactly what
the gate inspects.)

## Files (pin to `4733683`)

- https://raw.githubusercontent.com/henrydan111/quant-system/4733683/workspace/research/ai_research_dept/engine/macro_exposure.py
- https://raw.githubusercontent.com/henrydan111/quant-system/4733683/workspace/research/ai_research_dept/tests/test_macro_exposure.py

## Confirmation questions

1. Does the any-bad-row rule now close the P1 completely — any remaining ordinary-DataFrame shape
   where a malformed source is neither refused nor honestly labelled?
2. Is the docstring contract now complete for the M3 supplier?
3. **Verdict:** SOUND-TO-PROCEED (M1 closed → M2; mapping YAMLs still queued for the user's
   content pass) or a specific residual gap.
