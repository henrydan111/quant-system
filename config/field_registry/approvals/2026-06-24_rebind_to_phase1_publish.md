# Approval re-bind — provider_build_id 20260623_004545 → phase1_qfields_holdertrade_v2_20260624

**Date:** 2026-06-24. Provider-build re-bind (plus the NEW `stk_holdertrade` 高管 approval, recorded
in `2026-06-24_stk_holdertrade_mgr_directional_to_approved.yaml`).

## What happened
Materialization-expansion Phase-1 rebuilt + published the provider (`build_qlib_backend --mode update
--datasets indicators,stk_holdertrade --stage provider-only`, build_id
`phase1_qfields_holdertrade_v2_20260624`) by atomic swap (`StagedQlibBackendBuilder.publish`; old
provider backed up at `data/qlib_data.bak_phase1_qfields_holdertrade_v2_20260624`). The new
`provider_build.json` carries `provider_build_id: phase1_qfields_holdertrade_v2_20260624` (calendar
policy unchanged: `frozen_20260227_system_build`).

The build added: the 8 `holdertrade_mgr_*` 高管 directional fields (NEW, registered approved) and the
25 vendor `q_*` indicator bins (materialized but **deliberately NOT registered** — see below).

## Re-verification (why the re-bind is sound)
The rebuild only RE-MATERIALIZED `indicators` (existing fields reproduced identically; q_* added) and
`stk_holdertrade` (existing net/gross/events identical; 高管 fields added). Every OTHER dataset was
COPIED unchanged. Verified BEFORE re-binding (`_register_phase1_holdertrade.py`): a sample across the
re-bound datasets is **byte-identical new-live vs `.bak`** — `close`, `n_income_sq_q0`,
`total_assets_q0`, `forecast__np_q_yoy`, `net_mf_amount`, `report_rc__n_active_analysts` (copied) +
`q_roe`, `arturn_days` (re-materialized) — for 000001_sz / 600519_sh. So every re-bound dataset's
evidence holds UNCHANGED under the new build. The re-bind updates the binding id only.

Verification: `evaluate_approval_evidence_bindings()` → **21 scanned, 0 drift** (the 20 re-bound +
the new `stk_holdertrade` 高管 approval).

## ⚠ The 25 vendor `q_*` were NOT registered (deliberate)
field_status.yaml (indicators block, 2026-06-09) records the 25 `q_*` single-quarter fields as
**INTENTIONALLY NOT added** — "we self-compute PIT-correct pit_*/_sq equivalents; the vendor q_* are
not guaranteed PIT-safe." The Phase-1 rebuild materialized their bins (the materializer has no
allowlist) but they remain **unregistered = inert**: formal runs fail-closed on them, the PIT loader
refuses them, sandbox only warns. The non-redundant q_* are being re-expressed as our own PIT-correct
`_sq` derivations separately (Phase B), NOT by registering the vendor fields.

## Re-bound YAMLs (20)
indicators_unlisted, indicators_loader_qfields, statements_unknown, wave2_indicator_ratios, stk_limit,
alpha_endpoints_batch, margin_detail_partial, moneyflow, hk_hold, income_rd_exp_sq_q0,
indicators_level_indicators, report_rc, balancesheet_d4a_equity_payables, balancesheet_d4a_q1_slots,
balancesheet_d4a_q1_slots_batch2, cashflow_n_cashflow_act_sq_q4, income_n_income_sq_q4, limit_status,
north_hold_vol, forecast — all `provider_build_id` → `"phase1_qfields_holdertrade_v2_20260624"`.
