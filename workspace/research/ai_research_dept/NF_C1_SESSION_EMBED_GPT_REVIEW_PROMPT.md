# GPT Cross-Review Request — NF integration C1 (sealed-decision consumption + session embedding) — Tier-2

Reviewing **one unit**: C1, the CONSUMER half — the last unit of the NF chain
(P1→P2→P3a→P3b→P4a→P4b all closed SOUND; the remaining final-integration items — ChainContract
binding, production root binding, chain-version bump, macro seat — are separate units).

## ⚠ FROZEN REVIEW TIER — Tier-2

Per CLAUDE.md §10: set at design freeze; **do not escalate mid-arc**. Declared-invariant review;
the v3 threat-model scope rule applies (root selection out of scope, findings hold the root set
fixed); no crafted-object/dunder analysis. The sealing/verification core below this unit closed its
own Tier-1 arcs.

**Commit under review: `6a95a62`** on branch `calendar-unfreeze`.

## What C1 is

`news_session_embed.consume_news_decision(code, cutoff, *, ingest_class, roots..., nf_contract)`:
rebuild the D7 artifact deterministically from committed evidence → read the sealed decision
through **`load_and_verify_decision_archive`** (the decision-level canonical door) → return
`{"seat", "nf_decision", "no_decision"}`. Plus an **optional `nf_news` hook** in
`analyst_chain.run_stock/_execute_attempt` (default `None` = legacy path byte-identical): hook on →
the news seat comes from consumption (no inline LLM call) and the session archive gains a
strictly-additive `nf_decision` identity block sealed under `archive_sha256`.

## The seven declared invariants (spec: NF_UNIT2_SESSION_EMBEDDING_DESIGN.md §3; wiring:
NF_UNIT_C1_DESIGN.md)

1. **Single door** — `load_and_verify_execution_archive` never appears in the module (AST-guarded
   test over names/attributes).
2. **Identity, not copy** — the embedded block is ids + hashes only (the 8 spec fields, plus
   `assembly_hash` — a strictly-additive 9th field the spec predates: P4a's chain identity —
   plus `output_mode` / `binding_eligible` as carried semantics; no payload copies).
3. **Recompute, don't trust** — the seat's `final` must equal the sealed
   `news_final_by_horizon[primary]` AND the sealed `news_final` (the deep entry-level re-derivation
   — `trusted_eval` — runs inside the load door); mismatch → hard error seat.
4. **Fail-closed seat** — missing archive / verify failure / non-success → error seat
   (`final=None` + structured error); the SHARED integrity predicate
   (`verify_publishable_archive`) then refuses publication — tested end to end.
5. **`vector_only` never yields a scalar** — `final=None` WITHOUT error; `binding_eligible=False`
   carried in the identity block.
6. **Legacy unchanged** — hook default OFF; both signatures default `nf_news=None`; the nf branch
   and block are unreachable. Turning it on in production is the final-integration chain bump
   (the chain's same-version drift guard makes in-place behaviour flips illegal — this is the
   premise-checked correction to the old "replace the inline seat" wording, per the user-approved
   option B).
7. **No post-cutoff reads** — inputs are committed evidence + sealed artifacts only.

## Declared design decisions (challenge explicitly)

- **`NothingToDecide` → fallback, everything else → fail-closed.** No flash routed = a structural
  "no news decision exists" → `no_decision=True`, the caller falls back to the legacy inline seat.
  A decision that SHOULD exist but cannot be verified NEVER falls back (that would silently swallow
  a broken producer chain). Is that dichotomy right?
- **Falsifier mapping (the spec-§5 declared question):** NF `horizon_theses[].strongest_counter` →
  legacy `{condition: str≤60, observable_in: "news"}` entries (≤5, truncation/loss counted in
  `falsifier_norm`). If you think the bear should consume NF theses natively, that is a
  separate-unit contract change — flag, don't fold.
- **The consumption seat's `record` carries empty `factor_scores`/`penalty_scores`** (+ the mapped
  falsifiers): the NF scorecard's dimensions are a different contract from the session seat
  weights, so pretending they are session dims would fake comparability; `scored_dims/total_dims`
  report the NF factor-entry count for display. The judge receives the seat `final` as today. Right
  call, or should the NF dims be surfaced differently (separate unit)?
- **Total `except Exception` conversion to error seats** inside the consumption door — invariant
  4's "fail-closed seat" as a total function (the `archive_complete` philosophy). Acceptable at
  Tier-2, or do you want specific exception classes enumerated?

## Files (pin to `6a95a62`)

- https://raw.githubusercontent.com/henrydan111/quant-system/6a95a62/workspace/research/ai_research_dept/engine/news_session_embed.py
- https://raw.githubusercontent.com/henrydan111/quant-system/6a95a62/workspace/research/ai_research_dept/engine/analyst_chain.py (the hook diff only — `_execute_attempt` / `run_stock` / the `nf_decision` block)
- https://raw.githubusercontent.com/henrydan111/quant-system/6a95a62/workspace/research/ai_research_dept/tests/test_news_session_embed.py
- design: https://raw.githubusercontent.com/henrydan111/quant-system/6a95a62/workspace/research/ai_research_dept/NF_UNIT_C1_DESIGN.md
- spec: https://raw.githubusercontent.com/henrydan111/quant-system/6a95a62/workspace/research/ai_research_dept/NF_UNIT2_SESSION_EMBEDDING_DESIGN.md

## Self-review

Clean for GPT. Premise checks: the same-version drift guard (hence hook-not-replace);
`verify_publishable_archive` accepts empty `factor_scores` lists and refuses error seats / None
finals (so acceptance 4/5 compose structurally); thesis key set verified against
`news_horizon._THESIS_KEYS` (8 keys, no "thesis" — my first test fixture had it wrong and produced
a hard_failed chain, caught by probing rather than assuming). Tests: **11** C1 acceptance tests +
full `ai_research_dept` **895** green.

## Review questions

1. **The consumption matrix**: routed+success / vector_only / no-decision / missing / hard_failed /
   tampered — every cell lands in exactly one of {seat with final, seat without final, no_decision,
   error seat}? Any input shape that escapes the total conversion?
2. **Identity block completeness** (invariant 2): anything a future session-archive auditor needs
   that is missing — or anything present that is a payload copy in disguise?
3. **The four declared design decisions.**
4. **The hook diff**: with `nf_news=None`, is the legacy path provably byte-identical (any
   evaluation-order or archive-shape side effect I missed)?
5. **Verdict:** SOUND-TO-PROCEED (C1 closed; remaining = final-integration units) or specific
   in-tier gaps.
