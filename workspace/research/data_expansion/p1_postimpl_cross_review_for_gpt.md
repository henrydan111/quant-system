# Post-Implementation Code Review for GPT 5.5 Pro — report_rc P1 plumbing slice

**Date:** 2026-06-08.
**Repository:** https://github.com/henrydan111/quant-system (public). **Branch:** `report-rc-p1-plumbing`.
**Scope:** review the ACTUAL CODE of the P1 no-alpha plumbing slice you signed off in design (round-3
"P1-CODING GO-WITH-NITS"). This is an implementation review, not a design re-litigation — the A2′
event-flow architecture, the ledger key, the create_time anchor, the kill-rule, etc. are settled. Find
bugs: PIT leakage, incorrect event-flow logic, determinism gaps, performance traps at full scale, edge
cases, and test-coverage holes. P1 is deliberately no-alpha (no screen, no full rebuild) — judge it as
plumbing, accept-by-canaries/parity/determinism (not IC).

**Read (raw):**
- **The full code diff (424 additive lines, 3 files):**
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-p1-plumbing/workspace/research/data_expansion/p1_report_rc_code.diff
- The implemented module (for surrounding context — `build_ledger` ~L2070, `_materialize_report_rc_consensus`, `_write_feature_series`, `materialize_provider` hook):
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-p1-plumbing/src/data_infra/pit_backend.py
- Tests:
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-p1-plumbing/tests/data_infra/test_report_rc_ledger.py
- The signed-off design (context only):
  https://raw.githubusercontent.com/henrydan111/quant-system/report-factor-expansion-review/workspace/research/data_expansion/report_factor_expansion_plan.md

## What was implemented (the diff)
1. **`DatasetSpec("report_rc")`** — `event_periodic`, `ann_date_column="report_date"`,
   `f_ann_date_column="create_time"` (so `disclosure_dates()` → `max(report_date, create_time)` →
   `strictly_next_open_trade_day` gives the anchor; `create_time` is a vendor timestamp parsed by
   `normalize_date_series`'s flexible fallback). Added to `PHASE3_DATASETS` + `PERIODIC_LEDGER_DATASETS`.
   `duplicate_key_columns` deliberately UNSET so normalize doesn't collapse.
2. **Custom `build_ledger` branch** (`elif dataset_name == "report_rc"`) — computes
   `normalized_analyst_id` then keys on `(ts_code, report_date, normalized_analyst_id, quarter)`. Exact
   dups merge via `collapse_duplicate_versions`' existing content-hash tie-break (the `_src_*` columns are
   stripped at normalize, so no bespoke hash was added — the existing fallback covers determinism).
3. **`normalized_analyst_id()`** helper — NFKC org + sorted author-team tokens.
4. **`_materialize_report_rc_consensus`** — emits the P1 subset `$report_rc__{eps_up, eps_dn,
   eps_revision_count, n_active_analysts}`:
   - revisions: per `(qlib_code, normalized_analyst_id, quarter)`, `delta = eps − eps.shift(1)`;
     up/dn by `±EPS_REVISION_EPSILON (1e-4)`; first forecast (prev NaN) is coverage-init, not a revision;
   - `n_active_analysts`: per analyst, each forecast keeps them live for
     `REPORT_RC_ACTIVE_TTL_OPEN_DAYS (120)` trading days; per-analyst intervals merged, summed per day
     via a diff array; `NaN` before the stock's first coverage;
   - event bins `NaN` on no-event days; written DIRECTLY as `report_rc__*` (not via
     `EVENT_LIKE_DAILY_FIELD_PREFIX`); aligned to the reference `close.day.bin` by `_write_feature_series`.
5. **Explicit `materialize_provider` hook** + `$report_rc__` registered **quarantine** in `field_status.yaml`.
6. **Tests (7):** ledger row-preservation/anti-collapse, create_time anchor, ledger determinism,
   materializer event-flow primitives + a no-lookahead canary (future-dated row dropped), build-selection
   (hook fires), real Qlib bin round-trip + byte-determinism, analyst-id normalization. 123
   pit_backend/field-registry/namespace/approval regression tests still green.

## Review questions (find bugs)
**Q1 — event-flow correctness.** Is the per-`(code, analyst, quarter)` `eps.shift(1)` revision
classification correct under the sort key `["qlib_code","normalized_analyst_id","quarter","effective_date"]`?
Any way two forecasts with the SAME `effective_date` (e.g. same-day duplicates that didn't fully merge, or
two reports by one analyst that map to the same next-open) produce a wrong/ambiguous `delta`? Should the
sort include a stable secondary key (report_date / create_time) before `shift(1)`?

**Q2 — `n_active_analysts` interval logic.** The merge uses `a <= merged[-1][1] + 1` and writes
`diff[a]+=1 ; diff[b+1]-=1` with `b = min(p+ttl, n_cal-1)`. Is the off-by-one correct (inclusive
`[a,b]`)? Does `b+1` ever exceed `n_cal` (the diff array is `n_cal+1`, so index `n_cal` is the last valid
— OK?) Is "live for 120 days after EACH forecast, merged across an analyst's forecasts" the intended
semantic, and does merging across DIFFERENT quarters for the same analyst over-count a single analyst
(it shouldn't — one analyst = one unit of coverage regardless of how many quarters they forecast)?

**Q3 — PIT leakage.** `ledger.dropna(subset=["effective_date"])` runs before both the revision and
n_active computations. Is that sufficient to guarantee no row with a NaT/future effective_date influences
any earlier day? The no-lookahead test only covers the "effective beyond calendar → NaT" case — what
other leakage paths should a canary cover (a row whose effective_date is valid but whose create_time
implies later availability; a same-day-anchor; a within-window backfill)?

**Q4 — determinism at scale.** We rely on `collapse_duplicate_versions`' `_row_content_hash` tie-break
(the `_src_*` columns are stripped). Is that hash stable across machines/pandas versions for report_rc's
payload (Unicode org/author, float eps, the create_time timestamp string)? The determinism test rebuilds
in-process — would a cross-machine rebuild also be byte-identical?

**Q5 — performance at full scale.** Full history is ~2.87M ledger rows × ~5,600 stocks. Concerns:
`active_by_code` does a `groupby(["qlib_code","normalized_analyst_id"]).apply(sorted set)` over all rows;
the per-symbol Python loop builds a `n_cal+1` diff array (~4,400) per stock; `normalized_analyst_id` is a
per-row Python list-comp. Will this be acceptable (minutes), or are there obvious vectorization wins /
memory traps before the full build?

**Q6 — edge cases.** Stocks with forecasts but all-NaN `eps`; an analyst with a single forecast (only
coverage-init, no revision events — does the stock still get `n_active`?); `quarter` missing/malformed;
`create_time` present but `report_date` after it; the `events` groupby including coverage-init days as
`count=0` rows (is `0` vs `NaN` on a forecast-but-no-revision day the right convention for the downstream
`Sum(If(IsNull,0,…))` factor?).

**Q7 — test adequacy.** What's the highest-value test still missing for a plumbing slice (before the full
rebuild)? Candidates: same-day-anchor canary, fiscal-roll classification, vendor-backfill canary, an
all-NaN-eps stock, a single-forecast stock's `n_active`. Which would you require before merge?

**Q8 — overall.** MERGE / MERGE-WITH-NITS / CHANGES-REQUIRED for the P1 plumbing branch, and the single
most important fix or test to add first. (Full rebuild / screen remain separately gated NO-GO.)
