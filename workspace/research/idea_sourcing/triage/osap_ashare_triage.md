# OSAP → A-share triage

*Generated 2026-06-08 from osap_signaldoc.parquet (212 predictors).*

Heuristic triage — **novelty/dup flags need human confirmation**. Stubs under `stubs/` are DRAFTS: not registerable until you implement the factor, set `expected_effect`, and confirm an unburned OOS window.

## Summary matrix (feasibility × novelty)

| feasibility \ novelty | DUP | LIKELY_NOVEL | REVIEW |
|---|---|---|---|
| BUILDABLE_NOW | 14 | 0 | 124 |
| NOT_PORTABLE | 0 | 9 | 0 |
| PARTIAL | 1 | 64 | 0 |

## Top 15 buildable, non-dup candidates (clean reproduction)

| Acronym | Sign | Cites | Novelty | OSAP category | A-share data need | Stub |
|---|---|---|---|---|---|---|
| AM | + | 29625 | REVIEW | valuation | daily_basic+statements | `stubs/hyp_osap_am.json` |
| BookLeverage | − | 29625 | REVIEW | leverage | balance | `stubs/hyp_osap_bookleverage.json` |
| Beta | + | 21173 | REVIEW | risk | price+index | `stubs/hyp_osap_beta.json` |
| LRreversal | − | 13447 | REVIEW | long term reversal | price | `stubs/hyp_osap_lrreversal.json` |
| MeanRankRevGrowth | + | 7664 | REVIEW | sales growth | income | `stubs/hyp_osap_meanrankrevgrowth.json` |
| BetaLiquidityPS | + | 7459 | REVIEW | liquidity | price+vol+amount | `stubs/hyp_osap_betaliquidityps.json` |
| betaVIX | − | 6323 | REVIEW | volatility | price | `stubs/hyp_osap_betavix.json` |
| IdioVol3F | − | 6323 | REVIEW | volatility | price | `stubs/hyp_osap_idiovol3f.json` |
| Coskewness | − | 3704 | REVIEW | risk | price+index | `stubs/hyp_osap_coskewness.json` |
| GP | + | 2980 | REVIEW | profitability | income+balance | `stubs/hyp_osap_gp.json` |
| ProbInformedTrading | + | 2835 | REVIEW | liquidity | price+vol+amount | `stubs/hyp_osap_probinformedtrading.json` |
| ForecastDispersion | − | 2775 | REVIEW | volatility | price | `stubs/hyp_osap_forecastdispersion.json` |
| FirmAgeMom | + | 2599 | REVIEW | momentum | price | `stubs/hyp_osap_firmagemom.json` |
| Leverage | + | 2597 | REVIEW | leverage | balance | `stubs/hyp_osap_leverage.json` |
| IndMom | + | 2565 | REVIEW | momentum | price | `stubs/hyp_osap_indmom.json` |

## How to use a stub

1. Implement the proposed factor in the factor library (US definition → A-share fields, PIT-safe).
2. Open the stub, replace `expected_effect: null` with your A-share prediction.
3. Edit the `[DRAFT]` pre-registered concerns.
4. Confirm the OOS window is unburned, then `hypothesis_cli.py register --file stubs/<file>.json --profile-id factor_screening`.
