# NF integration P4 — record → execute → seal, honouring the frozen obligations (design)

**Status:** split + tiers **user-approved 2026-07-23** (P4a = Tier-1 under the existing frozen
[NF_ARCHIVE_THREAT_MODEL.md](NF_ARCHIVE_THREAT_MODEL.md) v2; P4b = Tier-2). P4a implemented
2026-07-23, pending its Tier-1 review. Two implementation-time deltas from this design, both
recorded in the review prompt: (1) the ledger decision row embeds the FULL `assembly.payload`
(not just the hash) — required for pure-disk crash recovery, following the commitment-row
contract-embedding precedent (re-review#5 P0); (2) seal binds the assembly against
`verify_execution_bundle`'s internal verified-artifact copy instead of running its own
`verify_d7_artifact` at entry — an entry-point verification is a registry callback point BEFORE
the contract/outcome snapshots and re-opens the GPT #23 P1#1 timing class (the pinned probes
caught exactly this on the first attempt).

**Round-1 fold (2026-07-24, user-arbitrated: evidence-at-the-door).** The Tier-1 review's P1:
`AssemblyProvenance` was a *self-consistent claim*, not a verifiable proof — the reviewer's
public-constructor probe (real `artifact_hash`, forged ts_code/cutoff/SHAs) completed
record → execute → seal → load end-to-end. In-process Python has no unforgeability primitive,
so the only complete closure is evidence at the first-write door: `record_decision` now REQUIRES
`assessed_artifact` + `split_artifact` + `source_rows` and proves the claim via
`prove_assembly_by_rederivation` — re-run P3b from the evidence with the CLAIMED identity and
demand bit-equality of both `artifact_hash` and `assembly_hash`. Any forged field dies in the
upstream identity/chain gates or the hash comparison, BEFORE any ledger write. Downstream doors
(seal / read-back / recovery) byte-compare against the ledger-pinned row and inherit the proof.
Two cheaper shapes were rejected in arbitration: field-level cross-checking (leaves the
same-fingerprint-prefix and forged-split-text faces open) and a persisted P3b record (the writer
is equally forgeable).

**Round-3 arbitration (2026-07-24, at the §10 budget ceiling).** Re-review#3: REVISE, 2 P1.
P1#2 (the P1←store binding checked only the subset direction — a valid 2-row chain over a 3-row
store recorded successfully) — folded: exact-SET equality both directions, matching the P2
production path's own population gate; regression = the reviewer's probe (store grown after the
chain committed → refused, no ledger). P1#1 (a caller can designate its OWN roots and run the
genuine pipeline over fabricated data) — **user-arbitrated: re-scope the threat model** (over a
config-binding mechanism — the NF-archive 24-round lesson — and over tracked debt):
[NF_ARCHIVE_THREAT_MODEL.md](NF_ARCHIVE_THREAT_MODEL.md) **v3** rules root selection out of scope
(all five operator root dirs are one trust class; guarantees are relative to a fixed root set;
production-root binding = a FORWARD_PREREG governed-runner obligation, the `book_seal.py`
live-refusal pattern). Confirmation round #4 is scoped to the P1#2 diff + the v3 model.

**Round-2 fold (2026-07-24, repeat-class ⇒ structural chokepoint).** The re-review found the
round-1 fold's evidence was still CALLER-SUPPLIED (2 P1): self-hashes over forged content are
recomputable, so re-derivation only proved "the caller's own materials cohere" (the reviewer
walked a wholly forged plain-dict P2→P3a→record→seal→load end to end); and a stateful dict
subclass could swap values after verification (`_verified_inputs` returned the caller's dict).
Same invariant class two rounds running → per §10 the fold is architectural:
`resolve_committed_evidence` — the door now takes **trusted roots** (`store_dir`,
`artifact_dir`), never evidence objects, and resolves the COMMITTED records itself: text store
first (`require_exists`, the data root), then P1 at its canonical write-once slot (re-verified,
and every typed flash's `content_hash` must recompute from THE store's rows — P1←store), then
P2 (`consumed_typed_flash_sha256` == that P1 — P2←P1), then P3a (P3a←P2). Disk JSON is plain by
construction, so the caller-object TOCTOU surface is gone wholesale; `_verified_inputs` also
snapshots-then-verifies for its remaining producer-path callers. The mechanical guard
(repeat-class rule): a parameter-enumeration test pins the exact signatures of
`record_decision` / `prove_assembly_by_rederivation` / `resolve_committed_evidence` — a future
evidence-object parameter fails the enumeration until deliberately reviewed. Trust bottoms out
at: the text store (upstream data-provenance layer) + first-write-wins canonical artifact slots
(the same trust class as the ledger itself). Both reviewer probes pinned as regressions
(forged files without a store; a valid-but-wrong-lineage P2/P3a over a real store dying on
chain binding), each asserting no ledger row is produced. Collateral: the engine test corpus's hand-built artifact factories were
migrated to REAL chains (`tests/assembly_fixtures.py` builds cached
text_store→P1→P2→P3a→P3b chains; variants basic/full/context_only/floor3 re-express the old
shapes — a P3a split ALWAYS carries a penalty-eligible `source_status` child, so "empty penalty
population" now means floor3 = no ≥floor fact; evaluation pins moved 74.0→49.0 because
`fundamental_link` is uncited under the chain's 2-row factor population).

## What P4 is

The persistence boundary of the NF chain. Per (stock, cutoff): take P3b's
`(D7DecisionArtifact, AssemblyProvenance)` and drive `record_decision` →
`execute_news_decision` (factor + penalty LLM legs) → `seal_decision_archive`, discharging the
**five frozen obligations** from the P3b arc (a require / b verify-then-bind order / c ledger
`assembly_hash` / d archive schema v1→v2 with read-back re-verification / e refusal tests incl.
"a v1-shaped archive must not verify").

## Premise check (read-only, done)

- Ledger entry body = `{kind, decision_id, bundle_hash, artifact_hash, final_registry_hash,
  source_card_hash, cutoff_iso, seq, prev_hash, entry_hash}`. `_ARTIFACT_FIELDS` drives BOTH
  `record_decision` idempotency and `require_recorded`'s full-field match. **`assembly_hash` cannot
  join `_ARTIFACT_FIELDS`**: it is not derivable from the artifact, and `require_recorded` (the
  executors' ledger gate) has no assembly in hand. It must be a separate entry field with its own
  comparison at record time.
- `seal_decision_archive` → `verify_execution_bundle` (verifies the artifact internally) → strict
  key set `_ARCHIVE_KEYS` + `archive_schema` value check on read-back. Bumping to v2 and extending
  the key set makes a v1-shaped archive fail the key-set gate **by construction** — obligation (e)'s
  round-trip half needs a test, not new machinery.
- `_load_and_verify_archive_file` holds a single ledger snapshot (`chain`) — the assembly↔ledger
  cross-check can run on that same snapshot (no TOCTOU).
- `execute_news_decision`'s signature does not change: the executors' ledger gate compares only
  artifact-derived fields; the assembly is pinned at record and re-checked at seal — the middle leg
  never touches it.
- The NF archive boundary already has a **user-approved frozen threat model**
  ([NF_ARCHIVE_THREAT_MODEL.md](NF_ARCHIVE_THREAT_MODEL.md) v2 at `c3a8d93`): a boundary function is
  defective iff a crafted in-process instance can (i) seal/accept a forged/non-exact/decoupled
  value, (ii) mutate already-verified/trusted state, or (iii) leak. The P4a edits live **inside that
  same trust boundary**, so the Tier-1 sending precondition is satisfied by linking it — no new
  threat model is minted.

## Proposed split (mirrors the approved P3a/P3b split)

### P4a — chain binding in the ledger + archive (Tier-1, under the EXISTING frozen threat model)

Small, focused diff to the two Tier-1 modules only:

1. **`record_decision(ledger_dir, decision_id, artifact, *, assembly)`** — `assembly` REQUIRED, no
   default (obligation a). Order: `verify_d7_artifact` → `require_assembly_for(assembly, artifact)`
   (obligation b). Entry gains `assembly_hash`. Idempotency: artifact fields AND `assembly_hash`
   all equal → idempotent return; a second write with a different `assembly_hash` → refuse
   (first-write-wins now also pins WHICH upstream chain owns the decision id — obligation c).
2. **`seal_decision_archive(..., *, assembly)`** — REQUIRED. At entry: verify artifact → bind
   assembly (order per obligation b) → **ledger cross-check**: the decision row's `assembly_hash`
   must equal `assembly.assembly_hash` (the sealed chain is the recorded chain — a decision recorded
   under chain A cannot be archived claiming chain B). Archive payload gains `"assembly":
   assembly.payload`; `_ARCHIVE_SCHEMA` → `news_decision_archive_v2`; `_ARCHIVE_KEYS` + `assembly`.
3. **Read-back** (`_load_and_verify_archive_file`): after the seal/schema gates —
   `verify_assembly_provenance(archive["assembly"])` (recompute, not trust) →
   `require_assembly_for` against the verified artifact copy → ledger cross-check on the SAME
   `chain` snapshot (decision row's `assembly_hash` == archived assembly's). A decision row lacking
   a well-formed `assembly_hash` refuses (fail-closed; no legacy ledgers exist — zero production
   callers).
4. **Refusal tests** (obligation e): missing assembly (TypeError — no default), artifact-hash
   mismatch, ledger/archive assembly mismatch, tampered archived assembly payload, v1-shaped archive
   (key set) refused, plus the positive round-trip: seal → read back → the recovered assembly proves
   ts_code / fact set / P2+P3a SHAs.

### P4b — the per-stock decision driver (Tier-2)

New module `news_flash_decide.py`: `decide_stock(cutoff, *, ingest_class, ts_code,
assessed_artifact, split_artifact, source_rows, ledger_dir, prov_dir, archive_dir, contract,
call_fn)`:

1. **Deterministic decision identity**: `decision_id = f"nf:{ingest_class}:{ts_code}:{cutoff_iso}"`
   — same (stock, cutoff, class) → same id, so re-runs meet the ledger's first-write-wins instead of
   minting parallel decisions. (`NothingToDecide` propagates — no ledger row is ever written for a
   stock with no routed flash.)
2. `assemble_stock_artifact` (P3b) → `record_decision(..., assembly=...)` →
   `execute_news_decision(...)` → `seal_decision_archive(..., assembly=...)`.
3. Returns `{decision_id, execution_id, news_status, archive_sha256, assembly_hash}` — identities,
   not payloads.
4. Invariants: ids exact str; the SAME artifact/assembly objects flow record→seal (no re-assembly
   between steps); a failed execution still leaves the ledger + provenance audit trail (crash-visible,
   the executors already guarantee this); NON_EVIDENTIARY stays true — zero production callers until
   FORWARD_PREREG; `contract` is caller-supplied (binding it from the on-disk `ChainContract` is the
   final-integration item, out of P4).

## Not in P4

- C1 (session embedding of the sealed decision), the macro seat, `NewsScoringContract`-from-
  `ChainContract`, `scorecard.py` dispatch, chain version bump — final integration.

## Cost note

P4b introduces the chain's per-stock LLM cost: 2 legs (factor + penalty) per (stock, day) with a
routed flash. Offline-batch shape (option B, user-approved) — no session run pays this.
