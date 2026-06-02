# IMPLEMENTATION Cross-Review (for GPT) — Phase 7 composite/industry-rel gating (commit c91cda9)

You GO'd the Phase-7 design v2 (extend the IS-only factor gate to 20 composite + 4
industry-relative factors; harden the cross-sectional helpers against the positional-level
PIT leak). This is the IMPLEMENTATION review — verify the code matches the GO'd design and find
any residual leak/bug. No repo access; actual committed code embedded. 178 tests pass (only the
2 documented pre-existing failures elsewhere). NO run yet.

## 1. The leak fix — all 4 helpers now name-based + fail-closed (operators.py)
```python
def _date_level_key(series):
    """Prefer the level NAMED 'datetime' (robust to either order); else the datetime-TYPED
    level by dtype; else FAIL CLOSED. A positional level-0 fallback is the leak path and is
    intentionally NOT provided."""
    names = list(series.index.names)
    if "datetime" in names:
        return "datetime"
    for i in range(series.index.nlevels):
        if pd.api.types.is_datetime64_any_dtype(series.index.get_level_values(i)):
            return i
    raise ValueError("cross-sectional op requires a 'datetime' MultiIndex level; none found ...")

def cs_rank(series):
    return series.groupby(level=_date_level_key(series)).rank(pct=True)

def cs_zscore(series):
    key = _date_level_key(series)
    mean = series.groupby(level=key).transform('mean')
    std = series.groupby(level=key).transform('std')
    return (series - mean) / std.replace(0, np.nan)        # zero-std -> NaN preserved (your must-keep)

def cs_demean(series):
    return series - series.groupby(level=_date_level_key(series)).transform('mean')

def winsorize(series, lower=0.01, upper=0.99):
    key = _date_level_key(series)
    def _clip_group(g): return g.clip(g.quantile(lower), g.quantile(upper))
    return series.groupby(level=key).transform(_clip_group)
```
Tests (`test_cross_sectional_helpers.py`, 10): order-invariance for all 4 (same per-date result
in both index orders); `test_mutating_future_value_does_not_change_current_rank` — mutate stock
0's LAST-date value below its first-date value, assert the FIRST date's rank is unchanged (a
per-stock grouping — the leak — would shift it). I verified this test FAILS on the pre-fix
`groupby(level=0)` (the pre-fix first-date rank DID change). Plus zero-std→NaN and fail-closed.

## 2. The Layer-2 IS-only builder (walk_forward_validation.py) — full function
```python
def load_is_windowed_panel_with_layer2(*, gated_base, gated_composite_defs, gated_industry_defs,
        time_split, horizon=DEFAULT_HORIZON, qlib_dir=None, trade_cal=None,
        compute_factors_fn=None, industry_series_fn=None, adj_close_expr=None):
    cf = compute_factors_fn or operators.compute_factors
    adj_expr = adj_close_expr or operators.ADJ_CLOSE
    base_catalog = get_factor_catalog(include_new_data=True)
    dep = set(gated_base)
    for d in gated_composite_defs: dep.update(d.get("components", []))
    for d in gated_industry_defs:
        if d.get("base"): dep.add(d["base"])
    dep = sorted(x for x in dep if x)
    missing = [x for x in dep if x not in base_catalog]
    if missing: raise ValueError(... )                      # dep base absent from catalog -> hard error
    base_panel, _ = cf(catalog={n: base_catalog[n] for n in dep}, start_date=is_start,
                       end_date=is_end, horizons=None, ...)  # belt 1: horizons=None over [is_start,is_end]
    adj_panel, _  = cf(catalog={"adj_close": adj_expr}, start_date=is_start, end_date=is_end, horizons=None, ...)
    panel = base_panel
    if gated_composite_defs or gated_industry_defs:
        if list(base_panel.index.names) != ["datetime", "instrument"]:   # belt-and-suspenders order assert
            raise IsEndLeakageError(...)
    if gated_composite_defs:
        panel = operators.add_composites(panel, gated_composite_defs, progress_every=0)
    if gated_industry_defs:
        industry = (industry_series_fn or _default_industry_series)(panel.index)  # PIT-safe SW2021 L1
        mcap = None
        if any(bool(d.get("requires_market_cap")) for d in gated_industry_defs):
            mcap_panel, _ = cf(catalog={"market_cap": "Ref($total_mv, 1)"}, ...)   # shifted, approved
            mcap = mcap_panel["market_cap"]
        panel = operators.add_industry_relative_composites(panel, industry, market_cap=mcap,
                                                           defs=gated_industry_defs, progress_every=0)
    gated_cols = list(gated_base) + [d["name"] for d in gated_composite_defs] + [d["name"] for d in gated_industry_defs]
    missing_cols = [c for c in gated_cols if c not in panel.columns]
    if missing_cols: raise ValueError(...)
    return build_is_windowed_panel(panel[gated_cols], adj_panel["adj_close"], is_end=is_end, horizon=horizon, trade_cal=trade_cal)
```
`build_is_windowed_panel` is UNCHANGED (the Phase-6-reviewed exact-calendar `r(t)` label + belts).
**Dependency-only bases** (composite components / industry-rel bases not in `gated_*`) are in
`dep` (computed as inputs) but NOT in `gated_cols` → excluded from verdicts. Tests
(`test_factor_lifecycle_walk_forward.py::Layer2PanelTests`): (a) gated cols ==
{base, composite, industry-rel}, dependency-only bases EXCLUDED; (b) `max_label_realization_date
<= is_end`; (c) composite ∈ [0,1] (rank-avg) and computed; (d) base-only (empty defs) ==
`load_is_windowed_panel`; (e) an `(instrument, datetime)` base panel raises `IsEndLeakageError`
(the order assert) before any Layer-2 compute.

## 3. dataset_build split (factor_lifecycle_steps.py)
```python
gated_base     = sorted(n for n in eligible if n in full)                  # base catalog
gated_composite= sorted(n for n in eligible if n in composite_defs_all)
gated_industry = sorted(n for n in eligible if n in industry_defs_all)
unknown        = sorted(n for n in eligible if n not in full and n not in composite_defs_all and n not in industry_defs_all)
if unknown: raise ValueError(...)                                          # no silent drop
if not (gated_base or gated_composite or gated_industry): raise ValueError(...)
panel = load_is_windowed_panel_with_layer2(gated_base=gated_base,
            gated_composite_defs=[composite_defs_all[n] for n in gated_composite],
            gated_industry_defs=[industry_defs_all[n] for n in gated_industry], ...)
```
(No `non_base_deferred` bucket anymore.) Field-ineligible factors are already excluded upstream
by the resolver's per-factor `field_eligible`; they never enter `eligible`.

## 4. `$total_mv` in the industry-rel field-eligibility check (factor_lifecycle_steps.py)
```python
if name in industry:
    d = industry[name]; base = str(d.get("base", ""))
    if base not in catalog: return None
    exprs = [catalog[base]]
    if d.get("requires_market_cap"):
        exprs.append("Ref($total_mv, 1)")     # field gate now SEES the real mcap dep of mom_idio_20d
    return exprs
```

## 5. `expected_direction` recording (walk_forward_validation.py)
```python
def _expected_direction(icir):
    if icir is None or pd.isna(icir) or icir == 0: return "undetermined"
    return "positive" if icir > 0 else "inverse"
# added to every verdict row (both generated + a_priori branches):
#   {..., "heldout_rank_icir": heldout (SIGNED), "expected_direction": _expected_direction(heldout)}
```
The evidence row (`record_lifecycle_evidence`) already stores the SIGNED `is_rank_icir`
(= heldout ICIR); I did NOT add an `expected_direction` COLUMN to the `factor_evidence` schema
(it would be a schema change), reasoning that the signed `is_rank_icir` already encodes direction
on the evidence row and the explicit label lives on the verdict rows + (next step) the funnel
artifact. **Confirm this is sufficient, or do you want `expected_direction` persisted as an
evidence/master column too?**

## 6. Verification asks
1. Is the leak fix COMPLETE — all positional `groupby(level=0)` cross-sectional ops converted,
   fail-closed correct, no residual? (You earlier named `cs_rank`/`cs_zscore`/`cs_demean`; I also
   found+fixed `winsorize`. `operators.neutralize` you flagged as non-Phase-7 — confirmed Phase 7
   uses `neutralize_size_industry` which normalizes, so it's untouched here.)
2. Does `load_is_windowed_panel_with_layer2` preserve the `is_end` boundary for BOTH composites
   and industry-relative, and is the dependency-only-base EXCLUSION correct (no gated verdict for
   a non-gated component)?
3. Is `expected_direction` on the verdict row + signed `is_rank_icir` on the evidence row
   sufficient (vs an evidence-schema column)?
4. Any edge case: empty-defs base-only equivalence; `market_cap` loaded only when a def needs it;
   the order assert firing only when Layer-2 ops run (base-only path stays order-robust via
   `build_is_windowed_panel`)?

## 7. Verdict requested
GO to merge PR (then proceed to the operational promote-16 `oos_informed_backfill` run), or
NO-GO with specific findings.
