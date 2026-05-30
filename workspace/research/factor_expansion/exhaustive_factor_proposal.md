# Exhaustive Factor Proposal — A-Share Multi-Factor System

**Status:** research proposal — Rounds 1 (Claude) + 2 + 3 (GPT 5.5 Pro review integrated). Not wired into the catalog.
**Date:** 2026-05-30.
**Author:** Claude (handoff prep), reviewed and complemented by GPT 5.5 Pro (2 rounds).
**Companion artifacts (same repo):**
- [`factor_candidates_merged.csv`](factor_candidates_merged.csv) — **canonical merged set: 70 unique factors** (51 Claude-v2 + 19 GPT, deduplicated), each re-stamped with live field-registry status + a `source` column. **Source of truth for exact expressions.** All rows pass raw-field-existence + PIT-safety validation. **21 formal-eligible.**
- [`factor_candidates.csv`](factor_candidates.csv) — the Claude-generated set (51 rows, post Round-2/3 fixes).
- [`../../../Knowledge/factor_expansion_gpt_review_new_candidates.csv`](../../../Knowledge/factor_expansion_gpt_review_new_candidates.csv) — GPT's Round-2 candidates.
- [`../../../Knowledge/factor_candidates_round3_additions_corrections.csv`](../../../Knowledge/factor_candidates_round3_additions_corrections.csv) — GPT's Round-3 corrections/additions.
- [`../../../data/factor_research/field_inventory.md`](../../../data/factor_research/field_inventory.md) — the 518 base field stems / 3,649 raw bins materialized in the live Qlib provider (ground-truth snapshot).
- [`../../scripts/generate_factor_candidates.py`](../../scripts/generate_factor_candidates.py) — read-only generator (hardened raw-token field-existence gate).
- [`../../scripts/validate_factor_candidates.py`](../../scripts/validate_factor_candidates.py) — read-only validator (raw-token existence + PIT parser + registry status).
- [`../../scripts/merge_factor_candidates.py`](../../scripts/merge_factor_candidates.py) — read-only merge/dedup producing the canonical merged set.

---

## Review rounds — what changed

**Round 2 (GPT 5.5 Pro).** Found a real defect: `val_payout_ratio` referenced the
non-existent `$cash_div_q0` (dividends endpoint has no `_q0..q4` variants). Root-cause
fix: the field-existence gate now validates every **raw `$field` token** against the
materialized bin set, not collapsed base stems. Applied: `_cum_q0`→TTM `_sq`-sum rewrites
(EV value, accruals, cash-ROA, capex/R&D, net-debt/EBITDA, interest coverage); QoQ→YoY+
acceleration; DuPont/margin dedup; true log-range Parkinson. Merged GPT's 27 candidates.

**Round 3 (GPT 5.5 Pro).** Verified the integration and caught residual issues, all fixed:
(a) `qual_gross_profitability` still used `_cum_q0`/end-assets → replaced with TTM/avg-assets
(`qual_gross_profitability_ttm`, decay 250); (b) `qual_cash_roa` dropped (redundant with
`acc_cash_roa_ttm`); (c) the YoY-acceleration rows were mis-specified (needed the
unmaterialized `_sq_q5`) → rewritten as `Delta(YoY, 63)`; (d) **moneyflow unit fix** —
amounts are 万元 vs daily `$amount` 千元 → divide by `($amount/10)`; (e) **margin unit fix**
— `rzmre/rzche` 元 vs `circ_mv` 万元 → `* 10000`; (f) `mom_continuous_info_252d` sign bug
(smooth losers ranked high) → `mom_continuous_info_252d_dir` with `Abs()`; (g)
`risk_parkinson_logrange_{60,120}d` decay now tracks the window. Added 4 approved
price/volume families (`mom_skip5d_120d`, `risk_garman_klass_20d`, `rev_turnover_spike_5d`,
`mom_continuous_info_252d_dir`), lifting formal-eligible to **21**. §3 below is Round-1 and
**superseded** — see the merged CSV.

---

## 0. Purpose & how to read this

The current factor library is **171 named factors** but consumes only **~50 of the
518 materialized field stems**. This document maps the *entire* constructible factor
surface from the present backend, organized as **factor families** (templates), each
with a PIT-safe Qlib expression skeleton, the fields it consumes, its **field-registry
status**, expected sign, decay horizon, and default neutralization.

**The ask for GPT 5.5 Pro:** review this enumeration for (a) missing factor angles,
(b) A-share-specific anomalies we have not encoded, (c) which untapped fields are the
highest-priority to promote out of `unknown_field`/`quarantine`, and (d) redundancy /
multicollinearity risks within the proposed set. See §6 for explicit prompts.

Every expression below obeys the system's hard invariants (verified by the generator
and the PIT-safety parser — see §5):
- **PIT safety:** every `$field` is wrapped in `Ref(..., 1)` (or uses the `ADJ_*_T1`
  adjusted-price atoms). Factor value at *t* uses data only through *t−1*.
- **Negation:** `0 - Operator(...)`, never `-Operator(...)`.
- **Adjusted vs raw:** adjusted price (`$close*$adj_factor`) for cross-day
  returns/momentum; raw values for PIT accounting ratios.

---

## 1. Backend field inventory (what we can actually query)

Verified by enumerating `data/qlib_data/features/<stock>/*.bin` and collapsing PIT
suffixes (full list in [`field_inventory.md`](../../../data/factor_research/field_inventory.md)):

| Source dataset | Field family | Approx. base stems | Registry status |
|---|---|---|---|
| `market_daily` | OHLCV, `pre_close`, `adj_factor`, `pct_chg`, `change` | 10 | **approved** |
| `daily_basic` | `pe/pe_ttm/pb/ps/ps_ttm`, `dv_ratio/dv_ttm`, `total_mv/circ_mv`, `total_share/float_share/free_share`, `turnover_rate(_f)`, `volume_ratio` | 15 | **approved** |
| `indicators` (`fina_indicator_vip`) | `roe/roa/roic`, margins, turnover, per-share, leverage, YoY/QoQ | ~109 | **approved** |
| `pit_fundamentals` | curated `$pit_*` PIT-derived growth aliases | ~7 | **approved** |
| `income` statement line-items | `total_revenue`, `oper_cost`, `ebit`, `ebitda`, `n_income`, `rd_exp`, `int_exp`, … (`_cum_q0..4`, `_q`, `_sq_q0..4`) | ~85 | **unknown_field** (materialized, unregistered) |
| `balancesheet` line-items | `total_assets`, `total_liab`, `money_cap`, `inventories`, `accounts_receiv`, `goodwill`, `st_borr/lt_borr`, … (`_q0..4`) | ~152 | **unknown_field** |
| `cashflow` line-items | `n_cashflow_act`, `c_pay_acq_const_fiolta`, `free_cashflow`, … (`_cum_q0..4`, `_sq_q0..4`) | ~60 | **unknown_field** |
| `moneyflow` | `buy/sell_{sm,md,lg,elg}_{vol,amount}`, `net_mf_amount/vol` | ~18 | **quarantine** |
| `hk_hold` (northbound) | `ratio` (foreign-holding %) | 1 | **quarantine** |
| `margin_detail` | `rzye/rqye/rzmre/rzche/rqmcl/rqchl/rzrqye` | 7 | **quarantine** |
| `stk_limit` | `up_limit/down_limit` | 2 | **quarantine** |
| `top_list` / `top_inst` | 龙虎榜 per-stock + institutional (`$top_list__*`, `$top_inst__*`) | ~16 | **pending_review** |
| `block_trade` | `$block_trade__{price,vol,amount}` | 3 | **pending_review** |
| `cyq_perf` | chip distribution (`$cyq_perf__cost_*`, `winner_rate`, `weight_avg`) | 9 | **pending_review** |
| `stk_holdertrade` | `$holdertrade_{net_vol,gross_vol,net_ratio,events}` | 4 | **pending_review** |
| `reference` | `industry`, `sw2021_l1/l2`, `is_st` | 4 | **approved** |

**PIT-variant grammar** (applies to every fundamental field):

| Suffix | Meaning |
|---|---|
| `_q0 .. _q4` | snapshot value, latest → 4-period lag (balance sheet / indicators) |
| `_cum_q0 .. _cum_q4` | cumulative period value, latest → 4-lag (income / cashflow) |
| `_q` | single-quarter derived value |
| `_sq_q0 .. _sq_q4` | single-quarter snapshot, latest → 4-lag |

This is the lever that makes the surface combinatorial: every statement line-item
yields level, YoY (`_sq_q0 / _sq_q4`), QoQ (`_sq_q0 / _sq_q1`), trend (`Slope` over
`_sq_q0..q4`), and stability (`Std` over the quarter lags) variants.

---

## 2. Gap analysis — what the current 171-factor catalog leaves on the table

**Fields the current catalog uses (~50):** OHLCV + `adj_factor`; `pe/pe_ttm/pb/ps/ps_ttm`,
`dv_ratio/dv_ttm`, `total_mv/circ_mv/free_share`, `turnover_rate(_f)`, `volume_ratio`;
indicator ratios `roe/roa/roic`, margins, `assets_turn`, `debt_to_assets`,
`current_ratio/quick_ratio`, `ocfps/bps/eps`, and YoY/QoQ growth fields; plus the
new-data fields (moneyflow / northbound / margin / alpha endpoints) behind
`include_new_data=True`.

**Entirely untapped (the opportunity):**

1. **Raw statement line-items (~300 stems).** The catalog uses vendor *ratios* but never
   the *building blocks*. This blocks every accruals, working-capital, asset-composition,
   and EV-based factor — the single biggest gap.
2. **Single-quarter (`_sq`) growth series.** The catalog's growth factors use the
   indicator YoY snapshots (`or_yoy`, `netprofit_yoy`); it never builds clean
   single-quarter YoY/QoQ/acceleration from `revenue_sq_q0..q4`.
3. **Cashflow quality.** `n_cashflow_act`, `c_pay_acq_const_fiolta`, `free_cashflow` are
   materialized but unused → no FCF yield, OCF/EV, cash-ROA, accruals, CapEx intensity.
4. **EV-based value.** `total_liab` + `money_cap` + `total_mv` enable EV/EBITDA, EBIT/EV,
   OCF/EV — none exist today (the catalog is price-multiple-only on value).
5. **Balance-sheet composition & investment.** `goodwill`, `intan_assets`, `rd_exp`,
   `inventories`, `accounts_receiv` → quality/earnings-management angles unused.
6. **Path-shape & risk-adjusted price factors.** 52-week-high proximity, vol-scaled
   momentum, Parkinson range vol, Lesmond zero-return illiquidity — standard anomalies
   absent from the current windows-only momentum/vol families.

---

## 3. Factor families by category

> ⚠️ **SUPERSEDED — historical / non-authoritative (retained for audit trail).**
> The skeletons in §3 are the **Round-1** expressions and contain known issues that
> were fixed in Round 2/3: `val_payout_ratio` referenced the non-existent
> `$cash_div_q0`; the EV/cashflow/accrual/leverage rows used `_cum_q0` (YTD,
> quarter-seasonal) instead of TTM `_sq` sums; the "Parkinson" row was a range
> ratio; the moneyflow/margin ratios had unit-scale bugs. **Do not copy expressions
> from §3.** The single source of truth for exact, validated expressions is
> [`factor_candidates_merged.csv`](factor_candidates_merged.csv) (70 rows, every
> row passes raw-field-existence + PIT-safety validation). §3 is kept only to show
> the original family taxonomy and rationale.

Notation: expressions are Qlib strings. `ADJ` = `($close * $adj_factor)`. Status is the
**worst-case** registry status across the fields the family touches (formal-eligible only
if *all* fields are `approved`). **For current expressions see the merged CSV, not these
tables.**

### 3.1 Value (extend) — EV / cashflow yields

| Family | Skeleton (PIT-safe) | Fields | Status | Sign | Decay |
|---|---|---|---|---|---|
| `val_ev_ebitda` | `(Ref($total_mv,1)*10000 + Ref($total_liab_q0,1) - Ref($money_cap_q0,1)) / Ref($ebitda_cum_q0,1)` | total_mv, total_liab, money_cap, ebitda | unknown_field | − | 60 |
| `val_ebit_ev` | `Ref($ebit_cum_q0,1) / (EV)` | ebit, total_liab, money_cap, total_mv | unknown_field | + | 60 |
| `val_fcf_yield` | `(Ref($n_cashflow_act_cum_q0,1) - Ref($c_pay_acq_const_fiolta_cum_q0,1)) / (Ref($total_mv,1)*10000)` | OCF, CapEx, total_mv | unknown_field | + | 90 |
| `val_ocf_ev` | `Ref($n_cashflow_act_cum_q0,1) / (EV)` | OCF, EV components | unknown_field | + | 90 |
| `val_retearn_yield` | `Ref($retained_earnings_q0,1) / (Ref($total_mv,1)*10000)` | retained_earnings, total_mv | unknown_field | + | 120 |
| `val_ncav_to_price` | `(Ref($total_cur_assets_q0,1) - Ref($total_liab_q0,1)) / (Ref($total_mv,1)*10000)` | cur_assets, total_liab, total_mv | unknown_field | + | 120 |
| `val_payout_ratio` | `Ref($cash_div_q0,1) / Ref($eps,1)` | cash_div, eps | unknown_field | ? | 250 |

Price basis: **mixed** (raw fundamentals over market cap; market cap is a price quantity
but used point-in-time, not cross-day, so no `adj_factor`).

### 3.2 Quality / profitability (large expansion)

| Family | Skeleton | Fields | Status | Sign |
|---|---|---|---|---|
| `qual_gross_profitability` | `(Ref($total_revenue_cum_q0,1) - Ref($oper_cost_cum_q0,1)) / Ref($total_assets_q0,1)` | revenue, oper_cost, assets | unknown_field | + |
| `qual_cash_roa` | `Ref($n_cashflow_act_cum_q0,1) / Ref($total_assets_q0,1)` | OCF, assets | unknown_field | + |
| `qual_dupont_margin` | `Ref($netprofit_margin,1)` | netprofit_margin | **approved** | + |
| `qual_dupont_turnover` | `Ref($assets_turn,1)` | assets_turn | **approved** | + |
| `qual_margin_{grossprofit_margin,netprofit_margin,op_of_gr,ebit_of_gr,profit_to_gr}` | `Ref($<f>,1)` | indicator ratios | mixed (3 approved, 2 unknown) | + |

Novy-Marx gross profitability and cash-ROA are the headline additions; they require the
raw statement line-items (currently `unknown_field`). The DuPont legs and margin-ladder
members built from registered indicator fields are **formal-eligible today**.

### 3.3 Accruals / earnings quality (NEW — the biggest gap)

| Family | Skeleton | Fields | Status | Sign |
|---|---|---|---|---|
| `acc_total_accruals_ni_ocf` | `(Ref($n_income_cum_q0,1) - Ref($n_cashflow_act_cum_q0,1)) / Ref($total_assets_q0,1)` | NI, OCF, assets | unknown_field | − |
| `acc_cfo_to_ni` | `Ref($n_cashflow_act_cum_q0,1) / Ref($n_income_cum_q0,1)` | OCF, NI | unknown_field | + |
| `acc_asset_growth` | `Ref($total_assets_q0,1) / Ref($total_assets_q4,1) - 1` | assets | unknown_field | − |
| `acc_noa_scaled` | `(assets − cash − liab + st_borr + lt_borr) / Ref($total_assets_q4,1)` | assets, money_cap, liab, borr | unknown_field | − |
| `acc_dWC_inventory` | `(Ref($inventories_q0,1) - Ref($inventories_q4,1)) / Ref($total_assets_q4,1)` | inventories, assets | unknown_field | − |
| `acc_dWC_receivables` | `(Ref($accounts_receiv_q0,1) - Ref($accounts_receiv_q4,1)) / Ref($total_assets_q4,1)` | AR, assets | unknown_field | − |
| `acc_capex_intensity` | `Ref($c_pay_acq_const_fiolta_cum_q0,1) / Ref($total_assets_q0,1)` | CapEx, assets | unknown_field | − |
| `acc_rd_intensity` | `Ref($rd_exp_cum_q0,1) / Ref($total_revenue_cum_q0,1)` | rd_exp, revenue | unknown_field | + |
| `acc_goodwill_ratio` | `Ref($goodwill_q0,1) / Ref($total_assets_q0,1)` | goodwill, assets | unknown_field | − |
| `acc_net_share_issuance` | `0 - (Ref($total_share,1) / Ref($total_share,251) - 1)` | total_share | **approved** | + |

Canonical anomalies (Sloan accruals, Cooper asset growth, Hirshleifer NOA, Pontiff/Woodgate
net-share-issuance). All but net-share-issuance need the unregistered statement fields.
`acc_net_share_issuance` uses only `total_share` (daily_basic) and is **formal-eligible today**.

### 3.4 Growth (single-quarter `_sq` extension)

Template per field `f ∈ {revenue, operate_profit, n_income_attr_p, total_revenue}`:
- YoY: `Ref($<f>_sq_q0,1) / Ref($<f>_sq_q4,1) - 1`
- QoQ: `Ref($<f>_sq_q0,1) / Ref($<f>_sq_q1,1) - 1`

Status `unknown_field` (single-quarter `_sq` series are statement-derived). Extends
trivially to acceleration (`Delta` of YoY) and 4-quarter `Slope`. Expected sign +,
decay 60–90 days. The existing catalog only has the indicator-snapshot YoY equivalents.

### 3.5 Leverage / solvency (extend)

| Family | Skeleton | Status | Sign |
|---|---|---|---|
| `lev_net_debt_to_ebitda` | `(st_borr + lt_borr − money_cap) / ebitda_cum_q0` | unknown_field | − |
| `lev_interest_coverage` | `Ref($ebit_cum_q0,1) / Ref($int_exp_cum_q0,1)` | unknown_field | + |

Complements the existing registered `debt_to_assets/current_ratio/quick_ratio` factors
with debt-service and coverage angles.

### 3.6 Momentum / reversal (extend) — **all formal-eligible**

| Family | Skeleton | Status | Sign |
|---|---|---|---|
| `mom_52w_high_proximity` | `ADJ_T1 / Max(ADJ_HIGH_T1, 250)` | **approved** | + |
| `mom_volscaled_{20,60,120}d` | `momentum(w) / (Std(DAILY_RET, w) + 1e-4)` | **approved** | + |

George-Hwang 52-week-high and volatility-scaled (risk-adjusted) momentum — both buildable
from price alone, so deployable now. Further untapped: residual/idiosyncratic momentum
(Layer-2, needs market+industry regression), information-discreteness (Da-Gurun-Warachka).

### 3.7 Volatility / risk (extend) — **all formal-eligible**

| Family | Skeleton | Status | Sign |
|---|---|---|---|
| `risk_parkinson_{20,60,120}d` | `Mean(Ref(($high-$low)/$close,1), w)` | **approved** | − |

Untapped extensions (Layer-2 / multi-field): CAPM beta, idiosyncratic vol vs market,
co-skewness, downside/upside beta, Garman-Klass range vol.

### 3.8 Liquidity / microstructure (extend) — **all formal-eligible**

| Family | Skeleton | Status | Sign |
|---|---|---|---|
| `liq_zero_ret_days_{5,10,20}d` | `Count(Abs(DAILY_RET) < 1e-4, w) / w` | **approved** | − |

Lesmond zero-return illiquidity. Untapped: Roll effective-spread proxy, Amihud variants
on free-float dollar volume.

### 3.9 Capital flow (`moneyflow` — quarantine)

| Family | Skeleton | Status | Sign |
|---|---|---|---|
| `flow_elg_net_pct_{5,10,20}d` | `Mean(Ref((($buy_elg_amount-$sell_elg_amount)/$amount),1), w)` | quarantine | + |

Extra-large-order net inflow share (smart-money proxy). Not formal-eligible until
`moneyflow` clears anomaly review. Untapped: order imbalance across all four size tiers,
retail-vs-institutional divergence (`sm` vs `elg`), flow persistence/autocorrelation.

### 3.10 Margin (`margin_detail` — quarantine)

| Family | Skeleton | Status | Sign |
|---|---|---|---|
| `margin_net_buy_ratio_20d` | `Mean(Ref(($rzmre-$rzche),1), 20) / Ref($circ_mv,1)` | quarantine | + |

Untapped: margin balance / float, short-selling balance Δ, margin-to-short ratio.

### 3.11 Alpha endpoints (`top_*`/`block_trade`/`cyq_perf`/`holdertrade` — pending_review)

| Family | Skeleton | Status | Sign |
|---|---|---|---|
| `alpha_chip_winner_rate_level` | `Ref($cyq_perf__winner_rate,1)` | pending_review | ? |

The current catalog already has ~20 alpha-endpoint factors (chip distribution, 龙虎榜
flow, block-trade discount, insider net-buy). Untapped: cost-percentile compression as a
breakout precursor, chip-concentration regime, institutional-vs-retail 龙虎榜 divergence.

### 3.12 Composites (Layer-2)

Once §3.1–3.3 land, natural composites: **Piotroski F-score** (9 binary accruals/
profitability/leverage signals), **Quality-Minus-Junk** (profitability+growth+safety),
**accruals-screened value** (cheap *and* clean earnings). These reuse
`operators.add_composites` rank-blending — no new fields beyond their components.

---

## 4. PIT / registry caveats — what blocks formal use today

Of the 51 representative instances: **15 approved (formal-eligible now)**, **31
`unknown_field`**, **4 quarantine**, **1 pending_review**.

- **`unknown_field` (statement line-items):** materialized in the provider but **not
  listed** in [`field_status.yaml`](../../../config/field_registry/field_status.yaml).
  They fail-closed at formal stages (`unknown_field_policy[formal_validation] = fail`).
  **To promote:** add an `income` / `balancesheet` / `cashflow` dataset entry (status
  `approved`, PIT-anchored on `max(ann_date, f_ann_date)` per CLAUDE.md §3) + an approval
  YAML under `config/field_registry/approvals/`. These flow through the *same* PIT
  pipeline as the already-approved `$pit_*` and `indicators` families, so the promotion is
  a registry/governance step, not a data change — but it needs the PR-9a-style review
  (per-family bare-name guardrail tests + indicator-style `Ref(...,1)` lag contract).
- **`quarantine` (moneyflow / margin / northbound):** downloaded, pending anomaly review.
  Usable in sandbox/vectorized screening, blocked at formal. Promotion requires the
  anomaly review noted in `project_state` 2026-05-26.
- **`pending_review` (alpha endpoints):** namespacing fixed (2026-04-20), anomaly review
  WIP. Same gating as quarantine for formal stages.

**Recommended sequencing:** (1) screen the 15 already-formal families immediately;
(2) prioritize promoting the **cashflow + core balance-sheet** line-items (unlock
accruals + FCF + EV value — the highest-conviction academic anomalies); (3) defer
moneyflow/margin/alpha until their anomaly reviews complete.

---

## 5. Verification performed

Applies to the canonical [`factor_candidates_merged.csv`](factor_candidates_merged.csv)
(70 rows) via [`validate_factor_candidates.py`](../../scripts/validate_factor_candidates.py):

- **PIT-safety:** all 70 merged expressions pass the project's own
  `find_unwrapped_field_references` parser (from
  [`test_factor_library_pit_safety.py`](../../../tests/alpha_research/test_factor_library_pit_safety.py)) —
  zero unwrapped `$field`.
- **Field existence (hardened in Round 2):** every raw `$field` token in every expression
  exists in the materialized **3,649-bin** set — not just the collapsed 518 base stems.
  This is the check that catches non-existent PIT variants like `$cash_div_q0`. 0 failures.
- **Status stamping:** resolved via the live registry
  ([`field_registry.py`](../../../src/data_infra/field_registry.py)) — 21 approved /
  formal-eligible, 38 unknown_field, 8 quarantine, 3 pending_review.
- **Caveat — STATIC validation only.** No Qlib parser/runtime execution yet. Expressions
  are confirmed field-valid + PIT-safe + registry-resolved, but not yet computed. Runtime
  screening is the next phase (gated behind promoting the Wave-1 statement fields per §7).
- **No system mutation:** only the handoff files were written; `data/qlib_data/`,
  `config/`, `src/`, and all registries untouched.

---

## 6. Open questions for GPT 5.5 Pro

1. **Missing families:** what well-established A-share / EM-equity factors are absent
   here? (Candidates we deliberately left for you: Piotroski F-score detail, QMJ,
   seasonality/`turn-of-quarter`, analyst-revision proxies via `forecast`, beta-arbitrage,
   short-term-reversal conditioning on liquidity.)
2. **A-share specificity:** which factors need A-share-specific treatment (T+1, 10%/20%
   limit boards, ST handling, retail-dominated microstructure, state-ownership)? The
   `cyq_perf` chip-distribution and `moneyflow` tier data are A-share-rich — what is the
   best way to exploit them?
3. **Promotion priority:** given the `unknown_field` statement line-items all share one
   PIT pipeline, which 10–20 fields would you promote first to maximize incremental
   breadth per unit of review effort?
4. **Redundancy:** which proposed families are likely to be highly collinear with the
   existing 171 (e.g. `qual_dupont_margin` ≈ existing `qual_net_margin`) and should be
   dropped or merged before screening?
5. **Sign/decay priors:** challenge any `expected_sign` / `expected_decay_days` you
   disagree with — these are priors to be tested, not claims.
6. **Construction correctness:** flag any expression where the `_q0/_cum_q0/_sq` variant
   choice is wrong for the intended economic quantity (e.g. flow vs stock mismatch in EV,
   or cumulative-vs-single-quarter in a margin).

---

## 7. GPT 5.5 Pro answers — promotion priority & A-share notes (Round 2)

These are GPT's responses to the §6 questions, retained for the implementation phase.

### 7.1 Promotion-priority ranking for `unknown_field` statement line-items

All share one PIT pipeline, so promotion is a single governance review (`field_status.yaml`
dataset entry + approval YAML), not a data change. Register in this order to maximize
factor breadth per unit of review:

**Wave 1 (unlocks accruals + cash quality + gross profitability + Piotroski):**
`total_assets`, `n_cashflow_act`, `n_income_attr_p`, `total_revenue`, `oper_cost`,
`total_liab`, `money_cap`, `c_pay_acq_const_fiolta`, `accounts_receiv`, `inventories`,
`total_cur_assets`, `total_cur_liab`.

**Wave 2 (unlocks EV value + debt-service):** `ebit`, `ebitda`, `st_borr`, `lt_borr`,
`fin_exp_int_exp`, `rd_exp`, `goodwill`, `total_hldr_eqy_exc_min_int`.

**Wave 3 (derived):** `fcff`, `fcfe`, `interestdebt`, `netdebt`, `working_capital`,
`retained_earnings` — promote raw building blocks first since they make vendor-derived
formulas auditable.

Note: GPT recommends registering the **`_sq` single-quarter variants** specifically (the
TTM constructions depend on `_sq_q0..q3`), and confirming the indicator-style `Ref(...,1)`
lag contract + per-family bare-name guardrail tests (PR-9a pattern) at promotion time.

### 7.2 A-share-specific implementation notes

- **T+1 / close-to-open:** the gap-reversal and high-turnover-reversal families must be
  evaluated with the **EventDrivenBacktester (T+1)**, not a same-day-exit vector backtest —
  a close-to-close signal can look tradable while being unrealizable.
- **Limit boards:** do **not** hard-code 10%/20%. Use `$up_limit`/`$down_limit` (currently
  `quarantine`) once promoted; SSE main board = 10%, STAR = 20%, ST = 5%, first 5 IPO days =
  no limit. Families: `limit_up_hit_5d`, `limit_down_hit_20d`, `limit_up_distance_1d`,
  post-limit drift/reversal.
- **ST handling:** treat `is_st` primarily as a **universe/risk filter**, not alpha. Run a
  diagnostic-only segment to confirm factors aren't merely learning distress/tradability.
- **Retail microstructure:** the strongest A-share pattern is **interactions** — small-order
  vs large/extra-large flow, turnover spikes, chip-cost compression, holder-count changes —
  not standalone levels.
- **State ownership:** a real axis but **not constructible** from current materialized
  fields. Do not fake it with size/industry/leverage. Future dataset: actual
  controller / SOE flag, then SOE × {leverage, default-risk, value}.
- **Seasonality:** add as **Layer-2 calendar features** (turn-of-month, half-month, Lunar
  New Year, holiday, report-window, post-report drift), not Qlib `$field` expressions.
- **Forecast/revision:** `forecast` endpoints are materialized but unregistered; best first
  three are midpoint level, midpoint revision, band width — short decay (~20–30d).

### 7.3 Recommended implementation sequence

1. **Screen the 18 formal-eligible factors now** (no registry change needed).
2. **Promote Wave-1 statement fields together** (one governance review) → unlocks the
   accruals / cash-quality / gross-profitability / Piotroski / working-capital cluster.
3. **Promote Wave-2 EV/debt fields** → FCF/EV, EBITDA/EV, net-debt/EBITDA, interest coverage.
4. **Keep quarantine/pending families in research only** until their anomaly reviews clear.
5. **Add Layer-2 features** for seasonality and (future) state ownership.

---

*Round 1 generated by Claude; Round 2 integrates the GPT 5.5 Pro review. The merged CSV
([`factor_candidates_merged.csv`](factor_candidates_merged.csv)) is the source of truth for
exact expressions; this markdown is the rationale + review surface. Every expression is
validated for raw-field existence and PIT safety by
[`validate_factor_candidates.py`](../../scripts/validate_factor_candidates.py).*
