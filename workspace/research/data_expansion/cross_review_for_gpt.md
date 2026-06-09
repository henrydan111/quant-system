# Cross-Review for GPT 5.5 Pro — Tushare 15000积分 Data-Expansion Plan

**Date:** 2026-06-07.
**Repository:** https://github.com/henrydan111/quant-system
**Scope:** review a *proposal*, not merged code. We upgraded the Tushare Pro account 5000 → 15000
积分 and must decide which new endpoints to ingest into an A-share quant factor system. Two things to
cross-review: (1) the *verified facts* (live access + history-coverage probes), and (2) the
*prioritization & sequencing* of the expansion plan those facts imply. We want adversarial scrutiny of
the reasoning, the PIT hazards, and the cost/benefit — especially whether the flagship bet is sound.

Artifacts in repo (`workspace/`): plan = `research/data_expansion/tushare_15000_expansion_plan.md`;
probes = `outputs/tushare_endpoint_probe_*.json`, `tushare_coverage_probe_*.json`,
`tushare_depth_probe_*.json`, `outputs/report_rc_universe_*.json`; probe scripts =
`scripts/probe_tushare_{endpoints,coverage,depth}.py`, `scripts/probe_report_rc_universe.py`.

> **POST-GPT-CROSS-REVIEW UPDATE (2026-06-08).** GPT's review was accepted in full — all 5 findings
> are correct. Actions taken: (1) **Finding 1** — ran the all-market `report_rc` coverage probe (breadth
> / survivorship / cap-bucket / pagination); results in §2.3 (and the probe exposed a 5000-row
> per-call cap → ingestion must month-chunk). (2) **Finding 2** — the "Wave 1 all PIT-clean" claim was
> a real internal contradiction; `report_rc` is now treated **quarantine-until-tested**, anchored
> `effective_date = strictly_next_open_trade_day(report_date)` + a forecast-age expiry (§3, §4 Q-D1).
> (3) **Finding 3** — `pledge_stat` exposes only `end_date` (a weekly exchange statistic date, not a
> disclosure date) → NOT auto-PIT-safe; date-semantics check required before Wave-4 promotion (§2.2).
> (4) **Finding 4** — corrected: the JoinQuant PIT cache today holds index-membership/valuation/ST/
> paused only; concept membership requires a **new schema + refresh notebook** extension, not "already
> there" (§3). (5) **Finding 5** — access count reworded: 55 probes = 53 not-owned + 2 owned controls.
> **Verdict adopted:** do **Wave 1A audit-first** (a raw, non-Qlib `report_rc` IS-2014-20 pilot
> measuring *incremental* RankIC after neutralizing vs price/size/industry/fundamentals/owned-flow),
> not full ingestion; recent-only Wave 2/3 → raw archival only, no governance toll until a
> pre-registered short-window or live-forward protocol exists.
> **The two residual open items are now worked** (2026-06-08): §2.4 resolves the size-selection design
> question (direction signal ⟂ size → pooled-on-covered is sound; analyst-count is a size proxy →
> dropped); §2.5 baselines a `report_date` backfill canary (ingestion lag = 1 day; decisive diff after
> a 2nd snapshot). Only the post-2nd-snapshot backfill diff + GPT's anchor-buffer call remain.

---

## 0. Context GPT needs (you have not seen this repo)

- **System:** A-share quant factor platform. Tushare Pro → Parquet → PIT ledger → Qlib backend.
  177-factor catalog; **6 factors `approved`** (the rest draft/candidate). Research protocol is
  **walk-forward: 5y train / 2y val / 1y test**, with the standing convention **IS 2014-2020 /
  sealed OOS 2021-2026** and a one-shot OOS (sacred — run once per variant).
- **Governance (relevant to cost):** every new field passes a fixed toll — fetch script → raw Parquet
  → normalize → PIT ledger (correct disclosure anchor) → Qlib materialization (event-like daily
  endpoints **must** be namespaced `{dataset}__{col}` so they don't shadow OHLCV bins) →
  `field_status.yaml` `quarantine`→coverage+parity audit→`approved` (with append-only approval log +
  per-promotion YAML). Same-day daily outcomes must be wrapped in `Ref(...,1)` (enforced by a
  PIT-safety lint).
- **What we already own (do NOT re-propose):** `daily`, `daily_basic`, `adj_factor`, `stk_limit`,
  `suspend_d`; full statement families (`income/balancesheet/cashflow/fina_indicator` + VIP),
  `forecast`, `dividend`; `moneyflow` (standard), `hk_hold` (northbound), `margin_detail`,
  `stk_holdernumber`, and the 5 alpha endpoints `top_list/top_inst/block_trade/stk_holdertrade/cyq_perf`;
  SW2021 industry + index weights; a **JoinQuant PIT cache** already exists for point-in-time index
  membership (this matters for §4 below).
- **The prior-art result that should anchor your skepticism:** the most recent *new-data factor
  screen* (factors derived from the already-owned moneyflow/LHB/chip endpoints) was a **negative
  result — 0/8 cleared the pre-registered bar**. So "more endpoints" has already failed once. The
  burden of proof on any new ingestion is real.
- **The strategic gap (from the strategy KB):** the book is **100% long-only**; we want either a
  market-neutral leg or genuinely orthogonal long-only alpha.

---

## 1. TL;DR — what to check

| # | Claim / decision | Risk | What to verify |
|---|---|---|---|
| A | **Access:** all 55 probed high-value endpoints are callable at 15000积分 (54 ACCESS / 1 missing-arg / 0 DENIED). | low (tested) | Sanity-check the probe method; is "permission passed" a safe inference from a non-permission error? |
| B | **Coverage kills Wave 2/3:** `limit_list_d`=2020+, `moneyflow_dc`=2024+, `hm_detail`=2024+, `dc_member`=2025-snapshot. These **cannot** support IS-2014-20. | **high** | Is deferring all recent-only sentiment/flow/concept data correct, or is a 2021-2026 forward-only study worth the governance toll now? |
| C | **Flagship = `report_rc`** (analyst consensus, deep history 2010+). Thesis: orthogonal to price+fundamentals+flow. | **high** | Is the orthogonality thesis sound, or is sell-side consensus over-arbitraged / PIT-hazardous? Are we rationalizing past the 0/8 result? |
| D | **PIT anchor for `report_rc`** = `report_date` (only date column; no separate first-publish/entry date). | **high** | Is `report_date` a safe strict visibility anchor? Does Tushare backfill/restate it? Coverage-survivorship in analyst panels? |
| E | **Concept membership** has no deep history in Tushare (`ths_member` current-only, `dc_member` recent-only). Plan pivots to the existing JoinQuant PIT cache. | medium | Right call, or drop historical concept work entirely? |
| F | `fina_mainbz` depth shows 2016+ but is likely a 150-row pagination cap (unverified). | medium | Agree this needs a paginated recount before committing? |

---

## 2. Verified facts (the probes)

### 2.1 Access (tested 2026-06-07)
A strictly-sequential read-only probe of **55 endpoints — 53 not currently ingested + 2 owned positive
controls (`daily`, `top_inst`)** → **54 `ACCESS`, 1 `ACCESS_PARAM` (missing arg only, permission OK),
0 `DENIED`** (both controls returned ACCESS as expected). Method note we want challenged: we
classify any *non-permission* exception (e.g. a missing required param) as "permission passed →
accessible", and only a message containing 权限/积分/permission/不足 as `DENIED`. We retry once on a
rate-limit message; we do **not** reuse the production `_safe_api_call` because it 30s-backoff-retries
3× on any "limit" substring, which would be definitive-answer churn here.

> Honest scope limit: the account is **already** upgraded, so we cannot re-test the 5000 ceiling. The
> deciding fact is "not ingested + now callable", so tier attribution is documentation-sourced; the
> access result is tested.

### 2.2 History coverage (the plan-changing result)
Row counts by representative year-start trading day (per-date endpoints) / full-history date span
(per-stock, Moutai 600519.SH):

| Endpoint | Coverage (verified) | Verdict for IS 2014-20 / OOS 21-26 |
|---|---|---|
| `report_rc` | report_date **2010→2025**; all-market breadth + cap-tilt now verified — see §2.3 | ✅ deep history; broad but **cap-tilted** coverage |
| `repurchase` | ann_date **2010+** (early-yr counts 21→920→capped 2000) | ✅ deep |
| `pledge_stat` | end_date **2014→2026** (950 recs, Moutai); **no `ann_date` — only `end_date`** | ⚠ history from 2014 BUT not auto-PIT-safe (`end_date` = weekly exchange statistic date, not a disclosure/visibility date; needs a date-semantics + publication-lag check before Wave-4 promotion) |
| `top10_floatholders` | end_date **2007→2026** (792 recs) | ✅ deep |
| `fina_audit` | ann_date **2001→2026** | ✅ deep |
| `disclosure_date` | ann_date **2002→2026** | ✅ deep |
| `express` | ann_date **2008→2022** (only 3 recs — sparse per stock) | ✅ deep but event-sparse |
| `fina_mainbz` | end_date **2016→2025** (150 rows — **likely cap**, pre-2016 unverified) | ⚠ verify pagination |
| `stk_surv` | per-date 0 until 2022 (single-day, sparse); ts_code=Moutai → **0 rows** | ⚠ start year **unresolved** |
| `share_float` | Moutai 2007-2009 only (event-sparse per stock) | ⚠ dataset depth unresolved |
| `limit_list_d` | **0 rows 2010-2018**, data 2020+ | ❌ recent-only (no IS) |
| `moneyflow_dc` | **0 until 2024**, then full market | ❌ recent-only |
| `hm_detail` | **0 until 2024** | ❌ recent-only |
| `dc_member` | **0 until a 2025 snapshot** | ❌ no historical membership |

The 0s for `limit_list_d`/`moneyflow_dc`/`dc_member` are **reliable** (every trading day has limit-ups
/ per-stock flow / pre-existing concepts → a 0 means the dataset has no rows that far back, not a
sparse-day miss). The 0s for `stk_surv`/`share_float` are **not reliable** (genuinely sparse events;
single-day or single-megacap probes under-count) — flagged as unresolved, not concluded.

### 2.3 `report_rc` all-market coverage (GPT Finding 1 — resolved, with a caveat)
The §2.2 row was Moutai-only. We re-probed the **full universe** by `report_date` year (month-chunked,
offset-paginated with a dedup-stop; the §2.1 `report_rc` per-call cap is a hard **5000 rows** →
ingestion MUST month-chunk). Result:

| Year | reports | unique stocks | breadth (of listed) | delisted-but-present | Q1 small-cap cov | Q5 large-cap cov |
|---|---|---|---|---|---|---|
| 2014 | 95,186 | 2,123 | **90.2%** | 148 | 52.9% | 98.5% |
| 2018 | 197,740 | 2,409 | 74.1% | 111 | 34.1% | 95.4% |
| 2022 | 260,766 | 3,085 | 66.1% | 26 | 22.2% | 94.3% |
| 2024 | 247,863 | 3,349 | **62.8%** | 9 | 30.4% | 94.4% |

Three load-bearing conclusions:
1. **Broad & dense, not a megacap toy** — 2.1k–3.3k unique covered names/yr, 95k–261k reports/yr.
2. **Delisted names ARE retained** (148/111/26/9 ever-delisted stocks present in old years; the count
   falls only because fewer *recently*-covered names have delisted yet). This substantially defuses the
   coverage-survivorship-by-omission hazard (Q-D1b) — the panel is not reconstructed from currently-
   listed firms. (It does NOT prove the vendor never *removed* a dropped-coverage analyst row — that
   restatement question is still open.)
3. **Strong size selection bias** — large-caps ~94–98% covered every year; small-caps only ~22–53%,
   and headline breadth falls 90%→63% as the post-2019 IPO wave outgrew analyst coverage (absolute
   coverage still *grew* 2123→3349). **Implication for factor design:** a `report_rc` cross-sectional
   factor effectively ranks only the covered (larger/more-liquid) sub-universe; coverage is NOT
   missing-at-random (its absence is itself informative). The Wave-1A pilot must (a) define the signal
   on the covered sub-universe, (b) neutralize against size hard, and (c) test whether incremental IC
   survives *within* size buckets, not just pooled.

Pagination/ingestion note (no silent caps): `offset_works=True`, `capped_under_months=[]` for all 4
years — the corrected probe captured each year fully. The earlier (broken) single-page probe reported
49/25/21/19% breadth; those numbers were a first-5000-rows artifact and are discarded.

### 2.4 Size-selection — RESOLVED (the design question Q-D1 raised)
`scripts/report_rc_size_bias_diagnostic.py` (sandbox, no forward returns — that IC study is Wave-1A).
For 3 IS-window cross-sections we measured coverage∼size, signal∼size, and within-size dispersion of a
consensus **rating** signal (ordinal map; near-zero `rating_score` ⇒ neutral):

| As-of | covered/listed | coverage% by size decile (1 small → 10 large) | rankcorr(n_analysts, size) | rankcorr(rating, size) | rating std within-decile / overall |
|---|---|---|---|---|---|
| 2016-06-30 | 2046/2585 | 30 61 64 70 72 80 82 85 88 **97** | 0.433 | **0.015** | 0.317 / 0.322 |
| 2018-06-29 | 2000/3325 | 10 25 36 47 50 66 72 80 88 **95** | 0.575 | **0.169** | 0.301 / 0.282 |
| 2019-12-31 | 1776/3742 | **8** 11 22 32 44 46 59 74 80 **94** | 0.589 | **0.123** | 0.312 / 0.305 |

**Verdict (three-part):**
1. **Coverage is strongly size-selected** (and worsening: small-cap decile 30%→8%) → a `report_rc`
   factor must be defined on the **covered sub-universe**; it cannot rank the whole market, and absence
   of coverage is informative, not missing-at-random.
2. **Intensity features (analyst count) ARE a size proxy** — rankcorr 0.43–0.59 → do NOT build a
   standalone factor on coverage count / n_analysts; it is ~half a size bet.
3. **Direction features (consensus rating, and by extension revision) are NOT a size bet** — rankcorr
   0.01–0.17, and within-size-decile dispersion ≈ overall dispersion → **a pooled rating/revision
   factor is NOT unsound-due-to-size**; size-neutralization is cheap hygiene and within-size ranking
   costs ~nothing. This is the green light for the Wave-1A *direction/revision* signal, with the
   universe restricted to covered names.

Caveat (honest): the ordinal rating map left a minority of rows unmapped (3.4k/8.7k/8.5k — English
broker labels + niche tags); `rating_score` is computed on mapped rows only. The size-correlation
conclusion is robust to this (no mechanism by which the unmapped minority flips a ~0.0–0.17 corr), but
the production signal should extend the map.

### 2.5 Backfill canary — BASELINED (the report_date PIT test Q-D1a)
`scripts/report_rc_backfill_canary.py` snapshots `report_rc` over a trailing window with per-row
content hashes; a `diff` mode flags the three smoking guns (old-dated rows appearing only in the newer
snapshot = the decisive PIT violation; `report_date` drift; payload restatement). **Baseline captured
2026-06-08:** 64,966 rows / 2,743 stocks over 2026-02-08→06-07; **ingestion-lag observation = 1 day**
(freshest `report_date` 2026-06-07 vs today 2026-06-08). The 1-day leading-edge freshness is consistent
with — but does NOT prove — PIT-safety of a `strictly_next_open_trade_day(report_date)` anchor; the
decisive test is the `diff` after a 2nd snapshot ≥1 week out (whether old-dated rows get backfilled
into the already-observed window). Store + manifest under `data/external/report_rc_canary/`.

**Diff machinery validated (same-day control, 2026-06-08):** a 2nd same-day snapshot diffed against the
baseline returned **(1) backfilled = 0, (2) report_date drift = 0**, (3) payload restatement = 26
(intraday vendor micro-updates — informational only; the verdict keys solely on (1)+(2), so this does
not fail it). The `diff` path runs end-to-end. A `recheck` subcommand now chains snapshot→auto-diff→
verdict in one command. **The decisive 2nd reading is scheduled (local, one-time) for 2026-06-15**; if
metric (1) > 0 it sizes an ingestion-lag buffer from the backfilled rows' date gaps, else the
`strictly_next_open_trade_day` anchor is confirmed sufficient.

---

## 3. The plan, as revised by §2.2–§2.5

**Original plan** (pre-coverage-probe) proposed 4 waves: (1) analyst/earnings, (2) sentiment/flow,
(3) concept membership, (4) governance/context. The coverage probe forces this revision:

- **Wave 1 — analyst & earnings-timing — SURVIVES, now the only clearly-justified near-term wave.**
  `report_rc` (deep) + `express`/`disclosure_date`/`fina_audit` (deep) + `fina_mainbz` (pending the
  pagination check). `express`/`disclosure_date`/`fina_audit` carry `ann_date` → disclosure-anchored,
  reuse the existing PIT-ledger machinery. **`report_rc` is NOT yet PIT-verified** (per GPT Finding 2):
  it is treated **quarantine-until-tested**, with the intended anchor
  `effective_date = strictly_next_open_trade_day(report_date)` + a forecast-age expiry rule (no
  infinite carry-forward); promotion waits on the §4 Q-D1 PIT checks. Correcting the earlier "all
  PIT-clean" overclaim.
- **Wave 4 — governance/risk — PARTIALLY SURVIVES.** `repurchase` (2010+), `pledge_stat` (2014+),
  `top10_floatholders` (2007+) all deep → usable as event/risk overlays across the window.
- **Wave 2 — sentiment/flow — DEMOTED.** `limit_list_d`/`moneyflow_dc`/`hm_detail` are recent-only.
  They can support at most a **2021/2024-onward forward-or-OOS-style study**, never the standard
  IS-2014-20 screen. Defer until either (a) we accept a short-window protocol, or (b) enough live
  history accrues going forward.
- **Wave 3 — concept membership — RE-ROUTED.** Tushare offers no deep history. The system maintains a
  JoinQuant PIT cache, but **today it covers index-membership / valuation / ST / paused only — NOT
  concept membership** (GPT Finding 4). So historical concept/theme membership, if pursued, requires
  **extending the JQ PIT cache with a new concept-membership schema + refresh notebook** (schema/
  version bump), not reusing what's there. Tushare `ths_index`/`ths_daily` (index *prices*) may still
  be useful; historical membership is the blocked part.

---

## 4. Claims we want challenged + honest open risks

**Q-C1 (flagship soundness — most important).** Is `report_rc` worth the toll, or are we sunk-cost
rationalizing after the 0/8 new-data screen? Our thesis: analyst consensus carries information
*orthogonal* to price/fundamentals/flow (EPS-revision, dispersion, rating change, target-implied
return, SUE-vs-consensus), and orthogonality is the one axis the 8 rejected moneyflow-derived factors
did **not** add (they were correlated with the price/flow block we'd already screened). Counter-case
we can't dismiss: A-share sell-side consensus is optimistically biased, herding, and revision factors
are among the most-arbitraged signals globally — the alpha may be fully priced. **Is the orthogonality
argument a real edge or a just-so story?** What single test would most cheaply falsify it before we pay
the full ingestion cost?

**Q-D1 (PIT hazard).** `report_rc` exposes only `report_date` — there is no separate "row-entry /
first-visible" timestamp. We would anchor visibility on `effective_date =
strictly_next_open_trade_day(report_date)` (strict next-open, per the project's PIT anchor) +
`Ref(...,1)`. Status of the three sub-risks: (a) **backfill/restate** of `report_date` — still
**unverified** (the most dangerous, since it silently breaks PIT); (b) **coverage-survivorship** —
**substantially defused by §2.3** (delisted names are retained; 148 present in 2014), though
vendor-side *removal* of dropped rows is still unproven; (c) **stale-forecast carry-forward** — a
policy choice, to be fixed by a forecast-age expiry (e.g. drop a forecast N months after its
`report_date`, and/or once the target `quarter` is realized). **Size-selection (§2.4) — now resolved:** coverage is
strongly size-selected, but the *direction* signal (rating/revision) is near-orthogonal to size
(rankcorr 0.01–0.17) with full within-size dispersion → a pooled direction factor on the covered
sub-universe is sound; only *intensity* (analyst-count) features are size proxies and are dropped.
**Backfill (§2.5) — baselined:** canary live, ingestion lag observed at 1 day; the decisive diff awaits
a 2nd snapshot ≥1 week out. **Remaining genuinely-open for you (GPT):** of (a) `report_date`
backfill/restate vs (b) vendor-side *removal* of dropped-coverage rows — which is the more dangerous
residual, and is a 1-trading-day `strictly_next_open_trade_day` buffer sufficient, or do you want the
canary to drive an empirically-measured ingestion-lag buffer (e.g. anchor at the observed 95th-pctile
lag) before any Wave-1A result is trusted?

**Q-B1 (recent-only cost/benefit).** Given Wave-2/3 data cannot run the standard IS protocol, is it
ever worth paying the full governance toll now for `limit_list_d`/`moneyflow_dc` to enable a
2021/2024+ forward study — or is the disciplined move to **not ingest** until the history matures (and
revisit in N years)? Note the strategic pull: limit-board/打板 is a genuinely *different style* from
our long-only value/quality book, which is the diversification we want — but only ~2-5 yrs of history
exists.

**Q-E1 (concept membership routing).** We propose sourcing historical concept membership from the
existing JoinQuant PIT cache rather than Tushare. Is that the right call, or does the
survivorship/lookahead difficulty of *any* concept-membership backtest (concepts are
created/renamed/back-dated by data vendors) make historical concept-rotation research not worth it at
all — i.e., treat concepts as a *live-forward-only* signal?

**Q-F1 (verification gaps).** Before committing, we will: (1) paginate `fina_mainbz` to confirm
pre-2016 depth; (2) re-probe `stk_surv`/`share_float` with date-range counts (not single-day/single-
megacap) to resolve start years. Are there other coverage/PIT checks you'd require **before** the first
fetch script is written?

**Q-G1 (omissions).** Did our 55-endpoint probe set miss anything high-value for an A-share factor
system? We deliberately deferred `stk_mins` (intraday paradigm), `cyq_chips` (redundant w/ owned
`cyq_perf`), `stk_factor_pro` (261 cols; we compute our own factors), `cb_daily`/`fund_nav` (other
asset classes), and connect aggregates (`hsgt_top10` etc.; we own per-stock `hk_hold`). Agree, or is
one of these mis-deferred?

**Q-H1 (sequencing).** Proposed: ship **only Wave 1** next (`report_rc` first, standalone consensus
panel + pre-registered revision/dispersion/SUE factor family), with Wave-4 governance overlays as a
fast-follow, and Waves 2/3 explicitly parked. Is that the right and sufficient near-term scope?

---

## 5. Consolidated questions for GPT

1. **(C1)** Is `report_rc` a real orthogonal edge or sunk-cost rationalization post-0/8? Cheapest
   falsification test before full ingestion?
2. **(D1)** Of the three `report_date` PIT hazards (backfill/restate, coverage-survivorship, stale
   carry-forward), which is most dangerous and how do we anchor/decay against it?
3. **(B1)** Pay the toll now for recent-only sentiment/flow (2021/2024+ forward study), or defer until
   history matures?
4. **(E1)** Route historical concept membership through the JoinQuant PIT cache, or abandon historical
   concept research as inherently survivorship-broken (live-forward only)?
5. **(F1)** Required coverage/PIT checks before the first fetch script?
6. **(G1)** Any high-value endpoint we wrongly deferred?
7. **(H1)** Is "Wave 1 only, report_rc first, Waves 2/3 parked" the correct near-term sequencing?

---

*Method honesty: single-day per-date probes under-count sparse events; 2000-row returns are pagination
caps, not true counts; per-megacap depth probes (Moutai) under-represent event-sparse endpoints
(`share_float`, `stk_surv`). All conclusions marked ⚠ are explicitly unresolved, not asserted.*
