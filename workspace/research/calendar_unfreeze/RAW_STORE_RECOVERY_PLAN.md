# RAW STORE RECOVERY PLAN — 2026-07-13 deletion incident

**Status: PLAN ONLY — nothing here has been executed. Every fetch/restore step is §13-gated on the user.**

## 0. Incident summary (forensics complete, actor unidentified)

2026-07-13 **04:06:16–04:06:29** local: a programmatic alphabetical sweep emptied `data/analyst`, `data/corporate`, `data/fundamentals`, `data/market`, `data/normalized`, `data/pit_ledger`, and was deleting inside `data/qlib_builds/phase1_qfields_holdertrade_20260623` when it stopped.

**Ruled out:** the Phase 5-B B3 worktree session (tests fully tmp-isolated — verified its diff), all repo `rmtree` sites (provider/staging-scoped only), the 04:01 dashboard refresh (read-only), the 04:44 PR3 pytest battery (after the fact). No deleter process alive by 04:45; no matching session transcript. Recycle Bin / VSS require elevation (user step, §1).

**Intact (verified):**
- `data/qlib_data` — the LIVE provider (research/backtests unaffected), + `qlib_data.bak_thaw_step1_20260703c` (370.8 GB) + `qlib_data.bak_phasec_profit_dedt_sq_20260624` (224.3 GB) + staged `qlib_builds/thaw_step1_20260703c`
- `data/reference/` (trade_cal 8,797 rows / stock_basic / namechange / suspension_ranges…)
- all 5 registries, governance, holdout_seals, testing_ledger, text_store, `data_tracker.md` + `data_dictionary.md` (= the restoration checklist)
- `data/backups/` — but it holds **no raw-parquet backup** (only factor-registry + share_capital bins)

**Blocked until recovery:** daily raw job (5-C), monthly bump (5-B), PIT-ledger rebuilds, `pit_research_loader` sandbox research (fail-closed on the empty ledger — correct behavior). Provider-based formal research continues to work.

## 1. FIRST — user-run elevated recovery checks (cheap, before any re-fetch)

Run from an **elevated** console:

```bat
:: 1) VSS shadow copies on E: (if any exist, we can copy the whole raw tree back)
vssadmin list shadows /for=E:

:: 2) Recycle Bin usage on E: (programmatic deletes usually bypass it, but confirm)
dir /a E:\$RECYCLE.BIN

:: 3) "Previous Versions" GUI equivalent: right-click E:\量化系统\data -> Properties -> Previous Versions
```

Also check any personal backup surface: BaiduNetdisk, cloud drives, another machine, an old disk image. **If ANY copy of `data/market` + `data/fundamentals` + `data/analyst` + `data/corporate` exists, restore beats re-fetch** (hours vs days) — then jump to §4 verification.

Also worth 2 minutes: if you ran ANY cleanup/prune/migration around 04:06 (or an elevated tool did), say so — it changes nothing about recovery but closes the incident.

## 2. Re-fetch scope (what was lost, from the surviving data_tracker.md)

| Dataset family | Path | Approx rows (tracker) | Fetcher |
|---|---|---|---|
| daily OHLCV+basic+adj (2008/2010→2026-06-30) | `market/daily/` | ~14.8M rows / 4,495 files | `init_market_data.py` |
| index daily | `market/index/` | 7 indices | `init_market_data.py` |
| moneyflow / stk_limit / hk_hold / margin / margin_detail | `market/…` | per-day since ~2010 | `init_factor_data.py` |
| suspend_d per-date store | `market/suspend_d/` | per-day | `fetch_suspend_d_historical.py` |
| top_list / top_inst / block_trade / stk_holdertrade / cyq_perf | `market/…` | 5 endpoints | `fetch_new_alpha_endpoints.py` |
| statements (income/balancesheet/cashflow ×cumulative+quarterly), indicators (167-field), forecast, dividends, holder_number, index_weights, industry | `fundamentals/` | ~10M+ rows | `init_fundamentals_data.py` + `refresh_indicator_history.py` |
| report_rc deep history (2010-01→2026-06, 2.87M rows) + express/disclosure_date/fina_mainbz/fina_audit/repurchase/pledge_stat/top10_floatholders | `analyst/`, `fundamentals/`, `corporate/` | Bucket A ~10M rows | `workspace/scripts/fetch_bucket_a.py` |
| dividends/corporate actions | `corporate/` | — | `init_fundamentals_data.py` |
| `normalized/` + `pit_ledger/` | — | DERIVED | rebuilt in §4, not fetched |

## 3. Re-fetch sequence (STRICTLY SERIAL — §6.1, one fetcher, never parallel; machine-global api lock now enforces this across every session)

Preflight: `git stash`-free tree not required; but **stop/pause all other quant sessions' fetch-capable work first** (the api lock will serialize anyway, but quota is shared).

1. `venv/Scripts/python.exe src/data_infra/pipeline/init_market_data.py --start_date 20080101 --end_date 20260630`
2. `venv/Scripts/python.exe src/data_infra/pipeline/init_fundamentals_data.py --start_year 2008`
3. `venv/Scripts/python.exe src/data_infra/pipeline/init_factor_data.py --start-date 20080101 --end-date 20260630`
4. `venv/Scripts/python.exe src/data_infra/pipeline/refresh_indicator_history.py` (staged; captures update_flag revisions)
5. `venv/Scripts/python.exe scripts/fetch_suspend_d_historical.py` then `--ranges-only` sanity
6. `venv/Scripts/python.exe scripts/fetch_new_alpha_endpoints.py` (top_list/top_inst/block_trade/stk_holdertrade/cyq_perf; cyq_perf is 2018+ only — expected)
7. `venv/Scripts/python.exe workspace/scripts/fetch_bucket_a.py` (report_rc deep history + the 7 sibling endpoints)
8. Daily-window catch-up to today: `workspace/scripts/catchup_daily_range.py --start 20260701 --end <last session>` + `catchup_fundamentals_range.py` (ann_date-window per UNFREEZE_PLAN)

**Estimate:** 3–5 days wall-clock at 15000-积分 quotas (the original bootstrap + Bucket A took comparable time), single serial fetcher, `base_sleep=1.5` untouched. Each script is resume-safe/idempotent; on 429s slow down, never parallelize.

**PIT integrity of a re-fetch (why this is safe):** all our PIT anchors come from SERVED date fields (`ann_date`/`f_ann_date`/`update_flag`/`report_date`/`create_time`), not from our capture time — the ledger rebuild re-derives identical anchors. report_rc keeps the validated `max(report_date, create_time)` / `+2 open days` anchoring (REPORT_RC_PIT_ANCHOR_VALIDATION). The one caveat: if the VENDOR has restated any history since our original download, §4's oracle check will catch it as a diff — those become typed exceptions, not silent drift.

## 4. Verification (the intact provider is the oracle)

1. `verify_database.py` — raw integrity gate + PIT live regression harness.
2. Row-count reconciliation vs the surviving `data_tracker.md` per-dataset table (exact counts recorded pre-incident).
3. Rebuild derived layers: `build_qlib_backend.py --stage upstream-only` → regenerates `normalized/` + `pit_ledger/` (NO provider publish — the live provider is intact and stays untouched).
4. **Oracle check:** stage a full provider build (`--mode all`, staged, NOT published) and run the frozen-prefix audit + `canonical_kline_hash` against the LIVE provider — if the re-fetched raw regenerates a byte-identical frozen prefix, the re-fetch provably reproduces the pre-incident cut. Any diff = vendor restatement → typed exception process.
5. `run_daily_qa.py` full pass; then unblock 5-C daily job.

Disk: staged build needs the usual ≥400GB floor — currently 1354GB free, fine.

## 5. Prevention (fold into the standing plan)

- **Raw mirror backup**: the whole raw parquet layer is only ~6 GiB / ~35k files — add a nightly `robocopy /MIR` of `data/{market,fundamentals,analyst,corporate}` to `data/backups/raw_mirror/` (or another drive) at the end of the 5-C daily job. Trivial cost, removes this entire failure mode. (Add to the 5-C hardening.)
- The Phase 5-B **B3 attestation chain** (in-flight parallel session) would have made this tamper-EVIDENT at the next publish gate; it does not PREVENT deletion — the mirror does.
- Identify-the-actor follow-up: enable file-audit (SACL) on `data/` if the user wants attribution for a recurrence.
