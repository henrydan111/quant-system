# Wave-1 Statement-Field Promotion Plan

> ✅ **EXECUTED 2026-05-31** (branch `wave1-field-promotion`). 53 statement
> line-item variants promoted `unknown_field → approved` across income (24) /
> balancesheet (17) / cashflow (12). Evidence: live coverage audit (all ≥50%
> non-null; `ebitda`/`fin_exp_int_exp`/`rd_exp` EXCLUDED for sparse coverage)
> + independent-recompute provider parity (15,351 cells, 0 mismatch via
> [verify_statement_provider_parity.py](../../scripts/verify_statement_provider_parity.py)).
> Registry: [field_status.yaml](../../../config/field_registry/field_status.yaml)
> + [approval YAML](../../../config/field_registry/approvals/2026-05-31_statements_unknown_to_approved.yaml)
> + JSONL log + guardrail tests
> ([test_field_registry.py](../../../tests/data_infra/test_field_registry.py)
> `test_statement_fields_approved_for_formal` / `test_excluded_statement_fields_not_approved`).
> **Outcome: merged-candidate formal-eligible 21 → 47.** Approval-evidence drift
> check + 86 registry tests + 52 field-gate tests all pass.

**Status:** plan only — NOT executed. Promotion requires running the parity harness +
anomaly review below and is gated on GPT's Round-4 go and owner approval.
**Goal:** move the income / balancesheet / cashflow line-item fields the formal-eligible
factor candidates depend on from `unknown_field` → `approved`, so the accruals / cash-
quality / gross-profitability / EV-value / Piotroski cluster can enter formal screening.

This plan follows the governance contract in
[config/field_registry/approvals/README.md](../../../config/field_registry/approvals/README.md)
and the CLAUDE.md §3 PIT invariants. It does **not** change any on-disk data — the fields
are already materialized (verified in [field_inventory.md](../../../data/factor_research/field_inventory.md));
this is a registry-coverage + parity-verification step only.

---

## 1. Why these fields, in this order

GPT 5.5 Pro's Round-2 promotion ranking (recorded in the proposal §7) — Wave-1 unlocks the
most independent factor definitions per single governance review because every field is a
shared denominator/numerator across many candidates:

| # | Field stem | PIT variants needed | Unlocks (merged-CSV factors) |
|---|---|---|---|
| 1 | `total_assets` | `_q0`, `_q4` | every accruals/ROA/asset-growth/NOA/gross-prof denominator |
| 2 | `n_cashflow_act` | `_sq_q0..q3` | cash-ROA, total accruals, FCF/EV, CFO/NI, Piotroski |
| 3 | `n_income_attr_p` | `_sq_q0..q4` | accruals, Piotroski, growth YoY/accel |
| 4 | `total_revenue` | `_sq_q0..q4` | gross profitability, growth, R&D intensity |
| 5 | `oper_cost` | `_sq_q0..q3` | gross profitability |
| 6 | `total_liab` | `_q0`, `_q4` | EV bridge, NOA, NCAV, Piotroski leverage |
| 7 | `money_cap` | `_q0` | EV bridge, net-debt, NOA |
| 8 | `c_pay_acq_const_fiolta` | `_sq_q0..q3` | FCF/EV, capex intensity |
| 9 | `accounts_receiv` | `_q0`, `_q4` | receivables-vs-sales mismatch |
| 10 | `inventories` | `_q0`, `_q4` | inventory-vs-sales mismatch |
| 11 | `total_cur_assets` | `_q0`, `_q4` | NCAV, Piotroski current ratio |
| 12 | `total_cur_liab` | `_q0`, `_q4` | Piotroski current ratio |

Plus the EV/leverage closure (GPT Wave-2 head, cheap to bundle): `ebit` (`_sq_q0..q3`),
`st_borr`/`lt_borr` (`_q0`).

> ⚠️ **Removed from the Wave-1 bundle by factor audit (F5, 2026-05-30; GPT Round-5):**
> - `ebitda` — 3.3% non-null in the live materialized provider. Do not promote
>   until rematerialized or rebuilt from statement components. Use `ebit`-based
>   yields (`val_ebit_ev_ttm` already in the candidate set) as the EV-value path.
> - `fin_exp_int_exp` — **0% non-null** in the live materialized provider (bin
>   file exists but contains no data). Do not promote. Replace the interest-
>   coverage factor slot with `int_exp` from the income statement only after
>   running a coverage audit on it. The proposal's `lev_interest_coverage_ttm`
>   and `lev_net_debt_to_ebitda_ttm` candidates have been DROPPED for this reason.

The exact variant set to register is **the union of `$field` tokens** across the merged-CSV
rows that resolve to `unknown_field` — derive it mechanically (see §4 step 1), do not
hand-list, so the registry covers exactly what the candidates consume.

---

## 2. The PIT contract these fields inherit (CRITICAL — differs from indicators)

Per CLAUDE.md §3: the **5 statement families** (`income`, `income_quarterly`,
`balancesheet`, `cashflow`, `cashflow_quarterly`) anchor visibility on
**`max(ann_date, f_ann_date)`** — NOT `ann_date`-only like the `indicators` family. The
approval YAML's `pit_contract` block must therefore record:

```yaml
pit_contract:
  availability_column: "max(ann_date, f_ann_date)"
  provider_transform: pit_aligned_by_disclosure_date_with_shift1
  provider_transform_owner: src/data_infra/pit_backend.py  # _materialize_*_dataset
  expression_lag_required: true
  approved_usage_pattern: "Ref($field, 1) or stricter"
  same_day_raw_usage_allowed: false
```

The `_sq` / `_cum` / `_q0..q4` variants are produced by the staged PIT backend's
quarter-canonical serving (data_tracker §9). The cumulative→quarterly late-restatement
behavior (CLAUDE.md §3) applies: a `_sq` value can retroactively change at a restatement's
effective date — intentional (best-known state), but the parity harness must test it.

---

## 3. Required evidence (fail-closed gates)

A statement-family promotion to `approved` must satisfy ALL of:

1. **Live-provider parity.** Extend the parity grid in
   [tests/data_infra/test_pit_loader_provider_parity.py](../../../tests/data_infra/test_pit_loader_provider_parity.py)
   to include each promoted field (lag-0 as-of AND lag-1 signal), across the existing
   security grid + at least one delisted/IPO-edge name. Loader kernel value must equal the
   live provider `D.features($field)` (rtol=1e-4, atol=1e-3).
2. **Anomaly review.** Null-rate, sign sanity, and unit sanity per field over 2014→2026.
   Statement line-items are raw 元 — document the basis next to any factor that ratios them
   against a 万元/千元 market field (cf. the moneyflow/margin unit bugs Round 3 caught).
3. **Restatement canary.** At least one known cumulative→quarterly late-restatement fixture
   showing the `_sq` derivation updates at the restatement effective date, not before.
4. **Provider-build binding.** `provider_build_id: prod_full_20260421_namespace_v1` +
   `calendar_policy_id: frozen_20260227_system_build` (current live build) — required by the
   approval-evidence drift check (CLAUDE.md PR 10/10a/10b/10c).
5. **NEW — Live coverage gate (F5; GPT Round-5).** Sample the live materialized provider
   over a representative window (e.g. 2018 full market) and confirm non-null coverage above
   threshold per the GPT Round-5 two-tier rule:
   * **Hard-block** if coverage < 10% (clearly empty — like `fin_exp_int_exp` at 0%).
   * **Hard-block formal use** if coverage < 50% unless the field is explicitly marked
     `sparse_allowed` in the registry (e.g. R&D, forecasts — segment-specific by nature).
   * **Warn** in 10–50%.
   This step catches the F5 class (bin file present but data sparse/empty). Without it,
   `fin_exp_int_exp` would have entered Wave-2 and silently produced all-NaN factors.

---

## 4. Execution steps (when approved)

1. **Derive the exact field set.** From `factor_candidates_merged.csv`, collect every
   `$field` token in rows with `registry_status=unknown_field` whose stem is in the Wave-1
   list. This is the authoritative variant list (already validated to exist in the 3,649-bin
   inventory by `validate_factor_candidates.py`).
2. **Run parity + anomaly harness** (steps §3.1–§3.3). Capture results.
3. **Add a `statement_line_items` dataset entry** (or per-family `income`/`balancesheet`/
   `cashflow` entries — prefer per-family so the `max(ann_date,f_ann_date)` contract and the
   reason string are precise) to
   [config/field_registry/field_status.yaml](../../../config/field_registry/field_status.yaml)
   with `status: approved` and an explicit `fields:` list (NOT prefixes — fail-closed on any
   new unreviewed variant, matching the `indicators` precedent).
4. **Write the approval YAML(s)** under `config/field_registry/approvals/` named
   `2026-MM-DD_{family}_unknown_to_approved.yaml`, carrying the `pit_contract` from §2, the
   §3 evidence, and the provider-build binding.
5. **Append the JSONL log line(s)** to `field_approval_log.jsonl` (`event: promotion`,
   `fields_added`, `evidence_file`, `pr`).
6. **Add per-family guardrail tests** in
   [tests/data_infra/test_field_registry.py](../../../tests/data_infra/test_field_registry.py)
   (one `test_<family>_bare_fields_approved_for_formal`) mirroring the indicators precedent,
   and extend the PR-9a formal-factor compatibility test so the newly-formal candidates are
   asserted eligible (and leave `KNOWN_NON_FORMAL_FACTORS`).
7. **Re-run** `scripts/run_daily_qa.py` (approval-evidence binding check + parity must pass)
   and `validate_factor_candidates.py` (the Wave-1 rows should flip `unknown_field`→`approved`).

---

## 5. Expected outcome

After Wave-1, the merged-CSV formal-eligible count rises from 21 to roughly the mid-40s (all
accruals/cash-quality/gross-profitability/growth-`_sq` rows that touch only Wave-1 fields).
EV-value and net-debt/interest-coverage rows flip only if the `ebit`/`ebitda`/`borr`/
`fin_exp_int_exp` bundle is included. Quarantine (moneyflow/margin/northbound) and
pending_review (alpha endpoints) rows remain blocked — their own anomaly reviews are separate
and out of Wave-1 scope.

**Then, and only then**, run the formal screening (IC/RankIC/ICIR/quantile/decay/turnover via
[src/result_analysis/](../../../src/result_analysis/)) on the now-formal-eligible set —
through the sanctioned `compute_factors()` → `qlib_windowed_features` path, never a hand-rolled
loader.

---

## 6. Out of scope for Wave-1

- Moneyflow / margin / northbound (`quarantine`) — separate anomaly review.
- Alpha endpoints (`pending_review`) — separate anomaly review.
- Wave-3 derived fields (`fcff`, `fcfe`, `netdebt`, `working_capital`, `retained_earnings`).
- Any catalog wiring or strategy promotion — that is downstream of screening and gated by the
  promotion gate (CLAUDE.md §3).
