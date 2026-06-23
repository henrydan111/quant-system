# Approval re-bind — provider_build_id indicators_fields_20260609 → 20260623_004545

**Date:** 2026-06-23. **Not a status change** — a provider-build re-bind only (plus the
NEW `forecast` approval, recorded separately in
`2026-06-23_forecast_np_q_yoy_to_approved.yaml`).

## What happened
The `forecast` derived field `$forecast__np_q_yoy` (业绩预告 single-quarter net-profit YoY;
rung-3) was added to the live Qlib provider via an **incremental** staged build
(`build_qlib_backend --mode update --datasets forecast --fields forecast__np_q_yoy
--stage provider-only`, build_id `20260623_004545`), published 2026-06-23 by atomic swap
(`StagedQlibBackendBuilder.publish`; old provider backed up at
`data/qlib_data.bak_20260623_004545`). The publish emitted a new `provider_build.json`
with `provider_build_id: 20260623_004545` (calendar policy unchanged:
`frozen_20260227_system_build`).

Per the `approval_evidence_binding` contract (`src/data_infra/approval_evidence.py`), every
approval YAML bound to the prior `provider_build_id` (`indicators_fields_20260609`) drifts on
a provider rebuild and must be refreshed **after re-verifying the on-disk evidence under the
new build**.

## Re-verification (why the re-bind is sound, not a rubber-stamp)
The incremental build COPIED the prior provider and materialized ONLY `forecast__np_q_yoy`
on top; no other dataset was re-materialized. Verified BEFORE publishing:
- **Kline + every approved field byte-identical** — `close`, `total_mv`, `n_income_sq_q0`,
  `net_mf_amount` `.day.bin` sha match the prior live provider for 000001_sz / 600519_sh /
  300750_sz. Only `forecast__np_q_yoy` is new (present in staged, absent in the prior live).

So every re-bound dataset's evidence (coverage / parity / value-sanity recorded in its YAML)
holds UNCHANGED under `20260623_004545`. The re-bind updates the binding id only.

## Re-bound YAMLs (19)
indicators_unlisted, indicators_loader_qfields, statements_unknown, wave2_indicator_ratios,
stk_limit, alpha_endpoints_batch, margin_detail_partial, moneyflow, hk_hold,
income_rd_exp_sq_q0, indicators_level_indicators, report_rc, balancesheet_d4a_equity_payables,
balancesheet_d4a_q1_slots, balancesheet_d4a_q1_slots_batch2, cashflow_n_cashflow_act_sq_q4,
income_n_income_sq_q4, limit_status, north_hold_vol — all `provider_build_id` →
`"20260623_004545"` (quoted: the all-digit build id parses as an int unquoted).

Verification: `evaluate_approval_evidence_bindings()` → **20 scanned, 0 drift** (the 19
re-bound + the new `forecast` approval).
