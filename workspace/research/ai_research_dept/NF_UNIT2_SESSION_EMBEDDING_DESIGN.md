# NF Final-Integration Unit 2 — Decision-archive → session-archive embedding (design)

**Review tier:** **Tier-2** (governance plumbing; 2-round budget; NO crafted-object/dunder analysis).
Rationale: Tier-1 is reserved for seal spend / holdout / PIT kernels / **sealed-archive commitment** —
and the sealed-archive commitment *is* Unit 1, which closed SOUND-TO-PROCEED at `6886e39` under the
frozen v2 model. Unit 2 **assembles** that already-hardened core into the session flow; the pipeline
stays NON_EVIDENTIARY with zero production callers until FORWARD_PREREG. *Tier is a user decision —
say so and I re-scope.*

**Status (HISTORICAL — SUPERSEDED 2026-07-24; do not implement from this document).**
First correction (2026-07-22): the premise was FALSIFIED by the pre-implementation self-review —
this unit consumes a sealed NF decision archive that the session pipeline never produces; the doc
was retained as the C1 spec pending producers P1→P4. Second correction (C1 review round-1 P1#1 +
re-review#3 P2-1): §1's scope — "replace the inline news seat in `analyst_chain._execute_attempt`
and write the session archive" — is **NOT C1 and must not be built before the chain-version bump**:
the manifest hashes `analyst_chain.py`'s bytes into the frozen v3.1 contract, so ANY edit to that
file (even a default-OFF hook parameter) is a version bump by definition. The live contracts are:

- **C1 (consumption only, closed separately):** [NF_UNIT_C1_DESIGN.md](NF_UNIT_C1_DESIGN.md) —
  `news_session_embed.consume_news_decision` + identity block + opaque flags; NO `analyst_chain`
  change (byte-hash-pinned until the bump).
- **The session WIRING (this doc's §1 scope):** deferred to the final-integration chain-version
  bump unit, governed by the **FROZEN WIRING OBLIGATIONS** in
  [news_session_embed.py](engine/news_session_embed.py)'s module docstring (bump-first;
  opaque-scalar judge semantics; full-timestamp cutoff binding; fixed fallback dichotomy).

The seven invariants below remain valid **as the bump unit's inherited requirements** (1–5, 7 are
already discharged inside the consumption module; 6 becomes the bump's own legacy-compat proof).
Nothing below this line is a current work order.

---

## 1. Scope — what this unit IS

Replace the news seat's inline LLM scoring in `analyst_chain._execute_attempt` with **consumption of
the sealed NF decision archive**, and embed that decision's identity into the four-seat session
archive.

Today: `seat_results["news"] = run_seat("news", prompt, {"news_card": …}, …)` — an inline LLM call.
After: the news seat's outcome is **derived from a sealed, verified NF decision archive** produced by
the Unit-1 chain (`execute_news_decision` → `seal_decision_archive`), read back through the single
sanctioned door.

## 2. Explicitly NOT in this unit (separate units, do not bundle — §10)

- **The macro fourth seat** (§6 / §7 step 9) — new card, new prompt, new seat, four-seat composite.
- **`scorecard.py` strict-additive change + scoring contract + chain bump** (§7 step 7, step 14).
- **Post-judge isolation / chief liveness** (§7 step 10).
- **Adversarial prompt-freeze tests** (§7 step 4 of the final-integration list).
- **Single-day smoke + §5 M6 read-quality gate** (§7 step 14).
- Any change to `composite` weights (`macro` stays `shadow_only` until §5 weighted promotion).

The name "four-seat embedding" is therefore **aspirational** for the eventual state; this unit wires
the NEWS seat only. The fourth seat lands in its own unit.

## 3. Declared invariants (Tier-2: these are what the review judges)

1. **Single door.** The session archive's news outcome comes **exclusively** from
   `load_and_verify_decision_archive`. `load_and_verify_execution_archive` is audit/display only and
   MUST NOT appear on this path (binding requirement #7 from the executor arc, NF_SEAL_HARDENING).
   *Enforced mechanically:* an AST guard asserting the symbol is never imported/called in the
   session-embedding module.
2. **Identity, not copy.** The session archive embeds the decision's **identity block** —
   `decision_id`, `archive_sha256`, `contract_hash`, `artifact_hash`, `bundle_hash`,
   `final_registry_hash`, `outcome_hash`, `ledger_head_at_seal` — so the session archive's own
   `archive_sha256` commits to exactly which decision was consumed. It does not re-derive or
   re-summarise the decision's internals.
3. **Recompute, don't trust.** `seats["news"].final` is recomputed from the verified decision
   archive's sealed evaluation (the existing `verify_archive_semantics` philosophy: never trust a
   sealed *value*, re-derive it from sealed *entries*). A mismatch is a hard failure, not a warning.
4. **Fail-closed seat.** Missing decision archive, verification failure, or `news_status != success`
   → the news seat is an **error seat** (`final=None` + structured error), never a silent absence and
   never a zero score. `archive_complete` then refuses publication, matching existing seat-error
   semantics exactly.
5. **`vector_only` never yields a scalar.** If the consumed decision's contract is `vector_only`,
   there is no `seats["news"].final` and the session archive is `binding_eligible=false` — the mode
   is carried through, never collapsed to a number.
6. **Legacy archives still load.** The embedded block is strictly additive; chain versions ≤ v3.1
   remain loadable and their `archive_complete` verdict is unchanged (proven by a legacy-identity
   test over existing fixtures).
7. **No decision-time data leaks backwards.** The news card / decision inputs are already
   cutoff-bound by Unit 1; this unit adds no new read of post-cutoff data.

## 4. Acceptance criteria

Each invariant gets a test that FAILS if the invariant is removed:
1. AST guard: `load_and_verify_execution_archive` absent from the embedding path.
2. Tamper the embedded identity block → session `archive_sha256` changes (commitment proven).
3. Forge the decision archive's `evaluation` value → recompute mismatch → hard failure.
4. Each of {no archive, verify raises, `news_status=hard_failed`} → error seat, `complete=False`,
   nothing published.
5. `vector_only` decision → no `seats["news"].final`, `binding_eligible=false`.
6. A v3.1 fixture archive loads and its `archive_complete` verdict is byte-identical to before.

## 5. Open question for the reviewer (declared up front)

The existing `run_seat` path produces `record`, `what_could_weaken` (falsifiers), and `fence_stats`,
which the **bear seat** consumes. The NF decision archive produces `horizon_theses` with a mandatory
`strongest_counter` per thesis (D3 falsification-first), not the legacy `what_could_weaken` shape.
This unit maps NF `horizon_theses[].strongest_counter` → the falsifier registry the bear consumes,
preserving the bear's existing typed contract. **If the reviewer thinks the bear should instead
consume the NF theses natively, that is a contract change and belongs in its own unit** — flag it,
do not fold it here.
