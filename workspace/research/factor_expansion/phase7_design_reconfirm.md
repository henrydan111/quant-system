# DESIGN v2 Re-confirmation (for GPT) — composite/industry-rel gating

You conditionally-GO'd the Phase-7 design (extend the IS-only factor gate to 20 composite + 4
industry-relative factors). All conditions are integrated below. This is a SHORT re-confirm:
verify the concrete `cs_rank`-class hardening is correct and nothing else blocks the build.

## Your conditions → integrated
1. **`cs_rank` positional-`level=0` is a PIT lookahead leak (not just correctness)** — accepted &
   re-framed. Fix = harden the cross-sectional helpers to group by the `datetime` level by NAME
   (not just an assert). Concrete code below.
2. Sign-agnostic admission of negative-ICIR composites, but **record signed `rank_icir` +
   `expected_direction`** (don't imply long-only-positive). Integrated.
3. **Phase-7 funnel artifact + ledger event** for the full 24 → 16 `oos_informed_backfill`
   surface (mirror Phase 6). Integrated.
4. **Add `$total_mv` to the industry-rel field-eligibility check** (real dep of `mom_idio_20d`).
   Integrated.
5. **`out_date` is INCLUSIVE** (`in_date ≤ t ≤ out_date`; only `t > out_date` invalidates) —
   wording corrected; boundary convention, not a leak. Integrated.

## Concrete hardening of the 4 shared helpers (operators.py)
A single name-based date-level resolver, used by all four. Behavior-PRESERVING for every current
caller (all pass `(datetime, instrument)` from `compute_factors`), fixes only the wrong-order leak:

```python
def _date_level_key(series):
    """groupby key for a per-DATE cross-section. Prefer the level NAMED 'datetime' (robust to
    (datetime,instrument) vs (instrument,datetime)); else the datetime-TYPED level by dtype;
    else FAIL CLOSED — a cross-sectional-per-date op on a series with no datetime level is a
    misuse and must not silently fall back to positional level 0 (the leak path)."""
    names = list(series.index.names)
    if "datetime" in names:
        return "datetime"
    for i in range(series.index.nlevels):
        if pd.api.types.is_datetime64_any_dtype(series.index.get_level_values(i)):
            return i
    raise ValueError("cross-sectional op requires a 'datetime' MultiIndex level; none found")

def cs_rank(series):
    return series.groupby(level=_date_level_key(series)).rank(pct=True)

def cs_zscore(series):
    key = _date_level_key(series)
    mean = series.groupby(level=key).transform('mean')
    std = series.groupby(level=key).transform('std')
    return (series - mean) / std

def cs_demean(series):
    return series - series.groupby(level=_date_level_key(series)).transform('mean')

def winsorize(series, lower=0.01, upper=0.99):
    key = _date_level_key(series)
    def _clip_group(g): return g.clip(g.quantile(lower), g.quantile(upper))
    return series.groupby(level=key).transform(_clip_group)
```

Plus a **local builder assert** in `load_is_windowed_panel_with_layer2`:
`assert list(base_panel.index.names) == ["datetime", "instrument"]` before `add_composites`
(belt-and-suspenders; `compute_factors` guarantees it).

Tests: per-helper **order-invariance** (build the same fixture in both index orders → identical
per-date output) + a **leakage-specific** test (a per-stock-time-series mis-grouping would make
`factor[t]` depend on `value[t+k]`; assert mutating `value[t+k]` does NOT change `cs_rank` at `t`)
+ the full operators/factor-library test sweep (shared code under ~42 call sites).

## The one decision I want you to confirm
`_date_level_key` **fails closed** (raises) when no `datetime`-named AND no datetime-typed level
exists, rather than falling back to positional level 0. This is the safe choice (positional-0
fallback is exactly the leak path), but it COULD raise for a legacy caller that passes an
oddly-named/single-level index. I judge fail-closed correct (a cross-sectional op genuinely needs
a date level; the full test sweep will catch any real caller that breaks). **Confirm fail-closed,
or do you want a logged positional-0 fallback for back-compat?**

## Verdict requested
Confirm GO to build v2 (with the hardening as written), or flag any residual leakage/soundness
issue. Scope of the build: the 4-helper hardening + tests; the Layer-2 IS-only builder +
`dataset_build` change; `$total_mv` field-check; signed-ICIR/direction recording. NO run yet
(the operational promote-the-16 run is the subsequent step, mirroring Phase 6).
