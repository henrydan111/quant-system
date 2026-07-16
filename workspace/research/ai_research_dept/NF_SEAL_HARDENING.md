# NF Seal Hardening — pre-forward gate (deferred fortress items)

**Status:** OPEN — this file MUST be fully closed before the first *forward
(evidentiary)* news run. It does NOT gate NON_EVIDENTIARY replay/backtest work.

**Decision (2026-07-13, user directive):** the news-pipeline seal foundation went
through three implementation-review FIX-FIRST rounds (3B → 3B → 4B). The findings
split into two threat models:

1. **Genuine correctness / determinism under NORMAL operation** — a wrong result
   or non-deterministic output with no adversary. These were FIXED immediately
   (see "Fixed now" below).
2. **Fortress hardening against our-own-future-bugs / adversarial in-process
   self-mutation** — defends against a *future downstream bug* directly mutating a
   sealed object, forging a hash, or hand-editing our own parquet. The news
   pipeline is **NON_EVIDENTIARY** (replay only) with **zero production callers**;
   nothing it emits feeds a real decision until the FORWARD_PREREG gate far
   downstream. So these are deferred to THIS milestone, which is the explicit
   pre-forward gate — not dropped.

The rule: **build the product on the fixed-correctness foundation now; close every
item in this file before any forward run consumes the seal for a real decision.**

---

## Fixed now (genuine correctness / determinism — landed 2026-07-13)

| # | Finding | File | What was wrong under normal op | Fix |
|---|---------|------|--------------------------------|-----|
| 1 | B1 | `text_store._hash_row` | flat `key=value\|…` join is ambiguous — `title="x\|content=y",content="z"` and `title="x",content="y\|content=z"` hash identically → two distinct news rows dedup to one (**data loss**) | `news` uses an injection-proof JSON list-of-pairs; the 4 populated legacy stores keep the flat form (byte-stable) — see "Deferred B1-legacy" |
| 2 | B3 | `text_store.ingest_rows` | read/check/append/write had no lock → two concurrent ingesters each read the old file, second `os.replace` clobbers the first's rows | `_store_lock` (atomic-mkdir spin) around the whole transaction |
| 3 | B3 | `text_store.load_text` | a news partition missing the `ingest_class` column loaded as forward (validation only ran when the column existed) → history could leak into a forward decision | absence of the column is now fail-closed for `CLASS_REQUIRED_SOURCES` |
| 4 | M2 | `news_ingest.build_cluster_snapshots` | grouped by source-family only → a wording reappearing weeks later merged into the first occurrence's date → `flow_count=0` on the new day | group by **(family, effective calendar day)** → reappearance = a new `family@day` fact occurrence; same family shares `cluster_id` (breadth counts wording once) |
| 5 | M1 | `news_ingest.build_coverage_artifact` | a complete pull WITH rows was labeled `confirmed_absent` (mislabels news as "no news") | added `complete_present`; `confirmed_absent` only when complete AND zero rows |
| 6 | M1 | `fetchers.fetch_news` / `fetch_news_covered` / `build_coverage_artifact` | a `None`/failed API response sealed as `complete + confirmed_absent` (false absence) | `response_ok` flag → `source_available=False` → `source_unavailable`, never absent |
| 7 | B4 | `news_routing.resolve_codes` | ADR/name matching iterated `exact` in dict-insertion order → same sealed hash, different output order (non-deterministic) | canonical `sorted(exact.items())` iteration |
| 8 | M3 | `news_ingest.no_exchange_session_since_publish` | a zero-length/reversed/unknown-state target interval silently counted as price discovery | validate each interval (`start < end`, `state ∈ {tradable,suspended,locked}`) — fail closed |

Enforced by: `tests/data_infra/test_text_store_news_isolation.py`,
`tests/data_infra/test_news_fetch_coverage.py`,
`workspace/research/ai_research_dept/tests/test_news_ingest_deterministic.py`,
`…/test_news_routing.py`.

---

## Deferred to this gate (fortress — close before forward)

Each item names the review finding, the threat model (why it is not a
normal-operation bug), and GPT's prescribed exact fix.

### H1 — Tagged, collision-free canonical AST  (review B1, `news_seal.canon`)
> **补充(re-review#8 R2, 2026-07-16):** 空白垫 claim_id 变体(` CLAIM:x `)因 canon
> 的空白折叠与原身同印——同属本项。**席位接线必须逐字节保存身份字符串**(不折叠、
> 不 strip、不大小写化),把身份规范化整体留给 H1 的 tagged AST。
- **Threat:** `canon()` uses bare strings as type markers, so distinct values
  can share a seal: `None` vs the literal `"\x00NULL\x00"`; a timestamp vs the
  literal `"T:<iso>"` string; `{1:"x"}` vs `{"1":"x"}` (keys via `str(k)`);
  `np.int64(7)` vs `"7"`; list vs tuple; native `datetime` vs `pd.Timestamp`.
  Requires a decision input whose VALUE literally equals a sentinel/tag form —
  never produced by real typed vendor data, but a latent collision surface.
- **Fix:** one versioned tagged AST in `src/` consumed by BOTH `text_store` and
  `news_seal`: `["null"]`, `["str",v]`, `["timestamp",cn_iso]`, `["int",dec]`,
  `["float",hex]`, `["map",pairs]`, `["list",…]`, `["tuple",…]`; typed dict keys;
  strict canonical JSON `allow_nan=False`; canonicalize supported NumPy/Pandas/
  native datetime, reject unsupported. Add an injectivity matrix test.

### H1-legacy — Structured hash for the 4 legacy text sources  (review B1)
- **Threat:** `anns_d` / `irm_qa_sh` / `irm_qa_sz` / `research_report` still use
  the ambiguous flat `key=value|…` join (a free-text `q`/`a`/`title`/`url` could
  forge a boundary). Kept flat to preserve their EXISTING on-disk `content_hash`.
- **Fix:** migrate them to the structured encoding as a deliberate store re-hash
  (new `adapter_contract_hash`, one-time rebuild), not a silent mid-stream change.

### H2 — Deep immutability under self-mutation  (review B2)
- **Threat:** `verify_sealed` checks only at construction; factory-built objects
  still contain mutable inner containers. A future downstream bug could mutate
  `ClusterSnapshot.members` (tuple of mutable dicts) / an `AliasRegistry` /
  `AtomicClaim` / `SystemicExposureSnapshot` built by direct-but-self-consistent
  construction, changing ownership/routing under an unchanged hash. `deep_ro`
  leaves sets mutable; `canon` doesn't understand `MappingProxyType`, so
  `seal_hash(deep_ro(x)) != seal_hash(x)`.
- **Fix:** every `__post_init__` canonicalizes + recursively deep-freezes its own
  inputs via `object.__setattr__` (freeze sets→frozenset, dicts→MappingProxyType,
  seqs→tuple; `canon` understands all three); prefer `init=False` + audited
  classmethods retaining canonical payload bytes; re-`verify()` at every trust
  boundary (`resolve_codes`, `flow_features`, `scoring_owner`). Test: build a
  self-consistent mutable object, mutate it, assert the mutation is rejected.

### H3 — Row-rooted lineage: `TextRowSeal`  (review B3)
- **Threat:** `build_cluster_snapshots` trusts caller-supplied `content_hash` /
  `object_id_hash`; a forged pair with different tail content yields the same
  snapshot ID. Hand-editing the store's ingestion timestamps, or deleting the
  `ingest_class` column (partially closed by fix #3), can misdate visibility.
  Under normal operation the hashes come from `text_store` and are correct.
- **Fix:** a full-hash `TextRowSeal` binding canonical raw fields + full
  adapter-contract hash + source + object/content hashes + publication/retrieval/
  first-ingestion/decision-visible timestamps + missing-publication flag +
  ingest class. Verify every row seal and RECOMPUTE `decision_visible_at` on load;
  make `ingest_class` a mandatory typed field in a news stamp schema;
  `ClusterSnapshot` accepts only verified `TextRowSeal`s with `ingest_class=="forward"`;
  validate all referenced hashes as full lowercase SHA-256; make `n_outlets` /
  first-visibility derived-or-sealed (currently excluded from the payload).

### H4 — Claim/ownership mechanically PIT-bound  (review B4)
- **Threat:** `build_atomic_claim` accepts a loose mutable route dict + arbitrary
  `alias_registry_hash` (tests pass `"reghash"`); it binds none of claim text,
  snapshot/member hashes, cutoff, primary route, taxonomy hashes, route-policy
  version, or an approved exposure mapping. `scoring_owner` can then receive any
  structurally-sealed exposure and assign `macro`. Alias PIT bounds are optional
  (`cutoff` omitted → future-listed admitted); current `stock_basic.name` is used
  with no historical name-validity interval.
- **Fix:** make alias `as_of` mandatory with valid listing/delisting (fail closed
  on missing dates); row-level historical aliases from `namechange` + dated
  H/ADR seeds; sealed PIT-effective industry/concept taxonomy snapshots; build
  `AtomicClaim` from a verified `ClusterSnapshot` + exact atomic text/span +
  effective registry + taxonomy objects + cutoff + route-policy hash (not a
  caller dict); bind claim-text hash / snapshot ID / fact ID / route / mentions /
  subject codes / tags / cutoff / all governing hashes; bind the permitted
  exposure mapping to the claim/fact and have `scoring_owner` cross-check it
  before assigning `macro`. **This is built when scoring consumes the claim** —
  the claim is currently an unconsumed stub.

### H5 — Coverage from typed fetch-response records  (review M1)
- **Threat:** `fetch_news_covered` returns a mutable dict; `population_hash`,
  availability, and watermarks are caller assertions, not derived; no raw-response
  hashes; no atomic manifest+watermark publication. (The two worst false-absence
  paths — None response, complete-with-rows — are closed by fixes #5/#6.)
- **Fix:** the fetch layer returns typed response/window records (API outcome +
  raw payload hashes); build coverage directly from those + the actual population
  (derive count/hash internally); enforce whitelist, timestamp ordering, window
  schema, monotonic watermark, hash formats, and atomic manifest/watermark publish.

### H6 — Sealed target-session snapshot  (review M3)
- **Threat:** `target_intervals` is an optional raw list; even with structural
  validation (fix #8) a "tradable" interval on a non-open day, or intervals that
  don't cover the exchange session, aren't checked against the calendar.
- **Fix:** a sealed target-session snapshot (target code + calendar-policy hash +
  source/state hash + complete normalized non-overlapping intervals validated
  against open days and exchange price-discovery sessions); target-specific
  decisions consume the artifact, not a raw list.

### H7 — True fact-clustering for cross-midnight syndication  (review M2)
- **Threat:** fix #4 buckets by calendar day, so one burst syndicated across
  midnight splits into two occurrences (a conservative over-count, not a silent
  zero). Acceptable for now; a real later reappearance is correctly a new
  occurrence.
- **Fix:** deterministic bounded occurrence episodes (gap-based) or actual fact
  clustering so cross-midnight syndication of ONE event stays one occurrence.

---

## Seat-wiring REQUIREMENTS (from the 8-round step-5/6 GPT arc — binding on the next block)

The step-5/6 substrate passed its gate (SOUND-TO-PROCEED, 2026-07-16, commit
`272c13e`). The reviewer's accumulated requirements for the seat-wiring block are
BINDING inputs to its design, collected here verbatim-in-substance:

1. **Ledger owns the authoritative `decision_id`** — atomic first-write-wins
   `decision_id → bundle_hash` under ONE lock; the ledger checks the EXPECTED id,
   requires `verify_d7_artifact` to pass on the exact artifact, and commits the
   first write atomically BEFORE any payload construction or LLM call. A second
   different hash for the same id must fail; identical recomputation may be
   idempotent. It accepts ONLY `D7DecisionArtifact`s passing `verify_d7_artifact`
   — never a bare self-sealed `AttributeBundle` (`verify_bundle_registry` is NOT
   the lineage boundary).
2. **Closed payload AST** — the serializer consumes a closed set of node types
   (typed `EvidenceRef` nodes for references; `[ID]` is only their canonical
   output encoding); reject sets/custom objects; NEVER `default=str`.
3. **No fragment concatenation** — a known id split across strings (`["NFD","01"]`)
   is tolerated at the gate because the canonical serialization keeps fragments
   separated; seat wiring must therefore PROHIBIT any later concatenation and
   re-gate the EXACT final serialized bytes.
4. **Seal the exact payload/registry pair** — seal the exact serialized payload
   bytes + registry hash before every positive LLM call; construct payloads
   exclusively from `build_factor_payload_ids` over the artifact's final registry.
5. **Identity bytes preserved exactly** — no strip/casefold/whitespace-collapse on
   claim/record identities anywhere in seat wiring (H1 owns canonicalization).

## Chain-touching-unit REQUIREMENTS (from the seat-wiring units-1+2 GPT arc — binding)

Seat-wiring units 1+2 (decision ledger + choke point + two-leg state machine)
passed their gate (SOUND-TO-PROCEED, 2026-07-16, commit `bdf8e73`, 3-round arc).
The reviewer's requirements for the chain-touching unit are BINDING:

1. **The chain's ONLY executor input is a freshly created immutable view of the
   verified `payload_text`** — never expose `payload_ast` (or any mutable
   component) to an executor; mutation-after-verification is otherwise
   undetectable (the reviewer's headline requirement).
2. **Expected-context provenance**: `expected_decision_id` comes from the
   ledger/artifact; `expected_consumer_seat` / `expected_use` /
   `expected_target_dimension` / `expected_output_mode` come ONLY from the
   frozen scoring contract — never from payloads, LLM output, or caller input.
3. **Persist execution/output provenance before binding** (which payload hash was
   executed, raw output hash, validation verdict) — self-minted `NewsLegOutcome`
   objects are possible in-process (H2-deferred); the archive/binding path must
   rely on persisted provenance + `verify_outcome_for_binding`, never on an
   outcome object alone.
4. **M2⁴ zero-evidence path**: a zero-factor-positive population is legal —
   deterministic NO-SCORE contribution 0. Prefer emitting the required all-zero
   factor/horizon result WITHOUT an LLM call; otherwise output validation must
   enforce all required (dimension, horizon) pairs, zero scores, and no citations.
5. **Output validation binds every (dimension, horizon) result to typed evidence
   and recomputes `dimension_ceiling` per result** before acceptance (the leg
   input gate is use×seat; the dimension binding bites here).
6. **Ledger head anchoring**: the decision ledger's hash-chain head anchors into
   the append-only publication/seal ledger (wholesale chain re-computation is
   undetectable self-contained).

## Closure checklist (all must be ✅ before the first forward run)
- [ ] H1 tagged canonical AST + injectivity matrix
- [ ] H1-legacy 4-source structured-hash migration
- [ ] H2 deep-immutable sealed objects + boundary re-verify
- [ ] H3 `TextRowSeal` row-rooted lineage
- [ ] H4 PIT-bound claim/ownership (built with scoring)
- [ ] H5 typed fetch-response coverage
- [ ] H6 sealed target-session snapshot
- [ ] H7 fact-clustering (or accept the documented over-count with sign-off)
