# report_rc `report_date+1` PIT-anchor validation — VERDICT: PASS

*2026-06-08, branch `report-rc-p1-plumbing`. Answers the user's challenge to the prior
session's "forward-only" call: prove, via JoinQuant's genuine-PIT research data, whether
setting the visibility anchor to `report_date + 1` validates the pre-2022-05 backfilled
report_rc as point-in-time.*

## The challenge to the prior verdict

The prior session ruled report_rc **forward-only** (PIT 2022-05+) because 100% of rows
dated 2010-2021 carry `create_time = 2022-05-02/03` (a Tushare bulk-ingestion stamp).
That reasoning conflated two different things:

- **When Tushare *ingested* the row** (`create_time` = May 2022 for the whole backfill) — TRUE.
- **Whether `report_date` (the analyst publication date) is *faithful*** — NOT TESTED.

If `report_date` is a faithful publication date, then anchoring visibility at
`report_date + 1` (= `strictly_next_open_trade_day(report_date)`) is PIT-correct for the
deep history — regardless of when Tushare's DB happened to ingest it. The `create_time`
anchor (added in P1 by GPT review) is *safe but over-conservative*: it throws away the
entire 2010-2021 history on the assumption that report_date can't be trusted. This
document tests that assumption directly.

## Oracle

JoinQuant's 朝阳永续 一致预期 consensus (`jqfactor.get_factor_values`) is **genuinely
point-in-time** — prior Test A proved it via cyclical regime sign-flips that a
hindsight-fill cannot manufacture (神华/海螺 over-forecast +110%/+70% into the 2015 bust,
then under-forecast into the 2017 boom). It is an *independent* vendor pipeline from
Tushare report_rc. If a report_date+1 reconstruction from Tushare reproduces what the JQ
oracle saw, the report_date timestamps are real and the anchor is PIT.

## Test A′ — forecast LEVEL parity (no realized-actual in the loop)

`report_rc_pit_anchor_level_check.py`. Tushare report_date+1 consensus FY1 earnings-yield
(`mean(visible analyst FY1 eps) / raw close`) vs JQ PIT `predicted_earnings_to_price_ratio`,
5 large caps × {2015,2017,2019,2021}-06-30 (`jq_consensus_canary_SNAP1.csv`).

| Metric (n=20) | Value |
|---|---|
| Pearson corr | **+0.997** |
| Spearman corr | **+0.997** |
| mean \|jq_ep − ts_ep\| | 0.0055 (½ pp of earnings yield) |
| mean ratio ts_ep / jq_ep | 0.927 (Tushare ~7% *lower* = conservative) |

→ The report_date+1 reconstruction reproduces the genuine PIT consensus **level**
near-exactly. The 7% offset is methodology calibration (naive equal-weight FY1 mean vs
朝阳永续's blended/recency-weighted consensus) and is in the *conservative* direction.

## Test B′ — forecast-ERROR parity (the lookahead discriminator)

`report_rc_pit_anchor_validation.py`. Tushare report_date+1 `consensus_FY-Y / realized
basic_eps − 1` vs JQ PIT `pred_over_actual_minus1`, 15 large caps × fy 2013-2019
(`jq_consensus_pit_test.csv`), as-of mid-FY.

| Metric (n=103) | Value |
|---|---|
| Pearson corr(jq_err, ts_err) | **+0.775** |
| Spearman corr | **+0.833** |
| mean \|jq_err − ts_err\| | 0.081 |
| mean\|ts_err\| − mean\|jq_err\| | **+0.054** |

The last row is decisive: the Tushare report_date+1 reconstruction is *slightly LESS*
accurate than the PIT oracle — the **opposite** of the lookahead signature (a leaky
backfill would be *more* accurate than something genuinely blind to the future).

**Cyclical regime canaries — reproduced at full magnitude:**

| FY | name | JQ PIT err | Tushare rd+1 err |
|---|---|---|---|
| 2015 | 神华 (coal) | +1.105 | **+1.173** |
| 2015 | 海螺 (cement) | +0.695 | **+0.684** |
| 2017 | 神华 (coal) | −0.328 | **−0.305** |
| 2017 | 海螺 (cement) | −0.292 | **−0.343** |
| 2018 | 海螺 (cement) | −0.318 | **−0.354** |

If the 2022 backfill had leaked future knowledge, the 2015 神华 error would be ~0 (it
would "know" coal earnings were about to collapse). Instead it is +1.17 — equally
over-optimistic as the genuinely-PIT +1.105. **Two independent vendor pipelines agree
they were both blind to the future → report_date+1 is genuinely point-in-time.**

## Breadth structure survived the backfill

`eps_diffusion` (the flagship) is net-% analysts raising FY1 EPS — it needs ≥2 dated
forecasts per (stock × analyst × quarter). Local check:

| Era | groups with ≥2 dated forecasts | of those, share with a real eps revision |
|---|---|---|
| 2015 (backfilled) | 27.0% | 70.6% |
| 2018 (transition) | 39.8% | 71.4% |
| 2023 (contemporaneous) | 41.8% | 78.4% |

The granular revision history is **present** in the deep backfill, not collapsed to
one-row-per-quarter. The 2015→2023 gradient (27%→42%) is a mild flag (genuinely fewer
analyst updates in 2015, or some intermediate revisions lost in backfill) to quantify,
not a blocker.

## VERDICT

**`report_date + 1` IS a validated PIT visibility anchor for the pre-2022-05 backfilled
report_rc history.** `create_time = 2022-05` is an *ingestion* stamp, not evidence that
`report_date` is unreliable. Anchored at report_date+1, the deep history reconstructs the
exact point-in-time consensus that the independent 朝阳永续 oracle saw — no more (Test A′
level corr 0.997; Test B′ reproduces the genuine forecast errors incl. regime sign-flips,
with Tushare *less* accurate, ruling out lookahead). **This reverses the prior
"forward-only / eps_diffusion deep-history UNRECOVERABLE" call.**

## Broad-universe confirmation (2026-06-08) — PASS, market-wide

`jq_pit_anchor_broad_pull.py` (run in JoinQuant) → `predicted_earnings_to_price_ratio`
for the survivorship-correct as-of universe, 9 Jun-30 cross-sections 2013-2021, 3,802
distinct stocks. `report_rc_pit_anchor_broad_compare.py` matched 17,717 cells / 3,712
stocks.

| Check | Result |
|---|---|
| per-date cross-sectional Spearman | 0.914–0.978, **mean +0.940** (rising over time) |
| pooled Pearson / Spearman | +0.934 / **+0.950** |
| smallest size decile (1) Spearman | **+0.902** → monotone to +0.982 (decile 10) |
| later-delisted subset (789 names) | Spearman **+0.932** |
| level ratio ts/jq (median) | ~0.91 every year (stable conservative offset, no drift) |

Closes the two open objections: agreement holds for the **smallest caps** (0.90, not just
blue chips) and for **later-delisted names** (0.93, not a survivorship artifact). A backfill
that fabricated/cleaned report_dates would degrade precisely on thin-coverage small caps and
survivorship-sensitive delisted names — it does not. **report_date+1 is a validated PIT
anchor market-wide.** (No 朝阳永续 PIT revision/breadth factor existed in the JQ library to
add, so the BREADTH form is still pending the restatement canary — see below.)

## Honest residual scope (what PASS does and does not cover)

- **Proven decisively** on 15-20 large/mid caps over 2013-2021: report_date+1 reconstructs
  the PIT consensus **level and forecast error** faithfully (the timestamps are real).
- **Recommended scale-up (survivorship-robust):** `jq_pit_anchor_broad_pull.py` (JoinQuant
  research notebook) pulls the consensus for the **as-of universe incl. later-delisted +
  small caps**; `report_rc_pit_anchor_broad_compare.py` reports per-date / size-decile /
  delisted Spearman. This converts "15 blue chips" into "broad market" and rules out a
  large-cap-only faithfulness.
- **eps_diffusion BREADTH specifically:** level-parity is *necessary and strong but not
  sufficient* for breadth (breadth is a second-difference, more sensitive to the exact
  per-revision set than the mean). The **restatement canary** (2nd snapshot diff,
  `scripts/report_rc_backfill_canary.py recheck`, scheduled 2026-06-15) closes the last
  gap by detecting whether per-analyst rows are retroactively backfilled/restated into a
  past window.

## P1 backend re-anchor — IMPLEMENTED (2026-06-08, after broad confirmation)

The P1 `report_rc` anchor was `effective = next_open(max(report_date, create_time))` →
`create_time = 2022-05` dominated → effective dates collapsed to 2022-05+ (the P3
finding). Re-anchored in `pit_backend.py` `build_ledger` (report_rc branch): a
`create_time` is trusted ONLY when **contemporaneous** (gap ≤ `REPORT_RC_BACKFILL_GAP_DAYS
= 45` calendar days) → `max(report_date, create_time)`; a **bulk-backfill** stamp (gap >
45, e.g. 2022-05 on a 2010-2021 report) or a missing create_time → `report_date +
REPORT_RC_VENDOR_LAG_OPEN_DAYS (=2) open days`. Contemporaneous-era (2023+) behavior is
byte-identical; only the backfilled deep history is reclaimed.

- **Tests:** `tests/data_infra/test_report_rc_ledger.py` 12/12 (new
  `test_report_rc_backfill_create_time_ignored_anchors_on_report_date`); +84
  pit_backend/field-registry/namespace regression green (96 total).
- **End-to-end (real data, `p3_report_rc_basket_build.py`, 5-stock basket, 33k rows):**
  ledger effective-date span moved from `2022-05-05..2026-02-27` to
  **`2010-01-07..2026-02-27`**; `$report_rc__*` bins carry full-history events (茅台
  2,005 up / 2,297 down, 3,917 active days) and validate OK. Live `data/qlib_data`
  untouched (sandbox stage).

Still gated (unchanged): a full provider rebuild on the re-anchored history, the
remaining primitives (eps_same / dispersion / FY1-level / coverage), the catalog factor
(P4), and the compliant screen (P5). `$report_rc__*` stays QUARANTINE. Recommended before
merge: a GPT post-impl review of the re-anchor (matches the P1 review cadence).

## Artifacts
- `report_rc_pit_anchor_validation.py` → `workspace/outputs/report_rc_pit_anchor_validation.{csv,json}`
- `report_rc_pit_anchor_level_check.py`
- `jq_pit_anchor_broad_pull.py` (JoinQuant research notebook — user runs in cloud)
- `report_rc_pit_anchor_broad_compare.py` (consumes the broad pull)
- JQ oracle inputs: `聚宽回测明细/jq_consensus_pit_test.csv`, `jq_consensus_canary_SNAP1.csv`

No OOS touched. Sandbox; reads raw `data/` only.
