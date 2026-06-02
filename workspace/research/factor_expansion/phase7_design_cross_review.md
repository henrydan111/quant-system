# DESIGN Cross-Review Request (for GPT) — extend the IS-only factor gate to composites + industry-relative

You are adversarially reviewing a **design** (no code written yet) to extend an A-share
`factor_lifecycle` IS-only `draft→candidate` gate from base factors to the **20 composite + 4
industry-relative** "Layer-2" factors. The prior phase (Phase 6) promoted 72 of 147 base
factors through this gate; a PIT-lookahead bug in earlier research is the reason this whole
arc is paranoid about leakage. You have **no repo access** — all code needed is embedded.
Find: any leakage path, any unsound reuse, any mis-stated guarantee. A NO-GO with specifics
beats a GO.

## 0. The guarantee that must be preserved
The IS-only gate computes each factor's cross-sectional rank IC over `[is_start=2014-01-01,
is_end=2020-12-31]`. The forward-return label is FUTURE-looking, so the binding constraint is
the **label-realization date**: for factor date `t`, the label uses adjusted close at the EXACT
trading-calendar target `r(t) = open_days[pos(t)+horizon]`, and the panel is rejected
(`IsEndLeakageError`) unless `max_factor_date ≤ is_end` AND `max_label_realization_date ≤ is_end`.
The design claim: composites/industry-relative inherit this unchanged because they are
**same-date cross-sectional transforms** of already-PIT-safe base factors.

## 1. The two Layer-2 compute paths (ACTUAL code)

### `add_composites` (cross-sectional rank-average)
```python
def add_composites(factors_df, composite_defs=None, progress_every=5):
    ...
    rank_cache = {}
    composite_columns = {}
    for cdef in composite_defs:
        name = cdef['name']; components = cdef['components']
        weights = cdef.get('weights', None); negates = cdef.get('negate', [False]*len(components))
        missing = [c for c in components if c not in df.columns]
        if missing: continue
        if weights is None: weights = [1.0/len(components)]*len(components)
        result = pd.Series(0.0, index=df.index)
        for comp, w, neg in zip(components, weights, negates):
            ranked = rank_cache.get((comp, neg))
            if ranked is None:
                vals = df[comp]
                if neg: vals = 0 - vals
                ranked = cs_rank(vals)          # <-- cross-sectional rank, per date
                rank_cache[(comp, neg)] = ranked
            result = result + w * ranked
        composite_columns[name] = result
    df = pd.concat([df, pd.DataFrame(composite_columns, index=df.index)], axis=1)
    return df
```
`cs_rank`'s ACTUAL definition is `series.groupby(level=0).rank(pct=True)` — it groups by
**positional level 0**, which equals `datetime` ONLY when the panel is `(datetime, instrument)`
order. `compute_factors` returns exactly that order, so in-path `composite[t]` is a weighted sum
of per-date cross-sectional ranks and depends only on base values at date `t`. **But this is the
SAME positional-level fragility class as the Phase-6 bug** (`build_is_windowed_panel` hardcoded
`(instrument, datetime)`): if a future caller fed `add_composites` an `(instrument, datetime)`
panel, `cs_rank` would silently compute a per-STOCK time-series rank — a WRONG factor.
Importantly this is a **correctness** bug, NOT a leakage one: a per-stock rank over
`[is_start, is_end]` still uses only values `≤ is_end` (no value past `r(t)` enters). The design
therefore adds a guard: the Layer-2 builder ASSERTS the base panel is `(datetime, instrument)`
(it is, from `compute_factors`) before calling `add_composites`. Verify the leakage argument
holds regardless of this order (it does — the window bound is independent of the grouping axis),
and weigh whether the guard is sufficient vs. making `cs_rank` itself name-based.

### `add_industry_relative_composites` (within-industry demean / size-industry neutralize)
```python
def add_industry_relative_composites(factors_df, industry_series, market_cap=None, defs=None, ...):
    industry_aligned = industry_series.reindex(factors_df.index)
    mcap_aligned = market_cap.reindex(factors_df.index) if market_cap is not None else None
    for d in defs:
        name=d["name"]; base=d["base"]; kind=d["kind"]
        if base not in factors_df.columns: continue
        base_series = factors_df[base]
        if kind == "industry_mean_subtract":
            dt_level = names.index("datetime")  # robust to either index order
            mask = industry_aligned.notna()
            grouped = base_series.where(mask).groupby(
                [factors_df.index.get_level_values(dt_level), industry_aligned])
            industry_mean = grouped.transform("mean")     # <-- per (date, industry)
            relative = (base_series - industry_mean).where(mask)   # null industry -> NaN
            new_columns[name] = relative.astype(np.float32)
        elif kind == "size_industry_neutralize":
            mask = industry_aligned.notna() & mcap_aligned.notna()
            residual = neutralize_size_industry(base_series.where(mask),
                                                mcap_aligned.where(mask),
                                                industry_aligned.where(mask))  # per-date OLS residual
            new_columns[name] = residual.astype(np.float32)
    ...
```
The 4 industry-rel defs: `mom_industry_rel_20d` (base `mom_return_20d`, mean_subtract),
`mom_idio_20d` (base `mom_return_20d`, size_industry_neutralize, needs mcap),
`val_ep_industry_rel` (base `val_ep_ttm`, mean_subtract), `val_bp_industry_rel` (base `val_bp`,
mean_subtract). **Claim: both kinds are per-date.** `neutralize_size_industry` regresses
`base[t] ~ log(mcap[t]) + industry_dummies[t]` and returns residuals, per date. Verify it does
not pool dates. **Unlike `cs_rank`, both industry-rel paths are MultiIndex-order-robust**:
`industry_mean_subtract` uses a name-based `datetime` level (`names.index("datetime")`) for the
groupby, and `neutralize_size_industry` → `neutralize` calls `_normalize_multiindex` first. So
the only order-fragile helper is `add_composites`/`cs_rank` (guarded per §1).

### `build_industry_series_asof` (PIT-safe industry labels) — docstring
> per-instrument membership lookup using a vectorized merge_asof on the `in_date` dimension,
> then a forward boundary check on `out_date`. Returns industry code aligned to the index; NaN
> for any (datetime, instrument) without an active SW2021 classification on that date.

i.e. label at `(t, stock)` = the SW2021 industry whose `in_date ≤ t < out_date`. **Claim: no
lookahead** (uses only membership active AS OF `t`). `market_cap` = `Ref($total_mv, 1)`
(approved, shifted by 1 day → strictly past).

## 2. The label + belts the Layer-2 panel REUSES verbatim (already GPT-reviewed in Phase 6)
```python
def build_is_windowed_panel(factor_panel, adj_close, *, is_end, horizon=20, trade_cal=None):
    open_days = load_open_trading_days(trade_cal); is_end_ts = pd.Timestamp(is_end)
    f_max = factor_panel.index.get_level_values("datetime").max()
    a_max = adj_close.index.get_level_values("datetime").max()
    if f_max > is_end_ts: raise IsEndLeakageError(...)   # belt 0
    if a_max > is_end_ts: raise IsEndLeakageError(...)    # belt 0
    # r(t) = open_days[pos(t)+horizon] per unique factor date; missing -> NaT -> dropped
    ...
    names = list(factor_panel.index.names)               # level-order robust (Phase-6 fix)
    if list(adj.index.names) != names: adj = adj.reorder_levels(names).sort_index()
    future_index = MultiIndex in factor_panel's level order with datetime = r(t)
    cur = adj.reindex(factor_panel.index); fut = adj.reindex(future_index)
    label = (fut/cur - 1).dropna(); aligned = factor_panel.loc[label.index]
    return IsWindowedPanel(factor_panel=aligned, label=label, is_end=is_end_ts, horizon=horizon, open_days=open_days)

# IsWindowedPanel.__post_init__ (belt 3):
#   raises unless factor_panel/label indices align, max_factor_date <= is_end,
#   and realization_date(max_factor_date, horizon) <= is_end.
```
The Layer-2 builder will assemble the composite/industry-rel value columns into `factor_panel`
and call this UNCHANGED (same `adj_close`, same `r(t)` label, same belts).

## 3. Proposed Layer-2 IS-only builder (pseudocode of the new function)
```python
def load_is_windowed_panel_with_layer2(*, gated_base, gated_composite_defs, gated_industry_defs,
                                       time_split, horizon, qlib_dir):
    base_catalog = get_factor_catalog(include_new_data=True)
    # dependency closure: gated bases + all composite components + all industry-rel bases
    dep = set(gated_base) | {c for d in gated_composite_defs for c in d["components"]} \
          | {d["base"] for d in gated_industry_defs}
    base_panel, _ = compute_factors(catalog={n: base_catalog[n] for n in dep},
                                    start_date=is_start, end_date=is_end, horizons=None, ...)
    adj_panel, _ = compute_factors(catalog={"adj_close": ADJ_CLOSE},
                                   start_date=is_start, end_date=is_end, horizons=None, ...)
    industry = build_industry_series_asof(base_panel.index, "L1")
    mcap = compute_factors({"market_cap":"Ref($total_mv,1)"}, ...)["market_cap"] if any size-neut else None
    panel = add_composites(base_panel, gated_composite_defs)
    panel = add_industry_relative_composites(panel, industry, mcap, gated_industry_defs)
    gated_cols = list(gated_base) + [d["name"] for d in gated_composite_defs] + [d["name"] for d in gated_industry_defs]
    return build_is_windowed_panel(panel[gated_cols], adj_panel["adj_close"], is_end=is_end, horizon=horizon)
```
**Note the gated-subset contract:** dependency-only bases (composite components that are NOT
themselves gated — e.g. `grow_netprofit_yoy`, a known OOS-collapser used by `comp_garp`) are
computed as Layer-2 INPUTS but EXCLUDED from `gated_cols`, so they never produce a verdict.

## 4. OOS discipline (same `oos_informed_backfill` as the 72)
Full-window (2014–2026) evidence exists for all 24 in `derived_revalidation_status.csv`:
**16 OOS-stable** (12 composites + all 4 industry-rel), 7 `draft`, 1 `deprecated`
(`comp_anti_risk`, collapsed). Plan: promote the 16 (exclude the 8), same caveats as the 72
(IS-only validator uncontaminated; candidate ≠ approved; **2021–2026 burned** → a future
candidate→approved needs a genuinely-sealed window). Several "candidate" composites have
NEGATIVE OOS ICIR but high sign-consistency (`comp_momentum_quality` −0.41, `comp_52w_position`
−0.32) — sign-stable inverse predictors; the IS gate's `|rank_icir|≥0.10 ∧ sign_consistency≥0.70`
admits them (Phase 6 likewise admitted negative-ICIR reversal/low-vol factors).

## 5. The 5 open questions (my recommended answers in brackets)
1. Is the same-date-cross-sectional leakage argument airtight, or can `add_composites` /
   `add_industry_relative_composites` / `build_industry_series_asof` pull a value dated after
   `r(t)` into a factor date `≤ is_end`? [I claim airtight — all per-date.]
2. Unified single panel (base+composite+industry-rel in one `IsWindowedPanel`/one walk_forward)
   vs separate panels? [Unified — simpler, shares the label, identical belts.]
3. Sign-agnostic admission of negative-ICIR composites? [Yes — consistent with Phase 6.]
4. Promote the 16 OOS-stable vs promote-all-that-pass-IS? [16 OOS-stable — precedent-consistent.]
5. Add `$total_mv` to the industry-rel field-eligibility check now (defense-in-depth; only
   `mom_idio_20d` uses it, and `$total_mv` is `approved`)? [Yes — cheap.]
6. Is an order-ASSERT on the base panel sufficient for the `cs_rank` positional-level fragility,
   or should `cs_rank` itself be made name-based (`groupby(level="datetime")`)? [Recommend: assert
   in the Layer-2 builder now (minimal, local); a name-based `cs_rank` hardening is a separate
   follow-up since it is shared code under ~42 call sites and needs its own test sweep.]

## 6. Verdict requested
GO to build (with any required changes to the 5 answers), or NO-GO with specific leakage/soundness findings.
