# NF final-integration unit — chain_v3.2 bump (design)

**Review tier:** proposed **Tier-2** (chain-contract plumbing + judge semantics; no sealed-archive /
seal-spend / PIT-kernel edit — the NF sealing core closed its own Tier-1 arcs; the v3 root-scope
rule applies). *Tier is a user decision at design freeze.*

**Status:** design FROZEN 2026-07-24 — user decisions recorded: **Tier-2**;
`primary_decision_horizon = "1-3d"`; `input_cutoff_time = "18:00:00"` (both frozen into the v3.2
manifest's `nf_contract` section; changing either later = another version bump). This unit DISCHARGES the four
FROZEN WIRING OBLIGATIONS recorded in [news_session_embed.py](engine/news_session_embed.py)'s
docstring (the C1 arc's output) — it is the only remaining implementation unit of the NF wave
before the separate macro-seat / prompt-freeze / smoke+M6 units.

## Premise checks (read-only, done)

1. **`judge()`** (analyst_chain:388) recomputes `adj_finals[seat]` from
   `record.factor_scores/penalty_scores` with bear discounts — for an opaque consumed seat (empty
   lists BY CONTRACT) `total=0.0`: the C1 P1#2 zeroing point. Only seats with `final is not None`
   reach `judge` (ok_seats filter), so `opaque_external`-only (vector) seats never enter — the
   obligation's "judge must not manufacture a scalar" holds structurally.
2. **`build_manifest`** hashes 7 contract files (incl. `analyst_chain.py`, `integrity.py`) byte-wise
   into `engine_contract_sha256`; a version bump = edit `CHAIN_VERSION`, edit files freely, first
   full run freezes `chain_v3.2/manifest.json` (same procedure as v2.9→v3.1).
   `verify_manifest_body` verifies by fingerprint recomputation, not a strict key set → a new
   `nf_contract` section is strictly additive and automatically covered by `manifest_fp`.
3. **No existing cutoff constant** in `config.py` — the day→cutoff binding must be newly frozen;
   the manifest's `nf_contract` section is the natural contract-frozen home.
4. `NewsScoringContract` needs `{schema_id, output_mode, primary_decision_horizon}` — none exist in
   the current manifest; same new section.

## Scope — the four obligations, discharged

**(a) Bump-first.** `CHAIN_VERSION = "chain_v3.2"`; the C1-reverted wiring lands NOW, under the new
version: `run_stock(..., nf_news=None)` → `_execute_attempt(..., nf_news=None)`; news-seat branch
(`no_decision` → legacy inline fallback; consumed seat otherwise — the obligation-(d) dichotomy is
in `consume_news_decision` itself, the hook only routes); strictly-additive `nf_decision` identity
block sealed under `archive_sha256`. The C1 byte pin MOVES: the test constant becomes the v3.2
LF-canonical hash (its comment already mandates exactly this).

**(b) Opaque-scalar judge semantics.** In `judge()`, before the recompute loop:
`if res.get("opaque_scalar") is True: adj_finals[seat] = res["final"]; continue` — the sealed
external scalar passes through UNdiscounted (absent an NF-native discount contract, per the frozen
obligation; a bear refutation targeting the news seat does NOT discount it — there are no
contract-registered dims to discount, and inventing a mapping would be a new scoring contract =
its own unit). Regression pins `news.adj_final == news.final` with AND without bear refutations
present, and pins that a non-opaque seat still discounts (the legacy path is untouched).

**(c) Cutoff binding.** Manifest `nf_contract` section (frozen at version freeze):
`{schema_id: "c16_news_horizon_v1", output_mode: "primary_horizon",
primary_decision_horizon: <user-confirmed>, input_cutoff_time: <user-confirmed "HH:MM:SS">,
ingest_class: "forward"}`. New helpers in `news_session_embed`:
- `nf_contract_from_chain(chain_contract) -> NewsScoringContract` — constructed ONLY from the
  on-disk-verified `ChainContract`'s `nf` mapping (read-only, validated at `ChainContract.load`
  with exact-type checks; missing/malformed section → load refuses, fail-closed);
- `nf_cutoff_for_day(day, chain_contract) -> Timestamp` — `f"{day} {input_cutoff_time}"`
  canonicalized by the SAME `_canonical_cutoff` every NF door uses. The production hook closure is
  then `lambda code, day: consume_news_decision(code, nf_cutoff_for_day(day, cc), ...)` — a bare
  date can never reach the NF doors.

**(d) Fallback dichotomy** — already fixed inside `consume_news_decision` (C1); the hook branch
preserves it verbatim (a `no_decision` result falls through to the legacy inline seat; an error
seat is adopted as-is). A wiring test pins both paths.

## Also in this unit

- `ChainContract` gains the read-only `nf` mapping + load-time validation (integrity/analyst_chain
  are both re-frozen under v3.2 anyway).
- **Turning the hook ON per run stays the CALLER's decision**: `main()` does NOT auto-enable NF
  (the NF pipeline is NON_EVIDENTIARY; the production enablement — real roots, real LLM route,
  batch driver — is FORWARD_PREREG's governed runner, per threat model v3). v3.2 = the capability
  is wired and contract-frozen, not switched on.

## NOT in this unit

Macro fourth seat; adversarial prompt-freeze tests; single-day smoke + §5 M6 gate; any
`scorecard.py` change (judge lives in `analyst_chain`; `compute_scorecard_final` untouched);
FORWARD_PREREG (roots + enablement).

## Acceptance criteria

1. Judge: opaque seat passes through (`adj_final == final`) with/without bear refutations; legacy
   seats still discount; vector/error seats never reach judge (existing filter pinned).
2. Wiring (monkeypatched `run_seat`/`run_bear` stubs — no LLM): hook-on consumed seat lands in
   `seats["news"]` + `nf_decision` sealed into `archive_sha256`; `no_decision` falls back to the
   inline seat; error seat → `complete=False`.
3. `nf_contract_from_chain` / `nf_cutoff_for_day`: round-trip from a manifest fixture; malformed
   `nf_contract` section → `ChainContract.load` refuses; bare-date binding produces the exact
   canonical cutoff.
4. Byte pin: moved to the v3.2 LF hash; the old v3.1 pin retired WITH the version (comment updated).
5. Legacy: v3.1 archives remain loadable/verdict-unchanged (version dirs are separate; existing
   platform version gates untouched — pinned by a no-change assertion on `SCHEMA1_CHAINS` etc.).
