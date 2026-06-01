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

from typing import Any

from src.research_orchestrator.dag import StepExecutionContext, StepExecutionResult
from src.research_orchestrator.runtime import write_json

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
        base = str(industry[name].get("base", ""))
        return [catalog[base]] if base in catalog else None
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
