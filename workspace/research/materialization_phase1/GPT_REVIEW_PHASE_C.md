ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. A single lookahead, a spent out-of-sample window, or a survivorship-filtered universe invalidates the result even if every test passes. Be skeptical, surface blockers, and do not rubber-stamp.

REPO (public — fetch any file to verify against the live code)
https://github.com/henrydan111/quant-system   (branch: report-rc-registration)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/<path>
NOTE: the materializer + canaries + all R2 folds (the publish script, the approval YAML, the Minor-1 helper
fix, the Minor-2 test fix) are COMMITTED + PUSHED to branch report-rc-registration (HEAD = d5f9083) — the
permalinks below are LIVE and reflect the R2 state. The factor `qual_dtprofit_to_profit_q` is NOT yet added
to the catalog (that lands post-publish); it is embedded below as the authoritative proposed definition.

CONTEXT — read these to judge the change against the contract:
- CLAUDE.md (hard invariants §3, PIT §3.2, formal-run governance §3.4, factor lifecycle §3.5, research integrity §7, no-hedge §7.10)
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/CLAUDE.md
- src/data_infra/pit_backend.py (the flow kernel `materialize_canonical_quarter_segments` @ ~L1387, `arrays_from_snapshot_segments` @ ~L1329, `derive_single_quarter_value`, `_write_feature_series` @ ~L2465, `materialize_provider` @ ~L3430, `publish` @ ~L3652 — ALL UNCHANGED; my new method `_materialize_profit_dedt_sq` is inserted @ ~L3060)
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/src/data_infra/pit_backend.py
- tests/data_infra/test_pit_backend.py (the EXISTING kernel canaries this change reuses: `test_flow_single_quarter_derivation_tracks_late_revision`, `test_canonical_quarter_segments_prefer_direct_quarter_and_fallback_per_field`)
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/tests/data_infra/test_pit_backend.py
- tests/data_infra/test_profit_dedt_sq.py (the 5 NEW method-level canaries — full source)
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/tests/data_infra/test_profit_dedt_sq.py
- config/field_registry/field_status.yaml (income family — `$n_income_attr_p_sq_q0` already approved @ L398)
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/config/field_registry/field_status.yaml

================================================================================
R3 — FOLDS APPLIED (responding to your R2 = REVISE: 1 Blocker + 1 Major)
================================================================================
BLOCKER (provider-bound approval YAML committed before the provider/registry state exists — §3.4
approval-evidence binding fails on the branch; $profit_dedt_sq_q0 not in field_status.yaml). FOLDED:
  - The approval YAML is MOVED OUT of config/field_registry/approvals/ to
    workspace/research/materialization_phase1/pending_registration/2026-06-24_profit_dedt_sq_to_approved.yaml
    so daily-QA approval_evidence_binding no longer sees a future-bound record. VERIFIED:
    tests/data_infra/test_approval_evidence.py now PASSES (it exposed the blocker; green after the move).
  - field_status.yaml is UNCHANGED pre-publish ($profit_dedt_sq_q0 stays unregistered → unknown → formal-blocked,
    which is correct until the provider attests to it).
  - The post-publish registration is now SCRIPTED + FAIL-CLOSED: workspace/scripts/_register_phasec.py REFUSES
    to register unless (1) the live provider_build.json provider_build_id == phasec_profit_dedt_sq_20260624 AND
    (2) the live provider actually SERVES $profit_dedt_sq_q0 (spot-checks real bins). Only then does it copy the
    approval YAML into approvals/, insert $profit_dedt_sq_q0 into the INDICATORS block of field_status.yaml, and
    append the field_approval_log.jsonl entry. So the governance layer can never claim an approved field the
    live provider/registry does not attest (your residual risk).
  - A field-registry smoke test is added: tests/data_infra/test_profit_dedt_sq_registry.py — SKIPS pre-publish
    (field not yet in field_status.yaml), and post-publish actively pins `resolve_field($profit_dedt_sq_q0)` =
    allowed/approved/dataset=indicators at every formal stage (also pins Major-2: indicators, NOT income).

MAJOR (additive copy /E can publish stale extras; integrity sampled). FOLDED in _publish_phasec_additive.py:
  - robocopy `/E` -> `/MIR` (MIRROR = /E + /PURGE): the staged tree is made EXACTLY equal to live, purging any
    stale extras (incl. a prior --dry-run's $profit_dedt_sq_*.day.bin). The mirror runs BEFORE materialize, so
    the order (mirror -> materialize the new field) is intact; the run also asserts robocopy mismatch==0 (not
    just failed==0).
  - integrity_check is now FULL (every one of the ~5755 feature dirs, not a 120-dir sample): per-dir
    (filename, size) equality staged-vs-live, added-field bins excluded; fail-fast after 50 mismatches.

ALL R3 + R2 helper/test/canary tests GREEN: test_profit_dedt_sq.py + test_profit_dedt_sq_registry.py(skip) +
test_approval_evidence.py + test_pit_backend.py + test_field_registry.py + test_pit_alignment_core.py.

R3 NEW/CHANGED FILES:
  - workspace/scripts/_publish_phasec_additive.py        (/MIR + full integrity)
  - workspace/scripts/_register_phasec.py                (NEW — fail-closed post-publish registration)
  - tests/data_infra/test_profit_dedt_sq_registry.py     (NEW — skip-until-present smoke test)
  - config/field_registry/approvals/2026-06-24_profit_dedt_sq_to_approved.yaml  (MOVED OUT -> pending_registration/)

R3 REVIEW QUESTION: does moving the approval out of approvals/ (clean branch now) + the fail-closed
_register_phasec.py (provider must attest the build-id AND serve the field before any governance edit) close
the Blocker? Any remaining objection to the additive /MIR publish?

================================================================================
R2 — FOLDS APPLIED (responding to your R1 = REVISE; no blocker was found)
================================================================================
Your R1 found 0 Blockers, 2 Majors, 2 Minors. All folded; please confirm SHIP.

MAJOR-1 (publish provenance too informal — the residual risk). FOLDED via a scripted, honest-provenance
additive publish: workspace/scripts/_publish_phasec_additive.py.
  - The manifest schema (schemas/provider_build.schema.json) ENUM-constrains builder.stage to
    {full, upstream-only, provider-only} and is additionalProperties=False — so `builder_stage="additive_provider_copy"`
    would FAIL validation. Instead the script emits the TRUTHFUL existing enum values
    `builder_mode="update"` + `builder_stage="provider-only"` (the builder's publish() hardcodes all/full for
    EVERY publish — a latent inaccuracy your review surfaced; flagged separately, not fixed in-scope), via
    `publish(emit_manifest=False)` then a direct `emit_manifest_at_publish(...)`. NO core-builder change.
  - A free-form sidecar `data/qlib_data/metadata/additive_build_provenance.json` records exactly what you
    asked: base_provider_build_id, added_fields=[$profit_dedt_sq_q0..q4], robocopy exit/summary (files
    total/copied/skipped/FAILED, bytes), unchanged-bin integrity (dir-list identity + sampled per-dir
    file-count/size equality, asserted BEFORE the new field is materialized), and new-field parity vs vendor
    q_dtprofit. The script ABORTS (non-zero) on robocopy failures, integrity mismatch, or parity failure.
  - The approval YAML (below) binds to provider_build_id="phasec_profit_dedt_sq_20260624" — the same id the
    manifest + sidecar carry. So the rebind lands on a provider whose evidence fully describes the additive add.

MAJOR-2 (registry placement must be indicators-derived, not income). FOLDED:
  config/field_registry/approvals/2026-06-24_profit_dedt_sq_to_approved.yaml registers $profit_dedt_sq_q0 under
  dataset_id=indicators with source_dataset=indicators, source_class=derived_flow_from_snapshot_ledger,
  coverage_tier=sub, replacement_for_vendor_q=q_dtprofit_to_profit, bound to the new provider_build_id. The
  field_status.yaml line is appended to the `indicators` family block (NOT income) at publish time.

MINOR-1 (shared helper accepts any March date as Q1). FOLDED: pit_backend.py
  derive_single_quarter_value L1273-1274 now `(end_date.month, end_date.day) == (3, 31)` (was `month == 3`).
  Full helper-driving test files re-run GREEN: test_pit_backend.py + test_profit_dedt_sq.py +
  test_pit_alignment_core.py (40) + test_field_registry.py (49) = 89 passed.

MINOR-2 (test used uppercase fake Qlib code). FOLDED: test_profit_dedt_sq.py `_FAKE_CODE = "000001_sz"` (lowercase).

NEW/CHANGED FILES FOR THIS R2 (raw links live after the R2 push):
  - workspace/scripts/_publish_phasec_additive.py
  - config/field_registry/approvals/2026-06-24_profit_dedt_sq_to_approved.yaml
  - src/data_infra/pit_backend.py (helper Minor-1) ; tests/data_infra/test_profit_dedt_sq.py (Minor-2)

R2 REVIEW QUESTION: does the additive-publish provenance (truthful update/provider-only manifest + the
additive_build_provenance.json sidecar + the build-id-bound approval YAML) close your residual risk? Any
remaining objection to the additive path vs forcing the full ~8h copytree+re-materialize?

--------------------------------------------------------------------------------

SELF-REVIEW PREFLIGHT — completed before this GPT request: PASS. Checked §3 invariants + the 9 principles.
- PIT: the new field anchors on the indicators `ann_date → effective_date` (strict next-open after disclosure), the SAME anchor as the already-approved `q_roe`/`pit_*` indicators fields; it reuses the proven restatement-safe kernel `derive_single_quarter_value`; predictive factor wraps every field in `Ref(...,1)`. No raw-ledger read in any research path (the materializer is a BUILDER, not a research reader).
- DENOMINATOR self-corrected from the Plan-C fold: the empirical value-parity test (mandated by the plan) picked 归母 `n_income_attr_p`, NOT consolidated `n_income` — proven from data, not assumed (see below).
- Fixes made vs the plan: (1) denominator 归母 not consolidated; (2) 5 method-level canaries instead of re-testing the already-canaried kernel.
- Residual concerns for reviewer: (a) is the additive-only robocopy-stage publish (skip re-materializing unchanged indicators bins) safe vs the documented full-copytree+re-materialize path? (b) is `coverage_tier=sub` the right governance label given the board-skewed derivability? (c) the 99.2% exact match to the vendor's own ratio — is reproducing a PIT-uncertain vendor field through the PIT path a legitimate validation, or circular?

================================================================================
WHAT CHANGED (authoritative)
================================================================================

GOAL. The 25 Tushare `fina_indicator` single-quarter `q_*` fields are PIT-UNCERTAIN (vendor pre-computed,
no disclosure-anchor guarantee) and were INTENTIONALLY left unregistered (2026-06-09). Phase-B re-derived
the derivable ones PIT-correctly from our approved `_sq` fields. The LAST valuable one not so expressible is
`q_dtprofit_to_profit` (单季扣非净利润占净利润 = earnings quality: fraction of single-quarter net profit that is
recurring/core). Its numerator (单季扣非净利润) is not in any approved `_sq` slot, so we materialize it
PIT-correctly as a NEW provider field `$profit_dedt_sq_q0..q4` and define ONE factor on it.

SOURCE. `profit_dedt` (扣非净利润, 归母-scope) lives in the indicators (fina_indicator) PIT ledger as a
fiscal-YTD CUMULATIVE, reported at ALL FOUR fiscal quarters (verified coverage Q1 94% / H1 96% / Q3 95% /
FY 98% — NOT semi-annual like the cashflow 折旧摊销 fields, which was the make-or-break risk). So the single
quarter = `profit_dedt[Q] − profit_dedt[Q−1]` is genuinely derivable through the same kernel the
income/cashflow families use.

--- NEW METHOD (src/data_infra/pit_backend.py, inserted ~L3060) ---

    def _materialize_profit_dedt_sq(
        self,
        calendar: pd.DatetimeIndex,
        target_dirs: dict[str, str],
    ) -> list[str]:
        """Single-quarter 扣非净利润 ($profit_dedt_sq_q0..q4) from the indicators-ledger CUMULATIVE.

        `profit_dedt` (扣除非经常性损益后的归母净利润) is reported CUMULATIVE YTD in the fina_indicator
        (indicators) ledger at ALL four fiscal quarters. It is not a flow-family ledger field, so this
        custom materializer drives the SAME flow path the income/cashflow families use:
        `materialize_canonical_quarter_segments` (cumulative -> single-quarter via
        `derive_single_quarter_value`, restatement-safe) + `arrays_from_snapshot_segments` on the DERIVED
        quarter values. It does NOT snapshot-expand the raw cumulative (GPT Plan-C Minor).

        PIT: anchored on the indicators `ann_date -> effective_date` (strict next-open after disclosure,
        §3.2), same anchor as the approved q_roe; restatement-safe. Served NaN where the consecutive
        cumulative chain is not yet PIT-computable is a SUB-UNIVERSE coverage gap vs the vendor q_dtprofit
        (which reports the single-q DIRECTLY at higher coverage); that gap is the PIT cost (coverage_tier=sub).
        Consumers wrap in Ref(...,1).

        GPT Plan-C Major-3: PREFILTERS to standard fiscal-quarter ends (03-31/06-30/09-30/12-31) so an
        irregular end_date can never be mis-mapped to a quarter (a 03-30 row is dropped, not treated as Q1).
        """
        field = "profit_dedt"
        slots = [f"{field}_sq_q{s}" for s in range(self.slot_depth)]
        if self.field_filter and not any(s in self.field_filter for s in slots):
            return []
        ledger_path = self.ledger_path("indicators")
        if not os.path.exists(ledger_path):
            return []
        ledger = pd.read_parquet(ledger_path)
        if ledger.empty or field not in ledger.columns:
            return []
        keep = [c for c in ("qlib_code", "end_date", "ann_date", "f_ann_date", "disclosure_date",
                            "effective_date", "report_type", "update_flag", field) if c in ledger.columns]
        ledger = ledger[keep].dropna(subset=[field, "effective_date", "end_date"]).copy()
        # GPT Plan-C Major-3: keep ONLY standard fiscal-quarter ends; irregular dates -> excluded.
        ed = normalize_date_series(ledger["end_date"])
        std = (((ed.dt.month == 3) & (ed.dt.day == 31)) | ((ed.dt.month == 6) & (ed.dt.day == 30))
               | ((ed.dt.month == 9) & (ed.dt.day == 30)) | ((ed.dt.month == 12) & (ed.dt.day == 31)))
        ledger = ledger.loc[std.to_numpy()].copy()
        ledger = ledger[ledger["qlib_code"].isin(set(target_dirs))]
        if ledger.empty:
            return []
        written: list[str] = []
        groups = {code: g for code, g in ledger.groupby("qlib_code")}
        for qlib_code in iter_progress(sorted(groups), total=len(groups),
                                       desc="Materialize profit_dedt_sq", unit="symbol", leave=False):
            feature_dir = target_dirs.get(qlib_code)
            if feature_dir is None:
                continue
            segments = materialize_canonical_quarter_segments(
                groups[qlib_code], None, calendar, quarter_fields=[field], slot_depth=self.slot_depth)
            arrays = arrays_from_snapshot_segments(segments, [field], len(calendar), self.slot_depth)
            for slot in range(self.slot_depth):
                name = f"{field}_sq_q{slot}"
                self._write_feature_series(feature_dir, name, arrays[f"{field}_q{slot}"])
                written.append(name)
        return sorted(set(written))

--- DISPATCH WIRING (materialize_provider, ~L3483) ---

        if "indicators" in active_datasets and os.path.exists(self.ledger_path("indicators")):
            written["indicators"] = self._materialize_snapshot_dataset("indicators", calendar, target_dirs)
            # Custom: single-quarter 扣非净利润 derived from the indicators-ledger CUMULATIVE profit_dedt
            # (flow-state via materialize_canonical_quarter_segments, NOT snapshot-expanded). Writes
            # $profit_dedt_sq_q0..q4 (sub-universe; the vendor q_dtprofit reports the single-q directly).
            written["profit_dedt_sq"] = self._materialize_profit_dedt_sq(calendar, target_dirs)

--- THE FACTOR (to be added to src/alpha_research/factor_library/catalog.py AFTER publish, then sync as draft) ---

    qual_dtprofit_to_profit_q = If(Abs(Ref($n_income_attr_p_sq_q0, 1)) > 0,
                                   Ref($profit_dedt_sq_q0, 1) / Ref($n_income_attr_p_sq_q0, 1),
                                   np.nan)
    # 单季扣非净利润占归母净利润 (earnings quality). Denominator 归母 n_income_attr_p (already approved),
    # numerator the new $profit_dedt_sq_q0. coverage_tier=sub. Both fields Ref(...,1) lagged (§3.2).

================================================================================
DENOMINATOR — EMPIRICALLY DECIDED (the Plan-C fold said "ship only the match"; it ran)
================================================================================
The vendor's OWN single-quarter ratio `$q_dtprofit_to_profit_q0` is served (it is PIT-uncertain so we do
NOT register it, but it is a valid VALUE oracle). Using the proven identity `$profit_dedt_sq_q0 ==
$q_dtprofit_q0` (the vendor's direct single-q amount; see validation below) to reconstruct the ratio
`q_dtprofit_q0 / <denom>_sq_q0 × 100` vs the vendor ratio, 180 stocks × 2016-24, 254,576 obs:

  denominator                          med abs diff (pct-pts)   within 0.5 pts
  n_income_attr_p_sq_q0 (归母净利润)         0.000                  99.2%   <- MATCH
  n_income_sq_q0        (consolidated)      2.264                  33.1%
  total_profit_sq_q0    (利润总额)          16.557                  2.4%

=> denominator is 归母 `n_income_attr_p` (numerator 扣非归母 and denominator 归母 are both 归母-scope —
accounting-consistent). The Plan-C fold's generic "n_income" was loose; the data says 归母. (rule §7.10:
proven from data, not assumed.)

================================================================================
VALIDATION
================================================================================
1. CANARIES (tests/data_infra/test_profit_dedt_sq.py — 5, ALL PASS). The kernel
   (`materialize_canonical_quarter_segments` + `derive_single_quarter_value`) is ALREADY canaried in
   test_pit_backend.py for late-restatement + Q3−Q2 + slot-order, so these target the SEAM unique to the
   new method:
     - test_irregular_fiscal_end_excluded   : a synthetic 2023-03-30 row (sentinel 9999) NEVER leaks into any slot (the Major-3 prefilter)
     - test_q1_equals_cumulative            : Q1 single-q == cumulative
     - test_missing_prior_quarter_is_nan    : at first Q1 visibility, deeper slots are NaN (never fabricated)
     - test_single_quarter_and_slot_order   : full 2023 stack q0..q3 = [Q4=140, Q3=110, Q2=150, Q1=100] (newest->oldest), rolls correctly when Q1-2024 arrives
     - test_all_five_slots_written          : field plumbing profit_dedt -> profit_dedt_sq_q0..q4
   Method is driven REAL (monkeypatch `_write_feature_series` to capture arrays — no close.day.bin fixture needed).

2. SANDBOX VALUE-PARITY (5-stock provider-only build, read through Qlib). `$profit_dedt_sq_q0` vs the
   vendor's direct `$q_dtprofit_q0`: med_rel 0.00000, within-1% 1.000, sign 1.000, ~98% non-NaN. The PIT
   derivation reproduces the vendor's direct single-q EXACTLY — but via the sanctioned PIT path, so it is
   formal-eligible where the vendor q_dtprofit is not. (This exactness is EXPECTED: the vendor's single-q is
   itself a cumulative difference; the match validates the ARITHMETIC. PIT-correctness is inherited from the
   proven kernel/anchor, not from this match.)

3. COVERAGE (_phasec_profit_dedt_coverage_audit.py) -> coverage_tier=sub. Single-q derivability by board:
   主板 84.6% / 创业板 64.6% / 科创板 52.4% / 北交所 27.0%; young-cohort thinning (Q4 derivability 60%->90%,
   2016->2024). Structurally tilted to established Main-board names. The factor must NOT compete as a
   full-universe factor without the sub-universe mask/disclosure (E1g/E1h precedent).

================================================================================
STAGING / PUBLISH (operational — NOT the materializer; flagged for your sanity check)
================================================================================
`materialize_provider(mode="update")` with no touched-symbols does `shutil.copytree(live -> staged)` of the
3.8M-file provider = ~8 h on this disk (130 files/s, single-threaded Python). To add ONE additive field that
is unviable. Plan:
  (1) robocopy /MT:32 live -> staged (parallel, INDEPENDENT files; ~2 min, 192 dirs/s benchmarked).
  (2) materialize ONLY $profit_dedt_sq into the staged tree (call `_materialize_profit_dedt_sq` directly;
      it writes ONLY new files; the existing bins are byte-identical robocopy copies, NOT re-derived).
  (3) verify staged: vendor-parity on $profit_dedt_sq + a sample of existing fields (close, q_roe)
      byte-identical staged-vs-live.
  (4) `builder.publish()` — the PROVEN atomic os.replace swap + .bak backup + fresh provider_build.json.
End state + publish path identical to the Phase-1 publish; only the staging COPY mechanism differs, and the
staged tree is verified byte-identical (minus the new field) before the swap. Q FOR YOU: is skipping the
re-materialization of the unchanged indicators bins (they are current — built by the Phase-1 publish off the
same ledger) sound, or do you want the full re-materialize+validate path despite the regression risk of
re-deriving identical bins?

REGISTRATION (after publish): append `$profit_dedt_sq_q0` to the income or a new indicators-derived block in
field_status.yaml with an approval YAML + field_approval_log.jsonl entry bound to the new provider_build_id;
add `qual_dtprofit_to_profit_q` to the catalog + `sync_catalog` (lands as draft); re-bind the prior approvals
to the new publish (the daily-QA approval_evidence_binding requires 0 drift).

================================================================================
QUANTITATIVE-RESEARCH PRINCIPLES — check the change against EACH; a violation is a Blocker
================================================================================
1. PIT / NO-LOOKAHEAD. Does any value at time t use info not knowable at t? Anchor = indicators
   ann_date->effective_date (strict next-open); restatement via derive_single_quarter_value; factor Ref(...,1).
2. OOS SACRED. (N/A — no OOS spent here; this is a data-materialization + one draft factor. The factor's
   eventual IS/OOS gate is downstream.)
3. SURVIVORSHIP. The materializer writes per existing provider feature dir (delisted names included via the
   instruments sidecar); does it introduce any currently-listed-only filter? (it should not).
4. FACTOR-EVAL STANDARD. (factor lands as DRAFT; promotion is a separate gate. Is coverage_tier=sub the right
   guard so it cannot masquerade as a full-universe factor?)
5–6. EXECUTION / NO LEVERAGE. (N/A — no backtest here.)
7. NO HEDGE WORDS. Are any claims above unbacked by a named script/output?
8. FOUR-LAYER. (factor computed on the full provider; sub-universe is a downstream mask, not a pre-filter.)
9. MULTIPLE TESTING. (one factor; the coverage skew + the redundancy vs the vendor q_dtprofit are disclosed.)

REVIEW QUESTIONS
1. Correctness — logic bugs / edge cases in `_materialize_profit_dedt_sq`: the std-end prefilter, the
   cumulative->single-q via the snapshot-segments path, slot semantics, NaN/sign propagation, the
   `quarterly_df=None` call into `materialize_canonical_quarter_segments`. The Tushare(000001.SZ) vs
   Qlib(000001_SZ) format is handled by `isin(target_dirs)` (target_dirs keys are qlib_code lower) — correct?
2. Governance — does adding a NEW provider field via a bespoke materializer in the dispatch (rather than a
   DATASET_SPECS-driven family) honor §3.2/§3.4? Is the additive robocopy publish a legitimate use of the
   proven publish path, or a §6.3 violation?
3. Design — is reusing `materialize_canonical_quarter_segments` (a snapshot-family helper) for a single
   cumulative field the right call, or should this go through a flow-family spec? Any hidden coupling?
4. Evidence — what proof is missing; the exact test/command you'd run to confirm it.

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested
  replacement. Map every Blocker to the principle or invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
