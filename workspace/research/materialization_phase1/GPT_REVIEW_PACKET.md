ROLE
You are a senior reviewer for an A-share quantitative research system where RESEARCH VALIDITY outranks code that merely runs. A single lookahead, a spent out-of-sample window, or a survivorship-filtered universe invalidates the result even if every test passes. Be skeptical, surface blockers, and do not rubber-stamp.

REPO (public — fetch any file to verify against the live code)
https://github.com/henrydan111/quant-system   (branch: report-rc-registration)
Raw file form: https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/<path>
NOTE: the code diff below is LOCAL/uncommitted (the live link shows the PRE-change function for surrounding-code context). The embedded diff is authoritative.

CONTEXT — read these to judge the change against the contract:
- CLAUDE.md (hard invariants §3, PIT §3.2/§3.3, field-status governance §3.4, research integrity §7)
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/CLAUDE.md
- src/data_infra/pit_backend.py (the materializer being extended — `_materialize_stk_holdertrade`, ~line 2535)
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/src/data_infra/pit_backend.py
- data/data_dictionary.md (stk_holdertrade section, ~line 852)
  https://raw.githubusercontent.com/henrydan111/quant-system/report-rc-registration/data/data_dictionary.md

================================================================================
WHAT CHANGED (authoritative — treat the embedded text as the source of truth)
================================================================================

## Background / motivation
A materialization audit found three datasets with ledger-resident-but-unmaterialized fields:
- **indicators**: 25 `q_*` single-quarter metrics (q_eps, q_netprofit_yoy, q_op_yoy, q_gr_yoy,
  q_dtprofit, q_sales_qoq, q_netprofit_margin, …), 83–89% ledger coverage (= the already-APPROVED,
  already-materialized sibling `q_roe` at 87.7%). They were absent only because the live provider
  predates these columns entering the indicators ledger.
- **stk_holdertrade**: the existing materializer emits all-holder net signals; the user wants
  果仁-style 高管 (董监高) directional rolling signals (高管过去5d/20d 增持股数/金额/次数/比例).
- **report_rc**: 8 analyst consensus levels — DEFERRED (needs rolling-FY1 design + JoinQuant
  validation + its own review; not in this change).

## Change 1 — indicators q_* (NO CODE CHANGE)
`indicators` is a `periodic_snapshot` DatasetSpec with NO field allowlist, and a full build
materializes `_apply_field_filter(payload_numeric_columns(ledger))` with an empty field_filter =
ALL numeric ledger columns. So a plain rebuild of the `indicators` dataset materializes the 25 q_*
with no code change. Verified in sandbox: q_eps_q0 materializes (n=4344, 茅台 last 15.35元), and the
already-materialized `q_roe` re-materializes BYTE-IDENTICAL to the live provider (no regression).

## Change 2 — stk_holdertrade 高管 directional (CODE; the review focus)
Extend `_materialize_stk_holdertrade` to ALSO emit, per (qlib_code, effective_date), 高管
(holder_type=='G') DIRECTIONAL aggregates split by 增持(IN)/减持(DE):
  holdertrade_mgr_in_{vol,amount,events,ratio}  and  holdertrade_mgr_de_{vol,amount,events,ratio}
where vol=Σchange_vol (shares), amount=Σ(change_vol·avg_price) (元), ratio=Σchange_ratio (占流通%),
events=count. Each field is non-NaN ONLY on a day carrying that direction's 高管 event (sparse, same
convention as the existing net/gross fields), so a NaN-skipping window sum is exact:
  高管过去N日增持股数 = Sum($holdertrade_mgr_in_vol, N).
The existing all-holder net_vol/gross_vol/net_ratio/events are UNCHANGED (verified byte-identical
post-rebuild). 大股东(C)/个人(P) splits are intentionally NOT materialized (read the ledger).

### Embedded diff (the aggregation + write block of `_materialize_stk_holdertrade`)
```python
        change_vol = pd.to_numeric(ledger.get("change_vol"), errors="coerce")
        change_ratio = pd.to_numeric(ledger.get("change_ratio"), errors="coerce")
        avg_price = pd.to_numeric(ledger.get("avg_price"), errors="coerce")   # NEW
        in_de = ledger.get("in_de", pd.Series("", index=ledger.index)).astype(str).str.upper()
        holder_type = ledger.get("holder_type", pd.Series("", index=ledger.index)).astype(str).str.upper()  # NEW
        sign = np.where(in_de == "DE", -1.0, 1.0)
        ledger["_signed_vol"] = change_vol * sign
        ledger["_abs_vol"] = change_vol.abs()
        ledger["_signed_ratio"] = change_ratio * sign
        ledger["_event_count"] = 1
        ledger["_amount"] = change_vol * avg_price   # NEW: transaction value 元; NaN where avg_price absent (~29%)

        agg = (  # UNCHANGED all-holder net/gross/net_ratio/events
            ledger.groupby(["qlib_code", "effective_date"], sort=False)
            .agg(
                holdertrade_net_vol=("_signed_vol", "sum"),
                holdertrade_gross_vol=("_abs_vol", "sum"),
                holdertrade_net_ratio=("_signed_ratio", "sum"),
                holdertrade_events=("_event_count", "sum"),
            ).reset_index()
        )

        # NEW: 高管(G) directional per-day aggregates (sparse: non-NaN only on a day with that
        # direction's 高管 event, so Sum(...,N) is the exact 果仁 rolling signal).
        def _dir_agg(mask: np.ndarray, prefix: str) -> tuple[pd.DataFrame, list[str]]:
            sub = ledger[mask]
            fmap = {f"{prefix}_vol": "change_vol", f"{prefix}_amount": "_amount",
                    f"{prefix}_ratio": "change_ratio", f"{prefix}_events": "_event_count"}
            if sub.empty:
                return pd.DataFrame(columns=["qlib_code", "effective_date", *fmap]), list(fmap)
            work = sub[["qlib_code", "effective_date", "_amount", "_event_count"]].copy()
            work["change_vol"] = change_vol[mask].values
            work["change_ratio"] = change_ratio[mask].values
            out = (
                work.groupby(["qlib_code", "effective_date"], sort=False)
                .agg(**{out_name: (src, "sum") for out_name, src in fmap.items()})
                .reset_index()
            )
            return out, list(fmap)

        is_mgr = (holder_type == "G").to_numpy()
        is_in = (in_de == "IN").to_numpy()
        is_de = (in_de == "DE").to_numpy()
        mgr_in_agg, mgr_in_fields = _dir_agg(is_mgr & is_in, "holdertrade_mgr_in")
        mgr_de_agg, mgr_de_fields = _dir_agg(is_mgr & is_de, "holdertrade_mgr_de")

        base_fields = ["holdertrade_net_vol", "holdertrade_gross_vol", "holdertrade_net_ratio", "holdertrade_events"]
        all_fields = self._apply_field_filter(base_fields + mgr_in_fields + mgr_de_fields)
        if not all_fields:
            return []

        def _per_symbol(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
            return {code: g.set_index("effective_date") for code, g in frame.groupby("qlib_code")} if not frame.empty else {}

        sym_base = _per_symbol(agg)
        sym_in = _per_symbol(mgr_in_agg)
        sym_de = _per_symbol(mgr_de_agg)
        written: list[str] = []
        for qlib_code, feature_dir in iter_progress(target_dirs.items(), total=len(target_dirs),
                desc="Materialize stk_holdertrade", unit="symbol", leave=False):
            parts = [p.get(qlib_code) for p in (sym_base, sym_in, sym_de)]
            if all(p is None or p.empty for p in parts):
                continue
            merged = pd.concat([p for p in parts if p is not None and not p.empty], axis=1)
            frame = merged.reindex(calendar)
            for field_name in all_fields:
                series = frame[field_name] if field_name in frame.columns else pd.Series(np.nan, index=calendar)
                self._write_feature_series(feature_dir, field_name, series.to_numpy(dtype=np.float32))
                written.append(field_name)
        return sorted(set(written))
```

## PIT / governance posture
- The stk_holdertrade ledger is PIT-anchored on `effective_date` (visibility anchor; the dataset
  carries ann_date + disclosure_date + effective_date). The new fields aggregate per effective_date
  exactly like the existing approved net/gross fields. Predictive use → consumers wrap in Ref(...,1)
  (documented). Sparse-event staleness/decay is the consumer's responsibility (same as net/gross).
- Field-status: the 8 new fields + the 25 q_* will be registered in config/field_registry/
  field_status.yaml (extend the existing approved `stk_holdertrade` and indicators q-field blocks) +
  approval YAML + log + re-bind, AFTER publish. NOT yet flipped to approved (would let a formal run
  reference fields not yet in the live provider).

## EVIDENCE (claims backed by named outputs)
- Correctness (stk_holdertrade): independent re-aggregation of the ledger for 600157_sh 高管-IN
  matches the materialized bins EXACTLY — holdertrade_mgr_in_{vol,ratio,events} n=7 event-days,
  MATCH=True, sums equal (vol 5.548e7, ratio 0.3176, events 88).
  (workspace/scripts/_rung5_field_sweep.py family + the sandbox verify command.)
- No regression: post-rebuild, close (copied) + q_roe (re-materialized) + holdertrade_net_vol
  (re-materialized) are BYTE-IDENTICAL staged-vs-live for 000002_sz / 600519_sh. Full build: 0
  validation warnings.
- Coverage: q_eps_q0/q_netprofit_yoy_q0/q_dtprofit_q0 = 3779–4344 non-NaN across 5 stocks;
  holdertrade_mgr_in_vol sparse + plausible (000404=37, 002456=25, 600157=7, 茅台=0).

## SELF-IDENTIFIED CONCERN (want your read)
`amount = Σ(change_vol·avg_price)` with `.agg("sum")` (pandas default min_count=0): on a 高管-IN day
where EVERY event lacks avg_price (~29% of events are unpriced), the amount group is all-NaN and
pandas sum returns 0.0, NOT NaN — so `mgr_in_amount = 0` on a day that DID have an increase
(`mgr_in_vol > 0`). For a window Sum this silently understates 增持金额. Should the amount agg use
`min_count=1` so an all-unpriced day → NaN (skipped by the rolling sum) rather than a misleading 0?
(vol/ratio/events are unaffected — their source columns are always present on an event row.)

================================================================================
QUANTITATIVE-RESEARCH PRINCIPLES — check the change against EACH; a violation is a Blocker
================================================================================
1. PIT / NO-LOOKAHEAD (cardinal). effective_date anchor; Ref(...,1) for predictive use. Does any
   value at t use info not knowable at t? (note the materializer aggregates per effective_date and
   reindexes to the calendar — confirm no forward leakage.)
2. OUT-OF-SAMPLE sealed — n/a (data-infra materialization, no OOS spend).
3. SURVIVORSHIP — materializes for all ledger codes (incl. delisted); confirm no currently-listed filter.
4. FACTOR-EVAL — n/a (no factor promotion here; raw fields).
5. EXECUTION & COST — n/a.
6. NO LEVERAGE — n/a.
7. NO HEDGE WORDS — every claim above is backed by a named output; flag any that isn't.
8. FOUR-LAYER — these are Layer-1 raw fields; confirm nothing encodes tradability/universe.
9. MULTIPLE TESTING — n/a (no selection).

REVIEW QUESTIONS
1. Correctness — `_dir_agg`'s `change_vol[mask].values` / `change_ratio[mask].values` positional
   assignment onto `sub = ledger[mask]` (same boolean mask) — is the row alignment guaranteed? Any
   index/order trap? The min_count=0 amount issue above. NaN/sign propagation. The pd.concat(axis=1)
   + reindex(calendar) merge of base/in/de per-symbol frames — column-collision or mis-align risk?
2. Governance — does registering 25 q_* (same PIT path as approved q_roe) + 8 高管 fields honor §3.4
   field-status governance and §3.2/§3.3 PIT? Is the "register only AFTER publish" sequencing right?
3. Design — is the 高管-only (G) directional choice + sparse-NaN + window-sum convention sound? Is
   deferring report_rc consensus (rolling-FY1 + JoinQuant validation) the right call vs forcing it now?
4. Evidence — what proof is missing before publish; the exact test/command you'd run.

OUTPUT FORMAT
- Issues ranked Blocker / Major / Minor, each with the offending line quoted + an exact suggested
  replacement. Map every Blocker to the principle/invariant it violates.
- Final line: SHIP / REVISE / REWORK, plus the single most important residual risk.
