# Design: extend the `factor_lifecycle` IS-only gate to the 24 composite + industry-relative factors

Phase 5 narrowed the `factor_lifecycle` profile to `consumes_types=("factor",)` and the
`dataset_build` handler records composite / industry-relative factors as `non_base_deferred`
(not computed, not gated). Phase 6 promoted 72 of the 147 BASE factors. This design closes the
deferral: gate the **20 composite + 4 industry-relative** factors through the SAME IS-only
walk-forward gate, preserving every leakage belt.

## 1. The leakage analysis (the load-bearing part)

Both Layer-2 compute paths are **same-date cross-sectional transforms of already-PIT-safe base
factors** — they introduce NO cross-date dependency and NO new `$field` references, so the
`is_end` boundary that Phase 4 guarantees for base factors is **inherited unchanged**:

- **Composites** (`operators.add_composites`): `composite[t] = Σ wᵢ · cs_rank(±baseᵢ[t])`.
  `cs_rank` is per-date; the weighted sum is per-row. `composite[t]` depends ONLY on base
  values at date `t`.
- **Industry-relative** (`operators.add_industry_relative_composites`):
  - `industry_mean_subtract`: `base[t] − groupby((t, industry)).mean()` — per-date.
  - `size_industry_neutralize`: residual of `base[t] ~ log(mcap[t]) + industry_dummies[t]` —
    per-date regression.
  Both per-date; `industry_series` is PIT-safe by construction
  (`provider_metadata.build_industry_series_asof` uses `in_date ≤ as_of < out_date`); `mcap`
  is `Ref($total_mv, 1)` (approved, shifted).

**Consequence:** if the base factors are computed over `[is_start, is_end]` and the label is the
exact-calendar `r(t)` forward return (`≤ is_end`) — exactly as the base path already does — then
the Layer-2 factor values are also bounded by `is_end` (a same-date transform cannot move a
value's date). The Layer-2 panel reuses the **identical** label + the **identical**
`IsWindowedPanel` belts (`max_factor_date ≤ is_end` AND `max_label_realization_date ≤ is_end`).
No belt is weakened; the gate stays IS-only.

One subtlety to record (not a leak): `cs_rank` / industry-demean at date `t` use the stocks
present at `t` *within the IS window*. That is the correct cross-section at `t` (identical to
how the base factors' own ICs are computed). No future stocks enter.

## 2. The new Layer-2 IS-only panel builder

Add `load_is_windowed_panel_with_layer2(...)` in
`src/alpha_research/factor_lifecycle/walk_forward_validation.py` (parallel to
`load_is_windowed_panel`, reusing `build_is_windowed_panel` for the label + belts):

1. **Dependency closure** of base factors = `gated_base ∪ {components of gated composites} ∪
   {bases of gated industry-rel}`. All are base-catalog factors and field-clean by construction
   (a composite is field-eligible IFF all its components' base exprs pass the field gate, so its
   components are field-clean; same for an industry-rel's base).
2. Compute the dependency-closure base panel over `[is_start, is_end]` with `horizons=None`
   (belt 1) — the SAME `compute_factors` call the base path uses.
3. `industry_series = build_industry_series_asof(base_panel.index, "L1")`;
   `market_cap = compute_factors({"market_cap": "Ref($total_mv, 1)"}, …)["market_cap"]`
   (only if a gated industry-rel needs it — `mom_idio_20d`).
4. `add_composites(base_panel, gated_composite_defs)` +
   `add_industry_relative_composites(base_panel, industry_series, market_cap, gated_industry_defs)`.
5. **Gated panel** = the columns for `gated_base + gated_composites + gated_industry_rel` ONLY
   (dependency-only bases are computed for inputs but EXCLUDED from the gated panel → never
   appear as verdicts). This mirrors the Phase-3 `get_factor_selection` dependency contract.
6. `build_is_windowed_panel(gated_panel, adj_close, is_end=…, horizon=…)` → `IsWindowedPanel`
   (belts re-assert `is_end`). `adj_close` is the same `Ref`-free adjusted close loaded over
   `[is_start, is_end]`.
7. `run_is_walk_forward(panel=…, factor_origin="a_priori")` → per-factor `candidate`/`draft`
   verdicts over base + composite + industry-rel together.

The MultiIndex level-order fix (Phase-6 bug #1) already makes `build_is_windowed_panel` robust;
`add_composites`/`add_industry_relative_composites` are level-order tolerant (name-based).

## 3. `dataset_build` change

`handle_factor_lifecycle_dataset_build` currently splits `eligible` into `eligible_base`
(in `get_factor_catalog`) vs `non_base_deferred`. New behavior: split into
`base / composite / industry_relative` (via `get_composite_defs` / `get_industry_relative_defs`
membership) and call the unified Layer-2 builder for all three. A factor in `eligible` that is
in NONE of the three is a hard error (unknown). No `non_base_deferred` bucket anymore (or it
stays only for genuinely-unknown names). The `consumes_types=("factor",)` stays — composites
and industry-rel are `object_type='factor'` rows in `factor_master` (verified: 20 + 4 of the
171), so the resolver allow-set + field gate already handle them per-factor.

## 4. Field-eligibility (already handled, one note)

`per_factor_field_eligible` → `_field_check_expressions` already resolves composite (all
component base exprs) and industry-rel (base expr) eligibility. **Known-benign gap:**
`mom_idio_20d` (`size_industry_neutralize`) also consumes `$total_mv` via `market_cap`, which
`_field_check_expressions` does not include (it checks only the base `mom_return_20d`). `$total_mv`
is `approved` (daily_basic), so the run is sound; the design will OPTIONALLY add `$total_mv` to
the industry-rel field-check for completeness (defense-in-depth, not a correctness fix).

## 5. OOS discipline — same `oos_informed_backfill` contract as the 72

Full-window (2014–2026) evidence already exists for all 24 in
`catalog_revalidation/derived_revalidation_status.csv` (same schema as the base CSV). The
honest, precedent-consistent choice (matching the user's "promote 72 OOS-stable only" call):

- **Promote the 16 OOS-stable** (derived-CSV `status == candidate`): 12 composites
  (`comp_defensive, comp_small_value, comp_rev_low_turn, comp_multi_6, comp_quality_value,
  comp_growth_value, comp_momentum_quality, comp_low_vol_value, comp_cash_sheep, comp_size_quality,
  comp_relative_strength, comp_52w_position`) + all 4 industry-rel (`mom_industry_rel_20d,
  mom_idio_20d, val_ep_industry_rel, val_bp_industry_rel`).
- **Exclude the 8** (7 `draft` marginal + 1 `deprecated` collapsed `comp_anti_risk`).
- Same caveats: IS-only validator uncontaminated; candidate ≠ approved; 2021–2026 burned for
  these 24 (sealed-window required for any future candidate→approved). The selection is
  `oos_informed_backfill` — recorded in the provenance artifact + a ledger funnel event.

NOTE several "candidate" composites have NEGATIVE OOS ICIR but high sign-consistency
(`comp_momentum_quality` −0.41, `comp_52w_position` −0.32) — they are sign-stable predictors in
the inverse direction; the IS-only gate's `|rank_icir| ≥ 0.10 ∧ sign_consistency ≥ 0.70` bar
admits them (direction is a deployment concern, recorded as `expected_direction` metadata, not
an IS-gate reject). **Decision to confirm:** do we want sign-agnostic admission (consistent with
the base run, which also admitted negative-ICIR factors like the reversal/low-vol set), or
restrict composites to positive-ICIR? Recommend sign-agnostic (consistent with Phase 6).

## 6. Tests (the belts must be re-proven for Layer-2)

- **Layer-2 leakage bound:** a synthetic fixture where a gated composite's value at the last
  factor date realizes its label at exactly `is_end` and one base date past it; assert the
  builder drops the past-`is_end` rows and `IsWindowedPanel` accepts (belt 3 holds for Layer-2).
- **Same-date-only proof:** mutate a base value at date `t+k` (k>0) and assert the composite
  value at `t` is unchanged (no cross-date dependency).
- **Dependency-only bases excluded:** a composite whose component base is NOT itself gated →
  the base is computed (input) but absent from the verdicts.
- **dataset_build computes (not defers) composites/industry-rel**; unknown name → hard error.
- **Industry-rel needs market_cap:** `mom_idio_20d` without `$total_mv` available → handled
  (the builder loads it; if a future field-gate blocks `$total_mv`, fail-closed).

## 7. Scope & sequencing

- This PR: the Layer-2 IS-only builder + `dataset_build` change + tests + the field-check note.
  NO run (the operational run is the next step, mirroring Phase 6: dry-run → temp validation →
  live promote-the-16 with the gate + `oos_informed_backfill` provenance).
- Reuses Phase-6 tooling (`phase6_setup_request.py` / `phase6_drive_gates.py` /
  `phase6_record_selection_provenance.py`) for the eventual run.
- Branch `factor-lifecycle-p7` → PR → `wave1-field-promotion`.

## 8. GPT conditional-GO integrated (design v2, 2026-06-01)

GPT cross-review = **Conditional GO**. All 6 answers confirmed (unified panel; sign-agnostic
admission; promote-16 OOS-stable; add `$total_mv`; etc.) with ONE contract correction + small
fixes. Integrated:

1. **cs_rank IS a PIT/lookahead leak if misused — re-framed (GPT main finding, I was wrong).**
   My v1 called the `cs_rank` positional-`level=0` issue "correctness, not leakage." That is
   WRONG: if a panel were `(instrument, datetime)`, `groupby(level=0)` ranks each stock ACROSS
   TIME, so `factor[t]` would use that stock's values at `t+1 … is_end` — **including dates after
   that row's label-realization `r(t)`** → a genuine lookahead leak INSIDE the IS window. **Fix
   (not just a guard):** harden the cross-sectional helpers to group by the `datetime` level BY
   NAME (with a dtype fallback when names are absent) — `cs_rank` (operators.py:1054),
   `cs_zscore` (:1069), `cs_demean` (:1086), and `winsorize` (:1186) all share the positional
   `groupby(level=0)` pattern. This is behavior-PRESERVING for every current caller (all pass
   `(datetime, instrument)` from `compute_factors`) and only fixes the wrong-order leak.
   ALSO add the local builder assert (`(datetime, instrument)` before `add_composites`) as
   belt-and-suspenders. Tests: per-helper order-invariance (same per-date result in both index
   orders) + the full operators/factor-library test sweep (shared helper under ~42 call sites).
2. **Negative-ICIR composites: sign-agnostic admission, but record direction.** Store/report the
   SIGNED `rank_icir` + an `expected_direction` (sign of the IS ICIR) on each verdict/evidence
   row; do NOT imply these are long-only-positive alpha (several admitted composites have
   negative OOS ICIR — inverse predictors).
3. **Phase-7 funnel artifact + ledger event for the FULL 24 → 16 surface** (mirror Phase 6's
   `oos_informed_backfill`): record `24 considered → field-eligible → IS-candidates → 16 promoted`
   + the label, so the multiple-testing surface for the composites is not understated.
4. **`$total_mv` added to the industry-rel field-eligibility check now** (`mom_idio_20d` really
   depends on `Ref($total_mv, 1)`; the field gate should see the real dependency even though
   `$total_mv` is `approved`).
5. **`out_date` wording corrected.** `build_industry_series_asof` treats `out_date` as INCLUSIVE
   (a membership is active for `in_date ≤ t ≤ out_date`; only `t > out_date` invalidates) — not
   the `t < out_date` my v1 stated. This is a boundary convention, NOT a lookahead (`out_date` is
   a known historical boundary), but the spec must match the code.

## Open questions for review
1. Is the same-date-cross-sectional leakage argument airtight, or is there a path by which
   `add_composites` / `add_industry_relative_composites` / `build_industry_series_asof` could
   pull a value dated after `r(t)` into a factor date `≤ is_end`?
2. Unified single-panel (base + composite + industry-rel in one `IsWindowedPanel` + one
   walk_forward) vs separate panels — any reason to keep them separate?
3. Sign-agnostic admission of negative-ICIR composites (recommended) vs positive-only?
4. Promote-16-OOS-stable (recommended, precedent-consistent) vs promote-all-that-pass-IS?
5. Add `$total_mv` to the industry-rel field-check now (defense-in-depth) or note-and-defer?
