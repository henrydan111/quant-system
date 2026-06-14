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

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.research_orchestrator.dag import StepExecutionContext, StepExecutionResult
from src.research_orchestrator.runtime import write_json

logger = logging.getLogger(__name__)
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
    """Phase 5 slice 3 (+ Phase 7 Layer-2): build the IS-only windowed panel for the GATE
    input. Field-ineligible factors (from the resolver's per-factor `field_eligible`) are
    EXCLUDED from compute — a disallowed `$field` never reaches the builder. The panel is
    IS-only (structurally `is_end`-bounded by the Phase-4 builder); the profile has no OOS
    stage. The IsWindowedPanel (non-serializable) is passed to the walk-forward step via
    ``context.state``; only a summary is written.

    Phase 7: eligible factors are split into base / composite / industry-relative and all
    flow through ``load_is_windowed_panel_with_layer2`` (composites + industry-relative are
    SAME-DATE cross-sectional transforms of PIT-safe base factors, so they inherit the
    `is_end` boundary). Dependency-only bases (composite components / industry-rel bases not
    themselves gated) are computed as inputs but EXCLUDED from the verdict columns. There is
    no `non_base_deferred` bucket; an eligible name that is neither base, composite, nor
    industry-relative hard-fails."""
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


# --------------------------------------------------------------------------- #
# P-GATE/F3 (item 2b): CICC-cohort replication-ceiling adjudication at publish
# --------------------------------------------------------------------------- #
# Non-cohort factors are UNAFFECTED — `_cohort_ceiling` returns None and the gate behaves
# exactly as before. A cohort factor whose adjudicated ceiling is below candidate
# (blocked / dev_evidence_only / evidence_only) is REFUSED candidate promotion; a
# candidate_ceiling-or-higher cohort factor promotes as before. Either way a
# ReplicationGovernanceRecord is persisted so the ceiling is gate-readable (roadmap Rev5
# §item-2). The lifecycle gate is univ_all-primary, so the gated domain is univ_all.
_CANDIDATE_BLOCKED_CEILINGS = frozenset({"blocked", "dev_evidence_only", "evidence_only"})


def _parse_umj(v: Any) -> dict:
    try:
        return json.loads(v) if isinstance(v, str) else (v or {})
    except (TypeError, ValueError):
        return {}


def _load_cohort_manifests() -> list:
    """Load every frozen cohort manifest under config/replication/. A manifest that fails to
    load (e.g. a ``manifest_sha`` mismatch — the frozen content was edited) is a HARD
    governance stop (GPT review F2): it RAISES rather than being skipped, so a broken manifest
    can NEVER make a cohort factor silently look non-cohort and slip through the gate. In a
    healthy system every manifest loads, so non-cohort publish runs are unaffected; only a
    genuinely broken manifest halts the publish step."""
    from src.alpha_research.factor_registry.replication_governance import (
        DEFAULT_MANIFEST_DIR,
        load_cohort_manifest,
    )

    out = []
    if DEFAULT_MANIFEST_DIR.exists():
        for p in sorted(DEFAULT_MANIFEST_DIR.glob("*.yaml")):
            try:
                out.append(load_cohort_manifest(p))
            except Exception as e:  # noqa: BLE001
                raise ValueError(
                    f"cohort manifest {p.name} failed to load ({e}); refusing the publish step — "
                    "a broken cohort manifest is a hard governance stop (GPT review F2), not a "
                    "warning, so no cohort factor can slip through the gate as non-cohort") from e
    return out


def _composite_components(factor_id: str) -> list:
    """Component factor ids of a composite (empty if not a composite). Used for F5-lite
    composite truth-observation inheritance (GPT R2 Cond-4)."""
    try:
        from src.alpha_research.factor_library.catalog import get_composite_defs
        for d in get_composite_defs():
            if d.get("name") == factor_id:
                return [str(c) for c in d.get("components", [])]
    except Exception:  # noqa: BLE001
        pass
    return []


@lru_cache(maxsize=1)
def _oos_trade_calendar() -> tuple:
    """Sorted ``YYYY-MM-DD`` trading days for the EXACT OOS quarantine (R1 F9). Cached.

    Returns ``()`` on ANY load failure — ``_cohort_ceiling`` then leaves the quarantine
    ``approximate=True``, which the sealed-OOS gate refuses (fail-safe: a missing/broken calendar
    can NEVER make an approximate quarantine look exact, so it cannot authorize an OOS spend)."""
    try:
        from src.data_infra.pit_research_loader import _trading_calendar
        return tuple(d.strftime("%Y-%m-%d") for d in _trading_calendar())
    except Exception as e:  # noqa: BLE001
        logger.warning("OOS trade calendar load failed (quarantine stays approximate): %s", e)
        return ()


def _cohort_ceiling(factor_id: str, universe_id: str, *, manifests, evidence_df, claim_store,
                    system_oos_start: str = "2021-01-01", current_definition_hash: str = "",
                    certified_operators=frozenset(), trade_calendar=None,
                    is_cohort_linked: bool = False):
    """Adjudicate the replication status ceiling for one (factor, universe) by composing the
    cohort manifest (tier + oos_eligibility), the 7-domain matrix evidence (coverage + depth)
    and the FactorDomainClaim (class). Returns ``None`` ONLY if the factor is in NO cohort
    manifest (→ the gate is unchanged for it). Everything that can fail is done AFTER cohort
    membership is confirmed, so the caller can treat any raised exception as a cohort-factor
    failure and fail closed (GPT review F1). Fail-closed details:
      * >1 manifest match → ambiguous membership → raise (F3);
      * a non-univ_all ``primary_claim_universe`` → raise (the univ_all-only gate cannot
        adjudicate it, F9);
      * the OOS quarantine is computed from the truth-table label window (F4);
      * required operators outside the built-in whitelist → uncertified (F7);
      * missing claim / missing matrix evidence are passed through as fail-closed caps (F6/F8).
    """
    from src.alpha_research.factor_registry.replication_governance import (
        CERTIFIED_BUILTIN_OPERATORS,
        compute_oos_quarantine_start,
        resolve_replication_ceiling,
    )

    matches = []
    for m in manifests:
        r = m.row_for(catalog_factor_id=factor_id)
        if r is not None:
            matches.append((m.source_cohort_id, r, str(m.handbook_label_window_end or "")))
    if not matches:
        # F3 (GPT R1, now enforced): a factor that CARRIES a cohort linkage (factor_master stamp
        # or an active CohortFactorLinkageStore entry) but resolves to 0 manifest rows is a
        # dropped/forgotten link — fail closed rather than silently revert to non-cohort. A
        # genuinely non-cohort factor (no stamp/link) returns None and the gate is unchanged.
        if is_cohort_linked:
            raise ValueError(
                f"{factor_id} carries a cohort linkage stamp/ledger entry but matches 0 manifest "
                "rows — a dropped/forgotten manifest link; failing closed (F3) rather than treating "
                "a CICC-claiming factor as non-cohort")
        return None
    if len(matches) > 1:
        raise ValueError(
            f"{factor_id} matches {len(matches)} cohort manifest rows ({[c for c, *_ in matches]}) "
            "— ambiguous cohort membership, failing closed (F3)")
    cohort_id, row, handbook_label_end = matches[0]

    # F9-full (GPT R1, now enforced): the gate adjudicates the REQUESTED ``universe_id`` directly,
    # not only the manifest ``primary_claim_universe``. The replication tier is domain-agnostic;
    # coverage (matrix evidence) and the FactorDomainClaim are pulled per-universe below, so a
    # declared non-primary domain (e.g. csi300) is adjudicated on its OWN evidence/claim. The
    # manifest ``primary_claim_universe`` is retained as informational provenance only.

    # F8 + freshness (GPT R2 Cond-1b): matrix evidence counts as coverage ONLY when its
    # source_hash matches the factor's CURRENT definition_hash — a stale row from before an
    # expression change must NOT satisfy the availability audit. Unknown current hash or no
    # matching fresh row → coverage_observed stays False → availability_audit_missing cap.
    coverage_tier, effective_ic_days, coverage_observed = "", None, False
    if evidence_df is not None and len(evidence_df) and current_definition_hash:
        auto = evidence_df[
            (evidence_df["factor_id"] == factor_id)
            & (evidence_df["run_type"].isin(["factor_lifecycle_auto", "factor_lifecycle_refresh"]))
            & (evidence_df["universe_id"].fillna("univ_all") == universe_id)
            & (evidence_df["source_hash"].astype("string").fillna("") == current_definition_hash)
        ]
        if len(auto):
            rr = auto.sort_values("evidence_time").iloc[-1]
            coverage_tier = str(rr.get("coverage_tier") or "")
            effective_ic_days = _parse_umj(rr.get("unified_metrics_json")).get("effective_ic_days")
            coverage_observed = bool(coverage_tier) or effective_ic_days is not None

    # F6 + exactly-one (GPT R2 Cond-2): a cohort factor must resolve to EXACTLY one active
    # claim for the adjudicated universe — 0 → missing_domain_claim cap (in the resolver);
    # >1 → ambiguous, fail closed (DataFrame order must not silently pick the ceiling).
    claim_class = claim_id = ""
    claims = claim_store.claims()
    if len(claims):
        cc = claims[(claims["factor_id"] == factor_id) & (claims["universe_id"] == universe_id)
                    & (claims["status"] != "rejected_claim")]
        if len(cc) > 1:
            raise ValueError(
                f"{factor_id} has {len(cc)} active claims for {universe_id!r} — ambiguous, failing "
                "closed; expected exactly one active claim (GPT R2 Cond-2)")
        if len(cc):
            claim_class = str(cc.iloc[0]["claim_class"] or "")
            claim_id = str(cc.iloc[0]["claim_id"] or "")

    # F4 (+ GPT R2 Cond-3): truth-observation quarantines the OOS window. The row's own
    # truth_table_label_end takes precedence; if blank, fall back to the cohort-level
    # handbook_label_window_end so a lazily-enumerated row cannot escape the short-OOS cap.
    truth_label_end = str(getattr(row, "truth_table_label_end", "") or "") or handbook_label_end
    # F5-lite (GPT R2 Cond-4): a COMPOSITE inherits truth-observation from any truth-observed
    # component — closes the leak where a composite's own row omits truth_label_end while its
    # components were observed. (Full §3.1c lineage taint remains deferred.)
    if not truth_label_end:
        for comp in _composite_components(factor_id):
            for m in manifests:
                cr = m.row_for(catalog_factor_id=comp)
                if cr is not None:
                    truth_label_end = (str(getattr(cr, "truth_table_label_end", "") or "")
                                       or str(m.handbook_label_window_end or ""))
                    if truth_label_end:
                        break
            if truth_label_end:
                break
    # OOS quarantine (§9.3). Inject the trading calendar (R1 F9 "approximate=False") so the
    # quarantine date is EXACT, not the conservative calendar-day fallback. trade_calendar is a
    # sorted iterable of YYYY-MM-DD strings; when absent (e.g. unit tests) the helper falls back
    # to approximate=True, which the sealed-OOS gate then refuses (assert_oos_quarantine_satisfied).
    oos_quarantine_start, oos_quarantine_approximate = compute_oos_quarantine_start(
        truth_label_end, system_oos_start, trade_calendar=trade_calendar)
    # F7 + P-OP: an operator is certified iff it is a trusted built-in OR has a `certified`
    # OperatorCertification record; anything else is uncertified → hard-block (a wrong
    # operator silently produces plausible-but-wrong alpha, §10A).
    required_ops = set(getattr(row, "required_operators", ()) or ())
    certified = set(CERTIFIED_BUILTIN_OPERATORS) | set(certified_operators)
    has_uncertified_operator = bool(required_ops - certified)

    decision = resolve_replication_ceiling(
        replication_tier=row.replication_tier_planned, claim_class=claim_class,
        coverage_tier=coverage_tier, effective_ic_days=effective_ic_days,
        oos_eligibility=row.oos_eligibility, truth_observed=bool(truth_label_end),
        coverage_observed=coverage_observed, require_claim=True,
        has_uncertified_operator=has_uncertified_operator,
    )
    return {"decision": decision, "cohort_id": cohort_id, "row": row, "claim_id": claim_id,
            "oos_quarantine_start": oos_quarantine_start,
            "oos_quarantine_approximate": oos_quarantine_approximate}


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
    from src.alpha_research.factor_registry.domain_claims import DomainClaimStore
    from src.alpha_research.factor_registry.replication_governance import ReplicationGovernanceStore

    rd = context.registry_dirs
    store = FactorRegistryStore(rd["factor_registry_dir"])
    run_id = Path(str(context.run_dir)).name or "factor_lifecycle_run"

    # P-GATE/F3 (item 2b, GPT-review-hardened): adjudicate CICC-cohort factors against the
    # replication ceiling (univ_all — the gate is univ_all-primary). Non-cohort factors return
    # None and are unaffected. FAIL-CLOSED (GPT review F1): `_cohort_ceiling` does all fallible
    # work AFTER confirming cohort membership, so a raised exception is a COHORT factor whose
    # adjudication failed → REFUSE it (never fall back to non-cohort promotion). A broken
    # manifest already hard-stopped in `_load_cohort_manifests` (F2).
    gate_universe = "univ_all"
    try:
        system_oos_start = str(_lifecycle_time_split(context.request).oos_start)
    except Exception:  # noqa: BLE001
        system_oos_start = "2021-01-01"
    manifests = _load_cohort_manifests()
    claim_store = DomainClaimStore(rd["factor_registry_dir"])
    # current definition_hash per factor — matrix evidence must match it to count as fresh
    # coverage (GPT R2 Cond-1b: a stale row from before an expression change must not pass).
    _cur = store.factor_master[store.factor_master["is_current"].fillna(False)]
    def_hashes = ({str(r["factor_id"]): str(r.get("definition_hash") or "")
                   for _, r in _cur.iterrows()} if len(_cur) else {})
    # P-OP: operators with a `certified` OperatorCertification (fail-safe — if the cert store
    # can't be read, no operator is treated as certified → uncertified ones block).
    try:
        from src.alpha_research.factor_library.operator_certification import OperatorCertStore
        certified_ops = OperatorCertStore(rd["factor_registry_dir"]).certified_operators()
    except Exception as e:  # noqa: BLE001
        logger.warning("P-OP cert store read failed (fail-closed: none certified): %s", e)
        certified_ops = frozenset()
    # F11 linkage ledger + F3 reverse-stamp: a factor that has an active CohortFactorLinkageStore
    # entry OR a factor_master replication_cohort_id stamp "claims CICC metadata" → _cohort_ceiling
    # fails closed if it then resolves to != 1 manifest row (a dropped/forgotten link). Fail-safe:
    # an unreadable ledger degrades to the factor_master stamp only, never to "not linked".
    from src.alpha_research.factor_registry.replication_governance import CohortFactorLinkageStore
    linkage_store = CohortFactorLinkageStore(rd["factor_registry_dir"])
    try:
        linked_ids = set(linkage_store.linked_factor_ids())
    except Exception as e:  # noqa: BLE001
        logger.warning("linkage ledger read failed (fail-safe: stamp-only): %s", e)
        linked_ids = set()
    if len(_cur) and "replication_cohort_id" in _cur.columns:
        stamped = _cur[_cur["replication_cohort_id"].notna()]
        if len(stamped):
            stamped = stamped[stamped["replication_cohort_id"].astype("string").str.strip() != ""]
            linked_ids |= set(stamped["factor_id"].astype(str).tolist())
    oos_cal = _oos_trade_calendar() or None   # exact OOS quarantine (R1 F9); None → approximate
    cohort_adj: dict[str, dict] = {}
    refused: list[str] = []
    cohort_errors: dict[str, str] = {}
    for v in candidate_verdicts:
        fid = str(v.get("factor", ""))
        if not fid:
            continue
        try:
            info = _cohort_ceiling(
                fid, gate_universe, manifests=manifests, evidence_df=store.factor_evidence,
                claim_store=claim_store, system_oos_start=system_oos_start,
                current_definition_hash=def_hashes.get(fid, ""),
                certified_operators=certified_ops,
                trade_calendar=oos_cal, is_cohort_linked=(fid in linked_ids),
            )
        except Exception as e:  # noqa: BLE001
            logger.error("P-GATE adjudication FAILED for %s — refusing (fail-closed): %s", fid, e)
            refused.append(fid)
            cohort_errors[fid] = str(e)
            continue
        if info is not None:
            cohort_adj[fid] = info
            if info["decision"].status_ceiling in _CANDIDATE_BLOCKED_CEILINGS:
                refused.append(fid)

    # F3 + F11: stamp the reverse cohort link + append a definition-hash-bound ledger event for
    # every CONFIRMED cohort factor (==1 manifest match above). Done after adjudication so only
    # genuine members are stamped; a future dropped manifest link then trips the is_cohort_linked
    # fail-closed path. Non-fatal (the load-bearing governance record is persisted by F10 below);
    # a stamp/ledger failure is logged, not promoted-around. The stamp is in-memory until store.save().
    for fid, info in cohort_adj.items():
        hb = str(getattr(info["row"], "handbook_id", "") or "")
        try:
            store.set_replication_link(factor_id=fid, cohort_id=info["cohort_id"], handbook_id=hb)
            linkage_store.record_linkage(
                cohort_id=info["cohort_id"], factor_id=fid, handbook_id=hb,
                definition_hash=def_hashes.get(fid, ""),
                event=("relinked" if fid in linked_ids else "linked"),
                notes=f"P-GATE registry_publish (universe={gate_universe})")
        except Exception as e:  # noqa: BLE001
            logger.warning("F3/F11 linkage stamp/ledger failed for %s (non-fatal): %s", fid, e)

    # F9-full: adjudicate every OTHER declared domain (active-claim universe != univ_all) the
    # factor carries, persisting a governance record PER domain (resolve-but-label). Promotion is
    # still decided by the univ_all primary; non-primary domains are recorded, not promoted.
    extra_domain_adj: list[tuple] = []   # (fid, universe, info)
    _claims_all = claim_store.claims()
    if len(_claims_all):
        for fid in cohort_adj:
            doms = sorted({str(u) for u in _claims_all[
                (_claims_all["factor_id"] == fid) & (_claims_all["status"] != "rejected_claim")
            ]["universe_id"].tolist()} - {gate_universe})
            for dom in doms:
                try:
                    di = _cohort_ceiling(
                        fid, dom, manifests=manifests, evidence_df=store.factor_evidence,
                        claim_store=claim_store, system_oos_start=system_oos_start,
                        current_definition_hash=def_hashes.get(fid, ""),
                        certified_operators=certified_ops, trade_calendar=oos_cal,
                        is_cohort_linked=(fid in linked_ids))
                except Exception as e:  # noqa: BLE001
                    logger.error("F9-full per-domain adjudication failed for %s@%s: %s", fid, dom, e)
                    continue
                if di is not None:
                    extra_domain_adj.append((fid, dom, di))

    refused_set = set(refused)
    to_promote = [v for v in candidate_verdicts if str(v.get("factor", "")) not in refused_set]

    # F10: persist EVERY cohort factor's ReplicationGovernanceRecord BEFORE any status write.
    # The upsert raises on a store failure, so no cohort candidate promotion is committed
    # without its durable ceiling record (was previously persisted AFTER set_status).
    if cohort_adj:
        gov_store = ReplicationGovernanceStore(rd["factor_registry_dir"])
        for fid, info in cohort_adj.items():
            dec, row = info["decision"], info["row"]
            gov_store.upsert(
                cohort_id=info["cohort_id"], factor_id=fid,
                factor_domain_claim_id=info["claim_id"] or f"{fid}:{gate_universe}",
                replication_tier=row.replication_tier_planned,
                active_cap_reasons=dec.active_cap_reasons,
                oos_eligible_gates_met=dec.oos_eligible_gates_met,
                cohort_denominator_membership=["formalization_candidate"],
                truth_label_end=row.truth_table_label_end,
                oos_quarantine_start=info.get("oos_quarantine_start", ""),
                oos_quarantine_approximate=bool(info.get("oos_quarantine_approximate", False)),
                notes=f"P-GATE adjudicated at registry_publish (universe={gate_universe})",
            )
        # F9-full: one governance record per OTHER declared domain (keyed by the per-domain claim).
        for fid, dom, di in extra_domain_adj:
            dec, row = di["decision"], di["row"]
            gov_store.upsert(
                cohort_id=di["cohort_id"], factor_id=fid,
                factor_domain_claim_id=di["claim_id"] or f"{fid}:{dom}",
                replication_tier=row.replication_tier_planned,
                active_cap_reasons=dec.active_cap_reasons,
                oos_eligible_gates_met=dec.oos_eligible_gates_met,
                cohort_denominator_membership=["formalization_candidate"],
                truth_label_end=row.truth_table_label_end,
                oos_quarantine_start=di.get("oos_quarantine_start", ""),
                oos_quarantine_approximate=bool(di.get("oos_quarantine_approximate", False)),
                notes=f"P-GATE F9-full declared-domain adjudication (universe={dom})",
            )

    # Evidence (idempotent) for the promotable set, then the candidate status change.
    ev_report = store.record_lifecycle_evidence(
        run_id=run_id, verdicts=to_promote, evidence_class=evidence_kind,
        source_run_dir=str(context.run_dir),
    )
    promoted: list[str] = []
    for v in to_promote:
        fid = str(v.get("factor", ""))
        if fid and fid in ev_report["attached"]:
            store.set_status(
                factor_id=fid, status="candidate",
                reason=f"factor_lifecycle IS-heldout gate ({evidence_kind})", source_run_id=run_id,
            )
            # GPT Phase-7 impl-review must-fix: persist the durable direction metadata
            # (the future FrozenSelectionSet hash consumes factor_master.expected_direction).
            # Metadata-only — does NOT touch status / approval_validity / definition_hash.
            store.set_expected_direction(
                factor_id=fid, expected_direction=str(v.get("expected_direction", "")),
            )
            promoted.append(fid)
    store.save()

    # gate-readable governance summary for step_outputs (accurate `promoted` after the loop).
    promoted_set = set(promoted)
    governance = [
        {"factor": fid, "universe": gate_universe,
         "status_ceiling": info["decision"].status_ceiling,
         "blocking_reasons": list(info["decision"].blocking_reasons),
         "promoted": fid in promoted_set}
        for fid, info in cohort_adj.items()
    ]

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
        # GPT R2 Finding-4: distinguish "the evidence producer never ran" from "real
        # governance failure" so the operator knows which to fix.
        "refused_by_missing_prerequisite": sorted(
            fid for fid in cohort_adj
            if "availability_audit_missing" in cohort_adj[fid]["decision"].blocking_reasons),
        "refused_by_true_governance_cap": sorted(
            fid for fid in cohort_adj
            if cohort_adj[fid]["decision"].status_ceiling in _CANDIDATE_BLOCKED_CEILINGS
            and "availability_audit_missing" not in cohort_adj[fid]["decision"].blocking_reasons),
        "refused_by_adjudication_error": cohort_errors,
        "replication_governance": governance,
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
