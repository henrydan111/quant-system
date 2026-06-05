# Design — Factor Expansion on the Newly-Unlocked Data (Wave-3)

**Status:** DESIGN for review (no catalog/registry change yet). **Author:** Claude, 2026-06-05.
**Decision owner:** user (+ optional GPT cross-review), mirroring prior factor-lifecycle phases.

> **Update (2026-06-05, post-GPT-cross-review):** Conditional GO for the **Tier-1 IS-only screen**;
> **NO-GO for the later `approved` OOS step until a window-level OOS budget is formalized.** The frozen
> Tier-1 spec is [PRE_REGISTRATION_tier1.md](PRE_REGISTRATION_tier1.md) (authoritative). **CORRECTION:**
> the 2021-26 OOS is NOT "fresh/unspent" globally — it is **UNOBSERVED for this new factor set** but a
> **shared resource already spent once** (claim_index will be ≥2; window-level multiple testing is real
> and budgeted at the OOS stage). The "§3 claimed advantage" and any "unspent/fresh" wording below are
> superseded by this correction.

## 1. Objective & why now

The 2026-06-04/05 gated-dataset review promoted **8 new datasets to `approved`**, none of which any of
the 177 catalog factors uses. This wave builds the first factors on that data. Two reasons it's the
highest-value next step:

- **Fresh, well-studied A-share alpha sources** (capital flow, margin/leverage, 龙虎榜, 大宗交易, 筹码,
  northbound) — previously unusable in formal research, now `approved`.
- **A clean path to `approved` that the existing 87 candidates lack.** The 87 are stuck (their 2021-26
  OOS is burned by `oos_informed` selection). Genuinely-NEW factors, developed purely on **IS 2014-2020**
  without examining 2021-26, have an **unspent 2021-26 sealed OOS** available (a new frozen-set hash → an
  independent `HoldoutSealStore` claim). So these can run the FULL lifecycle draft→candidate→`approved`.

**Hard discipline for that to hold:** all design + selection happens on IS 2014-2020 ONLY. 2021-26 is NOT
examined until the one-shot sealed OOS. (Same rule that the sealed-OOS winners followed.)

## 2. Data families, IS coverage, PIT contract

All new fields are same-day OUTCOMES (or post-close events) → every `$field` (incl. denominators like
`$amount`/`$total_mv`) is wrapped in `Ref(...,1)`. Smoke-confirmed working in `compute_factors`.

| family | fields | type | IS 2014-2020 cov | tier |
|---|---|---|---|---|
| Capital flow `moneyflow` | 16 buy/sell sm/md/lg/elg vol+amount (net_mf_* opaque — avoid) | daily-dense | FULL (2014+) | **1** |
| Margin/leverage `margin_detail` | $rzye $rqye $rzmre $rzrqye $rqmcl | daily-dense | FULL (2010+) | **1** |
| 龙虎榜 `top_list`/`top_inst` | $top_list__{net_amount,l_buy,l_sell,amount}, $top_inst__{net_buy,buy,sell} | SPARSE event | full (2008/2012+) | 2 |
| 大宗交易 `block_trade` | $block_trade__{price,vol,amount} | SPARSE event | full (2008+) | 2 |
| 筹码 `cyq_perf` | $cyq_perf__{winner_rate,cost_50pct,cost_5pct,cost_95pct,weight_avg} | daily-dense | PARTIAL (2018+ → only 2018-20 in IS) | 3 |
| Northbound `hk_hold` | $ratio | daily-dense | PARTIAL (2017+ → 2017-20 in IS) | 3 |

Tier 1 (moneyflow, margin) is the cleanest + highest-coverage → build + screen first. Tier 2 (sparse
events) needs a recency/decay construction (§4). Tier 3 has short IS → screen but treat results cautiously.

## 3. Candidate factors (IS-only hypotheses + PIT-safe sketch expressions)

`eps` = small constant; all denominators `Ref(...,1)`. Names follow `{cat}_{name}_{lookback}`.
Sign noted as the economic prior (the screen confirms the empirical sign).

### Tier 1 — capital flow (moneyflow), daily-dense
- `flow_mainforce_imbalance_5d` (+): main-force net pressure, turnover-normalized.
  `Mean( ( Ref($buy_lg_amount,1)+Ref($buy_elg_amount,1)-Ref($sell_lg_amount,1)-Ref($sell_elg_amount,1) ) / (Ref($amount,1)+1), 5)`
- `flow_mainforce_imbalance_20d` (+): 20d version of the above.
- `flow_retail_pressure_5d` (−, contrarian): small-order net buying = retail → fade.
  `0 - Mean( (Ref($buy_sm_amount,1)-Ref($sell_sm_amount,1)) / (Ref($amount,1)+1), 5)`
- `flow_elg_concentration_5d` (+): xlarge net share of gross flow (institutional concentration).
  `Mean( (Ref($buy_elg_amount,1)-Ref($sell_elg_amount,1)) / (Ref($buy_elg_amount,1)+Ref($sell_elg_amount,1)+1), 5)`
- `flow_net_accel_10d` (+): acceleration of main-force net pressure (Δ of the smoothed series).
  `Delta( Mean((Ref($buy_lg_amount,1)+Ref($buy_elg_amount,1)-Ref($sell_lg_amount,1)-Ref($sell_elg_amount,1))/(Ref($amount,1)+1),5), 10)`

### Tier 1 — margin / leverage (margin_detail), daily-dense
- `lev_margin_bal_growth_20d` (sign TBD — momentum vs over-leverage): 融资融券余额 growth.
  `Delta(Ref($rzrqye,1),20) / (Ref($rzrqye,1)+1)`
- `lev_short_interest_ratio` (−, bearish): short balance share of total margin.
  `Ref($rqye,1) / (Ref($rzrqye,1)+1)`
- `lev_margin_buy_intensity_5d` (+): financing-buy intensity vs turnover.
  `Mean(Ref($rzmre,1),5) / (Ref($amount,1)+1)`
- `lev_margin_to_mktcap` (sign TBD): margin balance as a fraction of market cap (leverage level).
  `Ref($rzye,1) / (Ref($total_mv,1)+1)`

### Tier 2 — 龙虎榜 + 大宗 (sparse events; construction caveat §4)
- `attn_lhb_recency_20d` (sign TBD): recency-decayed 龙虎榜 appearance intensity.
- `attn_inst_netbuy_20d` (+): institutional seat net-buy on 龙虎榜, decayed.
- `block_discount_20d` (−): recent block-trade price vs market close (discount = informed selling).

### Tier 3 — 筹码 + northbound (short IS)
- `chip_winner_rate` (− reversal / + momentum, TBD): `Ref($cyq_perf__winner_rate,1)` (profit-holding ratio).
- `chip_cost_distance` (sign TBD): `(Ref($close,1)*Ref($adj_factor,1) - Ref($cyq_perf__cost_50pct,1)) / (Ref($cyq_perf__cost_50pct,1)+1)`
- `nb_hold_chg_20d` (+, foreign smart money): `Delta(Ref($ratio,1),20)`

~15 candidates (4 flow + 4 margin + 3 event + 3 chip/nb, with room to trim/add at the screen).

## 4. The sparse-event construction challenge (must resolve in the build)

`$top_list__*` / `$block_trade__*` are NaN on non-event days. A raw level is mostly NaN → unusable. The
build must FIRST confirm the materialized non-event-day value (NaN vs 0) — see
`EVENT_LIKE_DAILY_FIELD_PREFIX` materialization — then construct **recency/decay/count** signals (e.g.
"days since last 龙虎榜", "decayed net-buy", "count in 20d") rather than levels. This is the open
construction question for Tier 2; if it's awkward, Tier 2 is deferred behind Tier 1.

## 5. Process (IS-only; clean-OOS preserving)

1. **Build** the candidate expressions in a sandbox catalog (NOT yet `catalog.py`); PIT-lint each
   (`Ref(...,1)` everywhere; field-eligibility at sandbox stage — all approved).
2. **IS discovery screen** on **2014-2020** via `compute_factors(stage="sandbox_screening")` →
   `factor_eval` IC / RankIC / ICIR / quantile monotonicity / decay / turnover. Rank; keep survivors
   (e.g. |RankICIR| ≥ a pre-set bar, monotone quantiles, sane turnover).
3. **Promote survivors to the catalog** as `draft` (+ count-doc sweep) and run the **`factor_lifecycle`**
   IS-only gate → `candidate`.
4. **Sealed OOS** (later, separate gate): freeze the candidate set BEFORE touching 2021-26, claim a NEW
   `HoldoutSealStore` seal (new frozen-set hash), run the OOS ONCE → the bar-passers → `approved` via the
   promotion-evidence harness. (The clean-OOS path the 87 lack.)

## 6. Risks / open questions for review

1. **Multiple testing.** ~15 candidates screened on IS → control false positives (require economic prior
   + monotonicity + decay, not just top-IC; the lifecycle gate's yearly-sign-consistency helps). Pre-set
   the screen bar BEFORE looking.
2. **Daily-outcome PIT.** All fields are same-day outcomes → `Ref(...,1)` mandatory (enforced by the
   factor-library PIT-safety lint). Confirmed in the smoke test.
3. **moneyflow net-field opacity.** Use the 16 component fields (done above); avoid `$net_mf_amount`/
   `$net_mf_vol` (opaque vendor nets — documented caveat).
4. **Sparse-event construction (§4).** The Tier-2 NaN-handling is unresolved; may defer Tier 2.
5. **Short IS for Tier 3** (cyq 2018+, nb 2017+) → less robust; flag results as lower-confidence.
6. **Capacity/crowding.** Flow + 龙虎榜 + margin signals are crowded/capacity-limited; note for any later
   strategy use (factor `approved` ≠ tradable).
7. **OOS-seal discipline.** The whole clean-OOS advantage evaporates if 2021-26 is examined during
   design/selection. Enforce IS-only until the sealed run.

## 7. Verdict requested

GO to build Phase 1 — the **Tier-1 (moneyflow + margin) candidate expressions + the IS-2014-2020
discovery screen** — as the first concrete step (cheap, IS-only, tells us which new-data factors carry
signal before any catalog/gate commitment). Tier 2/3 follow based on Tier-1 results + the §4 resolution.
Or redirect (different families first, a wider/narrower candidate set, etc.).
