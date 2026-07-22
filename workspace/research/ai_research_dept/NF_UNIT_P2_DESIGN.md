# NF integration P2 — market-wide cluster + route + assess (design, frozen)

**Review tier:** Tier-2 (pipeline plumbing; declared-invariant review; 2-round budget; no
crafted-object/dunder analysis). *Tier is a user call — say so to change it.*

**Status:** design frozen 2026-07-22 after a read-only premise check; pending implementation.

## Premise check (read-only, done — no falsified assumption this time)

The routing layer **exists** and is not new work: `news_routing.route_cluster(content, registry,
cutoff)` returns `{primary_route, subject_codes, industry_tags, concept_tags, mentions}`, built on
`AliasRegistry.resolve_codes(text, cutoff)` (deterministic, alias-based, PIT-bound by cutoff).
`news_routing.build_alias_registry(stock_basic, version=…)` builds the registry from `stock_basic`.
`assess_flash(cluster, typing_rec, route)` already assembles the assessed flash. So P2 is **wiring +
a sealed output artifact**, not new classification/routing.

## Scope correction: P2 is MARKET-WIDE, not per-stock

The sequencing doc labeled P2 "per-stock". That was wrong: **routing** (not clustering) is what
associates a flash to stocks (`route.subject_codes`), and one flash can mention many stocks. So
clustering + routing + assessment are done **once, market-wide, per (cutoff, ingest_class)**, and the
**per-stock selection happens in P3** (render that stock's relevant assessed flashes). P2 extends P1's
market-wide posture from typing to clustering+routing+assessment.

## Flow (market-wide, per cutoff+panel)

1. Load the day's cutoff-visible news via `text_store.load_text("news", cutoff, ingest_class=…)`
   (same PIT gate + forward fail-closed rule as P1 — reused, not re-implemented). Keep the raw rows
   (full `content`, needed for routing text).
2. `build_cluster_snapshots(rows, cutoff)` → sealed `ClusterSnapshot`s (clustered by wording family @
   effective day).
3. Load + verify the P1 typed-flash artifact for the SAME (cutoff, ingest_class)
   (`load_typed_flash_artifact`); index typing by `content_hash`.
4. Build the `AliasRegistry` from `stock_basic` (as-of cutoff).
5. Per cluster: pick the **deterministic representative member** (`members[0]` — the snapshot is
   already sorted by `(content_hash, src, decision_visible_at)`), take its full `content` (from the
   loaded rows) + its P1 `typing[content_hash]` → `route_cluster(content, registry, cutoff)` →
   `assess_flash(cluster, typing, route)`.
6. Emit a **sealed market-wide assessed-flash artifact**: per cluster {cluster_id,
   fact_occurrence_id, representative content_hash, typing, route, evidence_class,
   coordination_fired}, plus a self-describing header (cutoff, ingest_class, population_hash over the
   cluster set, the P1 `artifact_sha256` it consumed, `artifact_sha256`). P3 selects per stock by
   `route.subject_codes` (and, later, industry/concept exposure).

## Declared invariants (the review target)

1. **PIT inherited + consistent cutoff.** P2 loads via `load_text` (cutoff filter + forward
   fail-closed) and builds clusters with the SAME canonical `cutoff` (reuse P1's `_canonical_cutoff`,
   microsecond-max). `build_cluster_snapshots` independently re-asserts `effective_at <= cutoff`.
   Routing is as-of the same cutoff (`resolve_codes(..., cutoff)`), so an alias listed after cutoff is
   not resolved.
2. **P1 binding — same identity, full coverage, fail-closed.** P2 consumes the P1 artifact for the
   EXACT (cutoff, ingest_class), verifies its `artifact_sha256` + `population_hash` on load, and binds
   the consumed `artifact_sha256` into P2's own artifact. Every cluster representative's `content_hash`
   MUST be present in the P1 typing index; a missing one is a hard error (P1/P2 population mismatch),
   never a silent default typing.
3. **Routing is deterministic + PIT.** `route_cluster` over `resolve_codes(..., cutoff)` is
   deterministic given the alias registry; the registry's `content_hash` (version + as-of) is recorded
   in P2's artifact so P3/P4 can bind the exact routing basis. No LLM in P2.
4. **evidence_class is verify-not-trust.** `assess_flash` recomputes `evidence_class` from typing +
   route (existing guard); P2 does not carry a caller-supplied class.
5. **Macro-routed flashes are kept but flagged.** A `primary_route == "macro"` cluster stays in the
   market-wide artifact (audit) but is marked so P3's NEWS render excludes it (`render_news_flash_
   section` already rejects macro route). The macro seat is a separate unit; P2 does not route macro
   into the news decision.
6. **Immutable, self-describing, write-once persistence.** Same discipline as P1: canonical-cutoff
   microsecond path, write-once/first-write-wins under a lock, load re-verifies both hashes.
7. **NON_EVIDENTIARY.** Empty day → empty artifact (P1 empty ⇒ P2 empty); replay-class marker.

## Acceptance criteria (each a fail-if-removed test)

1. A flash visible after cutoff, or an alias listed after cutoff, does not appear / does not resolve.
2. P2 consuming a P1 artifact of a DIFFERENT cutoff/class → refused; a cluster whose representative
   content_hash is absent from P1 typing → hard error.
3. Deterministic: same (cutoff, panel, P1 artifact, stock_basic) → identical `artifact_sha256`.
4. A macro-routed flash is flagged and excluded from the news-render selection.
5. Tampered P2 artifact (or altered consumed-P1 SHA) → refused on load.
6. Write-once/first-write-wins + microsecond-cutoff path (inherited discipline) hold.

## GPT round-1 fold (CHANGES-REQUIRED: 1 P0 + 2 P1) — all folded

- **P0 (as-of registry PIT leak):** P2 no longer accepts a pre-built registry (whose build-cutoff it
  couldn't verify). It takes raw `stock_basic` and **builds the alias registry itself AS-OF the
  canonical cutoff**, so a future-listed stock cannot resolve. The as-of routing basis (registry
  hash/version + industry/concept term-set hashes) is recorded in `routing_reference`.
- **P1-#2 (dict artifact bypassed the seal):** `verify_typed_flash_artifact(dict)` extracted in P1;
  P2 verifies the P1 artifact for BOTH dict and path inputs (schema + artifact_sha256 +
  population_hash + content_hash uniqueness + n_flashes count). A dict's self-claimed SHA is never
  trusted.
- **P1-#3 (coverage only checked the representative):** P2 now asserts the raw content-hash set
  EQUALS the P1-typed set exactly (`seal_hash(sorted(set(df.content_hash))) == P1.population_hash`)
  before clustering — missing/extra/duplicate refuses.
- **Representative-member routing:** RESOLVED IN P2 (not deferred) — routing now UNIONs every cluster
  member's mentions, so a cluster whose members mention different stocks (the 120-char-key case) keeps
  all of them. Typing still uses the representative (the population gate guarantees every member is
  P1-typed; `assess_flash` consumes one typing per cluster).
- **coordination:** now recorded as `coordination_evaluated: False` (unassessed), not a bare `False`
  that could read as "confirmed no coordination".

## Deferred / disclosed simplifications in the P2 implementation (honest, not hidden)

- **CLI reference assembly is an explicit seam.** `assess_day_flashes` (the testable core) takes the
  alias registry, industry-term set, and concept-term set INJECTED. The CLI's `_build_reference_inputs`
  (build the registry from `stock_basic` as-of cutoff; the SW L1 industry-name set from
  `provider_metadata`; the THS concept-name set from `config.load_concept_members`) is a documented
  `NotImplementedError` seam, wired at the first real offline run — it depends on live reference files
  (some affected by the 2026-07-13 incident) and per-source PIT details that deserve their own care.
  The reviewable unit is the injected core + persistence; the term sources are all confirmed to exist.
- **`coordination_fired` is inert in P2 v1.** P2 calls `assess_flash` without a coordination flag, so
  the NFC coordination/pump negative-evidence path is not exercised. `news_ingest.coordination_flag`
  needs `structured_backing_status` from the event store (a §6 wiring); flagging coordination is its
  own unit. P2 v1 assesses typing + route only.

## Not in P2 (separate units)

- Per-stock selection + `render_news_flash_section` + D7 splits → **P3**.
- `record_decision` + `execute_news_decision` + `seal_decision_archive` → **P4**.
- Consume + embed into the session archive → **C1**.
- The macro fourth seat.
