# Phase 6 Cross-Review Request (for GPT)

You are adversarially reviewing **Phase 6** of an A-share factor-lifecycle formalization effort:
the first operational run of the `factor_lifecycle` orchestrator profile, which promoted
**72 of 147 base catalog factors from `draft` → `candidate`** on the live factor registry,
plus **two bug fixes** that this operational run surfaced in already-merged code.

You have **no repo access** — all code/evidence needed is embedded below. Be skeptical.
Your job is to find: residual bugs, incomplete fixes, OOS/PIT leakage, mis-stated
guarantees, and unsound decisions. A NO-GO with specific findings is more useful than a GO.

---

## 0. Background you need

- The `factor_lifecycle` profile is an **IS-only** `draft→candidate` gate. It computes each
  factor's cross-sectional rank IC over an in-sample window (2014-01-01 … 2020-12-31),
  derives a heldout/yearly-sign-consistency stat, and promotes factors that clear
  `|rank_icir| ≥ 0.10 ∧ yearly_sign_consistency ≥ 0.70`. It has **no OOS leg** by design
  (no `oos_test` stage, no backtest, no holdout-seal claim). `candidate → approved` is a
  SEPARATE governed OOS/promotion gate (P1.1, not exercised here).
- `candidate` is an **additive registry tier**: `get_factor_catalog()` (the code-defined
  catalog) stays authoritative for ALL discovery/sandbox research — its 42 call sites ignore
  registry status. Registry status gates ONLY formal `hypothesis_validation` components, and
  `candidate` can never auto-become `approved`.
- The forward-return label used by the IS gate is FUTURE-looking
  (`fut/cur - 1` where `fut` = adjusted close `horizon=20` trading days later). The whole
  Phase-4 design exists to guarantee the label-realization date never crosses `is_end`
  (2020-12-31) — i.e. no lookahead.

---

## 1. BUG FIX #1 — Phase-4 MultiIndex level-order (leakage-adjacent correctness)

### Symptom
The first real run aborted with `IsEndLeakageError: IsWindowedPanel: empty factor panel /
label`. The 114-factor panel (5.4M rows) and the adj-close panel both built fine, but the
forward-return label came out **entirely NaN** → empty panel → the belt-3 guard fired.

### Root cause (proven on real data)
`compute_factors` returns a panel indexed `MultiIndex(datetime, instrument)`. The builder
constructed the future-price lookup index hardcoded as `(instrument, datetime)`. pandas
`reindex` matches MultiIndex levels **positionally**, so instrument-values were compared
against datetime-values → every future price NaN → all-NaN label.

Proof (real adj_close, isolated): with the OLD construction `fut non-NaN = 0/20`; with the
fixed construction `fut non-NaN = 16/20` (the 4 dropped = last 2 dates × 2 stocks whose
`r(t)` is out of range — exactly correct). Every Phase-4 unit-test fixture was built in
`(instrument, datetime)` order, so this integration point was never exercised — the builder
had **never** run against real `compute_factors` output.

### The fix (`src/alpha_research/factor_lifecycle/walk_forward_validation.py`)
```python
    insts = factor_panel.index.get_level_values("instrument")
    dts = factor_panel.index.get_level_values("datetime")
    r_for_rows = pd.DatetimeIndex([real_map.get(d, pd.NaT) for d in dts])

    # The future-price lookup reindexes adj POSITIONALLY by MultiIndex level, so
    # future_index MUST carry the SAME level order as the factor panel, and adj MUST
    # share it too. compute_factors returns (datetime, instrument); a hardcoded
    # (instrument, datetime) future index silently matches NOTHING -> all-NaN label.
    names = list(factor_panel.index.names)
    if set(names) != {"instrument", "datetime"}:
        raise IsEndLeakageError(
            f"build_is_windowed_panel expects an (instrument, datetime) MultiIndex; got names={names}"
        )
    if list(adj.index.names) != names:
        adj = adj.reorder_levels(names).sort_index()
    _future_levels = {"datetime": r_for_rows, "instrument": insts}
    future_index = pd.MultiIndex.from_arrays(
        [_future_levels[name] for name in names], names=names,
    )

    cur = adj.reindex(factor_panel.index)
    fut = adj.reindex(future_index)  # adj at the EXACT calendar r(t); missing -> NaN
    # Defensive guard: if current prices matched but EVERY future price is NaN, the reindex
    # aligned on the wrong levels (a MultiIndex-order regression) rather than hitting a
    # legitimately empty window -> fail loud with a diagnosable message.
    if bool(cur.notna().any()) and not bool(fut.notna().any()):
        raise IsEndLeakageError(
            "build_is_windowed_panel: future-price reindex matched zero rows while current "
            f"prices matched (factor names={names}, adj names={list(adj.index.names)}) — "
            "MultiIndex level-order mismatch, not an empty window."
        )
    label_vals = fut.to_numpy() / cur.to_numpy() - 1.0
    label = pd.Series(label_vals, index=factor_panel.index, name="label").dropna()
    aligned = factor_panel.loc[label.index]
```
The `real_map` (computed just above this block, unchanged) maps each factor date `t` to the
EXACT trading-calendar target `r(t) = open_days[pos(t)+horizon]` (a missing `r(t)` row drops,
never substitutes a later row); both `factor_panel` and `adj_close` are asserted `≤ is_end`
before this block (belt 0); and `IsWindowedPanel.__post_init__` re-asserts both
`max_factor_date ≤ is_end` and `max_label_realization_date ≤ is_end` (belt 3).

### Regression test
`test_build_is_multiindex_level_order_invariant` builds the same fixture in BOTH
`(datetime,instrument)` and `(instrument,datetime)` order and asserts identical, correct
labels (with a concrete forward-return check). Fails on pre-fix code (empty → `IsEndLeakageError`).

### On real data after the fix
`Panel built: factor_panel shape=(4889095, 114), max_factor_date=2020-12-03,
max_label_realization=2020-12-31` (== is_end, never past). The IS ICIR values reproduce the
prior independent catalog-revalidation CSV (e.g. `rev_max_return_20d` −0.717 vs −0.709;
`risk_vol_20d` −0.502 vs −0.500).

### Questions for you
- Is the fix correct AND complete? Any *other* positional-MultiIndex assumption in the same
  module? (I checked: all other `get_level_values` calls are name-based; `factor_ic` routes
  through `factor_eval.compute_ic_series` which normalizes either order. Verify my claim.)
- Does the level-order bug have any way to have produced a *wrong-but-nonempty* label
  (silent corruption) rather than the all-NaN it actually produced? I argue no (positional
  mismatch on disjoint value-spaces → all NaN), but challenge it.

---

## 2. BUG FIX #2 — Phase-5 publish resume-safety

### The DAG (10 steps; gate pauses split the run across processes)
```
1 data_scope  2 data_readiness  3 object_resolver  4 dataset_build
5 walk_forward  6 gate_evaluation  7 gate_concern_scoring [pause_for_input]
8 gate_review [pause_for_gate]  9 registry_publish  10 report_render
```
Process 1 runs steps 1→7, pauses at 7. Operator writes concern scores; resume runs 7→8,
pauses at 8. Operator writes the gate decision; resume runs 8→10.

### Root cause
`registry_publish` (step 9) read the walk-forward verdicts from the **in-memory**
`context.state["factor_lifecycle"]["walk_forward_rows"]` dict (set by step 5). But on resume,
state is rebuilt by `reconstruct_state_from_completed_steps`, which restores ONLY:
```python
reconstructed = {"step_outputs": {}, "resumed_inputs": {}, "registry_resolution": {...},
                 "base_metadata": {}, "produced_objects": [], "registry_payloads": {}}
# ... populated from each completed step's persisted step_outputs.json
```
The custom `"factor_lifecycle"` key is NOT restored. So in process 3 (resume past the gate),
`context.state["factor_lifecycle"]` is `{}` → publish read `walk_forward_rows = []` →
`candidate_verdicts = []` → it would have promoted **NOTHING even on an `approved` decision**.
(All Phase-5 unit tests invoked the handler in-process with the in-memory dict pre-populated,
so they never exercised the cross-process resume path.)

### The fix (`src/research_orchestrator/factor_lifecycle_steps.py`)
walk_forward step 5 already PERSISTS its verdicts to `step_outputs.json`:
`{"factor_verdicts": [...], "evidence_kind": "...", ...}` — and `step_outputs` IS restored on
resume. So publish now reads from there:
```python
    decision = _read_gate_decision(context)
    # RESUME-SAFETY: gate pauses split the run across processes;
    # reconstruct_state_from_completed_steps restores ONLY step_outputs on resume — the
    # in-memory context.state["factor_lifecycle"] dict does NOT survive. Read verdicts from
    # the PERSISTED walk_forward step_outputs, falling back to in-memory only for the
    # single-process / no-pause path (tests + back-compat).
    wf_out = dict(context.state.get("step_outputs", {}).get("factor_lifecycle_walk_forward", {}))
    lifecycle_state = context.state.get("factor_lifecycle", {})
    if "factor_verdicts" in wf_out:
        verdicts = list(wf_out.get("factor_verdicts", []))
        evidence_kind = str(wf_out.get("evidence_kind", ""))
    else:
        verdicts = list(lifecycle_state.get("walk_forward_rows", []))
        evidence_kind = str(lifecycle_state.get("evidence_kind", ""))
    candidate_verdicts = [v for v in verdicts if v.get("status") == "candidate"]
```

### Regression test
`test_publish_reads_verdicts_from_persisted_step_outputs_on_resume`: pops the in-memory
`factor_lifecycle` dict, puts verdicts only in `step_outputs["factor_lifecycle_walk_forward"]`
(the resume shape), asserts publish promotes the candidate-verdict factors. Fails on pre-fix.

### Verified on the real run
The live 72-run paused at gate_concern_scoring, resumed (concern scores), paused at
gate_review, resumed (`approved`) → published 72. The publish ran in process 3 (post-gate
resume) and promoted all 72 — direct proof the fix works in a real cross-process run.

### Honest residual limitation I want you to weigh
The **panel** (a non-serializable object) is passed from `dataset_build` (4) →
`walk_forward` (5) via the in-memory `context.state["factor_lifecycle"]["panel"]`. Those two
steps are CONSECUTIVE with NO gate between them, so in normal operation they always run in
the same process pass (1→7). A crash/kill *between* 4 and 5 would, on resume, find step 4
"completed" (skipped, panel not recreated) and step 5 would raise
`ValueError("no panel from dataset_build")` — i.e. it **fails loudly / fail-closed**, never
silently promotes wrong; recovery is a restart. My fix targets the publish-across-gate-pause
case (the operational one). **Is fail-loud-on-crash-between-4-and-5 acceptable, or should the
panel handoff also be made resume-safe (e.g. persist a panel cache)?**

### Questions for you
- Are there OTHER cross-process state dependencies in the factor_lifecycle DAG I missed?
  My audit: resolver→dataset_build reads PERSISTED `step_outputs` (safe); gate_concern_scoring
  / gate_review read PERSISTED `step_outputs` from gate_evaluation (safe); dataset_build→
  walk_forward uses in-memory panel but is same-process (see residual above). Verify.
- Does reading verdicts from `step_outputs` vs in-memory change any value? The persisted
  `factor_verdicts` are `[dict(r) for r in result.rows]` — the same dicts the in-memory path
  held. I claim byte-identical. Challenge it.

---

## 3. The operational run — promotion correctness

### Pipeline & counts
147 base catalog factors → **114 field-eligible** (33 auto-excluded: their Qlib `$field`s are
in `quarantine`/`pending_review` datasets — `alpha_*`/`flow_*`/`margin_*`/`north_*`) →
**85 IS-candidates** (cleared `|rank_icir|≥0.10 ∧ sign_consistency≥0.70`) → **72 promoted**.

The **13 excluded** from the 85 are those whose INDEPENDENT full-window (2014–2026) evidence
(the pre-existing catalog-revalidation CSV, imported in Phase 2) shows OOS collapse/flip
(`status != candidate`): `grow_profit_trend, grow_roe_yoy, grow_eps_yoy, grow_opprofit_qoq,
grow_opprofit_yoy, earn_earnings_momentum, grow_profit_acceleration, grow_netprofit_yoy,
qual_asset_turnover, grow_consistency, qual_margin_trend, grow_peg, tech_kurt_20d` (8 are the
earnings-LEVEL factors already flagged IS-overfit). The user explicitly chose
"promote 72 OOS-stable only" over "promote all 85".

### Live registry state after the run (verified)
- 72 `candidate` + 99 `draft` (171 current).
- 72 formal lifecycle evidence rows: all `formal_evidence_eligible=True`, all
  `oos_rank_icir`=NA (no OOS field written), all `source_hash` nonblank (definition-bound).
- No `approved` status anywhere. The 13 collapsers + 33 field-ineligible stayed `draft`.

### The 1-factor benign sync (pre-condition)
`rev_up_down_ratio_20d` had a definition drift: catalog refactored `Count(X>0,20)/20` → the
equivalent `Sum(If(X>0,1,0),20)/20` (same factor, different string → different hash). The
resolver's P1.3 definition-binding gate would hard-fail on it. Cleared via
`sync_catalog_to_registry` (re-versioned to v3, hash now matches catalog). Dry-run confirmed
this touched exactly 1 of 171 rows.

### THE OOS-DISCIPLINE QUESTION I most want you to probe
By excluding the 13 collapsers from the gate's INPUT batch, I used OOS knowledge (the
full-window CSV) to curate what the IS-only gate sees. Two sub-questions:

(a) **Does this contaminate the IS-only gate?** My position: NO — the gate still computes
ONLY IS metrics and sees no OOS data; the 72's evidence rows are IS-only (`oos_rank_icir`=NA).
The exclusion is input curation using SEPARATELY-obtained OOS evidence, not feeding OOS into
the gate. But the SELECTION of which factors become `candidate` now depends on OOS knowledge —
is labeling them `candidate` (a tier a naive reader might read as "IS-only-validated")
misleading? Or is conservative pre-filtering (don't re-spend on factors already known dead)
the right call?

(b) **Is any future OOS burned?** The 72's 2021–2026 window was ALREADY observed in the
pre-Phase-2 catalog-revalidation CSV (full-window 2014–2026). Phase 6 introduced NO new OOS
observation. BUT: a future `candidate→approved` promotion for these 72 must use a
GENUINELY-SEALED window — **2021–2026 is already burned for them**. I claim this is a
pre-existing fact (not a Phase-6 defect) and a forward note for the promotion path. Agree?
Is there a cleaner way to have run the IS-only gate that doesn't entangle the candidate tier
with prior OOS knowledge at all (e.g. promote all 85 and let the separate gate cull)?

---

## 4. Scope, tests, provenance

- Commit `38ba203` on branch `factor-lifecycle-p6` (PR #35 → `wave1-field-promotion`):
  2 src fixes + 2 regression tests + 4 reproducible Phase-6 scripts + docs
  (project_state.md + CLAUDE.md §3 + AGENTS.md §2a).
- Safety arc: compute-only dry-run (IS ICIR cross-checked vs prior CSV) → 3-factor
  temp-registry orchestrator validation (full DAG incl. gates + publish) → live sync → live
  72-run through the human gate.
- Tests: factor_lifecycle + registry suite 81 passed; architecture/boundary 9 passed.
- Hypothesis ceremony: the profile is formal-only → requires a Hypothesis. `factor_lifecycle`
  is NOT in `SUCCESS_CRITERIA_FLOORS`, so floor-rails validation is a no-op; I set ONLY
  `success_criteria.min_rank_icir=0.10` (other fields None → no null hard rules → automated
  verdict honestly "accepted"); 4 pre-registered concerns keyed to `min_rank_icir` with the
  exact measured `rank_icir` anchor, `confirmed=false`/`severity=low` (honest: the gated batch
  is the OOS-stable subset, so the "IS-stable factor collapses OOS" concern is not realized).

### Final questions
- Did the live orchestrator run have any unintended side-effect I under-disclosed? Known
  writes: `data/factor_registry/` (72 candidate + evidence), `data/hypothesis_registry/`
  (the run's hypothesis registered at gate_review), `data/testing_ledger/` (walk_forward +
  gate measurement/verdict events). All gitignored local state. Anything else you'd check?
- Is setting only `min_rank_icir` (others None) to get an honest "accepted" automated verdict
  a sound pattern for an IS-only gate, or does dropping the other rules hide a real check?
- Overall: GO to merge PR #35, or NO-GO with specific findings?
