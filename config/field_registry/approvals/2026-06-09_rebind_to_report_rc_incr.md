# Approval re-bind — provider_build_id prod_full_20260421_namespace_v1 → report_rc_incr_20260608

**Date:** 2026-06-09. **Not a status change** — a provider-build re-bind only.

## What happened
The `report_rc` analyst-forecast dataset was added to the live Qlib provider via an
**incremental** build (`build_qlib_backend --mode update --datasets report_rc --stage full`,
build_id `report_rc_incr_20260608`), published 2026-06-09 (atomic swap; old provider backed
up at `data/qlib_data.bak_report_rc_incr_20260608`). The publish emitted a new
`provider_build.json` with `provider_build_id: report_rc_incr_20260608` (calendar policy
unchanged: `frozen_20260227_system_build`).

Per the `approval_evidence_binding` contract (`src/data_infra/approval_evidence.py`), every
approval YAML bound to the prior `provider_build_id` drifts on a provider rebuild and must be
refreshed **after re-verifying the on-disk evidence under the new build**.

## Re-verification (why the re-bind is sound, not a rubber-stamp)
The incremental build COPIED the prior provider (`shutil.copytree`) and materialized ONLY
`report_rc` on top; no other dataset was re-materialized. Verified before re-binding:
- **Kline byte-identical** — `close.day.bin` sha matches old build for 600519_sh / 000001_sz /
  300750_sz.
- **Other approved datasets byte-identical** — `net_mf_amount`, `roa`, `revenue`, `pe_ttm`,
  `up_limit`, `total_mv` `.day.bin` sha match old build for the sampled stocks.
- Same 5,755-stock universe; staged dirs = live + exactly the 4 `report_rc__*` bins per
  covered stock.

So every re-bound dataset's evidence (coverage / parity / value-sanity recorded in its YAML)
holds UNCHANGED under `report_rc_incr_20260608`. The re-bind updates the binding id only.

## Re-bound YAMLs (10)
indicators_unlisted, indicators_loader_qfields, statements_unknown, wave2_indicator_ratios,
stk_limit, alpha_endpoints_batch, margin_detail_partial, moneyflow, hk_hold,
income_rd_exp_sq_q0 — all `provider_build_id` → `report_rc_incr_20260608`.

Verification: `evaluate_approval_evidence_bindings()` → 10 scanned, **0 drift**.

## Note
`report_rc` itself remains **QUARANTINE** (this re-bind does not promote it). Its
quarantine→approved promotion is a separate, later step gated on the breadth restatement
canary + a parity/coverage review (see `workspace/research/data_expansion/REPORT_RC_REGISTRATION_ROADMAP.md`).
