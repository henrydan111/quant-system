# GPT Re-review #3 — NF integration C1 — Tier-2 — FINAL round (open sweep)

Round **3 of 3** (the unit's §10 budget). Final pre-SHIP round = full-unit open sweep. If the
verdict is not SOUND-TO-PROCEED, I stop folding and take the divergence to the user. **Tier stays
Tier-2**; the v3 root-scope rule applies.

**Fold commit: `c4c0d7f`** (you reviewed `59a7f18`). Verdict folded: **REVISE, 3 P2** (both round-1
P1s confirmed closed by you) — zero declines.

## Your three P2s → the folds

1. **`vector_only` carried `opaque_scalar=True`** — contradicting obligation (b)
   (`opaque_scalar ⇒ adj_final == final`) for a seat with no scalar. Folded exactly as you
   prescribed: `opaque_external=True` marks EVERY consumed seat (external origin);
   `opaque_scalar=True` marks ONLY the scalar branch; obligation (b) now states the judge must not
   manufacture a scalar for `opaque_external`-only seats. Regression: the vector seat has **no**
   `opaque_scalar` key at all.
2. **Stale wiring text in the docs** — the round-1 fold shrank the unit but leaked present-tense
   descriptions of the removed hook (the documented §10 doc-sweep failure mode; it has bitten this
   project before, so no defense offered). Swept: the design doc's premise correction explicitly
   supersedes the "optional hook, default OFF" shape; the wiring section states C1 ships NO
   `analyst_chain` change; the acceptance list reframes the seal-commitment test as a
   **wiring-obligation DEMO** the bump unit inherits (C1 writes no session archive); the
   sequencing table's C1 row rewritten to match.
3. **The untouched-guard proved nothing about bytes** — your appended-comment probe passed the
   string checks while changing the contract hash. Replaced with a **byte-hash pin**:
   `analyst_chain.py`'s sha256 is pinned to the frozen v3.1 blob
   (`0a9c58904a1fc1f0ac1f4e9b00d5f69cd3c807e39555ab317bffda501ff2350a` — the blob you verified
   equals the pre-C1 state whose full contract hash is `c0e45d49…`); ANY edit fails the guard; the
   pin moves only with the formal chain-version bump.

## Verification

12 C1 tests + full `ai_research_dept` **896** green (the byte-pin test fails on any
`analyst_chain.py` edit by construction — your probe is now structurally caught).

## Files (pin to `c4c0d7f`)

- https://raw.githubusercontent.com/henrydan111/quant-system/c4c0d7f/workspace/research/ai_research_dept/engine/news_session_embed.py
- https://raw.githubusercontent.com/henrydan111/quant-system/c4c0d7f/workspace/research/ai_research_dept/engine/analyst_chain.py (byte-pinned frozen v3.1)
- https://raw.githubusercontent.com/henrydan111/quant-system/c4c0d7f/workspace/research/ai_research_dept/tests/test_news_session_embed.py
- https://raw.githubusercontent.com/henrydan111/quant-system/c4c0d7f/workspace/research/ai_research_dept/NF_UNIT_C1_DESIGN.md
- https://raw.githubusercontent.com/henrydan111/quant-system/c4c0d7f/workspace/research/ai_research_dept/NF_INTEGRATION_SEQUENCING.md

## Open-sweep questions (final round)

1. **The flag discipline**: `opaque_external` on all consumed seats, `opaque_scalar` on scalar
   only — is the pair complete and non-overlapping for every cell of the consumption matrix, and
   is obligation (b)'s wording now free of contradictions for the bump unit to implement verbatim?
2. **The doc sweep**: any remaining stale phrasing describing removed wiring, in ANY of the five
   C1-touched documents (a mechanical full-text pass, per the §10 rule)?
3. **The byte pin**: is a test-constant sha256 pin the right mechanical hold, or do you see a
   maintenance failure mode worth recording (e.g. the pin being "helpfully" updated without a
   bump — is the comment discipline enough at Tier-2)?
4. **Anything in the whole unit** the prior rounds' narrower focus let through.
5. **Verdict:** SOUND-TO-PROCEED (C1 closed as the consumption unit; the NF wave's remaining work
   = the final-integration bump unit discharging the frozen wiring obligations) or specific
   in-tier findings.
