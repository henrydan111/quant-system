# Phase B Design Plan (v2) — vendor `q_*` → PIT-correct `_sq` factors

**Context.** The 25 Tushare `q_*` single-quarter fina_indicator fields were intentionally left
unregistered (field_status.yaml, 2026-06-09: vendor q_* not guaranteed PIT-safe; we self-compute
`_sq` equivalents). They are materialized-but-inert in the live provider. This plan replaces the
*valuable* ones with **our own PIT-correct `_sq` derivations** — never registering a vendor field.

**GPT R1 = REVISE-PLAN (no Blocker). Folded in v2:**
- **M1** (several Part-A mappings were wrong — written from assumption): re-mapped against the
  OFFICIAL Tushare fina_indicator definitions ([doc 79](../../../Tushare数据接口/content/79_财务指标数据.md)) —
  `q_profit_yoy`=净利润(NOT 利润总额); `q_netprofit_yoy`=归母; `_to_gr` ratios ÷营业总收入(total_revenue);
  `q_opincome`=经营活动净收益(=total_revenue−total_cogs, NOT gross profit); `q_ocf_to_or`÷opincome.
- **M2** (validate, don't assert): ran a **value-parity audit** vs the vendor bins
  ([_phaseb_qstar_parity_audit.py](../../scripts/_phaseb_qstar_parity_audit.py)) — a mapping is a
  "replacement" ONLY if it passes parity; else it's a local factor / deferred.
- **M3** (Part C flow-state, not snapshot expansion) + **m1/m2/m3** — folded below.

---

## Part A — derivable factors, EMPIRICALLY VALIDATED vs the vendor field (≈150 stocks, 2014-24)

`MATCH` = med rel-err ~0 + >0.94 within-1% vs the vendor q_* (by carried report value). PIT-correct
**by construction**: `_sq` anchors on `effective_date` (§3.2); every `$field` wrapped in `Ref(...,1)`.
Enter as `draft`. Denominator 0/NaN → **NaN, never 0** (m3); financial/net-cash firms → sub-universe
(Layer-2 mask, never inside the Layer-1 expr).

| proposed factor | vendor q_* (official def) | local expr (over existing `_sq`) | parity |
|---|---|---|---|
| `earn_sales_yoy_q` | q_sales_yoy 营业收入同比单季 | `(revenue_sq_q0−revenue_sq_q4)/Abs(revenue_sq_q4)` | ✅ 94% |
| `grow_totrev_yoy_q` | q_gr_yoy 营业总收入同比单季 | `(total_revenue_sq_q0−total_revenue_sq_q4)/Abs(...)` | ✅ 94% |
| `earn_np_yoy_q` | q_profit_yoy 净利润同比单季 | `(n_income_sq_q0−n_income_sq_q4)/Abs(n_income_sq_q4)` | ✅ 94% |
| `earn_npattr_yoy_q` | q_netprofit_yoy 归母净利润同比单季 | `(n_income_attr_p_sq_q0−sq_q4)/Abs(sq_q4)` | ✅ 94% |
| `qual_gross_margin_q` | q_gsprofit_margin 销售毛利率单季 | `(revenue_sq_q0−oper_cost_sq_q0)/revenue_sq_q0` | ✅ 99% |
| `qual_net_margin_q` | q_netprofit_margin 销售净利率单季 | `n_income_sq_q0/revenue_sq_q0` | ✅ 99% |
| `qual_op_to_gr_q` | q_op_to_gr 营业利润/营业总收入单季 | `operate_profit_sq_q0/total_revenue_sq_q0` | ✅ 99% |
| `qual_np_to_gr_q` | q_profit_to_gr 净利润/营业总收入单季 | `n_income_sq_q0/total_revenue_sq_q0` | ✅ 99% |
| `qual_finaexp_to_gr_q` | q_finaexp_to_gr 财务费用/营业总收入单季 | `fin_exp_sq_q0/total_revenue_sq_q0` | ✅ 99% |
| `earn_opincome_q` | q_opincome 经营活动净收益单季 | `total_revenue_sq_q0 − total_cogs_sq_q0` | ✅ 97% |
| `qual_opincome_to_ebt_q` | q_opincome_to_ebt 经营活动净收益/利润总额单季 | `(total_revenue_sq_q0−total_cogs_sq_q0)/total_profit_sq_q0` | ✅ 96% |
| `qual_ocf_to_opincome_q` | q_ocf_to_or 经营现金流/经营活动净收益单季 | `n_cashflow_act_sq_q0/(total_revenue_sq_q0−total_cogs_sq_q0)` | ✅ 96% |
| `qual_salescash_to_or_q` | q_salescash_to_or 销售收现/营业收入单季 | `c_fr_sale_sg_sq_q0/revenue_sq_q0` | ✅ 99% |
| `earn_eps_q` | q_eps 每股收益单季 | `n_income_attr_p_sq_q0/total_share` | ✅ 97% (med 3e-4; period-end ≈ weighted shares) |
| `earn_sales_qoq_q`/`grow_totrev_qoq_q`/`earn_np_qoq_q`/`earn_npattr_qoq_q` | q_sales_qoq/q_gr_qoq/q_profit_qoq/q_netprofit_qoq | same as `_yoy` but vs `_sq_q1` | ⏳ same structure as the ✅ YoY — re-confirm in the build audit |

**Flagged by the audit (do NOT define as vendor-equivalent until resolved):**
- `q_adminexp_to_gr` — `admin_exp_sq/total_revenue` MISMATCH (med 10.6%, sign 0.999). Cause: 研发费用
  split from 管理费用 post-2018 (新准则). **Test** `(admin_exp_sq + rd_exp_sq)/total_revenue` in the build
  audit; if it MATCHES, define that; else define `admin_exp/total_revenue` as a *local* factor, not a q_* replacement.
- `q_exp_to_sales` (销售期间费用率) — not yet audited; test `(sell+admin+fin)_sq/revenue` AND `/total_revenue`.
- `q_investincome` / `q_investincome_to_ebt` — 价值变动净收益 ≠ `invest_income` (audit: 59% within-1%,
  as predicted). 价值变动净收益 = 公允价值变动净收益 + 投资净收益 + 汇兑净收益 — a composite whose components
  may not be materialized. **DEFER** unless the composite is reconstructable + passes parity.

**Implementation checklist (m2 — machine-readable cohort markers):** every Phase-B factor carries
`family_id="phase_b_single_quarter_fina_indicator"`, `source_class="derived_from_existing_sq"`,
`replacement_for_vendor_q=<field|null>`, `parity_status` + `redundancy_note`. They are a CORRELATED
family — NOT independent discoveries; downstream selection by marginal orthogonal contribution
(memory `reference_factor_selection_marginal_not_icir`). Catalog-duplicate audit first
(`catalog_composition()`); some already exist (`earn_sales_yoy_q` ≈ validated `SalesQGr%PY`,
`qual_gross_margin_q` ≈ rung-4 `GrossProfit%...`) — skip duplicates (registry parity test forbids dup ids).

---

## Part B — `q_impair_to_gr_ttm` — DEFER
`assets_impair_loss` is in the income ledger but `$assets_impair_loss_sq` isn't materialized; sparse
post-2019 (新准则 → 信用减值损失). One sparse field is not worth a full income rebuild. Revisit if an
income rebuild happens for another reason.

---

## Part C — `q_dtprofit` (扣非净利润单季): DESIGN FOR ACCURACY + PIT

**Goal.** PIT-correct single-quarter 扣非净利润 (扣除非经常性损益后的归母净利润), replacing the
PIT-uncertain vendor `q_dtprofit` (official def: 扣除非经常损益后的单季度净利润).

**Source (verified cumulative).** `profit_dedt` (扣非净利润, YTD) in the indicators ledger — 600519 2022:
17.24B → 29.76B → 44.39B → 62.79B. `extra_item` (非经常性损益) also cumulative there.

**Derivation.** single-q = `profit_dedt[Q] − profit_dedt[Q−1]` (Q1 = `profit_dedt[Q1]`) via the
visible-state `derive_single_quarter_value` logic.

**M3 — implementation REQUIREMENT (flow-state, NOT snapshot expansion).** `_materialize_profit_dedt_sq`
must read the indicators PIT ledger, subset to `qlib_code/effective_date/end_date/profit_dedt`, build
**visibility segments by effective_date**, and derive q0..q4 with the same visible-state logic as
`arrays_from_flow_segments` / `derive_single_quarter_value`. It MUST NOT call
`arrays_from_snapshot_segments` for `profit_dedt` (a cumulative YTD flow living in a snapshot-configured
dataset). Custom materializer (Option A); reject Option B (turning indicators into a flow family — too invasive).

**PIT (by construction):** `profit_dedt` anchors on indicators `ann_date → effective_date` (§3.2, same
as approved `q_roe`); cumulative→single-q respects restatement (`derive_single_quarter_value` retroactively
updates at the restatement effective_date); `Ref(...,1)` for predictive use; served NaN where not yet
PIT-computable is meaningful.

**Accuracy validation (VALUE, not timing):**
- **PRIMARY oracle = 果仁** (trusted): if a 果仁 book shows 扣非净利润单季 / `EpsExclXorQ`, holding-level parity.
- **SECONDARY = vendor `q_dtprofit` VALUE — DIAGNOSTIC ONLY (m1):** intended to be the same quantity, but
  NOT authoritative (a vendor can be timing-correct yet formula-/definition-different). Any material
  mismatch is triaged against 果仁 + the cross-check, never waived.
- **CROSS-CHECK = `$profit_dedt_sq` vs `n_income_attr_p_sq − (single-q of extra_item)`** — the two
  independent derivations must agree.
- `q_dtprofit_to_profit` denom = **净利润** (n_income), per the doc — NOT 利润总额.

**Required canaries before publish/register (GPT m + Q5):**
1. Normal: `Q3_sq = Q3_cum − Q2_cum` only after both visible.
2. Late Q2 restatement after Q3: day before the restatement effective_date `Q3_sq` uses OLD Q2; ON it, NEW Q2.
3. Missing prior quarter: `Q2/Q3/Q4_sq = NaN`, not the current cumulative.
4. `Q1_sq = Q1 cumulative`.
5. Irregular `end_date` → NaN.
6. Slot-order: q0..q4 = latest VISIBLE fiscal periods, not latest calendar rows.
7. Provider-read exact-date audit (read `$profit_dedt_sq_q0..q4` through Qlib; exact served values, no dropna/ffill).

**Governance:** new materializer = substantial → GPT cross-review (like forecast R1→R4); build + publish
+ register `$profit_dedt_sq` + `qual_dtprofit_to_profit_q`.

### Self-review addendum (2026-06-24, BEFORE building — _phasec_profit_dedt_selfreview.py)
The make-or-break risk for Part C was the **D&A trap**: if `profit_dedt` were reported only semi-annually
(H1+FY, like the cashflow 折旧摊销), the single-quarter derivation would collapse to NaN. **REFUTED by the
data:** `profit_dedt` is reported at ALL four fiscal quarters — non-null coverage **Q1 94.0% / H1 96.1% /
Q3 94.5% / FY 98.2%** (indicators ledger). So `profit_dedt[Q] − profit_dedt[Q−1]` is genuinely derivable.
Two caveats folded into this plan:
1. **Coverage gap vs the vendor (the PIT-correctness cost).** The vendor `q_dtprofit` is served at 99.7%
   (Tushare reports the single-quarter DIRECTLY). Our PIT-correct derivation needs TWO consecutive
   cumulative values (~90-95% at the report level; lower on the early-data/delisted tail), so
   `$profit_dedt_sq` will have a modest coverage gap. It is a sub-universe factor (acceptable for draft).
   ADD a **coverage-vs-vendor canary** + document the gap in the approval evidence.
2. **Implementation: reuse the flow machinery, do NOT hand-roll.** `$profit_dedt_sq` needs q0..q4 SLOTS
   (the forecast materializer wrote a single value). The materializer must drive the income/cashflow flow
   path (`materialize_canonical_quarter_segments` + `derive_single_quarter_value` /
   `arrays_from_flow_segments`) over the indicators ledger's `profit_dedt`, NOT re-implement cumulative→
   single-q. This is exactly GPT M3 (flow-state, not snapshot expansion).
The vendor `q_dtprofit` at 99.7% also confirms `profit_dedt` is the 归母 扣非 quantity (value-validation +
the `n_income_attr_p_sq − extra_item_sq` cross-check will confirm the exact definition).

**COST/VALUE flag (honest):** Part C is ONE factor (`qual_dtprofit_to_profit_q`, sub-universe), at the cost
of a full materializer + build + publish + its own GPT review. The 14 Part-A factors already shipped. Worth
building only if 扣非单季 is specifically wanted.

---

## Sequencing & residual risks
1. **Part A** — catalog-duplicate audit → define the ✅ MATCH factors (+ the qoq re-confirm + the
   q_adminexp `+rd_exp` test) → `sync_catalog` (draft). No build. Flagged/approx ones stay deferred or
   are renamed local-only.
2. **Part C** — custom flow-state materializer → canaries → build/publish/register → factor.
3. **Part B / q_investincome family** — deferred.

**Residual risks:** (a) the vendor q_* as a *value* oracle is a diagnostic, not proof — 果仁 + cross-check
triage required; (b) 23-factor correlated family ≠ independent signals (cohort markers + marginal
selection); (c) the snapshot-vs-flow hazard for `profit_dedt` (M3 mitigates via explicit flow-state).
