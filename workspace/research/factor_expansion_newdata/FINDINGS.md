# Findings — new-data factor expansion

## Phase 1 (2026-06-05): Tier-1 IS discovery screen → 0/8 clear the pre-registered bar

Ran the FROZEN `PRE_REGISTRATION_tier1.md` spec (committed `486860e` before screening). IS 2014-2020
ONLY, window-enforced (ResearchAccessContext + label cap at 2020-12-31; verified no 2021+ read —
factors `(5,983,911 × 8)`, dates `2013-01-04..2020-12-31`). Bar (pre-set): `|RankICIR_20d|≥0.30` AND
`|meanRankIC_20d|≥0.015` AND top-vs-bottom quintile monotone AND 5/10/20d decay sign-consistent.

**Result: 0/8 survivors.** effective_trials = 8 (all recorded).

| factor (RankICIR_20d, meanRankIC, monotone) | note |
|---|---|
| `lev_margin_bal_growth_20d` (−0.2975, −0.0249, **No**) | strongest rank-corr but NON-monotone (tail-driven) + just under the 0.30 bar |
| `flow_retail_pressure_5d` (+0.1716, +0.0166, Yes) | clean monotone CONTRARIAN (retail small-order buying fades), but ~half the bar |
| `lev_margin_to_mktcap` (−0.105, −0.0134, Yes) | weak |
| `lev_short_interest_ratio` (−0.072, −0.0115, Yes) | weak |
| `flow_mainforce_imbalance_5d` (+0.072, +0.006, Yes, decay-inconsistent) | weak |
| `lev_margin_buy_intensity_5d` (−0.070, −0.010, Yes) | weak |
| `flow_elg_concentration_5d` (+0.059, +0.003, Yes, decay-inconsistent) | weak |
| `flow_mainforce_imbalance_20d` (+0.021, +0.002, Yes, decay-inconsistent) | negligible |

**Conclusion:** the straightforward single-field new-data factors (raw moneyflow/margin imbalances at
5/20d) carry **weak standalone IS signal**. Two are directionally real and both CONTRARIAN — retail
buying fades (`flow_retail_pressure`) and over-leverage predicts lower returns (`margin_bal_growth`) —
but neither is a clean, bar-clearing standalone factor. Nothing proceeds to the `factor_lifecycle` gate
from this batch. (Negative result, honestly reported; the bar was pre-registered so it stands.)

**Implication:** the obvious constructions are low-yield. Any further new-data factor work needs a NEW
pre-registration (the 2021-26 OOS budget counts every batch) and should test the two real-but-weak
contrarian hypotheses with better constructions (cross-sectional size/industry NEUTRALIZATION, LONGER
horizons 40/60d, and conditioning/interactions e.g. flow × reversal) — OR the new data should be
treated as a conditioning/combination input, not standalone alpha. Decision deferred to the user.
