# GPT cross-review prompt — bare share-capital bin re-anchor (REPORT → EFFECTIVE-DATE)

Copy the block below to GPT-5.5 Pro. Branch pushed: `trading-agents-design` @ `b6c6d1b` (fix commit `e3ea7c4`).

---

```text
ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. A single lookahead, a spent out-of-sample window, or a survivorship-filtered universe invalidates the result even if every test passes. Be skeptical, surface blockers, and do not rubber-stamp.

REPO (public — fetch any file to verify against the live code)
https://github.com/henrydan111/quant-system   (branch: trading-agents-design, pinned commit b6c6d1b; fix commit e3ea7c4)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/<path>

CONTEXT — read these to judge the change against the contract:
- CLAUDE.md  (hard invariants §3, PIT §3.2, sealed-OOS §3.4, research integrity §7, no-hedge §7.10, no-leverage §7.11)
  https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/CLAUDE.md
- https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/src/data_infra/pit_backend.py  (the touched module — SHARE_CAPITAL_DAILY_FIELDS, load_share_capital_daily_frame, share_capital_daily_arrays, _materialize_share_capital_daily, the two compat-alias skip guards, the materialize_provider wiring)
- https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/scripts/fix_share_capital_bins.py  (one-time in-place live-provider fix)
- https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/tests/data_infra/test_share_capital_daily.py  (5 new tests)
- https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/src/alpha_research/factor_library/catalog.py  (consumers: earn_q_eps line ~244 divides Ref($n_income_attr_p_sq_q0,1) by Ref($total_share,1); a qual composite line ~719 uses If(Ref($total_share,1) <= Ref($total_share,251)) as an anti-dilution term)
- https://raw.githubusercontent.com/henrydan111/quant-system/trading-agents-design/data/data_dictionary.md  (daily-section anchoring/unit note added)

SELF-REVIEW PREFLIGHT — completed before this GPT request: verdict = clean for GPT.
Checked §3 invariants + each quantitative-research principle. Fixes made during self-review:
- Made _materialize_share_capital_daily UNCONDITIONAL in materialize_provider (was gated on
  "daily" in active_datasets): the kline dump also runs unconditionally on non-scoped updates,
  so a datasets-subset update would have appended raw 万股 values to the total_share tail
  without the ×1e4 re-write — a silent unit-inconsistent last day.
- Annotated a PRE-EXISTING PIT001 lint error (workspace/scripts/guorn_dividend_caliber.py:113,
  unrelated file from the same branch) with the sanctioned noqa: end_date is used as a
  fiscal-period label AFTER the ann_date<=signal PIT filter — not a visibility anchor.
Residual concerns handed to you explicitly: see REVIEW QUESTIONS 5-9.

WHAT CHANGED (authoritative — treat the embedded text as the source of truth; the links cross-check the surrounding code)

## The bug (evidence-complete, found in the 果仁 parity battle 2026-07-01)
The Qlib provider's bare daily `total_share.day.bin` was REPORT-anchored: it equalled the
balancesheet snapshot family's `total_share_q0` on 100% of history (BYD 002594: 3,560/3,560
days; 成飞 302132: 1,830/1,830). Mechanism: `_build_price_csvs` dumps ALL numeric raw-daily
columns (including the effective-date-anchored daily_basic `total_share`, unit 万股), but
`_materialize_snapshot_dataset(balancesheet)` runs LATER and its bare compat-alias loop wrote
`{field}_q0` over the same file name (balancesheet carries a same-named `total_share` payload
column, unit 股). Consequences measured on the live provider BEFORE the fix:
- BYD 002594 bin stuck at 3.039e9 through 2025-10-31, stepping to 9.117e9 only at 2025-11-03
  (= Q3-report effective date; ledger row confirms), while raw daily showed the real steps
  2025-03-12 (H-share placement -> 3.039e9), 2025-06-11 (-> 5.495e9), 2025-07-29 (-> 9.117e9).
  The report-anchored bin NEVER saw the 5.495e9 level at all.
- 成飞 302132: real steps 2025-01-22 (merger share issuance) / 2025-08-15 (repurchase
  cancellation); bin stepped 2025-04-30 / 2025-10-30 (report disclosures) — 1-3 months late.
- Internal inconsistency: $total_share × $close vs $total_mv was off by >1% on 9.23% of
  stock-days (302-symbol sample, max_rel 30.4). $total_mv itself matches raw exactly.
- float_share / free_share bare bins were NOT clobbered (balancesheet has no such columns) —
  they were already effective-date-anchored from the kline dump, in raw 万股 units.

## The fix (code, commit e3ea7c4) — full diff of src/data_infra/pit_backend.py + the noqa:

[DIFF — pit_backend.py]
@@ CORE_METADATA_COLUMNS ... @@
 NORTHBOUND_RENAMES = {"vol": "north_hold_vol"}
 DIVIDEND_COMPAT_FIELDS = {"stk_div", "stk_bo_rate", "stk_co_rate", "cash_div", "cash_div_tax"}
+# Bare share-capital daily bins: EFFECTIVE-DATE anchored from the raw market/daily columns
+# (Tushare daily_basic merge, unit 万股). The balancesheet snapshot family carries a same-named
+# report-period `total_share` payload whose bare compat alias used to CLOBBER the daily bin with
+# the report-anchored q0 series — 1-2 months late vs real share changes and internally
+# inconsistent with $total_mv (2026-07-01 果仁-parity finding, BYD 002594 / 成飞 302132).
+# `_materialize_share_capital_daily` owns these bare bins; `_materialize_snapshot_dataset` /
+# `_materialize_flow_family` skip the colliding bare alias (the report-anchored series stays
+# available as `{field}_q0..qN`). Values are the multiplier × the raw 万股 column, preserving each
+# bin's LEGACY unit so consumers stay calibrated: `total_share` in 股 (earn_q_eps divides 元 by
+# it), `float_share`/`free_share` in 万股 (size_ln_free_float et al.).
+SHARE_CAPITAL_DAILY_FIELDS: dict[str, float] = {
+    "total_share": 1e4,
+    "float_share": 1.0,
+    "free_share": 1.0,
+}

+def load_share_capital_daily_frame(data_root: str, fields: Iterable[str] | None = None) -> pd.DataFrame:
+    """Column-projected load of the raw market/daily share-capital columns.
+
+    Reads the SAME files the kline dump consumes (``DATASET_SPECS['daily']``) but only
+    ``ts_code`` / ``trade_date`` + the requested ``SHARE_CAPITAL_DAILY_FIELDS`` columns
+    (unit 万股, verbatim from Tushare daily_basic). Tolerant of per-file schema gaps —
+    a file carrying none of the requested share columns is skipped. Shared by the
+    provider build step and ``scripts/fix_share_capital_bins.py`` so the source of the
+    bare share-capital bins lives in exactly one place.
+    """
+    selected = [name for name in (fields or SHARE_CAPITAL_DAILY_FIELDS) if name in SHARE_CAPITAL_DAILY_FIELDS]
+    if not selected:
+        return pd.DataFrame(columns=["ts_code", "trade_date"])
+    spec = DATASET_SPECS["daily"]
+    paths = sorted(glob(os.path.join(data_root, spec.raw_pattern), recursive=True))
+    if not paths:
+        raise BuildGateError("No market daily Parquet files found for share-capital materialization")
+    wanted = ["ts_code", "trade_date", *selected]
+    frames: list[pd.DataFrame] = []
+    for path in iter_progress(paths, total=len(paths), desc="Load share-capital raw", unit="file", leave=False):
+        try:
+            frame = pd.read_parquet(path, columns=wanted)
+        except (KeyError, ValueError):
+            frame = pd.read_parquet(path)
+            keep = [column for column in wanted if column in frame.columns]
+            if not set(keep) & set(selected):
+                continue
+            frame = frame[keep]
+        frames.append(frame)
+    out = pd.concat(frames, ignore_index=True)
+    out["ts_code"] = out["ts_code"].astype(str).str.upper()
+    out["trade_date"] = normalize_date_series(out["trade_date"])
+    return out.dropna(subset=["trade_date"])
+
+
+def share_capital_daily_arrays(
+    symbol_daily: pd.DataFrame,
+    calendar: pd.DatetimeIndex,
+    fields: Iterable[str] | None = None,
+) -> dict[str, np.ndarray]:
+    """Full-calendar effective-date-anchored share-capital arrays for ONE symbol.
+
+    ``symbol_daily`` holds the symbol's raw market/daily rows (``trade_date`` + 万股-unit
+    share columns). Each field is scaled by its ``SHARE_CAPITAL_DAILY_FIELDS`` multiplier
+    (legacy bin units), reindexed to the provider calendar, then FORWARD-FILLED from the
+    first observation: share capital is a state variable, so a suspension gap keeps the
+    last known share count (the §8.1 ranking-context contract — suspended-but-listed
+    names still need a denominator). No back-fill — days before the first observation
+    stay NaN. PIT: the value on trade day T is the same-day EOD daily_basic state (same
+    class as $total_mv/$pe); predictive factors apply their own ``Ref(..., 1)`` lag.
+    """
+    selected = {
+        name: SHARE_CAPITAL_DAILY_FIELDS[name]
+        for name in (fields or SHARE_CAPITAL_DAILY_FIELDS)
+        if name in SHARE_CAPITAL_DAILY_FIELDS
+    }
+    work = (
+        symbol_daily.sort_values("trade_date")
+        .drop_duplicates(subset=["trade_date"], keep="last")
+        .set_index("trade_date")
+    )
+    arrays: dict[str, np.ndarray] = {}
+    for field_name, multiplier in selected.items():
+        if field_name not in work.columns:
+            continue
+        series = pd.to_numeric(work[field_name], errors="coerce") * multiplier
+        arrays[field_name] = series.reindex(calendar).ffill().to_numpy(dtype=np.float32)
+    return arrays

@@ _materialize_snapshot_dataset, compat-alias loop @@
             if self.write_compat_aliases:
                 for field_name in numeric_fields:
+                    if field_name in SHARE_CAPITAL_DAILY_FIELDS:
+                        # The bare bin is EFFECTIVE-DATE anchored and owned by
+                        # _materialize_share_capital_daily; the report-anchored
+                        # series stays available as {field}_q0..qN.
+                        continue
                     self._write_feature_series(feature_dir, field_name, arrays[f"{field_name}_q0"])
                     written_fields.append(field_name)

@@ _materialize_flow_family, compat-alias loop @@
             if self.write_compat_aliases:
                 for field_name in raw_cumulative_fields:
+                    if field_name in SHARE_CAPITAL_DAILY_FIELDS:
+                        # Defensive: no flow family carries these names today, but a bare
+                        # share-capital bin must never be clobbered by a report-anchored alias.
+                        continue
                     self._write_feature_series(feature_dir, field_name, cumulative_arrays[f"{field_name}_cum_q0"])
                     written.append(field_name)

@@ new builder method (after _materialize_derived_limit_status) @@
+    def _materialize_share_capital_daily(
+        self,
+        calendar: pd.DatetimeIndex,
+        target_dirs: dict[str, str],
+    ) -> list[str]:
+        """Bare share-capital bins from the raw market/daily columns (EFFECTIVE-DATE anchor).
+
+        Owns the bare ``total_share`` / ``float_share`` / ``free_share`` day bins (see
+        ``SHARE_CAPITAL_DAILY_FIELDS`` for the collision story and the legacy unit contract).
+        The kline dump already stages these columns from raw daily, but this step re-writes
+        them explicitly AFTER every family materialization so the bare bins are
+        effective-date-anchored in every build mode — full ``all``, non-scoped ``update``
+        (kline dump only appends), and scoped ``--touched-symbols`` updates (no kline dump at
+        all). Symbols with no raw daily rows (index codes) keep their existing bins untouched.
+        """
+        fields = self._apply_field_filter(list(SHARE_CAPITAL_DAILY_FIELDS))
+        if not fields:
+            return []
+        frame = load_share_capital_daily_frame(self.paths.data_root, fields=fields)
+        available = [name for name in fields if name in frame.columns]
+        if not available:
+            return []
+        written: list[str] = []
+        groups = {ts_code: group for ts_code, group in frame.groupby("ts_code")}
+        for qlib_code, feature_dir in iter_progress(
+            target_dirs.items(), total=len(target_dirs),
+            desc="Materialize share capital", unit="symbol", leave=False,
+        ):
+            symbol_df = groups.get(qlib_code.replace("_", ".").upper())
+            if symbol_df is None:
+                continue
+            arrays = share_capital_daily_arrays(symbol_df, calendar, fields=available)
+            for field_name, values in arrays.items():
+                self._write_feature_series(feature_dir, field_name, values)
+                written.append(field_name)
+        return sorted(set(written))

@@ materialize_provider wiring (after quality_stability, before the daily-fact loop) @@
+        # Bare share-capital bins (total_share/float_share/free_share): effective-date
+        # anchor from raw daily. Runs AFTER the statement families so a colliding
+        # report-anchored compat alias can never be the last writer (the alias loops
+        # also skip these names — defense in depth). UNCONDITIONAL like the kline dump
+        # (NOT gated on active_datasets): a datasets-subset update still re-dumps the
+        # kline CSVs, which would append raw 万股 values to the total_share tail — this
+        # step must always follow to restore the ×1e4 股-unit contract.
+        written["share_capital_daily"] = self._materialize_share_capital_daily(calendar, target_dirs)

[DIFF — workspace/scripts/guorn_dividend_caliber.py (pre-existing lint, unrelated to the fix)]
-    ev["ed"] = ev["end_date"].astype(str)
+    ev["ed"] = ev["end_date"].astype(str)  # noqa: unsafe-pit-dates[PIT001] reason: end_date is a fiscal-period LABEL here; visibility already PIT-gated by the ann<=sig filter above

Plus: scripts/fix_share_capital_bins.py (dry-run-default in-place fixer sharing the SAME
kernel; backs up every overwritten bin; fetch via the raw link) and
tests/data_infra/test_share_capital_daily.py (5 tests: effective anchor + legacy units;
ffill-gap/no-backfill; snapshot alias skips share capital while _q0 slots still written and a
non-colliding field still gets its bare alias; end-to-end from raw daily parquet with an
index-like symbol untouched; field_filter respected).

## Applied to the LIVE provider + verified (2026-07-01):
- scripts/fix_share_capital_bins.py --live: 5,748 syms × 3 bins rewritten; backup
  data/backups/share_capital_bins_20260701_221439/ (17,244 files, 172MB).
- total_share changed on 2.81M stock-days (~9%); float/free only gained suspension-gap ffill
  (~0.5M days each) — their anchoring was already correct.
- Post-fix: BYD + 302132 bin step-dates == raw column step-dates (2024+ exact list match).
- $total_share × $close vs $total_mv: >1%-off days 9.23% → 0.0003% (max_rel 30.4 → 0.022).
- finite→NaN delta = 208,231 days, 100% BSE (.BJ) symbols in their pre-BSE-listing NEEQ era
  (2015-2022 peak), where the ENTIRE daily_basic block has no coverage ($total_mv finite on 0
  of those days) — the old values were report-ffill spillover into a period with no daily
  data, judged coverage-truth, not a regression.
- earn_q_eps denominator drift: 16.2% of stock-days changed; among changed, median |Δ| 2.9%.
- audit_qlib.py PASS (its alias-parity list never asserted total_share==q0), qlib_smoke PASS,
  run_daily_qa ALL PASS, pytest (share_capital 5 + pit_backend 34 + profit_dedt 5 +
  event_like namespace) 49 passed.

QUANTITATIVE-RESEARCH PRINCIPLES — check the change against EACH; a violation is a Blocker
1. PIT / NO-LOOKAHEAD (the cardinal rule). Fundamentals align on ann_date (NOT end_date), shift(1), forward-fill. Research PIT reads go ONLY through pit_research_loader / qlib_windowed_features — never raw data/pit_ledger/* and never hand-rolled alignment. Predictive factor fields are wrapped in Ref(...,1). Ask: does any value at time t use information not knowable at t?
2. OUT-OF-SAMPLE IS SACRED & SEALED. Temporal walk-forward splits only, never random. The holdout is single-shot / spend-on-attempt; never re-run a sealed OOS to "verify". No factor/parameter selected on OOS results.
3. SURVIVORSHIP. Universes include delisted + suspended names; never filter to currently-listed only.
4. FACTOR-EVAL STANDARD. IC, RankIC, ICIR, quantile spread, monotonicity, decay, turnover before promotion; marginal orthogonal contribution.
5. EXECUTION & COST REALISM. T+1, limit up/down, suspension, corporate actions.
6. NO LEVERAGE. Unlevered numbers only.
7. NO HEDGE WORDS. Every quantitative claim backed by a named dataset/script/output.
8. FOUR-LAYER PIPELINE. factor (full market) -> universe (masks) -> signal (rank in sub-universe) -> execution (tradability ONLY here).
9. MULTIPLE TESTING. Count effective trials; guard selection/overfitting.

REVIEW QUESTIONS
1. PIT: is the effective-date anchor PIT-safe as claimed? The daily_basic value on trade day T
   is the same-day EOD state (same visibility class as $total_mv/$pe, an approved family);
   predictive consumers wrap Ref(...,1). Is there ANY path where the new bin serves a value at
   t not knowable at t (e.g. Tushare retroactively backfilling a daily_basic row and our raw
   store absorbing it — does that differ materially from the same exposure $total_mv already
   has)?
2. Correctness of the kernel: reindex→scale→ffill→float32; drop_duplicates(trade_date,
   keep="last"); _write_feature_series slices the full-calendar array to the close bin's
   [start_index, start_index+len) window (the in-place script mirrors this slicing exactly).
   Any edge case (start_index>0, delisted names, symbols listed pre-2008 calendar start,
   float32 precision at 3.5e11 股) that breaks alignment or value?
3. The deliberate LEGACY-unit asymmetry (total_share in 股 via ×1e4; float/free in 万股
   verbatim): kept so earn_q_eps levels and size_ln_free_float values don't shift. Is
   preserving inconsistent units the right call vs unifying to 股 (which would uniformly shift
   size_ln_free_float by log(1e4) — rank-invariant but level-visible)? Note the pre-existing,
   unchanged workspace cicc_factor_defs.py EQUITY = "($bps * $total_share * 10000)" assumed
   万股 and therefore carries a uniform 1e4 level error (rank-invariant; evidence unaffected).
4. The ffill-across-suspension choice for all three fields (state variable; §8.1 ranking
   context). float/free previously had NaN on suspension days — this ADDS values there. Any
   consumer for which filled-during-suspension is wrong?
5. BSE NEEQ-era finite→NaN (208K days): we judged the old report-ffill values on days with NO
   daily_basic coverage (not even $total_mv) as spillover artifacts and let the new bin be NaN
   there. Agree, or should a report-anchored bridge fill pre-daily_basic history (mixed
   anchoring)?
6. Governance: the live provider was mutated in place WITHOUT rotating provider_build.json
   (build id depth9_20260630, published 2026-06-30; no formal artifacts were produced between
   the depth9 publish and this fix). Precedent: the quality_stability and report_rc in-place
   additive publishes also did not rotate. But THIS fix REWRITES an approved field's values
   rather than adding new fields. Is non-rotation acceptable here (with the fix recorded in
   project_state + data_tracker + backup retained), or should the manifest carry a new
   provider_build_id / patch marker — and if so, what about the 24 approval YAMLs freshly
   rebound to depth9_20260630 (rebinding again would be pure churn)?
7. field_status.yaml already registers $total_share/$float_share/$free_share under the
   daily_basic dataset (approved) — the fix ALIGNS the bin with its registered semantics, so we
   made NO registry/approval-log change. Agree, or does an anchoring change to an approved
   field's served values warrant an append-only approval-log administrative entry?
8. Evidence reproducibility: registry evidence computed BEFORE the fix that touched
   $total_share (e.g. any screening rows involving earn_q_eps or the qual dilution term) will
   not bit-reproduce against the fixed provider. We did NOT invalidate any evidence (the fix
   corrects data; affected factors are catalog-level, none of the 7 approved factors consume
   $total_share directly — verify this claim against the catalog). Sufficient, or should a
   revalidation note be attached anywhere machine-readable?
9. The unconditional wiring (self-review fix): _materialize_share_capital_daily now runs in
   EVERY materialize_provider call, including scoped --touched-symbols updates (where it loads
   the full ~14M-row share frame to rewrite a handful of symbols, ~15s). Correctness first,
   but flag if you see a cleaner way to keep the unit contract without the unconditional
   full-frame load.

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted and an exact suggested replacement. Map every Blocker to the principle or invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
```
