# Re-bind to the share-capital re-anchor patch (depth9_20260630_sharecap_reanchor_20260701)

The 2026-07-01 share-capital anchoring correction REWROTE the values of three approved daily_basic
fields in the live provider IN PLACE — the bare `$total_share` bin had been the balancesheet snapshot
family's compat alias (REPORT-anchored, 1-2 months late vs real share changes, internally inconsistent
with `$total_mv`), and was re-materialized from the raw `data/market/daily` columns (EFFECTIVE-DATE
anchor; `$total_share` ×1e4 → 股, `$float_share`/`$free_share` verbatim 万股; ffill across suspensions).
Fixer: `scripts/fix_share_capital_bins.py` (dry-run → live); pre-fix bins backed up under
`data/backups/share_capital_bins_20260701_221439/` (17,244 files).

**Because this rewrites APPROVED field history (unlike the additive quality_stability / report_rc
in-place publishes), the provider identity was rotated** (GPT cross-review REWORK finding M1):
`provider_build_id: depth9_20260630 → depth9_20260630_sharecap_reanchor_20260701`. Schema v1 forbids
extra manifest keys, so the patch lineage (base build id, patch type/fields/script/backup, audit
numbers) lives in the append-only sidecar `data/qlib_data/metadata/provider_patches.jsonl` next to the
manifest, plus this note.

**Re-bound (24 YAMLs, `provider_build_id → depth9_20260630_sharecap_reanchor_20260701`;
`calendar_policy_id` unchanged = `frozen_20260227_system_build`).** Justification: the patch touched
ONLY the three bare share-capital bins — every field named by these approvals is byte-untouched
(`fix_share_capital_bins.py` writes exactly `{total_share,float_share,free_share}.day.bin`; audit:
5,748 symbols × 3 bins, `$total_share×$close` vs `$total_mv` >1%-off days 9.23% → 0.0003%). None of the
24 approvals registers any of the three corrected fields ($total_share/$float_share/$free_share were
approved in the ORIGINAL daily_basic block of field_status.yaml, which predates the binding contract),
so the approvals carry over unchanged and only the binding pin needed refreshing.

**Evidence-staleness consequence (GPT finding B1) — RESOLVED same day by `data_correction_replay`:**
the approved factor `qual_piotroski_fscore_9pt` consumes `Ref($total_share,1)`/`Ref($total_share,251)`
(anti-dilution term), so its prior approval evidence was not bit-reproducible against the corrected
provider. The exact frozen design was replayed on the corrected provider via the promotion driver's
deterministic dryrun reproduction (`promote_sealed_oos_winners.py --mode dryrun`: frozen-13 set
`5a8d601a…`, definition binding bound, temp seal / NO real seal spend / NO registry writes — replacing
invalidated evidence, NOT a fresh OOS attempt): **PASS — rank_icir 0.2156 (orig 0.2089), ls_sharpe(5d)
1.6342 (orig 1.2029), clears the original bar with IMPROVED metrics; no downgrade.** Control: the 5
non-consuming winners reproduce their original evidence EXACTLY (4-dp), isolating the delta to the
share-capital correction. Artifact:
[sharecap_correction_replay_20260701.json](../../../workspace/research/factor_expansion/sharecap_correction_replay_20260701.json).

Rebind driver: [_rebind_approvals_sharecap.py](../../../workspace/scripts/_rebind_approvals_sharecap.py).
Administrative log entry: `field_approval_log.jsonl` event `approved_field_value_correction` (2026-07-01).
