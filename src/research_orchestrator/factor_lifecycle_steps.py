"""Factor-lifecycle profile step handlers (Phase 5).

The ``factor_lifecycle`` profile gates DRAFT factors into ``candidate`` using the IS-only
walk-forward validator. These are the lifecycle-specific step handlers (registered in
``steps.HANDLER_REGISTRY``):

  - ``factor_lifecycle_object_resolver``  — draft-ACCEPTING resolver + P1.3 definition-
    binding + PER-FACTOR field eligibility (slice 2)
  - ``factor_lifecycle_dataset_build``    — IS-only panel; excludes field-ineligible (slice 3)
  - ``factor_lifecycle_walk_forward``     — run_is_walk_forward + testing-ledger (slice 4)
  - ``factor_lifecycle_registry_publish`` — direct decision matrix; evidence-then-
    set_status(candidate) (slice 6)

They REUSE the formal gates unchanged (P1.3 ``_assert_no_definition_drift``, the field
registry, the gate triplet); only the lifecycle-status allow-set widens to include
``draft`` (the gate INPUT is draft factors). NO OOS leg — the profile is IS-only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.research_orchestrator.dag import StepExecutionContext, StepExecutionResult
from src.research_orchestrator.runtime import write_json
# Top-level so tests can monkeypatch `factor_lifecycle_steps.load_is_windowed_panel`
# (no import cycle: walk_forward_validation does not import research_orchestrator).
from src.alpha_research.factor_lifecycle.walk_forward_validation import (
    load_is_windowed_panel,
    load_is_windowed_panel_with_layer2,
    run_is_walk_forward,
)

# The lifecycle resolver allow-set: the gate INPUT is draft factors, so `draft` is
# ACCEPTED (unlike validation_object_resolver's {formal} set). stale / deprecated / plain
# candidate-registry / new are rejected.
LIFECYCLE_ALLOWED_LAYERS = frozenset(
    {"formal", "factor_registry_candidate", "factor_registry_draft"}
)


def _field_check_expressions(name: str) -> list[str] | None:
    """The Qlib expression(s) whose ``$field`` tokens determine ``name``'s field
    eligibility. base -> [catalog expr]; industry_relative -> [base expr]; composite ->
    [each component's base expr]; unknown / unresolvable -> ``None`` (fail-closed)."""
    from src.alpha_research.factor_library.catalog import (
        get_composite_defs,
        get_factor_catalog,
        get_industry_relative_defs,
    )

    catalog = get_factor_catalog(include_new_data=True)
    industry = {str(d["name"]): d for d in get_industry_relative_defs()}
    composites = {str(d["name"]): d for d in get_composite_defs()}
    if name in industry:
        d = industry[name]
        base = str(d.get("base", ""))
        if base not in catalog:
            return None
        exprs = [catalog[base]]
        # GPT Phase-7: a size_industry_neutralize def really consumes market cap
        # (Ref($total_mv, 1)) — the field gate must SEE that dependency, not only the base.
        if d.get("requires_market_cap"):
            exprs.append("Ref($total_mv, 1)")
        return exprs
    if name in catalog:
        return [catalog[name]]
    if name in composites:
        exprs: list[str] = []
        for comp in composites[name].get("components", []):
            c = str(comp)
            if c not in catalog:
                return None
            exprs.append(catalog[c])
        return exprs or None
    return None


def per_factor_field_eligible(factor_names: list[str], *, stage: str = "formal_validation") -> dict[str, bool]:
    """PER-FACTOR field eligibility (NOT batch-raise; GPT/Codex caution #2): a factor is
    eligible iff ALL of its field-check expressions clear the field-status gate at
    ``stage``. Fail-closed: unknown / unresolvable -> ``False``."""
    from src.research_orchestrator.release_gate import evaluate_field_dependencies

    out: dict[str, bool] = {}
    for name in factor_names:
        exprs = _field_check_expressions(name)
        if not exprs:
            out[name] = False
            continue
        out[name] = bool(evaluate_field_dependencies(expressions=exprs, stage=stage).eligible)
    return out


def handle_factor_lifecycle_object_resolver(context: StepExecutionContext) -> StepExecutionResult:
    """Phase 5 slice 2: resolve the factor batch (``request.consumes``) against the factor
    registry with a DRAFT-ACCEPTING allow-set, run the P1.3 definition-binding gate, and
    compute PER-FACTOR field eligibility (consumed by the dataset_build to EXCLUDE
    ineligible factors). Does NOT weaken P1.3 or the field gate — only widens the
    lifecycle-status allow-set to include ``draft``."""
    from src.research_orchestrator.resolver import ResolverHub
    from src.research_orchestrator.validation_steps import _assert_no_definition_drift

    consumes = list(context.request.consumes)
    if not consumes:
        raise ValueError(
            "factor_lifecycle_object_resolver requires request.consumes (the factor batch to gate)"
        )
    factor_names = [str(a.object_name) for a in consumes]

    rd = context.registry_dirs
    hub = ResolverHub(
        factor_registry_dir=rd["factor_registry_dir"],
        candidate_registry_dir=rd["candidate_registry_dir"],
        signal_registry_dir=rd["signal_registry_dir"],
        model_registry_dir=rd["model_registry_dir"],
        strategy_registry_dir=rd["strategy_registry_dir"],
    )
    raw_resolution = hub.resolve_assets(
        consumes=consumes,
        mode="formal",
        allowed_new_object_types=set(),  # the lifecycle gate never creates new factors
        research_profile=context.profile.profile_id,
    )

    rejected: list[dict[str, Any]] = []
    for entry in raw_resolution["resolved_objects"]:
        layer = str(entry.get("source_layer") or "")
        requested_name = entry.get("requested", {}).get("object_name", "")
        if entry.get("status") == "unresolved":
            rejected.append({"factor_name": requested_name, "reason": "unresolved"})
        elif layer not in LIFECYCLE_ALLOWED_LAYERS:
            rejected.append({
                "factor_name": requested_name,
                "reason": f"non-allowed source_layer={layer!r} (allowed={sorted(LIFECYCLE_ALLOWED_LAYERS)})",
            })
    if rejected:
        names = ", ".join(r["factor_name"] or "(unnamed)" for r in rejected)
        raise ValueError(
            "factor_lifecycle_object_resolver: cannot gate these factors via the lifecycle "
            f"allow-set: {names}. Accepts formal / factor_registry_candidate / "
            "factor_registry_draft; rejects stale / deprecated / candidate-registry / new."
        )

    # P1.3 definition-binding (reused VERBATIM — drift still hard-fails before any compute).
    label = str(
        getattr(getattr(context.request, "hypothesis", None), "hypothesis_id", "")
        or context.profile.profile_id
    )
    definition_binding_report = _assert_no_definition_drift(hub, raw_resolution, artifact_label=label)

    # Per-factor field eligibility for the dataset_build to exclude ineligible factors.
    field_eligible = per_factor_field_eligible(factor_names, stage="formal_validation")

    outputs = {
        "registry_resolution": raw_resolution,
        "consumes": [a.to_dict() for a in consumes],
        "definition_binding_report": definition_binding_report,
        "field_eligible": field_eligible,
        "field_ineligible_factors": sorted(n for n, ok in field_eligible.items() if not ok),
    }
    write_json(context.step_dir / "registry_resolution.json", outputs)
    return StepExecutionResult(status="completed", outputs=outputs)


def _lifecycle_time_split(request: Any):
    """The IS/OOS window for a lifecycle run — from ``request.inputs['time_split']`` (a
    TimeSplit dict) or ``hypothesis.time_split``. Required (no default)."""
    from src.alpha_research.walk_forward import TimeSplit

    inputs = getattr(request, "inputs", {}) or {}
    ts = inputs.get("time_split")
    if isinstance(ts, dict):
        return TimeSplit.from_dict(ts)
    hyp = getattr(request, "hypothesis", None)
    if hyp is not None and getattr(hyp, "time_split", None) is not None:
        return hyp.time_split
    raise ValueError(
        "factor_lifecycle requires a time_split (request.inputs['time_split'] or hypothesis.time_split)"
    )


def handle_factor_lifecycle_dataset_build(context: StepExecutionContext) -> StepExecutionResult:
    """Phase 5 slice 3: build the IS-only windowed panel for the GATE input. Field-
    ineligible factors (from the resolver's per-factor `field_eligible`) are EXCLUDED from
    compute (marked `draft`, recorded) — a disallowed `$field` never reaches
    ``load_is_windowed_panel``. The panel is IS-only (structurally `is_end`-bounded by the
    Phase-4 builder); the profile has no OOS stage. The IsWindowedPanel (non-serializable)
    is passed to the walk-forward step via ``context.state``; only a summary is written.

    Scope note: base factors are gated directly; composite / industry-relative factors in
    the batch are recorded as `non_base_deferred` (their Layer-2 compute via
    ``add_composites`` is a documented follow-up — the base-factor gate is the
    leakage-critical core)."""
    resolver_out = context.state.get("step_outputs", {}).get("factor_lifecycle_object_resolver", {})
    field_eligible = dict(resolver_out.get("field_eligible", {}))
    if not field_eligible:
        raise ValueError(
            "factor_lifecycle_dataset_build: missing field_eligible from the resolver step"
        )
    eligible = sorted(n for n, ok in field_eligible.items() if ok)
    excluded = sorted(n for n, ok in field_eligible.items() if not ok)

    time_split = _lifecycle_time_split(context.request)
    inputs = getattr(context.request, "inputs", {}) or {}
    horizon = int(inputs.get("horizon", 20))
    qlib_dir = inputs.get("qlib_dir")

    from src.alpha_research.factor_library.catalog import (
        get_composite_defs,
        get_factor_catalog,
        get_industry_relative_defs,
    )

    full = get_factor_catalog(include_new_data=True)
    composite_defs_all = {str(d["name"]): d for d in get_composite_defs()}
    industry_defs_all = {str(d["name"]): d for d in get_industry_relative_defs()}

    # Phase 7: gate BASE + composite + industry-relative (no `non_base_deferred` bucket).
    gated_base = sorted(n for n in eligible if n in full)
    gated_composite = sorted(n for n in eligible if n in composite_defs_all)
    gated_industry = sorted(n for n in eligible if n in industry_defs_all)
    unknown = sorted(
        n for n in eligible
        if n not in full and n not in composite_defs_all and n not in industry_defs_all
    )
    if unknown:
        raise ValueError(
            "factor_lifecycle_dataset_build: eligible factors not in catalog / composite / "
            f"industry-relative defs: {unknown}"
        )
    if not (gated_base or gated_composite or gated_industry):
        raise ValueError(
            "factor_lifecycle_dataset_build: no eligible factors to gate "
            f"(excluded {len(excluded)} field-ineligible)"
        )

    # Unified IS-only panel: base + Layer-2 composite/industry-relative columns, one label,
    # one set of is_end belts. Dependency-only bases (composite components / industry-rel bases
    # not themselves gated) are computed as inputs but EXCLUDED from the verdict columns.
    panel = load_is_windowed_panel_with_layer2(
        gated_base=gated_base,
        gated_composite_defs=[composite_defs_all[n] for n in gated_composite],
        gated_industry_defs=[industry_defs_all[n] for n in gated_industry],
        time_split=time_split, horizon=horizon, qlib_dir=qlib_dir,
    )

    # Pass the (non-serializable) panel + the excluded set to the walk-forward step.
    lifecycle_state = context.state.setdefault("factor_lifecycle", {})
    lifecycle_state["panel"] = panel
    lifecycle_state["excluded_factors"] = excluded
    lifecycle_state["horizon"] = horizon

    outputs = {
        "eligible_count": len(eligible),
        "field_ineligible_count": len(excluded),
        "field_ineligible_factors": excluded,
        "gated_base_factors": gated_base,
        "gated_composite_factors": gated_composite,
        "gated_industry_relative_factors": gated_industry,
        "is_window": {"is_start": time_split.is_start, "is_end": time_split.is_end},
        "horizon": horizon,
        "max_label_realization_date": str(getattr(panel, "max_label_realization_date", "")),
    }
    write_json(context.step_dir / "step_outputs.json", outputs)
    return StepExecutionResult(status="completed", outputs=outputs)


def _record_lifecycle_ledger(context: StepExecutionContext, result: Any, *, excluded: list[str]) -> dict:
    """Record per-factor IS-heldout measurements + ONE batch-effective-trials event to the
    file-locked TestingLedgerStore (the whole pool the selection rule saw = tested +
    field-excluded). Defensive: no testing_ledger_dir -> skip."""
    rd = context.registry_dirs or {}
    ledger_dir = rd.get("testing_ledger_dir")
    if not ledger_dir:
        return {"recorded": 0, "skipped": "no testing_ledger_dir"}
    from src.alpha_research.testing_ledger import TestingLedgerStore

    hyp = getattr(context.request, "hypothesis", None)
    hyp_id = str(getattr(hyp, "hypothesis_id", "") or "factor_lifecycle")
    try:
        design_hash = str(hyp.design_hash()) if hyp is not None else ""
    except Exception:
        design_hash = ""
    run_dir = str(context.run_dir)
    run_id = Path(run_dir).name or "factor_lifecycle_run"
    store = TestingLedgerStore(ledger_dir)
    profile_id = context.profile.profile_id

    recorded = 0
    for row in result.rows:
        store.record_event(
            hypothesis_id=hyp_id, design_hash=design_hash, prose_hash="", structural_family="",
            profile_id=profile_id, run_id=run_id, run_dir=run_dir,
            test_name=f"factor_lifecycle:{row['factor']}", stage="is_only",
            statistic_name="heldout_rank_icir", statistic_value=row.get("heldout_rank_icir"),
            n_obs=row.get("n_heldout_blocks"), notes=str(row.get("reason", "")),
            event_kind="measurement", verdict=str(row.get("status", "")),
        )
        recorded += 1
    # batch effective trials = the whole pool the selection rule saw (tested + field-excluded)
    store.record_event(
        hypothesis_id=hyp_id, design_hash=design_hash, prose_hash="", structural_family="",
        profile_id=profile_id, run_id=run_id, run_dir=run_dir,
        test_name="factor_lifecycle:batch_effective_trials", stage="is_only",
        statistic_name="effective_trials", statistic_value=float(len(result.rows) + len(excluded)),
        n_obs=len(result.rows) + len(excluded), event_kind="measurement",
        notes=f"tested={len(result.rows)} field_excluded={len(excluded)}",
    )
    return {"recorded": recorded + 1}


def handle_factor_lifecycle_walk_forward(context: StepExecutionContext) -> StepExecutionResult:
    """Phase 5 slice 4: run the IS-only walk-forward validator on the dataset_build panel,
    assign per-factor `candidate`/`draft` verdicts, and record per-factor + batch-effective-
    trials events to the file-locked testing ledger. The result carries NO `oos_*` field
    (structurally). `factor_origin` is enum-validated `{generated, a_priori}` and
    fail-closed (a typo / missing value raises, never silently takes a_priori)."""
    lifecycle_state = context.state.setdefault("factor_lifecycle", {})
    panel = lifecycle_state.get("panel")
    if panel is None:
        raise ValueError(
            "factor_lifecycle_walk_forward: no panel from dataset_build "
            "(state['factor_lifecycle']['panel'])"
        )
    time_split = _lifecycle_time_split(context.request)
    inputs = getattr(context.request, "inputs", {}) or {}
    horizon = int(inputs.get("horizon", 20))
    factor_origin = str(inputs.get("factor_origin", "")).strip()
    if factor_origin not in ("generated", "a_priori"):
        raise ValueError(
            "factor_lifecycle_walk_forward requires factor_origin in {generated, a_priori} "
            f"(fail-closed; no silent default), got {factor_origin!r}"
        )

    result = run_is_walk_forward(
        panel=panel, time_split=time_split, horizon=horizon, factor_origin=factor_origin,
    )
    ledger_report = _record_lifecycle_ledger(
        context, result, excluded=list(lifecycle_state.get("excluded_factors", []))
    )
    lifecycle_state["walk_forward_rows"] = [dict(r) for r in result.rows]
    lifecycle_state["evidence_kind"] = result.evidence_kind

    candidate_count = sum(1 for r in result.rows if r.get("status") == "candidate")
    outputs = {
        "evidence_kind": result.evidence_kind,
        "n_heldout_blocks": result.n_heldout_blocks,
        "tested_count": len(result.rows),
        "candidate_count": candidate_count,
        "field_ineligible_count": len(lifecycle_state.get("excluded_factors", [])),
        "factor_verdicts": [dict(r) for r in result.rows],
        "effective_eval_end": str(result.effective_eval_end),
        "ledger": ledger_report,
    }
    write_json(context.step_dir / "step_outputs.json", outputs)
    return StepExecutionResult(status="completed", outputs=outputs)


def _read_gate_decision(context: StepExecutionContext) -> str:
    """The injected gate_review step's decision ("approved"/"rejected"/"quarantined"/"")."""
    gate_outputs = dict(context.state.get("step_outputs", {}).get("gate_review", {}))
    decision = str(gate_outputs.get("decision", "") or "")
    if not decision:
        decision = str(dict(gate_outputs.get("verdict", {})).get("decision", "") or "")
    return decision


def handle_factor_lifecycle_registry_publish(context: StepExecutionContext) -> StepExecutionResult:
    """Phase 5 slice 6: DIRECT decision matrix (must-fix #2 — NOT
    ``_assert_gate_allows_publication``, whose ``quarantined`` -> ``under_review`` has no
    factor-registry status). ONLY a human ``approved`` decision promotes passing factors:
    for each ``candidate``-verdict factor, write a FORMAL lifecycle evidence row FIRST
    (idempotent, definition-bound, ``formal_evidence_eligible=True``) THEN
    ``set_status(candidate)`` (non-privileged; NO git-sha). ``rejected`` / ``quarantined``
    / missing / unknown -> NO status writes. NEVER writes ``approved`` (that stays behind
    the P1.1 promotion gate, unreachable from here)."""
    decision = _read_gate_decision(context)
    # RESUME-SAFETY (real-data finding 2026-06-01): the gate pauses
    # (gate_concern_scoring/gate_review) split the run across processes, and
    # reconstruct_state_from_completed_steps restores ONLY step_outputs on resume — the
    # in-memory context.state["factor_lifecycle"] dict (panel + walk_forward_rows) does NOT
    # survive. Read the verdicts from the PERSISTED walk_forward step_outputs
    # (factor_verdicts + evidence_kind), which ARE restored, falling back to the in-memory
    # state only for the single-process / no-pause path (tests + back-compat).
    wf_out = dict(context.state.get("step_outputs", {}).get("factor_lifecycle_walk_forward", {}))
    lifecycle_state = context.state.get("factor_lifecycle", {})
    if "factor_verdicts" in wf_out:
        verdicts = list(wf_out.get("factor_verdicts", []))
        evidence_kind = str(wf_out.get("evidence_kind", ""))
    else:
        verdicts = list(lifecycle_state.get("walk_forward_rows", []))
        evidence_kind = str(lifecycle_state.get("evidence_kind", ""))
    candidate_verdicts = [v for v in verdicts if v.get("status") == "candidate"]

    if decision != "approved":
        outputs = {
            "decision": decision or "(missing)",
            "promoted_to_candidate": [],
            "published": 0,
            "reason": f"gate decision={decision or '(missing)'!r} != approved -> NO candidate promotions",
        }
        write_json(context.step_dir / "step_outputs.json", outputs)
        return StepExecutionResult(status="completed", outputs=outputs)

    from src.alpha_research.factor_registry import FactorRegistryStore

    rd = context.registry_dirs
    store = FactorRegistryStore(rd["factor_registry_dir"])
    run_id = Path(str(context.run_dir)).name or "factor_lifecycle_run"

    # Evidence FIRST (idempotent), then the non-privileged candidate status change.
    ev_report = store.record_lifecycle_evidence(
        run_id=run_id, verdicts=candidate_verdicts, evidence_class=evidence_kind,
        source_run_dir=str(context.run_dir),
    )
    promoted: list[str] = []
    for v in candidate_verdicts:
        fid = str(v.get("factor", ""))
        if fid and fid in ev_report["attached"]:
            store.set_status(
                factor_id=fid, status="candidate",
                reason=f"factor_lifecycle IS-heldout gate ({evidence_kind})", source_run_id=run_id,
            )
            promoted.append(fid)
    store.save()

    # produced_objects for orchestrator lineage (GPT PR-#34 review): the promoted factors,
    # recorded at lifecycle status `candidate` (never typed-registry `approved` artifacts).
    produced_objects = [
        {"registry": "factor_registry", "object_type": "factor", "object_id": fid, "status": "candidate"}
        for fid in sorted(promoted)
    ]
    outputs = {
        "decision": "approved",
        "evidence_attached": ev_report["attached"],
        "promoted_to_candidate": sorted(promoted),
        "published": len(promoted),
        "skipped_drift": ev_report.get("skipped_drift", []),
        "skipped_unknown": ev_report.get("skipped_unknown", []),
        "produced_objects": produced_objects,
        "registry_payloads": {"factor_registry_publish": {
            "promoted_to_candidate": sorted(promoted),
            "evidence_attached": ev_report["attached"],
            "skipped_drift": ev_report.get("skipped_drift", []),
            "skipped_unknown": ev_report.get("skipped_unknown", []),
        }},
    }
    write_json(context.step_dir / "step_outputs.json", outputs)
    return StepExecutionResult(
        status="completed", outputs=outputs,
        summary={"produced_object_count": len(produced_objects)},
    )
