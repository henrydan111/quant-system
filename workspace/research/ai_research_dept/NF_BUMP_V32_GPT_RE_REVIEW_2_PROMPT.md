# GPT Re-review #2 — NF BUMP unit (chain_v3.2, DIFF-SCOPED) — Tier-2

Round 2 of 3. Per CLAUDE.md §10, diff-scoped: does the fold close what it claims, and does it
introduce new surface? **Tier-2**; v3 root-scope rule applies.

**Fold commit: `6747497`** (you reviewed `3a88064`). Verdict folded: **REVISE, 3 P1** — zero
declines.

## Your three P1s → the folds

1. **The hook bypassed consumption/identity/cutoff binding.** The free-form callable is **dead**:
   the parameter is now `nf_roots` — a mapping with EXACTLY the five trusted root dirs (the one
   thing the v3 model leaves outside the boundary); a callable / wrong key set refuses before any
   seat runs (`test_free_form_callback_is_dead` covers your probe shape). The new engine
   chokepoint `_consume_nf_seat` derives the cutoff (`nf_cutoff_for_day`), the NF contract
   (`nf_contract_from_chain`) and the ingest class from the **disk-verified `ChainContract`** and
   calls `consume_news_decision` itself — obligation (c) is engine code now, and the two helpers
   have their production call sites. Completeness gate before sealing: a non-`no_decision` result
   must be an error seat or carry the full 9-field identity block. The hook-on test now exercises
   the PRODUCTION binding (the caller passes roots only; the produced chain lives at the frozen
   18:00 cutoff, so a successful consumption is proof the engine derived it).
2. **`nf_contract` values not locked.** `_from_verified_manifest` now VALUE-LOCKS the section:
   `dict(nf) == NF_CONTRACT` exactly (shape checks retained for diagnostics). Your probe pinned on
   a REAL on-disk fixture: `build_manifest → ensure_immutable_manifest → ChainContract.load`
   round-trips with the frozen values; the hash-self-consistent manifest with `17:00:00` is
   **refused at load** (`test_value_locked_manifest_with_forged_cutoff_refused`). Changing any
   value = another bump (the constant moves with `CHAIN_VERSION`).
3. **The executed consumer was outside the engine contract.** `news_session_embed.py` joins the
   contract-file list (now `_engine_contract_files()`, so the test asserts membership AND that the
   manifest hash actually covers it — recomputing without the file yields a different digest).
   **Declared boundary, rule on it:** the deeper NF-engine files (`news_archive.py` etc.) are NOT
   hashed — they are governed by their own SOUND arcs + the 913-test regime, and the consumer file
   carries the session-facing behaviour; if you judge the hash surface must widen to the full NF
   engine, say so and it goes to the user as a scope decision.

**Version hygiene note:** `chain_v3.2`'s manifest has never been frozen on disk (no
`chain_v3.2/` version dir exists — verified), so these edits are a legal in-flight amendment of
the unfrozen version, not a re-bump. The byte pin moved in the same commit, per its rule; the pin
comment records the amendment.

## Verification

**17** bump tests (4 new + the hook suite reworked to the roots-only surface) + full
`ai_research_dept` **913** green. Honest note: the dead-callback and value-lock regressions
exercise the new surface; your own e2e reproductions at `3a88064` are the pre-fix acceptance
evidence.

## Files (pin to `6747497`)

- https://raw.githubusercontent.com/henrydan111/quant-system/6747497/workspace/research/ai_research_dept/engine/analyst_chain.py
- https://raw.githubusercontent.com/henrydan111/quant-system/6747497/workspace/research/ai_research_dept/tests/test_news_chain_bump.py
- https://raw.githubusercontent.com/henrydan111/quant-system/6747497/workspace/research/ai_research_dept/tests/test_news_session_embed.py (the moved pin)
- (unchanged this round) https://raw.githubusercontent.com/henrydan111/quant-system/6747497/workspace/research/ai_research_dept/engine/news_session_embed.py

## The two diff-scoped questions

1. **Do the folds close all three P1s?** In particular: with `_consume_nf_seat` as the only NF
   path and the roots-only parameter, is there any remaining way a session archive carries a
   non-genuine `nf_decision`, an unfrozen NF contract, or a non-18:00 cutoff — holding the root
   set fixed?
2. **Does the fix create new surface?** The five-root strict key set; the 9-field completeness
   gate (any legal consumption result it would wrongly refuse — e.g. the vector_only seat, whose
   `error` is None and whose block IS present?); the value lock's interaction with future bumps;
   and the declared not-hashed boundary for the deeper NF engine.

Verdict: SOUND-TO-PROCEED (BUMP closed; NF wave remaining = macro seat / prompt-freeze / smoke+M6
as separate units; enablement = FORWARD_PREREG) or specific in-tier findings.
