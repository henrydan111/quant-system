# Report-Factor Expansion Plan v2 (`report_rc` → factors, the COMPLIANT way)

*2026-06-08. v2 = v1 + the GPT 5.5 Pro design cross-review, **every repo-specific trap verified against
the live code** (line cites below). Verdict adopted: **GO-with-conditions for a no-alpha plumbing slice;
NO-GO for full rebuild / screen / promotion** until the semantics + wiring + canaries below are resolved.
This plan REDOES the quarantined hand-rolled pilot through the sanctioned backend (CLAUDE.md §3.2 /
src/system.md §0): a new dataset becomes a factor ONLY after `pit_backend` materializes it into the PIT
ledger + Qlib provider and `field_status.yaml` registers it; factors are `Ref(...)`-guarded Qlib
expressions via `compute_factors` — never hand-rolled from raw parquet.*

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
| PIT ledger | `data/pit_ledger/report_rc/` keyed `(ts_code, normalized_analyst_id, target_fy, report_date)`, with `effective_date` (§4) | ledger builder + `strictly_next_open_trade_day` L659 |
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
forecast already visible by `effective_date`. Deterministic ordering key:
`qlib_code, normalized_analyst_id, target_fy, effective_date, report_date, _src_file, _src_ordinal`
(reuse the P0-4 tie-break). **The first forecast for a new analyst / new `target_fy` is `coverage_init`,
NOT an up/down revision.** Same-day duplicates resolved deterministically before classification.

**The factor (Qlib expression, event-flow breadth, `Ref`-guarded, `Sum(If(...))` not `Count`):**
```
eps_rev_breadth_W = Ref(
  (Sum($report_rc__eps_up, W) - Sum($report_rc__eps_dn, W))
  / Max(Sum($report_rc__eps_revision_count, W), MIN_N),
  1)
```
`W ∈ {20,60,120}` becomes a factor hyperparameter (no re-materialize). `n_active_analysts` is carried as
STATE by the materializer (not inferred from sparse event sums). Discrete-ratio factors require a
minimum-evidence gate (`Sum(revision_count,W) >= 3` and/or `n_active_analysts >= 2`).

## 4. FY1 target = first-visible annual ACTUAL (no future leakage)
For stock S, day T: `target_fy` = the nearest annual fiscal year whose **annual actual has not yet
become visible by T**, where visibility = the first `effective_date` the annual-actual row appears in
the **sanctioned PIT statement ledgers** (income/indicators), NOT eventual data availability. Roll FY1
forward on that first-visible date. **Never classify a `YYYYQ4`→`(YYYY+1)Q4` change as an EPS revision —
that is a target change** (emit `coverage_change`/target-init, not up/down).

## 5. PIT anchor = max(next-open, vendor-lag) — quarantine until canary
`effective_date = max( strictly_next_open_trade_day(report_date), vendor_observed_effective_date )`.
`Ref(...,1)` does NOT fix vendor backfill lag (if a row dated T was only obtainable at T+K, the provider
is already too early). If row-level ingestion time is unavailable, use a **predeclared conservative lag**
and keep the field **quarantined** until the backfill canary (the standing 2026-06-15 reading) proves no
material lag. Registry fails closed on quarantine — exactly the desired gate.

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
Materialize the §3 primitive family. **Defer/quarantine:** `targetprice_*` (unit/scale contamination —
the `tp` field has 9600-type garbage); `rating_diffusion` (2% coverage, dead — negative control only);
analyst/org quality scores (circularity unless frozen ex-ante). Sparse fields stay NaN on no-event days;
factors decide no-event→0 via `Sum(If(IsNull,0,...))`.

## 9. Phases & gates (tightened)
- **P0 — pre-register + (this) design review DONE.** Freeze: event-flow semantics, the §3 primitives,
  FY1 first-visible rule, the anchor, the kill manifest. *Gate: design GO ✓ (with conditions).*
- **P1 — no-alpha PLUMBING slice (first PR).** 1-2 tickers, 1-2 years, quarantined `report_rc__eps_up/
  dn/revision_count/n_active_analysts` only, NO screen. Wire: `DatasetSpec` + add to `PHASE3_DATASETS`
  + `PERIODIC_LEDGER_DATASETS`; build `pit_ledger/report_rc/`; `_materialize_report_rc_consensus` + the
  explicit `materialize_provider` hook; register `$report_rc__` quarantine. **Acceptance = deterministic
  rebuild + the §6 PIT canaries + provider parity — NOT IC.**
- **P2 — full primitive family + parity/canary suite green on a small basket.** *Gate: all §6 tests.*
- **P3 — full provider rebuild (§13 risky — basket-first, confirm)** + coverage/parity audit + (canary
  permitting) quarantine→approved.
- **P4 — catalog factors** (`eps_rev_breadth_{20,60,120}`, `Ref`-guarded, `Sum(If)`); PIT-safety lint.
- **P5 — compliant `factor_lifecycle` IS screen** against the §7 manifest (REPLACES the tainted pilot —
  confirms or kills `eps_rev_breadth`). → draft→candidate by marginal/orthogonal IC.
- **P6 — sealed OOS (candidate→approved) OR ML features** read compliantly via `compute_factors`.

## 10. Open items still needing a call
1. **Event-flow vs active-latest** — v2 commits to event-flow (honest, valid Qlib math). Active-latest
   (true one-vote consensus) is a later refinement needing backend state/cancellation primitives or A1.
2. **Vendor ingestion-time** — does the raw `report_rc` carry an obtainable-at timestamp? If not, the
   conservative-lag + canary path is mandatory before promotion.
3. **`normalized_analyst_id`** — author/org strings are messy (multi-author rows, name variants); the
   per-analyst state machine needs a stable identity normalization — a sub-task to scope in P1.
