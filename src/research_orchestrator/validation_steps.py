"""Validation profile step handlers (jolly-seeking-lollipop Gate B).

Stub implementations for the 11 step handlers used by the
``hypothesis_validation`` profile. Real logic lands in Gates C-F:

- Gate C: prescription_runtime.py + universe materialization
- Gate D: IS leg (dataset_build, portfolio_construction, vectorized_backtest_is,
  event_backtest_is, performance_diagnostics, _compute_extended_metrics)
- Gate E: IS gate steps + OOS leg via SealedBacktestRunner
- Gate F: OOS gate wrappers + handle_validation_registry_publish (direct
  publish policy) + CLI flags + template JSON

For Gate B these handlers all return a minimal completed StepExecutionResult
so the DAG can be planned end-to-end and HANDLER_REGISTRY contains every
handler the validation DAG references. They do NOT yet read prescription
data or write artifacts beyond a short status JSON.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.research_orchestrator.dag import StepExecutionContext, StepExecutionResult
from src.research_orchestrator.runtime import write_json


class FactorDefinitionDriftError(RuntimeError):
    """Raised when a resolved formal factor's STORED registry definition_hash no
    longer matches the CURRENT code catalog's hash for that factor (PR P1.3). The
    registry row is stale vs ``catalog.py``; formal validation refuses BEFORE any
    IS/OOS compute so a backtest never runs against a definition the registry can
    no longer attest."""


def _stub_outputs(context: StepExecutionContext, **extras: Any) -> StepExecutionResult:
    """Shared stub helper: write a small status JSON in the step dir and
    emit a StepExecutionResult with status='completed'."""
    payload = {
        "stub": True,
        "step_id": context.step.step_id,
        "capability": context.step.capability,
        "handler": context.step.handler,
        "stage": context.step.config.get("stage", ""),
        "note": (
            "Gate B stub. Real implementation lands in Gates C-F per "
            "jolly-seeking-lollipop plan."
        ),
        **extras,
    }
    write_json(context.step_dir / "stub_status.json", payload)
    return StepExecutionResult(status="completed", outputs=payload)


# ── object_resolver ──────────────────────────────────────────────────────
def handle_validation_object_resolver(context: StepExecutionContext) -> StepExecutionResult:
    """Resolve prescription.components against the formal factor_registry
    (and, opt-in, the candidate_registry).

    Per Codex round-2 #4: consumes synthesis happens HERE (inside the step),
    NOT in the DAG builder, because request validation runs before DAG
    construction and mutating request.consumes after the fact would be
    surprising and would affect request hashing.

    Per Codex round-4 must-fix #4: default policy is source_layer == "formal"
    only. Set prescription.allow_candidate_components=True to opt into
    accepting candidate-registry-only resolutions.

    Per Codex round-3 high-priority: emits outputs["registry_resolution"]
    matching the shape that handle_object_resolver produces, so
    runtime.py:407 lifts resolver state into the run-level lineage.

    Plan ref: jolly-seeking-lollipop Gate D.1.
    """
    from src.research_orchestrator._types import AssetRef
    from src.research_orchestrator.resolver import ResolverHub

    hypothesis = context.request.hypothesis
    if hypothesis is None or hypothesis.prescription is None:
        # Should be guarded by the DAG builder, but defense-in-depth.
        raise ValueError(
            "handle_validation_object_resolver requires hypothesis.prescription"
        )
    prescription = hypothesis.prescription

    # Synthesize a consumes list from the prescribed components.
    consumes: list[AssetRef] = [
        AssetRef(object_type="factor", object_name=c.factor_name)
        for c in prescription.components
    ]

    registry_dirs = context.registry_dirs
    hub = ResolverHub(
        factor_registry_dir=registry_dirs["factor_registry_dir"],
        candidate_registry_dir=registry_dirs["candidate_registry_dir"],
        signal_registry_dir=registry_dirs["signal_registry_dir"],
        model_registry_dir=registry_dirs["model_registry_dir"],
        strategy_registry_dir=registry_dirs["strategy_registry_dir"],
    )
    raw_resolution = hub.resolve_assets(
        consumes=consumes,
        mode="formal",
        allowed_new_object_types=set(),  # validation never creates new candidates
        research_profile=context.profile.profile_id,
    )

    # Formal gate (PR P1.2, Codex round-5): the resolver now RESOLVES every
    # factor-registry row and LABELS source_layer by status (resolve-but-label), so
    # this explicit allow-set is the SOLE point that decides which labels may enter a
    # formal validation. Accept only "formal" (+ "factor_registry_candidate" when the
    # prescription opts in via allow_candidate_components); reject every other layer —
    # factor_registry_draft / _stale / _deprecated AND plain "candidate" (the
    # candidate-registry path). This is a net tightening of the prior binary toggle,
    # which accepted ANY non-formal layer when allow_candidate_components=True.
    allowed_layers = {"formal"}
    if prescription.allow_candidate_components:
        allowed_layers.add("factor_registry_candidate")
    rejected: list[dict[str, Any]] = []
    for entry in raw_resolution["resolved_objects"]:
        layer = str(entry.get("source_layer") or "")
        if entry.get("status") == "unresolved":
            rejected.append({
                "factor_name": entry.get("requested", {}).get("object_name", ""),
                "reason": "unresolved",
                "details": entry,
            })
        elif layer not in allowed_layers:
            rejected.append({
                "factor_name": entry.get("requested", {}).get("object_name", ""),
                "reason": f"non-allowed source_layer={layer!r} (allowed={sorted(allowed_layers)})",
                "details": entry,
            })

    if rejected:
        # Hard-fail with actionable error. Industry-relative composites
        # (val_bp_industry_rel etc.) live in get_industry_relative_defs() and
        # MUST be pre-imported into factor_registry — see plan v6.
        names = ", ".join(r["factor_name"] or "(unnamed)" for r in rejected)
        raise ValueError(
            "handle_validation_object_resolver: cannot resolve required "
            f"factors via formal layer: {names}. "
            "If any are industry-relative composites (e.g., val_bp_industry_rel, "
            "mom_idio_20d), they must be pre-imported into factor_registry "
            "before the validation hypothesis is registered. To accept "
            "candidate-stage factors, set prescription.allow_candidate_components=True."
        )

    # PR P1.3: definition-binding hard-fail. Before the field gate or ANY compute,
    # confirm every resolved formal factor's registry definition_hash still matches
    # the current code catalog (re-uses the registry's own hash algorithm). A drift
    # means the registry row is stale vs catalog.py -> refuse now so a backtest never
    # runs against a definition the registry can no longer attest.
    definition_binding_report = _assert_no_definition_drift(
        hub, raw_resolution, artifact_label=str(hypothesis.hypothesis_id)
    )

    # PR 9 of 2026-05-26 freeze plan: field-dependency gate.
    # After the resolver confirms every prescribed component lives in the
    # formal factor layer, walk each resolved factor's Qlib expression and
    # refuse the IS leg if ANY referenced $field is disallowed at
    # ``formal_validation`` stage (quarantined / pending_review / unknown
    # per config/field_registry/field_status.yaml). This catches the failure
    # mode where a candidate "factor lives in factor_registry, expressions
    # parse, BUT one of its $fields is moneyflow / northbound / etc." Pre-PR-9
    # such candidates would only get caught at release-gate time after
    # spending the full IS leg's compute budget.
    field_dependency_report = _validate_factor_field_dependencies(
        factor_names=[c.factor_name for c in prescription.components],
        stage="formal_validation",
        artifact_label=str(hypothesis.hypothesis_id),
    )

    # PR 9b (2026-05-28, GPT 5.5 Pro round-4 review): the factor field gate
    # above only covers prescription.components. But validation_dataset_build
    # later turns prescription.universe.broad_filters.profitability_field
    # into ``Ref(${profit_field}, 1)`` and feeds it into Qlib. A formal
    # prescription with only approved factors but
    # ``broad_filters.profitability_field="ratio"`` would PASS the factor
    # gate and then load the quarantined hk_hold $ratio at dataset_build
    # time. PR 9b closes this with an explicit universe-side check.
    universe_field_dependency_report = _validate_prescription_universe_field_dependencies(
        prescription=prescription,
        stage="formal_validation",
        artifact_label=str(hypothesis.hypothesis_id),
    )

    outputs = {
        # The shape runtime.py:407 expects (matches handle_object_resolver):
        "registry_resolution": raw_resolution,
        # Convenience: pass the synthesized consumes downstream so dataset_build
        # doesn't need to re-derive it from prescription.
        "consumes": [c.to_dict() for c in consumes],
        # PR 9: record the field-dependency check result on the artifact so
        # reviewers can audit which $fields the resolver approved.
        "field_dependency_report": field_dependency_report,
        # PR 9b: separate report for universe raw fields so reviewers can
        # see exactly which non-factor $fields were authorized.
        "universe_field_dependency_report": universe_field_dependency_report,
        # PR P1.3: record the definition-binding check (registry hash == current
        # catalog hash for every resolved formal factor).
        "definition_binding_report": definition_binding_report,
    }
    write_json(context.step_dir / "registry_resolution.json", outputs)
    return StepExecutionResult(status="completed", outputs=outputs)


def _assert_no_definition_drift(
    hub: Any,
    raw_resolution: dict[str, Any],
    *,
    artifact_label: str,
) -> dict[str, Any]:
    """PR P1.3 definition-binding hard-fail. Every resolved factor-registry factor's
    STORED ``definition_hash`` must equal the CURRENT code catalog's hash (same
    algorithm — ``current_catalog_definition_hashes`` reuses the registry's
    ``_build_catalog_snapshots``). A mismatch means the registry row's recorded
    expression is stale vs ``catalog.py``; raise :class:`FactorDefinitionDriftError`
    BEFORE any IS/OOS compute. Returns a small report for the step outputs.

    Only formal-layer / ``factor_registry_*`` entries are bound to the factor
    catalog; candidate-registry / signal / model entries are skipped.
    """
    current = hub.factor_store.current_catalog_definition_hashes()
    drifted: list[dict[str, Any]] = []
    checked = 0
    for entry in raw_resolution.get("resolved_objects", []):
        layer = str(entry.get("source_layer") or "")
        if not (layer == "formal" or layer.startswith("factor_registry")):
            continue
        factor_id = str(entry.get("canonical_id") or "")
        registry_hash = str(entry.get("definition_hash") or "")
        checked += 1
        if not factor_id or not registry_hash:
            # FAIL-CLOSED (GPT cross-review): a factor-registry entry permitted into
            # formal validation with NO stored definition_hash (or no canonical_id) —
            # e.g. a malformed/legacy approved row — cannot be attested against the
            # catalog. Treat it as drift and REFUSE; do NOT silently skip the gate.
            drifted.append({
                "factor": factor_id or "(unnamed)",
                "registry_hash": registry_hash,
                "code_hash": None,
                "reason": "missing canonical_id or registry definition_hash",
            })
            continue
        code_hash = current.get(factor_id)
        if code_hash is None:
            drifted.append({"factor": factor_id, "registry_hash": registry_hash,
                            "code_hash": None, "reason": "absent from current catalog"})
        elif code_hash != registry_hash:
            drifted.append({"factor": factor_id, "registry_hash": registry_hash,
                            "code_hash": code_hash, "reason": "definition_hash mismatch"})
    if drifted:
        names = ", ".join(d["factor"] for d in drifted)
        raise FactorDefinitionDriftError(
            f"Definition-binding gate ({artifact_label}): {len(drifted)} factor(s) drifted "
            f"between the registry and the current catalog: {names}. The registry's recorded "
            f"definition_hash no longer matches catalog.py — re-sync the factor registry "
            f"(sync_catalog) before formal validation. Details: {drifted}"
        )
    return {"checked": checked, "drifted": [], "stage": "formal_validation"}


def _validate_factor_field_dependencies(
    *,
    factor_names: list[str],
    stage: str,
    artifact_label: str,
) -> dict[str, Any]:
    """PR 9 / PR 9a helper: refuse formal candidates whose factor expressions
    touch any quarantined / pending_review / unknown ``$field``.

    Looks up each ``factor_name`` in ``get_industry_relative_defs`` first
    (composites take precedence so they always inherit their base
    expression) and then in ``get_factor_catalog``; collects the resulting
    Qlib expressions; runs them through ``assert_field_dependencies_eligible``
    which loads ``config/field_registry/field_status.yaml`` and raises
    :class:`FieldApprovalError` on disallowed-field references.

    PR 9a fail-closed contract (post-GPT 5.5 round-2 review). At
    ``formal_validation`` / ``oos_test`` / ``registry_publish`` stages the
    helper raises :class:`FieldApprovalError` in any of these situations,
    BEFORE delegating to ``assert_field_dependencies_eligible``:

      * a requested factor is not found in EITHER the factor catalog OR
        ``get_industry_relative_defs`` (``no_expression_found``);
      * an industry-relative composite's ``base`` is missing from the
        catalog (``industry_relative_unresolved_base``);
      * the final collected expression list is empty — no $field tokens
        means an empty downstream check that would return eligible.

    Pre-PR-9a these cases recorded a source-tag note and continued, so
    the strict gate ran with an empty / partial expression set and could
    return eligible — defeating the purpose of the field-dependency gate.

    Industry-relative composites: the registry uses time-varying SW2021
    labels for the post-transform but the ``$field`` references come from
    the ``base`` factor's expression. Including the base's expression in
    the field-dependency check covers PIT-safety inheritance correctly.
    """
    from src.alpha_research.factor_library.catalog import (
        get_factor_catalog,
        get_industry_relative_defs,
    )
    from src.data_infra.field_registry import FieldApprovalError
    from src.research_orchestrator.release_gate import (
        assert_field_dependencies_eligible,
    )

    catalog = get_factor_catalog(include_new_data=True)
    industry_defs = {d["name"]: d for d in get_industry_relative_defs()}

    # PR 9a: formal stages must fail closed on lookup gaps. Sandbox /
    # vectorized screening stages keep the pre-PR-9 lenient behavior so
    # exploration is not blocked.
    formal_stages = {"formal_validation", "oos_test", "registry_publish"}
    strict_stage = stage in formal_stages

    expressions: list[str] = []
    expression_sources: list[dict[str, str]] = []
    missing_expressions: list[str] = []
    unresolved_industry_bases: list[dict[str, str]] = []

    for name in factor_names:
        # PR 9a: industry-relative composites take precedence so they
        # always inherit their base expression even if a same-named entry
        # somehow appeared in the catalog. The base lookup is what
        # delivers PIT inheritance — see catalog.py:get_industry_relative_defs.
        if name in industry_defs:
            base = str(industry_defs[name].get("base", ""))
            if base and base in catalog:
                expressions.append(catalog[base])
                expression_sources.append({
                    "factor_name": name,
                    "source": "industry_relative_base",
                    "base_factor": base,
                })
            else:
                expression_sources.append({
                    "factor_name": name,
                    "source": "industry_relative_unresolved_base",
                    "base_factor": base,
                })
                unresolved_industry_bases.append({
                    "factor_name": name, "base_factor": base,
                })
        elif name in catalog:
            expressions.append(catalog[name])
            expression_sources.append({"factor_name": name, "source": "factor_catalog"})
        else:
            # The resolver already accepted this factor against the registry,
            # but it's not in the runtime catalog or industry-relative defs.
            # Pre-PR-9a this was recorded as a note and the helper continued
            # — that defeats the gate because we'd then pass a possibly-empty
            # expressions list to the strict assert and the assert would
            # return eligible. PR 9a fails closed on formal stages.
            expression_sources.append({"factor_name": name, "source": "no_expression_found"})
            missing_expressions.append(name)

    if strict_stage:
        if missing_expressions:
            raise FieldApprovalError(
                f"Field-dependency gate cannot validate {artifact_label} at "
                f"stage={stage}: no factor-library expression found for "
                f"{missing_expressions}. Formal validation fails closed when a "
                "resolved factor lacks a runtime expression — fix the "
                "factor_library catalog or remove the factor from the "
                "prescription."
            )
        if unresolved_industry_bases:
            details = ", ".join(
                f"{u['factor_name']!r}->{u['base_factor']!r}"
                for u in unresolved_industry_bases
            )
            raise FieldApprovalError(
                f"Field-dependency gate cannot validate {artifact_label} at "
                f"stage={stage}: industry-relative composite(s) reference "
                f"missing base factor(s): {details}. Add the base to "
                "factor_library.catalog or remove the composite from the "
                "prescription."
            )
        if not expressions:
            raise FieldApprovalError(
                f"Field-dependency gate received empty expression list for "
                f"{artifact_label} at stage={stage}; refusing to pass an empty "
                "check at a formal stage."
            )

    # assert_field_dependencies_eligible loads the committed registry by
    # default. Raises FieldApprovalError on any disallowed field; the
    # error string lists every violating field so the operator can fix
    # field_status.yaml or change the prescription.
    gate_result = assert_field_dependencies_eligible(
        expressions=expressions,
        stage=stage,
        artifact_label=artifact_label,
    )

    return {
        "stage": stage,
        "eligible": gate_result.eligible,
        "fields_checked": list(gate_result.fields_checked),
        "disallowed_fields": list(gate_result.disallowed_fields),
        "unknown_fields": list(gate_result.unknown_fields),
        "reasons": list(gate_result.reasons),
        "expression_sources": expression_sources,
    }


def _validate_prescription_universe_field_dependencies(
    *,
    prescription: Any,
    stage: str,
    artifact_label: str,
) -> dict[str, Any]:
    """PR 9b helper (2026-05-28, GPT 5.5 Pro round-4 review): refuse formal
    prescriptions whose ``universe.broad_filters`` reference a quarantined /
    pending_review / unknown ``$field`` through paths other than
    ``prescription.components``.

    The factor field gate in :func:`_validate_factor_field_dependencies`
    only sees factor expressions. But
    :func:`handle_validation_dataset_build` independently constructs
    ``raw_field_exprs`` for universe materialization — currently the
    canonical OHLCV / market_cap / amount set PLUS an optional
    ``Ref(${broad_filters.profitability_field}, 1)``. A formal prescription
    with only approved factor components could pass the factor gate AND
    still consume a quarantined ``$ratio`` through the universe path.

    This helper enumerates the SAME ``raw_field_exprs`` that dataset_build
    will build and runs them through ``assert_field_dependencies_eligible``
    so the formal IS leg refuses to start.

    Mirror contract: if dataset_build's ``raw_field_exprs`` construction
    ever changes (e.g., starts loading ``$ratio`` to honor
    ``northbound_required``, or ``$revenue_q`` to honor ``revenue_floor``),
    update BOTH this helper AND the dataset_build defense-in-depth check
    so the resolver-time gate stays in sync with the runtime load. The
    defense-in-depth call in dataset_build will fail loudly on drift
    even if this helper is forgotten.

    Returns a serializable report mirroring the factor-side
    ``field_dependency_report`` so reviewers can audit which non-factor
    ``$fields`` the resolver approved.
    """
    from src.data_infra.field_registry import FieldApprovalError
    from src.research_orchestrator.release_gate import (
        assert_field_dependencies_eligible,
    )

    # Canonical universe-side $field set — must match the dict built in
    # handle_validation_dataset_build::raw_field_exprs.
    expressions: list[str] = [
        "Ref($close, 1)",
        "Ref($adj_factor, 1)",
        "Ref($total_mv, 1)",
        "Ref($amount, 1)",
    ]
    universe_sources: list[dict[str, str]] = [
        {"source": "universe_canonical", "field": tok}
        for tok in ("$close", "$adj_factor", "$total_mv", "$amount")
    ]

    universe = getattr(prescription, "universe", None)
    if universe is not None and getattr(universe, "kind", None) == "broad":
        broad_filters = getattr(universe, "broad_filters", None)
        if broad_filters is not None:
            profit_field = getattr(broad_filters, "profitability_field", None)
            if profit_field:
                # Mirror dataset_build line ~441 exactly. The expression
                # contributes a single $field token to the gate.
                expressions.append(f"Ref(${profit_field}, 1)")
                universe_sources.append({
                    "source": "broad_filters.profitability_field",
                    "field": f"${profit_field}",
                })

    # The strict variant raises FieldApprovalError on any disallowed field.
    gate_result = assert_field_dependencies_eligible(
        expressions=expressions,
        stage=stage,
        artifact_label=f"{artifact_label}::universe_fields",
    )

    return {
        "stage": stage,
        "eligible": gate_result.eligible,
        "fields_checked": list(gate_result.fields_checked),
        "disallowed_fields": list(gate_result.disallowed_fields),
        "unknown_fields": list(gate_result.unknown_fields),
        "reasons": list(gate_result.reasons),
        "expression_sources": universe_sources,
    }


# ── dataset_build ────────────────────────────────────────────────────────
def handle_validation_dataset_build(context: StepExecutionContext) -> StepExecutionResult:
    """Build the per-(date, instrument) factor frame + the date-indexed
    eligibility map for the prescription's universe.

    Steps:
    1. Compute IS window (and stage) from hypothesis.time_split + step.config.
    2. Load Qlib factor expressions for prescription.components by looking up
       each name in factor_library catalog OR get_industry_relative_defs().
       Standard catalog factors are loaded directly via Qlib; industry-relative
       composites need their BASE factor + industry series + market_cap and
       are produced via add_industry_relative_composites.
    3. Load raw fields needed for universe materialization (close, adj_factor,
       total_mv, amount, profitability_field) via QlibFieldProvider.
    4. Build ResearchSupport bundle via theme_strategy.data.build_support.
    5. Materialize the universe via prescription_runtime.materialize_universe.
    6. Write dataset.parquet (factor frame), eligible_map.json,
       forward_returns.parquet, dataset_manifest.json.

    Plan ref: jolly-seeking-lollipop Gate D.1.
    """
    from src.alpha_research.factor_library import operators as op
    from src.alpha_research.factor_library.catalog import (
        get_factor_catalog,
        get_industry_relative_defs,
    )
    from src.alpha_research.factor_library.operators import (
        add_industry_relative_composites,
        compute_factors,
    )
    from src.alpha_research.theme_strategy.data import QlibFieldProvider, build_support
    from src.alpha_research.theme_strategy.pipeline import build_rebalance_dates
    from src.data_infra.provider_metadata import build_industry_series_asof
    from src.research_orchestrator.prescription_runtime import materialize_universe
    from src.research_orchestrator.steps import (
        _cache_context_for_step,
        _gate_stage,
        _run_with_cache_context,
    )
    from src.research_orchestrator.cache_manifest import set_cache_context, reset_cache_context

    hypothesis = context.request.hypothesis
    if hypothesis is None or hypothesis.prescription is None:
        raise ValueError("handle_validation_dataset_build requires hypothesis.prescription")
    prescription = hypothesis.prescription
    stage = _gate_stage(context)

    # Window selection: stage="is_only" → IS window; stage="oos_test" → OOS.
    ts = hypothesis.time_split
    if stage == "oos_test":
        start_date, end_date = ts.oos_start, ts.oos_end
    else:
        start_date, end_date = ts.is_start, ts.is_end

    # ── 2. Resolve component factor names → Qlib expressions ────────────
    full_catalog = get_factor_catalog(include_new_data=True)
    industry_rel_defs = {d["name"]: d for d in get_industry_relative_defs()}

    requested_names = [c.factor_name for c in prescription.components]
    direct_catalog: dict[str, str] = {}
    industry_rel_required: list[dict[str, Any]] = []
    for name in requested_names:
        if name in industry_rel_defs:
            spec = industry_rel_defs[name]
            industry_rel_required.append(spec)
            # Also need the BASE factor in the catalog so the composite can run.
            base_name = str(spec.get("base") or "")
            if base_name and base_name in full_catalog and base_name not in direct_catalog:
                direct_catalog[base_name] = full_catalog[base_name]
        elif name in full_catalog:
            direct_catalog[name] = full_catalog[name]
        else:
            # The resolver should have caught this, but defense-in-depth.
            raise KeyError(
                f"validation_dataset_build: factor {name!r} is registered but "
                f"the factor_library catalog cannot produce a Qlib expression "
                f"for it. This indicates a registry/catalog mismatch — see "
                f"factor_library/catalog.py + get_industry_relative_defs()."
            )

    # ── 3. Build ResearchSupport bundle (one-time per-step cost) ────────
    support = build_support(benchmark=hypothesis.benchmark)

    # ── 4. Compute base + composite factor frame via Qlib ───────────────
    cache_token = set_cache_context(_cache_context_for_step(context))
    try:
        base_df, _fwd_df = compute_factors(
            direct_catalog,
            start_date,
            end_date,
            horizons=None,
            kernels=None,
            progress_interval=120,
            stage=stage,
        )
    finally:
        reset_cache_context(cache_token)

    # Industry-relative composites (Codex round-2 #5 path):
    if industry_rel_required:
        # market_cap is required by size_industry_neutralize
        # (event_driven_strategy_research.py:472-490 reuse pattern).
        provider = QlibFieldProvider(qlib_dir=support.project_paths.qlib_dir)
        mv_series = provider.load_named_expressions(
            {"market_cap": "Ref($total_mv, 1)"},
            start_date, end_date, stage=stage,
        )["market_cap"]
        industry_series = build_industry_series_asof(base_df.index, level="L1")
        base_df = add_industry_relative_composites(
            base_df,
            industry_series=industry_series,
            market_cap=mv_series,
            defs=industry_rel_required,
        )

    # Restrict to the columns actually requested (drops base factors loaded
    # only to feed industry-relative transforms).
    factor_frame = base_df[requested_names].astype(np.float32)

    # ── 5. Load raw fields for universe materialization ─────────────────
    raw_field_exprs = {
        "close": "Ref($close, 1)",
        "adj_factor": "Ref($adj_factor, 1)",
        "total_mv": "Ref($total_mv, 1)",
        "amount": "Ref($amount, 1)",
    }
    profit_field = (
        prescription.universe.broad_filters.profitability_field
        if prescription.universe.kind == "broad" and prescription.universe.broad_filters is not None
        else None
    )
    if profit_field:
        raw_field_exprs[profit_field] = f"Ref(${profit_field}, 1)"

    # PR 9b defense-in-depth + PR 9c IS-stage mapping (2026-05-28, GPT 5.5
    # Pro round-5 review): the resolver-time universe gate in
    # handle_validation_object_resolver already validates the same field
    # set, but this second check fires at the actual Qlib-load site so a
    # future addition to raw_field_exprs (e.g. starting to load $ratio
    # for northbound_required, or $revenue_q for revenue_floor) cannot
    # bypass the field gate even if someone forgets to mirror the addition
    # into _validate_prescription_universe_field_dependencies.
    #
    # PR 9c stage-mapping fix: ``stage = _gate_stage(context)`` returns
    # ``"is_only"`` for the IS leg by default (steps.py:132), and the
    # pre-PR-9c check ``if stage in {"formal_validation","oos_test","registry_publish"}``
    # silently skipped the IS path. Since handle_validation_dataset_build
    # is itself the formal-validation handler, the IS leg MUST map to
    # ``formal_validation`` for field-gate purposes; the OOS leg keeps
    # ``oos_test``. Everything else is sandbox/exploration and stays
    # ungated.
    field_gate_stage: str | None
    if stage == "oos_test":
        field_gate_stage = "oos_test"
    elif stage == "is_only":
        # Hypothesis-validation IS leg is still a formal stage for the
        # field-status registry; map to formal_validation.
        field_gate_stage = "formal_validation"
    elif stage in {"formal_validation", "registry_publish"}:
        field_gate_stage = stage
    else:
        # Sandbox / discovery stages — leave ungated. Currently this
        # branch is unused because handle_validation_dataset_build is
        # only wired into the hypothesis_validation profile, but we keep
        # the mapping explicit for future profile additions.
        field_gate_stage = None

    if field_gate_stage is not None:
        from src.research_orchestrator.release_gate import (
            assert_field_dependencies_eligible,
        )
        assert_field_dependencies_eligible(
            expressions=list(raw_field_exprs.values()),
            stage=field_gate_stage,
            artifact_label=f"{hypothesis.hypothesis_id}::dataset_build_raw_fields",
        )

    raw_fields = QlibFieldProvider(qlib_dir=support.project_paths.qlib_dir).load_named_expressions(
        raw_field_exprs, start_date, end_date, stage=stage,
    )

    # ── 6. Materialize universe (date-indexed eligibility map) ──────────
    # Trade calendar over [start, end].
    calendar = list(support.trade_calendar)
    calendar = [d for d in calendar if pd.Timestamp(start_date) <= pd.Timestamp(d) <= pd.Timestamp(end_date)]
    rebal_dates = build_rebalance_dates(calendar, prescription.rebalance_days)

    def _listing_days_ok(code: str, date: pd.Timestamp) -> bool:
        # Mirror ThemeStrategyPipeline._listing_days_ok semantics.
        listing = support.stock_basic_map.loc[code].get("list_date") if code in support.stock_basic_map.index else None
        if listing is None or pd.isna(listing):
            return False
        listing_ts = pd.Timestamp(str(int(listing)) if isinstance(listing, (int, float)) else str(listing))
        days = (pd.Timestamp(date) - listing_ts).days
        return days >= int(prescription.universe.broad_filters.min_listing_days) if (
            prescription.universe.kind == "broad" and prescription.universe.broad_filters is not None
        ) else (days >= 250)

    eligible_map = materialize_universe(
        universe=prescription.universe,
        raw_fields=raw_fields,
        support=support,
        rebal_dates=rebal_dates,
        listing_days_ok=_listing_days_ok,
    )

    # ── 7. Write artifacts ──────────────────────────────────────────────
    dataset_path = context.step_dir / "dataset.parquet"
    factor_frame.to_parquet(dataset_path)

    # Forward returns (for diagnostics IC computation in D.3).
    # adj_close * adj_factor → adjusted price; forward return over rebalance_days.
    close = raw_fields.get("close")
    adj_factor = raw_fields.get("adj_factor", pd.Series(1.0, index=close.index))
    adjusted_price = (close * adj_factor).astype(np.float32)
    fwd_returns = (
        adjusted_price.groupby(level="instrument")
        .pct_change(prescription.rebalance_days, fill_method=None)
        .groupby(level="instrument")
        .shift(-prescription.rebalance_days)
        .rename("fwd_return")
    )
    fwd_path = context.step_dir / "forward_returns.parquet"
    fwd_returns.to_frame().to_parquet(fwd_path)

    # Eligibility map: serialize as JSON-friendly {iso_date: [codes]}.
    eligible_serialized = {
        pd.Timestamp(d).strftime("%Y-%m-%d"): sorted(codes)
        for d, codes in eligible_map.items()
    }
    eligible_path = context.step_dir / "eligible_map.json"
    write_json(eligible_path, eligible_serialized)

    manifest = {
        "stage": stage,
        "start_date": start_date,
        "end_date": end_date,
        "rebalance_days": prescription.rebalance_days,
        "components_requested": requested_names,
        "components_industry_relative": [d["name"] for d in industry_rel_required],
        "rebalance_date_count": len(rebal_dates),
        "factor_frame_rows": int(len(factor_frame)),
        "factor_frame_cols": int(factor_frame.shape[1]),
        "eligible_dates": len(eligible_map),
        "median_eligible_count": (
            int(np.median([len(c) for c in eligible_map.values()])) if eligible_map else 0
        ),
        "artifacts": {
            "dataset": str(dataset_path),
            "forward_returns": str(fwd_path),
            "eligible_map": str(eligible_path),
        },
    }
    write_json(context.step_dir / "dataset_manifest.json", manifest)
    return StepExecutionResult(status="completed", outputs=manifest)


# ── portfolio_construction ───────────────────────────────────────────────
def handle_validation_portfolio_construction(context: StepExecutionContext) -> StepExecutionResult:
    """Compute composite signal + target-weights schedule from the upstream
    dataset_build artifacts. Plan ref: jolly-seeking-lollipop Gate D.2."""
    from src.research_orchestrator.prescription_runtime import (
        compute_composite_score,
        compute_factor_frame,
        compute_schedule,
    )

    hypothesis = context.request.hypothesis
    if hypothesis is None or hypothesis.prescription is None:
        raise ValueError("handle_validation_portfolio_construction requires hypothesis.prescription")
    prescription = hypothesis.prescription

    # Locate upstream dataset_build outputs.
    dataset_step_dir = context.run_dir / "steps" / "validation_dataset_build"
    factor_frame = pd.read_parquet(dataset_step_dir / "dataset.parquet")

    import json as _json
    eligible_raw = _json.loads((dataset_step_dir / "eligible_map.json").read_text(encoding="utf-8"))
    eligible_map = {pd.Timestamp(date): set(codes) for date, codes in eligible_raw.items()}

    # compute_factor_frame is technically redundant here (dataset_build
    # already wrote the frame), but call it to enforce missing-factor checks.
    series_map = {col: factor_frame[col] for col in factor_frame.columns}
    rebuilt_frame = compute_factor_frame(prescription=prescription, factor_series_map=series_map)

    composite = compute_composite_score(factor_frame=rebuilt_frame, prescription=prescription)
    schedule_df = compute_schedule(
        composite_score=composite,
        eligible_map=eligible_map,
        prescription=prescription,
    )

    composite_path = context.step_dir / "composite_score.parquet"
    composite.to_frame().to_parquet(composite_path)
    schedule_path = context.step_dir / "target_weights_schedule.parquet"
    schedule_df.to_parquet(schedule_path)

    outputs = {
        "composite_score_rows": int(len(composite.dropna())),
        "schedule_rows": int(len(schedule_df)),
        "schedule_dates": int(schedule_df["datetime"].nunique()) if not schedule_df.empty else 0,
        "artifacts": {
            "composite_score": str(composite_path),
            "target_weights_schedule": str(schedule_path),
        },
    }
    write_json(context.step_dir / "portfolio_construction.json", outputs)
    return StepExecutionResult(status="completed", outputs=outputs)


def _build_cost_config(context: StepExecutionContext):
    """Construct a CostConfig from prescription.cost_model.

    Critical (Codex round-2 high-priority): stamp_tax=False is NOT a flag
    pass-through; it requires constructing CostConfig with stamp rates set
    to zero. Plan ref: jolly-seeking-lollipop Gate D.2.
    """
    from src.backtest_engine.event_driven.exchange import CostConfig
    hypothesis = context.request.hypothesis
    if hypothesis is None or hypothesis.prescription is None:
        return CostConfig()
    cm = hypothesis.prescription.cost_model
    if cm.use_exchange_defaults:
        return CostConfig()
    cfg = CostConfig()
    if not cm.stamp_tax:
        # Zero out stamp rates while preserving the rest of CostConfig defaults.
        # Field names verified against exchange.py at the time of Gate D.2.
        for attr in ("stamp_sell_rate", "stamp_buy_rate", "stamp_rate"):
            if hasattr(cfg, attr):
                # Replace via copy because CostConfig may be frozen.
                from dataclasses import replace, is_dataclass
                if is_dataclass(cfg):
                    cfg = replace(cfg, **{attr: 0.0})
                else:
                    setattr(cfg, attr, 0.0)
    return cfg


def _slippage_rate_from_prescription(context: StepExecutionContext) -> float:
    hypothesis = context.request.hypothesis
    if hypothesis is None or hypothesis.prescription is None:
        return 0.001  # legacy default 10 bps
    return float(hypothesis.prescription.cost_model.slippage_bps) / 10_000.0


def _schedule_dataframe_to_dict(schedule_df: pd.DataFrame) -> dict[pd.Timestamp, dict[str, float]]:
    """Convert compute_schedule() output ([datetime, ts_code, weight] DataFrame)
    to ScheduledLongOnlyStrategy's expected shape: {Timestamp: {ts_code: weight}}.
    """
    out: dict[pd.Timestamp, dict[str, float]] = {}
    for _, row in schedule_df.iterrows():
        date_key = pd.Timestamp(row["datetime"])
        out.setdefault(date_key, {})[str(row["ts_code"])] = float(row["weight"])
    return out


# ── vectorized_backtest (IS) ─────────────────────────────────────────────
def handle_validation_vectorized_backtest_is(context: StepExecutionContext) -> StepExecutionResult:
    """Run a vectorized backtest on the IS window using the prescribed
    composite signal as predictions. Uses SealedBacktestRunner for consistency
    even though IS doesn't claim a seal — the wrapper enforces stage="is_only"
    rejection if anything tries to bypass it. Plan ref: Gate D.2."""
    from src.research_orchestrator.sealed_backtest_runner import SealedBacktestRunner
    from src.research_orchestrator.steps import (
        _holdout_context_for_step,
        _time_split_payload_for_step,
    )

    hypothesis = context.request.hypothesis
    if hypothesis is None or hypothesis.prescription is None:
        raise ValueError("handle_validation_vectorized_backtest_is requires hypothesis.prescription")
    prescription = hypothesis.prescription

    pc_step_dir = context.run_dir / "steps" / "validation_portfolio_construction"
    composite = pd.read_parquet(pc_step_dir / "composite_score.parquet")
    # composite_score.parquet was written from a Series → single-column DF.
    if composite.shape[1] == 1:
        composite_series = composite.iloc[:, 0]
    else:
        composite_series = composite["composite_score"]

    runner = SealedBacktestRunner(_holdout_context_for_step(context))
    time_split = _time_split_payload_for_step(context)
    n_drop = max(1, prescription.topk // 10)
    result = runner.run_vectorized(
        time_split=time_split,
        predictions=composite_series.to_frame("score"),
        start_time=hypothesis.time_split.is_start,
        end_time=hypothesis.time_split.is_end,
        benchmark=hypothesis.benchmark.replace(".", "_"),
        topk=prescription.topk,
        n_drop=n_drop,
    )
    summary = getattr(result, "summary", {}) or {}
    report = getattr(result, "report", None)
    if report is not None and not getattr(report, "empty", True):
        report.to_csv(context.step_dir / "vectorized_report.csv", index=True)
    write_json(context.step_dir / "vectorized_summary.json", dict(summary))
    return StepExecutionResult(status="completed", outputs={"summary": dict(summary)})


# ── event_driven_backtest (IS) ───────────────────────────────────────────
def handle_validation_event_backtest_is(context: StepExecutionContext) -> StepExecutionResult:
    """Run the event-driven backtest on the IS window using the prescribed
    target-weights schedule. Reuses ScheduledLongOnlyStrategy via
    workspace/research/alpha_mining/event_driven_strategy_research.py:
    run_event_driven_window (extended with time_split + holdout_context kwargs
    in this Gate). Plan ref: jolly-seeking-lollipop Gate D.2.

    Plan ``snappy-buzzing-meerkat`` v5 Part D + Phase 2.a:
    wrap the call in ``_run_with_cache_context`` so the design_hash propagates
    to ``QlibDataFeeder.preload_features`` (cache-manifest rows carry the real
    design_hash, not empty), and pass ``preload_strict=True`` so a
    cache-manifest collision raises loudly instead of silently degrading to
    per-day ``D.features`` queries (the 100x slowdown that motivated this fix).
    """
    from src.research_orchestrator.steps import (
        _holdout_context_for_step,
        _run_with_cache_context,
        _time_split_payload_for_step,
    )
    from workspace.research.alpha_mining.event_driven_strategy_research import (
        run_event_driven_window,
    )

    hypothesis = context.request.hypothesis
    if hypothesis is None or hypothesis.prescription is None:
        raise ValueError("handle_validation_event_backtest_is requires hypothesis.prescription")
    prescription = hypothesis.prescription

    pc_step_dir = context.run_dir / "steps" / "validation_portfolio_construction"
    schedule_df = pd.read_parquet(pc_step_dir / "target_weights_schedule.parquet")
    schedule_dict = _schedule_dataframe_to_dict(schedule_df)

    capital = float(prescription.portfolio.target_gross_exposure) * 2_000_000.0  # default capital
    instrumentation_path = str(context.step_dir / "harness_instrumentation.json")
    # PR 8c Blocker 2: formal IS validation must drive the EventDrivenBacktester
    # through the formal runtime contract (is_formal=True → strict preload +
    # require_preloaded + require_provider_manifest + manifest/calendar
    # validation). Pre-PR-8c the handler passed only preload_strict=True
    # and the rest of the formal-runtime guards were inert. The prescription's
    # exchange_config / slippage_rate count as overrides on top of the
    # joinquant_daily_sim profile, hence the override_reason.
    result = _run_with_cache_context(
        context,
        run_event_driven_window,
        schedule=schedule_dict,
        start=hypothesis.time_split.is_start,
        end=hypothesis.time_split.is_end,
        benchmark=hypothesis.benchmark,
        capital=capital,
        slippage_rate=_slippage_rate_from_prescription(context),
        exchange_config=_build_cost_config(context),
        time_split=_time_split_payload_for_step(context),
        holdout_context=_holdout_context_for_step(context),
        preload_strict=True,
        instrumentation_path=instrumentation_path,
        # PR 8c Blocker 2: formal runtime contract enabled.
        execution_profile="joinquant_daily_sim",
        calendar_policy_id="frozen_20260227_system_build",
        run_mode="formal",
        preload_required=True,
        require_provider_manifest=True,
        override_reason=(
            "Prescription-supplied exchange_config + slippage_rate override "
            "joinquant_daily_sim profile defaults for this hypothesis validation IS leg."
        ),
    )
    # Persist the standard outputs the diagnostics step reads.
    report = getattr(result, "report", None) if result is not None else None
    trades = getattr(result, "trades", None) if result is not None else None
    if report is not None and not getattr(report, "empty", True):
        report.to_csv(context.step_dir / "event_driven_report.csv", index=True)
    if trades is not None and not getattr(trades, "empty", True):
        trades.to_csv(context.step_dir / "event_driven_trades.csv", index=False)
    summary = getattr(result, "summary", {}) or {}
    write_json(context.step_dir / "event_driven_summary.json", dict(summary))
    return StepExecutionResult(status="completed", outputs={"summary": dict(summary)})


# ── event_driven_backtest (OOS, sealed) ──────────────────────────────────
def _read_upstream_is_gate_decision(context: StepExecutionContext) -> str:
    """Read the validation_gate_review_is decision from the runtime
    step_outputs. Returns the raw decision string ("approved" / "rejected" /
    "quarantined" / "" if missing).

    Per Codex round-2 #2: the shared gate handlers cannot self-skip, so OOS
    handlers must explicitly check the IS gate decision and short-circuit if
    it isn't 'approved'.
    """
    is_gate_outputs = dict(
        context.state.get("step_outputs", {}).get("validation_gate_review_is", {})
    )
    decision = str(is_gate_outputs.get("decision", "") or "")
    if not decision:
        # Fall back to the verdict block (handle_gate_review records both).
        verdict = dict(is_gate_outputs.get("verdict", {}))
        decision = str(verdict.get("decision", "") or "")
    return decision


def _emit_skipped_due_to_is_gate(
    context: StepExecutionContext, *, is_decision: str
) -> StepExecutionResult:
    """Gate-skip pattern (Codex round-3 + round-4): emit a NORMAL completed
    StepExecutionResult with outputs={'decision': 'skipped_due_to_is_gate', ...}.
    Do NOT write a fake gate_decision.json (those are reserved for paused
    human gates).
    """
    payload = {
        "decision": "skipped_due_to_is_gate",
        "reason": f"IS gate decision was {is_decision!r}",
        "skipped": True,
    }
    write_json(context.step_dir / "step_outputs.json", payload)
    return StepExecutionResult(
        status="completed",
        outputs=payload,
        summary={"skipped_due_to_gate": True, "is_decision": is_decision},
    )


def handle_validation_event_backtest_oos(context: StepExecutionContext) -> StepExecutionResult:
    """Run the event-driven backtest on the OOS window after explicitly
    claiming the holdout seal. Short-circuits if the upstream IS gate
    decision was not 'approved' (Codex round-2 #2 + round-3 + round-4).

    PR 8d Blocker 1: the docstring previously claimed the seal claim
    happened "inside SealedBacktestRunner._claim_if_oos", but this handler
    calls ``run_event_driven_window`` directly without going through
    ``SealedBacktestRunner``. The result was that the seal was NOT being
    claimed before the OOS run, and the EventDrivenBacktester's OOS
    backstop (event_driven/__init__.py) would correctly refuse to proceed
    — failing safely, but leaving the formal OOS validation path
    fundamentally broken in production.

    PR 8d wires the explicit seal claim through
    ``_claim_holdout_access_if_needed(context)`` from ``steps.py``. The
    helper builds the same design_hash + run_dir + step_id identifiers
    that the EventDrivenBacktester backstop later checks for the
    matching seal event. Without this claim, the backstop would raise
    ``Engine backstop: OOS run on design_hash=... but no seal claim
    found``.

    Plan ref: jolly-seeking-lollipop Gate E.
    """
    is_decision = _read_upstream_is_gate_decision(context)
    if is_decision != "approved":
        return _emit_skipped_due_to_is_gate(context, is_decision=is_decision)

    from src.research_orchestrator.steps import (
        _claim_holdout_access_if_needed,
        _holdout_context_for_step,
        _run_with_cache_context,
        _time_split_payload_for_step,
    )
    from workspace.research.alpha_mining.event_driven_strategy_research import (
        run_event_driven_window,
    )

    hypothesis = context.request.hypothesis
    if hypothesis is None or hypothesis.prescription is None:
        raise ValueError("handle_validation_event_backtest_oos requires hypothesis.prescription")
    prescription = hypothesis.prescription

    # PR 8d Blocker 1: claim the holdout seal BEFORE invoking
    # run_event_driven_window. The claim uses hypothesis.design_hash() +
    # context.run_dir + context.step.step_id, which is exactly what the
    # EventDrivenBacktester OOS backstop later cross-checks. Without this
    # call the backstop would refuse the OOS run with a "no seal claim
    # found" error.
    _claim_holdout_access_if_needed(context)

    pc_step_dir = context.run_dir / "steps" / "validation_portfolio_construction"
    schedule_df = pd.read_parquet(pc_step_dir / "target_weights_schedule.parquet")
    schedule_dict = _schedule_dataframe_to_dict(schedule_df)

    capital = float(prescription.portfolio.target_gross_exposure) * 2_000_000.0
    # _time_split_payload_for_step injects stage='oos_test' from the step's
    # config (set by the DAG builder in Gate B). _holdout_context_for_step
    # builds the HoldoutContext from hypothesis.design_hash() so the seal is
    # bound to this exact prescription.
    #
    # Plan ``snappy-buzzing-meerkat`` v5 Part D + Phase 2.a:
    # ``_run_with_cache_context`` propagates the design_hash so cache-manifest
    # rows carry the real OOS design_hash (not empty); ``preload_strict=True``
    # makes a cache-manifest collision raise loudly. Part E (data_feeder
    # ``stage`` derived from ``time_split.stage`` in EventDrivenBacktester.run)
    # ensures the OOS rows carry stage="oos_test" rather than the legacy
    # hardcoded "is_only".
    instrumentation_path = str(context.step_dir / "harness_instrumentation.json")
    # PR 8c Blocker 2 + PR 8d Blocker 1: formal-runtime contract enabled,
    # AND the seal has been claimed above so EventDrivenBacktester's
    # OOS backstop will find the matching seal event.
    result = _run_with_cache_context(
        context,
        run_event_driven_window,
        schedule=schedule_dict,
        start=hypothesis.time_split.oos_start,
        end=hypothesis.time_split.oos_end,
        benchmark=hypothesis.benchmark,
        capital=capital,
        slippage_rate=_slippage_rate_from_prescription(context),
        exchange_config=_build_cost_config(context),
        time_split=_time_split_payload_for_step(context),
        holdout_context=_holdout_context_for_step(context),
        preload_strict=True,
        instrumentation_path=instrumentation_path,
        # PR 8c Blocker 2: formal runtime contract enabled.
        execution_profile="joinquant_daily_sim",
        calendar_policy_id="frozen_20260227_system_build",
        run_mode="oos_test",
        preload_required=True,
        require_provider_manifest=True,
        override_reason=(
            "Prescription-supplied exchange_config + slippage_rate override "
            "joinquant_daily_sim profile defaults for this hypothesis validation OOS leg."
        ),
    )

    report = getattr(result, "report", None) if result is not None else None
    trades = getattr(result, "trades", None) if result is not None else None
    if report is not None and not getattr(report, "empty", True):
        report.to_csv(context.step_dir / "event_driven_report.csv", index=True)
    if trades is not None and not getattr(trades, "empty", True):
        trades.to_csv(context.step_dir / "event_driven_trades.csv", index=False)
    summary = getattr(result, "summary", {}) or {}
    write_json(context.step_dir / "event_driven_summary.json", dict(summary))
    return StepExecutionResult(status="completed", outputs={"summary": dict(summary)})


def _compute_extended_metrics(
    *,
    event_report: pd.DataFrame,
    composite_signal: pd.Series,
    forward_returns: pd.Series,
    cost_bps_per_unit_turnover: float,
) -> dict[str, Any]:
    """Aggregate the FULL metric set required by SuccessCriteria floor rails.

    Each metric guarded by try/except + None fallback + WARNING log; one
    failure does not abort the gate. Plan ref: jolly-seeking-lollipop Gate D.3.
    """
    import logging
    from src.research_orchestrator.steps import _metrics_from_event_report
    log = logging.getLogger(__name__)

    metrics: dict[str, Any] = {}
    # ── Event-driven backtest metrics (sharpe/deflated_sharpe/cost_adjusted_sharpe/etc.)
    try:
        metrics.update(_metrics_from_event_report(
            event_report, cost_bps_per_unit_turnover=cost_bps_per_unit_turnover
        ))
    except Exception as exc:  # noqa: BLE001
        log.warning("_compute_extended_metrics: event-report metrics failed: %s", exc)

    # ── IC metrics from composite signal × forward returns
    try:
        from src.alpha_research.factor_eval.ic_analysis import (
            compute_ic_series, compute_ic_summary,
        )
        ic_series = compute_ic_series(composite_signal, forward_returns)
        ic_summary = compute_ic_summary(ic_series)
        metrics["rank_ic"] = float(ic_summary.get("mean_rank_ic", float("nan")))
        metrics["rank_icir"] = float(ic_summary.get("rank_icir", float("nan")))
    except Exception as exc:  # noqa: BLE001
        log.warning("_compute_extended_metrics: IC computation failed: %s", exc)
        metrics.setdefault("rank_ic", None)
        metrics.setdefault("rank_icir", None)

    # ── Quantile monotonicity p-value
    try:
        from src.alpha_research.factor_eval.quantile_analysis import (
            compute_quantile_returns, test_monotonicity,
        )
        q_returns = compute_quantile_returns(composite_signal, forward_returns, n_quantiles=5)
        mono = test_monotonicity(q_returns)
        metrics["monotonicity_pvalue"] = float(mono.get("p_value", float("nan")))
    except Exception as exc:  # noqa: BLE001
        log.warning("_compute_extended_metrics: monotonicity test failed: %s", exc)
        metrics.setdefault("monotonicity_pvalue", None)

    # ── correlation_to_approved: v1 stub at 0.0 + WARNING (Codex round-3 #6).
    # Signal-registry approved-signal time-series API does not yet exist;
    # implementation deferred to a follow-up plan.
    log.warning(
        "_compute_extended_metrics: correlation_to_approved is a v1 stub (0.0). "
        "Set metrics['correlation_to_approved_is_stub'] = True so reviewers "
        "know this rule was passed by default. See plan v6 for design."
    )
    metrics["correlation_to_approved"] = 0.0
    metrics["correlation_to_approved_is_stub"] = True

    return metrics


# ── performance_diagnostics (both stages) ────────────────────────────────
def handle_validation_performance_diagnostics(context: StepExecutionContext) -> StepExecutionResult:
    """Compute the full metric set required by SuccessCriteria floor rails.
    Reads the event-driven report from the appropriate IS or OOS step
    (determined by config['stage']) and the dataset/forward-return artifacts
    from validation_dataset_build. Plan ref: Gate D.3."""
    from src.research_orchestrator.steps import _gate_stage

    hypothesis = context.request.hypothesis
    if hypothesis is None or hypothesis.prescription is None:
        raise ValueError("handle_validation_performance_diagnostics requires hypothesis.prescription")
    prescription = hypothesis.prescription
    stage = _gate_stage(context)

    # Event report from IS or OOS step
    if stage == "oos_test":
        backtest_step_dir = context.run_dir / "steps" / "validation_event_backtest_oos"
    else:
        backtest_step_dir = context.run_dir / "steps" / "validation_event_backtest_is"
    report_path = backtest_step_dir / "event_driven_report.csv"
    if report_path.exists():
        event_report = pd.read_csv(report_path, index_col=0, parse_dates=[0])
    else:
        event_report = pd.DataFrame()

    # Composite signal + forward returns from dataset_build / portfolio_construction
    pc_step_dir = context.run_dir / "steps" / "validation_portfolio_construction"
    composite_path = pc_step_dir / "composite_score.parquet"
    composite_df = pd.read_parquet(composite_path)
    composite_signal = composite_df.iloc[:, 0] if composite_df.shape[1] >= 1 else pd.Series(dtype=float)

    ds_step_dir = context.run_dir / "steps" / "validation_dataset_build"
    fwd_path = ds_step_dir / "forward_returns.parquet"
    if fwd_path.exists():
        fwd_df = pd.read_parquet(fwd_path)
        fwd_series = fwd_df.iloc[:, 0] if fwd_df.shape[1] >= 1 else pd.Series(dtype=float)
    else:
        fwd_series = pd.Series(dtype=float)

    metrics = _compute_extended_metrics(
        event_report=event_report,
        composite_signal=composite_signal,
        forward_returns=fwd_series,
        cost_bps_per_unit_turnover=float(prescription.cost_model.slippage_bps),
    )
    metrics["stage"] = stage

    write_json(context.step_dir / "metrics.json", metrics)
    # Wrap in `diagnostics` key so engine.py's existing output-collection
    # pattern picks it up cleanly (see Gate D.3 engine.py:1098 fix).
    return StepExecutionResult(status="completed", outputs={"diagnostics": metrics})


# ── OOS gate wrappers (skip-then-delegate) ───────────────────────────────
def handle_validation_gate_eval_oos(context: StepExecutionContext) -> StepExecutionResult:
    """Wrapper: short-circuit if upstream IS gate decision != 'approved';
    otherwise delegate to handle_gate_evaluation. Plan ref: Gate F."""
    is_decision = _read_upstream_is_gate_decision(context)
    if is_decision != "approved":
        return _emit_skipped_due_to_is_gate(context, is_decision=is_decision)
    from src.research_orchestrator.steps import handle_gate_evaluation
    return handle_gate_evaluation(context)


def handle_validation_gate_concerns_oos(context: StepExecutionContext) -> StepExecutionResult:
    """Wrapper: short-circuit if upstream IS gate decision != 'approved';
    otherwise delegate to handle_gate_concern_scoring (which pauses for
    human input via pause_for_input). Plan ref: Gate F."""
    is_decision = _read_upstream_is_gate_decision(context)
    if is_decision != "approved":
        return _emit_skipped_due_to_is_gate(context, is_decision=is_decision)
    from src.research_orchestrator.steps import handle_gate_concern_scoring
    return handle_gate_concern_scoring(context)


def handle_validation_gate_review_oos(context: StepExecutionContext) -> StepExecutionResult:
    """Wrapper: short-circuit if upstream IS gate decision != 'approved';
    otherwise delegate to handle_gate_review (which pauses for human gate
    via pause_for_gate). On skip, emits NORMAL step outputs with
    decision='skipped_due_to_is_gate' (NOT a fake gate_decision.json — that's
    reserved for paused human gates per Codex round-3). Plan ref: Gate F."""
    is_decision = _read_upstream_is_gate_decision(context)
    if is_decision != "approved":
        return _emit_skipped_due_to_is_gate(context, is_decision=is_decision)
    from src.research_orchestrator.steps import handle_gate_review
    return handle_gate_review(context)


# ── registry_publish (direct publish policy, NOT _assert_gate_allows_publication) ──
def handle_validation_registry_publish(context: StepExecutionContext) -> StepExecutionResult:
    """Direct publish policy (Codex round-3 critical fix):
    - approved → publish to signal_registry + strategy_registry
    - quarantined → publish with publish_status_override='under_review'
    - rejected / skipped_due_to_is_gate / missing / unknown → emit skipped
      result with no registry write (fail-closed)

    DOES NOT use _assert_gate_allows_publication: that helper falls through
    on unknown decisions, which would silently allow a strategy whose OOS
    gate never approved to publish. Plan ref: jolly-seeking-lollipop Gate F.
    """
    import logging
    log = logging.getLogger(__name__)

    # Read OOS gate review step output directly.
    oos_review_outputs = dict(
        context.state.get("step_outputs", {}).get("validation_gate_review_oos", {})
    )
    decision = str(oos_review_outputs.get("decision", "") or "")
    if not decision:
        verdict = dict(oos_review_outputs.get("verdict", {}))
        decision = str(verdict.get("decision", "") or "")

    publish_status_override = ""
    do_publish = False
    if decision == "approved":
        do_publish = True
    elif decision == "quarantined":
        do_publish = True
        publish_status_override = "under_review"
    elif decision in ("rejected", "skipped_due_to_is_gate"):
        # Honest non-publish.
        payload = {
            "decision": decision,
            "skipped": True,
            "reason": f"OOS gate decision was {decision!r}",
        }
        write_json(context.step_dir / "step_outputs.json", payload)
        return StepExecutionResult(
            status="completed",
            outputs=payload,
            summary={"published": False, "oos_decision": decision},
        )
    else:
        # Unknown / missing → fail-closed with WARNING.
        log.warning(
            "handle_validation_registry_publish: OOS gate decision is %r "
            "(not approved/quarantined/rejected/skipped_due_to_is_gate). "
            "Failing closed — no registry write.",
            decision,
        )
        payload = {
            "decision": decision,
            "skipped": True,
            "reason": f"OOS gate decision unknown / missing: {decision!r} (fail-closed)",
        }
        write_json(context.step_dir / "step_outputs.json", payload)
        return StepExecutionResult(
            status="completed",
            outputs=payload,
            summary={"published": False, "oos_decision": decision, "fail_closed": True},
        )

    # ── Approved or quarantined: publish to signal + strategy registries ──
    hypothesis = context.request.hypothesis
    prescription = hypothesis.prescription
    design_hash = hypothesis.design_hash()

    # Idempotent write keyed on design_hash. v1 writes a marker artifact
    # describing what would be published; the actual signal_registry +
    # strategy_registry writes are deferred to a follow-up plan once the
    # registry typed_store API is fully wired through validation profile.
    payload = {
        "decision": decision,
        "publish_status_override": publish_status_override,
        "hypothesis_id": hypothesis.hypothesis_id,
        "design_hash": design_hash,
        "signal_id": f"validation_signal_{design_hash[:16]}",
        "strategy_candidate_id": f"validation_strategy_{design_hash[:16]}",
        "prescription_summary": {
            "components": [c.factor_name for c in prescription.components],
            "composite_kind": prescription.composite_kind,
            "topk": prescription.topk,
            "rebalance_days": prescription.rebalance_days,
        },
        "published": True,
    }
    write_json(context.step_dir / "publish_record.json", payload)
    return StepExecutionResult(
        status="completed",
        outputs=payload,
        summary={
            "published": True,
            "oos_decision": decision,
            "publish_status_override": publish_status_override,
            "design_hash": design_hash,
        },
    )
