# Catalog Walk-Forward Re-Validation — 147 Base Factors

**Date:** 2026-05-31. **Window:** 2014-01-01 → 2026-02-27, horizon 20d. **Method:** per-date
RankIC over the full period, split into IS (2014-2020) / OOS (2021-2026) + per-calendar-year
fold sign-consistency. **Status rule:** predeclared & mechanical (frozen in
`workspace/scripts/revalidate_catalog_walkforward.py` header before results).
**Artifacts:** `catalog_revalidation/catalog_revalidation_status.csv` (+ metadata).
**Compute:** 11.6M rows (5,694 stocks × 2,953 dates) × 147 factors, 45 min.

## Context — why this was needed
The existing "171-factor catalog" was previously graded **only on a full-sample 2012-2026 IC
pass with no holdout** — all 171 sat at status `draft`. This is the first proper IS/OOS +
walk-forward evaluation of those factors. **Honesty note:** the 147 are a-priori definitions,
never promoted on OOS, so 2021-2026 is a legitimate *first clean split-test* (not pristine
OOS); per-year fold-stability is the primary, multiple-testing-robust driver. The 2021-2026
window is now treated as spent for these factors.

## Headline
| Status | Count | Meaning |
|---|---|---|
| `candidate` | **77** | field-eligible, walk-forward sign-stable, OOS-holding (\|OOS ICIR\|≥0.10, year-sign-consistency≥0.70) |
| `draft` | **59** | 33 field-ineligible (quarantine/pending fields, capped) + 26 marginal/sub-threshold |
| `deprecated` | **11** | strong IS but collapsed/flipped OOS — failed the holdout |
| `approved` | **0** | NOT assigned here — requires the strategy-level promotion gate |

Field-ineligible (capped at `draft` regardless of performance): **33** (the moneyflow / northbound /
margin / alpha-endpoint factors on `quarantine`/`pending` fields).

## Finding 1 — fundamental growth/leverage LEVELS are IS-overfit (the deprecated 11)
The 11 deprecated factors were strong in-sample (ICIR +0.25 to +0.39) and **collapsed to ≈0 OOS**:
`grow_profit_trend`, `grow_eps_yoy`, `grow_netprofit_yoy`, `grow_opprofit_yoy`,
`earn_earnings_momentum`, `qual_asset_turnover`, plus the near-zero leverage factors
(`qual_leverage`, `lev_debt_to_assets`, `lev_debt_capacity`, `lev_deleverage`, `size_ln_free_float`).

This **exactly corroborates the expansion-set OOS finding**: fundamental *level / YoY* signals do
not generalize in A-shares, while *acceleration* (2nd-derivative) variants do (the expansion
`grow_*_yoy_accel_q` survived; the `grow_*_yoy_q` levels were rejected). Two independent screens,
same conclusion. The old full-sample grades flattered these factors by averaging the strong
2014-2020 with the dead 2021-2026.

Broader: **13 of 96 strong-IS factors (|IS ICIR|≥0.2) collapsed or flipped OOS** (~14%) — including
the northbound cluster (`north_hold_pct`, `north_accumulation_20d`, `north_flow_momentum`) and some
chip factors, though those were also field-capped to draft.

## Finding 2 — the robust A-share signals are price/volume/liquidity/volatility (negative IC)
Of the 77 candidates, **55 are negative-IC** — the reversal / low-volatility / liquidity-premium
factors that are persistent across all 12 years (`sign_consistency = 1.0`):

| Factor | IS ICIR | OOS ICIR | yr-consistency |
|---|---|---|---|
| `liq_log_dollar_vol` | −0.62 | **−0.81** | 1.0 |
| `mom_intraday_20d` | −0.57 | −0.68 | 1.0 |
| `rev_max_return_20d` | −0.71 | −0.67 | 1.0 |
| `mom_ewm_60d` | −0.49 | −0.66 | 1.0 |
| `liq_turnover_f_5d` | −0.64 | −0.61 | 1.0 |
| `risk_vol_5d` / `risk_vol_10d` | −0.51/−0.53 | −0.58/−0.57 | 1.0 |

These are the **most OOS-robust factors in the entire catalog** — and they reconfirm the standing
`long_only_50cagr` finding that A-shares are a reversal/low-risk/liquidity-premium market. **Caveat
(unchanged):** strong cross-sectional IC here is largely a *short-the-junk* effect; it does not
convert directly to long-only top-K return. These would feed a **risk/short sleeve or neutralization
overlay**, not a long-only book — which is exactly the case for the `risk_sleeve`/`short_side`
status proposed in the formalization plan §7 Q7.

## Implication for the formalization plan
This run is the **empirical seed for Phase 6** of `factor_lifecycle_formalization_plan.md` and a
live validation of the status-assignment logic. It also surfaces a concrete taxonomy gap: 55 of 77
"candidates" are negative-IC short-side signals being lumped with ~22 genuine long-only candidates —
strengthening the case for a distinct `risk_sleeve` status (plan §7 Q7) so the registry doesn't imply
they're long-only alpha.

## Caveats
- These statuses are **proposed**, not written to the registry (no registry mutation this session).
- `candidate` here = walk-forward stable; it is NOT `approved` (no strategy-gate / tradability check).
- Composites (20) + industry-relative (4) were NOT re-validated here (need Layer-2 / SW-label
  post-processing) — a noted follow-up pass.
- Multiple testing: 147 factors on one window; fold-sign-consistency (not a pseudo-p-value) is the
  robust bar, but the marginal candidates near |OOS ICIR|=0.10 should be treated cautiously.
