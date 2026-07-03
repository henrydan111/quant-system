from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

import pandas as pd

from src.alpha_research.candidate_registry import CandidateRegistryStore
from src.alpha_research.factor_eval import (
    annualized_turnover,
    bootstrap_sharpe_ci,
    cost_adjusted_sharpe,
    deflated_sharpe_ratio,
    regime_pass_count,
    summarize_regime_performance,
)
from src.alpha_research.hypothesis_registry import HypothesisRegistryStore
from src.alpha_research.testing_ledger import TestingLedgerStore
from src.research_orchestrator.cache_manifest import CacheContext, reset_cache_context, set_cache_context
from src.research_orchestrator.gate_report import (
    ConcernEnforcementError,
    compute_automated_verdict,
    derive_severity,
    evaluate_success_criteria,
    write_gate_report,
)
from src.research_orchestrator.factor_screening_steps import (
    load_screening_request,
    load_screening_metadata,
    run_screening_dataset_build_step,
    run_screening_registry_publish_step,
    run_screening_vectorized_backtest_step,
)
from src.research_orchestrator.holdout_seal import HoldoutSealStore
from src.research_orchestrator.resolver import ResolverHub
from src.research_orchestrator.registries import SignalRegistryStore, StrategyRegistryStore
from src.research_orchestrator.runtime import collect_artifact_manifest, write_json
from src.research_orchestrator.sealed_backtest_runner import HoldoutContext, SealedBacktestRunner
# jolly-seeking-lollipop Gate B: hypothesis_validation profile handlers.
# Aliased with `_validation_handle_*` to match HANDLER_REGISTRY entries
# without leaking new top-level names that could shadow existing symbols.
from src.research_orchestrator.validation_steps import (
    handle_validation_object_resolver as _validation_handle_object_resolver,
    handle_validation_dataset_build as _validation_handle_dataset_build,
    handle_validation_portfolio_construction as _validation_handle_portfolio_construction,
    handle_validation_vectorized_backtest_is as _validation_handle_vectorized_backtest_is,
    handle_validation_event_backtest_is as _validation_handle_event_backtest_is,
    handle_validation_event_backtest_oos as _validation_handle_event_backtest_oos,
    handle_validation_performance_diagnostics as _validation_handle_performance_diagnostics,
    handle_validation_gate_eval_oos as _validation_handle_gate_eval_oos,
    handle_validation_gate_concerns_oos as _validation_handle_gate_concerns_oos,
    handle_validation_gate_review_oos as _validation_handle_gate_review_oos,
    handle_validation_registry_publish as _validation_handle_registry_publish,
)
# factor_lifecycle plan Phase 5: the IS-only draft->candidate factor-gate handlers.
from src.research_orchestrator.factor_lifecycle_steps import (
    handle_factor_lifecycle_object_resolver as _factor_lifecycle_handle_object_resolver,
    handle_factor_lifecycle_dataset_build as _factor_lifecycle_handle_dataset_build,
    handle_factor_lifecycle_walk_forward as _factor_lifecycle_handle_walk_forward,
    handle_factor_lifecycle_registry_publish as _factor_lifecycle_handle_registry_publish,
)
from src.research_orchestrator.dag import PauseForInputPayload, StepExecutionContext, StepExecutionResult
from src.research_orchestrator.ml_signal_steps import (
    run_ml_dataset_build_step,
    run_ml_event_backtest_step,
    run_ml_experiment_tracking_step,
    run_ml_label_builder_step,
    run_ml_model_training_step,
    run_ml_registry_publish_step,
    run_ml_signal_search_step,
)
from src.research_orchestrator.strategy_improvement_steps import (
    run_improvement_dataset_build_step,
    run_improvement_event_backtest_step,
    run_improvement_execution_validation_step,
    run_improvement_portfolio_construction_step,
    run_improvement_registry_publish_step,
    run_improvement_risk_overlay_step,
    run_improvement_stress_test_step,
)
from src.research_orchestrator.theme_strategy_steps import (
    run_theme_component_step,
    run_theme_dataset_build_step,
    run_theme_event_driven_step,
    run_theme_recipe_step,
    run_theme_universe_step,
)
from src.research_orchestrator.event_signal_steps import run_event_backtest_stage, run_signal_search_stage
from src.research_orchestrator.window_enforcement import enforce_is_window_if_hypothesis


def _relative_paths(run_dir: Path, paths: list[Path]) -> list[str]:
    normalized: list[str] = []
    for path in paths:
        resolved = path.resolve()
        try:
            normalized.append(resolved.relative_to(run_dir.resolve()).as_posix())
        except ValueError:
            normalized.append(str(resolved))
    return normalized


def _load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _gate_decision_path(step_dir: Path) -> Path:
    return step_dir / "gate_decision.json"


def _load_gate_decision(step_dir: Path) -> dict[str, Any]:
    path = _gate_decision_path(step_dir)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_gate_decision(value: str) -> str:
    decision = str(value).strip().lower()
    if decision in {"approve", "approved", "pass", "passed"}:
        return "approved"
    if decision in {"reject", "rejected", "fail", "failed"}:
        return "rejected"
    if decision in {"quarantine", "quarantined"}:
        return "quarantined"
    return ""


def _gate_stage(context: StepExecutionContext) -> str:
    return str(context.step.config.get("stage", "is_only") or "is_only")


def _upsert_cli_option(argv: list[str], flag: str, value: str) -> list[str]:
    updated = list(argv)
    if not value:
        return updated
    for index, token in enumerate(updated):
        if token == flag:
            if index + 1 < len(updated):
                updated[index + 1] = value
            else:
                updated.append(value)
            return updated
        if str(token).startswith(f"{flag}="):
            updated[index] = f"{flag}={value}"
            return updated
    updated.extend([flag, value])
    return updated


def _dag_step_map(context: StepExecutionContext) -> dict[str, Any]:
    return {step.step_id: step for step in context.dag.steps}


def _find_predecessor_step_id(context: StepExecutionContext, capability: str) -> str:
    step_map = _dag_step_map(context)
    matches = [step_id for step_id in context.step.depends_on if step_map[step_id].capability == capability]
    if len(matches) != 1:
        raise ValueError(
            f"Step {context.step.step_id!r} expected exactly one predecessor with capability "
            f"{capability!r}, found {matches or 'none'}"
        )
    return str(matches[0])


def _pre_registered_concern_rows(context: StepExecutionContext) -> list[dict[str, Any]]:
    hypothesis = context.request.hypothesis
    if hypothesis is None or hypothesis.pre_registered_concerns is None:
        return []
    concerns = hypothesis.pre_registered_concerns
    return [
        {
            "label": "most_likely_failure_mode",
            "text": concerns.most_likely_failure_mode,
            "evidence_status": "pending_human_review",
        },
        {
            "label": "weakest_assumption",
            "text": concerns.weakest_assumption,
            "evidence_status": "pending_human_review",
        },
        {
            "label": "what_would_falsify_this",
            "text": concerns.what_would_falsify_this,
            "evidence_status": "pending_human_review",
        },
        {
            "label": "priors_on_cost_sensitivity",
            "text": concerns.priors_on_cost_sensitivity,
            "evidence_status": "pending_human_review",
        },
    ]


def _load_concern_scores_from_outputs(context: StepExecutionContext) -> list[dict[str, Any]]:
    score_step_id = _find_predecessor_step_id(context, "gate_concern_scoring")
    score_outputs = dict(context.state.get("step_outputs", {}).get(score_step_id, {}))
    concern_scores = list(score_outputs.get("concern_scores", []))
    if context.request.hypothesis is not None and context.request.hypothesis.pre_registered_concerns is not None:
        if not concern_scores:
            raise ConcernEnforcementError(
                "gate_review invoked with empty concern_scores - gate_concern_scoring step must run first"
            )
    return concern_scores


def _severity_rank(value: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}[str(value)]


def _metrics_from_event_report(
    report_df: pd.DataFrame,
    *,
    cost_bps_per_unit_turnover: float = 10.0,
) -> dict[str, Any]:
    """Compute event-driven backtest metrics from a report DataFrame.

    Args:
        report_df: backtest report with at least a "return" column; "cost"
            and "turnover" optional.
        cost_bps_per_unit_turnover: bps charged per unit turnover. Defaults to
            10.0 for backward compatibility with existing callers
            (theme_strategy, event_driven_signal_research). The
            hypothesis_validation profile passes prescription.cost_model.slippage_bps
            here. Plan ref: jolly-seeking-lollipop Gate D.0.
    """
    if report_df.empty or "return" not in report_df.columns:
        return {}
    gross = report_df["return"].astype(float)
    cost = report_df["cost"].astype(float) if "cost" in report_df.columns else pd.Series(0.0, index=gross.index)
    turnover = (
        report_df["turnover"].astype(float)
        if "turnover" in report_df.columns
        else pd.Series(0.0, index=gross.index)
    )
    net = gross - cost
    std = float(net.std(ddof=1))
    sharpe = float((net.mean() * (252 ** 0.5)) / std) if std > 0 else None
    cumulative = net.add(1.0).cumprod()
    max_drawdown = None
    if not cumulative.empty:
        max_drawdown = float(abs((cumulative / cumulative.cummax() - 1.0).min()))
    bootstrap = bootstrap_sharpe_ci(net) if len(net) >= 10 else {"ci_low": None, "ci_high": None}
    regime_summary = summarize_regime_performance(net)
    return {
        "sharpe": sharpe,
        "deflated_sharpe": deflated_sharpe_ratio(net, number_of_trials=1) if len(net) >= 10 else None,
        "cost_adjusted_sharpe": cost_adjusted_sharpe(
            gross, turnover, cost_bps_per_unit_turnover=cost_bps_per_unit_turnover
        ) if len(gross) >= 2 else None,
        "annual_turnover": annualized_turnover(turnover),
        "max_drawdown": max_drawdown,
        "bootstrap_sharpe_ci_low": bootstrap.get("ci_low"),
        "bootstrap_sharpe_ci_high": bootstrap.get("ci_high"),
        "regime_pass_count": regime_pass_count(regime_summary),
        "report_row_count": int(len(report_df)),
        "cost_bps_per_unit_turnover": float(cost_bps_per_unit_turnover),
    }


def _collect_measured_values(context: StepExecutionContext) -> dict[str, Any]:
    if context.profile.profile_id == "factor_screening":
        report_df = _load_csv_if_exists(context.run_dir / "factor_screening_report.csv")
        if report_df.empty:
            return {}
        rank_icir = None
        for column in ("rank_icir_5d", "abs_icir"):
            if column in report_df.columns:
                rank_icir = float(report_df[column].astype(float).max())
                break
        return {
            "factor_count": int(len(report_df)),
            "rank_icir": rank_icir,
        }

    if context.profile.profile_id == "event_driven_signal_research":
        values = _metrics_from_event_report(_load_csv_if_exists(context.run_dir / "event_driven_report.csv"))
        values["selected_factor_rows"] = int(
            context.state.get("step_outputs", {}).get("signal_search", {}).get("selected_factor_rows", 0)
        )
        return values

    if context.profile.profile_id == "theme_strategy":
        rows = []
        for theme_dir in sorted(item for item in context.run_dir.iterdir() if item.is_dir()):
            variant_df = _load_csv_if_exists(theme_dir / "event_driven_variant_summary.csv")
            if variant_df.empty:
                continue
            rows.append(variant_df.iloc[0].to_dict())
        if not rows:
            return {}
        best = rows[0]
        return {
            "relative_excess_return": best.get("relative_excess_return", best.get("stitched_relative_excess_return")),
            "max_drawdown": best.get("max_drawdown", best.get("worst_max_drawdown")),
            "theme_count": len(rows),
        }

    if context.profile.profile_id in {"ml_signal_model_research", "strategy_improvement"}:
        report_df = _load_csv_if_exists(context.run_dir / "event_driven_report.csv")
        return _metrics_from_event_report(report_df)

    # jolly-seeking-lollipop Gate D.3: hypothesis_validation reads metrics.json
    # written by validation_performance_diagnostics. The handler computes the
    # full SuccessCriteria-required metric set there, so we just surface it.
    if context.profile.profile_id == "hypothesis_validation":
        gate_stage = _gate_stage(context)
        diagnostics_step = (
            "validation_diagnostics_oos" if gate_stage == "oos_test" else "validation_diagnostics_is"
        )
        metrics_path = context.run_dir / "steps" / diagnostics_step / "metrics.json"
        if metrics_path.exists():
            import json as _json
            return _json.loads(metrics_path.read_text(encoding="utf-8"))
        return {}

    # factor_lifecycle plan Phase 5 (slice 5): surface the IS-only walk-forward metrics so
    # the shared gate has a non-empty rule table for a factor BATCH. The lifecycle heldout
    # ICIR is MAPPED into the standard `rank_icir` metric (GPT slice-1 risk, option a) so a
    # SuccessCriteria with metric=rank_icir auto-evaluates -> non-empty criteria_results.
    if context.profile.profile_id == "factor_lifecycle":
        wf = context.state.get("step_outputs", {}).get("factor_lifecycle_walk_forward", {})
        verdicts = wf.get("factor_verdicts", [])
        icirs: list[float] = []
        for v in verdicts:
            val = v.get("heldout_rank_icir")
            if val is None:
                continue
            try:
                f = abs(float(val))
            except (TypeError, ValueError):
                continue
            if f == f:  # exclude NaN
                icirs.append(f)
        icirs.sort()
        median_icir = icirs[len(icirs) // 2] if icirs else None
        tested = int(wf.get("tested_count", 0))
        ineligible = int(wf.get("field_ineligible_count", 0))
        return {
            "rank_icir": (icirs[-1] if icirs else None),  # max |heldout ICIR| -> standard rule
            "median_heldout_rank_icir": median_icir,
            "candidate_count": int(wf.get("candidate_count", 0)),
            "tested_count": tested,
            "field_ineligible_count": ineligible,
            "effective_trials": tested + ineligible,
        }

    return {}


def _assert_gate_allows_publication(context: StepExecutionContext) -> None:
    try:
        gate_step_id = _find_predecessor_step_id(context, "gate_review")
    except Exception:
        gate_step_id = "gate_review"
    gate_outputs = dict(context.state.get("step_outputs", {}).get(gate_step_id, {}))
    verdict = dict(gate_outputs.get("verdict", {}))
    decision = _normalize_gate_decision(verdict.get("decision", gate_outputs.get("decision", "")))
    if decision == "rejected":
        raise ValueError("Registry publish blocked because gate_review rejected this run.")
    if decision == "quarantined":
        context.state["publish_status_override"] = "under_review"


def _assert_cicc_oos_quarantine(context: StepExecutionContext, prescription, oos_window_start: str) -> None:
    """Fail-closed OOS-quarantine guard for CICC-cohort factors (§9.3 / R1 F9), enforced at the
    UNIVERSAL seal-claim chokepoint so EVERY sealed-OOS path is covered (event-driven, vectorized,
    promotion-evidence — all route through ``_claim_holdout_access_if_needed``), not just one handler
    (GPT scale-review #2).

    If any factor named in the prescription carries a ``ReplicationGovernanceRecord``, the OOS window
    must start at/after its EXACT (``approximate=False``) quarantine — else
    ``assert_oos_quarantine_satisfied`` raises ``OosQuarantineError``. A pure no-op for non-cohort
    prescriptions (no governance store / no matching record). Only the STORE LOAD is guarded
    (a missing store must not break non-CICC OOS); the assertion itself is never swallowed."""
    if prescription is None:
        return
    try:
        from src.alpha_research.factor_registry.replication_governance import (
            ReplicationGovernanceStore,
            assert_oos_quarantine_satisfied,
        )
        rd = getattr(context, "registry_dirs", None) or {}
        gov_dir = rd.get("factor_registry_dir")
        if not gov_dir:
            return
        recs = ReplicationGovernanceStore(gov_dir).records()
    except Exception:  # noqa: BLE001 — store/import problems must not break non-CICC OOS runs
        return
    if recs is None or not len(recs):
        return
    fids = {str(getattr(c, "factor_name", "")) for c in getattr(prescription, "components", ())}
    fids.discard("")
    if not fids:
        return
    hits = recs[recs["factor_id"].astype("string").isin(fids)]
    for _, r in hits.iterrows():
        assert_oos_quarantine_satisfied(
            oos_quarantine_start=str(r.get("oos_quarantine_start") or ""),
            oos_quarantine_approximate=bool(r.get("oos_quarantine_approximate", False)),
            oos_window_start=str(oos_window_start),
            factor_id=str(r.get("factor_id") or ""),
        )


def _claim_holdout_access_if_needed(context: StepExecutionContext) -> None:
    hypothesis = context.request.hypothesis
    if hypothesis is None or hypothesis.time_split is None:
        return
    if _gate_stage(context) != "oos_test":
        return
    # OOS-quarantine enforcement at the universal seal-claim chokepoint — refuse a sealed-OOS claim
    # for a CICC-cohort component whose quarantine is approximate or unsatisfied, BEFORE the seal is
    # spent (no-op for non-cohort prescriptions). Covers every OOS path that claims a seal here.
    _assert_cicc_oos_quarantine(context, hypothesis.prescription, str(hypothesis.time_split.oos_start))
    # v1.4 A8 (implementation-review Blocker 1, 2026-07-03): this chokepoint claims by the
    # LEGACY design_hash identity. A post-2026-02-27 VIRGIN window may be spent only by the
    # PR3 StrategyRegistryStore/book_seal_key path (or a pre-authorized A5 override study,
    # which claims through the skill's own seal path) — refuse it HERE, at the chokepoint,
    # so every orchestrator OOS handler (event-driven AND vectorized) is covered, before the
    # seal is spent. Already-burned windows (oos_end <= 2026-02-27) still pass: the required
    # PR3 dry-run pilot runs on a burned window through this same path.
    from src.alpha_research.factor_eval_skill.multiplicity import is_virgin_window

    if is_virgin_window(str(hypothesis.time_split.oos_end)):
        raise RuntimeError(
            "v1.4_A8_virgin_window_blocked_until_pr3: the orchestrator OOS seal claim still "
            "uses the legacy design_hash identity. Post-2026-02-27 virgin OOS may be spent "
            "only by the PR3 StrategyRegistryStore/book_seal_key path, or by a "
            "pre-authorized A5 override study. Use already-burned windows for the required "
            "dry-run pilot."
        )
    seal_store = HoldoutSealStore(context.registry_dirs["holdout_seal_dir"])
    seal_store.claim_holdout_access(
        design_hash=hypothesis.design_hash(),
        hypothesis_id=hypothesis.hypothesis_id,
        structural_family=hypothesis.structural_family(),
        profile_id=context.profile.profile_id,
        run_dir=str(context.run_dir),
        step_id=context.step.step_id,
        stage="oos_test",
        allow_same_run=context.resumed,
    )


def _time_split_payload_for_step(context: StepExecutionContext) -> dict[str, Any] | None:
    hypothesis = context.request.hypothesis
    if hypothesis is None or hypothesis.time_split is None:
        return None
    payload = hypothesis.time_split.to_dict()
    payload["stage"] = _gate_stage(context)
    return payload


def _cache_context_for_step(context: StepExecutionContext) -> CacheContext:
    hypothesis = context.request.hypothesis
    return CacheContext(
        design_hash=hypothesis.design_hash() if hypothesis is not None else "",
        hypothesis_id=hypothesis.hypothesis_id if hypothesis is not None else "",
        structural_family=hypothesis.structural_family() if hypothesis is not None else "",
        profile_id=context.profile.profile_id,
        run_dir=str(context.run_dir),
        step_id=context.step.step_id,
    )


def _holdout_context_for_step(context: StepExecutionContext) -> HoldoutContext | None:
    hypothesis = context.request.hypothesis
    if hypothesis is None or hypothesis.time_split is None:
        return None
    return HoldoutContext(
        design_hash=hypothesis.design_hash(),
        hypothesis_id=hypothesis.hypothesis_id,
        structural_family=hypothesis.structural_family(),
        run_dir=str(context.run_dir),
        step_id=context.step.step_id,
        stage=_gate_stage(context),
        allow_same_run=context.resumed,
        seal_store_dir=str(context.registry_dirs["holdout_seal_dir"]),
    )


def _run_with_cache_context(context: StepExecutionContext, fn, /, *args, **kwargs):
    token = set_cache_context(_cache_context_for_step(context))
    try:
        return fn(*args, **kwargs)
    finally:
        reset_cache_context(token)


def handle_noop(context: StepExecutionContext) -> StepExecutionResult:
    outputs = {
        "step_id": context.step.step_id,
        "capability": context.step.capability,
        "status": "completed",
        "summary": {
            "profile_id": context.profile.profile_id,
            "mode": context.request.mode,
        },
    }
    return StepExecutionResult(outputs=outputs, summary={"message": f"{context.step.capability} recorded"})


def handle_object_resolver(context: StepExecutionContext) -> StepExecutionResult:
    if context.request.mode != "formal" or not context.profile.formal_requires_resolver:
        resolution = {
            "formal_hits": 0,
            "candidate_hits": 0,
            "new_objects_created": 0,
            "unresolved_objects": [],
            "resolved_objects": [],
        }
    else:
        resolver = ResolverHub(
            factor_registry_dir=context.registry_dirs["factor_registry_dir"],
            candidate_registry_dir=context.registry_dirs["candidate_registry_dir"],
            signal_registry_dir=context.registry_dirs["signal_registry_dir"],
            model_registry_dir=context.registry_dirs["model_registry_dir"],
            strategy_registry_dir=context.registry_dirs["strategy_registry_dir"],
        )
        allowed_new_object_types = {item.object_type for item in context.request.produces}
        resolution = resolver.resolve_assets(
            consumes=context.request.consumes,
            mode=context.request.mode,
            allowed_new_object_types=allowed_new_object_types,
            research_profile=context.profile.profile_id,
        )
        if resolution["unresolved_objects"]:
            unresolved = resolution["unresolved_objects"]
            names = [
                item.get("requested", {}).get("object_name") or item.get("requested", {}).get("object_id")
                for item in unresolved
            ]
            raise ValueError(
                f"Formal research blocked by unresolved objects: {', '.join(str(item) for item in names if item)}"
            )
    return StepExecutionResult(
        outputs={"registry_resolution": resolution},
        summary={
            "formal_hits": int(resolution.get("formal_hits", 0)),
            "candidate_hits": int(resolution.get("candidate_hits", 0)),
            # PR P1.2: surface the per-layer registry hits so a discovery run's
            # draft/stale/deprecated factor consumes stay visible in the summary.
            "factor_registry_hits_by_layer": dict(resolution.get("factor_registry_hits_by_layer", {})),
        },
    )


def handle_screening_dataset_build(context: StepExecutionContext) -> StepExecutionResult:
    args_payload = dict(context.request.inputs.get("args", {}))
    argv = list(context.request.inputs.get("argv", []))
    start_value, end_value = enforce_is_window_if_hypothesis(
        context,
        args_payload.get("start"),
        args_payload.get("end"),
        stage=_gate_stage(context),
    )
    if start_value:
        args_payload["start"] = start_value
        argv = _upsert_cli_option(argv, "--start", start_value)
    if end_value:
        args_payload["end"] = end_value
        argv = _upsert_cli_option(argv, "--end", end_value)
    result = _run_with_cache_context(
        context,
        run_screening_dataset_build_step,
        output_root=context.run_dir,
        args_payload=args_payload,
        argv=argv,
    )
    return StepExecutionResult(
        outputs={
            "screening_stage": "dataset_build",
            "request_path": result["request_path"],
            "effective_start": start_value,
            "effective_end": end_value,
        },
        summary={"argv_count": int(result["argv_count"]), "effective_start": start_value, "effective_end": end_value},
    )


def handle_screening_factor_discovery(context: StepExecutionContext) -> StepExecutionResult:
    request_payload = load_screening_request(context.run_dir)
    args_payload = dict(request_payload.get("args", {}))
    argv = list(request_payload.get("argv", []))
    horizon_values = args_payload.get("horizon", [])
    if not isinstance(horizon_values, list):
        horizon_values = [horizon_values] if horizon_values else []
    outputs = {
        "screening_stage": "factor_discovery",
        "engine": str(args_payload.get("engine", "")),
        "cache_mode": str(args_payload.get("cache_mode", "")),
        "include_new_data": bool(args_payload.get("include_new_data", True)),
        "horizons": [str(item) for item in horizon_values if str(item)],
        "argv_count": len(argv),
    }
    return StepExecutionResult(
        outputs=outputs,
        summary={
            "horizon_count": len(outputs["horizons"]),
            "engine": outputs["engine"],
        },
    )


def handle_screening_vectorized_backtest(context: StepExecutionContext) -> StepExecutionResult:
    runner = SealedBacktestRunner(_holdout_context_for_step(context))
    result = _run_with_cache_context(
        context,
        runner.run_workspace_pipeline,
        pipeline_fn=run_screening_vectorized_backtest_step,
        time_split=_time_split_payload_for_step(context),
        pipeline_args={"output_root": context.run_dir},
    )
    metadata = dict(result.get("metadata", {}))
    return StepExecutionResult(
        outputs={
            "screening_stage": "vectorized_backtest",
            "screening_metadata": metadata,
            "report_path": result.get("report_path", ""),
        },
        summary={"metadata_keys": sorted(metadata.keys())},
    )


def handle_screening_registry_publish(context: StepExecutionContext) -> StepExecutionResult:
    _assert_gate_allows_publication(context)
    result = run_screening_registry_publish_step(
        output_root=context.run_dir,
        factor_registry_dir=context.registry_dirs["factor_registry_dir"],
    )
    return StepExecutionResult(
        outputs={
            "base_metadata": dict(result.get("base_metadata", {})),
            "produced_objects": list(result.get("produced_objects", [])),
            "registry_payloads": dict(result.get("registry_payloads", {})),
        },
        summary={
            "registry_payload_keys": sorted(result.get("registry_payloads", {}).keys()),
        },
    )


def _theme_ids(theme_name: str) -> list[str]:
    from src.alpha_research.theme_strategy.registry import get_theme_specs

    return list(get_theme_specs().keys()) if theme_name == "all" else [theme_name]


def _theme_stage_metadata(context: StepExecutionContext) -> dict[str, Any]:
    return {
        "generated_at": pd.Timestamp.utcnow().tz_localize(None).strftime("%Y-%m-%d %H:%M:%S"),
        "theme": str(context.request.inputs.get("theme", "")),
        "stage": str(context.request.inputs.get("stage", "")),
        "output_dir": str(context.run_dir),
        "execution_mode": "dag_staged",
    }


def handle_theme_dataset_build(context: StepExecutionContext) -> StepExecutionResult:
    start_override, end_override = enforce_is_window_if_hypothesis(
        context,
        "",
        "",
        stage=_gate_stage(context),
    )
    result = _run_with_cache_context(
        context,
        run_theme_dataset_build_step,
        output_root=context.run_dir,
        theme=str(context.request.inputs.get("theme", "all")),
        start_override=start_override or None,
        end_override=end_override or None,
    )
    return StepExecutionResult(
        outputs={
            "theme_stage": "field_audit",
            "theme_ids": result["theme_ids"],
            "ranking": result["ranking"],
            "base_metadata": _theme_stage_metadata(context),
            "effective_start": start_override,
            "effective_end": end_override,
        },
        summary={
            "theme_count": len(result["theme_ids"]),
            "effective_start": start_override,
            "effective_end": end_override,
        },
    )


def handle_theme_universe_builder(context: StepExecutionContext) -> StepExecutionResult:
    result = _run_with_cache_context(
        context,
        run_theme_universe_step,
        output_root=context.run_dir,
        theme=str(context.request.inputs.get("theme", "all")),
    )
    return StepExecutionResult(
        outputs={"theme_stage": "universe", "ranking": result["ranking"]},
        summary={"ranking_rows": int(result["ranking_rows"])},
    )


def handle_theme_factor_construction(context: StepExecutionContext) -> StepExecutionResult:
    component_count = 0
    for theme_id in _theme_ids(str(context.request.inputs.get("theme", "all"))):
        path = context.run_dir / theme_id / "component_registry.csv"
        if path.exists():
            component_count += len(pd.read_csv(path))
    return StepExecutionResult(
        outputs={"theme_stage": "factor_construction", "component_count": int(component_count)},
        summary={"component_count": int(component_count)},
    )


def handle_theme_factor_discovery(context: StepExecutionContext) -> StepExecutionResult:
    result = _run_with_cache_context(
        context,
        run_theme_component_step,
        output_root=context.run_dir,
        theme=str(context.request.inputs.get("theme", "all")),
    )
    selected_components = 0
    for row in result["ranking"]:
        selected_components += int(row.get("selected_components") or 0)
    return StepExecutionResult(
        outputs={"theme_stage": "component", "ranking": result["ranking"]},
        summary={"selected_components": selected_components},
    )


def handle_theme_signal_search(context: StepExecutionContext) -> StepExecutionResult:
    result = _run_with_cache_context(
        context,
        run_theme_recipe_step,
        output_root=context.run_dir,
        theme=str(context.request.inputs.get("theme", "all")),
    )
    return StepExecutionResult(
        outputs={"theme_stage": "recipe", "ranking": result["ranking"]},
        summary={"ranking_rows": int(result["ranking_rows"])},
    )


def handle_theme_vectorized_backtest(context: StepExecutionContext) -> StepExecutionResult:
    theme_rows: list[dict[str, Any]] = []
    total_recipe_rows = 0
    for theme_id in _theme_ids(str(context.request.inputs.get("theme", "all"))):
        recipe_df = _load_csv_if_exists(context.run_dir / theme_id / "signal_recipe_summary.csv")
        best_row = recipe_df.iloc[0].to_dict() if not recipe_df.empty else {}
        theme_rows.append(
            {
                "theme_id": theme_id,
                "recipe_rows": int(len(recipe_df)),
                "best_universe_id": best_row.get("universe_id"),
                "best_recipe_id": best_row.get("recipe_id"),
                "best_stitched_relative_excess_return": best_row.get("stitched_relative_excess_return"),
                "best_holdout_relative_excess_return": best_row.get("holdout_relative_excess_return"),
            }
        )
        total_recipe_rows += int(len(recipe_df))
    return StepExecutionResult(
        outputs={"theme_stage": "vectorized_backtest", "ranking": theme_rows},
        summary={"theme_count": len(theme_rows), "recipe_rows": total_recipe_rows},
    )


def handle_theme_event_driven_backtest(context: StepExecutionContext) -> StepExecutionResult:
    recipe_source = str(context.request.inputs.get("recipe_source_run_dir", "") or "").strip()
    runner = SealedBacktestRunner(_holdout_context_for_step(context))
    result = _run_with_cache_context(
        context,
        runner.run_workspace_pipeline,
        pipeline_fn=run_theme_event_driven_step,
        time_split=_time_split_payload_for_step(context),
        pipeline_args={
            "output_root": context.run_dir,
            "theme": str(context.request.inputs.get("theme", "all")),
            "recipe_source_run_dir": recipe_source or None,
            "stage": _gate_stage(context),
        },
    )
    return StepExecutionResult(
        outputs={"theme_stage": "event_driven", "ranking": result["ranking"]},
        summary={"ranking_rows": int(result["ranking_rows"])},
    )


def handle_theme_execution_validation(context: StepExecutionContext) -> StepExecutionResult:
    theme_rows: list[dict[str, Any]] = []
    total_event_rows = 0
    validated_themes = 0
    for theme_id in _theme_ids(str(context.request.inputs.get("theme", "all"))):
        theme_dir = context.run_dir / theme_id
        event_df = _load_csv_if_exists(theme_dir / "event_driven_variant_summary.csv")
        best_row = event_df.iloc[0].to_dict() if not event_df.empty else {}
        best_report_exists = (theme_dir / "best_backtest_report.html").exists()
        theme_review_exists = (theme_dir / "theme_review_zh.md").exists()
        row = {
            "theme_id": theme_id,
            "event_variant_rows": int(len(event_df)),
            "best_recipe_id": best_row.get("recipe_id"),
            "best_universe_id": best_row.get("universe_id"),
            "best_event_relative_excess_return": best_row.get("relative_excess_return"),
            "best_event_max_drawdown": best_row.get("max_drawdown"),
            "best_backtest_report_exists": bool(best_report_exists),
            "theme_review_exists": bool(theme_review_exists),
        }
        theme_rows.append(row)
        total_event_rows += int(len(event_df))
        if row["event_variant_rows"] > 0:
            validated_themes += 1
    return StepExecutionResult(
        outputs={"theme_stage": "execution_validation", "validation_rows": theme_rows},
        summary={
            "theme_count": len(theme_rows),
            "validated_theme_count": validated_themes,
            "event_variant_rows": total_event_rows,
        },
    )


def handle_theme_registry_publish(context: StepExecutionContext) -> StepExecutionResult:
    _assert_gate_allows_publication(context)
    from src.research_orchestrator.engine import _load_base_metadata

    metadata = _load_base_metadata(context.run_dir)
    generated_at = str(metadata.get("generated_at") or _theme_stage_metadata(context)["generated_at"])
    provisional_metadata = dict(metadata)
    provisional_metadata.update(_theme_stage_metadata(context))
    provisional_metadata["generated_at"] = generated_at
    provisional_metadata.setdefault("status", "running")
    provisional_metadata["artifact_count"] = len(collect_artifact_manifest(context.run_dir))
    write_json(context.run_dir / "run_metadata.json", provisional_metadata)
    candidate_store = CandidateRegistryStore(context.registry_dirs["candidate_registry_dir"])
    signal_store = SignalRegistryStore(context.registry_dirs["signal_registry_dir"])
    migration_result = signal_store.migrate_theme_recipes_from_candidate_registry(
        context.registry_dirs["candidate_registry_dir"]
    )
    candidate_publish = candidate_store.import_theme_strategy_run(
        context.run_dir,
        include_recipe_objects=False,
    )
    signal_publish = signal_store.import_theme_strategy_run(context.run_dir)
    candidate_store.save()
    signal_store.save()
    metadata.update(_theme_stage_metadata(context))
    metadata["generated_at"] = generated_at
    metadata["candidate_registry_publish"] = {"status": "completed", **candidate_publish}
    metadata["signal_registry_publish"] = {
        "status": "completed",
        **signal_publish,
        "migration_result": migration_result,
    }
    produced_objects = [
        {
            "registry": "candidate_registry",
            "object_type": "factor",
            "object_id": candidate_id,
        }
        for candidate_id in candidate_publish.get("candidate_ids", [])
    ] + [
        {
            "registry": "signal_registry",
            "object_type": "signal",
            "object_id": object_id,
        }
        for object_id in signal_publish.get("object_ids", [])
    ]
    return StepExecutionResult(
        outputs={
            "base_metadata": metadata,
            "produced_objects": produced_objects,
            "registry_payloads": {
                "candidate_registry_publish": candidate_publish,
                "signal_registry_publish": signal_publish,
                "signal_registry_migration": migration_result,
            },
        },
        summary={"produced_object_count": len(produced_objects)},
    )


def handle_event_dataset_build(context: StepExecutionContext) -> StepExecutionResult:
    screening_run_dir = Path(str(context.request.inputs.get("screening_run_dir", ""))).resolve()
    report_df = _load_csv_if_exists(screening_run_dir / "factor_screening_report.csv")
    metadata = _load_json_if_exists(screening_run_dir / "factor_screening_run_metadata.json")
    ab_candidate_count = 0
    if not report_df.empty and "grade" in report_df.columns:
        ab_candidate_count = int(
            report_df["grade"].astype(str).str.startswith(("A", "B")).sum()
        )
    outputs = {
        "event_stage": "dataset_build",
        "screening_run_dir": str(screening_run_dir),
        "screening_report_rows": int(len(report_df)),
        "ab_candidate_count": int(ab_candidate_count),
        "screening_start_date": metadata.get("start_date"),
        "screening_end_date": metadata.get("end_date"),
        "benchmark": str(context.request.inputs.get("benchmark", "")),
        "topk": int(context.request.inputs.get("topk", 0) or 0),
        "rebalance_days": int(context.request.inputs.get("rebalance_days", 0) or 0),
        "capital": float(context.request.inputs.get("capital", 0.0) or 0.0),
    }
    return StepExecutionResult(
        outputs=outputs,
        summary={
            "screening_report_rows": outputs["screening_report_rows"],
            "ab_candidate_count": outputs["ab_candidate_count"],
        },
    )


def handle_event_signal_search(context: StepExecutionContext) -> StepExecutionResult:
    from types import SimpleNamespace

    payload = dict(context.request.inputs)
    payload["stage"] = _gate_stage(context)
    if context.request.hypothesis is not None:
        payload["hypothesis"] = context.request.hypothesis.to_dict()
    result = _run_with_cache_context(context, run_signal_search_stage, SimpleNamespace(**payload))
    return StepExecutionResult(
        outputs={
            "event_stage": "signal_search",
            "candidate_count": int(result["candidate_count"]),
            "selected_factor_rows": int(result["selected_factor_rows"]),
        },
        summary={
            "candidate_count": int(result["candidate_count"]),
            "selected_factor_rows": int(result["selected_factor_rows"]),
        },
    )


def handle_event_portfolio_construction(context: StepExecutionContext) -> StepExecutionResult:
    signal_meta = _load_json_if_exists(context.run_dir / "signal_stage_metadata.json")
    selected_df = _load_csv_if_exists(context.run_dir / "selected_core_factors_by_fold.csv")
    unique_factor_count = (
        int(selected_df["factor"].astype(str).nunique()) if not selected_df.empty and "factor" in selected_df.columns else 0
    )
    outputs = {
        "event_stage": "portfolio_construction",
        "selected_factor_rows": int(signal_meta.get("selected_factor_rows", len(selected_df))),
        "unique_selected_factor_count": unique_factor_count,
        "topk": int(context.request.inputs.get("topk", 0) or 0),
        "rebalance_days": int(context.request.inputs.get("rebalance_days", 0) or 0),
        "capital": float(context.request.inputs.get("capital", 0.0) or 0.0),
        "benchmark": str(context.request.inputs.get("benchmark", "")),
    }
    return StepExecutionResult(
        outputs=outputs,
        summary={
            "selected_factor_rows": outputs["selected_factor_rows"],
            "unique_selected_factor_count": outputs["unique_selected_factor_count"],
        },
    )


def handle_event_backtest(context: StepExecutionContext) -> StepExecutionResult:
    from types import SimpleNamespace

    payload = dict(context.request.inputs)
    payload["stage"] = _gate_stage(context)
    if context.request.hypothesis is not None:
        payload["hypothesis"] = context.request.hypothesis.to_dict()
    runner = SealedBacktestRunner(_holdout_context_for_step(context))
    result = _run_with_cache_context(
        context,
        runner.run_workspace_pipeline,
        pipeline_fn=run_event_backtest_stage,
        time_split=_time_split_payload_for_step(context),
        pipeline_args=SimpleNamespace(**payload),
    )
    metadata_path = context.run_dir / "run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    return StepExecutionResult(
        outputs={
            "event_stage": "event_driven_backtest",
            "base_metadata": metadata,
            "candidate_count": int(result["candidate_count"]),
            "selected_factor_rows": int(result["selected_factor_rows"]),
        },
        summary={
            "candidate_count": int(result["candidate_count"]),
            "selected_factor_rows": int(result["selected_factor_rows"]),
        },
    )


def handle_event_execution_validation(context: StepExecutionContext) -> StepExecutionResult:
    metadata = _load_json_if_exists(context.run_dir / "run_metadata.json")
    report_df = _load_csv_if_exists(context.run_dir / "event_driven_report.csv")
    trades_df = _load_csv_if_exists(context.run_dir / "event_driven_trades.csv")
    sensitivity_df = _load_csv_if_exists(context.run_dir / "sensitivity_topk_rebalance.csv")
    outputs = {
        "event_stage": "execution_validation",
        "report_row_count": int(len(report_df)),
        "trade_row_count": int(len(trades_df)),
        "stress_scenario_rows": int(len(sensitivity_df)),
        "backtest_report_exists": bool((context.run_dir / "strategy_backtest_report.html").exists()),
        "master_review_exists": bool((context.run_dir / "master_review.md").exists()),
        "benchmark": metadata.get("benchmark"),
        "topk": metadata.get("topk"),
        "rebalance_days": metadata.get("rebalance_days"),
        "capital": metadata.get("capital"),
    }
    return StepExecutionResult(
        outputs=outputs,
        summary={
            "report_row_count": outputs["report_row_count"],
            "trade_row_count": outputs["trade_row_count"],
            "backtest_report_exists": outputs["backtest_report_exists"],
        },
    )


def handle_ml_dataset_build(context: StepExecutionContext) -> StepExecutionResult:
    args_payload = dict(context.request.inputs)
    args_payload["stage"] = _gate_stage(context)
    if context.request.hypothesis is not None:
        args_payload["hypothesis"] = context.request.hypothesis.to_dict()
    result = _run_with_cache_context(
        context,
        run_ml_dataset_build_step,
        output_root=context.run_dir,
        args_payload=args_payload,
    )
    return StepExecutionResult(
        outputs={"ml_stage": "dataset_build", "candidate_factor_count": int(result["candidate_factor_count"])},
        summary={"candidate_factor_count": int(result["candidate_factor_count"])},
    )


def handle_ml_label_builder(context: StepExecutionContext) -> StepExecutionResult:
    result = _run_with_cache_context(
        context,
        run_ml_label_builder_step,
        output_root=context.run_dir,
        args_payload=dict(context.request.inputs),
    )
    return StepExecutionResult(
        outputs={"ml_stage": "label_builder", "window_count": int(result["window_count"])},
        summary={"window_count": int(result["window_count"])},
    )


def handle_ml_model_training(context: StepExecutionContext) -> StepExecutionResult:
    result = _run_with_cache_context(
        context,
        run_ml_model_training_step,
        output_root=context.run_dir,
        args_payload=dict(context.request.inputs),
    )
    return StepExecutionResult(
        outputs={
            "ml_stage": "model_training",
            "variant_count": int(result["variant_count"]),
            "ml_variant_count": int(result["ml_variant_count"]),
        },
        summary={
            "variant_count": int(result["variant_count"]),
            "ml_variant_count": int(result["ml_variant_count"]),
        },
    )


def handle_ml_signal_search(context: StepExecutionContext) -> StepExecutionResult:
    result = _run_with_cache_context(
        context,
        run_ml_signal_search_step,
        output_root=context.run_dir,
        args_payload=dict(context.request.inputs),
    )
    return StepExecutionResult(
        outputs={
            "ml_stage": "signal_search",
            "best_variant_id": str(result["best_variant_id"]),
            "adoption_recommendation": str(result["adoption_recommendation"]),
        },
        summary={
            "best_variant_id": str(result["best_variant_id"]),
        },
    )


def handle_ml_portfolio_construction(context: StepExecutionContext) -> StepExecutionResult:
    selection_summary = _load_json_if_exists(context.run_dir / "cache" / "ml_selection_summary.json")
    best_ml_summary = dict(selection_summary.get("best_ml_summary", {}))
    outputs = {
        "ml_stage": "portfolio_construction",
        "best_variant_id": str(best_ml_summary.get("variant_id", "")),
        "adoption_recommendation": str(selection_summary.get("adoption_recommendation", "")),
        "topk": int(context.request.inputs.get("topk", 0) or 0),
        "rebalance_days": int(context.request.inputs.get("rebalance_days", 0) or 0),
        "capital": float(context.request.inputs.get("capital", 0.0) or 0.0),
        "benchmark": str(context.request.inputs.get("benchmark", "")),
    }
    return StepExecutionResult(
        outputs=outputs,
        summary={
            "best_variant_id": outputs["best_variant_id"],
            "adoption_recommendation": outputs["adoption_recommendation"],
        },
    )


def handle_ml_event_backtest(context: StepExecutionContext) -> StepExecutionResult:
    runner = SealedBacktestRunner(_holdout_context_for_step(context))
    result = _run_with_cache_context(
        context,
        runner.run_workspace_pipeline,
        pipeline_fn=run_ml_event_backtest_step,
        time_split=_time_split_payload_for_step(context),
        pipeline_args={
            "output_root": context.run_dir,
            "args_payload": {**dict(context.request.inputs), "stage": _gate_stage(context)},
        },
    )
    return StepExecutionResult(
        outputs={
            "ml_stage": "event_driven_backtest",
            "best_variant_id": str(result["best_variant_id"]),
            "base_metadata": dict(result.get("base_metadata", {})),
        },
        summary={"best_variant_id": str(result["best_variant_id"])},
    )


def handle_ml_execution_validation(context: StepExecutionContext) -> StepExecutionResult:
    metadata = _load_json_if_exists(context.run_dir / "run_metadata.json")
    best_ml_summary = dict(metadata.get("best_ml_summary", {}))
    best_variant_id = str(best_ml_summary.get("variant_id", ""))
    variant_dir = context.run_dir / "cache" / "ml_variants" / best_variant_id if best_variant_id else context.run_dir
    outputs = {
        "ml_stage": "execution_validation",
        "best_variant_id": best_variant_id,
        "best_report_exists": bool((context.run_dir / "best_ml_variant_backtest_report.html").exists()),
        "variant_event_report_exists": bool((variant_dir / "event_driven_report.csv").exists()),
        "strategy_signal_exists": bool((variant_dir / "strategy_signal.parquet").exists()),
        "adoption_recommendation": metadata.get("adoption_recommendation"),
    }
    return StepExecutionResult(
        outputs=outputs,
        summary={
            "best_variant_id": best_variant_id,
            "best_report_exists": outputs["best_report_exists"],
        },
    )


def handle_ml_experiment_tracking(context: StepExecutionContext) -> StepExecutionResult:
    result = _run_with_cache_context(
        context,
        run_ml_experiment_tracking_step,
        output_root=context.run_dir,
        args_payload=dict(context.request.inputs),
    )
    return StepExecutionResult(
        outputs={
            "ml_stage": "experiment_tracking",
            "tracking_status": str(result["tracking_status"]),
        },
        summary={"tracking_status": str(result["tracking_status"])},
    )


def handle_ml_registry_publish(context: StepExecutionContext) -> StepExecutionResult:
    _assert_gate_allows_publication(context)
    result = run_ml_registry_publish_step(
        output_root=context.run_dir,
        registry_dirs=context.registry_dirs,
    )
    return StepExecutionResult(
        outputs={
            "base_metadata": dict(result.get("base_metadata", {})),
            "produced_objects": list(result.get("produced_objects", [])),
            "registry_payloads": dict(result.get("registry_payloads", {})),
        },
        summary={"produced_object_count": len(result.get("produced_objects", []))},
    )


def handle_improvement_dataset_build(context: StepExecutionContext) -> StepExecutionResult:
    args_payload = dict(context.request.inputs)
    args_payload["stage"] = _gate_stage(context)
    if context.request.hypothesis is not None:
        args_payload["hypothesis"] = context.request.hypothesis.to_dict()
    result = _run_with_cache_context(
        context,
        run_improvement_dataset_build_step,
        output_root=context.run_dir,
        args_payload=args_payload,
    )
    return StepExecutionResult(
        outputs={
            "improvement_stage": "dataset_build",
            "candidate_factor_count": int(result["candidate_factor_count"]),
            "fold_count": int(result["fold_count"]),
        },
        summary={
            "candidate_factor_count": int(result["candidate_factor_count"]),
            "fold_count": int(result["fold_count"]),
        },
    )


def handle_improvement_portfolio_construction(context: StepExecutionContext) -> StepExecutionResult:
    result = _run_with_cache_context(
        context,
        run_improvement_portfolio_construction_step,
        output_root=context.run_dir,
        args_payload=dict(context.request.inputs),
    )
    return StepExecutionResult(
        outputs={"improvement_stage": "portfolio_construction", "stage_a_count": int(result["stage_a_count"])},
        summary={"stage_a_count": int(result["stage_a_count"])},
    )


def handle_improvement_risk_overlay(context: StepExecutionContext) -> StepExecutionResult:
    result = _run_with_cache_context(
        context,
        run_improvement_risk_overlay_step,
        output_root=context.run_dir,
        args_payload=dict(context.request.inputs),
    )
    return StepExecutionResult(
        outputs={"improvement_stage": "risk_overlay", "stability_pool_count": int(result["stability_pool_count"])},
        summary={"stability_pool_count": int(result["stability_pool_count"])},
    )


def handle_improvement_stress_test(context: StepExecutionContext) -> StepExecutionResult:
    result = _run_with_cache_context(
        context,
        run_improvement_stress_test_step,
        output_root=context.run_dir,
        args_payload=dict(context.request.inputs),
    )
    return StepExecutionResult(
        outputs={"improvement_stage": "stress_test", "baseline_variant_id": str(result["baseline_variant_id"])},
        summary={"baseline_variant_id": str(result["baseline_variant_id"])},
    )


def handle_improvement_event_backtest(context: StepExecutionContext) -> StepExecutionResult:
    runner = SealedBacktestRunner(_holdout_context_for_step(context))
    result = _run_with_cache_context(
        context,
        runner.run_workspace_pipeline,
        pipeline_fn=run_improvement_event_backtest_step,
        time_split=_time_split_payload_for_step(context),
        pipeline_args={
            "output_root": context.run_dir,
            "args_payload": {**dict(context.request.inputs), "stage": _gate_stage(context)},
        },
    )
    return StepExecutionResult(
        outputs={"improvement_stage": "event_driven_backtest", "best_variant_id": str(result["best_variant_id"])},
        summary={"best_variant_id": str(result["best_variant_id"])},
    )


def handle_improvement_execution_validation(context: StepExecutionContext) -> StepExecutionResult:
    result = _run_with_cache_context(
        context,
        run_improvement_execution_validation_step,
        output_root=context.run_dir,
        args_payload=dict(context.request.inputs),
    )
    return StepExecutionResult(
        outputs={
            "improvement_stage": "execution_validation",
            "best_variant_id": str(result["best_variant_id"]),
            "base_metadata": dict(result.get("base_metadata", {})),
        },
        summary={"best_variant_id": str(result["best_variant_id"])},
    )


def handle_improvement_registry_publish(context: StepExecutionContext) -> StepExecutionResult:
    _assert_gate_allows_publication(context)
    result = run_improvement_registry_publish_step(
        output_root=context.run_dir,
        strategy_registry_dir=context.registry_dirs["strategy_registry_dir"],
    )
    return StepExecutionResult(
        outputs={
            "base_metadata": dict(result.get("base_metadata", {})),
            "produced_objects": list(result.get("produced_objects", [])),
            "registry_payloads": dict(result.get("registry_payloads", {})),
        },
        summary={"produced_object_count": len(result.get("produced_objects", []))},
    )


def handle_benchmark_audit_step(context: StepExecutionContext) -> StepExecutionResult:
    from dataclasses import asdict

    from workspace.research.alpha_mining.audit_benchmark_index import run_audit

    benchmark = str(context.request.inputs["benchmark"])
    result = run_audit(benchmark, context.run_dir)
    metadata = {
        "generated_at": pd.Timestamp.utcnow().tz_localize(None).strftime("%Y-%m-%d %H:%M:%S"),
        "benchmark": benchmark,
        "output_dir": str(context.run_dir),
        "audit_result": asdict(result),
    }
    return StepExecutionResult(
        outputs={"base_metadata": metadata, "audit_result": asdict(result)},
        summary={"passed": bool(result.passed)},
    )


def handle_event_registry_publish(context: StepExecutionContext) -> StepExecutionResult:
    _assert_gate_allows_publication(context)
    from src.research_orchestrator.engine import (
        _definition_hash,
        _event_signal_payload,
        _load_base_metadata,
        _load_optional_csv,
        _publish_typed_objects,
        _stable_object_id,
        _summarize_event_report,
    )
    from src.research_orchestrator.registries.typed_store import TypedObjectSnapshot

    metadata = _load_base_metadata(context.run_dir)
    generated_at = str(metadata.get("generated_at") or "")
    factor_store = context.registry_dirs.get("factor_registry_dir")
    # Factor import still belongs to the same formal publication step.
    from src.alpha_research.factor_registry import FactorRegistryStore

    factor_registry = FactorRegistryStore(factor_store)
    factor_import = factor_registry.import_research(context.run_dir)
    factor_registry.save()

    selected_by_fold = _load_optional_csv(context.run_dir / "selected_core_factors_by_fold.csv")
    signal_summary = _summarize_event_report(context.run_dir / "event_driven_report.csv")
    signal_payload = _event_signal_payload(metadata, selected_by_fold)
    signal_hash = _definition_hash("signal:event_driven", signal_payload)
    signal_id = _stable_object_id("signal::event_driven", signal_payload)
    signal_name = f"event_signal_{signal_hash[:8]}"

    strategy_payload = {
        "source_profile": "event_driven_signal_research",
        "signal_object_id": signal_id,
        "signal_definition_hash": signal_hash,
        "screening_run_dir": str(metadata.get("screening_run_dir", "")),
        "benchmark": metadata.get("benchmark"),
        "capital": metadata.get("capital"),
        "topk": metadata.get("topk"),
        "rebalance_days": metadata.get("rebalance_days"),
        "adv_median_floor": metadata.get("adv_median_floor"),
        "participation_cap": metadata.get("participation_cap"),
        "strategy_style": metadata.get("strategy_style"),
    }
    strategy_hash = _definition_hash("strategy:event_driven", strategy_payload)
    strategy_id = _stable_object_id("strategy::event_driven", strategy_payload)
    strategy_name = f"event_strategy_{strategy_hash[:8]}"

    signal_store = SignalRegistryStore(context.registry_dirs["signal_registry_dir"])
    strategy_store = StrategyRegistryStore(context.registry_dirs["strategy_registry_dir"])

    signal_publish = _publish_typed_objects(
        store=signal_store,
        run_type="event_driven_signal_research",
        research_profile="event_driven_signal_research",
        run_dir=context.run_dir,
        generated_at=generated_at,
        objects=[
            TypedObjectSnapshot(
                object_id=signal_id,
                object_name=signal_name,
                object_type="signal",
                research_profile="event_driven_signal_research",
                definition_payload_json=json.dumps(signal_payload, ensure_ascii=True, sort_keys=True, default=str),
                definition_hash=signal_hash,
                display_name_zh=signal_name,
                recommended_status="under_review",
            )
        ],
        summaries_by_object_id={
            signal_id: {
                **signal_summary,
                "candidate_count": int(metadata.get("candidate_count", 0)),
                "selected_factor_rows": int(context.state.get("step_outputs", {}).get("signal_search", {}).get("selected_factor_rows", 0)),
            }
        },
    )
    strategy_publish = _publish_typed_objects(
        store=strategy_store,
        run_type="event_driven_signal_research",
        research_profile="event_driven_signal_research",
        run_dir=context.run_dir,
        generated_at=generated_at,
        objects=[
            TypedObjectSnapshot(
                object_id=strategy_id,
                object_name=strategy_name,
                object_type="strategy_candidate",
                research_profile="event_driven_signal_research",
                definition_payload_json=json.dumps(strategy_payload, ensure_ascii=True, sort_keys=True, default=str),
                definition_hash=strategy_hash,
                display_name_zh=strategy_name,
                recommended_status="under_review",
            )
        ],
        summaries_by_object_id={
            strategy_id: {
                **signal_summary,
                "candidate_count": int(metadata.get("candidate_count", 0)),
                "selected_factor_rows": int(context.state.get("step_outputs", {}).get("signal_search", {}).get("selected_factor_rows", 0)),
            }
        },
    )
    produced_objects = [
        {"registry": "signal_registry", "object_type": "signal", "object_id": signal_id},
        {"registry": "strategy_registry", "object_type": "strategy_candidate", "object_id": strategy_id},
    ]
    return StepExecutionResult(
        outputs={
            "base_metadata": metadata,
            "produced_objects": produced_objects,
            "registry_payloads": {
                "factor_registry_import": factor_import,
                "signal_registry_publish": signal_publish,
                "strategy_registry_publish": strategy_publish,
            },
        },
        summary={"produced_object_count": len(produced_objects)},
    )


def _build_concern_scores_template(
    context: StepExecutionContext,
    rule_table: list[dict[str, Any]],
    measured_values: dict[str, Any],
) -> dict[str, Any]:
    hypothesis = context.request.hypothesis
    concerns = hypothesis.pre_registered_concerns if hypothesis is not None else None
    if concerns is None:
        return {"scores": []}
    return {
        "_instructions": (
            "Fill in each concern below. Every field is mandatory. "
            "'measured_evidence_against_concern' must be at least 80 characters. "
            "'keyed_to_rule_id' must reference a rule_id from the rule table. "
            "'quantitative_anchor' must contain the keyed rule's metric with the exact measured value."
        ),
        "_schema_id": "gate_concern_scores_v1",
        "_measured_values_available": sorted(measured_values.keys()),
        "_rule_ids_available": [str(row.get("rule_id") or row.get("rule", "")) for row in rule_table],
        "_rule_metrics": {
            str(row.get("rule_id") or row.get("rule", "")): str(row.get("metric", "")) for row in rule_table
        },
        "scores": [
            {
                "concern_id": concern_id,
                "concern_text": str(getattr(concerns, concern_id, "")),
                "keyed_to_rule_id": "",
                "measured_evidence_against_concern": "",
                "quantitative_anchor": {},
                "confirmed": False,
                "severity": "low",
            }
            for concern_id in (
                "most_likely_failure_mode",
                "weakest_assumption",
                "what_would_falsify_this",
                "priors_on_cost_sensitivity",
            )
        ],
    }


def handle_gate_evaluation(context: StepExecutionContext) -> StepExecutionResult:
    hypothesis = context.request.hypothesis
    measured_values = _collect_measured_values(context)
    criteria_results = evaluate_success_criteria(hypothesis, measured_values)
    return StepExecutionResult(
        outputs={
            "gate_stage": _gate_stage(context),
            "measured_values": measured_values,
            "criteria_results": criteria_results,
        },
        summary={"criteria_count": len(criteria_results), "measured_value_count": len(measured_values)},
    )


def handle_gate_concern_scoring(context: StepExecutionContext) -> StepExecutionResult:
    hypothesis = context.request.hypothesis
    if hypothesis is None or hypothesis.pre_registered_concerns is None:
        return StepExecutionResult(
            outputs={"concern_scores": []},
            summary={"skipped": True, "reason": "no hypothesis"},
        )

    evaluation_step_id = _find_predecessor_step_id(context, "gate_evaluation")
    eval_out = dict(context.state.get("step_outputs", {}).get(evaluation_step_id, {}))
    rule_table: list[dict[str, Any]] = list(eval_out.get("criteria_results", []))
    measured_values: dict[str, Any] = dict(eval_out.get("measured_values", {}))
    if not rule_table:
        raise ValueError(
            "gate_concern_scoring requires the predecessor gate_evaluation step to produce criteria_results"
        )

    artifact_path = context.step_dir / "gate_concern_scores.json"
    template_path = context.step_dir / "gate_concern_scores_template.json"
    if not context.resumed:
        template = _build_concern_scores_template(context, rule_table, measured_values)
        write_json(template_path, template)
        return StepExecutionResult(
            outputs={"template_path": str(template_path.resolve())},
            artifacts=[str(template_path.resolve())],
            summary={"state": "waiting_for_concern_scores"},
            status="pause_for_input",
            pending_input=PauseForInputPayload(
                artifact_path=str(artifact_path.resolve()),
                schema_id="gate_concern_scores_v1",
                description="LLM or human must score the 4 pre-registered concerns against measured evidence",
                template_path=str(template_path.resolve()),
                expected_fields=("scores",),
            ),
        )

    resumed_payload = dict(context.state.get("resumed_inputs", {}).get(context.step.step_id, {}))
    if not resumed_payload:
        raise ValueError("gate_concern_scoring resumed without resumed_inputs payload")
    scores_raw: list[dict[str, Any]] = list(resumed_payload.get("scores", []))
    rule_by_id = {
        str(row.get("rule_id") or row.get("rule", "")): dict(row)
        for row in rule_table
        if str(row.get("rule_id") or row.get("rule", "")).strip()
    }

    for score in scores_raw:
        concern_id = str(score["concern_id"])
        rule_id = str(score["keyed_to_rule_id"])
        if rule_id not in rule_by_id:
            raise ConcernEnforcementError(
                f"concern {concern_id}: keyed_to_rule_id '{rule_id}' not in rule table"
            )
        rule_row = rule_by_id[rule_id]
        required_metric = str(rule_row.get("metric") or "")
        if not required_metric:
            raise ConcernEnforcementError(
                f"concern {concern_id}: rule '{rule_id}' has no metric field"
            )
        if required_metric not in score["quantitative_anchor"]:
            raise ConcernEnforcementError(
                f"concern {concern_id}: quantitative_anchor must contain the keyed rule metric '{required_metric}'"
            )
        anchor_value = score["quantitative_anchor"][required_metric]
        if not isinstance(anchor_value, (int, float)):
            raise ConcernEnforcementError(
                f"concern {concern_id}: anchor[{required_metric}] must be numeric"
            )
        actual_measured = measured_values.get(required_metric)
        if actual_measured is not None and abs(float(anchor_value) - float(actual_measured)) > 1e-6:
            raise ConcernEnforcementError(
                f"concern {concern_id}: anchor[{required_metric}]={anchor_value} does not match measured value {actual_measured}"
            )
        derived = derive_severity(rule_row, score["quantitative_anchor"])
        declared = str(score["severity"])
        if _severity_rank(declared) < _severity_rank(derived):
            raise ConcernEnforcementError(
                f"concern {concern_id}: declared severity '{declared}' is lower than derived severity '{derived}'"
            )

    write_json(artifact_path, resumed_payload)
    return StepExecutionResult(
        outputs={"concern_scores": scores_raw},
        artifacts=[str(artifact_path.resolve())],
        summary={"state": "scored", "count": len(scores_raw)},
    )


def handle_gate_review(context: StepExecutionContext) -> StepExecutionResult:
    hypothesis = context.request.hypothesis
    gate_stage = _gate_stage(context)
    eval_step_id = _find_predecessor_step_id(context, "gate_evaluation")
    eval_outputs = dict(context.state.get("step_outputs", {}).get(eval_step_id, {}))
    previous_outputs = dict(context.state.get("step_outputs", {}).get(context.step.step_id, {}))
    measured_values = dict(eval_outputs.get("measured_values", {}))
    criteria_results = list(eval_outputs.get("criteria_results", []))
    gate_id = str(context.step.step_id)
    decision_path = _gate_decision_path(context.step_dir)
    decision_payload = _load_gate_decision(context.step_dir)
    decision = _normalize_gate_decision(decision_payload.get("decision", ""))
    automated_verdict = compute_automated_verdict(criteria_results)
    measurement_event_id = str(previous_outputs.get("measurement_event_id", "") or "")

    if hypothesis is not None:
        registry = HypothesisRegistryStore(context.registry_dirs["hypothesis_registry_dir"])
        registry.register(hypothesis)
        registry.save()

    concern_rows = _load_concern_scores_from_outputs(context)
    payload = {
        "identity": {
            "gate_id": gate_id,
            "hypothesis_id": hypothesis.hypothesis_id if hypothesis is not None else "",
            "design_hash": hypothesis.design_hash() if hypothesis is not None else "",
            "profile_id": context.profile.profile_id,
            "gate_stage": gate_stage,
            "run_dir": str(context.run_dir),
        },
        "pre_committed_rule_table": criteria_results,
        "measured_values": measured_values,
        "pre_registered_concerns": concern_rows,
        "verdict": {
            "state": "waiting_for_human_gate" if not decision else "decision_recorded",
            "automated_verdict": automated_verdict,
            "decision": decision,
            "decision_by": str(decision_payload.get("decision_by", "") or ""),
            "reason": str(decision_payload.get("reason", "") or ""),
        },
        "next_action": {
            "required_action": (
                "Run hypothesis_cli.py approve|reject|quarantine, then resume the orchestrator run."
                if not decision
                else "Decision recorded. Resume is allowed."
            ),
            "decision_path": str(decision_path.resolve()),
        },
    }
    artifact_paths = write_gate_report(context.step_dir, payload)
    gate_payload = {
        "gate_id": gate_id,
        "gate_stage": gate_stage,
        "decision_path": str(decision_path.resolve()),
        **artifact_paths,
    }

    if hypothesis is not None and not measurement_event_id:
        ledger = TestingLedgerStore(context.registry_dirs["testing_ledger_dir"])
        run_id = hashlib.sha256(f"{context.run_dir}|{gate_id}".encode("utf-8")).hexdigest()[:16]
        primary_metric = (
            hypothesis.expected_effect.statistic
            if hypothesis.expected_effect is not None
            else next(iter(measured_values.keys()), "gate_review")
        )
        measurement = ledger.record_event(
            hypothesis_id=hypothesis.hypothesis_id,
            design_hash=hypothesis.design_hash(),
            prose_hash=hypothesis.prose_hash(),
            structural_family=hypothesis.structural_family(),
            economic_family=hypothesis.economic_family(),
            profile_id=context.profile.profile_id,
            run_id=run_id,
            run_dir=str(context.run_dir),
            test_name=f"gate:{gate_id}",
            stage=gate_stage,
            statistic_name=str(primary_metric),
            statistic_value=measured_values.get(str(primary_metric)),
            p_value=measured_values.get("monotonicity_pvalue"),
            n_obs=measured_values.get("report_row_count"),
            sharpe=measured_values.get("sharpe"),
            # jolly-seeking-lollipop Gate D.0: read cost from prescription if
            # present (validation profile); fall back to legacy 10.0 for
            # discovery profiles whose hypotheses don't carry a prescription.
            cost_bps_assumed=(
                float(hypothesis.prescription.cost_model.slippage_bps)
                if hypothesis is not None and hypothesis.prescription is not None
                else 10.0
            ),
            notes=str(decision_payload.get("reason", "") or ""),
            event_kind="measurement",
        )
        measurement_event_id = str(measurement["event_id"])

    if not decision:
        return StepExecutionResult(
            outputs={
                "gate_id": gate_id,
                "gate_stage": gate_stage,
                "measured_values": measured_values,
                "criteria_results": criteria_results,
                "verdict": payload["verdict"],
                "decision": "",
                "measurement_event_id": measurement_event_id,
            },
            artifacts=list(artifact_paths.values()),
            summary={"gate_stage": gate_stage, "state": "waiting_for_human_gate"},
            status="pause_for_gate",
            gate=gate_payload,
        )

    if hypothesis is not None:
        ledger = TestingLedgerStore(context.registry_dirs["testing_ledger_dir"])
        run_id = hashlib.sha256(f"{context.run_dir}|{gate_id}".encode("utf-8")).hexdigest()[:16]
        if measurement_event_id:
            ledger.record_verdict(
                related_event_id=measurement_event_id,
                design_hash=hypothesis.design_hash(),
                verdict=decision,
                decision_by=str(decision_payload.get("decision_by", "") or ""),
                reason=str(decision_payload.get("reason", "") or ""),
                run_id=run_id,
                run_dir=str(context.run_dir),
            )
        if decision == "quarantined":
            context.state["publish_status_override"] = "under_review"

    return StepExecutionResult(
        outputs={
            "gate_id": gate_id,
            "gate_stage": gate_stage,
            "measured_values": measured_values,
            "criteria_results": criteria_results,
            "verdict": payload["verdict"],
            "decision": decision,
            "measurement_event_id": measurement_event_id,
        },
        artifacts=list(artifact_paths.values()),
        summary={"gate_stage": gate_stage, "decision": decision, "automated_verdict": automated_verdict},
        gate=gate_payload,
    )


def handle_registry_publish(context: StepExecutionContext) -> StepExecutionResult:
    return StepExecutionResult(
        outputs={
            "produced_objects": list(context.state.get("produced_objects", [])),
            "registry_payloads": dict(context.state.get("registry_payloads", {})),
        },
        summary={
            "produced_object_count": len(context.state.get("produced_objects", [])),
            "registry_payload_keys": sorted(context.state.get("registry_payloads", {}).keys()),
        },
    )


def handle_performance_diagnostics(context: StepExecutionContext) -> StepExecutionResult:
    step_outputs = dict(context.state.get("step_outputs", {}))
    outputs: dict[str, Any] = {
        "run_dir": str(context.run_dir),
        "effective_capabilities": context.effective_capabilities,
        "effective_capability_metadata": context.effective_capability_metadata,
    }
    if context.profile.profile_id == "theme_strategy":
        outputs.update(
            {
                "ranking": step_outputs.get("event_driven_backtest", {}).get(
                    "ranking",
                    step_outputs.get("signal_search", {}).get("ranking", []),
                ),
                "theme_stage": step_outputs.get("event_driven_backtest", {}).get(
                    "theme_stage",
                    step_outputs.get("signal_search", {}).get("theme_stage", ""),
                ),
            }
        )
    elif context.profile.profile_id == "event_driven_signal_research":
        outputs.update(
            {
                "signal_search": step_outputs.get("signal_search", {}),
                "event_driven_backtest": step_outputs.get("event_driven_backtest", {}),
            }
        )
    elif context.profile.profile_id == "factor_screening":
        report_df = _load_csv_if_exists(context.run_dir / "factor_screening_report.csv")
        outputs.update(
            {
                "factor_count": int(len(report_df)),
                "screening_metadata": load_screening_metadata(context.run_dir),
                "factor_registry_import": context.state.get("registry_payloads", {}).get("factor_registry_import", {}),
            }
        )
    elif context.profile.profile_id == "ml_signal_model_research":
        metadata = _load_json_if_exists(context.run_dir / "run_metadata.json")
        variant_summary = _load_csv_if_exists(context.run_dir / "variant_comparison_summary.csv")
        outputs.update(
            {
                "best_ml_summary": metadata.get("best_ml_summary", {}),
                "adoption_recommendation": metadata.get("adoption_recommendation", ""),
                "variant_count": int(len(variant_summary)),
            }
        )
    elif context.profile.profile_id == "strategy_improvement":
        metadata = _load_json_if_exists(context.run_dir / "run_metadata.json")
        variant_summary = _load_csv_if_exists(context.run_dir / "variant_comparison_summary.csv")
        outputs.update(
            {
                "best_variant": metadata.get("best_variant", {}),
                "variant_count": int(len(variant_summary)),
            }
        )
    elif context.profile.profile_id == "benchmark_audit":
        metadata = _load_json_if_exists(context.run_dir / "run_metadata.json")
        outputs.update({"audit_result": metadata.get("audit_result", {})})
    return StepExecutionResult(
        outputs={"diagnostics": outputs},
        summary={"output_keys": sorted(outputs.keys())},
    )


def handle_report_render(context: StepExecutionContext) -> StepExecutionResult:
    files = collect_artifact_manifest(context.run_dir)
    return StepExecutionResult(
        outputs={"artifact_count": len(files)},
        summary={"artifact_count": len(files)},
    )


HANDLER_REGISTRY = {
    "noop": handle_noop,
    "object_resolver": handle_object_resolver,
    "screening_dataset_build": handle_screening_dataset_build,
    "screening_factor_discovery": handle_screening_factor_discovery,
    "screening_vectorized_backtest": handle_screening_vectorized_backtest,
    "screening_registry_publish": handle_screening_registry_publish,
    "theme_dataset_build": handle_theme_dataset_build,
    "theme_universe_builder": handle_theme_universe_builder,
    "theme_factor_construction": handle_theme_factor_construction,
    "theme_factor_discovery": handle_theme_factor_discovery,
    "theme_signal_search": handle_theme_signal_search,
    "theme_vectorized_backtest": handle_theme_vectorized_backtest,
    "theme_event_driven_backtest": handle_theme_event_driven_backtest,
    "theme_execution_validation": handle_theme_execution_validation,
    "theme_registry_publish": handle_theme_registry_publish,
    "event_dataset_build": handle_event_dataset_build,
    "event_signal_search": handle_event_signal_search,
    "event_portfolio_construction": handle_event_portfolio_construction,
    "event_backtest": handle_event_backtest,
    "event_execution_validation": handle_event_execution_validation,
    "event_registry_publish": handle_event_registry_publish,
    "ml_dataset_build": handle_ml_dataset_build,
    "ml_label_builder": handle_ml_label_builder,
    "ml_model_training": handle_ml_model_training,
    "ml_signal_search": handle_ml_signal_search,
    "ml_portfolio_construction": handle_ml_portfolio_construction,
    "ml_event_backtest": handle_ml_event_backtest,
    "ml_execution_validation": handle_ml_execution_validation,
    "ml_experiment_tracking": handle_ml_experiment_tracking,
    "ml_registry_publish": handle_ml_registry_publish,
    "improvement_dataset_build": handle_improvement_dataset_build,
    "improvement_portfolio_construction": handle_improvement_portfolio_construction,
    "improvement_risk_overlay": handle_improvement_risk_overlay,
    "improvement_stress_test": handle_improvement_stress_test,
    "improvement_event_backtest": handle_improvement_event_backtest,
    "improvement_execution_validation": handle_improvement_execution_validation,
    "improvement_registry_publish": handle_improvement_registry_publish,
    "benchmark_audit_step": handle_benchmark_audit_step,
    "gate_evaluation": handle_gate_evaluation,
    "gate_concern_scoring": handle_gate_concern_scoring,
    "gate_review": handle_gate_review,
    "registry_publish": handle_registry_publish,
    "performance_diagnostics": handle_performance_diagnostics,
    "report_render": handle_report_render,
    # jolly-seeking-lollipop Gate B: hypothesis_validation profile handlers.
    # Stubs land here in Gate B; real logic lands in Gates C-F.
    "validation_object_resolver": _validation_handle_object_resolver,
    "validation_dataset_build": _validation_handle_dataset_build,
    "validation_portfolio_construction": _validation_handle_portfolio_construction,
    "validation_vectorized_backtest_is": _validation_handle_vectorized_backtest_is,
    "validation_event_backtest_is": _validation_handle_event_backtest_is,
    "validation_event_backtest_oos": _validation_handle_event_backtest_oos,
    "validation_performance_diagnostics": _validation_handle_performance_diagnostics,
    "validation_gate_eval_oos": _validation_handle_gate_eval_oos,
    "validation_gate_concerns_oos": _validation_handle_gate_concerns_oos,
    "validation_gate_review_oos": _validation_handle_gate_review_oos,
    "validation_registry_publish": _validation_handle_registry_publish,
    # factor_lifecycle plan Phase 5 (slices 2-6: resolver/dataset/walk-forward/publish).
    "factor_lifecycle_object_resolver": _factor_lifecycle_handle_object_resolver,
    "factor_lifecycle_dataset_build": _factor_lifecycle_handle_dataset_build,
    "factor_lifecycle_walk_forward": _factor_lifecycle_handle_walk_forward,
    "factor_lifecycle_registry_publish": _factor_lifecycle_handle_registry_publish,
}
