# PRE-REGISTRATION — Tier-1 new-data factor IS discovery screen (FROZEN before screening)

**Frozen:** 2026-06-05, BEFORE running any factor-performance computation. **Author:** Claude.
**Status:** the committed git timestamp of this file is the freeze record (GPT cross-review required
change #3: freeze the IS-only design spec before screening). Nothing below may change after the screen
runs without a new dated pre-registration.

GPT cross-review (Conditional GO for Tier-1 IS-only; NO-GO for the `approved` OOS step until a
window-level OOS budget is formalized) — all 4 required changes integrated here.

## 1. OOS language (required change #1 — corrected)

The 2021-01-01..2026-02-27 window is **NOT globally "fresh/unspent."** It has already been spent once
(the 6 sealed-OOS winners, claim_index=1). For this new factor set it is **UNOBSERVED**, but the
calendar window is a **shared OOS resource**. Any future sealed-OOS run on it is `claim_index>=2` and
incurs **window-level multiple testing** — handled at the OOS stage (§6), which is a SEPARATE, later,
currently-NO-GO gate. THIS document covers only the IS-2014-2020 discovery screen.

## 2. IS window + enforcement (required change #4)

- **IS window:** 2014-01-01 .. **2020-12-31** (factor dates AND label-realization dates both ≤ 2020-12-31).
- **Warmup:** factors computed from COMPUTE_START 2013-01-01 (lookback warmup; no labels there).
- **Enforcement:** the screen runs under a `ResearchAccessContext` with `allowed_end=2020-12-31`
  (stage non-OOS) AND caps labels via the factor-lifecycle belt (`build_is_windowed_panel(is_end=
  2020-12-31)`), so NO 2021-26 bar is ever read. This is structural, not just discipline.
- **No 2021-26 performance** (returns, IC, Sharpe, monotonicity, top-k, ranking) is computed before the
  separate sealed-OOS gate (required change #2 boundary; data-QA over 2021-26 was governance only).

## 3. Frozen candidate set — Tier-1 ONLY (effective_trials = 8)

moneyflow + the 5 approved margin balance/buy fields. All `Ref(...,1)`-wrapped (daily-outcome PIT).
`$net_mf_amount`/`$net_mf_vol` (opaque vendor nets) and `$rzche`/`$rqchl` (quarantined repayment) are
EXCLUDED. `eps`=1 (amounts in 万元). Sign = economic prior (screen confirms empirical sign).

| # | name | prior | expression |
|---|---|---|---|
| 1 | `flow_mainforce_imbalance_5d` | + | `Mean((Ref($buy_lg_amount,1)+Ref($buy_elg_amount,1)-Ref($sell_lg_amount,1)-Ref($sell_elg_amount,1))/(Ref($amount,1)+1),5)` |
| 2 | `flow_mainforce_imbalance_20d` | + | same numerator, window 20 |
| 3 | `flow_retail_pressure_5d` | − | `0 - Mean((Ref($buy_sm_amount,1)-Ref($sell_sm_amount,1))/(Ref($amount,1)+1),5)` |
| 4 | `flow_elg_concentration_5d` | + | `Mean((Ref($buy_elg_amount,1)-Ref($sell_elg_amount,1))/(Ref($buy_elg_amount,1)+Ref($sell_elg_amount,1)+1),5)` |
| 5 | `lev_margin_bal_growth_20d` | TBD | `Delta(Ref($rzrqye,1),20)/(Ref($rzrqye,1)+1)` |
| 6 | `lev_short_interest_ratio` | − | `Ref($rqye,1)/(Ref($rzrqye,1)+1)` |
| 7 | `lev_margin_buy_intensity_5d` | + | `Mean(Ref($rzmre,1),5)/(Ref($amount,1)+1)` |
| 8 | `lev_margin_to_mktcap` | TBD | `Ref($rzye,1)/(Ref($total_mv,1)+1)` |

These are **a-priori economic factors** (not tuned/generated variants), so per GPT open-Q1, yearly
sign-consistency at the gate is acceptable for `candidate`; ALL 8 tested are recorded as effective
trials regardless of outcome. No lookback/parameter grid search in this batch (fixed 5/20 windows).

Tier 2 (龙虎榜/大宗, sparse) and Tier 3 (cyq 2018+/northbound 2017+) are **DEFERRED** (GPT open-Q2/Q4):
sparse-event recency/decay construction needs its own tested design; short-IS families are lower-confidence.

## 4. Screen metrics + PRE-SET bar (frozen before looking)

Compute on IS 2014-2020 via `factor_eval`: per-date RankIC → mean RankIC, **RankICIR** (mean/std),
quantile (quintile) monotonicity, IC decay, turnover. Primary horizon **20d** (also report 5d/10d).

**Survivor bar (a factor "carries signal" iff ALL hold):**
- `|RankICIR_20d| >= 0.30`, AND
- `|mean RankIC_20d| >= 0.015`, AND
- quintile spread monotone with the RankIC sign (top vs bottom quintile sign-consistent), AND
- IC not fully decayed by 20d (5d/10d/20d same sign).

Ranking metric: `|RankICIR_20d|` (desc). No multiple-testing inflation guard beyond the pre-set bar +
economic priors at THIS discovery stage; the real candidate bar is the `factor_lifecycle` IS-only gate
(yearly sign consistency etc.), applied next.

## 5. Selection rule + downstream

Survivors (≤ 8) → add to a SANDBOX catalog → PIT-safety lint + field-eligibility (sandbox stage) →
`factor_lifecycle` IS-only gate → `candidate` (in the registry). Record all 8 trials + outcomes in the
screen output JSON. No `approved` from this document.

## 6. OOS-window budget reservation (required change #2) — SEPARATE, currently NO-GO

The eventual sealed OOS for any Tier-1 candidate is a DISTINCT gate, **blocked until the window-level
OOS budget is formalized** (GPT NO-GO). When it runs it MUST record, in the testing ledger / a budget
provenance file, BEFORE touching 2021-26: `oos_window=2021-01-01..2026-02-27`, `claim_index` (>=2),
the pre-registered candidate pool + selection rule + success bar + **max selected set size**, and the
FULL effective trial count across ALL sealed tests ever run on this window (not only winners). The
window is "unobserved for this set," never "fresh."
