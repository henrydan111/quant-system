# Report-Factor Expansion Plan v3 (`report_rc` → factors, the COMPLIANT way)

*2026-06-08. v3 = v2 + GPT 5.5 Pro **round-2** review, all checkable claims re-verified against the live
code/data. Verdict adopted (both rounds): **GO-with-conditions for a no-alpha P1 plumbing slice; NO-GO
for full rebuild / screen / promotion.** This plan REDOES the quarantined hand-rolled pilot through the
sanctioned backend (CLAUDE.md §3.2 / src/system.md §0): a new dataset becomes a factor ONLY after
`pit_backend` materializes it into the PIT ledger + Qlib provider and `field_status.yaml` registers it;
factors are `Ref(...)`-guarded Qlib expressions via `compute_factors` — never hand-rolled from raw parquet.*

## v3 changelog — round-2 conditions (verified, then folded in)
- **T5 (CRITICAL) — ledger collapse:** `build_ledger` (pit_backend L2060-2083) special-cases
  forecast/dividends/stk_holdertrade then **falls back to `(ts_code, end_date, disclosure_date)`**.
  `report_rc` has NO `end_date` → it would key on `(ts_code, report_date)` and `collapse_duplicate_versions`
  would **collapse every analyst×quarter row into one** (the ~99% loss the stk_holdertrade branch comment
  L2069-74 exists to prevent). → **report_rc needs its OWN explicit `elif` key branch** (§2). *Verified.*
- **T6 — tie-break:** `_src_file`/`_src_ordinal` are injected during normalize but **stripped before the
  normalized parquet write** (CLAUDE §6.3 P0-4). v2's ordering key can't use them → P1 must persist durable
  `source_file`/`source_row_ordinal` OR use a stable content-hash tie-break (§3). *Verified.*
- **T7 — `tp` is NOT target price:** verified on the data — `tp` is predicted **total profit** (万元,
  median 128,700, range −3.9M…52M, can be negative); the real target price is **`max_price`/`min_price`**
  (price-scale 4–408). The pilot's "target-implied = tp/close−1" was meaningless. Correct §8. *Verified.*
- **T8 — `create_time` absent:** my download used the default 21-col fetch (no `create_time`); Tushare
  `report_rc` exposes `create_time` (TS更新时间, nightly 19:00-22:00). P1 must **re-fetch with
  `fields=…create_time`** and use it as the vendor-observed time (§5). *Verified (column absent on disk).*
- **Formula fix:** v2's `Max(Sum(revision_count,W),MIN_N)` is denominator *clamping*, not an evidence
  *gate*, and omits null-safe zero-fill → replaced with `If(eligible, raw, NaN)` + `Sum(If(IsNull,0,…))` (§3).
- Plus: FY1-boundary **sidecar** (§4), `n_active` live-definition + `eps_change_epsilon` + robust
  `eps_fy1_dispersion` (§3/§8), the `normalized_analyst_id` P1 rule (§3), and the **9-item P1 acceptance
  gate** (§9).

## 0. The prior (tainted) pilot does NOT inform go/no-go
`eps_diffusion` "strong + tradeable" was produced by a non-compliant raw-read + hand-rolled-PIT path with
no provider-bounds masking → **untrusted hypothesis, schema/method reference only.** It must be
re-derived through the compliant pipeline (Phase 5) before any claim stands.

## 1. GPT review — verified repo traps (these break a naive build)
| # | Trap (GPT) | Verified in code |
|---|---|---|
| T1 | A `DatasetSpec` is NOT enough — ledgers build only for configured sets | `build_ledgers` gates on `PERIODIC_LEDGER_DATASETS` (pit_backend.py L2105); `stk_holdertrade` ∈ `PHASE3_DATASETS` L86 + `PERIODIC_LEDGER_DATASETS` L101 → **report_rc must be added to BOTH** |
| T2 | Do NOT reuse `EVENT_LIKE_DAILY_FIELD_PREFIX` | `test_prefix_keys_match_event_like_dataset_set` + `test_every_event_like_dataset_has_a_prefix_entry` force prefix-map keys == `EVENT_LIKE_DAILY_DATASETS` → adding report_rc there would route it through the generic daily-fact path. **Custom materializer writes `report_rc__*` names directly** (как `_materialize_stk_holdertrade`); register the `$report_rc__` prefix in `field_status.yaml`. |
| T3 | Mirror the explicit hook, not just the style | `materialize_provider` hard-codes `self._materialize_stk_holdertrade(...)` (L2829) → add an explicit `written["report_rc"] = self._materialize_report_rc_consensus(...)` hook |
| T4 | `Count(cond,N)` is broken in this repo | use `Sum(If(cond,1,0),N)`, never `Count(...)` (matches the prior production `operators.py` fix) |

## 2. Architecture mapping (corrected)
| Step | Mechanism | File / anchor |
|---|---|---|
| Dataset contract | `DatasetSpec(kind="event_periodic", ann_date_column="report_date")` **+ add `report_rc` to `PHASE3_DATASETS` and `PERIODIC_LEDGER_DATASETS`** | `pit_backend.py` L82/L88/L240 |
| PIT ledger | **explicit `elif dataset_name=="report_rc"` key branch in `build_ledger`** (T5) keyed `(ts_code, report_date, normalized_analyst_id, quarter)` so each analyst×quarter row survives `collapse_duplicate_versions`; `effective_date` per §5 | `build_ledger` L2042/L2080 + `strictly_next_open_trade_day` L659 |
| Daily materialization | custom `_materialize_report_rc_consensus` writing `report_rc__*` PRIMITIVE bins directly; **explicit hook in `materialize_provider`** | precedent `_materialize_stk_holdertrade` L2340 / hook L2829 |
| Namespace | written directly by the materializer; register `$report_rc__` prefix in registry (NOT via `EVENT_LIKE_DAILY_FIELD_PREFIX`) | `config/field_registry/field_status.yaml` |
| Factor defs | Qlib exprs over primitives, `Ref(...,1)`-guarded, `Sum(If(...))` not `Count` | `factor_library/catalog.py`+`operators.py` |
| IS screen / OOS | `factor_lifecycle` (draft→candidate) → single sealed-OOS | `research_orchestrator` |

## 3. The materializer — A2′ (atomic primitives; Qlib does the windowing)
**Decision (GPT-adjudicated): A2′, not A1, and the field is EVENT-FLOW revision breadth, not
"active-latest consensus".** A windowed cross-analyst aggregate needs per-analyst stateful logic Qlib
can't express; but we minimize that to per-event primitives and push windowing to Qlib operators. The
honest claim — per GPT — is **event-flow EPS-revision breadth**, NOT one-vote-per-analyst consensus
(which would require backend state/cancellation primitives; deferred, or A1-only, as a later refinement).

**Why the v1 A2 formula was wrong (GPT, accepted):** `Sum($active,W)` is analyst-days not coverage
(invalid denominator); `Sum($up,W)` counts events and does NOT dedupe "latest per analyst within W".

**Materializer emits per `(qlib_code, effective_date)` (NaN on no-event days, never zero-filled):**
```
report_rc__eps_up, report_rc__eps_dn, report_rc__eps_same   # per-analyst revision direction events
report_rc__eps_revision_count                               # # of directional revisions that day
report_rc__eps_revision_sum, report_rc__eps_revision_mean   # magnitude (Δ vs that analyst's prior)
report_rc__eps_fy1_mean, report_rc__eps_fy1_dispersion      # level + cross-analyst std/|mean|
report_rc__n_active_analysts                                # state: # analysts with a live FY1 view
report_rc__coverage_init, report_rc__coverage_change        # first-coverage / Δcoverage events
report_rc__days_since_last_forecast, report_rc__mean_forecast_age_days
```
**Per-analyst revision state machine (the stateful part the materializer owns):** for each
`(qlib_code, normalized_analyst_id, target_fy)`, compare a forecast ONLY to that analyst's previous
forecast already visible by `effective_date`. **Deterministic ordering key (T6 — `_src_*` are stripped
before normalized write, so they're unavailable):**
`qlib_code, normalized_analyst_id, target_fy, effective_date, report_date, create_time, <stable
content-hash of (org,author,quarter,eps,report_title)>` — persist durable provenance OR the content hash.
**An EPS revision needs a tolerance `eps_change_epsilon`** (exact float compare would turn rounding into
revisions): `up/dn/same` classified by `Δeps` vs `±epsilon`. **The first forecast for a new analyst / new
`target_fy` is `coverage_init`, NOT an up/down revision.** Same-day duplicates resolved deterministically.
**`n_active_analysts` needs a LIVE definition** (load-bearing — it's a gate): "analysts whose latest
visible forecast for the current FY1 is not yet expired", expiry = fiscal-roll OR a predeclared age TTL.

**`normalized_analyst_id` (P1 must implement, not defer — GPT rule):** `org_norm` (NFKC, trim, collapse
ws/punct, drop predeclared legal-suffix noise) `+ "::" +` sorted `author_norms` (split on `/ & ， 、 ; ；`,
NFKC, trim); `org_only` fallback flagged; emit `analyst_id_quality ∈ {exact_author, multi_author,
org_only, missing_org}`. Multi-author = team identity in P1.

**The factor (Qlib expression, event-flow breadth — MASK, don't clamp; null-safe; `Sum(If)` not `Count`):**
```
up_W = Sum(If(IsNull($report_rc__eps_up),0,$report_rc__eps_up), W)
dn_W = Sum(If(IsNull($report_rc__eps_dn),0,$report_rc__eps_dn), W)
n_W  = Sum(If(IsNull($report_rc__eps_revision_count),0,$report_rc__eps_revision_count), W)
eligible = (n_W >= 3) & (Ref($report_rc__n_active_analysts,1) >= 2)     # evidence GATE, not clamp
eps_rev_breadth_W = Ref( If(eligible, (up_W - dn_W)/n_W, NaN), 1 )      # repo-compatible boolean nesting TBD
```
`W ∈ {20,60,120}` is a factor hyperparameter (no re-materialize). The gate returns **NaN** (not a clamped
small value) → the screen MUST report eligibility coverage by date/sector/size/coverage bucket (NaN
silently shrinks the cross-section). `n_active_analysts` is carried as STATE by the materializer.

## 4. FY1 target = first-visible annual ACTUAL (auditable sidecar, no future leakage)
For stock S, day T: `target_fy` = the nearest annual fiscal year whose **annual actual has not yet
become visible by T** (visibility = first `effective_date` the annual-actual appears in the sanctioned
PIT statement ledgers, NOT eventual availability). **P1 materializes an auditable sidecar
`report_rc_fy1_boundary.parquet`** (`qlib_code, fiscal_year, actual_source_dataset, actual_field,
annual_end_date, actual_first_visible_effective_date, source_row_id, boundary_status`) rather than opaque
in-materializer cross-ledger lookups; the report materializer consumes it. This makes restatement / missing-
annual / income-vs-indicators-timing behavior testable. **Never classify `YYYYQ4`→`(YYYY+1)Q4` as an EPS
revision — that is a target change** (`coverage_change`/target-init). The parity oracle (§6) must
INDEPENDENTLY rebuild this boundary from test inputs — it must NOT consume the materializer's sidecar.

## 5. PIT anchor — request `create_time`, else a fixed non-tunable lag (T7/T8); quarantine until canary
Tushare `report_rc` exposes **`create_time`** (TS更新时间; nightly 19:00-22:00) — NOT in the default
21-col fetch, so **P1 re-fetches with `fields=…create_time`** and persists it. Anchor:
`effective_date = max( strictly_next_open_trade_day(report_date),
strictly_next_open_trade_day(create_time) )` — implementable via `f_ann_date_column="create_time"` so the
existing `disclosure_dates()` max() does it, OR a custom report_rc effective-date resolver. **If historical
raw truly lacks `create_time`,** use a single non-tunable constant `REPORT_RC_VENDOR_LAG_OPEN_DAYS = 2`
(data-infra config/code, NO per-window/per-factor override; reducible later only via a documented vendor-lag
audit, never via IC). `Ref(...,1)` does NOT fix vendor backfill. Keep the field **quarantined** until the
backfill canary proves no material lag (registry fails closed — the desired gate).

## 6. Test/parity strategy — 3 layers + negative canaries (NOT just parity)
Parity alone proves implementation math, not PIT correctness. Required:
1. **Primitive-bin parity** — ledger rows → independent pandas primitives vs provider `$report_rc__*`.
2. **Expression parity** — provider primitives → pandas rolling expr vs the Qlib factor (via
   `qlib_windowed_features`, never raw files).
3. **Negative PIT canaries** (the decisive layer) — inject a future report with a huge EPS revision, a
   same-day-anchor row, duplicate same-day reports, a fiscal-year roll, and a vendor-backfill row; assert
   **none change any feature dated before its `effective_date`.** Adversarial fixture: 3-analyst case
   (one revises twice in W, one once, one stale) forcing the event-flow-vs-active-latest declaration.

## 7. Pre-registered kill rule (Risk-1) — before any compliant screen
Write a `report_rc` research manifest (hypotheses, windows {20,60,120}, denominators, neutralizations,
thresholds, allowed negative controls) BEFORE screening; reject any result using fields/windows not in
it. Pass bar (lifecycle floor + anti-mining): `|rank_icir| ≥ 0.10` IS, yearly sign-consistency ≥ 0.70,
**survives industry/size/coverage neutralization**, not concentrated in one year/sector, min
coverage/revision-count gate met, **no post-hoc targetprice/rating substitution if EPS fails.** Kill
rule: if the lead EPS-revision-breadth family fails, promote NOTHING beyond quarantine/candidate unless a
NEW hypothesis is registered before testing. A null is a valid result (the primitives may still serve as
ML inputs / negative controls).

## 8. Candidate fields — small pre-registered family; defer the rest
Materialize the §3 primitive family. **Field-meaning correction (T7):** Tushare `tp` is predicted **total
profit** (万元, can be negative — NOT a price); the real **target price is `max_price`/`min_price`**. A
target-implied-return feature (if pursued later) = `mean(max_price/min_price)/close − 1`, NOT `tp/close`;
defer it (sparse + needs sanity bounds). **`eps_fy1_dispersion = std/|mean|` is unstable near zero/negative
EPS** → use an EPS floor / median denominator / unscaled std or MAD, OR keep `eps_fy1_dispersion`
quarantined until a robust definition is registered. **Defer/quarantine:** `rating_diffusion` (2% coverage,
dead — negative control only); analyst/org quality scores (circularity unless frozen ex-ante). Sparse fields
stay NaN on no-event days; factors decide no-event→0 via `Sum(If(IsNull,0,...))`.

## 9. Phases & gates (tightened)
- **P0 — pre-register + (this) design review DONE.** Freeze: event-flow semantics, the §3 primitives,
  FY1 first-visible rule, the anchor, the kill manifest. *Gate: design GO ✓ (with conditions).*
- **P1 — no-alpha PLUMBING slice (first PR).** 1-2 tickers, 1-2 years, quarantined primitive bins only,
  NO screen. **Acceptance = deterministic rebuild + §6 PIT canaries + provider parity — NOT IC.**
  **P1 MUST include (GPT round-2 mandatory gate):**
  1. explicit `report_rc` `build_ledger` key branch (T5) — **+ a test asserting ledger row-count ==
     expected analyst×quarter rows on a 2-org / 2-author / 3-quarter same-date fixture** (fails on the
     generic key, passes only after the branch);
  2. `create_time` requested/persisted (re-fetch), OR the fixed `REPORT_RC_VENDOR_LAG_OPEN_DAYS=2` applied;
  3. durable deterministic tie-break provenance OR a stable content hash (T6);
  4. `normalized_analyst_id` golden tests (Chinese punctuation, full/half-width, author-order, missing
     author, two authors at one broker) + `analyst_id_quality` share reporting;
  5. null-safe rolling expression / parity fixture (no-event, 1-event→NaN, 3-event→ratio), even if catalog
     factors wait until P4;
  6. the live/active definition for `n_active_analysts` + a stale-analyst test;
  7. `$report_rc__` registered **quarantine** in `field_status.yaml`;
  8. NO `EVENT_LIKE_DAILY_FIELD_PREFIX` reuse (write names directly);
  9. explicit `materialize_provider` hook mirroring `stk_holdertrade`.
  Plus the wiring: `DatasetSpec` + add to `PHASE3_DATASETS` + `PERIODIC_LEDGER_DATASETS`.
- **P2 — full primitive family + parity/canary suite green on a small basket.** *Gate: all §6 tests.*
- **P3 — full provider rebuild (§13 risky — basket-first, confirm)** + coverage/parity audit + (canary
  permitting) quarantine→approved.
- **P4 — catalog factors** (`eps_rev_breadth_{20,60,120}`, `Ref`-guarded, `Sum(If)`); PIT-safety lint.
- **P5 — compliant `factor_lifecycle` IS screen** against the §7 manifest (REPLACES the tainted pilot —
  confirms or kills `eps_rev_breadth`). → draft→candidate by marginal/orthogonal IC.
- **P6 — sealed OOS (candidate→approved) OR ML features** read compliantly via `compute_factors`.

## 10. Resolved by round-2 / remaining calls
- **Event-flow as primary** — RESOLVED: ship event-flow for P1 (honest, valid Qlib math); active-latest
  one-vote consensus deferred (needs state/cancellation primitives or A1). Requires coverage-neutralization
  + contributor-concentration diagnostics before any screen result is trusted.
- **Vendor time** — RESOLVED to a path: request `create_time` (§5); fixed `=2` open-day lag only if absent.
- **`normalized_analyst_id`** — RESOLVED to a P1 rule (§3); still the most load-bearing input → golden tests.
- **Still open:** the exact repo-compatible Qlib boolean/nesting for the `If(eligible, ratio, NaN)` mask
  (must pass the PIT-safety static lint, not just read well); the `eps_fy1_dispersion` robust definition
  (floor/MAD) before that field leaves quarantine.
