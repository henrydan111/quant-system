# GPT Re-review #4 — Macro wave M1 — CONFIRMATION round (user-arbitrated folds)

Round 3 hit the §10 budget with 2 P1 + 1 P2; per protocol the residue went to **user
arbitration**, who chose: fold all three + this confirmation round. Scope: exactly the three fold
diffs. NOT a fresh open sweep. **Tier-2**.

**Fold commit: `75cc2c4`** (you reviewed `bb603e8`).

## Your findings → the folds

1. **P1 source failure disguised as legal omission.** `select_ths_snapshot` now returns a 4th
   element `status ∈ {selected, no_eligible_snapshot, source_unavailable}`. An empty frame,
   missing columns, unparseable timestamps, or a non-frame → **`source_unavailable`**, and MS03
   becomes that distinct row status (null bucket/value — unscorable even though the industry could
   resolve; a broken source must surface loudly, matching the NF P1 forward-store precedent). The
   genuine all-later-snapshot store keeps `mapped` + the `concepts_omitted` value marker. Your
   probe pinned across all four malformed shapes AND the legal case in one test.
2. **P1 duplicate pool rows.** `pool_metrics.ts_code` must be UNIQUE across the whole frame —
   duplicates refuse fail-closed with the offending codes named (no silent dedup rule, exactly
   your prescription's stricter arm). Your low-first/high-first probe pinned in both orders
   (identical refusal).
3. **P2 stale phrasing (third occurrence of the class — swept full-text, then grep-verified zero
   hits).** The premise section's `mapping_status=no_contemporaneous_snapshot` phrasing → the
   value-marker contract; "mapping tables DO NOT EXIST" → authored-pending-user-review; "columns
   to re-verify at implementation" → the verified `pool_metrics` contract incl. the uniqueness
   rule; "Open decisions" → "Resolved decisions" historical record; "L1/L2" → L1 only; the module
   docstring's "frozen 11 fields verbatim" → 11 + the recorded `row_id` amendment.

## Verification

**21** M1 tests; the two new P1 probes verified **fail-pre-fix** by stashing the engine diff
(2 failed pre-fix, all pass post-fix). Full `ai_research_dept` suite **937** green.

## Files (pin to `75cc2c4`)

- https://raw.githubusercontent.com/henrydan111/quant-system/75cc2c4/workspace/research/ai_research_dept/engine/macro_exposure.py
- https://raw.githubusercontent.com/henrydan111/quant-system/75cc2c4/workspace/research/ai_research_dept/tests/test_macro_exposure.py
- https://raw.githubusercontent.com/henrydan111/quant-system/75cc2c4/workspace/research/ai_research_dept/NF_UNIT_M1_DESIGN.md

## Confirmation questions

1. **P1#1:** is the three-way status split (`selected` / `no_eligible_snapshot` /
   `source_unavailable`) the right partition, and is making the MS03 row wholly unscorable on
   source failure (rather than industry-only-mapped) the right severity?
2. **P1#2:** is whole-frame uniqueness (vs target-stock-only) the right scope, and is fail-closed
   refusal without a dedup rule acceptable for the M3 supplier contract?
3. **P2:** any stale phrase the full-text sweep still missed, in either file?
4. **Verdict:** SOUND-TO-PROCEED (M1 closed → M2, the macro flash section; the mapping YAMLs
   remain queued for the user's content edit pass) or a specific residual gap.
