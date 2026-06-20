# CICC Wave E1h — 融资融券 / margin (chart 88) factor-logic spec

> Pre-registration factor logic for the E1h tranche, to be GPT-reviewed BEFORE registration (mirrors
> E1a–E1g). Source: handbook chart 88 in
> [CICC_价量因子定义.md](../../../Knowledge/AI量化增强/CICC_价量因子定义.md) §8 (融资融券因子, ~12). Data:
> Tushare `margin_detail`. **NO custom operator** — inline `Sum`/`Ref`/`Delta`/division.

## KEY FINDING: the frozen manifest's chart-88 exclusions are STALE

The manifest marks `margin_sell_sec_prop` `not_replicable` citing "rqye/rqchl 融券 quarantine". But the
**2026-06-04 partial promotion approved `$rzye` (融资余额), `$rqye` (融券余额), `$rzmre` (融资买入额),
`$rzrqye` (融资融券余额), `$rqmcl` (融券卖出量)** — verified `resolve_field` = approved/allowed for all 5.
**Only the two REPAYMENT fields `$rzche` (融资偿还额) + `$rqchl` (融券偿还量) stay quarantined** (BSE-localized
negatives, `margin_detail_repayment`). → the **融券 side IS now replicable** (balance + sell-volume), and only
the repayment-dependent `shift_dist` factors are blocked. The manifest chart-88 rows need correction.

## Scope: ~12 handbook factors → 5 faithful NEW + 2 dedups + 2 repayment-blocked

| handbook | construction | field | disposition |
|---|---|---|---|
| margin_buy_money_prop (融资买入占比) | Σ(融资买入额,20) / Σ(成交额,20) | `$rzmre` | **NEW** |
| margin_money_bal_growth (融资增量增长率) | rz / (rz[t−20]+1) − ret₂₀ | `$rzye` | **NEW** |
| margin_sell_sec_prop (融券卖出占比) | Σ(融券卖出量·VWAP,20) / Σ(成交额,20) | `$rqmcl` | **NEW** |
| margin_sec_bal_prop (融券余额占比) | 融券余额 / 流通市值 | `$rqye` | **NEW** |
| margin_sec_bal_growth (融券增量增长率) | rq / (rq[t−20]+1) − ret₂₀ | `$rqye` | **NEW** |
| margin_money_bal_prop (融资余额占比) | 融资余额 / 流通市值 | `$rzye` | **DEDUP** → existing `margin_balance_pct` |
| margin_sec_avg (融券卖出因子) | Σ(融券卖出量·VWAP) / Σ成交额 | `$rqmcl` | **DEDUP** → `margin_sell_sec_prop` (same formula) |
| net_margin_buy_money_shift_dist | Σ(融资买入−融资偿还)/Σ\|...\| | `$rzche` | **BLOCKED** (repayment quarantine) |
| net_margin_sell_sec_shift_dist | Σ(融券卖出−融券偿还)·VWAP/Σ\|...\| | `$rqchl` | **BLOCKED** (repayment quarantine) |

Existing `margin_*`: `margin_balance_pct` (= margin_money_bal_prop, dedup), `margin_net_buy_20d` (uses
quarantined `$rzche` → field-ineligible draft), `margin_sl_balance_change` (= `Delta($rqye,20)`, distinct
from the growth-rate `margin_sec_bal_growth`).

## The 5 NEW factors (PIT lag-1 — margin is T-disclosed-AFTER-close, so `Ref(...,1)` minimum)

```
rz   = Ref($rzye, 1)        rq   = Ref($rqye, 1)        rzm = Ref($rzmre, 1)
rqm  = Ref($rqmcl, 1)       amt  = Ref($amount, 1)      vwap = Ref($amount,1) / guard(Ref($vol,1))
cmv  = Ref($circ_mv, 1)     ret20 = ADJ_CLOSE_T1 / Ref(ADJ_CLOSE, 21) - 1

1. margin_buy_money_prop_20d = Sum(rzm, 20) / guard(Sum(amt, 20))
2. margin_money_bal_growth_20d = rz / (Ref($rzye, 21) + 1) - ret20            # handbook's "+1" guard
3. margin_sell_sec_prop_20d  = Sum(rqm * vwap, 20) / guard(Sum(amt, 20))      # rqm is VOLUME → ×VWAP = value
4. margin_sec_bal_prop_20d   = rq / guard(cmv)
5. margin_sec_bal_growth_20d = rq / (Ref($rqye, 21) + 1) - ret20
```
`guard(x) = _nan_if_nonpos(x)`.

## GPT questions

- **Q1 (masking / coverage_tier — the load-bearing one).** Margin trading applies only to **margin-eligible
  stocks** (a subset, expanding over time; non-eligible names have `$rzye=$rqye=0`). E1g's analogous masking
  made `coverage_tier=sub` → P-GATE `availability_floor_fail` → `evidence_only` (no promotion). Options:
  (a) **mask** `If($rzye>0 …)` (the prop/growth factors only meaningful for eligible names) — risks `sub`
  tier → evidence_only; (b) **don't mask** — `bal_prop`=0 for non-eligible is meaningful ("no margin"), but
  the growth factors degrade to `−ret20` for non-eligible. The margin universe is much larger than
  northbound's (~50-70% vs ~35%), so the tier may land `full`/`partial`. **Which masking, and is E1h
  likely to clear the availability floor where E1g did not?**
- **Q2 (growth "+1" guard).** The handbook uses `bal / (bal[t−20] + 1)`; for a name newly entering margin
  eligibility (bal[t−20]=0) this → `bal/1 − ret20` (a large jump). Mask those, or keep faithful?
- **Q3 (sell-vol × VWAP).** `$rqmcl` is 融券卖出**量** (shares); the handbook's 融券卖出占比 uses 卖出额 =
  量×VWAP. Confirm `rqm * vwap` is the right value basis (vs raw volume).
- **Q4 (manifest correction).** Correct the stale chart-88 exclusion (`$rqye` is approved; only repayment
  blocked) — register the 5 faithful + mark only `net_margin_*_shift_dist` blocked-on-repayment.
- **Q5 (dedups + no operator).** `margin_money_bal_prop`≡`margin_balance_pct`, `margin_sec_avg`≡
  `margin_sell_sec_prop` skipped; inline `Sum/Sum` (no operator). Confirm.

## Plan (pending GPT APPROVE)

Define 5 guarded inline factors (no operator) → register draft → v2 manifest expand chart-88 (5 factor-level
rows + correct the stale 融券 exclusion) → 7-domain matrix → import → P-GATE → IS-gate. resolve-but-label;
a_priori; this is the **last data-ready handbook chart** before the chart-100 composite + the mandated
family-aware selection (see `project_e_wave_selection_mandate`).
