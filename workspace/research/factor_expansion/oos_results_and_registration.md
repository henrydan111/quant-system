# Sealed-OOS Results & Registration Decision

**Date:** 2026-05-31. **OOS window:** 2021-01-01 → 2026-02-27 (`stage='oos_test'`),
run **exactly once** on the 13-factor frozen top set (frozen pre-OOS at commit `73d556a`).
**IS window:** 2014-01-01 → 2020-12-31. No tuning, no re-selection after OOS.

## 1. OOS run integrity
- Frozen set of 13 read from `oos_frozen_topset.json` (committed before OOS).
- `run_sealed_oos.py` one-shot guard active (refuses to overwrite an existing result).
- 0 NaN/degenerate rows. inf sanitation: a few `oos_n_inf` cells on the revenue-accel
  ratios (829 on `grow_total_revenue_yoy_accel_q`) were sanitized by the screening
  pipeline before IC computation (0 NaN result rows confirms it).
- All 13 factors are `approved` / formal-eligible / PIT-safe / Count-free (static gates
  passed pre-freeze; unchanged by OOS).

## 2. IS → OOS evidence (the decision table)

`signOK` = IC sign AND LS-Sharpe sign both preserved IS→OOS. `retain%` = OOS_ICIR / IS_ICIR.

| Factor | IS ICIR | OOS ICIR | IS LS | OOS LS | OOS MaxDD% | signOK | retain% | Decision |
|---|---|---|---|---|---|---|---|---|
| `grow_total_revenue_yoy_accel_q` | +0.449 | +0.257 | +3.58 | **+3.44** | 0.16 | ✅ | 57% | **REGISTER** |
| `rev_turnover_spike_5d` | +0.268 | +0.276 | +2.60 | **+2.68** | 0.43 | ✅ | 103% | **REGISTER** |
| `liq_zero_ret_days_10d` | +0.296 | +0.411 | +1.09 | **+2.14** | 0.44 | ✅ | 139% | **REGISTER** |
| `grow_n_income_attr_p_yoy_accel_q` | +0.499 | +0.250 | +5.35 | **+1.96** | 0.22 | ✅ | 50% | **REGISTER** |
| `grow_operate_profit_yoy_accel_q` | +0.501 | +0.197 | +4.74 | **+1.49** | 0.24 | ✅ | 39% | **REGISTER** |
| `qual_piotroski_fscore_9pt` | +0.334 | +0.209 | +2.22 | **+1.20** | 0.68 | ✅ | 62% | **REGISTER** |
| `acc_cfo_to_ni_ttm` | +0.308 | +0.185 | +1.36 | +0.46 | 0.58 | ✅ | 60% | defer (OOS LS<1) |
| `val_retearn_yield` | +0.287 | +0.305 | +1.10 | +0.57 | 1.46 | ✅ | 106% | defer (OOS LS<1) |
| `val_fcf_ev_ttm` | +0.270 | +0.142 | +1.01 | −0.15 | 0.99 | ❌ | 53% | reject (LS sign flip) |
| `val_ebit_ev_ttm` | +0.283 | +0.113 | +0.93 | −0.61 | 1.92 | ❌ | 40% | reject (LS sign flip) |
| `grow_operate_profit_yoy_q` | +0.326 | −0.012 | +2.88 | −0.32 | 0.93 | ❌ | −4% | reject (IC+LS collapse) |
| `grow_n_income_attr_p_yoy_q` | +0.305 | +0.004 | +2.83 | −0.36 | 0.91 | ❌ | 1% | reject (IC+LS collapse) |
| `acc_cash_roa_ttm` | +0.301 | +0.002 | +1.64 | −0.70 | 1.31 | ❌ | 1% | reject (IC+LS collapse) |

## 3. Registration decision (predeclared post-OOS gate)

**Gate (set before reading OOS, consistent with the long-only objective):** register only
factors that are (a) sign-stable IS→OOS in BOTH IC and LS Sharpe, AND (b) OOS LS Sharpe
> 1.0 (a genuine tradable long-short in unseen data), AND (c) already passing all
static/PIT/operator/registry gates.

### REGISTER (6 factors)
1. `grow_total_revenue_yoy_accel_q` — OOS ICIR +0.26, LS +3.44, MDD 0.16%. Strongest OOS.
2. `rev_turnover_spike_5d` — OOS ICIR +0.28, LS +2.68, hit-rate 0.72. **retain 103%** (no decay).
3. `liq_zero_ret_days_10d` — OOS ICIR +0.41, LS +2.14. **Strengthened OOS** (retain 139%).
4. `grow_n_income_attr_p_yoy_accel_q` — OOS ICIR +0.25, LS +1.96, monotonic.
5. `grow_operate_profit_yoy_accel_q` — OOS ICIR +0.20, LS +1.49, monotonic.
6. `qual_piotroski_fscore_9pt` — OOS ICIR +0.21, LS +1.20. Classic composite holds.

### DEFER (2 factors) — sign-stable but OOS LS Sharpe < 1.0
- `acc_cfo_to_ni_ttm` (OOS LS +0.46), `val_retearn_yield` (OOS LS +0.57). Real but weak in
  OOS; revisit in an ensemble context, do not register standalone.

### REJECT (5 factors) — failed OOS
- **Sign flip:** `val_fcf_ev_ttm`, `val_ebit_ev_ttm` (LS turned negative OOS).
- **Collapse to noise:** `grow_operate_profit_yoy_q`, `grow_n_income_attr_p_yoy_q`,
  `acc_cash_roa_ttm` (IS LS +2.8/+2.8/+1.6 → OOS ≈ 0 / negative; ICIR retain ≈ 0%).

## 4. Key findings

1. **The earnings-ACCELERATION factors generalize; the LEVEL factors do not.** The three
   `*_yoy_accel_q` survived (decayed but sign-stable, LS > 1.4 OOS), while the two
   `*_yoy_q` *level* factors collapsed to noise OOS (retain ≈ 0%). The second derivative
   (change in growth rate) carries the durable signal in A-shares; the level is IS-overfit.
2. **`rev_turnover_spike_5d` and `liq_zero_ret_days_10d` did NOT decay** (retain 103% / 139%)
   — the microstructure/liquidity signals are the most OOS-robust of the set, even though
   their IS ICIR was lower than the acceleration factors. IS rank ≠ OOS rank.
3. **The accruals/cash-quality/EV-value Tier-2 cluster mostly failed OOS** — `acc_cash_roa_ttm`,
   `val_ebit_ev_ttm`, `val_fcf_ev_ttm` did not hold. Honest: the Wave-1 promotion unlocked
   them for evaluation, and the evaluation says most are not durable long-only alpha here.
4. **Protocol worked as designed.** The predeclared rule + one-shot OOS separated 6 durable
   from 7 non-durable factors with no opportunity for post-hoc tuning. This is the exact
   discipline the invalidated val_heavy "champion" lacked.

## 5. Caveats (honest)
- IS→OOS decay is real (acceleration factors retain 39-57% of ICIR). These are **moderate**
  signals, not the IS headline. A deployed book should expect the OOS magnitudes, not IS.
- Cross-sectional LS Sharpe is **not** a long-only return guarantee (prior long_only_50cagr
  finding: top-K long-only can still disappoint). Registration here = "validated factor",
  NOT "validated strategy". Strategy-level OOS (EventDrivenBacktester, tradability) and the
  promotion gate remain separate downstream steps before any deployment.
- 13 factors tested in one OOS shot → mild multiple-testing exposure. The 6 registered all
  clear a LS Sharpe > 1.0 bar with sign stability, which is robust to that exposure, but the
  marginal ones (Piotroski OOS LS 1.20) are closest to the line.
