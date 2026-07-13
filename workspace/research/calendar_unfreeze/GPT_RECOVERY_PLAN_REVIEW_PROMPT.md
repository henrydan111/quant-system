# GPT 5.5 Pro cross-review — raw-store RECOVERY design (plan v2 + C:-staged coordinator)

Status: ready to send. Branch `calendar-unfreeze`, artifacts pinned to commit `dfe5608`. NO fetch has been executed; this review gates the wiring + execution of the fetch legs.

**Self-review (§10 prerequisite, done):** cited numbers verified this session (manifest read: 27 datasets / 78,948,729 rows, daily 4,493/14,821,292; coordinator runs: 21 LOST / 77,516,755 rows, preflight C: 2,801 GB, 10 survivor sets copied+row-verified); script gaps verified by grep/ls (base_sleep=1.0 in 3 initializers, verify_database lacks --data-root, fetch_bucket_a.py in scripts/, init_market_data fetches+overwrites reference); no OOS/seal semantics touched (recovery is data-ops; the one research-integrity surface = vendor-history drift, disclosed in §4); §3 invariants not modified. Fix during self-review: suspension_ranges wrongly listed as a reference survivor — it was in the deleted tree, DERIVED (rebuilt via --ranges-only); reference/ hand-curated irreplaceables (daily_price_repair_overrides.csv, moneyflow_known_empty_dates.txt, northbound_nonconnect_days.txt, ths_concept/) added to the survivor copy set. Verdict: clean for GPT.

---

```text
ROLE
Senior reviewer for an A-share quant system where research validity outranks code that runs. This is an
OPERATIONS review with one research-integrity surface: on 2026-07-13 04:06 the operator accidentally
deleted the raw parquet store — `git worktree remove --force` on a temp worktree recursed through
Windows JUNCTIONS into the live `E:\量化系统\data` and deleted 21 of the 27 provider-input datasets
(~77.5M rows) plus several non-registry stores, until killed. INTACT: the live Qlib provider
(thaw_step1_20260703c, 5,809 feature dirs) + two large provider backups + reference/ + universe/ +
all registries. There is NO raw backup, NO VSS shadow, empty recycle bin; E: is NVMe (TRIM) — undelete
is dead. Recovery = re-fetch from Tushare (15000-point account), STAGED ON C: (separate physical SSD,
~2.8TB free), promoted to E: once, then derived layers rebuilt and verified against the intact provider.
You are reviewing the RECOVERY DESIGN BEFORE any fetch is authorized. The fetch legs are deliberately
NOT wired yet — the coordinator's --fetch refuses; wiring happens only after this review + the
operator's explicit go-ahead.

REPO https://github.com/henrydan111/quant-system  (branch calendar-unfreeze, commit dfe5608)
- Recovery plan v2:  https://raw.githubusercontent.com/henrydan111/quant-system/dfe5608/workspace/research/calendar_unfreeze/RAW_STORE_RECOVERY_PLAN.md
- Coordinator:       https://raw.githubusercontent.com/henrydan111/quant-system/dfe5608/scripts/raw_recovery_coordinator.py
Context (contracts the design must honor):
- CLAUDE.md §6.1 (Tushare safety: ONE serial fetcher, base_sleep>=1.5, backoff not retry), §6.4
  (mutation safety), §13 (risky-action gating):
  https://raw.githubusercontent.com/henrydan111/quant-system/dfe5608/CLAUDE.md
- The reconciliation baseline is data/qlib_builds/thaw_step1_20260703c/manifest.json (not in git —
  gitignored data): 27 datasets profiled at the July-3 build, 78,948,729 rows total, per-dataset
  file/row/date-range counts (e.g. daily 4,493 files / 14,821,292 rows, 20080102..20260701).
- Relevant fetchers the legs will drive (verify the plan's gap matrix against them):
  https://raw.githubusercontent.com/henrydan111/quant-system/dfe5608/src/data_infra/pipeline/init_market_data.py
  https://raw.githubusercontent.com/henrydan111/quant-system/dfe5608/src/data_infra/pipeline/init_fundamentals_data.py
  https://raw.githubusercontent.com/henrydan111/quant-system/dfe5608/src/data_infra/pipeline/init_factor_data.py
  https://raw.githubusercontent.com/henrydan111/quant-system/dfe5608/scripts/fetch_suspend_d_historical.py
  https://raw.githubusercontent.com/henrydan111/quant-system/dfe5608/scripts/fetch_new_alpha_endpoints.py
  https://raw.githubusercontent.com/henrydan111/quant-system/dfe5608/scripts/fetch_bucket_a.py
  https://raw.githubusercontent.com/henrydan111/quant-system/dfe5608/src/data_infra/pipeline/refresh_indicator_history.py

DESIGN SUMMARY (authoritative text = the two pinned artifacts)
1. C:-only staging (C:\quant_recovery\staging_data with the full data_root layout); every coordinator
   write is structurally refused unless under C:\quant_recovery (_assert_staging_path); E: is read-only
   during recovery (minimize NVMe writes per the operator's directive).
2. Survivors (reference/ + universe/ + hand-curated CSVs/txts) are COPIED E:->C: and NEVER re-fetched;
   init_market_data's reference leg is BANNED (it would overwrite intact stock_basic and truncate the
   authoritative 1990-2026 trade_cal to the requested window).
3. Nine declared fetch legs (L1 market daily/index; L2 fundamentals incl. VIP quarterly; L3 factor
   daily incl. margin_detail; L4 suspend_d year + per-date store; L5 alpha endpoints; L6 Bucket-A
   report_rc deep history + 7 siblings; L7 broker_recommend [new leg — no bootstrap script existed];
   L8 indicator staged archives; L9 post-manifest tail 20260702..last-complete-session). All serial,
   base_sleep floor 1.5 enforced at leg-load (dataclass __post_init__ raises), machine-global api lock
   already serializes cross-session.
4. Reconciliation: per-(dataset,partition) append-only ledger on C:; counts/date-ranges vs the manifest
   baseline; the post-manifest tail reconciled via calendar session enumeration. verify_database.py is
   NOT used in staging (it has no --data-root and would read the empty live store).
5. Promotion: ONE atomic C:->E: pass per family, only after reconciliation passes and with a separate
   operator go-ahead. Then: build_qlib_backend --stage upstream-only (rebuild normalized/ + pit_ledger/),
   staged full rebuild + frozen-prefix audit + canonical_kline_hash vs the INTACT live provider (the
   oracle), run_daily_qa.
6. Vendor-history caveat (research integrity, disclosed not hidden): a fresh download reflects TODAY's
   vendor tables; the oracle proves provider-SERVED outputs regenerate byte-identically, but CANNOT
   prove raw-only columns / superseded revision rows match the originals (no raw content hashes were
   stored pre-incident). Any oracle diff = vendor restatement -> typed exception, per dataset.
7. Backup v2 (post-recovery): versioned generations on the OTHER physical disk (C:\quant_backups),
   robocopy /E (NEVER /MIR — deletion propagation), N-generation retention, and a large-deletion guard
   (refuse to back up if source file count dropped >2% vs the last generation). Root-cause prevention:
   never junction live data into disposable trees; junction scan (dir /AL /S) before any worktree remove.

REVIEW QUESTIONS
1. Containment: is the C:-staging + promote-once architecture sound? Any path in the coordinator or the
   driven scripts where a fetch/normalize/log write can still reach E: (log handlers, config-relative
   paths, StorageManager defaults) despite _assert_staging_path — and how should the leg wiring pass the
   staging data-root to each driver so NOTHING falls back to the live root?
2. Inventory completeness: with the 21 manifest datasets + the 6 extra stores (per-date suspend_d,
   broker_recommend, Bucket-A siblings, margin_detail, indicator archives, derived suspension_ranges) +
   the post-manifest tail — is anything still missing for a complete raw-layer restoration? (Note:
   stock_st_daily has no fetcher and SURVIVED; ST authority for its gap window is namechange ranges.)
3. Reconciliation: is manifest-count + per-partition ledger + calendar-enumerated tail sufficient to
   declare a dataset restored? Should any dataset require stronger evidence (e.g. per-date row-count
   distributions for daily-partitioned sets, schema-variant checks vs the manifest's schema_variants)?
4. Research integrity: is the vendor-drift posture correct — oracle-verifies-served-outputs + typed
   exceptions on diff + explicit non-claim about raw-only columns? Any PIT hazard introduced BY the
   recovery itself (e.g. report_rc rows arriving 2026-07-01..today now being bulk-backfilled — does the
   Phase 5-A availability-boundary guard need a special case for the re-fetch)?
5. Promotion safety: should the C:->E: promotion re-verify (re-hash staging vs ledger) immediately
   before each family move, and what is the right atomicity primitive on Windows for a cross-volume
   move (copy+verify+swap vs robocopy /E + count-verify)? Cross-volume os.replace does not exist —
   propose the concrete sequence.
6. §6.1 enforcement: base_sleep floor at leg-load + machine-global api lock + serial legs — airtight,
   or does any driven script construct its own fetcher with base_sleep<1.5 in a way the coordinator
   cannot override without code changes (name them)?
7. Backup v2: is the >2% large-deletion guard the right shape (vs absolute thresholds / two-man rule)?
   Retention N? Should generations be hardlink-deduped?
8. The damaged staged build (phase1_qfields_holdertrade_20260623, 3,217/? feature dirs) and the
   incident-evidence worktree (may still contain junctions into live data): correct handling? Propose
   the safe dismantling procedure for the junctioned worktree when evidence retention ends.

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending text/code quoted + exact fix.
- Answer the 8 questions explicitly.
- Final line: SHIP / REVISE / REWORK + the single most important residual risk before authorizing the fetch.
```
