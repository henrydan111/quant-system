# CICC Wave E1g — 北向资金 / northbound (chart 76) factor-logic spec

> Pre-registration factor logic for the E1g tranche, to be GPT-reviewed BEFORE registration (mirrors
> the E1a–E1f logic reviews). Source: handbook chart 76 in
> [CICC_价量因子定义.md](../../../Knowledge/AI量化增强/CICC_价量因子定义.md) §7 (北向资金流因子, 9-10). Data:
> Tushare `hk_hold` (approved) — `$ratio` (holding % of **ISSUED** shares per doc 188) + `$north_hold_vol`
> (holding shares, registered approved 2026-06-20). **NO custom operator** — all inline.

## GPT verdict (2026-06-20): CHANGES REQUIRED → **Plan C APPROVED** (4 faithful, with `$north_hold_vol`)

GPT approved the direction (defer unsupported, inline, mask, spent-OOS resolve-but-label) but blocked the
original ratio-only "4 faithful" claim on two points, both folded in:
- **VWAP proxy not faithful from `$ratio` alone** — `ratio×VWAP` assumes the share-base cancels, but hk_hold
  also exposes `vol` (holding shares). → adopted **Plan C**: registered `$north_hold_vol` (already
  materialized via `NORTHBOUND_RENAMES`; registry flip, no rebuild) and the two value-based factors now use
  **`hv = $north_hold_vol × VWAP`** (faithful holding-VALUE, no share-base assumption). Also: doc 188 says
  `$ratio` is **% of issued shares** (not free-float) → the ratio-only factors are faithful to the issued-
  share field, close to but not exact to CICC's `流通股本` (recorded on the manifest rows + data_dictionary).
- **Prefer-family defer rationale corrected** — the *level* `north_hold_prefer` IS a cross-sectional rank-
  alias of `north_hold_pct`, but `prefer_st_chg`/`prefer_lt_chg` are NOT aliases (the cs-mean varies over
  time); they're deferred because they need a **cross-sectional materialization path** Qlib per-instrument
  expressions can't express — NOT because they're aliases. (Q2: mean baseline confirmed; Q4: keep explicit
  `If(r>0)` mask; Q5: spent-OOS/short-window framing confirmed; Q6: no operator confirmed.)

## Three load-bearing caveats (E1g is qualitatively different from E1a–E1f)

1. **The north family's 2021-2026 OOS is ALREADY SPENT** (`oos_eligibility: spent_same_family` in the frozen
   manifest). The arXiv D4 batch (2026-06-10) sealed-OOS-tested `north_hold_change_{20,60}d_cov` and they
   **sign-flipped** (foreign-accumulation→continuation reversed in the 2021+ outflow era). → the IS-gate
   (draft→candidate, IS-only 2010-2020) is valid, but the candidate→approved path via a fresh 2021+ OOS is
   **foreclosed** for this family. Promote resolve-but-label only.
2. **Short IS window.** `hk_hold` starts 2017 → only **2017-2020** (~3.5y) lies inside the 2010-2020 IS window
   → weaker, noisier IS evidence; partial-window in the matrix.
3. **Coverage masking.** ~half the universe has `$ratio = 0` (non-Connect names). Every E1g factor masks to
   the held sub-universe via `If(Ref($ratio,1) > 0, …, np.nan)` (the established arXiv-D4 cov-variant pattern)
   so the cross-section ranks only northbound-held names.

## Scope: 10 handbook factors → 4 faithful NEW + dedups/defers

| handbook | construction | disposition |
|---|---|---|
| north_hold_prop | 持仓量/流通股本 = `$ratio` | **DEDUP** → existing `north_hold_pct` (`Ref($ratio,1)`) |
| north_hold_prop_st_chg / north_hold_st_chg | ratio − mean(ratio,20) | **NEW** (mean-deviation; distinct from the point-to-point `north_hold_change_20d`) |
| north_inflow_shift_dist (+细分) | Σ(Δratio,20) / Σ(\|Δratio\|,20) | **NEW** (位移路程比; inline, drop `shift_distance_ratio`) |
| north_excess_hold_st | (ratio·VWAP)ₜ / mean(ratio·VWAP,20) − ret₂₀ | **NEW** (VWAP; free-float cancels in the ratio) |
| north_trade_prop | (ratio·VWAP)ₜ / mean(ratio·VWAP,20) / Σ(amount,20) | **NEW** (VWAP; float cancels) |
| north_hold_prefer (+st/lt chg) | ratio / cross-sectional-market-avg(ratio) | **DEFER** (see Q1 — rank-alias + not Qlib-expressible) |

**Q1 — the prefer family is a cross-sectional RANK-ALIAS + not per-instrument-expressible.** `north_hold_prefer
= ratio / cs_mean(ratio)`: `cs_mean(ratio)` is a per-DATE constant across stocks, so dividing by it PRESERVES
the cross-sectional rank → **RankIC identical to `north_hold_pct`** (the existing `$ratio` factor). And Qlib
factor expressions are per-INSTRUMENT time-series — they cannot reference a cross-sectional mean at all. → I
**DEFER** the whole prefer family (prefer / prefer_st_chg / prefer_lt_chg). Confirm, or is there a sanctioned
cross-sectional path that would make `prefer_st_chg` (a time-path of the cs-rescaled quantity) non-aliased?

## The 4 NEW factors (PIT lag-1; masked to held sub-universe; guarded NaN-not-inf)

```
r      = Ref($ratio, 1)                                   # holding % at T-1 (masked: factor = If(r>0, …, NaN))
vwap   = Ref($amount, 1) / guard(Ref($vol, 1))            # VWAP at T-1
hv     = r * vwap                                         # holding-VALUE proxy (ratio×VWAP; free-float cancels)
ret20  = ADJ_CLOSE_T1 / Ref(ADJ_CLOSE, 21) - 1            # 20d adjusted return

1. north_hold_prop_st_chg = r - Mean(r, 20)
2. north_inflow_shift_dist = Sum(Delta(r,1), 20) / guard(Sum(Abs(Delta(r,1)), 20))     # ∈ [−1,1]
3. north_excess_hold_st   = hv / guard(Mean(hv, 20)) - ret20
4. north_trade_prop       = (hv / guard(Mean(hv, 20))) / guard(Sum(Ref($amount,1), 20))
```
`guard(x) = _nan_if_nonpos(x)`. All four wrapped in `If(r > 0, …, np.nan)` (coverage mask). Note
`Sum(Delta(r,1),20)` telescopes to `r[t]−r[t−20]` (= `north_hold_change_20d`), so `#2` is that change
NORMALIZED by gross flow `Σ|Δr|` — a new construction, not a dup.

## GPT questions

- **Q1 (prefer family defer).** Rank-alias of `north_hold_pct` + not Qlib-expressible → defer. Confirm.
- **Q2 (sum vs mean in the excess/trade denominators).** Handbook "/(20交易日 VWAP×持仓)" — I read it as the
  20d MEAN of `ratio·VWAP` (so the current/avg ratio ~1), not the sum. Confirm.
- **Q3 (VWAP proxy validity).** `hv = ratio·VWAP` as a holding-VALUE proxy: free-float cancels in the
  current/average ratio (`excess`, `trade`), so the missing raw holding-volume is not needed. Sound?
- **Q4 (masking).** `If(ratio>0, …, NaN)` to the held sub-universe (cov-variant pattern). The guards already
  NaN the degenerate ratio=0 stocks (Δr=0, hv=0 → 0/0) — is the explicit `If` mask still preferred for clarity?
- **Q5 (spent-OOS / short-window).** Given `spent_same_family` + the 2017-2020 IS window, promote the passers
  resolve-but-label, no fresh-OOS approval path. Confirm this is the right framing.
- **Q6 (no operator).** `shift_distance_ratio` dropped (inline `Sum/Sum`), as E1c/E1d/E1f dropped theirs.

## Plan (pending GPT APPROVE)

Define 4 guarded+masked inline factors (no operator) → register draft → v2 manifest expand chart-76 (4
factor-level rows + `catalog_factor_id`, drop `shift_distance_ratio`; record the prefer-family defer + dedup) →
7-domain matrix → import → P-GATE → IS-gate. resolve-but-label; no promotion beyond candidate (OOS spent).
a_priori; short IS window (2017-2020). Expected weaker/selective IS (cf. E1f).
