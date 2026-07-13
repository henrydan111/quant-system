# GPT 5.5 Pro RE-review #2 — raw-store RECOVERY design (plan v3 + coordinator v2, post-REWORK)

Status: ready to send. Branch `calendar-unfreeze`, artifacts pinned to commit `ee94dc5`. Still NO fetch executed; this re-review gates adapter construction + the fetch authorization.

**Self-review (§10, done):** every REWORK claim re-verified against code before folding (broker/quarterly scripts exist — `ls`; margin_detail canonical path — data_dictionary L750; init_fundamentals dataset set — grep; init_market main() reference call — read; 4×base_sleep=1.0 — grep). Central floor implemented + test-pinned (`test_spaced_call_floors_base_sleep_centrally`); lock/fetcher batteries 34/34; the 20 data-dependent test failures in tests/data_infra are the incident blast radius (empty pit_ledger/caches), verified unrelated to the floor change (no failing test touches fetcher/lock). Coordinator v2 smoke: run `20260713a` created; inventory 21 lost / 77,516,755 rows; preflight 234 survivor files (whole trees, hashed) + 18 evidence files; `--plan` = 10/10 legs doc-gate-blocked; `--fetch` exit 3; duplicate run refused. Verdict: clean for GPT.

---

```text
ROLE
Senior reviewer for an A-share quant system where research validity outranks code that runs. You
reviewed the recovery design for the 2026-07-13 junction-deletion incident (user's `git worktree
remove --force` recursed through junctions into the live raw store; 21/27 provider-input datasets
deleted, ~77.5M rows; live Qlib provider + reference/ + universe/ + registries INTACT) and returned
REWORK with 6 Blockers + 4 Majors + 2 Minors. This RE-REVIEW verifies the fold. Fetch remains
REFUSED: adapters are deliberately NOT built yet — this review gates their construction.

REPO https://github.com/henrydan111/quant-system  (branch calendar-unfreeze, commit ee94dc5)
- Plan v3:           https://raw.githubusercontent.com/henrydan111/quant-system/ee94dc5/workspace/research/calendar_unfreeze/RAW_STORE_RECOVERY_PLAN.md
- Coordinator v2:    https://raw.githubusercontent.com/henrydan111/quant-system/ee94dc5/scripts/raw_recovery_coordinator.py
- Endpoint doc-gate: https://raw.githubusercontent.com/henrydan111/quant-system/ee94dc5/workspace/configs/recovery_endpoint_contracts.yaml
- Central throttle floor: https://raw.githubusercontent.com/henrydan111/quant-system/ee94dc5/src/data_infra/tushare_lock.py  (MIN_BASE_SLEEP in spaced_call)
  + https://raw.githubusercontent.com/henrydan111/quant-system/ee94dc5/src/data_infra/fetchers/__init__.py  (constructor floor)
  + the four raised constructors: init_market_data / init_fundamentals_data / init_factor_data /
    scripts/fetch_quarterly_statements.py (all at the same pin)
- Floor regression test: https://raw.githubusercontent.com/henrydan111/quant-system/ee94dc5/tests/data_infra/test_daily_update_5c.py  (test_spaced_call_floors_base_sleep_centrally)

HOW EACH FINDING WAS FOLDED

B1 (containment not end-to-end): RecoveryPaths per immutable run (C:\quant_recovery\runs\<run_id>);
assert_write = Path.relative_to(run_root) [kills the quant_recovery_evil prefix bypass] + reparse-point
rejection over the FULL ancestry (is_symlink/is_junction on every parent) + E:-prefix refusal; fsync'd
journal/report writes; ledger under a file lock. The DRIVEN scripts are declared UNTRUSTED — every one
of your verified E: leak points (import-time log handlers, fetch_bucket_a DATA/LOGS, alpha-endpoint
roots, suspend/broker hard-coding, indicator logs-despite--data-root, catch-up state + bare
StorageManager, pit_backend profiling reports) is recorded as an adapter GAP in ADAPTER_SPECS, and the
plan requires every adapter to take ALL paths injected (no defaults) + pass an E:-write-denied
integration test BEFORE wiring.
B2 (wrong leg matrix): free-text drivers replaced by ADAPTER_SPECS with verified gaps: L1 bypasses
init_market_data.main() (it unconditionally downloads reference); L2 split — statements core vs
L2b (cashflow/forecast/quarterlies via scripts/fetch_quarterly_statements.py, which EXISTS and was
omitted); industry+index_weights refetch (survivors) marked as a must-skip gap; broker leg uses the
EXISTING scripts/fetch_broker_recommend_historical.py (v2's "no script existed" claim retracted);
margin_detail folded into market/margin (same manifest dataset); L9 tail = NEW adapter (catch-ups
can't target C:), cadence documented as NOT uniformly session-based (ann_date calendar windows /
monthly broker / report_rc TTL halo).
B3 (metadata-only throttle): the floor is now CENTRAL — tushare_lock.MIN_BASE_SLEEP=1.5 applied INSIDE
spaced_call (callers cannot lower it) + floored in TushareFetcher.__init__; the four 1.0s constructors
raised to 1.5; a regression test pins the chokepoint floor (cooldown written >= 1.5s ahead for a 0.1s
caller).
B4 (no operational ledger): RecoveryPaths.ledger_append implements the row schema
(LEDGER_REQUEST_FIELDS: query params, page count, raw rows, confirmed_empty [positive-proof-only],
schema fingerprint, key null/dup stats, output sha256, first-fetch ts, exception, doc hash, state);
consolidation only after all partitions verified; dataset-level proof = ledger 100% + the dataset
profiler re-run on C: compared to the manifest's schema_variants/null/dup/warnings — counts demoted to
a coarse presence scan (labeled).
B5 (oracle could bless drift): plan §5 — full raw->normalized->ledger->provider chain ON C: before any
promotion; recovery-specific FULL-BIN frozen-prefix comparison with NO sampling and NO exception
auto-excusals; builder pinned to the live provider's source commit f93cb9d2...; canonical_kline_hash
computed directly on BOTH providers (live manifest's stored value is null); a diff BLOCKS promotion
until its cause is PROVEN (explicitly not auto-attributed to vendor restatement); report_rc: explicit
create_time + per-content raw_fetch_ts, first-seen reconstructed from the July catch-up state/logs
where provable else recovery-time floor or quarantine, revision baseline re-established only after
exact live-provider parity; raw-only data = NEW raw generation identity, never claimed byte-equivalent.
B6 (impossible atomic promotion): your 10-step journaled sequence adopted verbatim in plan §6
(freeze C: manifest -> locks -> reparse rescan -> incident-empty fingerprint check -> robocopy /E /XJ
to .recovery_incoming -> per-file sha256 verify -> PREPARED -> same-volume tombstone+rename -> SWAPPED
+ re-hash -> per family; tombstones retained until QA + first verified backup).
M1 (inventory): whole reference/+universe/ trees copied+hashed (234 files, incl.
industry_sw2021_members, ths_concept, stock_basic .bak); evidence snapshot (raw_cache manifests,
calendar-unfreeze state, July logs — 18 files); explicit yearly market/suspension files; margin_detail
correction; balancesheet_quarterly known-empty preserved; indicator archives + report_rc revision
baseline + first-seen stamps classified IRRECOVERABLE EVIDENCE (never "restored").
M2 (stale contamination): immutable runs/<run_id>; new run refuses existing id; no dirs_exist_ok
merging; fsync + file-locked ledger.
M3 (doc gate): workspace/configs/recovery_endpoint_contracts.yaml — 30 endpoints, each requiring
doc_path/doc_sha256/fields/limits/cadence/PIT semantics/human reviewed_by+at; --plan BLOCKS any leg
with an incomplete contract (today 10/10 blocked — the gate is active before any adapter exists).
M4 (backup): manifest-based non-regression (path/size/sha256 per generation; ZERO tolerance for an
unexplained missing historical path), 14 daily + 8 weekly + 12 monthly verified generations, >=3
independently restorable, no hardlink dedup, offline generation, prune as a SEPARATE job that
preserves good generations on guard failure.
Minors: presence labeled "count scan only"; baseline manifest sha256-pinned (fbc4aec0..., refused on
drift).

DISCLOSED LIMITS OF THIS FOLD
- The fetch ADAPTERS themselves are not built (that construction is what this re-review gates); the
  E:-write-denied integration test harness therefore does not exist yet either.
- The endpoint contracts are scaffolded empty — the 30 human doc reviews are pending.
- The C:-side provider build + full-bin oracle are specified (plan §5) but not implemented; they land
  with the adapters.
- ~20 data-dependent tests in tests/data_infra fail against the empty live store (pit_ledger/caches)
  — the incident's expected blast radius until restoration, not regressions (no failing test touches
  the changed fetcher/lock code; the lock/fetcher batteries pass 34/34).

RE-REVIEW QUESTIONS
1. Is the containment design now correct-in-principle AND correctly sequenced (adapters gated on an
   E:-write-denied integration test)? Anything still missing from RecoveryPaths' write-surface
   coverage (build output, profiler reports, quarantine)?
2. Is ADAPTER_SPECS now factually accurate and complete against the drivers at this pin? Any remaining
   dataset/store missing from inventory+specs?
3. Is the central MIN_BASE_SLEEP floor airtight at the chokepoint (spaced_call) — any Tushare call
   path that bypasses spaced_call entirely (thus the floor) besides raw-client construction already
   banned by PRO001?
4. Does the B4 ledger schema + profiler-comparison protocol constitute sufficient restoration proof?
   What would you add for the sparse/event datasets (confirmed_empty discipline)?
5. Is the §5 oracle protocol + report_rc first-seen policy adequate against the headline risk
   (backdating reconstructed revisions into sealed history)? Is "recovery-time floor or quarantine"
   the right default when July catch-up logs cannot prove first-seen?
6. Promotion §6: any hole left in the 10-step journaled sequence (crash windows between PREPARED and
   SWAPPED; tombstone retention; the .recovery_incoming staging dir's own reparse exposure)?
7. Sequencing: we propose GPT-verdict -> contract reviews + adapter construction (parallel) -> fetch
   authorization -> C:-build + oracle -> promotion authorization. Correct order? What is the minimal
   adapter test matrix you require before the fetch go-ahead?

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending text/code quoted + exact fix.
- Answer the 7 questions explicitly.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk before authorizing
  adapter construction + fetch.
```
