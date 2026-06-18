# CICC Wave E1d — 量价相关性 / price-volume correlation (chart 40) factor-logic spec

> Pre-registration factor logic for the E1d tranche, to be GPT-reviewed BEFORE registration (mirrors
> the E1a/E1b/E1c logic reviews). Source: handbook chart 40 in
> [CICC_价量因子定义.md](../../../Knowledge/AI量化增强/CICC_价量因子定义.md) §4 (量价相关性因子, 8). **Claim:
> NO custom operator needed** — all 8 are inline `Corr(...)` (Qlib built-in, already used by the unwired
> `price_vol_corr` operator) + `Ref` shifts. The manifest's pre-registered `lead_lag_corr` should be
> DROPPED (exactly as E1c dropped the stale `kbar_shortcut`).

## Scope: 3 sub-families × {sync, lead, lag} = 8 (single 20d window — handbook chart 40 is 1M only)

Handbook §4: "均为过去 20 个交易日的相关系数；'prior/post' 指领先/滞后 1 日。三小类：价格相关、量能领先、量价同步。"

| handbook code | construction | 中金 sub-type | our name |
|---|---|---|---|
| corr_price_turn_1M | corr(turnover_t, close_t) over 20d | 量价同步 (sync) | `corr_price_turn_20d` |
| corr_price_turn_post_1M | corr(turnover_t, close_{t+1}) | 量能领先 (turnover leads) | `corr_price_turn_post_20d` |
| corr_price_turn_prior_1M | corr(turnover_t, close_{t−1}) | 价格领先 (price leads) | `corr_price_turn_prior_20d` |
| corr_ret_turn_1M | corr(turnover_t, ret_t) | 量价同步 | `corr_ret_turn_20d` |
| corr_ret_turn_post_1M | corr(turnover_t, ret_{t+1}) | 量能领先 | `corr_ret_turn_post_20d` |
| corr_ret_turn_prior_1M | corr(turnover_t, ret_{t−1}) | 价格领先 | `corr_ret_turn_prior_20d` |
| corr_ret_turnd_1M | corr(Δturnover_t, ret_t) | 量价同步 | `corr_ret_turnd_20d` |
| corr_ret_turnd_prior_1M | corr(Δturnover_t, ret_{t−1}) | 价格领先 | `corr_ret_turnd_prior_20d` |

(`corr_ret_turnd` has NO `post` variant in the handbook → sync + prior only = 2; matches the manifest
comment `corr(Δturn, ret) sync/lag = 2`. Total 3+3+2 = **8**.)

**Naming note (faithful-replication):** kept the handbook's `_post`/`_prior`. Semantics are NON-obvious:
`post` = price is POSTerior (t+1) → **turnover leads**; `prior` = price is PRIOR (t−1) → **price leads**.
Documented per-row below + in the catalog comment. (Open to `_vlead`/`_plead` if GPT prefers clarity over
handbook fidelity.)

## Base series (all PIT lag-1; fields all approved: `$turnover_rate`, `$close`, `$adj_factor`)

```
turn1  = Ref($turnover_rate, 1)                         # turnover at T−1
close1 = ADJ_CLOSE_T1 = Ref($close * $adj_factor, 1)    # ADJUSTED close at T−1 (split-robust)
ret    = DAILY_RET = (ADJ_CLOSE_T1 / Ref(ADJ_CLOSE, 2) − 1)   # adjusted daily return realized at T−1
turnd  = turn1 − Ref($turnover_rate, 2)                 # Δturnover = turn[T−1] − turn[T−2]
```

## The 8 inline expressions (lead/lag realized by shifting the LEADING series BACK — never forward)

```
1. corr_price_turn_20d        = Corr(turn1,          close1,          20)   # sync
2. corr_price_turn_post_20d   = Corr(Ref(turn1, 1),  close1,          20)   # turnover LEADS close
3. corr_price_turn_prior_20d  = Corr(turn1,          Ref(close1, 1),  20)   # close LEADS turnover
4. corr_ret_turn_20d          = Corr(turn1,          ret,             20)   # sync
5. corr_ret_turn_post_20d     = Corr(Ref(turn1, 1),  ret,             20)   # turnover LEADS ret
6. corr_ret_turn_prior_20d    = Corr(turn1,          Ref(ret, 1),     20)   # ret LEADS turnover
7. corr_ret_turnd_20d         = Corr(turnd,          ret,             20)   # sync
8. corr_ret_turnd_prior_20d   = Corr(turnd,          Ref(ret, 1),     20)   # ret LEADS Δturnover
```

## PIT-safety argument (the load-bearing claim — please scrutinize)

The handbook's "corr(turn_t, close_{t+1})" is computed WITHIN the trailing 20d window as-of the eval date
T, so both legs are in the past — it is NOT a forward reference. The PIT-safe realization shifts the
**leading** series further back (`Ref(turn1,1)`), pairing `turn[t−1]↔close[t]` over the window — which is
the same lead relationship as `turn[t']↔close[t'+1]` (relabel t'=t−1), with the latest pair at indices
`(T−2, T−1)`, strictly `< T`. **No leg ever uses a forward `Ref(..., −1)`.** Every `$field` sits inside a
`Ref(..., ≥1)` frame, so the PIT lint (`lint_no_unsafe_pit_dates` / `test_factor_library_pit_safety`
stack-walk) and the behavioral PIT test (factor[T] ⊥ close[T]) both pass by construction. The lead/lag legs
are even stricter (≤ T−2).

## No custom operator (drop `lead_lag_corr`)

`Corr` is a Qlib built-in (the unwired `price_vol_corr` operator already uses it). The lead/lag is pure
`Ref` arithmetic. So — exactly as E1c dropped the stale `kbar_shortcut` — the chart-40 manifest rows should
**drop `required_operators: [lead_lag_corr]`** and carry `catalog_factor_id` only. (Alternative: build +
certify a `lead_lag_corr(a, b, lead, window)` operator for a golden-value lock on the shift direction. The
inline form is preferred for consistency with E1c, but I'll defer to GPT if the lead/lag subtlety warrants
certification.)

## Dedup vs existing catalog

- **No existing `corr_*` catalog factor** (grep clean). These 8 are genuinely new.
- The closest relative, the **`price_vol_corr` operator, is UNWIRED** (defined, never wired into a catalog
  factor) and uses `Corr(ret, $vol_pct_change)` — RAW volume **ratio** change, not turnover. `corr_ret_turnd`
  uses `Corr(Δturnover, ret)` — turnover **difference**. Distinct series (turnover vs raw volume; difference
  vs ratio) → **not a dedup**.
- The 3 families are mutually distinct (price LEVEL vs return; turnover level vs Δturnover).

**→ 8 new drafts, 0 dedup.**

## Price basis

- `corr_price_turn*` correlate turnover with the **adjusted** close LEVEL (`ADJ_CLOSE_T1`): a split would
  otherwise inject a spurious step into the 20d price-level series → adjusted is the correct, split-robust
  basis. `corr_ret_turn*`/`corr_ret_turnd*` use the adjusted `DAILY_RET`. `$turnover_rate` is the raw
  normalized ratio; `turnd` is its first difference.

## GPT verdict (2026-06-18): **APPROVE for draft registration** — no operator build; 1 non-blocking test req

GPT confirmed all 6 points: (1) lead/lag PIT-safe and **directionally correct** in both directions (shift
the leader back for `post`, the counterpart back for `prior`; no forward `Ref`, latest pair `< T`); (2) drop
`lead_lag_corr` — pure `Corr`+`Ref`, no certified operator; (3) adjusted close level + adjusted return + raw
turnover correct; (4) **8 new / 0 dedup** confirmed (`price_vol_corr` unwired + raw-volume-ratio ≠ turnover
diff); (5) keep `_post`/`_prior` for handbook fidelity **+ add explicit `lead_lag_semantics` mapping** (don't
rename to `_vlead`/`_plead`); (6) **20d only** — do NOT add 60/120 (those would be exploratory, not faithful
chart-40 replication).

**Non-blocking requirement (before matrix/P-GATE, NOT before draft registration):** a lightweight
**golden-value lead/lag direction test** (expression/golden, NOT `OperatorCertification`): toy panel
`turnover=[1,2,3,…]`, `close=ret=turnover shifted +1`; assert the `post` expression peaks when turnover
leads, `prior` peaks when price/return leads, and **no expression uses `Ref(…,−1)`**. Plus the standard
guards: PIT lint (existing stack), warmup/runway discipline (as E1a/E1b), manifest drops `lead_lag_corr`.

## Plan (GPT-approved)

Define 8 inline factors (no operator) **with `lead_lag_semantics` catalog comments** → register draft →
**golden lead/lag direction test** → v2 manifest expand chart-40 (8 factor-level rows + `catalog_factor_id`,
drop `lead_lag_corr`) → 7-domain matrix → import → P-GATE → IS-gate. resolve-but-label; no promotion here.
a_priori; 2021+ sealed.
