# NF Integration — corrected unit sequencing (self-review 2026-07-22)

**Why this doc exists:** the pre-implementation self-review of `NF_UNIT2_SESSION_EMBEDDING_DESIGN.md`
found that unit's premise FALSIFIED. Unit 2 was scoped as "consume the sealed NF decision archive" —
but **the sealed NF decision archive is never produced by the session pipeline.** This doc records the
verified state and the corrected sequencing. Scope/tier decisions below are the user's.

## Verified state (read-only investigation, certain — not hypotheses)

1. **The entire NF decision stack has ZERO production callers.** `execute_news_decision`,
   `seal_decision_archive`, `render_news_flash_section`, `build_attribute_bundle`,
   `load_and_verify_decision_archive`, `D7DecisionArtifact`, `record_decision` appear ONLY in the NF
   engine modules and tests — never in `analyst_chain.py` or any driver script. ~40 review rounds of
   hardened code, wired to nothing.
2. **The session news seat uses a DIFFERENT renderer.** `analyst_chain.build_inputs` calls
   `cards.render_news_card(r, day)` (event-library summary card), NOT
   `news_cards.render_news_flash_section` (the NF D7 flash section). Different renderers, different
   inputs.
3. **No producer of NF-flash typing exists.** `assess_flash` needs
   `{event_type∈NF enum, verification_status, content_kind, direction, importance 0-5, is_rumor}`.
   `irm_typing.py` types 互动易 Q&A only (different schema). The event library carries
   `event_type/direction/importance` but NOT `verification_status/content_kind/is_rumor`, and those
   three cannot be deterministically derived from the event-library `event_type`. **NF-flash typing
   is new LLM classification, not wiring.**
4. **`build_inputs` reads event-library summaries, not text_store provenance rows.**
   `build_cluster_snapshots` requires full-provenance columns (content_hash/object_id_hash/three
   timestamps/ingest_class) stamped by `text_store`. The session's `retr` DataFrame does not carry
   them → a new per-stock text_store read path is needed.

## The corrected chain (producer P1→P4, then consumer C1)

| unit | what | build vs wire | new LLM calls | depends on |
|---|---|---|---|---|
| **P1** | NF-flash typing pass — classify each day's flashes into the NF typing schema | **DONE + SOUND 2026-07-22** — driver around the EXISTING `news_ingest.type_batch` classifier + inherited `text_store.load_text` PIT gate. GPT Tier-2 arc: round-1 CHANGES-REQUIRED (2 blockers: forward-missing-store fail-closed; artifact immutability/collision) → re-review#1/#2 REVISE (cutoff-identity precision: second→microsecond) → **ceiling reached** on a nanosecond precision instance → **user arbitration: reject sub-microsecond cutoffs** (microsecond-max contract makes the path bijective — definitive class closure, not another per-instance fold). 19 tests. | 1 batched pass/day | — |
| **P2** | **DONE + SOUND 2026-07-22** (GPT Tier-2 SOUND-TO-PROCEED at `4b901f4`, 8-round arc) — MARKET-WIDE (corrected from "per-stock"): text_store read → `build_cluster_snapshots` → `route_cluster` (existing router, PIT as-of registry built by P2) → `assess_flash` (with P1 typing) → sealed assessed-flash artifact. Per-stock selection is P3. GPT Tier-2 arc: round-1 CHANGES (P0 as-of registry + 2 P1) → re-review#1 CHANGES (namechange as-of names, typing wash) → ceiling → **user arbitration: fail-closed omit** (name resolves only on a clean ann_date-anchored unique as-of name; no current-name fallback; numeric code still resolves). Design: NF_UNIT_P2_DESIGN.md | wire (+ new read path) | 0 | P1 |
| **P3a** | **DONE + SOUND 2026-07-22** (GPT Tier-2 SOUND-TO-PROCEED at `d178b47`, 7-round arc) — market-wide D7 attribute splitting, keyed by `fact_occurrence_id` (a flash relevant to 50 stocks is split ONCE; `D7BaseFact.fact_cluster_id == cluster.fact_occurrence_id` is the join key). **v1 ended up FULLY DETERMINISTIC — no LLM**: the arc established that no partial-text scheme survives review (free-written invents facts → verbatim span loses context → sentence expansion still splits neighbouring-sentence qualifiers), so `fact` is the WHOLE hash-bound source, `source_status` is derived, `economic_linkage`/`timing` deferred. Source bound to P2 by **recomputing** `content_hash`. Contract ENFORCED at the read boundary (schema v3 + `fact_mode`). [news_flash_split.py](engine/news_flash_split.py) | **NEW** (became deterministic) | **0** | P2 |
| **P3b** | per-stock: select `subject_codes` hits → reconstruct+verify cluster → `render_news_flash_section` → join P3a splits by `fact_cluster_id` → `build_attribute_bundle` → `D7DecisionArtifact` | wire | 0 | P3a |
| **P4** | per-stock: `record_decision` → `execute_news_decision` (factor + penalty legs) → `seal_decision_archive` | wire | 2 | P3 |
| **C1** | consume `load_and_verify_decision_archive` → recompute news seat → embed identity (= old "Unit 2") | wire | 0 | P4 |

Each unit is Tier-2, sequential. Net new LLM cost per stock ≈ **P4's 2 legs** (factor+penalty) + a
share of P1's batched typing (+ possibly P3 splits). That is a material per-stock cost increase on top
of the existing fund/tech/news/bear seats.

## Decisions the user must make before P1 starts (convergence protocol: re-scoping is a user call)

- **P0 architecture — market-wide typing pass vs per-stock.** `assess_flash` typing is per-FLASH, not
  per-stock; a single industry flash is relevant to many stocks. The efficient shape is: **P1 types
  each flash once per day (market-wide); P2–P4 build one NF decision per (stock, day) from that
  stock's relevant typed flashes.** Confirm this, or specify per-stock typing.
- **Full-wire vs offline-batch + optional-consume.** The NF pipeline is NON_EVIDENTIARY with zero
  production callers until FORWARD_PREREG. Two integration shapes:
  - **(A) Full inline wiring** — the per-stock session loop produces-then-consumes the NF decision
    (P1–P4 run inside/before `run_stock`). Heaviest; every session run pays the NF LLM cost.
  - **(B) Offline batch + optional consume** — a separate per-day driver produces sealed NF decision
    archives; the session's news seat consumes the archive **when present**, else falls back to the
    current inline `render_news_card` seat. Lets C1 be a thin optional consumer and decouples the
    heavy producer from every session run. Matches the "NON_EVIDENTIARY, zero production callers"
    posture better.
  Recommendation: **(B)** — build the producer as an offline driver first (P1→P4), keep the session
  seat's current behaviour as the fallback, and make C1 an *optional* consumer gated on archive
  presence. This avoids forcing the full NF cost into every session run before there is any forward
  evidence that it improves the seat.
- **P3 open question — where do D7 attribute splits come from?** `build_attribute_bundle` takes
  `splits` (per-fact attribute decompositions for importance≥4 facts). In tests these are
  hand-authored. Is the split a deterministic rule over the flash, or another LLM step? This scopes
  P3.

## Status of the earlier docs

- `NF_UNIT2_SESSION_EMBEDDING_DESIGN.md` — its consumer-side invariants (single door, identity-not-
  copy, recompute-don't-trust, fail-closed seat, vector_only, legacy-unchanged) remain valid **as the
  C1 spec**; only its position (last, after P1–P4) and its premise (archive already produced) were
  wrong. Header updated to point here.
