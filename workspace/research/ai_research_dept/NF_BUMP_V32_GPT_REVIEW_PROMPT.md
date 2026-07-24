# GPT Cross-Review Request — NF final-integration BUMP unit (chain_v3.2) — Tier-2

Reviewing **one unit**: the chain-version bump that DISCHARGES the four frozen wiring obligations
from the C1 arc — the last implementation unit of the NF wave before the separate macro-seat /
prompt-freeze / smoke+M6 units.

## ⚠ FROZEN REVIEW TIER — Tier-2 (user-assigned at design freeze)

Declared-invariant review; no crafted-object/dunder analysis; the v3 threat-model root-scope rule
applies (findings hold the root set fixed). The NF sealing core and the P4a ledger/archive doors
closed their own Tier-1 arcs and are UNCHANGED here.

**Commit under review: `3a88064`** on branch `calendar-unfreeze`.

## Context

C1 closed SOUND with four FROZEN WIRING OBLIGATIONS (recorded in
[news_session_embed.py](https://raw.githubusercontent.com/henrydan111/quant-system/3a88064/workspace/research/ai_research_dept/engine/news_session_embed.py)'s
docstring, now marked DISCHARGED). User decisions at this unit's design freeze: **Tier-2**;
`primary_decision_horizon = "1-3d"`; `input_cutoff_time = "18:00:00"`.

## The four obligations → what shipped

**(a) Bump-first.** `CHAIN_VERSION = "chain_v3.2"`; the wiring (your C1 P1#1 said it MUST land with
a version bump, never in-place) ships in the SAME commit that moves the byte pin: `run_stock` /
`_execute_attempt` gain `nf_news=None` (default = pure legacy; `main()` does NOT auto-enable — the
enablement is FORWARD_PREREG's governed-runner obligation per threat model v3); the news-seat
branch; the strictly-additive `nf_decision` identity block sealed under `archive_sha256`. Platform
`RENDER_VERSION` synced (a lockstep test enforces chain==platform).

**(b) Opaque-scalar judge semantics.** `judge()` now passes `opaque_scalar` seats through:
`adj_final = clamp(final)` — no empty-list recompute (your C1 P1#2: the sealed 49.0 became
`adj_final=0.0` in a publishable archive), and NO discount even when a bear refutation targets the
news seat: there is no contract-registered NF dim for it to act on, and inventing a
refutation→NF-score mapping would be a new scoring contract (its own unit — flag if you disagree
with that boundary). Only scalar seats carry the flag (the C1 P2#1 discipline); vector/error seats
never reach `judge` (the `ok_seats` filter — pinned).

**(c) Cutoff binding.** The v3.2 manifest gains a frozen `nf_contract` section
(`{schema_id: c16_news_horizon_v1, output_mode: primary_horizon, primary_decision_horizon: "1-3d",
input_cutoff_time: "18:00:00", ingest_class: forward}`), validated per-value at
`ChainContract.load` (`_verify_nf_contract`: strict key set; HH:MM:SS regex; mode-conditional
primary — `vector_only` must carry `None`; registered ingest_class) and byte-compared in
`verify_contract_matches_manifest`'s on-disk re-verification. `news_session_embed` gains:
- `nf_contract_from_chain(chain_contract)` — the `NewsScoringContract` is constructed ONLY from the
  disk-verified `ChainContract.nf`; a pre-v3.2 contract (no section) is refused fail-closed;
- `nf_cutoff_for_day(day, chain_contract)` — `YYYYMMDD` → the full frozen timestamp via the SAME
  `_canonical_cutoff` every NF door uses; a bare date can never reach the NF doors.

**(d) Fallback dichotomy** — preserved verbatim in the hook branch (`no_decision` → legacy inline
seat; consumed/error seats adopted, never silent fallback).

## Files (pin to `3a88064`)

- https://raw.githubusercontent.com/henrydan111/quant-system/3a88064/workspace/research/ai_research_dept/engine/analyst_chain.py (the diff: version note, `NF_CONTRACT`, `_verify_nf_contract`, `ChainContract.nf`, judge branch, hook wiring, manifest section)
- https://raw.githubusercontent.com/henrydan111/quant-system/3a88064/workspace/research/ai_research_dept/engine/news_session_embed.py (the two helpers + DISCHARGED obligations block)
- https://raw.githubusercontent.com/henrydan111/quant-system/3a88064/workspace/research/ai_research_dept/platform/server.py (RENDER_VERSION sync only)
- https://raw.githubusercontent.com/henrydan111/quant-system/3a88064/workspace/research/ai_research_dept/tests/test_news_chain_bump.py (13 tests)
- https://raw.githubusercontent.com/henrydan111/quant-system/3a88064/workspace/research/ai_research_dept/tests/test_news_session_embed.py (the moved byte pin)
- design: https://raw.githubusercontent.com/henrydan111/quant-system/3a88064/workspace/research/ai_research_dept/NF_UNIT_BUMP_DESIGN.md

## Self-review

Clean for GPT. Premise checks: `judge` only receives `final is not None` seats (so the opaque
branch cannot see a scalar-less seat); `verify_manifest_body` verifies by fingerprint recomputation
(the new section is strictly additive and automatically covered); the manifest freeze procedure is
unchanged (first v3.2 run writes `chain_v3.2/manifest.json`; v3.1 archives live in their own
version dir). The hook-on wiring test runs `_execute_attempt` with stubbed seat/bear runners (no
LLM) against a REAL produced-and-sealed NF decision: consumed seat + `adj_final == final` end to
end + identity block sealed + `complete=True`; plus no-decision fallback, error-seat
unpublishable, default-off pure legacy. One test-construction correction made honestly: my fake
bear initially had an empty `kill_switches`, which the shared integrity predicate rightly refuses
— fixed the stub, not the predicate. Tests: **13** bump + full `ai_research_dept` **909** green.

## Review questions

1. **Obligation fidelity:** does each of (a)–(d) match its frozen text exactly — anything
   discharged in letter but not in spirit?
2. **The judge branch:** is `opaque_scalar` pass-through safe against every seat shape that can
   legally reach `judge` under v3.2 (legacy seats, consumed seats, mixed archives), and is the
   no-discount-without-a-contract boundary the right unit split?
3. **The `nf_contract` section:** validation completeness (`_verify_nf_contract`), the load/verify
   round-trip, and the pre-v3.2 refusal — any way a session runs NF with an unfrozen or mismatched
   NF contract?
4. **Version hygiene:** CHAIN_VERSION + byte pin + RENDER_VERSION all moved in one commit — any
   remaining v3.1-frozen surface this bump silently altered (manifest contract files list is
   unchanged: 7 files)?
5. **Verdict:** SOUND-TO-PROCEED (bump unit closed; NF wave remaining = macro seat / prompt-freeze
   / smoke+M6 as separate units; enablement = FORWARD_PREREG) or specific in-tier findings.
