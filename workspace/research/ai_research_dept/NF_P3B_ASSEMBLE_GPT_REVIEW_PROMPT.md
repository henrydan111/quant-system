# GPT Cross-Review Request — NF integration P3b (per-stock D7 artifact assembly) — Tier-2

Reviewing **one unit**: P3b, where the market-wide artifacts become ONE stock's decision input — the
last producer stage before P4 records/executes/seals.

## ⚠ FROZEN REVIEW TIER — Tier-2

Per CLAUDE.md §10: the tier is set at design freeze and **the reviewer must not escalate it mid-arc**.
Tier-2 = declared-invariant review against ordinary well-formed in-process inputs. **Tier-1 analysis
(crafted objects, subclass overrides, dunder/metaclass, adversarial in-process callers) is OUT OF
TIER** — record such a finding as a tracked note, or raise a tier change as a **recommendation to the
user**, whose decision it is.

**Commit under review: `c591629`** on branch `calendar-unfreeze`.

## Context — the chain so far

P1 typing (SOUND) → P2 cluster/route/assess (SOUND) → P3a D7 attribute split (SOUND; ended up fully
deterministic, no LLM) → **P3b assembly** → P4 record/execute/seal → C1 session embedding.

## Flow

1. Verify BOTH inputs (P2 assessed, P3a split), dict or path; require both for this run's
   `(cutoff, ingest_class)`; require P3a's `consumed_assessed_flash_sha256 == p2["artifact_sha256"]`.
2. Bind source text by **recomputing** `content_hash` from caller-supplied raw rows (same primitive as
   P3a — the caller's `text_store` read is not trusted).
3. Select (derived): `news_render_eligible ∧ ts_code ∈ route.subject_codes`.
4. Reconstruct a `ClusterSnapshot` per selected flash (self-verifying `snapshot_id`), assemble the
   assessed dicts with `route.content` = the hash-bound text.
5. `render_news_flash_section(...)` → `(card, records, base_facts)` — it **recomputes**
   `evidence_class` and rejects macro routes.
6. Join P3a splits by `fact_cluster_id` for every base fact with `importance >= D7_IMPORTANCE_FLOOR`.
7. `build_attribute_bundle(...)` → `D7DecisionArtifact` (self-verifying via `verify_d7_artifact`).

## Declared invariants (the review target)

1. **Chain binding** — both artifacts verified + identity-matched + P3a provably produced FROM this
   exact P2 artifact. Mixing two runs is refused.
2. **PIT inherited; no dated source of its own** — the only text used is bound by recomputed
   `content_hash` against the P2 population.
3. **Selection is DERIVED**, never caller-supplied.
4. **Split coverage EXACT** — every `importance>=4` minted base fact has exactly one P3a split
   (joined by `fact_cluster_id`); missing → hard error here, with a clearer cause than the downstream
   `verify_d7_artifact` gate would give.
5. **Verify-not-trust throughout** — reconstructed `ClusterSnapshot` self-verifies; render recomputes
   `evidence_class`; `build_attribute_bundle` → `verify_d7_artifact` re-derives the whole lineage.
6. **`decision_id` discipline** — exact non-empty `str` (the ledger becomes its authority in P4).
7. **NON_EVIDENTIARY** — a stock with no routed flash raises `NothingToDecide`; an evidence-free
   decision is never manufactured.

## Declared design decisions (please challenge these explicitly)

- **P3b seals nothing of its own.** It returns the in-memory `D7DecisionArtifact` + a provenance dict
  (consumed P2/P3a SHAs, selection basis), because **P4 is the sealing boundary** and binds all of it
  into the decision archive. Is that right, or does P3b need its own sealed artifact for auditability?
- **The reconstructed `ClusterSnapshot` has no independent claimed `snapshot_id` to check against** —
  P2's `_cluster_payload` does not carry it. The reconstruction is bound by P2's *artifact* seal
  (verified on load), and `__post_init__` recomputes the id. I judged that adequate rather than
  bumping the frozen-SOUND P2's schema to add `snapshot_id`. Is the artifact-level binding enough, or
  should the cluster self-verify independently?

## Files (pin to `c591629`)

- https://raw.githubusercontent.com/henrydan111/quant-system/c591629/workspace/research/ai_research_dept/engine/news_flash_assemble.py
- https://raw.githubusercontent.com/henrydan111/quant-system/c591629/workspace/research/ai_research_dept/tests/test_news_flash_assemble.py
- design: https://raw.githubusercontent.com/henrydan111/quant-system/c591629/workspace/research/ai_research_dept/NF_UNIT_P3B_DESIGN.md
- downstream contract: https://raw.githubusercontent.com/henrydan111/quant-system/c591629/workspace/research/ai_research_dept/engine/news_cards.py

## Self-review

Clean for GPT. Premise check done before designing (the habit that caught two falsified premises
earlier): confirmed what `render_news_flash_section` needs per item, that `ClusterSnapshot` is
reconstructable and self-verifying, and that P2 does not carry `route.content` (hence the recompute
binding). Tests: 16 P3b + full ai_research_dept **831** + data_infra news 17 green.

## Review questions

1. **PIT / no-lookahead:** any path where text or a flash outside the verified P2 population, or from
   another cutoff, reaches the artifact?
2. **Chain binding:** is `consumed_assessed_flash_sha256 == p2.artifact_sha256` sufficient to prove the
   two inputs belong to one run, or is there a mixing case it misses?
3. **Split coverage:** does the `fact_cluster_id` join plus the importance floor exactly match what
   `verify_d7_artifact`'s coverage gate demands — could P3b build a `splits` list that the gate then
   refuses (or, worse, accepts while being wrong)?
4. **The two declared design decisions above** — please rule on both.
5. **Verdict:** SOUND-TO-PROCEED (to P4) or a specific in-tier declared-invariant gap.
