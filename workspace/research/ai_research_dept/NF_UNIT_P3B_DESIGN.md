# NF integration P3b — per-stock D7 artifact assembly (design, frozen)

**Review tier:** Tier-2 (pipeline plumbing; declared-invariant review; Tier-1 crafted-object analysis
out of tier). *Tier is a user call.*

**Status:** design frozen 2026-07-22 after a read-only premise check; pending implementation.

## Premise check (read-only, done — no falsified assumption)

`render_news_flash_section(assessed, cutoff)` needs, per assessed item: `cluster` (a **ClusterSnapshot
object** — `.fact_occurrence_id`, `.cluster_first_visible_at_iso`, `.members`), `typing`, `route`
(`primary_route` + `content`, the latter via `_member_content`), `evidence_class`, `coordination_fired`.
It **recomputes** `evidence_class` from typing+route (verify-not-trust) and **rejects** macro-routed
flashes — which lines up with P2's `news_render_eligible`.

`ClusterSnapshot` is a frozen dataclass whose `snapshot_id` is recomputed in `__post_init__`, so it can
be reconstructed from P2's serialized cluster payload. P2's artifact does **not** carry `route.content`
(only `content_hash`), so P3b binds the text the same way P3a does — by **recomputing** `content_hash`
from caller-supplied raw rows.

`D7BaseFact.fact_cluster_id == cluster.fact_occurrence_id` (verified earlier) is the join key from a
render-minted `base_record_id` back to P3a's split.

## Flow (per (stock, cutoff))

1. Verify BOTH input artifacts (P2 assessed, P3a split) — dict or path — and require both to be for
   this run's `(cutoff, ingest_class)`.
2. **Chain binding**: P3a's `consumed_assessed_flash_sha256` must equal the P2 artifact's
   `artifact_sha256`. Two artifacts from different runs cannot be mixed.
3. Bind source text by recomputed `content_hash` (same primitive as P3a).
4. **Select** (derived, never caller-supplied): assessed where `news_render_eligible` AND
   `ts_code ∈ route.subject_codes`.
5. Reconstruct a `ClusterSnapshot` per selected flash (self-verifying) and assemble the assessed dicts
   with `route.content` = the hash-bound source text.
6. `render_news_flash_section(...)` → `(card, records, base_facts)`.
7. **Join splits**: for every minted base fact with `importance >= D7_IMPORTANCE_FLOOR`, look up
   P3a's split by `fact_cluster_id` and emit `{base_record_id, attributes}`. Coverage must be EXACT —
   a missing split is a hard error (it is what `verify_d7_artifact`'s split-coverage gate would refuse
   anyway, but P3b fails earlier with a clearer cause).
8. `build_attribute_bundle(splits, base_facts, records, card=, decision_id=, cutoff=)` →
   `D7DecisionArtifact` (self-verifying through `verify_d7_artifact`).

## Declared invariants (the review target)

1. **Chain binding.** Both artifacts verified; both identity-matched to this run; P3a's consumed-P2
   SHA equals the P2 artifact's SHA. Mixing runs is refused.
2. **PIT inherited; no dated source of its own.** The only text P3b uses is bound by recomputed
   `content_hash` against the P2 population, exactly as in P3a. (The caller obtains rows from
   text_store; that read is not trusted.)
3. **Selection is derived**: `news_render_eligible ∧ ts_code ∈ subject_codes` — never a caller-supplied
   list of flashes.
4. **Split coverage is exact**: every `importance>=4` minted base fact has exactly one P3a split, joined
   by `fact_cluster_id`; missing → hard error; no extra splits are passed through.
5. **Verify-not-trust throughout**: the reconstructed `ClusterSnapshot` self-verifies; render recomputes
   `evidence_class`; `build_attribute_bundle` + `verify_d7_artifact` re-derive the full lineage.
6. **`decision_id` discipline**: exact non-empty `str` (the ledger becomes its authority in P4).
7. **NON_EVIDENTIARY**; a stock with no selected flashes yields **no artifact** (an explicit
   "nothing to decide" result), never an empty-but-valid D7 artifact.

8. **The assembly result is a bound identity** (added after GPT review round-1 P1). Not a loose dict:
   `AssemblyProvenance` is frozen, canonically hashed, self-verifying, and its hash body contains
   `artifact_hash` — the upstream chain cannot be dropped, swapped, or paired with another artifact.

## Output shape (was a declared decision; RULED ON in review round-1)

P3b returns the in-memory `D7DecisionArtifact` plus the assembly provenance, and seals nothing on
disk of its own — P4 is the sealing boundary. **The reviewer accepted "no separate on-disk seal" but
raised a P1 on the rest of it:** the provenance was a plain dict, and P4's three interfaces
(`record_decision`, the executors, `seal_decision_archive`) all take only a `D7DecisionArtifact` —
so the dict had nowhere to go. An ordinary call sequence silently dropped it, and the sealed archive
could then prove the D7 artifact but **not which P2/P3a run, which stock, or which facts produced
it**. The design claim "P4 binds all of it" was false as built.

**Fold (P3b half, done):** `AssemblyProvenance` — frozen, canonically hashed, self-verifying, hash
body includes `artifact_hash` — plus `verify_assembly_provenance` (strict key set + schema + recompute)
and `require_assembly_for(assembly, artifact)`, the single binding door P4 must call.

### ⚠ FROZEN P4 OBLIGATION (the consumer half — a precondition of the P4 unit, not optional)

Until P4 does all five, the chain still terminates at P3b's exit:

| # | obligation |
|---|---|
| a | **require** the `AssemblyProvenance` at `record_decision` / `seal_decision_archive` — no default, no `None` path |
| b | call `require_assembly_for(assembly, artifact)` so a provenance for a different artifact is refused |
| c | write `assembly_hash` into the decision ledger entry (first-write-wins then also pins *which upstream chain* owns the decision id) |
| d | embed `assembly.payload` + `assembly_hash` in the sealed archive under a bumped `_ARCHIVE_SCHEMA` (v1 → v2, extending the strict key set), re-verified through `verify_assembly_provenance` on read-back |
| e | refusal tests: missing provenance, artifact-hash mismatch, and an archive round-trip proving the chain survives (a v1-shaped archive must not verify) |

This is mirrored verbatim in the [news_flash_assemble.py](engine/news_flash_assemble.py) module
docstring so it cannot be lost between units.

## Not in P3b

- `record_decision` / `execute_news_decision` / `seal_decision_archive` → **P4**.
- Consuming the sealed decision into the session archive → **C1**.
- The macro seat; coordination (NFC) detection (still unevaluated, carried from P2).
