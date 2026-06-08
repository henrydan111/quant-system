# Post-Implementation Code Review for GPT 5.5 Pro — report_rc PIT re-anchor

**Date:** 2026-06-08.
**Repository:** https://github.com/henrydan111/quant-system (public). **Branch:** `report-rc-p1-plumbing`.
**Scope:** review the ACTUAL CODE of a single, surgical change to the `report_rc` PIT visibility anchor in
`pit_backend.py build_ledger`. This sits on top of the P1 plumbing slice you already signed off
(MERGE-WITH-NITS). It is NOT a re-litigation of the P1 architecture (event-flow, ledger key, materializer,
TTL) — those are settled. Judge ONLY the re-anchor: is it PIT-correct, are the threshold semantics right,
are there leakage/determinism/edge-case bugs, and is the test coverage adequate to merge?

## Why this change (the empirical result it encodes)
The P1 anchor was `effective = strictly_next_open(max(report_date, create_time))`. For the pre-2022-05
backfilled history, `create_time` is a **2022-05-03 bulk-ingestion stamp** on every 2010-2021 forecast, so
the `max()` collapsed the entire deep history's visibility to 2022-05 — discarding it. The prior session
called report_rc "forward-only" on that basis.

This was tested directly against JoinQuant's **genuinely point-in-time** 朝阳永续 一致预期 consensus
(`jqfactor.get_factor_values`), which is an independent vendor pipeline. Result (full writeup:
`REPORT_RC_PIT_ANCHOR_VALIDATION.md`):
- **Forecast LEVEL** (Tushare `report_date+1` consensus FY1 E/P vs JQ `predicted_earnings_to_price_ratio`):
  Pearson/Spearman **+0.997**, mean |diff| 0.0055.
- **Forecast-ERROR parity** (Tushare `pred/actual−1` vs JQ PIT `pred/actual−1`, 103 cells): reproduces the
  cyclical regime sign-flips at full magnitude (神华 FY2015 +1.17 vs JQ +1.105; flips negative into the 2017
  boom), and the Tushare reconstruction is *slightly LESS* accurate than the oracle (`mean|ts_err| −
  mean|jq_err| = +0.054`) — the **opposite** of a lookahead signature.
- **Broad / survivorship** (JoinQuant cloud pull, 3,712 stocks × 9 Jun-30 cross-sections 2013-2021): per-date
  cross-sectional Spearman mean **+0.940**, holding for the **smallest size decile** (+0.902) and
  **later-delisted** names (+0.932).

Conclusion: `create_time = 2022-05` is an *ingestion* stamp, not evidence `report_date` is unreliable.
`report_date` is the faithful publication date market-wide, so `report_date+1` is a PIT-correct anchor and
the backfill stamp must not gate the deep history.

**Read (raw):**
- **The code diff (79 insertions / 23 deletions, 2 files):**
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-p1-plumbing/workspace/research/data_expansion/reanchor_report_rc_code.diff
- The implemented module (surrounding context — the `report_rc` `DatasetSpec` ~L517, the constants
  `REPORT_RC_VENDOR_LAG_OPEN_DAYS` / `REPORT_RC_BACKFILL_GAP_DAYS` ~L150, the `build_ledger` report_rc branch
  ~L2170, `add_open_day_lag` ~L709, `strictly_next_open_trade_day`, `normalize_date_series`):
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-p1-plumbing/src/data_infra/pit_backend.py
- Tests:
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-p1-plumbing/tests/data_infra/test_report_rc_ledger.py
- The validation writeup (the evidence behind the change):
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-p1-plumbing/workspace/research/data_expansion/REPORT_RC_PIT_ANCHOR_VALIDATION.md

## What was implemented (the diff)

1. **New constant** `REPORT_RC_BACKFILL_GAP_DAYS = 45` (calendar days). A `create_time` whose gap after
   `report_date` exceeds this is treated as a **bulk-backfill stamp** and ignored; within it, a
   **contemporaneous** ingestion timestamp. Justification baked into the docstring: genuine contemporaneous
   lags are ≤ a few days (2023+ median 1d); the smallest backfill gap (late-2021 reports stamped 2022-05) is
   ~120d, so 45 cleanly separates the two regimes. `REPORT_RC_VENDOR_LAG_OPEN_DAYS = 2` (open trading days)
   is unchanged.

2. **`build_ledger` report_rc branch** — replaced the old `observed = max(report_date, create_time)` with
   missing-create fallback by:
   ```python
   report_dt = normalize_date_series(work["report_date"])
   create_dt = normalize_date_series(work["create_time"]) if "create_time" in work.columns else NaT
   gap_days = (create_dt - report_dt).dt.days
   contemporaneous = create_dt.notna() & (gap_days >= 0) & (gap_days <= REPORT_RC_BACKFILL_GAP_DAYS)
   # default (backfill stamp / missing / pre-dated create_time): report_date + lag
   observed = add_open_day_lag(report_dt, self.open_calendar(), REPORT_RC_VENDOR_LAG_OPEN_DAYS)
   if contemporaneous.any():
       trusted = pd.concat([report_dt, create_dt], axis=1).max(axis=1)   # = max(report, create)
       observed.loc[contemporaneous] = trusted.loc[contemporaneous]
   work["disclosure_date"] = observed
   work["effective_date"] = strictly_next_open_trade_day(observed, self.open_calendar())
   ```
   Net effect: **contemporaneous rows behave byte-identically to the old code** (`max(report, create)` →
   next-open); **backfill-stamped or missing-create rows** anchor at `report_date + 2 open days` → next-open,
   reclaiming the deep history instead of collapsing to 2022-05. The `DatasetSpec` + constant comments were
   updated to document the new semantics.

3. **New test** `test_report_rc_backfill_create_time_ignored_anchors_on_report_date` — two analysts, same
   `report_date=2020-01-01`: one with a contemporaneous `create_time` (honored → 2020-01-02), one with a
   `create_time=2022-05-03` bulk stamp (ignored → `report_date + 2 open days` → 2020-01-06, the row SURVIVES
   rather than dropping to NaT off-calendar). The 11 existing report_rc tests + 84
   pit_backend/field-registry/namespace regression tests stay green.

**Verification done locally:** 12/12 report_rc + 84 regression green; end-to-end on the real 5-stock basket
(`p3_report_rc_basket_build.py`, 33k rows) the ledger effective-date span moved from `2022-05-05..2026-02-27`
to **`2010-01-07..2026-02-27`**, and `$report_rc__*` bins carry full-history events (茅台 2,005 up / 2,297
down, 3,917 active days), all bins validate OK. CI (offline PIT-prevention gate) is green on the PR.

## Review questions (find bugs)

**Q1 — threshold semantics / leakage.** Is `gap_days = (create_dt - report_dt).dt.days` with
`contemporaneous = notna & (gap_days ≥ 0) & (gap_days ≤ 45)` correct? Specifically: (a) when `create_dt` is
NaT, `gap_days` is NaN → both comparisons False → row falls to `report_date + lag` (intended); confirm no
NaN-propagation surprise. (b) a `create_time` slightly EARLIER than `report_date` (gap < 0) is treated as
backfill/`report_date+lag` — is that the right call, or should a pre-dated create_time be honored? (c) the
crux: is there ANY row for which the new anchor exposes a forecast EARLIER than it was actually available
(a real lookahead) that the old `max()` anchor did not?

**Q2 — the 45-day constant.** Is 45 calendar days defensible as the separator? The risk in the
"too-permissive" direction: a genuinely late-ingested contemporaneous report with gap > 45d gets classified
backfill → anchored at `report_date+2` (earlier than its true `create_time`). The validation argues
`report_date` IS the availability date (so this is not a leak), but is that reasoning airtight, or should the
threshold be larger (e.g. 90d, still below the ~120d minimum backfill gap) for a safety margin? Conversely,
could any legitimate 2022-transition backfill row have a gap ≤ 45d and be wrongly trusted (anchored late, no
leak but loses deep-history reclamation for that row)?

**Q3 — contemporaneous vs backfill anchor asymmetry.** Contemporaneous rows get `max(report, create)` with NO
`+2 open-day` floor; backfill/missing rows get `report_date + 2 open days`. So two rows with the same
`report_date` can receive DIFFERENT effective dates (a contemporaneous one can be EARLIER than a backfill one).
Intended (the contemporaneous create_time is the real availability, trusted directly; preserving exact prior
behavior for 2023+). Any scenario where this asymmetry is wrong — e.g. in the 2022 transition where the same
stock-date has both a contemporaneous and a backfill-stamped forecast?

**Q4 — determinism & dtype.** `(create_dt - report_dt).dt.days` and the boolean-mask `.loc[contemporaneous]`
assignment — stable across pandas versions / machines? Does `normalize_date_series` floor `create_time` to a
date or preserve the intraday time (and does it matter, given `.dt.days` floors and
`strictly_next_open_trade_day` normalizes)? Any index-alignment hazard in
`observed.loc[contemporaneous] = trusted.loc[contemporaneous]`?

**Q5 — interaction with the materializer / full-scale.** Reclaiming 2010-2021 means effective_dates now span
16 years instead of ~4. The downstream `_materialize_report_rc_consensus` (per-`(code, analyst, quarter)`
`eps.shift(1)` revisions; `n_active` 120-open-day TTL merged per analyst) consumes `effective_date`
unchanged. Any correctness or performance concern from the now-much-larger effective-date range at the full
2.87M-row / 5,600-stock build (vs the 33k basket that was verified)?

**Q6 — test adequacy.** The new test covers a years-large backfill gap. What's the highest-value MISSING
test before merge? Candidates: a boundary case (gap exactly 45 vs 46), a pre-dated create_time (gap < 0), a
contemporaneous-but-multi-day lag (gap 3-44, must still trust create_time and end up later than
`report_date+2`), a 2022-transition stock with mixed contemporaneous+backfill rows. Which would you require?

**Q7 — overall.** MERGE / MERGE-WITH-NITS / CHANGES-REQUIRED for the re-anchor, and the single most important
fix or test to add first. (The full provider rebuild on the re-anchored history, the remaining primitives,
the P4 catalog factor, and the P5 screen remain separately gated; `$report_rc__*` stays QUARANTINE.)
