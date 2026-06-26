# GPT cross-review packet — `_materialize_quality_stability` (PIT materializer)

> **Gate:** CLAUDE.md §10 — a new PIT materializer must pass independent GPT 5.5 Pro review before it is
> published to the live provider / registered / relied on. Foreground the **quantitative-research principles
> (PIT / no-lookahead FIRST)**. Public repo: `https://github.com/henrydan111/quant-system` (branch
> `report-rc-registration`). **The embedded diff below is authoritative** (not yet pushed — shared-tree).

## What it is / why

The 果仁 #59 Comp_Core_Quality book uses 2 stability factors — `STDEVQ(RoeCoreQ,12)` and
`STDEVQ(SalesQGr%PY,12)` — that need a trailing-12-quarter single-quarter series (the live provider only
materializes `_sq_q0..q4`). A scoped deep-slot build proved these 2 factors lift #59 holdings overlap
**21.6%→35.9%** and converge the backtest to 果仁 (annual +25.3→+21.4% vs +22.6%; vol 27.1→25.7 vs 26.7).
To formalize #59 we materialize them as 2 PIT provider fields (`$roe_core_stab_12q` / `$sales_gr_stab_12q`),
**mirroring the GPT-reviewed `_materialize_forecast_growth` precedent** (custom cross-quarter PIT field).

## Definitions

- `RoeCoreQ(q) = CoreProfit_sq(q) / equity(q)`; `CoreProfit_sq = revenue_sq − oper_cost_sq −
  (admin_exp+sell_exp+fin_exp)_sq − biz_tax_surchg_sq`; single-quarter `_sq = cum[q] − cum[q−1]` (Q1 = cum).
  `equity = total_hldr_eqy_exc_min_int` (balancesheet point balance).
- `SalesQGr%PY(q) = (revenue_sq(q) − revenue_sq(q−4)) / |revenue_sq(q)|` — **slot-aligned: q−4 = 4 report
  slots back, NOT a calendar year** (matches the provider `_sq_q{i}` convention the factor was validated against).
- Output = POPULATION stdev (ddof=0) over the N-th-most-recent report quarters known as-of the day; ≥8 finite.

## PIT design (the load-bearing claims to check)

1. **As-of, restatement-aware:** at each disclosure event `e` (effective_date), a report period's value =
   the latest disclosure with `effective_date ≤ e` (`searchsorted(..., 'right')-1` on per-period eff arrays).
   A period is "known" iff its EARLIEST effective_date ≤ e.
2. **Step function:** fill `[e, next_event)` with the value computed AS-OF e; NaN before first computable;
   the next event recomputes. (Same structure as `_materialize_forecast_growth`.)
3. **Quarter-end prefilter:** only standard fiscal ends (03-31/06-30/09-30/12-31) — an irregular end_date
   can't be mis-slotted (mirrors `_materialize_profit_dedt_sq` GPT Plan-C Major-3).
4. **Sub-universe:** needs ~3yr history → ~73% coverage; consumers `Ref(...,1)` + gate on non-null/recency.

## R1 = REVISE → folded (this is the R2 packet)

R1 verdict was REVISE (2× P1 + P2). All folded:
- **P1-1 (field_filter not honored):** each field's build+write gated by `out_fields`; canaried.
- **P1-2 (no canary tests):** **7 canaries** lock no-lookahead, ≥8-finite, restatement-recompute,
  quarter-end prefilter, slot-aligned q−4, field-filter, exact hand-calc value. **38 data_infra tests pass.**
- **P2 (deterministic dedup):** `canonicalize_report_variants` per-stock-group.
- **Tail (R1 answer 5): RESOLVED.** Classified + fixed in two steps: (a) refactored to REUSE the proven
  single-quarter kernel (`materialize_canonical_quarter_segments` + `arrays_from_snapshot_segments`) instead
  of reinventing `cum[q]−cum[q−1]`; (b) the residual was the income family's `quarterly_dataset` —
  `income_quarterly` (direct single-quarter, the kernel's direct-quarter precedence) — which the deepslot
  `_sq` slots used but the materializer wasn't feeding. Now feeds it.

## Validation (vs the rung-6 deepslot f9/f10 = the +14.3pp truth) — now BIT-FAITHFUL

Real code path (scoped staged build, 54 symbols, read via D.features) vs the deepslot-provider factors:
**`$roe_core_stab_12q` vs f9 — median rel-err 0.0, 98.4% w/1%, 99.0% w/5%; `$sales_gr_stab_12q` vs f10 —
median 0.0, 100% w/1%, 100% w/5%** (coverage 0.75/0.73 ≈ truth 0.76/0.74). `median=0.0` ⇒ most values
float32-IDENTICAL; the kernel+`income_quarterly` reuse eliminated the R1 tail (was 70/84% w/1%). roe residual
1.6% = float32/equity-snapshot edge, negligible. Script: `workspace/scripts/_validate_stability_materializer.py`.

## Review questions (please assess)

1. **No-lookahead:** is the as-of computation strictly lookahead-free? Any path where a disclosure with
   `effective_date > e` leaks into the value filled at a day in `[e, next_event)`?
2. **Single-quarter derivation** (`cum[q]−cum[q−1]`, Q1=cum): correct + restatement-consistent? Edge cases
   (a period restated AFTER e but its prior-quarter not, mixing vintages)?
3. **Slot-aligned q−4** (N-th-most-recent, not calendar-year): is this the right PIT convention, or should
   SalesQGr%PY use the calendar prior-year quarter (and would that better match 果仁)? Note the holder-grid
   rung-5 finding (slot-REF vs report-period-REF diverge under sparse disclosure).
4. **ddof=0 + ≥8-of-12 threshold + the trailing-16 window for SalesQGr** — appropriate? Bias from a variable
   number of finite quarters in the stdev?
5. **The ~15-20% tail vs the deepslot truth** — benign edge-case difference, or a latent bug?
6. **Registration:** sub-universe ~73% coverage, no `f_ann_date` in income/balancesheet? (Both anchor
   `max(ann_date, f_ann_date)` — confirm the effective_date the ledger carries is correct for these.)
7. **Unit safety:** ratios are dimensionless (元/元) so no scale issue — confirm.

## The diff (authoritative)

`src/data_infra/pit_backend.py` — new method `_materialize_quality_stability` (after `_materialize_forecast_growth`)
+ dispatch wiring (gated on `{income,balancesheet} ⊆ active_datasets`). [Embed the method body from the working
tree here when sending — it is the ~140-line block beginning `def _materialize_quality_stability`.]

Contract sections it must honor: CLAUDE.md §3.2 (PIT correctness — effective_date>disclosure, no lookahead,
no hand-rolled alignment), §3.4 (field-status registry — the 2 fields need an approval YAML + log), §6.1
(read the Tushare income/balancesheet doc — done in data_dictionary). `_materialize_forecast_growth` is the
approved precedent (project_state 2026-06-23 rung-3, GPT R1→R4 SHIP).
