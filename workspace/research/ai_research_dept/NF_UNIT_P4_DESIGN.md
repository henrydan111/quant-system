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
