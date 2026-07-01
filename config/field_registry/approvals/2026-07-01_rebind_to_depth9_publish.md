# Re-bind to the depth-9 slot-depth publish (depth9_20260630)

After publishing the depth-9 provider (`SLOT_DEPTH_DEFAULT` 5→9 — single-quarter `_sq_q*` and level `_q*`
slots materialized to q0..q8; full `mode=all stage=provider-only` re-materialization; safe-ordered
staged→live swap), the live `provider_build_id` became `depth9_20260630`, so the 24 prior approval YAMLs
(bound to `phasec_profit_dedt_sq_20260624`) drifted.

**Re-bound (24 YAMLs, `provider_build_id → depth9_20260630`; `calendar_policy_id` unchanged =
`frozen_20260227_system_build`) after the m1 byte-audit proved the re-materialization is ADDITIVE-ONLY** —
every approved field lives in q0..q4, and q0..q4 is byte-identical old-live vs new-live:

- size-checked ALL 18,719,845 q0..q4 bins across all 5,755 symbols → 0 size-mismatch / 0 missing / 0
  unexpected-new (every staged-only file is a q5..q8 slot);
- full-SHA1-hashed a deterministic 1-in-50 sample (116 symbols, 374,045 q0..q4 bins) → 0 mismatch;
- corroborated by byte-identical calendar (4410 days, diff empty), a 3-symbol smoke that proved q0..q4
  value-identical, the deterministic P0-4 rebuild, and `provider-only` = no upstream re-ingest (same normalized
  inputs). Independent Codex pre-publish review judged this sufficient (SHIP).

Only q5..q8 are new (additive); NOTHING in q0..q4 was re-materialized differently. `evaluate_approval_evidence_bindings()`
→ 0 drift after the rebind (daily-QA `approval_evidence_binding` PASS). The prior depth-5 provider is retained
as `data/qlib_data.bak_depth9_20260630` (one atomic rename from restore).

Evidence: [PROVIDER_DEPTH9_UPGRADE_PLAN.md](../../../workspace/research/idea_sourcing/guorn/PROVIDER_DEPTH9_UPGRADE_PLAN.md),
`logs/depth9_audit_fast.log`, `logs/depth9_postpublish_qa.log`, `data/qlib_data/metadata/provider_build.json`.
Rebind driver: [_rebind_approvals_depth9.py](../../../workspace/scripts/_rebind_approvals_depth9.py).
