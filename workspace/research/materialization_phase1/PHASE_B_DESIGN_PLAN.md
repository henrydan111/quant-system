# Phase B Design Plan — vendor `q_*` → PIT-correct `_sq` factors

**Context.** The 25 Tushare `q_*` single-quarter fina_indicator fields were intentionally left
unregistered (field_status.yaml indicators block, 2026-06-09: *"we self-compute PIT-correct pit_*/_sq
equivalents; the vendor q_* are not guaranteed PIT-safe"*). The Phase-1 rebuild materialized their bins
but they are **inert** (unregistered → formal fail-closed, loader-refused, sandbox-warn). This plan
replaces the *valuable* ones with **our own PIT-correct `_sq` derivations** — never registering the
vendor field. PIT correctness is the cardinal constraint (§3.2).

**Classification (verified against the live provider + ledgers):**
- **23 fully derivable** from existing PIT-correct `_sq` fields → Part A (factor definitions, no build).
- **1 needs a base-field materialization** (`q_impair_to_gr_ttm`) → Part B.
- **1 genuinely hard** (`q_dtprofit` 扣非单季) → Part C (the focus; new derivation + validation).

---

## Part A — Define the 23 derivable `q_*` as factors (no new materialization)

Each is expressible from existing, validated `_sq` fields. PIT-correct **by construction**: the `_sq`
snapshots anchor on `effective_date` (strict next-open after disclosure, §3.2); every `$field` sits
inside a `Ref(...,1)` frame per the factor-library PIT-safety invariant. All enter as **`draft`**
status (discovery-usable; promotion is a separate sealed-OOS gate).

| factor (proposed) | vendor q_* replaced | expression (over existing `_sq`, each field `Ref(...,1)`) |
|---|---|---|
| `earn_np_yoy_q` | q_netprofit_yoy | `(n_income_sq_q0 − n_income_sq_q4)/Abs(n_income_sq_q4)` |
| `grow_sales_yoy_q` | q_gr_yoy | `(revenue_sq_q0 − revenue_sq_q4)/Abs(revenue_sq_q4)` |
| `earn_op_yoy_q` | q_op_yoy | `(operate_profit_sq_q0 − operate_profit_sq_q4)/Abs(operate_profit_sq_q4)` |
| `earn_totprofit_yoy_q` | q_profit_yoy | `(total_profit_sq_q0 − total_profit_sq_q4)/Abs(total_profit_sq_q4)` |
| `grow_sales_qoq_q` | q_sales_qoq / q_gr_qoq | `(revenue_sq_q0 − revenue_sq_q1)/Abs(revenue_sq_q1)` |
| `earn_np_qoq_q` | q_netprofit_qoq | `(n_income_sq_q0 − n_income_sq_q1)/Abs(n_income_sq_q1)` |
| `earn_totprofit_qoq_q` | q_profit_qoq | `(total_profit_sq_q0 − total_profit_sq_q1)/Abs(total_profit_sq_q1)` |
| `qual_gross_margin_q` | q_gsprofit_margin | `(revenue_sq_q0 − oper_cost_sq_q0)/revenue_sq_q0` |
| `qual_net_margin_q` | q_netprofit_margin | `n_income_sq_q0/revenue_sq_q0` |
| `qual_op_margin_q` | q_op_to_gr | `operate_profit_sq_q0/revenue_sq_q0` |
| `qual_totprofit_margin_q` | q_profit_to_gr | `total_profit_sq_q0/revenue_sq_q0` |
| `qual_opincome_margin_q` | q_opincome / q_op_to_gr | `(total_revenue_sq_q0 − total_cogs_sq_q0)/revenue_sq_q0` |
| `qual_adminexp_ratio_q` | q_adminexp_to_gr | `admin_exp_sq_q0/revenue_sq_q0` |
| `qual_finaexp_ratio_q` | q_finaexp_to_gr | `fin_exp_sq_q0/revenue_sq_q0` |
| `qual_exp_to_sales_q` | q_exp_to_sales | `(admin_exp_sq_q0 + sell_exp_sq_q0 + fin_exp_sq_q0)/revenue_sq_q0` |
| `qual_ocf_to_or_q` | q_ocf_to_or | `n_cashflow_act_sq_q0/revenue_sq_q0` |
| `qual_salescash_to_or_q` | q_salescash_to_or | `c_fr_sale_sg_sq_q0/revenue_sq_q0` |
| `earn_eps_q` | q_eps | `n_income_attr_p_sq_q0/total_share` |
| `earn_investincome_to_ebt_q` | q_investincome_to_ebt | `invest_income_sq_q0/total_profit_sq_q0` |
| `qual_opincome_to_ebt_q` | q_opincome_to_ebt | `(total_revenue_sq_q0 − total_cogs_sq_q0)/total_profit_sq_q0` |
| `earn_investincome_q` | q_investincome | `invest_income_sq_q0` (level; pair with size scaling downstream) |
| `qual_dtprofit_to_profit_q` | q_dtprofit_to_profit | `profit_dedt_sq_q0/total_profit_sq_q0` (depends on Part C) |

**Design rules for Part A:**
1. **Catalog-duplicate audit FIRST** (`catalog_composition()` + a name/expression scan): some already
   exist (e.g. `grow_sales_yoy_q` ≈ the validated `SalesQGr%PY`; `qual_gross_margin_q` ≈ rung-4
   `GrossProfit%...`). Skip any duplicate; the catalog↔registry parity test forbids duplicate ids.
2. **Redundancy disclosure**: these are a *correlated family* (one YoY cluster, one margin cluster).
   Define them (per directive) but they are NOT independent discoveries — downstream selection is by
   marginal orthogonal contribution, not standalone ICIR (memory `reference_factor_selection_marginal_not_icir`).
3. **Denominator guards**: division by `revenue_sq`/`total_profit_sq`/`total_share` must guard 0/NaN
   (the rung-4/5 `If(denom!=0,...)` pattern) — financial/net-cash firms have undefined ratios → sub-universe.
4. **Where**: factor library [operators.py](../../../src/alpha_research/factor_library/operators.py) /
   [catalog.py](../../../src/alpha_research/factor_library/catalog.py); `sync_catalog` to the registry as `draft`.

---

## Part B — `q_impair_to_gr_ttm` (needs a base-field materialization)

`assets_impair_loss` (资产减值损失) IS in the income ledger but `$assets_impair_loss_sq` is not
materialized (income family built before it entered the ledger / sparse post-2019 新准则 — most
impairment moved to 信用减值损失). **Plan: DEFER** — materializing one sparse field needs a full income
rebuild for low marginal value. Revisit if a future income rebuild happens for another reason, then
the factor is `TTM(assets_impair_loss_sq)/TTM(revenue_sq)`.

---

## Part C — `q_dtprofit` (扣非净利润单季): the hard case — DESIGN FOR ACCURACY + PIT

**Goal.** A PIT-correct single-quarter 扣非净利润 (扣除非经常性损益后的归母净利润), replacing the
PIT-uncertain vendor `q_dtprofit`.

**Source (verified).** `profit_dedt` (扣非净利润, **cumulative YTD**) in the indicators (fina_indicator)
ledger — confirmed cumulative (600519 2022: 17.24B → 29.76B → 44.39B → 62.79B). `extra_item`
(非经常性损益) is also cumulative there. The vendor `q_dtprofit` is the single-quarter we are replacing.

**Derivation.** single-q = `profit_dedt[Q] − profit_dedt[Q−1]` (Q1 = `profit_dedt[Q1]`) — the standard
`derive_single_quarter_value` logic already used PIT-correctly by the income/cashflow flow families.

**Implementation options:**
- **Option A — custom materializer (RECOMMENDED).** `_materialize_profit_dedt_sq`, mirroring
  `_materialize_forecast_growth`: read the indicators ledger's `profit_dedt` cumulative, apply
  `derive_single_quarter_value`, write `$profit_dedt_sq_q0..q4`. Self-contained; does not restructure
  the indicators (snapshot) dataset.
- **Option B — flow-family inclusion.** Register `profit_dedt` into a flow family so the standard
  machinery derives it. More invasive (indicators is not a flow family). Rejected unless A proves unsafe.

**PIT-correctness (by construction, NOT validated against the distrusted vendor field):**
1. `profit_dedt` anchors on the indicators `ann_date` → `effective_date` (strict next-open after
   disclosure, §3.2) — the same anchor as the already-approved `q_roe`.
2. Cumulative→single-q respects restatement: `derive_single_quarter_value` retroactively updates the
   single-q at a restatement's `effective_date` (§3.2 cumulative→quarterly late-restatement) — best-known
   state, no lookahead.
3. Predictive factors wrap in `Ref(...,1)`; served NaN where the cumulative chain is not yet
   PIT-computable is meaningful, not an error.

**Accuracy validation (the "ensure accuracy" requirement) — value, not timing:**
- **Primary oracle — 果仁** (trusted benchmark): if a 果仁 book displays 扣非净利润单季 or `EpsExclXorQ`
  (`IfNULL(扣非净利润单季, 归母单季)/总股本`), holding-level parity (the rung-2/4 method). Preferred.
- **Secondary oracle — vendor `q_dtprofit` VALUE**: Tushare's single-q *value* is correct (only its PIT
  timing is uncertain) — our `$profit_dedt_sq` should match it near-exactly; a mismatch flags a
  derivation bug.
- **Consistency cross-check**: `$profit_dedt_sq` vs the alternative `n_income_attr_p_sq − (single-q of
  extra_item)` — the two independent derivations must agree.

**PIT validation:** restatement canary (as-of OLD the day before / NEW on the restatement
effective_date) + provider-read exact-date audit (served value PIT-correct; NaN where not computable).

**Factors (Part C output):** `qual_dtprofit_to_profit_q` = `profit_dedt_sq_q0/total_profit_sq_q0`;
optionally `earn_dtprofit_yoy_q` = `(profit_dedt_sq_q0 − sq_q4)/Abs(sq_q4)`.

**Governance:** new materializer = substantial → GPT cross-review (like the forecast R1→R4); staged
build + publish + register `$profit_dedt_sq` + the factors; re-bind.

---

## Sequencing & risks

1. **Part A** (define 23 factors) — independent, no build. Catalog-audit → define → `sync_catalog` (draft).
2. **Part C** (q_dtprofit) — new materializer → build/publish/register; the `qual_dtprofit_to_profit_q`
   factor depends on it.
3. **Part B** deferred.

**Risks to flag for review:**
- Deriving a single-q flow from the **indicators (snapshot) ledger** — is the cumulative semantics +
  restatement handling sound when the source dataset is configured as a snapshot, not a flow?
- Using the **distrusted vendor field as the accuracy oracle** — valid for *value* (the PIT concern is
  *timing*), but is that separation airtight, or could a vendor value-error hide here? (果仁 oracle preferred.)
- **Catalog redundancy / multiplicity** — 23 correlated single-q factors are not independent signals.
- **Denominator domain** — financial/net-cash firms: undefined ratios → sub-universe masks, not data defects.
