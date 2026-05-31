# Catalog Walk-Forward Re-Validation — FULL 171 (147 base + 24 derived)

**Date:** 2026-05-31. **Window:** 2014-01-01 → 2026-02-27, horizon 20d. **Method:** per-date
RankIC, IS(2014-2020)/OOS(2021-2026) split + per-year fold sign-consistency; predeclared
mechanical status rule. **Derived run also adds a LONG-ONLY top-bucket metric.**
**Artifacts:** `catalog_revalidation/catalog_revalidation_status.csv` (147 base),
`catalog_revalidation/derived_revalidation_status.csv` (24 derived).

## Coverage — the full 171 is now re-validated
| Set | Count | Status breakdown |
|---|---|---|
| Base (Layer-1) | 147 | 77 candidate / 59 draft / 11 deprecated |
| Composites (Layer-2) | 20 | 13 candidate / 6 draft / 1 deprecated |
| Industry-relative | 4 | 4 candidate / 0 draft / 0 deprecated |
| **TOTAL** | **171** | **93 candidate / 66 draft / 12 deprecated** |

`approved` = 0 (reserved for the strategy-level promotion gate). 33 of the 66 draft are
field-ineligible (quarantine/pending fields), capped regardless of performance.

## Finding 1 (base) — fundamental growth/leverage LEVELS are IS-overfit
11 deprecated base factors were strong IS (ICIR +0.25..+0.39) but collapsed to ≈0 OOS
(`grow_netprofit_yoy`, `grow_eps_yoy`, `grow_opprofit_yoy`, `grow_profit_trend`,
`earn_earnings_momentum`, `qual_asset_turnover`, + near-zero leverage factors). 13 of 96
strong-IS factors collapsed/flipped OOS. **Corroborates the expansion-set OOS**: fundamental
*level/YoY* signals don't generalize; *acceleration* variants do.

## Finding 2 (base) — the OOS-robust catalog signals are price/vol/liquidity (negative IC)
55 of 77 base candidates are negative-IC with year-sign-consistency 1.0 (`liq_log_dollar_vol`
OOS ICIR −0.81, `rev_max_return_20d` −0.67, `risk_vol_*` −0.57) — the reversal/low-vol/liquidity
premia. Durable, but short-side in character (see Finding 3).

## Finding 3 (derived + LONG-ONLY metric) — **IC does NOT equal long-only return**
This is the decisive new result, and it directly answers "can we just flip a negative-IC factor
to get positive long-only returns?" — **mostly no.** The long-only top-bucket metric (sign-aligned
top-decile-minus-universe excess) shows:

- Of the **16 IC-candidate derived factors, only 2 have long-only Sharpe ≥ 1.0**:
  `comp_small_value` (OOS ICIR +0.60, **LO Sharpe +1.40**, hit 0.66) and
  `comp_size_quality` (OOS ICIR +0.49, **LO Sharpe +1.22**, hit 0.65) — both small-cap tilts.
- **12 of the 16 have long-only Sharpe < 0.5**, several **negative**: `comp_low_vol_value`
  (LO +0.01), `comp_defensive` (−0.03), `comp_52w_position` (−0.16), `comp_relative_strength` (−0.02).
- The starkest case: **`val_bp_industry_rel` has the highest OOS ICIR of any derived factor
  (+0.775) but a long-only Sharpe of just +0.49** — a textbook demonstration that a strong
  cross-sectional IC lives mostly in the spread (incl. the short leg a no-shorting book can't hold).

**Conclusion:** ranking a high-|IC| factor and holding its top bucket does NOT reliably produce a
tradable long-only return. The IC/long-short metrics that drove `candidate` status overstate
long-only viability. Only factors whose **long leg itself earns the premium** (here: the small-cap
composites) are long-only-viable. This is the same lesson as `long_only_50cagr`, now measured
directly per factor.

## Implications
1. **`candidate` (IC-based) ≠ long-only deployable.** The registry needs the long-only metric as a
   first-class column, and likely a `risk_sleeve`/`short_side` status (formalization plan §7 Q7) for
   the many high-IC / weak-long-only factors (the 55 negative-IC base + ~12 of these derived).
2. **Backfill the long-only metric onto the 147 base + the 6 OOS-registered expansion factors** so
   every factor carries a long-only-viability flag, not just IC/long-short.
3. The genuinely long-only-promising catalog factors are **few** and concentrated in small-cap-value
   / small-cap-quality — consistent with the A-share small-cap premium and the prior 50cagr work.

## Caveats
- Statuses are PROPOSED, not written to the registry.
- `candidate` = walk-forward IC-stable; NOT `approved` (no tradability/promotion gate).
- Long-only metric uses overlapping 20d forward returns (same convention as the screen's LS metric);
  it is a top-bucket *proxy*, not a full transaction-cost backtest — directional, not deployment-grade.
- Multiple testing: 171 factors on one window; fold-sign-consistency is the robust bar; marginal
  candidates near |OOS ICIR|=0.10 / LO Sharpe≈0 should be treated cautiously.
