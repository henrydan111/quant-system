# GPT re-review #2 prompt — share-capital re-anchor REWORK fold (clearing pass)

Copy the block below to GPT-5.5 Pro. Branch pushed: `trading-agents-design` @ `be3bb9c` (rework commit; R1 reviewed `b6c6d1b`).

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. This is re-review #2 (clearing pass) of the share-capital bin re-anchor you reviewed in round 1 (verdict REWORK: "the data fix is good; the publication/governance handling is not"). Verify that every round-1 finding is genuinely closed; surface anything new; do not rubber-stamp.

REPO (public — fetch any file to verify against the live code)
https://github.com/henrydan111/quant-system   (branch: trading-agents-design, pinned commit be3bb9c)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/<path>

CONTEXT
- CLAUDE.md: https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/CLAUDE.md
- src/data_infra/pit_backend.py (M2 fold): https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/src/data_infra/pit_backend.py
- tests/data_infra/test_share_capital_daily.py (M2 regression): https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/tests/data_infra/test_share_capital_daily.py
- config/field_registry/approvals/2026-07-01_sharecap_reanchor_rebind.md (M1+M3+B1 record): https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/config/field_registry/approvals/2026-07-01_sharecap_reanchor_rebind.md
- config/field_registry/field_approval_log.jsonl (M3 entry, last line): https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/config/field_registry/field_approval_log.jsonl
- workspace/research/factor_expansion/sharecap_correction_replay_20260701.json (B1 replay artifact): https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/workspace/research/factor_expansion/sharecap_correction_replay_20260701.json
- workspace/scripts/promote_sealed_oos_winners.py (the replay driver — pre-existing, unchanged): https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/workspace/scripts/promote_sealed_oos_winners.py
- workspace/scripts/_rebind_approvals_sharecap.py (M1 rebind driver): https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/workspace/scripts/_rebind_approvals_sharecap.py
- schemas/provider_build.schema.json (why the manifest could NOT carry inline patch keys): https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/schemas/provider_build.schema.json

SELF-REVIEW PREFLIGHT: verdict = clean for GPT. All 4 round-1 findings accepted, none declined. One deviation from your suggested M1 text, with reason (see FOLD M1). Residual concerns: none beyond the two backlog items you yourself marked as future work (m1 revision-drift canary, m6 scoped-load projection).

ROUND-1 FINDINGS → FOLDS (authoritative summary; links above cross-check)

FOLD B1 (Blocker — approved qual_piotroski_fscore_9pt consumes $total_share; evidence stale):
1. Claim corrected everywhere (project_state 2026-07-01d; the approvals note; the approval-log
   entry): qual_piotroski_fscore_9pt's anti-dilution term
   `If(Ref($total_share, 1) <= Ref($total_share, 251), 1, 0)` directly consumes the corrected
   field. The other 6 approved factors were re-verified clean (their catalog expressions touch
   none of total_share/float_share/free_share).
2. data_correction_replay EXECUTED (not deferred): the promotion driver's deterministic dryrun
   reproduction (promote_sealed_oos_winners.py --mode dryrun) re-ran the EXACT frozen approved
   design on the corrected provider — frozen-13 set hash 5a8d601a… (unchanged), definition
   binding bound=True mismatched=[], OOS window 2021-01-01..2026-02-27, horizon 20,
   n_quantiles 5, temp seal claim (NO real seal spend), NO registry writes, promotion_evidence
   self-verified through the gate (all 6 PIT canaries + lint + live-provider parity passed).
   This replaces invalidated evidence after a data-layer correction; the design was not
   altered; the window remains spent for the frozen set.
3. RESULT — PASS, no downgrade needed:
     qual_piotroski_fscore_9pt: rank_icir 0.2156 (orig 0.2089), ls_sharpe(5d) 1.6342
     (orig 1.2029) — clears the original bar (sign+ AND >1.0) with IMPROVED metrics.
   Attribution control: the 5 non-consuming winners reproduce their ORIGINAL April-provider
   evidence EXACTLY (4-dp on both metrics: 0.4109/2.1431, 0.2759/2.6818, 0.2565/3.4441,
   0.2499/1.9560, 0.1966/1.4924) — so the Piotroski delta is isolated to the share-capital
   correction, and the approved set shows zero drift across three provider generations
   (prod_full_20260421 → phasec_20260624 → depth9 → sharecap patch).
   Artifact: sharecap_correction_replay_20260701.json (artifact_class: data_correction_replay,
   original vs replay per factor, verdicts, replay git_sha).

FOLD M1 (provider identity):
provider_build.json rotated: provider_build_id depth9_20260630 →
depth9_20260630_sharecap_reanchor_20260701 (+ provider_published_at refreshed,
source_git_commit = the fix commit e3ea7c4). DEVIATION from your suggested inline keys
(base_provider_build_id / patch_type / patch_fields / audit): schema v1
(schemas/provider_build.schema.json) declares additionalProperties:false, so inline patch keys
would make the manifest schema-invalid and fail load_provider_manifest. The patch lineage
therefore lives in a NEW append-only sidecar next to the manifest —
data/qlib_data/metadata/provider_patches.jsonl (gitignored with the provider tree, like the
manifest itself) — carrying exactly your suggested fields:
  {"provider_build_id": "depth9_20260630_sharecap_reanchor_20260701",
   "base_provider_build_id": "depth9_20260630",
   "patch_type": "in_place_value_correction",
   "patch_fields": ["$total_share", "$float_share", "$free_share"],
   "patch_script": "scripts/fix_share_capital_bins.py",
   "patch_source_git_commit": "e3ea7c4…",
   "backup_dir": "data/backups/share_capital_bins_20260701_221439",
   "audit": {"symbols_rewritten": 5748, "total_share_changed_stock_days": 2812728,
             "total_share_close_mv_off_gt1pct_before": 0.092289,
             "total_share_close_mv_off_gt1pct_after": 0.0000026, …}}
plus the COMMITTED note config/field_registry/approvals/2026-07-01_sharecap_reanchor_rebind.md.
All 24 approval YAMLs rebound to the new id (driver _rebind_approvals_sharecap.py, mirrors the
depth9 precedent; justification recorded: the patch touches ONLY the 3 share bins, and none of
the 24 approvals registers any of the 3 corrected fields). run_daily_qa AFTER rotation+rebind:
ALL PASS including provider_manifest_check and approval_evidence_binding (0 drift).

FOLD M2 (field_filter bypass):
[DIFF pit_backend.py]
-    def _materialize_share_capital_daily(self, calendar, target_dirs) -> list[str]:
+    def _materialize_share_capital_daily(self, calendar, target_dirs, *, force: bool = False) -> list[str]:
...
-        fields = self._apply_field_filter(list(SHARE_CAPITAL_DAILY_FIELDS))
-        if not fields:
-            return []
+        fields = list(SHARE_CAPITAL_DAILY_FIELDS)
+        if not force:
+            fields = self._apply_field_filter(fields)
+        if not fields:
+            return []
and the materialize_provider call site now passes force=True (comment documents that the kline
dump ignores field_filter, so the corrective rewrite must too). New regression test
test_materialize_share_capital_force_bypasses_unrelated_field_filter pins BOTH behaviors:
non-forced + unrelated filter → [] ; forced → all 3 fields written. Full affected suites:
share_capital 6 + pit_backend 34 + field_registry/approval_evidence 127 total PASS.

FOLD M3 (registry administrative record):
Append-only field_approval_log.jsonl entry, event approved_field_value_correction,
dataset daily_basic, from_status approved → to_status approved (no transition),
fields_corrected [$total_share, $float_share, $free_share], notes carrying old/new anchor, the
provider rotation, the audit numbers, and the B1 staleness consequence + replay pointer.

MINORS: m1 (daily_basic revision-drift canary) + m6 (target_ts_codes projection) recorded as
backlog in project_state 2026-07-01d, per your "future work" framing; m2-m5 confirmations
required no change.

REVIEW QUESTIONS (clearing pass)
1. B1: does the data_correction_replay as executed (deterministic dryrun reproduction, frozen
   design, temp seal, no real spend, no registry writes, self-verified gate artifact) satisfy
   your required action? Is the PASS + exact-control attribution sufficient to keep
   qual_piotroski_fscore_9pt normal-approved with evidence REPLACED, or do you require anything
   further recorded (e.g. a registry evidence-row append, which we deliberately did NOT do —
   registry master mutations outside the orchestrator publish path are §13 user-confirmation
   territory, and the artifact + approvals-note + approval-log pointers are the committed
   record)?
2. M1: is the schema-constrained split (rotated provider_build_id in the manifest + patch
   lineage in the provider_patches.jsonl sidecar + committed note) an acceptable equivalent of
   your inline-keys suggestion? Note the sidecar is gitignored like the manifest — the
   COMMITTED record is the approvals note + approval log + project_state; flag if you want the
   sidecar contract hardened (e.g. schema v2 with patch keys) as follow-up.
3. M2: any残留 bypass path you can still construct (e.g. write_compat_aliases=False builds,
   scoped updates, stage variants)?
4. Anything NEW introduced by the rework itself (the force param, the rebind, the rotation)
   that breaks a §3 invariant or a quantitative-research principle?

OUTPUT FORMAT
- Per round-1 finding: CLOSED / PARTIAL / OPEN with one-line justification.
- Any NEW issues ranked Blocker / Major / Minor with offending line + exact replacement.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
