from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd

from src.alpha_research.factor_library.catalog import get_composite_defs
from src.alpha_research.hypothesis_registry import HypothesisRegistryStore
from src.research_orchestrator.capabilities import describe_capabilities, validate_capabilities
from src.research_orchestrator.dag import CompiledResearchDag, DagStepSpec, StepExecutionContext
from src.research_orchestrator.hypothesis import validate_success_criteria_floor_rails
from src.research_orchestrator.profiles import ProfileRegistry, ResearchProfile
from src.research_orchestrator.registries.typed_store import TypedObjectSnapshot
from src.research_orchestrator.resolver import ResolverHub
from src.research_orchestrator.runtime import (
    execute_dag,
    load_run_plan,
    load_run_state,
    write_root_artifacts,
)
from src.research_orchestrator.schema import AssetRef, ResearchRequest, ResearchRunResult
from src.research_orchestrator.steps import HANDLER_REGISTRY


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_ROOT = PROJECT_ROOT / "data"
DEFAULT_FACTOR_REGISTRY_DIR = DEFAULT_REGISTRY_ROOT / "factor_registry"
DEFAULT_CANDIDATE_REGISTRY_DIR = DEFAULT_REGISTRY_ROOT / "candidate_registry"
DEFAULT_SIGNAL_REGISTRY_DIR = DEFAULT_REGISTRY_ROOT / "signal_registry"
DEFAULT_MODEL_REGISTRY_DIR = DEFAULT_REGISTRY_ROOT / "model_registry"
DEFAULT_STRATEGY_REGISTRY_DIR = DEFAULT_REGISTRY_ROOT / "strategy_registry"
DEFAULT_HYPOTHESIS_REGISTRY_DIR = DEFAULT_REGISTRY_ROOT / "hypothesis_registry"
DEFAULT_TESTING_LEDGER_DIR = DEFAULT_REGISTRY_ROOT / "testing_ledger"
DEFAULT_HOLDOUT_SEAL_DIR = DEFAULT_REGISTRY_ROOT / "holdout_seals"
DEFAULT_HYPOTHESIS_FACTOR_DIR = DEFAULT_REGISTRY_ROOT / "hypothesis_factors"


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _definition_hash(prefix: str, payload: dict[str, Any]) -> str:
    return _sha256_text(f"{prefix}|{_json_dumps(payload)}")


def _stable_object_id(prefix: str, payload: dict[str, Any]) -> str:
    return f"{prefix}::{_definition_hash(prefix, payload)[:16]}"


def _coerce_run_dir(path_like: Any) -> Path:
    return Path(str(path_like)).resolve()


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_optional_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _summarize_event_report(path: str | Path) -> dict[str, Any]:
    df = _load_optional_csv(path)
    if df.empty:
        return {
            "return": None,
            "max_drawdown": None,
            "turnover": None,
            "blocked_order_ratio": None,
            "trade_count": 0,
        }
    returns = df["return"].astype(float) if "return" in df.columns else pd.Series(dtype=float)
    cumulative = float(returns.add(1.0).prod() - 1.0) if not returns.empty else None
    running = returns.add(1.0).cumprod() if not returns.empty else pd.Series(dtype=float)
    max_drawdown = float((running / running.cummax() - 1.0).min()) if not running.empty else None
    turnover = float(df["turnover"].astype(float).mean()) if "turnover" in df.columns else None
    blocked = (
        float(df["blocked_order_ratio"].astype(float).mean())
        if "blocked_order_ratio" in df.columns
        else None
    )
    trade_count = int(df["trade_count"].astype(float).sum()) if "trade_count" in df.columns else int(len(df))
    return {
        "return": cumulative,
        "max_drawdown": max_drawdown,
        "turnover": turnover,
        "blocked_order_ratio": blocked,
        "trade_count": trade_count,
    }


def _current_file_count(run_dir: str | Path) -> int:
    root = Path(run_dir)
    if not root.exists():
        return 0
    return sum(1 for item in root.rglob("*") if item.is_file())


def _composite_name_set() -> set[str]:
    return {str(item.get("name", "")).strip() for item in get_composite_defs()}


def _build_factor_assets(factor_names: list[str]) -> list[AssetRef]:
    composite_names = _composite_name_set()
    assets: list[AssetRef] = []
    for name in factor_names:
        factor = str(name).strip()
        if not factor:
            continue
        assets.append(
            AssetRef(
                object_type="composite_factor" if factor in composite_names else "factor",
                object_name=factor,
            )
        )
    return assets


def _registry_root_from_run_context(run_context: dict[str, Any]) -> Path:
    if run_context.get("registry_root"):
        return Path(str(run_context["registry_root"])).resolve()
    return DEFAULT_REGISTRY_ROOT.resolve()


def _resolve_registry_dirs(run_context: dict[str, Any]) -> dict[str, Path]:
    registry_root = _registry_root_from_run_context(run_context)
    return {
        "factor_registry_dir": Path(
            str(run_context.get("factor_registry_dir", registry_root / "factor_registry"))
        ).resolve(),
        "candidate_registry_dir": Path(
            str(run_context.get("candidate_registry_dir", registry_root / "candidate_registry"))
        ).resolve(),
        "signal_registry_dir": Path(
            str(run_context.get("signal_registry_dir", registry_root / "signal_registry"))
        ).resolve(),
        "model_registry_dir": Path(
            str(run_context.get("model_registry_dir", registry_root / "model_registry"))
        ).resolve(),
        "strategy_registry_dir": Path(
            str(run_context.get("strategy_registry_dir", registry_root / "strategy_registry"))
        ).resolve(),
        "hypothesis_registry_dir": Path(
            str(run_context.get("hypothesis_registry_dir", registry_root / "hypothesis_registry"))
        ).resolve(),
        "testing_ledger_dir": Path(
            str(run_context.get("testing_ledger_dir", registry_root / "testing_ledger"))
        ).resolve(),
        "holdout_seal_dir": Path(
            str(run_context.get("holdout_seal_dir", registry_root / "holdout_seals"))
        ).resolve(),
        "hypothesis_factor_dir": Path(
            str(run_context.get("hypothesis_factor_dir", registry_root / "hypothesis_factors"))
        ).resolve(),
    }


def _canonical_request_payload(request: ResearchRequest) -> dict[str, Any]:
    payload = request.to_dict()
    run_context = dict(payload.get("run_context", {}))
    # resume_policy controls runtime behavior, not the logical research definition.
    run_context.pop("resume_policy", None)
    payload["run_context"] = run_context
    if request.hypothesis is not None:
        request.hypothesis.validate()
        payload["hypothesis"] = {
            "design_hash": request.hypothesis.design_hash(),
        }
    return payload


def _effective_capabilities(profile: ResearchProfile, request: ResearchRequest) -> list[str]:
    merged = list(profile.default_capabilities) + list(request.requested_capabilities)
    return validate_capabilities(merged)


def _load_base_metadata(run_dir: str | Path) -> dict[str, Any]:
    path = Path(run_dir) / "run_metadata.json"
    if not path.exists():
        return {}
    return _load_json(path)


def _build_lineage_links(
    *,
    request: ResearchRequest,
    resolution: dict[str, Any],
    produced_objects: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    resolved_objects = resolution.get("resolved_objects", [])
    for produced in produced_objects:
        target_id = str(produced.get("object_id", "") or "")
        target_type = str(produced.get("object_type", "") or "")
        if not target_id:
            continue
        for resolved in resolved_objects:
            source_id = str(resolved.get("canonical_id", "") or "")
            if not source_id:
                continue
            links.append(
                {
                    "source_id": source_id,
                    "source_type": resolved.get("object_type", ""),
                    "source_layer": resolved.get("source_layer", ""),
                    "source_version": resolved.get("version"),
                    "target_id": target_id,
                    "target_type": target_type,
                    "relationship": "consumed_by",
                }
            )
        for consume in request.consumes:
            if consume.object_name:
                links.append(
                    {
                        "source_id": consume.object_id or consume.object_name,
                        "source_type": consume.object_type,
                        "source_layer": "request",
                        "source_version": consume.version,
                        "target_id": target_id,
                        "target_type": target_type,
                        "relationship": "requested_by",
                    }
                )
    return links


def _build_review_summary(
    *,
    request: ResearchRequest,
    registry_resolution: dict[str, Any],
    produced_objects: list[dict[str, Any]],
    outputs: dict[str, Any],
) -> dict[str, Any]:
    return {
        "profile_id": request.profile_id,
        "mode": request.mode,
        "effective_capabilities": outputs.get("effective_capabilities", []),
        "effective_capability_metadata": outputs.get("effective_capability_metadata", []),
        "formal_hits": int(registry_resolution.get("formal_hits", 0)),
        "candidate_hits": int(registry_resolution.get("candidate_hits", 0)),
        "new_objects_created": int(registry_resolution.get("new_objects_created", 0)),
        "unresolved_count": int(len(registry_resolution.get("unresolved_objects", []))),
        "produced_object_count": int(len(produced_objects)),
        "run_dir": str(outputs.get("run_dir", "")),
    }


def _validate_request_against_profile(request: ResearchRequest, profile: ResearchProfile) -> None:
    if request.hypothesis is not None:
        request.hypothesis.validate()
        registry_dirs = _resolve_registry_dirs(request.run_context)
        allow_override = False
        registry = HypothesisRegistryStore(registry_dirs["hypothesis_registry_dir"])
        allow_override = registry.has_manual_override(request.hypothesis.design_hash(), "floor_rails_relaxed:")
        validate_success_criteria_floor_rails(
            request.hypothesis,
            profile.profile_id,
            allow_override=allow_override,
        )
    if request.mode == "formal" and profile.profile_id != "benchmark_audit" and request.hypothesis is None:
        raise ValueError(f"Formal profile {profile.profile_id} requires a hypothesis.")
    unsupported_modes = set([request.mode]) - set(profile.supported_modes)
    if unsupported_modes:
        raise ValueError(
            f"Profile {profile.profile_id} does not support mode(s): {sorted(unsupported_modes)}"
        )
    unsupported_consumes = sorted(
        {item.object_type for item in request.consumes} - set(profile.consumes_types)
    )
    if unsupported_consumes:
        raise ValueError(
            f"Profile {profile.profile_id} does not consume object type(s): {unsupported_consumes}"
        )
    unsupported_produces = sorted(
        {item.object_type for item in request.produces} - set(profile.produces_types)
    )
    if request.mode == "formal" and unsupported_produces:
        raise ValueError(
            f"Profile {profile.profile_id} cannot produce object type(s): {unsupported_produces}"
        )


def _publish_typed_objects(
    *,
    store,
    run_type: str,
    research_profile: str,
    run_dir: str | Path,
    generated_at: str,
    objects: list[TypedObjectSnapshot],
    summaries_by_object_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not objects:
        return {"run_id": "", "object_count": 0, "object_ids": []}
    result = store.publish_objects(
        run_type=run_type,
        research_profile=research_profile,
        run_dir=run_dir,
        generated_at=generated_at,
        objects=objects,
        summaries_by_object_id=summaries_by_object_id,
        artifact_count=_current_file_count(run_dir),
    )
    store.save()
    return result


def _namespace_to_dict(args: argparse.Namespace) -> dict[str, Any]:
    return {key: getattr(args, key) for key in vars(args)}


def _screening_argv_from_namespace(args: argparse.Namespace) -> list[str]:
    argv: list[str] = [
        "--start",
        str(args.start),
        "--end",
        str(args.end),
        "--outdir",
        str(args.outdir),
        "--engine",
        str(args.engine),
        "--cache-mode",
        str(args.cache_mode),
        "--cache-dir",
        str(args.cache_dir),
        "--screen-checkpoint-every",
        str(args.screen_checkpoint_every),
        "--screen-progress-every",
        str(args.screen_progress_every),
    ]
    if getattr(args, "include_new_data", True):
        argv.append("--include-new-data")
    else:
        argv.append("--exclude-new-data")
    if getattr(args, "kernels", None) is not None:
        argv.extend(["--kernels", str(args.kernels)])
    for horizon in list(args.horizon):
        argv.extend(["--horizon", str(horizon)])
    return argv


def _build_factor_screening_request_from_args(args: argparse.Namespace) -> ResearchRequest:
    return ResearchRequest(
        profile_id="factor_screening",
        mode="formal",
        consumes=[],
        produces=[],
        requested_capabilities=[],
        inputs={
            "argv": _screening_argv_from_namespace(args),
            "args": _namespace_to_dict(args),
            "output_dir": str(Path(args.outdir).resolve()),
        },
        run_context={},
    )


def _build_theme_request_from_args(args: argparse.Namespace) -> ResearchRequest:
    import src.alpha_research.theme_strategy.cli as theme_cli

    candidate_dir = Path(theme_cli.DEFAULT_CANDIDATE_REGISTRY_DIR).resolve()
    registry_root = candidate_dir.parent
    return ResearchRequest(
        profile_id="theme_strategy",
        mode=str(getattr(args, "mode", "formal") or "formal"),
        consumes=[],
        produces=[],
        requested_capabilities=[],
        inputs={
            "theme": args.theme,
            "stage": args.stage,
            "output_dir": str(theme_cli.resolve_output_dir(args.output_dir, args.theme, args.stage)),
            "recipe_source_run_dir": str(Path(args.recipe_source_run_dir).resolve()) if getattr(args, "recipe_source_run_dir", None) else "",
        },
        run_context={
            "registry_root": str(registry_root),
            "candidate_registry_dir": str(candidate_dir),
            "signal_registry_dir": str((registry_root / "signal_registry").resolve()),
        },
    )


def _build_event_request_from_args(args: argparse.Namespace) -> ResearchRequest:
    from workspace.research.alpha_mining.event_driven_strategy_research import resolve_output_dir

    screening_run_dir = Path(args.screening_run_dir).resolve()
    candidate_df = pd.read_csv(screening_run_dir / "factor_screening_report.csv")
    if "grade" in candidate_df.columns:
        candidate_df = candidate_df[
            candidate_df["grade"].astype(str).str.startswith(("A", "B"))
        ].copy()
    factor_names = candidate_df["factor"].astype(str).str.strip().tolist()
    if getattr(args, "max_factors", None):
        factor_names = factor_names[: int(args.max_factors)]
    return ResearchRequest(
        profile_id="event_driven_signal_research",
        mode=str(getattr(args, "mode", "formal") or "formal"),
        consumes=_build_factor_assets(factor_names),
        produces=[],
        requested_capabilities=[],
        inputs={
            **_namespace_to_dict(args),
            "screening_run_dir": str(screening_run_dir),
            "output_dir": str(resolve_output_dir(SimpleNamespace(**_namespace_to_dict(args))).resolve()),
        },
        run_context={},
    )


def _build_ml_request_from_args(args: argparse.Namespace) -> ResearchRequest:
    from workspace.research.alpha_mining.event_driven_strategy_ml_research import resolve_output_dir

    baseline_run_dir = Path(args.baseline_run_dir).resolve()
    metadata = _load_json(baseline_run_dir / "run_metadata.json")
    factor_names = [str(item).strip() for item in metadata.get("candidate_factors", []) if str(item).strip()]
    return ResearchRequest(
        profile_id="ml_signal_model_research",
        mode=str(getattr(args, "mode", "formal") or "formal"),
        consumes=_build_factor_assets(factor_names),
        produces=[],
        requested_capabilities=[],
        inputs={
            **_namespace_to_dict(args),
            "baseline_run_dir": str(baseline_run_dir),
            "screening_run_dir": str(Path(args.screening_run_dir).resolve()),
            "output_dir": str(resolve_output_dir(SimpleNamespace(**_namespace_to_dict(args))).resolve()),
        },
        run_context={},
    )


def _build_improvement_request_from_args(args: argparse.Namespace) -> ResearchRequest:
    from workspace.research.alpha_mining.event_driven_strategy_improvement import resolve_output_dir

    baseline_run_dir = Path(args.baseline_run_dir).resolve()
    metadata = _load_json(baseline_run_dir / "run_metadata.json")
    factor_names = [str(item).strip() for item in metadata.get("candidate_factors", []) if str(item).strip()]
    return ResearchRequest(
        profile_id="strategy_improvement",
        mode="formal",
        consumes=_build_factor_assets(factor_names),
        produces=[],
        requested_capabilities=[],
        inputs={
            **_namespace_to_dict(args),
            "baseline_run_dir": str(baseline_run_dir),
            "output_dir": str(resolve_output_dir(SimpleNamespace(**_namespace_to_dict(args))).resolve()),
        },
        run_context={},
    )


def _build_audit_request_from_args(*, benchmark: str, output_dir: Path) -> ResearchRequest:
    return ResearchRequest(
        profile_id="benchmark_audit",
        mode="formal",
        consumes=[],
        produces=[],
        requested_capabilities=[],
        inputs={"benchmark": str(benchmark), "output_dir": str(output_dir.resolve())},
        run_context={},
    )


def _event_signal_payload(metadata: dict[str, Any], selected_by_fold: pd.DataFrame) -> dict[str, Any]:
    selected_payload = (
        selected_by_fold.sort_values(["fold_id", "selection_rank", "factor"]).to_dict(orient="records")
        if not selected_by_fold.empty
        else []
    )
    return {
        "source_profile": "event_driven_signal_research",
        "screening_run_dir": str(metadata.get("screening_run_dir", "")),
        "candidate_factors": list(metadata.get("candidate_factors", [])),
        "selected_core_factors_by_fold": selected_payload,
        "benchmark": metadata.get("benchmark"),
        "topk": metadata.get("topk"),
        "rebalance_days": metadata.get("rebalance_days"),
        "adv_median_floor": metadata.get("adv_median_floor"),
        "participation_cap": metadata.get("participation_cap"),
        "strategy_horizon": metadata.get("strategy_horizon"),
    }


def _request_run_dir(request: ResearchRequest) -> Path:
    output_dir = str(request.inputs.get("output_dir", "") or "").strip()
    if not output_dir:
        raise ValueError(
            f"ResearchRequest.inputs['output_dir'] must be pre-resolved for profile {request.profile_id}"
        )
    return Path(output_dir).resolve()


def _build_linear_dag(
    *,
    profile_id: str,
    run_dir: Path,
    steps: list[Any],
    metadata: dict[str, Any] | None = None,
) -> CompiledResearchDag:
    dag_steps: list[DagStepSpec] = []
    prev_step_id = ""
    for item in steps:
        if isinstance(item, DagStepSpec):
            step = item
            dag_steps.append(step)
            prev_step_id = step.step_id
            continue
        if isinstance(item, dict):
            step_id = str(item["step_id"])
            capability = str(item["capability"])
            handler = str(item["handler"])
            depends_on = tuple(item.get("depends_on", (prev_step_id,) if prev_step_id else ()))
            config = dict(item.get("config", {}))
        else:
            step_id, capability, handler = item
            depends_on = (prev_step_id,) if prev_step_id else ()
            config = {}
        dag_steps.append(
            DagStepSpec(
                step_id=step_id,
                capability=capability,
                handler=handler,
                depends_on=depends_on,
                description=f"{profile_id}:{capability}",
                config=config,
            )
        )
        prev_step_id = step_id
    dag = CompiledResearchDag(
        profile_id=profile_id,
        run_dir=str(run_dir),
        steps=tuple(dag_steps),
        metadata=dict(metadata or {}),
    )
    dag.validate()
    return dag


def _inject_gate_sequence(steps: list[Any], *, stage: str = "is_only") -> list[Any]:
    updated = list(steps)
    filtered = [
        item for item in updated
        if (item["step_id"] if isinstance(item, dict) else item[0]) != "gate_review"
    ]
    publish_index = next(
        (index for index, item in enumerate(filtered) if (item["step_id"] if isinstance(item, dict) else item[0]) == "registry_publish"),
        None,
    )
    if publish_index is None:
        return filtered
    if publish_index == 0:
        raise ValueError("registry_publish cannot be the first step when injecting gate sequence")
    upstream_item = filtered[publish_index - 1]
    upstream_step_id = upstream_item["step_id"] if isinstance(upstream_item, dict) else upstream_item[0]
    gate_steps: list[dict[str, Any]] = [
        {
            "step_id": "gate_evaluation",
            "capability": "gate_evaluation",
            "handler": "gate_evaluation",
            "depends_on": (str(upstream_step_id),),
            "config": {"stage": stage},
        },
        {
            "step_id": "gate_concern_scoring",
            "capability": "gate_concern_scoring",
            "handler": "gate_concern_scoring",
            "depends_on": ("gate_evaluation",),
            "config": {"stage": stage},
        },
        {
            "step_id": "gate_review",
            "capability": "gate_review",
            "handler": "gate_review",
            "depends_on": ("gate_evaluation", "gate_concern_scoring"),
            "config": {"stage": stage},
        },
    ]
    return filtered[:publish_index] + gate_steps + filtered[publish_index:]


def _factor_screening_dag_builder(
    request: ResearchRequest,
    effective_capabilities: list[str],
) -> CompiledResearchDag:
    del effective_capabilities
    steps = _inject_gate_sequence(
        [
            ("data_scope", "data_scope", "noop"),
            ("data_readiness", "data_readiness", "noop"),
            ("dataset_build", "dataset_build", "screening_dataset_build"),
            ("factor_discovery", "factor_discovery", "screening_factor_discovery"),
            ("vectorized_backtest", "vectorized_backtest", "screening_vectorized_backtest"),
            ("performance_diagnostics", "performance_diagnostics", "performance_diagnostics"),
            ("gate_review", "gate_review", "gate_review"),
            ("registry_publish", "registry_publish", "screening_registry_publish"),
            ("report_render", "report_render", "report_render"),
        ],
        stage="is_only",
    )
    return _build_linear_dag(
        profile_id="factor_screening",
        run_dir=_request_run_dir(request),
        steps=steps,
        metadata={"requested_stage": "screening"},
    )


def _factor_lifecycle_dag_builder(
    request: ResearchRequest,
    effective_capabilities: list[str],
) -> CompiledResearchDag:
    """Phase 5: the factor-lifecycle draft->candidate gate. IS-ONLY — note the ABSENCE of
    any oos_test stage, OOS backtest, or holdout-seal claim (the candidate->approved OOS
    spend is a SEPARATE frozen-set / promotion-gate path, never this profile). The
    object_resolver step is EXPLICIT (formal_requires_resolver does NOT auto-inject it)."""
    del effective_capabilities
    steps = _inject_gate_sequence(
        [
            ("data_scope", "data_scope", "noop"),
            ("data_readiness", "data_readiness", "noop"),
            ("factor_lifecycle_object_resolver", "object_resolver", "factor_lifecycle_object_resolver"),
            ("factor_lifecycle_dataset_build", "dataset_build", "factor_lifecycle_dataset_build"),
            ("factor_lifecycle_walk_forward", "walk_forward_validation", "factor_lifecycle_walk_forward"),
            ("registry_publish", "registry_publish", "factor_lifecycle_registry_publish"),
            ("report_render", "report_render", "report_render"),
        ],
        stage="is_only",
    )
    return _build_linear_dag(
        profile_id="factor_lifecycle",
        run_dir=_request_run_dir(request),
        steps=steps,
        metadata={"requested_stage": "factor_lifecycle", "is_only": True},
    )


def _theme_strategy_dag_builder(
    request: ResearchRequest,
    effective_capabilities: list[str],
) -> CompiledResearchDag:
    del effective_capabilities
    stage = str(request.inputs.get("stage", "all") or "all").strip()
    has_recipe_source = bool(str(request.inputs.get("recipe_source_run_dir", "") or "").strip())
    if stage == "field_audit":
        steps = [
            ("data_scope", "data_scope", "noop"),
            ("data_readiness", "data_readiness", "noop"),
            ("dataset_build", "dataset_build", "theme_dataset_build"),
            ("report_render", "report_render", "report_render"),
        ]
    elif stage == "universe":
        steps = [
            ("data_scope", "data_scope", "noop"),
            ("data_readiness", "data_readiness", "noop"),
            ("dataset_build", "dataset_build", "theme_dataset_build"),
            ("universe_builder", "universe_builder", "theme_universe_builder"),
            ("report_render", "report_render", "report_render"),
        ]
    elif stage == "component":
        steps = [
            ("data_scope", "data_scope", "noop"),
            ("data_readiness", "data_readiness", "noop"),
            ("dataset_build", "dataset_build", "theme_dataset_build"),
            ("universe_builder", "universe_builder", "theme_universe_builder"),
            ("factor_construction", "factor_construction", "theme_factor_construction"),
            ("factor_discovery", "factor_discovery", "theme_factor_discovery"),
            ("report_render", "report_render", "report_render"),
        ]
    elif stage == "recipe":
        steps = [
            ("data_scope", "data_scope", "noop"),
            ("data_readiness", "data_readiness", "noop"),
            ("dataset_build", "dataset_build", "theme_dataset_build"),
            ("universe_builder", "universe_builder", "theme_universe_builder"),
            ("factor_construction", "factor_construction", "theme_factor_construction"),
            ("factor_discovery", "factor_discovery", "theme_factor_discovery"),
            ("signal_search", "signal_search", "theme_signal_search"),
            ("vectorized_backtest", "vectorized_backtest", "theme_vectorized_backtest"),
            ("performance_diagnostics", "performance_diagnostics", "performance_diagnostics"),
            ("report_render", "report_render", "report_render"),
        ]
    elif stage in {"event_driven", "all"} and has_recipe_source:
        steps = _inject_gate_sequence([
            ("data_scope", "data_scope", "noop"),
            ("data_readiness", "data_readiness", "noop"),
            ("event_driven_backtest", "event_driven_backtest", "theme_event_driven_backtest"),
            ("execution_validation", "execution_validation", "theme_execution_validation"),
            ("performance_diagnostics", "performance_diagnostics", "performance_diagnostics"),
            ("gate_review", "gate_review", "gate_review"),
            ("registry_publish", "registry_publish", "theme_registry_publish"),
            ("report_render", "report_render", "report_render"),
        ], stage="is_only")
    else:
        steps = _inject_gate_sequence([
            ("data_scope", "data_scope", "noop"),
            ("data_readiness", "data_readiness", "noop"),
            ("dataset_build", "dataset_build", "theme_dataset_build"),
            ("universe_builder", "universe_builder", "theme_universe_builder"),
            ("factor_construction", "factor_construction", "theme_factor_construction"),
            ("factor_discovery", "factor_discovery", "theme_factor_discovery"),
            ("signal_search", "signal_search", "theme_signal_search"),
            ("vectorized_backtest", "vectorized_backtest", "theme_vectorized_backtest"),
            ("event_driven_backtest", "event_driven_backtest", "theme_event_driven_backtest"),
            ("execution_validation", "execution_validation", "theme_execution_validation"),
            ("performance_diagnostics", "performance_diagnostics", "performance_diagnostics"),
            ("gate_review", "gate_review", "gate_review"),
            ("registry_publish", "registry_publish", "theme_registry_publish"),
            ("report_render", "report_render", "report_render"),
        ], stage="is_only")
    return _build_linear_dag(
        profile_id="theme_strategy",
        run_dir=_request_run_dir(request),
        steps=steps,
        metadata={"requested_stage": stage, "recipe_reuse": has_recipe_source},
    )


def _event_driven_signal_research_dag_builder(
    request: ResearchRequest,
    effective_capabilities: list[str],
) -> CompiledResearchDag:
    del effective_capabilities
    steps = _inject_gate_sequence(
        [
            ("object_resolver", "object_resolver", "object_resolver"),
            ("data_scope", "data_scope", "noop"),
            ("dataset_build", "dataset_build", "event_dataset_build"),
            ("signal_search", "signal_search", "event_signal_search"),
            ("portfolio_construction", "portfolio_construction", "event_portfolio_construction"),
            {"step_id": "event_driven_backtest", "capability": "event_driven_backtest", "handler": "event_backtest", "config": {"stage": "is_only"}},
            ("execution_validation", "execution_validation", "event_execution_validation"),
            ("performance_diagnostics", "performance_diagnostics", "performance_diagnostics"),
            ("gate_review", "gate_review", "gate_review"),
            ("registry_publish", "registry_publish", "event_registry_publish"),
            ("report_render", "report_render", "report_render"),
        ],
        stage="is_only",
    )
    return _build_linear_dag(
        profile_id="event_driven_signal_research",
        run_dir=_request_run_dir(request),
        steps=steps,
    )


def _ml_signal_model_research_dag_builder(
    request: ResearchRequest,
    effective_capabilities: list[str],
) -> CompiledResearchDag:
    del effective_capabilities
    steps = _inject_gate_sequence(
        [
            ("data_scope", "data_scope", "noop"),
            ("data_readiness", "data_readiness", "noop"),
            ("dataset_build", "dataset_build", "ml_dataset_build"),
            ("label_builder", "label_builder", "ml_label_builder"),
            ("object_resolver", "object_resolver", "object_resolver"),
            ("model_training", "model_training", "ml_model_training"),
            ("signal_search", "signal_search", "ml_signal_search"),
            ("portfolio_construction", "portfolio_construction", "ml_portfolio_construction"),
            {"step_id": "event_driven_backtest", "capability": "event_driven_backtest", "handler": "ml_event_backtest", "config": {"stage": "is_only"}},
            ("execution_validation", "execution_validation", "ml_execution_validation"),
            ("performance_diagnostics", "performance_diagnostics", "performance_diagnostics"),
            ("experiment_tracking", "experiment_tracking", "ml_experiment_tracking"),
            ("gate_review", "gate_review", "gate_review"),
            ("registry_publish", "registry_publish", "ml_registry_publish"),
            ("report_render", "report_render", "report_render"),
        ],
        stage="is_only",
    )
    return _build_linear_dag(
        profile_id="ml_signal_model_research",
        run_dir=_request_run_dir(request),
        steps=steps,
    )


def _strategy_improvement_dag_builder(
    request: ResearchRequest,
    effective_capabilities: list[str],
) -> CompiledResearchDag:
    del effective_capabilities
    steps = _inject_gate_sequence(
        [
            ("object_resolver", "object_resolver", "object_resolver"),
            ("data_scope", "data_scope", "noop"),
            ("dataset_build", "dataset_build", "improvement_dataset_build"),
            ("portfolio_construction", "portfolio_construction", "improvement_portfolio_construction"),
            ("risk_overlay", "risk_overlay", "improvement_risk_overlay"),
            ("stress_test", "stress_test", "improvement_stress_test"),
            {"step_id": "event_driven_backtest", "capability": "event_driven_backtest", "handler": "improvement_event_backtest", "config": {"stage": "is_only"}},
            ("execution_validation", "execution_validation", "improvement_execution_validation"),
            ("performance_diagnostics", "performance_diagnostics", "performance_diagnostics"),
            ("gate_review", "gate_review", "gate_review"),
            ("registry_publish", "registry_publish", "improvement_registry_publish"),
            ("report_render", "report_render", "report_render"),
        ],
        stage="is_only",
    )
    return _build_linear_dag(
        profile_id="strategy_improvement",
        run_dir=_request_run_dir(request),
        steps=steps,
    )


def _benchmark_audit_dag_builder(
    request: ResearchRequest,
    effective_capabilities: list[str],
) -> CompiledResearchDag:
    del effective_capabilities
    return _build_linear_dag(
        profile_id="benchmark_audit",
        run_dir=_request_run_dir(request),
        steps=[
            ("data_scope", "data_scope", "noop"),
            ("data_readiness", "data_readiness", "noop"),
            ("benchmark_audit", "benchmark_audit", "benchmark_audit_step"),
            ("report_render", "report_render", "report_render"),
        ],
    )


def _hypothesis_validation_dag_builder(
    request: ResearchRequest,
    effective_capabilities: list[str],
) -> CompiledResearchDag:
    """DAG for the hypothesis_validation profile (jolly-seeking-lollipop Gate B).

    Runs a fully-prescribed recipe verbatim through IS+gate+OOS+publish.
    Per Codex round-2 review:
    - All step_ids are unique (validation_*); the shared gate handlers are
      reused for IS via custom step_ids (handle_gate_evaluation /
      handle_gate_concern_scoring / handle_gate_review look up predecessors
      by capability, so depends_on must list BOTH the eval AND concerns step
      for gate_review).
    - OOS gate steps use WRAPPER handlers (handle_validation_gate_*_oos)
      that read the upstream IS gate decision and either delegate to the
      shared handler or emit a skipped result.
    - Stage config is set explicitly on every stage-sensitive step
      (handle_gate_review reads stage from context.step.config["stage"];
      Codex round-4 must-fix #1).
    - The DAG includes an explicit object_resolver step
      (formal_requires_resolver=True does NOT auto-add it; Codex round-2 #3).
    - Publish gates on validation_gate_review_oos (NOT IS gate);
      handle_validation_registry_publish enforces direct decision matrix
      (Codex round-3 critical, since _assert_gate_allows_publication falls
      through on unknown decisions).
    """
    del effective_capabilities
    if request.hypothesis is None:
        raise ValueError(
            "hypothesis_validation profile requires a hypothesis with a prescription"
        )
    if request.hypothesis.prescription is None:
        raise ValueError(
            "hypothesis_validation profile requires hypothesis.prescription "
            "to be set (a PrescribedRecipe). For discovery-style runs, use "
            "theme_strategy or event_driven_signal_research instead."
        )
    steps: list[Any] = [
        ("data_scope", "data_scope", "noop"),
        ("data_readiness", "data_readiness", "noop"),
        ("validation_object_resolver", "object_resolver", "validation_object_resolver"),
        ("validation_dataset_build", "dataset_build", "validation_dataset_build"),
        ("validation_portfolio_construction", "portfolio_construction", "validation_portfolio_construction"),
        {"step_id": "validation_vectorized_backtest_is", "capability": "vectorized_backtest", "handler": "validation_vectorized_backtest_is", "config": {"stage": "is_only"}},
        {"step_id": "validation_event_backtest_is", "capability": "event_driven_backtest", "handler": "validation_event_backtest_is", "config": {"stage": "is_only"}},
        # Diagnostics depends on BOTH the vectorized and event-driven backtests.
        {"step_id": "validation_diagnostics_is", "capability": "performance_diagnostics", "handler": "validation_performance_diagnostics", "config": {"stage": "is_only"}, "depends_on": ("validation_event_backtest_is", "validation_vectorized_backtest_is")},
        {"step_id": "validation_gate_eval_is", "capability": "gate_evaluation", "handler": "gate_evaluation", "config": {"stage": "is_only"}, "depends_on": ("validation_diagnostics_is",)},
        {"step_id": "validation_gate_concerns_is", "capability": "gate_concern_scoring", "handler": "gate_concern_scoring", "config": {"stage": "is_only"}, "depends_on": ("validation_gate_eval_is",)},
        # IS gate review depends on BOTH eval and concerns (capability lookup, Codex #1).
        {"step_id": "validation_gate_review_is", "capability": "gate_review", "handler": "gate_review", "config": {"stage": "is_only"}, "depends_on": ("validation_gate_eval_is", "validation_gate_concerns_is")},
        {"step_id": "validation_event_backtest_oos", "capability": "event_driven_backtest", "handler": "validation_event_backtest_oos", "config": {"stage": "oos_test"}, "depends_on": ("validation_gate_review_is",)},
        {"step_id": "validation_diagnostics_oos", "capability": "performance_diagnostics", "handler": "validation_performance_diagnostics", "config": {"stage": "oos_test"}, "depends_on": ("validation_event_backtest_oos",)},
        # OOS gate triplet uses WRAPPER handlers that skip-then-delegate based
        # on upstream IS gate decision (the shared handlers cannot self-skip).
        {"step_id": "validation_gate_eval_oos", "capability": "gate_evaluation", "handler": "validation_gate_eval_oos", "config": {"stage": "oos_test"}, "depends_on": ("validation_diagnostics_oos",)},
        {"step_id": "validation_gate_concerns_oos", "capability": "gate_concern_scoring", "handler": "validation_gate_concerns_oos", "config": {"stage": "oos_test"}, "depends_on": ("validation_gate_eval_oos",)},
        {"step_id": "validation_gate_review_oos", "capability": "gate_review", "handler": "validation_gate_review_oos", "config": {"stage": "oos_test"}, "depends_on": ("validation_gate_eval_oos", "validation_gate_concerns_oos")},
        {"step_id": "validation_registry_publish", "capability": "registry_publish", "handler": "validation_registry_publish", "depends_on": ("validation_gate_review_oos",)},
        {"step_id": "report_render", "capability": "report_render", "handler": "report_render", "depends_on": ("validation_registry_publish",)},
    ]
    return _build_linear_dag(
        profile_id="hypothesis_validation",
        run_dir=_request_run_dir(request),
        steps=steps,
    )


_PROFILE_REGISTRY = ProfileRegistry()


def register_profile(profile: ResearchProfile) -> None:
    _PROFILE_REGISTRY.register(profile)


def profile_registry() -> ProfileRegistry:
    return _PROFILE_REGISTRY


def _register_builtin_profiles() -> None:
    if _PROFILE_REGISTRY.all_profiles():
        return

    builtins = [
        ResearchProfile(
            profile_id="factor_screening",
            supported_modes=("sandbox", "formal"),
            consumes_types=(),
            produces_types=(),
            default_capabilities=(
                "dataset_build",
                "factor_discovery",
                "vectorized_backtest",
                "gate_review",
                "registry_publish",
            ),
            formal_requires_resolver=True,
            dag_builder=_factor_screening_dag_builder,
        ),
        ResearchProfile(
            profile_id="theme_strategy",
            supported_modes=("sandbox", "formal"),
            consumes_types=(),
            produces_types=("factor", "composite_factor", "signal"),
            default_capabilities=(
                "dataset_build",
                "universe_builder",
                "factor_construction",
                "factor_discovery",
                "signal_search",
                "vectorized_backtest",
                "event_driven_backtest",
                "execution_validation",
                "gate_review",
                "registry_publish",
            ),
            formal_requires_resolver=True,
            dag_builder=_theme_strategy_dag_builder,
        ),
        ResearchProfile(
            profile_id="event_driven_signal_research",
            supported_modes=("sandbox", "formal"),
            consumes_types=("factor", "composite_factor"),
            produces_types=("signal", "strategy_candidate", "composite_factor"),
            default_capabilities=(
                "object_resolver",
                "dataset_build",
                "signal_search",
                "portfolio_construction",
                "event_driven_backtest",
                "execution_validation",
                "gate_review",
                "registry_publish",
            ),
            formal_requires_resolver=True,
            dag_builder=_event_driven_signal_research_dag_builder,
        ),
        ResearchProfile(
            profile_id="ml_signal_model_research",
            supported_modes=("sandbox", "formal"),
            consumes_types=("factor", "composite_factor"),
            produces_types=("model", "signal", "strategy_candidate", "composite_factor"),
            default_capabilities=(
                "dataset_build",
                "label_builder",
                "object_resolver",
                "model_training",
                "signal_search",
                "portfolio_construction",
                "event_driven_backtest",
                "execution_validation",
                "experiment_tracking",
                "gate_review",
                "registry_publish",
            ),
            formal_requires_resolver=True,
            dag_builder=_ml_signal_model_research_dag_builder,
        ),
        ResearchProfile(
            profile_id="strategy_improvement",
            supported_modes=("sandbox", "formal"),
            consumes_types=("factor", "composite_factor"),
            produces_types=("strategy_candidate",),
            default_capabilities=(
                "object_resolver",
                "dataset_build",
                "portfolio_construction",
                "risk_overlay",
                "stress_test",
                "event_driven_backtest",
                "execution_validation",
                "gate_review",
                "registry_publish",
            ),
            formal_requires_resolver=True,
            dag_builder=_strategy_improvement_dag_builder,
        ),
        ResearchProfile(
            profile_id="benchmark_audit",
            supported_modes=("sandbox", "formal"),
            consumes_types=(),
            produces_types=(),
            default_capabilities=("benchmark_audit",),
            formal_requires_resolver=False,
            dag_builder=_benchmark_audit_dag_builder,
        ),
        # jolly-seeking-lollipop Gate B: validation profile that runs a
        # fully-prescribed recipe verbatim through IS+gate+OOS+publish.
        ResearchProfile(
            profile_id="hypothesis_validation",
            supported_modes=("formal",),  # validation is always formal
            consumes_types=("factor", "composite_factor"),
            produces_types=("signal", "strategy_candidate"),
            default_capabilities=(
                "object_resolver",
                "dataset_build",
                "portfolio_construction",
                "vectorized_backtest",
                "event_driven_backtest",
                "performance_diagnostics",
                "gate_evaluation",
                "gate_concern_scoring",
                "gate_review",
                "registry_publish",
            ),
            # Set to True so the profile follows the formal-resolver convention,
            # but the actual resolver call happens INSIDE
            # handle_validation_object_resolver (which derives consumes from
            # prescription.components) — the request.consumes itself stays
            # empty until that step runs.
            formal_requires_resolver=True,
            dag_builder=_hypothesis_validation_dag_builder,
        ),
        # factor_lifecycle plan Phase 5: the IS-ONLY draft->candidate factor gate.
        # Runs run_is_walk_forward as the gate; publishes passing factors at status
        # `candidate` only (never `approved`). NO OOS leg (candidate->approved OOS spend
        # is the separate frozen-set / promotion-gate path).
        ResearchProfile(
            profile_id="factor_lifecycle",
            supported_modes=("formal",),  # the draft->candidate gate is a formal decision
            # BASE factors only (GPT PR-#34 review): the dataset_build computes via
            # load_is_windowed_panel (base Qlib expressions). Composite / industry-relative
            # gating (Layer-2 add_composites) is a documented follow-up; advertising only
            # `factor` keeps the profile faithful to what it actually gates.
            consumes_types=("factor",),
            produces_types=("factor",),  # same factors, now at status candidate (or left draft)
            default_capabilities=(
                "object_resolver",
                "dataset_build",
                "walk_forward_validation",
                "gate_evaluation",
                "gate_concern_scoring",
                "gate_review",
                "registry_publish",
            ),
            formal_requires_resolver=True,
            dag_builder=_factor_lifecycle_dag_builder,
        ),
    ]
    for profile in builtins:
        register_profile(profile)


_register_builtin_profiles()


def run_research(request: ResearchRequest) -> ResearchRunResult:
    request.validate()
    profile = _PROFILE_REGISTRY.get(request.profile_id)
    _validate_request_against_profile(request, profile)
    registry_dirs = _resolve_registry_dirs(request.run_context)
    effective_capabilities = _effective_capabilities(profile, request)
    effective_capability_metadata = describe_capabilities(effective_capabilities)

    dag = profile.dag_builder(request, effective_capabilities)
    dag.validate()
    run_dir = _coerce_run_dir(dag.run_dir)
    resume_policy = str(request.run_context.get("resume_policy", "resume") or "resume").strip().lower()
    if resume_policy not in {"resume", "restart"}:
        raise ValueError(f"Unsupported resume_policy: {resume_policy}")

    request_payload = request.to_dict()
    request_hash = _sha256_text(_json_dumps(_canonical_request_payload(request)))
    plan_hash = dag.plan_hash()

    if resume_policy == "restart" and run_dir.exists():
        # restart means ignore existing state, but do not delete user files.
        # The runtime will overwrite DAG state and metadata in-place.
        pass

    def _build_context(
        step_id: str,
        step_dir: Path,
        resumed: bool,
        shared_state: dict[str, Any],
    ) -> StepExecutionContext:
        step = next(item for item in dag.steps if item.step_id == step_id)
        return StepExecutionContext(
            request=request,
            profile=profile,
            dag=dag,
            step=step,
            run_dir=run_dir,
            step_dir=step_dir,
            registry_dirs=registry_dirs,
            effective_capabilities=effective_capabilities,
            effective_capability_metadata=effective_capability_metadata,
            state=shared_state,
            resumed=resumed,
        )

    shared_state = execute_dag(
        dag=dag,
        request_hash=request_hash,
        plan_hash=plan_hash,
        resume_policy=resume_policy,
        request_payload=request_payload,
        build_context=_build_context,
        handler_registry=HANDLER_REGISTRY,
    )

    registry_resolution = dict(
        shared_state.get(
            "registry_resolution",
            {
                "formal_hits": 0,
                "candidate_hits": 0,
                "new_objects_created": 0,
                "unresolved_objects": [],
                "resolved_objects": [],
            },
        )
    )
    # jolly-seeking-lollipop Gate D.3 fix: also look up the validation
    # profile's renamed diagnostics steps so ResearchRunResult.outputs picks
    # them up (Codex round-2 finding).
    _step_outputs = shared_state.get("step_outputs", {})
    diagnostics_outputs: dict[str, Any] = {}
    for _step_id in (
        "performance_diagnostics",         # legacy / discovery profiles
        "validation_diagnostics_oos",      # validation profile, OOS pass (preferred — last to write)
        "validation_diagnostics_is",       # validation profile, IS pass
    ):
        candidate = dict(_step_outputs.get(_step_id, {}).get("diagnostics", {}))
        if candidate:
            diagnostics_outputs = candidate
            # Keep the OOS/last-completed one if available, but keep walking
            # in case OOS skipped and only IS produced.
    diagnostics_outputs = dict(diagnostics_outputs)
    diagnostics_outputs.setdefault("run_dir", str(run_dir))
    diagnostics_outputs.setdefault("effective_capabilities", effective_capabilities)
    diagnostics_outputs.setdefault("effective_capability_metadata", effective_capability_metadata)
    base_metadata = dict(shared_state.get("base_metadata", {}))
    base_metadata.update(
        {
            "research_profile": request.profile_id,
            "research_mode": request.mode,
            "execution_model": "dag",
            "request_hash": request_hash,
            "plan_hash": plan_hash,
            "resume_policy": resume_policy,
            "effective_capabilities": effective_capabilities,
            "effective_capability_metadata": effective_capability_metadata,
            "dag_step_count": len(dag.steps),
        }
    )
    produced_objects = list(shared_state.get("produced_objects", []))
    lineage_links = _build_lineage_links(
        request=request,
        resolution=registry_resolution,
        produced_objects=produced_objects,
    )
    final_state = load_run_state(run_dir)
    review_summary = _build_review_summary(
        request=request,
        registry_resolution=registry_resolution,
        produced_objects=produced_objects,
        outputs=diagnostics_outputs,
    )
    review_summary.update(
        {
            "execution_model": "dag",
            "dag_status": str(final_state.get("status", "")),
            "dag_step_count": len(dag.steps),
            "completed_step_count": int(final_state.get("completed_step_count", 0)),
            "failed_step_id": str(final_state.get("failed_step_id", "") or ""),
            "resume_policy": resume_policy,
        }
    )
    base_metadata["completed_step_count"] = int(final_state.get("completed_step_count", 0))
    base_metadata["failed_step_id"] = str(final_state.get("failed_step_id", "") or "")
    base_metadata["dag_status"] = str(final_state.get("status", "") or "")
    base_metadata["pending_step_id"] = str(final_state.get("pending_step_id", "") or "")
    base_metadata["pending_gate"] = dict(final_state.get("pending_gate", {}) or {})
    base_metadata["produced_objects"] = produced_objects
    base_metadata["registry_resolution"] = registry_resolution
    base_metadata["lineage_links"] = lineage_links
    base_metadata["review_summary"] = review_summary
    metadata = write_root_artifacts(
        run_dir=run_dir,
        run_metadata=base_metadata,
        produced_objects=produced_objects,
        review_summary=review_summary,
        registry_resolution=registry_resolution,
        lineage_links=lineage_links,
    )
    return ResearchRunResult(
        profile_id=request.profile_id,
        mode=request.mode,
        run_dir=str(run_dir),
        metadata=metadata,
        registry_resolution=registry_resolution,
        produced_objects=produced_objects,
        lineage_links=lineage_links,
        outputs=diagnostics_outputs,
    )


def compile_research_plan(request: ResearchRequest) -> dict[str, Any]:
    request.validate()
    profile = _PROFILE_REGISTRY.get(request.profile_id)
    _validate_request_against_profile(request, profile)
    effective_capabilities = _effective_capabilities(profile, request)
    dag = profile.dag_builder(request, effective_capabilities)
    dag.validate()
    return {
        "execution_model": "dag",
        "profile_id": profile.profile_id,
        "run_dir": str(Path(dag.run_dir).resolve()),
        "effective_capabilities": effective_capabilities,
        "effective_capability_metadata": describe_capabilities(effective_capabilities),
        "steps": [step.to_dict() for step in dag.topological_order()],
        "metadata": dict(dag.metadata),
    }


def resume_research(run_dir: str | Path) -> ResearchRunResult:
    plan = load_run_plan(run_dir)
    request_payload = dict(plan.get("request", {}))
    if not request_payload:
        raise ValueError(f"Run dir {Path(run_dir).resolve()} does not contain a resumable request payload.")
    request = ResearchRequest.from_dict(request_payload)
    request.run_context["resume_policy"] = "resume"
    return run_research(request)
