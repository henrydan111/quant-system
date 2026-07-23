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

## Output shape (declared decision)

P3b returns the in-memory `D7DecisionArtifact` plus a small provenance dict (consumed P2/P3a SHAs,
selection basis). It does **not** seal a separate on-disk artifact: P4 (`record_decision` →
`execute_news_decision` → `seal_decision_archive`) is the sealing boundary and binds all of it into the
decision archive. Flag if you think P3b needs its own seal.

## Not in P3b

- `record_decision` / `execute_news_decision` / `seal_decision_archive` → **P4**.
- Consuming the sealed decision into the session archive → **C1**.
- The macro seat; coordination (NFC) detection (still unevaluated, carried from P2).
