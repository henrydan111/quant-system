# CICC Wave E1f — 资金流 / capital flow (chart 64) factor-logic spec

> Pre-registration factor logic for the E1f tranche, to be GPT-reviewed BEFORE registration (mirrors
> the E1a/E1b/E1c/E1d logic reviews). Source: handbook chart 64 in
> [CICC_价量因子定义.md](../../../Knowledge/AI量化增强/CICC_价量因子定义.md) §6 (资金流因子, 32). Data:
> Tushare `moneyflow` (approved). **Claim: NO custom operator** — all inline `Sum`/`Ref`/division.

## Scope: 32 handbook factors → 18 data-ready (大小单) + 10 DEFERRED (开盘/尾盘, proxy) + 4 reconciliation

The handbook splits chart 64 into two sub-families:
1. **大小单资金流向 (large/small-order flow)** — replicable from `moneyflow`'s order-size components. **THIS WAVE.**
2. **开盘/尾盘资金流向 (open/close-segment flow)** — `inflow_*_open` / `inflow_*_close`. **DEFERRED**: daily
   `moneyflow` has NO intraday open/close split (the frozen manifest already marks these `proxy_approx`).
   Faithful replication needs an intraday/tick moneyflow source — a separate ingestion (cf. E1e/cyq_chips).
   NOT registered here; recorded as a known gap.

(Handbook lists ~28 named + 4 window/variant; this spec registers the **18 faithful 大小单** factors below.)

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

## The 18 factors (act_buy = NET; buy = GROSS-BUY — see GPT question Q1)

```
# 主动(净) family — act_buy = net active inflow (buy − sell)
flow_act_buy_prop_20d              = Sum(total_net, 20)  / Sum(Ref($amount,1), 20)
flow_act_buy_prop_{l,m,s}_20d      = Sum(net_{lg,md,sm}, 20) / Sum(Ref($amount,1), 20)      # 3
flow_act_buy_shift_dist_20d        = Sum(total_net, 20)  / Sum(total_gross, 20)
flow_act_buy_shift_dist_{xl,l,m,s}_20d = Sum(net_{elg,lg,md,sm},20) / Sum(gross_{elg,lg,md,sm},20)  # 4
# 总(含被动) family — buy = gross active-buy amount (the "含被动" nuance is NOT separable in moneyflow; Q1)
flow_buy_prop_20d                  = Sum(total_buy, 20)  / Sum(Ref($amount,1), 20)
flow_buy_prop_{l,m,s}_20d          = Sum(buy_{lg,md,sm}, 20) / Sum(Ref($amount,1), 20)      # 3
flow_buy_shift_dist_20d            = Sum(total_buy, 20)  / Sum(total_gross, 20)
flow_buy_shift_dist_{xl,l,m,s}_20d = Sum(buy_{elg,lg,md,sm},20) / Sum(gross_{elg,lg,md,sm},20)  # 4
```
= 1+3+1+4 (act_buy) + 1+3+1+4 (buy) = **18**. All guarded against a zero denominator (NaN, not inf) via the
`_nan_if_nonpos` idiom (a stock with 0 turnover/flow over 20d → NaN, dropped by the eval).

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

## Plan (pending GPT APPROVE)

Define 18 guarded inline factors (no operator) → register draft → v2 manifest expand chart-64 (18 factor-
level rows + `catalog_factor_id`, drop `shift_distance_ratio`, correct `required_fields` to components, keep
the 2 open/close rows marked `proxy_approx`/deferred) → 7-domain matrix → import → P-GATE → IS-gate.
resolve-but-label; no promotion here. a_priori; 2021+ sealed. `moneyflow` coverage from 2014 (2008 partial)
→ near-full 2010-2020 IS window.
