# RAW STORE RECOVERY PLAN v4 — 2026-07-13 junction-deletion incident

**Status: design under GPT §10 review (re-review #2 verdict = REWORK, all findings folded → coordinator v3 + this v4). NO fetch executed; fetch stays refused until (a) endpoint contracts are human-reviewed FIRST, (b) adapters built from the unique-owner matrix + the pre-fetch test matrix passes, (c) GPT re-review passes, (d) the user's explicit §13 go-ahead.**

v1/v2 SUPERSEDED. v2's REWORK found: containment not end-to-end (drivers write E: logs/state; guard string-prefix-bypassable), a factually wrong leg matrix, a metadata-only throttle floor, a non-operational ledger, an oracle policy that could bless the very drift it must catch, and a physically impossible "atomic cross-volume promotion". Each is corrected below; the coordinator v2 (`scripts/raw_recovery_coordinator.py`) implements the run/ledger/doc-gate machinery.

## 0. Incident + evidence (user-confirmed; unchanged from v2)

`git worktree remove --force` on `C:\Users\henry\AppData\Local\Temp\quant-review-3d2ac0f` recursed through Windows junctions into live `data/` at 04:06:16, killed ~04:11. **Evidence handling (GPT answer 8):** the worktree stays read-only and unregistered (GPT's scan found zero reparse points remaining — rescan immediately before any dismantling); the damaged staged build `phase1_qfields_holdertrade_20260623` (3,217 feature dirs, incomplete) is quarantined read-only, excluded from every builder/oracle, deleted only after successful recovery + two verified backups + explicit approval. Dismantling procedure when evidence retention ends: rescan reparse points → record targets → unlink junction objects with no-follow ops → rescan to zero → verify live E: hashes → delete plain files under a containment-checked no-follow walker → `git worktree prune --dry-run` before any prune.

## 1. Baseline & classification (GPT M1 folded)

**Baseline = `data/qlib_builds/thaw_step1_20260703c/manifest.json`, sha256-pinned `fbc4aec0…7627f` (the coordinator refuses a drifted manifest):** 27 datasets, 78,948,729 rows. Inventory `presence` is a **coarse count scan only** — restoration proof is §4.

Classification (per target):
- **Survivors** — whole `reference/` + `universe/` trees (incl. `industry_sw2021_members/`, `ths_concept/`, `stock_basic.parquet.bak_*`, hand-curated repair/known-empty files) — copied+hashed into the run root by preflight (234 files), never re-fetched.
- **Refetchable** — the 21 lost manifest datasets + per-date `suspend_d` store + yearly `market/suspension/suspension_YYYY.parquet` + `broker_recommend`. (`margin_detail` is NOT a separate store — canonical raw = `market/margin/`, already the manifest's `margin` dataset; v2 misclassified it.)
- **Refetchable as a NEW RAW GENERATION** — Bucket-A siblings + all raw-only data: a fresh download is a new generation identity, **never claimed byte-equivalent** to pre-incident raw.
- **Derived** — `normalized/`, `pit_ledger/`, `suspension_ranges.parquet` (rebuilt via `--ranges-only` after suspend_d).
- **Known-empty** — `balancesheet_quarterly` stays empty unless a separately-reviewed vendor change.
- **IRRECOVERABLE EVIDENCE (recorded lost, not "restored")** — historical indicator staged archives (original capture times unreproducible); `report_rc.revision_baseline.parquet`; first-seen `raw_fetch_ts` stamps for rows arriving 2026-07-01→incident.
- **Incident evidence snapshot** — `raw_cache/` manifests, calendar-unfreeze state JSONs, July catch-up/update logs — copied+hashed to the run's `evidence/` (18 files).

## 2. Containment (GPT B1)

- **Run-scoped immutable staging** (GPT M2): `C:\quant_recovery\runs\<run_id>\{staging_data,ledger,reports,logs,evidence}`; a new run refuses an existing id; resume only re-opens the same ledger. No `dirs_exist_ok` merging into unverified trees.
- **Coordinator guard (v3)**: run_id restricted to one safe component (regex; `..\escape`-class traversal refuses before any path exists); **lexical containment validated BEFORE any resolve** (resolve() follows a junction and erases the evidence); per-component reparse inspection INCLUDING the leaf, RECOVERY_ROOT, and the run root, with inspection failure = refusal; realpath cross-check as a belt; root/tmp/`.lock` creation inside the authority; resume requires the original `run_created` ledger record (run id + pinned baseline hash). Junction/traversal/UNC/tamper probes are pinned tests (13-test battery).
- **Write-surface monitor (replaces the E-only test idea)**: adapter integration tests run under a filesystem ALLOWLIST monitor — run-root writes + the machine-global api-lock namespace ONLY; any other write fails the test, including `ts.set_token()`'s user-profile token-cache write (the adapter constructs the fetcher so that write is avoided or its exact path is explicitly allowlisted).
- **Drivers are NOT trusted**: verified E: leak points (import-time log handlers in all three initializers; `fetch_bucket_a` DATA/LOGS; alpha-endpoints roots; suspend/broker scripts; indicator refresh logs/reports even with `--data-root`; both catch-up drivers + bare `StorageManager()`; `pit_backend` profiling reports on C:-rooted builds). Therefore **every leg requires an ADAPTER** that (i) drives class methods directly (never `main()`), (ii) receives every path (data/logs/state/reports/build) from the run's `RecoveryPaths` with **no defaults**, (iii) removes/redirects import-time handlers, and (iv) passes an **E:-write-denied integration test** (run under an ACL-denied or monitored E: mount) before wiring.

## 3. Fetch legs (GPT B2/B3 folded — `ENDPOINT_MATRIX` in coordinator v3 is the authoritative machine-readable list: one row per endpoint/output family with callable, partitioner, pagination, natural key, empty policy, consolidation rule, tail rule, UNIQUE owner, and first-class sidecars)

Corrections vs v2: `init_market_data.main()` always downloads reference → the adapter bypasses `main()`; `init_fundamentals_data.run()` always refetches industry+index_weights (survivors!) and does NOT fetch cashflow/forecast/quarterlies → split legs, `scripts/fetch_quarterly_statements.py` added; `scripts/fetch_broker_recommend_historical.py` EXISTS (v2 claimed otherwise) and needs path injection; the tail (L9) needs a NEW adapter (catch-ups can't target C:) and is **not uniformly session-based** — announcements use calendar-day `ann_date` windows, broker is monthly, report_rc needs its TTL halo.

**Throttle (B3): enforced centrally, not in metadata** — `tushare_lock.MIN_BASE_SLEEP = 1.5` floors every `spaced_call` at the account chokepoint; `TushareFetcher.__init__` floors constructor values; the four 1.0s constructors (`init_market_data`, `init_fundamentals_data`, `init_factor_data`, `fetch_quarterly_statements`) are raised to 1.5. Regression test pins the chokepoint floor. Serial legs; machine-global api lock; backoff on 429s.

**Doc gate (M3):** `workspace/configs/recovery_endpoint_contracts.yaml` — one entry per endpoint (doc path + sha256, fields, limits, cadence, PIT semantics, human `reviewed_by/at`). The gate is STRUCTURAL (coordinator v3 `contract_errors`): doc_path resolved under the offline mirror with traversal/reparse rejection, doc_sha256 recomputed, structured field/key/pagination/empty-policy entries, ISO non-future `reviewed_at`, non-placeholder reviewer — an `"x"`-stuffed contract refuses. All rows blocked today; contracts must be signed BEFORE that endpoint's adapter logic (§8).

## 4. Restoration proof (GPT B4 — counts are not proof)

**Typed, transition-enforced ledger** (coordinator v3 `RecoveryLedger`: frozen hashed request plan -> per-kind schemas -> enforced planned->fetched|failed->verified|confirmed_empty transitions under the file lock; `verified` checks the actual output existence/containment/sha256; dense-empty refused; torn tail fails closed): one row per API request/partition carrying query params, page count, raw row count, `confirmed_empty` (only from a positive completeness proof — a failure or skip is never "empty"), schema fingerprint, natural-key null/duplicate stats, output path + sha256, first-fetch timestamp, exception, doc hash, state (`fetched|verified|failed|confirmed_empty`). Consolidated files are written only after every constituent partition is `verified`. Drivers that swallow failures and exit 0 cannot green a dataset — the ledger does.

**Dataset-level proof** = ledger 100% verified/confirmed_empty over the enumerated request set **+ the existing dataset profiler re-run against the C: store** compared to the manifest's `schema_variants`, mandatory-null counts, duplicate stats, warnings, and expected missing dates — not just totals. This catches missing-partition-masked-by-extras, pagination truncation, dropped columns/dtype drift, null keys, and event-day API failures masquerading as absent files.

## 5. PIT integrity & the oracle (GPT B5 — the headline residual risk)

**The residual risk this section exists to kill: backdating newly reconstructed `report_rc`/fundamental revisions into the sealed historical window, because the original first-seen and revision-baseline evidence was deleted.**

- **Full chain on C: BEFORE promotion**: raw → normalized → PIT ledger → **full provider build on C:** (builder pinned to the live provider's recorded source commit `f93cb9d2…17be2`). Drift is discovered on C:, never after touching E:.
- **Recovery-specific oracle**: a FULL-BIN frozen-prefix comparison vs the live provider — **no sampling, no exception auto-excusals** (the standing audit samples 1-in-50 and non-strict mode auto-excuses indicators + every `report_rc__*` mismatch — banned here). `canonical_kline_hash` is computed **directly on both providers** (the live manifest's stored value is null). Any served-prefix mismatch **blocks promotion until its cause is proven** — a diff is *not* automatically a "vendor restatement": it can equally be incomplete fetching, field drift, pagination loss, code drift, or tie-break drift. Attribution requires a per-diff investigation with evidence; only proven vendor changes become typed exceptions.
- **report_rc policy (M2-tightened evidence bar)**: refetch carries explicit `create_time` + per-content `raw_fetch_ts` stamped at recovery time. Prior first-seen is admissible **only when retained evidence cryptographically binds the report's natural key AND content hash to a timestamp — aggregate status flags and row-count log lines are inadmissible**. Otherwise: recovery-time visibility floor; **quarantine when a collision or prefix mismatch makes even the conservative floor ambiguous**. A proven vendor restatement may justify raw lineage but **never automatically authorizes rewriting the sealed provider's historical output**. The revision baseline is re-established only after exact live-provider parity; until then the Phase 5-A restatement guard treats recovery as a declared bulk-backfill epoch.
- **C:-side builder containment (M1)**: the pinned build runs from a **hash-verified `git archive` of `f93cb9d2…` extracted under the immutable C: run root** (no worktree, no junction), executed only with explicit C: data/provider paths under the write-allowlist monitor; tree hash, dependencies, and the exact command recorded. (Running the E: checkout would write `workspace/outputs/data_profiles` + the import-time `logs/` handler onto E:; running modified current code would break the source pin. If a path-injection patch proves unavoidable, its path-only diff hash is recorded SEPARATELY from the semantic source pin.) The oracle comparison **holds the provider-publish lock (or hashes the live provider before AND after)** and covers calendars, instruments, and **every** live feature bin.
- **Raw-only data** (Bucket-A siblings, broker_recommend): new raw generation identity; documented as reconstructed-current-snapshot, not historical reconstruction.

## 6. Promotion (GPT B6 + answer 5 — crash-resumable, not "atomic")

Cross-volume copies are never atomic. The sequence (journaled per family in the run ledger):

Per-family state machine (journal fsync'd BEFORE each transition; resume inspects all three paths + hashes and picks a deterministic roll-forward or rollback — a crash between the two renames can no longer strand an absent canonical path under a stale `PREPARED`):

`COPYING -> PREPARED -> OLD_MOVED -> NEW_INSTALLED -> LIVE_VERIFIED -> SWAPPED`

1. Finish + strictly verify the ENTIRE C: build (§4 + §5); freeze C: with a path/size/sha256 manifest — later mutation refuses promotion.
2. Write a durable E:-side **`RECOVERY_IN_PROGRESS` sentinel** BEFORE the first swap — all raw readers, daily/monthly jobs, and builders **fail closed while it exists** (checked at their entry points; wired before promotion is authorized).
3. Pause raw writers; acquire `raw_maintenance_lock` + the provider-publish lock.
4. **Refuse pre-existing** `.recovery_incoming`/tombstone destinations; re-scan the C: source AND the E: incoming trees **recursively for every reparse point before and after copying** (`/XJ` silently skipping one is NOT success — the post-scan must find zero); verify the live target families still match the recorded incident-empty fingerprint.
5. `COPYING`: copy ONE family to `data\.recovery_incoming\<run_id>\<family>` via `robocopy /E /XJ` (never `/MIR`/`/MOV`). `.recovery_incoming\` and tombstones live at the `data\` top level — **outside every dataset glob** (`market/**` etc. cannot match them).
6. Verify every incoming file against the frozen C: manifest (sha256) -> journal `PREPARED`.
7. Same-volume rename live family -> tombstone -> journal `OLD_MOVED`.
8. Same-volume rename incoming -> live name -> journal `NEW_INSTALLED`.
9. Re-hash the live family vs the frozen manifest -> journal `LIVE_VERIFIED` then `SWAPPED`.
10. Next family. Tombstones + sentinel retained until QA + the first verified backup complete. **Crash injection before/after EVERY rename and journal transition is a pre-promotion test requirement.** The live Qlib provider is untouched throughout.

Then: `build_qlib_backend --stage upstream-only` on E (derived layers), `run_daily_qa`, resume 5-C.

## 7. Backup v2 (GPT M4 + answer 7)

- Versioned generations on the OTHER physical disk — **verified by device identity, not asserted**: record the Windows volume + physical-disk IDs of source and destination; refuse a destination mapped to the same physical device. **14 daily + 8 weekly + 12 monthly** verified generations (measured free-space floor; always ≥3 independently restorable). `robocopy /E` — never `/MIR`.
- **No NTFS hardlink dedup** (one inode mutation damages multiple apparent backups); independent copies or content-addressed/COW storage, plus an offline/external generation.
- **Manifest-based non-regression guard** (replaces the weak >2% count rule): per-generation path/size/sha256 manifest; **zero tolerance for an unexplained missing historical path**; compares file count, total bytes, per-dataset counts and date floors. Backup and pruning are SEPARATE jobs; a failed guard preserves every existing good generation.

## 8. Execution gates (in order, each §13-held)

1. Coordinator containment/ledger/contract-schema fixes (DONE in v3) -> GPT re-review #3 verdict.
2. **Endpoint contracts reviewed + signed FIRST** — fields/limits/pagination/PIT anchors determine adapter design (repo rule: read the interface doc BEFORE writing the fetcher). Only generic containment/ledger test infrastructure proceeds in parallel; **no endpoint's partitioning or fetch logic is written before its contract is signed** (GPT M3).
3. Adapters built from the unique-owner ENDPOINT_MATRIX.
4. Pre-fetch test matrix (GPT answer 7): traversal/UNC/device/reparse/lock/temp containment; fresh-subprocess ALLOWLIST write monitoring; contract hash/schema negatives; single-page, exact-limit multipage, retry-exhaustion, partial-page crash + resume; dense-empty refusal + sparse-empty canary; null/duplicate natural-key + schema-drift rejection; ledger concurrency, torn-tail, invalid-transition; consolidation refusal with one missing constituent; throttle tests (proxy/fetch/retry incl. non-finite) + PRO001; mocked end-to-end representatives for per-date, per-stock, event/announcement, and monthly adapters.
5. User authorizes fetch -> legs run serially on C: (frozen request plan + typed ledger gate every request).
6. §4 restoration proof + §5 C:-side full-chain build + full-bin oracle -> user reviews.
7. Tiny-fixture raw->PIT->provider oracle tests + crash injection across every promotion transition -> user authorizes promotion -> §6 state machine.
8. Derived rebuild + QA + backup v2 live + incident close-out in project_state.
