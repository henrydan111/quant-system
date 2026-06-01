# Factor-lifecycle Phase 4 — port walk-forward revalidation → tested `factor_lifecycle/` modules (DESIGN, pre-build)

Status: **DESIGN v2 — conditional-GO review integrated; ready for confirm before build.** Round-1 design
review (leakage-focused) returned a conditional GO with 3 must-fixes — all integrated: (1) the `is_end`
guarantee must bound the **label-realization date**, not just the factor date (the forward-return label is
future-looking — compute with `horizons=None`, build the label capped at `is_end`, drop dates whose `t+h`
realization `> is_end`, assert both bounds); (2) the DEFAULT 5+2+1 fold config yields **0 folds** for the
2014-2020 IS window (verified) → mode 1 builds an explicit IS-internal holdout and FAILS CLOSED for generated
factors when none exists; (3) SPLIT `assign_historical_status` (oos-based parity) from `assign_candidate_status`
(IS-only). The 7 open questions are resolved below. Phases 1-3 are MERGED to `wave1-field-promotion`. This is
the **leakage-sensitive** phase.

## Goal
Turn the two stand-alone walk-forward revalidation scripts
([workspace/scripts/revalidate_catalog_walkforward.py](workspace/scripts/revalidate_catalog_walkforward.py),
[workspace/scripts/revalidate_derived_factors.py](workspace/scripts/revalidate_derived_factors.py)) into a
tested `src/alpha_research/factor_lifecycle/` package, reusing the existing
[src/alpha_research/walk_forward.py](src/alpha_research/walk_forward.py) (`TimeSplit`,
`build_walk_forward_folds`) and [src/alpha_research/factor_eval/](src/alpha_research/factor_eval/) (IC /
quantile metrics). The scripts become thin CLI wrappers over the modules so the existing
`catalog_revalidation/*.csv` workflow (which Phase 2's `import_revalidation` consumes) keeps working.

## The single most important rule — the `is_end` leakage boundary (plan §2.2 / Q4)
There are **two distinct walk-forward modes**, and conflating them is the leakage risk this phase exists to
prevent:
1. **Formal IS-only walk-forward (`draft → candidate` evidence).** Per plan §2.2: a generated / IS-selected
   factor's candidate evidence is an "IS-only held-out / walk-forward **bounded to `TimeSplit.is_end`** —
   never spends sealed OOS." This mode MUST be **structurally** incapable of reading past `is_end` — and the
   boundary is on the **label-realization date, not just the factor date** (design-review must-fix #1): the
   forward-return label is FUTURE-looking (`forward_return(h) = Ref(ADJ_CLOSE, 0 - h)/ADJ_CLOSE - 1`,
   [operators.py:1044](src/alpha_research/factor_library/operators.py)), so a factor evaluated at date `t`
   needs prices at `t + h`. Capping the `compute_factors` `end_date` at `is_end` is therefore NOT sufficient
   — the label for any `t` within `h` trading days of `is_end` would still pull OOS prices. The formal mode
   MUST: (a) compute factors with `horizons=None` (no `compute_factors`-built forward return); (b) build the
   label separately from adjusted close loaded only through `is_end`; (c) DROP every factor date whose
   label-realization date (`t + h` trading days) `> is_end` — i.e. the last usable factor date is `is_end`
   shifted back `h` trading days; (d) assert at runtime BOTH `max_loaded_date ≤ is_end` AND
   `max_label_realization_date ≤ is_end`. Post-hoc slicing of a full-window compute is NOT acceptable —
   neither OOS prices nor OOS-realizing labels may be in memory.
2. **Historical full-window revalidation (non-formal investigation).** The EXISTING scripts compute over the
   full `[2014-01-01 … 2026-02-27]` window (IS *and* OOS) and report `is_rank_icir` + `oos_rank_icir` for
   investigation. That OOS read is exactly why Phase 2 labels every imported revalidation row
   `evidence_class=historical_investigation` + `formal_evidence_eligible=False`. This mode is preserved AS-IS
   (it is not a formal gate) but is explicitly **fenced off from the `draft→candidate` decision** — only
   mode 1 can produce candidate-promotion evidence.

The spec's job: implement mode 1 as a new, structurally-bounded validator; port mode 2 faithfully; make it
**impossible** for a mode-2 (OOS-touching) result to be mistaken for mode-1 candidate evidence.

## Current state (grounded — Explore map, 2026-05-31)
- Both scripts load factor data ONLY through the sanctioned path `operators.compute_factors(...)` →
  [qlib_windowed_features](src/research_orchestrator/qlib_windowed_features.py) → `D.features`. **No raw
  `data/pit_ledger/*` reads, no bare `D.features`, no string-date comparisons** (IC sliced by
  `pd.Timestamp` index). Industry labels via PIT-safe `build_industry_series_asof(..., "L1")`. They are clean
  today — the port must PRESERVE this.
- Constants: `START=2014-01-01`, `IS_END=2020-12-31`, `OOS_START=2021-01-01`, `END=2026-02-27`, `HORIZON=20`.
- **Catalog script** → 147 base factors; CSV `factor, field_eligible, full_rank_icir, is_rank_icir,
  oos_rank_icir, sign_consistency, n_years, status, reason`.
- **Derived script** → 20 composite + 4 industry-relative; CSV adds `kind, lo_excess_ann, lo_sharpe, lo_hit`
  (the GROSS long-only top-bucket metric Phase 2 stores as `lo_*_gross`).
- `walk_forward.py` ALREADY defines `TimeSplit` (frozen; invariant `is_end < oos_start`) +
  `build_walk_forward_folds(...) → (folds: list[FoldSpec], holdout: HoldoutSpec|None)` (5y/2y/1y, step 1y).
- Reusable: `factor_eval` (`compute_ic_series`, `compute_ic_summary`, `compute_ic_by_year`,
  `compute_quantile_returns`), `testing_ledger.py` (verdict sink, P1.5 file-locked), `field_registry`
  (eligibility), `result_analysis` (canonical metrics).

## Boundary / non-goals (Phase 4)
NO new factors registered/promoted (Phase 6); NO orchestrator profile (Phase 5); NO status writes from the
module itself (it produces EVIDENCE/verdicts; the writer gate still owns `approved`); NO change to the
Phase-1/2/3 gates; NO change to `compute_factors` / the sanctioned loaders. Pure extraction + the `is_end`
structural boundary + tests.

## Proposed module structure
```
src/alpha_research/factor_lifecycle/
  __init__.py
  metrics.py        # pure metric builders over a factor/return panel (reuse factor_eval):
                    #   is/oos/full rank ICIR, per-year sign consistency, GROSS long-only top-bucket
                    #   (lo_excess_ann/lo_sharpe/lo_hit). NO data loading, NO window logic.
  revalidation.py   # the two MODES, sharing metrics.py:
                    #   run_is_walk_forward(catalog, time_split, ...)  -> FORMAL, is_end-bounded (mode 1)
                    #   run_historical_revalidation(catalog, window, ...) -> NON-FORMAL IS+OOS (mode 2)
  status_rules.py   # SPLIT (must-fix #3): assign_historical_status(...) = parity with the old CSVs (uses
                    #   oos_icir), vs assign_candidate_status(...) = IS-only evidence, emits NO oos_* field.
                    #   Long-only viability stays Phase-2 METADATA, never a lifecycle-status input here.
  report.py         # DataFrame -> the exact CSV columns the Phase-2 importer expects (historical mode)
```
The two scripts become ~20-line CLI wrappers calling `run_historical_revalidation` ONLY (open-Q5) — they keep
their `historical_investigation` status and are NOT candidate-promotion entry points.

### `run_is_walk_forward` (mode 1 — the leakage-critical piece)
- Signature (proposed): `run_is_walk_forward(*, catalog, time_split: TimeSplit, horizon=20, stage="sandbox_screening", field_gate=True, factor_origin="generated") -> WalkForwardResult`.
- **Three-belt label-safe boundary (must-fix #1 / #2):**
  1. **No `compute_factors` forward return:** call `compute_factors(catalog, time_split.is_start, time_split.is_end, horizons=None, stage=...)` — factors only, END = `is_end`.
  2. **Label capped at `is_end`:** build the forward return from adjusted close loaded only through `is_end`, and DROP every factor date `t` whose label-realization date (`t` shifted `+horizon` TRADING days via the trade calendar) `> is_end`. The last usable factor date is therefore `≈ is_end - horizon` trading days.
  3. **Runtime + result assertions:** `max_loaded_date ≤ is_end` AND `max_label_realization_date ≤ is_end`; the returned `WalkForwardResult` has NO `oos_*` field and records `effective_eval_end (= last realized label date)`.
- **Folds (must-fix #2; review sign-off):** the DEFAULT `build_walk_forward_folds` (5+2+1) returns **0 folds / None holdout** for the 2014-2020 IS window (verified). So mode 1 builds an **explicit IS-internal holdout** inside `[is_start, is_end - horizon]`. **Default protocol = rolling 3 train + 1 validation + 1 test** (gives MULTIPLE heldout blocks across the canonical 7-year IS window); an explicit `walk_forward_config` is allowed; a **single expanding-window holdout is a documented fallback only for shorter windows**. Every block's label-realized `test_end ≤ is_end` is asserted. The result records the `protocol`/`walk_forward_config` and `n_heldout_blocks`. **Fail closed:** for `factor_origin="generated"` / IS-selected, if no valid IS-internal heldout block can be built, RAISE — a generated factor cannot become `candidate` without true heldout evidence.
- **Evidence by origin (open-Q3; review sign-off):** `evidence_kind` is **first-class on BOTH the result metadata AND each per-factor row** (so a concatenated report can NEVER blur the two). Generated / IS-selected → `evidence_kind="generated_heldout"` (explicit IS-internal heldout rank ICIR + fold sign-consistency). A-priori → `evidence_kind="a_priori"` (yearly blocked sign-consistency within IS), never conflated with generated heldout.
- **Produces** per-factor: fold sign-consistency, IS-heldout rank ICIR, coverage, `evidence_kind`, `effective_eval_end` (= last realized label date), `protocol`, `n_heldout_blocks`. It does NOT compute or emit any `oos_*` field (structurally cannot).
- **Testing ledger (open-Q4):** Phase 4 returns a SERIALIZABLE verdict/event object only; it does NOT write formal `testing_ledger` rows by default — real ledger writes are deferred to Phase 5/6 when the orchestrator owns the run.

### `run_historical_revalidation` (mode 2 — preserve existing behavior)
- Faithful port of the current full-window scripts (IS + OOS reported), labeled non-formal. Emits the
  existing CSV columns (incl `is_rank_icir`/`oos_rank_icir`/`lo_*`) so `import_revalidation` is unchanged.
- Hard contract: its result type / CSV is tagged `historical_investigation`; it is NEVER accepted by mode-1
  candidate-promotion code.

## PIT-safety (preserved + hardened)
All loads stay on the sanctioned path (no raw ledger / bare `D.features` / string dates — the PIT002 lint +
the loader-parity contract already enforce this repo-wide and the new modules are in-scope). The `is_end`
structural boundary is the NEW guarantee: mode 1 never holds OOS data in memory. Module reuses
`build_industry_series_asof` for the derived/industry-relative factors (PIT-safe).

## Risks + the tests that close them
- **Label leakage (the whole point, must-fix #1)** → `test_is_walk_forward_label_never_realizes_past_is_end`:
  spy `compute_factors` and assert it is called with `horizons=None` AND `end_date == is_end` (never
  `oos_end`); assert the result's `max_label_realization_date ≤ is_end` AND `max_loaded_date ≤ is_end`;
  assert factor dates within `horizon` trading days of `is_end` are DROPPED (last usable `t ≈ is_end - h`);
  assert the `WalkForwardResult` exposes NO `oos_*` field. A synthetic-calendar fixture pins the
  `t + horizon` trading-day shift against `data/reference/trade_cal.parquet` semantics.
- **Fold config / fail-closed (must-fix #2)** → `test_default_folds_zero_for_is_window` (pins
  `build_walk_forward_folds("2014-01-01","2020-12-31") == ([], None)` so the regression is visible);
  `test_is_internal_holdout_built_and_bounded` (the formal validator's shorter config yields ≥1 heldout block
  with label-realized `test_end ≤ is_end`); `test_generated_factor_fails_closed_without_heldout` (RAISES when
  no valid IS-internal heldout can be built for `factor_origin='generated'`).
- **Mode confusion** → `test_historical_result_rejected_by_candidate_path`: a mode-2
  (`historical_investigation`) result cannot be passed where mode-1 candidate evidence is expected
  (type/label guard).
- **Metric parity** → `test_module_metrics_match_scripts`: on a small synthetic panel, `metrics.py`
  reproduces the scripts' `rank_icir`/`sign_consistency`/`lo_*` exactly (no behavioral drift in the port).
- **Split status rules (must-fix #3)** → `test_assign_historical_status_pinned` (the OLD oos-based thresholds,
  for CSV parity) AND `test_assign_candidate_status_is_only` (the candidate rule consumes NO `oos_*` field;
  long-only viability is NOT an input).
- **PIT lint** → the new package is covered by `lint_no_unsafe_pit_dates.py` (PIT002 hard) + the factor-
  library PIT-safety suite; CI/offline run stays green.
- **CSV contract** → `report.py` round-trips through Phase-2 `import_revalidation` (historical columns match).

## Open questions — RESOLVED (design review, conditional GO)
1. **Mode separation** → TWO functions (`run_is_walk_forward` vs `run_historical_revalidation`). A shared
   `mode=`/`include_oos=` flag is the exact footgun that caused the original PIT-lookahead incident. ✓
2. **`is_end` enforcement** → structural loading is correct but insufficient alone (future-return label).
   THREE belts: no `horizons` in the formal `compute_factors`; label loader capped at `is_end`;
   runtime/result assertions that no factor date OR label-realization date crosses `is_end`. An
   `evaluate_windowed_panel(...)` helper is fine only if the panel carries/validates window metadata. ✓
3. **Held-out evidence** → prefer an explicit IS-internal holdout; FAIL CLOSED for generated/IS-selected
   factors when none can be built. Yearly blocked sign-consistency within IS is acceptable only for a-priori
   factors and is labeled `a_priori` evidence, never conflated with generated-factor heldout. ✓
4. **Testing ledger** → DEFER real ledger writes to Phase 5/6 (orchestrator-owned). Phase 4 returns a
   serializable verdict/event object / optional sink; default library calls write no formal ledger rows. ✓
5. **Scripts** → keep `revalidate_*.py` as thin wrappers over `run_historical_revalidation` ONLY (preserve
   `historical_investigation`); NOT candidate-promotion entry points. ✓
6. **Status rules home** → `status_rules.py`, SPLIT into `assign_historical_status` (oos-based parity) vs
   `assign_candidate_status` (IS-only). Do NOT reconcile historical OOS thresholds into the formal candidate
   gate; long-only viability remains Phase-2 METADATA, not lifecycle status. ✓
7. **Scope** → modules + tests + thin wrappers, NO official new full revalidation run (existing CSVs stand);
   synthetic parity tests + an optional small fixed real-data smoke into scratch output; do NOT
   overwrite/import the existing `catalog_revalidation/*.csv` as part of Phase 4. ✓

## Build order (review-confirmed)
1. **`metrics.py`** — pure metric builders over a (factor, return) panel; reuse `factor_eval`.
2. **`status_rules.py`** — SPLIT `assign_historical_status` (oos-based parity) vs `assign_candidate_status`
   (IS-only); unit-pinned.
3. **`run_historical_revalidation`** (mode 2) + the CSV-parity test (port the existing scripts faithfully).
4. **label/calendar helper** (`t+h` trading-day realization via `trade_cal.parquet`) + its leakage tests,
   built BEFORE/ALONGSIDE **`run_is_walk_forward`** (mode 1) — the reviewer's sequencing tweak: the
   leakage-critical helper + tests land WITH the validator, not after historical parity.
5. **thin script wrappers** (`revalidate_*.py` → `run_historical_revalidation` only).

## Acceptance
`src/alpha_research/factor_lifecycle/` package added (metrics/revalidation/status_rules/report); the
**label-realization** `is_end` leakage test (must-fix #1) + the fold-config/fail-closed tests (must-fix #2) +
the SPLIT historical/candidate status-rule tests (must-fix #3) + mode-confusion + metric-parity + CSV-contract
tests all green; the two scripts reduced to thin wrappers over `run_historical_revalidation` with
byte-identical CSV output (or a documented diff); PIT002 lint + factor-library PIT suite green; CLAUDE.md §3 +
AGENTS.md §2a Phase-4 entry added (same pass, §11.2); full offline suite green. Then Phase 5 (orchestrator
`factor_lifecycle` profile) begins.

## Implementation (branch `factor-lifecycle-p4`)
IMPLEMENTED per the build order: `metrics.py` + `status_rules.py` + `revalidation.py`
(`revalidate_panel` + `run_historical_*`) + `report.py` + `walk_forward_validation.py`
(`IsWindowedPanel` 3-belt boundary + `run_is_walk_forward`); `revalidate_*.py` reduced to
thin wrappers. 30 package tests + 49-test regression sweep (architecture + factor_lifecycle)
green; PIT002 lint clean for the new code; no new revalidation run (existing CSVs stand).
