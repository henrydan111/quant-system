# NF integration C1 — sealed-decision consumption + session embedding (design, frozen)

**Review tier:** Tier-2 (assembly of the already-hardened Unit-1/P4a core into the session flow;
2-round budget; no crafted-object analysis; v3 root-scope rule applies). *Tier is a user call.*

**Status:** design frozen 2026-07-24 after a read-only premise check of `analyst_chain.py`.
**This document is THE C1 contract** (re-review#3 P2-1): the old
[NF_UNIT2_SESSION_EMBEDDING_DESIGN.md](NF_UNIT2_SESSION_EMBEDDING_DESIGN.md) is HISTORICAL /
superseded — its seven invariants carry over here (and into the bump unit's inherited
requirements), but its §1 wiring scope is NOT C1.

**Round-1 fold (2026-07-24, 2×P1, zero declines — the unit SHRINKS).** P1#1: even a default-OFF
hook parameter edits `analyst_chain.py`, whose BYTES are hashed into `engine_contract_sha256` —
the "byte-identical legacy path" claim held at runtime but broke the frozen v3.1 CONTRACT
(manifest collision under the same version label). Folded per the reviewer's minimal fix:
`analyst_chain.py` reverted to the exact frozen v3.1 bytes; C1 now ships the consumption module
ONLY, and the wiring (hook parameter, news-seat branch, `nf_decision` block) is deferred to the
formal chain-version bump — recorded as **FROZEN WIRING OBLIGATIONS** in the module docstring
(the P3b→P4a pattern): (a) any `analyst_chain.py` edit = a NEW chain version, never in-place;
(b) opaque-scalar judge semantics — `adj_final == final` absent an NF-native discount contract,
with a hook-on regression pinning it (P1#2: the legacy judge recomputes `adj_final` from the
seat's legacy scoring lists, which are empty BY CONTRACT for a consumed seat, so the sealed 49.0
became `adj_final=0.0` in a publishable archive — the sealed score silently erased); the consumed
seat now carries `opaque_scalar=True` as the anchor; (c) the production hook binds the session
`day` to the FULL pre-declared NF cutoff timestamp, never a bare date (reviewer-noted boundary);
(d) the fallback dichotomy is fixed (`no_decision` → legacy seat; verification failure → error
seat, never fallback). A mechanical guard test asserts `analyst_chain.py` contains no trace of
the wiring until the bump.

## Premise check (read-only, done — one load-bearing correction)

1. `_execute_attempt` runs three inline seats (`fund`/`tech`/`news`) via `run_seat`, then bear +
   judge; the archive embeds `seats` / `records` / falsifier registries and is sealed by
   `archive_seal`. The news seat's falsifiers feed the bear via `what_could_weaken`.
2. **The chain has a same-version drift guard**: changing the executed input/contract fingerprint
   under an unchanged `CHAIN_VERSION` is refused. The old Unit-2 wording ("replace the news seat
   inline scoring") would flip seat behaviour on external state (archive presence) inside v3.1 —
   *that is the excluded chain-bump territory (§2 of the Unit-2 spec)*.
   **Correction #1 (option B, user-approved 2026-07-22):** consumption is optional with a legacy
   fallback, never a replacement of v3.1 behaviour.
   **Correction #2 (round-1 P1#1 — supersedes the "optional hook, default OFF" shape):** even a
   default-OFF hook PARAMETER edits `analyst_chain.py`, whose bytes are hashed into the frozen
   contract — so C1 ships NO `analyst_chain` change at all; ALL session wiring is deferred to the
   chain-version bump under the FROZEN WIRING OBLIGATIONS.
3. `load_and_verify_decision_archive(decision_id, artifact, ...)` needs the D7 **artifact** — the
   consumer must rebuild it deterministically from the committed evidence
   (`resolve_committed_evidence` + `assemble_stock_artifact` under the driver's
   `nf_decision_id`), the same construction P4b proved. Verification then re-derives everything.

## Shape

New module `engine/news_session_embed.py`:

- **`consume_news_decision(code, cutoff, *, ingest_class, ledger_dir, prov_dir, archive_dir,
  store_dir, artifact_dir, nf_contract) -> dict`** — the C1 single door. Rebuilds the artifact from
  committed evidence, reads back through `load_and_verify_decision_archive` (THE only sanctioned
  consumer door — invariant 1), and returns:
  - `seat`: a seat-result dict in the EXACT `run_seat` result shape (`final` / `record` /
    `scored_dims` / `total_dims` [+ `error`]), where `final` is **recomputed** from the sealed
    evaluation entries (invariant 3) — on `primary_horizon`, the archived
    `evaluation.news_final_by_horizon[primary]` recomputed against `news_final`; a mismatch is a
    hard error seat, not a warning;
  - `nf_decision`: the **identity block** (invariant 2): `decision_id, archive_sha256,
    contract_hash, artifact_hash, bundle_hash, final_registry_hash, outcome_hash,
    ledger_head_at_seal` — identities only, no payload copies;
  - failure of ANY step (missing archive, verification failure, `news_status != success`) ⇒ an
    **error seat** (`final=None`, structured `error`, empty record) + `nf_decision=None`
    (invariant 4) — never a silent absence, never a zero;
  - `vector_only` contract ⇒ `final=None` WITHOUT error, `binding_eligible` carried false
    (invariant 5).
- **Falsifier mapping** (the declared open question, spec §5): NF `horizon_theses[].strongest_counter`
  → the legacy `what_could_weaken` registry shape the bear consumes (typed dicts, ids minted by the
  session layer as today). Mapping only — if the reviewer wants the bear to consume theses natively,
  that is a separate-unit contract change; flag, don't fold.
- **AST guard test**: `load_and_verify_execution_archive` never imported/called in this module
  (invariant 1's mechanical guard).

**Session wiring: NOT in C1** (round-1 P1#1 + re-review#2 P2#2 sweep). C1 ships NO `analyst_chain`
change of any kind — the manifest hashes that file's bytes into the frozen v3.1 contract, so even a
default-OFF parameter is a contract change. *(Historical note: the hook described below shipped in
the BUMP unit as a **roots-only API** — `nf_roots`, five trusted dirs, engine-derived binding; the
free-form `nf_news` callable named here was retired by the BUMP review's P1#1 before any freeze.)*
The hook (`nf_news` parameter, news-seat branch, the
strictly-additive `nf_decision` archive block, `run_stock` threading) is specified ONLY as the
**FROZEN WIRING OBLIGATIONS** in the [news_session_embed.py](engine/news_session_embed.py) module
docstring, and lands exclusively with the formal chain-version bump: (a) any `analyst_chain.py`
edit = new chain version; (b) opaque-scalar judge semantics (`adj_final == final` for
`opaque_scalar=True` seats — set ONLY on scalar seats; vector_only carries `opaque_external` only)
+ the hook-on regression; (c) session `day` binds to the FULL pre-declared NF cutoff timestamp;
(d) the fallback dichotomy (`no_decision` → legacy seat; verification failure → error seat, never
fallback). Until the bump, a mechanical guard pins `analyst_chain.py`'s **byte hash** (re-review#2
P2#3 — string-absence alone cannot prove frozen bytes).

## Not in C1 (per the Unit-2 spec §2 — separate units)

Macro seat; `scorecard.py`/scoring-contract/chain bump (ALL session wiring, incl. the hook and the
`nf_decision` archive embedding); post-judge isolation; prompt-freeze tests; single-day smoke +
§5 M6 gate.

## Acceptance criteria (each invariant one failing-without-it test; wiring items are
## OBLIGATION DEMOS, not C1 acceptances — re-review#2 P2#2)

1. AST guard (execution-archive door absent).
2. *(obligation demo)* an `nf_decision`-shaped block under `archive_seal` — tampering changes the
   seal (property of the FUTURE embedding, demonstrated so the bump unit inherits a pinned test).
3. Forged sealed `evaluation` ⇒ recompute mismatch ⇒ hard error seat.
4. {no archive, verify raises, hard_failed} ⇒ error seat; a seat with an error is unpublishable
   through the SHARED integrity predicate.
5. `vector_only` ⇒ no scalar, no `opaque_scalar` flag, `binding_eligible=false` carried.
6. `analyst_chain.py` byte-hash pinned to the frozen v3.1 blob until the version bump.
7. No new post-cutoff read (the consumption takes only sealed artifacts + committed evidence).
