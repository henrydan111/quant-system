# RAW STORE RECOVERY PLAN v2 — 2026-07-13 junction-deletion incident

**Status: PLAN + C:-staged coordinator prepared. NO Tushare call has been made; every fetch is §13-gated on the user. E: writes minimized (this doc + coordinator code only).**

v1 is SUPERSEDED — it was unsafe as written (would overwrite intact reference data, wrote directly to E:, missed datasets, wrong paths, over-claimed resume-safety). Every v1 defect the user identified is folded in below.

## 0. Incident record (final, user-confirmed)

At **04:06:16** the user ran `git worktree remove --force C:\Users\henry\AppData\Local\Temp\quant-review-3d2ac0f`. That temp worktree contained **Windows junctions into the live `E:\量化系统\data` family dirs**; git recursed through them and deleted live data until killed ~04:11. Consistent with all forensics (alphabetical enumeration, children-deleted / parents-kept, `phase1_qfields` partial).

- **The temp worktree still exists — incident evidence. DO NOT delete it, `git worktree remove` it, or run any recursive operation inside it (it may still contain junctions into live data).** Also run `git worktree prune` NOWHERE until it is dismantled deliberately (junctions unlinked first, then removed).
- VSS shadows on E:: **none**. Recycle Bin: **empty**. E: is NVMe with TRIM; ~hours have passed with ongoing writes from other sessions — file-carving recovery is effectively hopeless. Re-fetch is the path unless the user produces an external backup.
- **E: write discipline until recovery completes:** no bulk writes, no CHKDSK, no defrag, no fetch-to-E:. Staging happens on **C: (separate physical SSD, ~3 TB free)**.

## 1. Ground truth: what survived, what was lost

**Reconciliation baseline = [data/qlib_builds/thaw_step1_20260703c/manifest.json](E:/量化系统/data/qlib_builds/thaw_step1_20260703c/manifest.json)** — the July-3 build profile of all **27 provider inputs, 78,948,729 rows total** (e.g. `daily` = 4,493 files / 14,821,292 rows, 20080102–20260701). It supersedes data_tracker.md's approximate counts. Note that dir holds ONLY the manifest — it is NOT a spare staged provider.

**SURVIVED (6/27 + provider layer):**
| What | Detail |
|---|---|
| `data/qlib_data` | LIVE provider, build `thaw_step1_20260703c`, 5,809 feature dirs — all provider-based research keeps working |
| `qlib_data.bak_thaw_step1_20260703c` / `.bak_phasec_…0624` | 370.8 GB / 224.3 GB provider backups |
| `reference/` | trade_cal (8,797) · stock_basic (5,861) · stock_st_daily (307,696) · namechange (18,237) + the HAND-CURATED irreplaceables: daily_price_repair_overrides.csv · moneyflow_known_empty_dates.txt · northbound_nonconnect_days.txt · ths_concept/ (NOTE: suspension_ranges.parquet was NOT here — it was in the deleted tree; DERIVED, rebuilt post-suspend_d-refetch via `--ranges-only`) |
| `universe/` | index_weights (1,090,872) · industry_sw2021 (511) |
| registries / governance / seals / ledger / text_store | untouched |

**LOST — 21/27 datasets (~77.5M rows) + non-spec stores:**
| Family | Datasets (manifest rows) |
|---|---|
| `market/` (10) | daily 14.82M · stk_limit 17.37M · moneyflow 14.14M · cyq_perf 9.19M · margin 6.60M · northbound 5.60M · top_inst 2.64M · block_trade 0.32M · top_list 0.25M · index_daily 27.9K |
| `fundamentals/` (7) | indicators 557.7K · income_quarterly 472.6K · cashflow_quarterly 468.5K · balancesheet 398.6K · income 360.6K · cashflow 365.8K · forecast 136.3K |
| `corporate/` (3) | holder_number 524.7K · stk_holdertrade 183.6K · dividends 163.6K |
| `analyst/` (1) | report_rc 2.94M |
| **Non-DATASET_SPECS stores (v1 missed these)** | per-date `suspend_d` store (`market/suspend_d/<yr>/suspend_d_<date>.parquet` — timing-preserving, load-bearing for the monthly completeness proof) · `broker_recommend` (`analyst/broker_recommend/broker_recommend_{YYYYMM}.parquet` — the 金股 production TUD) · Bucket-A siblings (express / disclosure_date / fina_mainbz / fina_audit / repurchase / pledge_stat / top10_floatholders) · staged indicator-history archives · `margin_detail` |
| Derived (rebuild, don't fetch) | `normalized/` · `pit_ledger/` |
| Damaged staged build | `qlib_builds/phase1_qfields_holdertrade_20260623` — 3,217 feature dirs remain, INCOMPLETE; quarantine as abandoned, never publish |

## 2. Architecture: C:-staged recovery (never fetch-to-E:)

```
C:\quant_recovery\
  staging_data\        <- full data_root layout (market/, fundamentals/, corporate/, analyst/, reference/, universe/)
  ledger\recovery_ledger.jsonl   <- append-only per-(dataset,partition) fetch/verify records
  reports\             <- inventory / reconciliation JSON
```

1. **Fetch → C: staging only.** The coordinator refuses any target under `E:\` structurally.
2. **Reference/universe survivors are COPIED E:→C: (read-only from E:)** so staged fetchers have the calendar/stock_basic they need — the live copies are never re-fetched or overwritten (v1's `init_market_data` would have clobbered `stock_basic` and truncated the authoritative 1990–2026 `trade_cal`; that path is banned).
3. **Verify in staging** against the manifest baseline (§4) — `verify_database.py` lacks `--data-root`, so verification runs via the coordinator's own reconciliation plus targeted checks pointed at C:.
4. **Promote C:→E: once, atomically, per family**, only after reconciliation passes and with the user's explicit go-ahead (one bulk write pass to E:, not thousands of incremental ones).
5. Then rebuild derived layers (`build_qlib_backend --stage upstream-only`) and run the frozen-prefix / canonical-kline oracle vs the intact live provider.

## 3. Script-capability matrix (verified against code — why the coordinator exists)

| Script | Gap for recovery use | Coordinator handling |
|---|---|---|
| `init_market_data.py` | fetches + OVERWRITES `stock_basic`/`trade_cal` (window-truncated); `base_sleep=1.0` (<1.5 §6.1); logs hard-coded to E:\logs | reference leg SKIPPED (survivors copied); market legs driven with staging data-root + `base_sleep≥1.5` enforced |
| `init_fundamentals_data.py` | `base_sleep=1.0`; has `--data-root` (usable) | driven with C: data-root + spacing floor |
| `init_factor_data.py` | `base_sleep=1.0`; continues past failed dates and can still exit 0 (NOT resume-safe as v1 claimed) | per-date ledger rows; a failed partition stays `failed` and blocks reconciliation until refetched |
| `fetch_suspend_d_historical.py` | year files only; the per-date store is written by the daily updater | coordinator adds an explicit per-date `suspend_d` leg (canonical `write_suspend_d`, timing-preserving) |
| `fetch_new_alpha_endpoints.py` | E:-rooted paths | staging data-root |
| `scripts/fetch_bucket_a.py` (v1 had the wrong path) | E:-rooted | staging data-root; covers report_rc deep history + the 7 siblings |
| `refresh_indicator_history.py` | has `--data-root` | staged leg incl. history archives |
| `verify_database.py` | **no `--data-root`** — would inspect the empty live store | replaced in-staging by coordinator reconciliation (§4); run on E: only AFTER promotion |
| (new) broker_recommend leg | no bootstrap script existed | coordinator leg fetching `broker_recommend_{YYYYMM}` months per the data_dictionary spec |

**Global fetch rules (§6.1):** one serial fetcher, `base_sleep ≥ 1.5` (coordinator asserts a hard floor and refuses lower), the machine-global api lock already serializes across every session/worktree, all other quant sessions pause their Tushare-capable work during recovery, backoff on 429s — never parallelize.

## 4. Verification & the vendor-history caveat (honest scope)

1. **Reconciliation (staging, per dataset):** file/row counts + date-range vs the manifest baseline; per-partition ledger must be 100% `verified` — no `failed`/`missing` rows. The post-manifest tail (2026-07-02 → last complete session) is reconciled separately via the calendar (expected-session enumeration), since the manifest ends at 20260701.
2. **Oracle check (after promotion):** staged full rebuild (NOT published) + frozen-prefix audit + `canonical_kline_hash` vs the intact live provider — proves the re-fetched raw REGENERATES the provider byte-identically for everything the provider serves.
3. **Honest limitation (user-stated, correct):** a fresh Tushare download reflects TODAY's vendor tables. The oracle validates provider-SERVED outputs; it CANNOT prove raw-only columns / superseded revision rows are byte-identical to the originals (e.g. collapsed restatement intermediates). Any oracle diff = vendor restatement → typed exception process, documented per dataset. Research consequences: PIT anchors derive from served date fields, so ledger semantics survive; but raw-level provenance for pre-incident revisions is attested only by the manifest counts, not content hashes (we never stored raw content hashes before this incident — the Phase 5-B full-content manifest closes that hole going forward).

## 5. Backup design v2 (replaces v1's unsafe nightly /MIR)

v1's `robocopy /MIR` mirror inside `data/backups` was doubly wrong: same physical drive, and `/MIR` propagates deletions into the backup. Replacement:

- **Versioned copies on a DIFFERENT physical disk** (`C:\quant_backups\raw\<YYYYMMDD>\`), `robocopy /E` (never `/MIR`), N-generation retention.
- **Large-deletion guard** before each backup run: if the source raw tree's file count dropped >2% vs the last generation, REFUSE to back up and alert (a deletion must never age out the good generations).
- Wire into the 5-C daily job only after recovery; design reviewed with the Phase 5-C GPT thread.
- Plus the already-committed prevention: audit SACL on `data/` (user's elevated command, when convenient) and — root cause — **never junction live data into disposable trees; worktree removal must be preceded by a junction scan** (`dir /AL /S` inside the worktree).

## 6. Execution order (everything below §13-gated, in this order)

1. User reviews this plan + coordinator; user pauses other sessions' Tushare-capable work.
2. `raw_recovery_coordinator.py --inventory` (no network) — gap report vs manifest.
3. `--preflight` (no network) — staging disk, survivors copy, spacing floor, script matrix.
4. User authorizes fetch → coordinator legs run serially on C: (days; resumable via ledger).
5. Reconciliation report → user reviews.
6. User authorizes promotion → one C:→E: atomic pass per family.
7. Derived rebuild (`--stage upstream-only`) + oracle check + `run_daily_qa`.
8. Backup v2 goes live; daily 5-C job resumes; incident closed in project_state.
