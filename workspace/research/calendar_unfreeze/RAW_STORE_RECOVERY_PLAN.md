# RAW STORE RECOVERY PLAN v3 — 2026-07-13 junction-deletion incident

**Status: design under GPT §10 review (v2 verdict = REWORK, all findings folded here). NO fetch executed; fetch stays refused until (a) adapters are built + integration-tested, (b) endpoint contracts human-reviewed, (c) GPT re-review passes, (d) the user's explicit §13 go-ahead.**

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
- **Coordinator guard**: `Path.relative_to(run_root)` containment (kills the `C:\quant_recovery_evil` prefix bypass) + reparse-point rejection over the entire ancestry + E:-prefix refusal; ledger/report writes are fsync'd, ledger under a file lock.
- **Drivers are NOT trusted**: verified E: leak points (import-time log handlers in all three initializers; `fetch_bucket_a` DATA/LOGS; alpha-endpoints roots; suspend/broker scripts; indicator refresh logs/reports even with `--data-root`; both catch-up drivers + bare `StorageManager()`; `pit_backend` profiling reports on C:-rooted builds). Therefore **every leg requires an ADAPTER** that (i) drives class methods directly (never `main()`), (ii) receives every path (data/logs/state/reports/build) from the run's `RecoveryPaths` with **no defaults**, (iii) removes/redirects import-time handlers, and (iv) passes an **E:-write-denied integration test** (run under an ACL-denied or monitored E: mount) before wiring.

## 3. Fetch legs (GPT B2/B3 folded — see `ADAPTER_SPECS` in the coordinator for the authoritative list)

Corrections vs v2: `init_market_data.main()` always downloads reference → the adapter bypasses `main()`; `init_fundamentals_data.run()` always refetches industry+index_weights (survivors!) and does NOT fetch cashflow/forecast/quarterlies → split legs, `scripts/fetch_quarterly_statements.py` added; `scripts/fetch_broker_recommend_historical.py` EXISTS (v2 claimed otherwise) and needs path injection; the tail (L9) needs a NEW adapter (catch-ups can't target C:) and is **not uniformly session-based** — announcements use calendar-day `ann_date` windows, broker is monthly, report_rc needs its TTL halo.

**Throttle (B3): enforced centrally, not in metadata** — `tushare_lock.MIN_BASE_SLEEP = 1.5` floors every `spaced_call` at the account chokepoint; `TushareFetcher.__init__` floors constructor values; the four 1.0s constructors (`init_market_data`, `init_fundamentals_data`, `init_factor_data`, `fetch_quarterly_statements`) are raised to 1.5. Regression test pins the chokepoint floor. Serial legs; machine-global api lock; backoff on 429s.

**Doc gate (M3):** `workspace/configs/recovery_endpoint_contracts.yaml` — one entry per endpoint (doc path + sha256, fields, limits, cadence, PIT semantics, human `reviewed_by/at`). The coordinator's `--plan` BLOCKS any leg whose endpoints lack a complete reviewed contract (today: 10/10 legs blocked — the gate works before any adapter exists).

## 4. Restoration proof (GPT B4 — counts are not proof)

**Per-request ledger** (implemented; schema = `LEDGER_REQUEST_FIELDS`): one row per API request/partition carrying query params, page count, raw row count, `confirmed_empty` (only from a positive completeness proof — a failure or skip is never "empty"), schema fingerprint, natural-key null/duplicate stats, output path + sha256, first-fetch timestamp, exception, doc hash, state (`fetched|verified|failed|confirmed_empty`). Consolidated files are written only after every constituent partition is `verified`. Drivers that swallow failures and exit 0 cannot green a dataset — the ledger does.

**Dataset-level proof** = ledger 100% verified/confirmed_empty over the enumerated request set **+ the existing dataset profiler re-run against the C: store** compared to the manifest's `schema_variants`, mandatory-null counts, duplicate stats, warnings, and expected missing dates — not just totals. This catches missing-partition-masked-by-extras, pagination truncation, dropped columns/dtype drift, null keys, and event-day API failures masquerading as absent files.

## 5. PIT integrity & the oracle (GPT B5 — the headline residual risk)

**The residual risk this section exists to kill: backdating newly reconstructed `report_rc`/fundamental revisions into the sealed historical window, because the original first-seen and revision-baseline evidence was deleted.**

- **Full chain on C: BEFORE promotion**: raw → normalized → PIT ledger → **full provider build on C:** (builder pinned to the live provider's recorded source commit `f93cb9d2…17be2`). Drift is discovered on C:, never after touching E:.
- **Recovery-specific oracle**: a FULL-BIN frozen-prefix comparison vs the live provider — **no sampling, no exception auto-excusals** (the standing audit samples 1-in-50 and non-strict mode auto-excuses indicators + every `report_rc__*` mismatch — banned here). `canonical_kline_hash` is computed **directly on both providers** (the live manifest's stored value is null). Any served-prefix mismatch **blocks promotion until its cause is proven** — a diff is *not* automatically a "vendor restatement": it can equally be incomplete fetching, field drift, pagination loss, code drift, or tie-break drift. Attribution requires a per-diff investigation with evidence; only proven vendor changes become typed exceptions.
- **report_rc policy**: refetch carries explicit `create_time` + per-content `raw_fetch_ts` stamped at recovery time. First-seen evidence for 2026-07-01→incident rows is **reconstructed from the July catch-up state/logs where provable; otherwise visibility is floored at recovery time or the row is quarantined** — never backdated. The revision baseline is re-established **only after exact live-provider parity**; until then the Phase 5-A restatement guard treats recovery as a declared bulk-backfill epoch.
- **Raw-only data** (Bucket-A siblings, broker_recommend): new raw generation identity; documented as reconstructed-current-snapshot, not historical reconstruction.

## 6. Promotion (GPT B6 + answer 5 — crash-resumable, not "atomic")

Cross-volume copies are never atomic. The sequence (journaled per family in the run ledger):

1. Finish + strictly verify the ENTIRE C: build (§4 + §5).
2. Freeze C: with a path/size/sha256 manifest; any later mutation refuses promotion.
3. Pause all raw writers; acquire `raw_maintenance_lock` + the provider-publish lock.
4. Re-scan C: and E: for reparse points; verify the live target families still match the recorded incident-empty fingerprint.
5. Copy ONE family to `E:\量化系统\data\.recovery_incoming\<run_id>\<family>` via `robocopy /E /XJ` (never `/MIR`/`/MOV`).
6. Verify every incoming file against the frozen C: manifest (sha256).
7. Journal `PREPARED`.
8. Same-volume rename: empty live family → incident tombstone; incoming → live name (each rename atomic).
9. Journal `SWAPPED`; re-hash the live family.
10. Next family. Tombstones are retained until QA + the first verified backup complete. The live Qlib provider is untouched throughout.

Then: `build_qlib_backend --stage upstream-only` on E (derived layers), `run_daily_qa`, resume 5-C.

## 7. Backup v2 (GPT M4 + answer 7)

- Versioned generations on the OTHER physical disk: **14 daily + 8 weekly + 12 monthly** verified generations (subject to a measured free-space floor; always ≥3 independently restorable generations). `robocopy /E` — never `/MIR`.
- **No NTFS hardlink dedup** (one inode mutation damages multiple apparent backups); independent copies or content-addressed/COW storage, plus an offline/external generation.
- **Manifest-based non-regression guard** (replaces the weak >2% count rule): per-generation path/size/sha256 manifest; **zero tolerance for an unexplained missing historical path**; compares file count, total bytes, per-dataset counts and date floors. Backup and pruning are SEPARATE jobs; a failed guard preserves every existing good generation.

## 8. Execution gates (in order, each §13-held)

1. GPT re-review of this v3 + coordinator v2 → verdict.
2. Endpoint-contract review sweep (30 endpoints, human-signed) — can proceed in parallel with adapter construction.
3. Adapter construction + E:-write-denied integration tests.
4. User authorizes fetch → legs run serially on C: (ledger-gated).
5. §4 restoration proof + §5 C:-side oracle → user reviews.
6. User authorizes promotion → §6 sequence.
7. Derived rebuild + QA + backup v2 live + incident close-out in project_state.
