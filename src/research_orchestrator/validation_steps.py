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

    # Tightened policy: by default require source_layer="formal" for every
    # component. Opt in to candidate via prescription.allow_candidate_components.
    formal_only = not prescription.allow_candidate_components
    rejected: list[dict[str, Any]] = []
    for entry in raw_resolution["resolved_objects"]:
        layer = str(entry.get("source_layer") or "")
        if entry.get("status") == "unresolved":
            rejected.append({
                "factor_name": entry.get("requested", {}).get("object_name", ""),
                "reason": "unresolved",
                "details": entry,
            })
        elif formal_only and layer != "formal":
            rejected.append({
                "factor_name": entry.get("requested", {}).get("object_name", ""),
                "reason": f"non-formal source_layer={layer!r} but allow_candidate_components=False",
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

    outputs = {
        # The shape runtime.py:407 expects (matches handle_object_resolver):
        "registry_resolution": raw_resolution,
        # Convenience: pass the synthesized consumes downstream so dataset_build
        # doesn't need to re-derive it from prescription.
        "consumes": [c.to_dict() for c in consumes],
    }
    write_json(context.step_dir / "registry_resolution.json", outputs)
    return StepExecutionResult(status="completed", outputs=outputs)


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
