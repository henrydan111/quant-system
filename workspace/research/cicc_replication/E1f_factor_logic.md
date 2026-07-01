# CICC Wave E1f — 资金流 / capital flow (chart 64) factor-logic spec

> Pre-registration factor logic for the E1f tranche, to be GPT-reviewed BEFORE registration (mirrors
> the E1a/E1b/E1c/E1d logic reviews). Source: handbook chart 64 in
> [CICC_价量因子定义.md](../../../Knowledge/AI量化增强/CICC_价量因子定义.md) §6 (资金流因子, 32). Data:
> Tushare `moneyflow` (approved). **Claim: NO custom operator** — all inline `Sum`/`Ref`/division.

## Scope: 32 handbook factors → 9 FAITHFUL registered (大小单 active-net, path A) + the rest DEFERRED

> ⚠ The "18" in the original draft below was REDUCED to **9 faithful active-net factors (path A)** by the GPT
> factor-logic review — the 9 "buy" factors are affine aliases / unbuildable-total-buy proxies. See the
> **GPT verdict** section. (Of the 9 registered, the IS-gate later promoted only 3 — E1f is selective.)

The handbook splits chart 64 into two sub-families:
1. **大小单资金流向 (large/small-order flow)** — replicable from `moneyflow`'s order-size components. **THIS WAVE.**
2. **开盘/尾盘资金流向 (open/close-segment flow)** — `inflow_*_open` / `inflow_*_close`. **DEFERRED**: daily
   `moneyflow` has NO intraday open/close split (the frozen manifest already marks these `proxy_approx`).
   Faithful replication needs an intraday/tick moneyflow source — a separate ingestion (cf. E1e/cyq_chips).
   NOT registered here; recorded as a known gap.

(Handbook lists ~28 named + 4 window/variant. This draft first proposed 18 大小单 factors; GPT review reduced
to the **9 faithful active-net 大小单** factors — see the GPT verdict section.)

## Data (all PIT-lag-1 — `moneyflow` is a same-day OUTCOME, trade_date-anchored, knowable at close T)

`moneyflow` components (万元), size ∈ {sm, md, lg, elg} = handbook {s, m, l, xl}:
```
$buy_{size}_amount   $sell_{size}_amount        # active buy / active sell by order size
net_size   = Ref($buy_{size}_amount,1) - Ref($sell_{size}_amount,1)     # net active inflow
gross_size = Ref($buy_{size}_amount,1) + Ref($sell_{size}_amount,1)     # gross activity
total_net   = Σ_size net_size      total_gross = Σ_size gross_size       total_buy = Σ_size buy_size
```
⚠ Do NOT use `$net_mf_amount` — it is an OPAQUE vendor net (data_dictionary: best corr ~0.51 to the
component net, 0% exact match). All E1f factors derive net from the buy/sell components. (The manifest's
chart-64 `required_fields` listing `$net_mf_amount` is corrected to the component fields.)

## The two handbook constructions

- **prop (占比)** = `Sum(net, 20) / Sum($amount, 20)` — net inflow relative to total turnover (ratio-of-sums,
  faithful to the handbook "Σ净买入金额 / Σ成交额"). ⚠ cross-source unit note: `moneyflow` amounts are 万元,
  `$amount` is the provider's turnover unit → a constant scale factor. **Rank-invariant → IC/RankIC eval is
  unaffected**; only the absolute level is unit-scaled (documented, not a bug).
- **shift_dist (位移路程比)** = `Sum(net, 20) / Sum(gross, 20)` — net displacement / gross path = how
  DIRECTIONAL the flow was (∈ [−1, 1]). Self-contained units (both legs `moneyflow` 万元) → clean. Inline
  `Sum/Sum`, **no `shift_distance_ratio` operator** (drop it from the manifest, as E1c/E1d dropped theirs).

## GPT verdict (2026-06-19): CHANGES REQUIRED → **path A APPROVED** (9 faithful; buy family DEFERRED)

GPT approved the active-net construction, the gross `shift_dist` denominator, the prop ratio-of-sums (distinct
from the existing mean-of-ratios), the open/close defer, and no-operator — but **blocked the 9 "buy" factors**:
- `moneyflow` has only ACTIVE buy/sell, so the handbook's "总买入含被动" (total incl. passive) is **unbuildable**.
- **`buy_shift_dist` is a rank-identical affine ALIAS of `act_buy_shift_dist`**: with `B=Σbuy, S=Σsell`,
  `act = (B−S)/(B+S)` and `buy = B/(B+S) = 0.5·(1+act)`. **Empirically confirmed** (real data, 5 names ×
  2019-2020): Pearson **1.000000**, residual `|buy − 0.5(1+act)|` = 6e-8 → exact affine. (Spearman read 0.32,
  a float-precision artifact: the TOTAL `act_buy_shift_dist` is ≈0/near-constant on liquid names, so the 6e-8
  residual scrambles ranks within the tied cluster — Pearson is the correct diagnostic; the per-SIZE forms have
  real spread.) → the 5 `buy_shift_dist_*` are NOT new signals.

User chose **path A** (faithful-only; consistent with the E1e defer-not-proxy decision; the 4 distinct-but-proxy
`flow_buy_prop_*` were also deferred). The **9 faithful active-family factors registered**:

```
flow_act_buy_prop_20d                  = Sum(total_net, 20) / guard(Sum(Ref($amount,1), 20))
flow_act_buy_prop_{l,m,s}_20d          = Sum(net_{lg,md,sm}, 20) / guard(Sum(Ref($amount,1), 20))   # 3
flow_act_buy_shift_dist_20d            = Sum(total_net, 20) / guard(Sum(total_gross, 20))
flow_act_buy_shift_dist_{xl,l,m,s}_20d = Sum(net_{elg,lg,md,sm},20) / guard(Sum(gross_{elg,lg,md,sm},20))  # 4
```
= 1+3 (prop) + 1+4 (shift_dist) = **9**. `guard(x)` = `_nan_if_nonpos` (NaN-not-inf on a non-positive 20d
denominator). **DEFERRED:** the 9 "buy" factors (5 affine aliases + 4 active-buy proxies of the unbuildable
total-buy) and the 10 open/close factors (no intraday split). Real-data spot-check: 9 factors inf=0,
`shift_dist`∈[−1,1], `prop` sane, nan%=0; per-size `shift_dist` carries real spread (e.g. `_s` ∈ [−0.85, 0.29]).

## Dedup vs the 8 existing `flow_*` catalog factors

Existing (all `Mean`-of-ratios or `net_mf`-based): `flow_net_inflow_{5,20}d` (Mean of OPAQUE `net_mf`),
`flow_large_net_pct_20d` / `flow_small_net_pct_20d` (**Mean((buy−sell)/amount)** = mean-of-ratios),
`flow_large_small_ratio`, `flow_inflow_surge`, `flow_large_buy_ratio_5d`.

- The handbook `prop` = **ratio-of-sums** `Sum(net)/Sum(amount)`; the existing `flow_*_net_pct` = **mean-of-
  ratios** `Mean(net/amount)`. These are DIFFERENT estimators (ratio-of-sums weights high-turnover days more)
  → **not an exact dedup**; the handbook form is the faithful chart-64 construction. (Flag for GPT: near-
  overlap, register the faithful form? — Q3.)
- `shift_dist` (net/gross) is a NEW construction (no existing flow_* uses gross-flow denominator).
- `net_mf`-based and the 5d ratios are distinct (different field / window).

**→ 18 new (the shift_dist family entirely new; the prop family a faithful ratio-of-sums distinct from the
mean-of-ratios `flow_*_net_pct`); 0 exact dedup** (pending GPT Q3 on the prop near-overlap).

## GPT questions

- **Q1 (act_buy vs buy).** `moneyflow` gives only active buy (`buy_*`, buyer-initiated) + active sell
  (`sell_*`). I map **act_buy = net = buy − sell** and **buy = gross active-buy = buy_* alone** ("总买入含被动"
  is NOT separable — moneyflow has no passive split). Correct, or should "buy" be Σ(buy+sell) or omitted?
- **Q2 (shift_dist denominator).** `Σ|inflow|+|outflow| = Σ_size(buy+sell) = Σ gross`. Confirm gross (not
  `|net|`-based) is the handbook's 路程 (path).
- **Q3 (prop dedup).** Register the faithful ratio-of-sums `prop` despite the existing mean-of-ratios
  `flow_*_net_pct`? (They differ; I lean yes — faithful replication.)
- **Q4 (open/close defer).** Confirm deferring the `inflow_*_open/close` family (proxy_approx; needs
  intraday data) rather than registering a daily proxy.
- **Q5 (no operator).** Confirm `shift_distance_ratio` is dropped (inline `Sum/Sum`).

## Plan (GPT-approved path A)

Define **9** guarded inline factors (no operator) → register draft → v2 manifest expand chart-64 (9 factor-
level rows + `catalog_factor_id`, drop `shift_distance_ratio`, correct `required_fields` to the buy/sell
components, keep the open/close rows `proxy_approx`/deferred + a note that the "buy" family is deferred as
affine-alias/proxy) → 7-domain matrix → import → P-GATE → IS-gate. resolve-but-label; no promotion here.
a_priori; 2021+ sealed. `moneyflow` coverage from 2014 (2008 partial) → near-full 2010-2020 IS window.
