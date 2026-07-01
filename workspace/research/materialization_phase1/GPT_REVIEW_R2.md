ROLE
You are the same senior reviewer. This is round 2 — confirm your R1 findings on the stk_holdertrade
高管 directional materialization are correctly folded, and give a final SHIP / REVISE / REWORK.

REPO (public — the fold IS PUSHED at commit ada3c87)
https://github.com/henrydan111/quant-system   (branch: report-rc-registration)
- src/data_infra/pit_backend.py — new module fn `aggregate_directional_holdertrade` (~line 838) +
  the rewired `_materialize_stk_holdertrade` (~line 2590)
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/src/data_infra/pit_backend.py
- tests/data_infra/test_holdertrade_directional.py — the canary you required
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/tests/data_infra/test_holdertrade_directional.py
- data/data_dictionary.md — the amount partial-coverage contract (M2)
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/data/data_dictionary.md

YOUR R1 VERDICT = REVISE (no Blocker). Folds below.

## M1 (Major) — amount = 0 on all-unpriced days → FIXED
The directional aggregation is now a pure module-level fn using min_count=1 for amount ONLY:
```python
def aggregate_directional_holdertrade(sub: pd.DataFrame, prefix: str) -> tuple[pd.DataFrame, list[str]]:
    fields = [f"{prefix}_vol", f"{prefix}_amount", f"{prefix}_ratio", f"{prefix}_events"]
    if sub.empty:
        return pd.DataFrame(columns=["qlib_code", "effective_date", *fields]), fields
    cv = pd.to_numeric(sub["change_vol"], errors="coerce").abs()        # m2: magnitude guard
    work = pd.DataFrame({
        "qlib_code": sub["qlib_code"].to_numpy(),
        "effective_date": sub["effective_date"].to_numpy(),
        "_vol": cv.to_numpy(),
        "_amount": (cv * pd.to_numeric(sub["avg_price"], errors="coerce")).to_numpy(),
        "_ratio": pd.to_numeric(sub["change_ratio"], errors="coerce").to_numpy(),
        "_events": 1.0,
    })
    out = (
        work.groupby(["qlib_code", "effective_date"], sort=False)
        .agg(**{
            f"{prefix}_vol": ("_vol", "sum"),
            f"{prefix}_amount": ("_amount", lambda s: s.sum(min_count=1)),   # M1: all-unpriced -> NaN
            f"{prefix}_ratio": ("_ratio", "sum"),
            f"{prefix}_events": ("_events", "sum"),
        })
        .reset_index()
    )
    return out, fields
```
`_materialize_stk_holdertrade` now calls it on the two 高管 subsets (existing all-holder
net/gross/net_ratio/events block UNCHANGED):
```python
        is_mgr = holder_type == "G"
        mgr_in_agg, mgr_in_fields = aggregate_directional_holdertrade(
            ledger[is_mgr & (in_de == "IN")], "holdertrade_mgr_in")
        mgr_de_agg, mgr_de_fields = aggregate_directional_holdertrade(
            ledger[is_mgr & (in_de == "DE")], "holdertrade_mgr_de")
```

## m1 (Minor) — `change_vol[mask].values` positional assignment → REMOVED
Replaced by attaching numeric columns inside the pure fn (no positional `.values` onto a masked frame).

## m2 (Minor) — directional magnitude → FOLDED + verified
`vol`/`amount` use `abs(change_vol)`. Verified empirically: the ledger's `change_vol` has 0 negatives
(min 1.0, max 4e9) and `change_ratio` 0 negatives, so abs is a no-op today and a guard if the feed
changes. Canary `test_vol_is_positive_magnitude_even_if_change_vol_negative` pins it.

## m3 (Minor) — duplicate `qlib_code` columns in `pd.concat(axis=1)` → FIXED
`_per_symbol` now `.drop(columns=["qlib_code"]).set_index("effective_date")`.

## M2 (Major) — partial-coverage contract → DOCUMENTED
data_dictionary now states: `amount` = Σ(|change_vol|·avg_price) over PRICED events only; partial-priced
day = lower-bound priced-event sum (vol/ratio/events complete); ALL-unpriced day = NaN, not 0.0.
(The field-status approval YAML will carry the same contract at registration, post-publish.)

## EVIDENCE (the canary you required, run fresh)
- `tests/data_infra/test_holdertrade_directional.py` — **6 passed** (all-unpriced→NaN,
  partial-priced lower-bound, fully-priced full-sum, magnitude, grouping, empty-subset).
- Sandbox re-build (folded code), 600157_sh 高管-IN: vol/amount/ratio/events MATCH an independent
  new-logic ledger re-aggregation; the basket carries 21 all-unpriced 高管-IN day-stocks that
  exercise the min_count=1 path; `holdertrade_net_vol` BYTE-IDENTICAL staged-vs-live (no regression).
- Full v2 provider rebuild (folded code) is running; publish + field-status registration + re-bind
  happen only after it completes and after your SHIP.

REVIEW REQUEST
Confirm M1/M2/m1/m2/m3 are correctly resolved with no new issue (esp. the named-agg lambda
`min_count=1` semantics and the per-symbol concat after the dedup). Any residual before I publish +
register? Final line: SHIP / REVISE / REWORK + the single most important residual risk.
