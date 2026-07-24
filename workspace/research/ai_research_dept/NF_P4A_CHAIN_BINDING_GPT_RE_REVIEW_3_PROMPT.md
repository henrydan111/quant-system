# GPT Re-review #3 — NF integration P4a — Tier-1 — FINAL round (open sweep)

Round **3 of 3** (the unit's §10 budget). The final pre-SHIP round reverts to a **full-unit open
sweep**. If your verdict is not SOUND-TO-PROCEED, I stop folding and take the divergence to the user
with three options (re-scope the threat model / switch mechanism / accept residual as tracked debt)
rather than opening a round 4.

**Frozen threat model** (unchanged, the sending precondition):
https://raw.githubusercontent.com/henrydan111/quant-system/166813c/workspace/research/ai_research_dept/NF_ARCHIVE_THREAT_MODEL.md
— classify findings in/out-of-scope; scope-bounded verdict.

**Fold commit: `166813c`** (you reviewed `8479b31`). Verdict folded: **REVISE, 2 P1** — zero declines.
Same invariant class two consecutive rounds (caller-controlled evidence), so per §10 this fold is
**architectural**, exactly along your prescribed fix.

## Your two P1s → the structural fold

> P1#1: re-derivation had no trusted evidence root — caller-supplied P2/P3a/rows only prove "the
> caller's own materials cohere" (you walked a wholly forged plain-dict chain end to end).
> P1#2: `_verified_inputs` verified and then returned the CALLER's dict — a stateful subclass swaps
> values after verification.
> Fix: resolve P2/P3a and rows from trusted, fixed-location committed records; exact-type deep-plain
> snapshot; then re-derive.

Implemented as **`resolve_committed_evidence(cutoff, *, ingest_class, store_dir, artifact_dir)`** in
[news_flash_assemble.py](https://raw.githubusercontent.com/henrydan111/quant-system/166813c/workspace/research/ai_research_dept/engine/news_flash_assemble.py):

1. **The door takes trusted ROOTS, never evidence objects.**
   `record_decision(ledger_dir, decision_id, artifact, *, assembly, store_dir, artifact_dir)` — the
   dict/path/DataFrame evidence parameters are GONE. `store_dir` = the text store root; `artifact_dir`
   = the canonical write-once artifact slots. Both are operator trust roots of the same standing as
   `ledger_dir` itself.
2. **Resolution order = custody chain.** Text store first (`require_exists=True`; unknown class or
   missing panel = no data root, refused). Then P1 at its canonical slot — seal re-verified AND
   **every typed flash's `content_hash` must recompute from THE store's rows** (P1←store: a P1 file
   minted over a different store dies). Then P2 — `consumed_typed_flash_sha256` must equal that P1's
   `artifact_sha256` (P2←P1). Then P3a (P3a←P2; re-checked inside assemble). Then the full P3b
   re-derivation under the claimed identity, both hashes bit-equal (unchanged from round 1's fold).
3. **TOCTOU dead wholesale.** Disk JSON via `json.loads` is plain by construction — there are no
   caller objects on the door path at all. For the remaining producer-path callers of
   `_verified_inputs` (P3b as producer), it now **snapshots-then-verifies** (JSON round-trip BEFORE
   verification), so what was verified is byte-identical to what gets used; a lying `dumps` produces a
   consistently-used lie, which is P1#1 territory and dies at the door's disk resolution.
4. **Mechanical guard** (the §10 repeat-class rule): a parameter-enumeration test pins the exact
   signatures of `record_decision` / `prove_assembly_by_rederivation` / `resolve_committed_evidence`.
   A future evidence-object parameter fails the enumeration until deliberately reviewed.
5. **Where trust bottoms out (stated, not hidden):** the text store (the system's upstream
   data-provenance layer — an attacker who can fabricate store panels is attacking the data layer,
   which has its own attestation upstream) and **first-write-wins at the canonical artifact slots**
   (identical trust class to the ledger's own first-write-wins: the committed record is whichever was
   committed first). Typing content itself is LLM-derived and not re-derivable — its commitment IS the
   write-once P1 slot.

Downstream doors (seal / read-back / recovery) remain as you accepted them in round 2: byte-compare
against the ledger-pinned row, inheriting the (now genuinely proven) first write.

## Your probes, pinned as regressions

[test_news_p4a_chain_binding.py](https://raw.githubusercontent.com/henrydan111/quant-system/166813c/workspace/research/ai_research_dept/tests/test_news_p4a_chain_binding.py) (24 tests):

- `test_wholly_forged_evidence_files_refused_without_a_store` — your probe half 1: hand-rolled
  plain-dict P1 with recomputed self-hash committed to a scratch root → refused at the missing data
  root, **no ledger file**.
- `test_forged_p2_file_over_a_real_store_dies_on_chain_binding` — your probe half 2 in its sharpest
  form: a REAL store + REAL P1, with fully self-consistent but wrong-lineage P2/P3a substituted at the
  canonical slots → refused on P2←P1, **no ledger file**.
- `test_first_write_door_accepts_no_caller_evidence_objects` — the enumeration lock (P1#2's
  structural regression: there is no parameter to attack).
- The round-1 matrix retained: per-field forged assembly claims, cross-chain evidence, the hand-built
  artifact, the original forged-provenance probe — all now refusing via root resolution, each
  asserting no ledger write.

Honest verification note: the new probes exercise the new signature, so they are not apples-to-apples
pre-fix probes — the pre-fix acceptance is your own e2e reproduction at `8479b31`. Full
`ai_research_dept` suite **871** green.

## Files (pin to `166813c`)

- https://raw.githubusercontent.com/henrydan111/quant-system/166813c/workspace/research/ai_research_dept/engine/news_flash_assemble.py
- https://raw.githubusercontent.com/henrydan111/quant-system/166813c/workspace/research/ai_research_dept/engine/news_decision.py
- https://raw.githubusercontent.com/henrydan111/quant-system/166813c/workspace/research/ai_research_dept/engine/news_archive.py (unchanged this round — context)
- https://raw.githubusercontent.com/henrydan111/quant-system/166813c/workspace/research/ai_research_dept/tests/test_news_p4a_chain_binding.py
- https://raw.githubusercontent.com/henrydan111/quant-system/166813c/workspace/research/ai_research_dept/tests/assembly_fixtures.py
- design + fold record: https://raw.githubusercontent.com/henrydan111/quant-system/166813c/workspace/research/ai_research_dept/NF_UNIT_P4_DESIGN.md

## Open-sweep questions (final round)

1. **Does the custody chain close class (i)?** store → P1 (hash-recompute binding) → P2 (SHA) → P3a
   (SHA) → re-derivation → ledger pin → downstream byte-inheritance. Any remaining path by which a
   forged/decoupled provenance value is sealed or accepted — including through the stated trust
   boundary (first-write-wins slots + the text store as data root)? If you find one, classify whether
   it is in-scope for THIS boundary or an upstream data-layer concern.
2. **Does the fix create new surface?** The `_artifact_path` reuse for slot resolution; the
   `TextStoreError`→`ValueError`→`RegistryError` wrapping (fail-closed preserved?); the
   P1←store recompute over `rows.iterrows()`; the snapshot-then-verify in `_verified_inputs`.
3. **Anything in the whole unit** (ledger + archive + assembly doors) that the two prior rounds'
   narrower focus let through.
4. **Verdict:** SOUND-TO-PROCEED (to P4b) or specific in-scope findings.
