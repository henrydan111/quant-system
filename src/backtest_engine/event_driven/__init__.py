"""
Event-Driven A-Share Backtester

A realistic event-driven backtester for China A-shares that operates
independently of Qlib. Handles T+1, lot sizes, multi-tier price limits,
corporate actions, and date-aware transaction costs.

Usage:
    from src.backtest_engine.event_driven import (
        EventDrivenBacktester,
        QlibDataFeeder, Exchange, CostConfig,
        Strategy, Order, BacktestContext, BacktestResult,
        FixedSlippage, PctSlippage, NoSlippage,
    )

    bt = EventDrivenBacktester(data_dir='data')
    result = bt.run(
        strategy=MyStrategy(),
        start_time='2015-01-01',
        end_time='2025-12-31',
        benchmark='000852.SH',
        account=100_000,
    )
    print(pd.Series(result.summary).to_string())
"""

import os
import logging
from typing import Any
import pandas as pd

from .data_feeder import QlibDataFeeder
from .portfolio import Portfolio, Position
from .exchange import (
    Exchange, CostConfig,
    SlippageModel, NoSlippage, FixedSlippage, PctSlippage,
    JOINQUANT_DEFAULT_SLIPPAGE, CONSERVATIVE_SLIPPAGE_10BPS,
)
from .corporate_actions import CorporateActionHandler
from .strategy import Strategy, BacktestContext, Order
from .engine import BacktestEngine, BacktestResult
from .constants import ENGINE_REQUIRED_FIELDS, FORMAL_RUN_MODES
from src.backtest_engine.execution_profiles import (
    ExecutionProfile,
    ExecutionProfileError,
    OverrideRequiresReasonError,
    detect_override_diff,
    get_profile,
    resolve_cost_config,
    resolve_slippage_preset,
)
from src.data_infra.provider_manifest import (
    ProviderManifestError,
    load_provider_manifest,
)
from src.research_orchestrator.artifact_provenance import (
    ArtifactProvenance,
    attach_provenance,
)

logger = logging.getLogger(__name__)

__all__ = [
    'EventDrivenBacktester',
    'QlibDataFeeder', 'Portfolio', 'Position',
    'Exchange', 'CostConfig',
    'SlippageModel', 'NoSlippage', 'FixedSlippage', 'PctSlippage',
    'JOINQUANT_DEFAULT_SLIPPAGE', 'CONSERVATIVE_SLIPPAGE_10BPS',
    'CorporateActionHandler',
    'Strategy', 'BacktestContext', 'Order',
    'BacktestEngine', 'BacktestResult',
    'ENGINE_REQUIRED_FIELDS', 'FORMAL_RUN_MODES',
]


# ─────────────────────────────────────────────────────────────────────────
# PR 8 fix helpers — keep above the class so the wrapper can call them.
# ─────────────────────────────────────────────────────────────────────────


def _serialize_cost_config(cfg: CostConfig) -> dict[str, Any]:
    """Replayable serialization of a CostConfig override (PR 8 fix #6).

    Returns ``{"class": "CostConfig", "params": {...}}`` so the artifact
    contains every field needed to reconstruct the exact instance.
    """
    from dataclasses import asdict, is_dataclass
    if is_dataclass(cfg):
        params = {k: v for k, v in asdict(cfg).items()}
    else:
        params = {k: getattr(cfg, k) for k in dir(cfg)
                  if not k.startswith("_") and not callable(getattr(cfg, k))}
    return {"class": type(cfg).__name__, "params": params}


def _serialize_slippage(slip: SlippageModel) -> dict[str, Any]:
    """Replayable serialization of a SlippageModel override (PR 8 fix #6 +
    PR 8a fix #5).

    PR 8 hardcoded an attribute allow-list (``rate, value, bps, fixed_amount``)
    that missed ``FixedSlippage.spread``, so a JoinQuant-style FixedSlippage
    override was serialized as ``{"class": "FixedSlippage", "params": {}}``
    — not replayable. PR 8a inspects ``vars(slip)`` and keeps every
    JSON-safe value so any future SlippageModel subclass round-trips.
    """
    params: dict[str, Any] = {}
    raw = getattr(slip, "__dict__", None) or {}
    for k, v in raw.items():
        if k.startswith("_"):
            continue
        if isinstance(v, (int, float, str, bool, type(None))):
            params[k] = v
    return {"class": type(slip).__name__, "params": params}


def _read_provider_calendar_end(qlib_dir: str | os.PathLike[str]) -> str:
    """Read the provider's last trading day directly from calendars/day.txt.

    PR 8c Blocker 1: pre-PR-8c the runtime validator used ``D.calendar()``,
    which requires ``qlib.init(...)`` to have already run. PR 8b moved the
    validator BEFORE feeder construction (which is what calls qlib.init),
    so on a fresh process the call could fail with "Qlib not initialized"
    even when the provider on disk was perfectly fine.

    Reading the file directly mirrors what ``scripts/run_daily_qa.py``
    already does and avoids depending on global Qlib state. The on-disk
    format is one ISO date per line, sorted ascending; the last non-empty
    line is the live calendar end.
    """
    from pathlib import Path
    calendar_path = Path(qlib_dir) / "calendars" / "day.txt"
    if not calendar_path.exists():
        raise RuntimeError(
            f"Provider calendar file not found at {calendar_path}. "
            "The Qlib provider may not be initialized; verify the qlib_dir "
            "argument points at a published provider tree."
        )
    lines = [
        line.strip()
        for line in calendar_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not lines:
        raise RuntimeError(
            f"Provider calendar file is empty: {calendar_path}. "
            "Provider rebuild appears to have failed; re-run "
            "build_qlib_backend or restore the provider tree."
        )
    return lines[-1]


def _validate_provider_at_runtime(
    *,
    manifest: Any,
    calendar_policy_id: str,
    run_mode: str,
    qlib_dir: str | os.PathLike[str] | None = None,
) -> None:
    """Formal-runtime provider/calendar validation (PR 8 fix #3 + PR 8c).

    For a frozen policy, the observed Qlib calendar end-date MUST match the
    policy's calendar_end_date AND the manifest's calendar_end_date — the
    blanket "policy.frozen → allow any mismatch" was too loose. Mode-level
    permission is also checked: the run_mode (or profile deployment_target)
    must be in policy.allowed_modes.

    PR 8c Blocker 1: the live calendar end is now read directly from the
    provider's ``calendars/day.txt`` via :func:`_read_provider_calendar_end`,
    so the validator does not depend on ``qlib.init(...)`` having run yet.
    This is important because PR 8b moved the validator BEFORE feeder
    creation (which is what initializes Qlib).
    """
    from src.research_orchestrator.calendar_policy import load_calendar_policy
    from src.data_infra.provider_manifest import (
        validate_provider_manifest_against_qlib,
    )

    try:
        policy = load_calendar_policy(calendar_policy_id)
    except Exception as exc:
        raise RuntimeError(
            f"Formal run requires calendar_policy_id={calendar_policy_id!r} "
            f"but loading failed: {exc}"
        ) from exc

    # PR 8b Blocker 3: the manifest's own calendar_policy_id MUST match
    # the policy id the run claims to operate under. Without this check, a
    # caller could pass a different policy id with the same dates and
    # silently stamp a mismatched policy into the artifact, defeating the
    # self-attestation contract.
    if manifest.calendar_policy_id != calendar_policy_id:
        raise RuntimeError(
            f"Provider manifest declares calendar_policy_id="
            f"{manifest.calendar_policy_id!r} but the run was launched with "
            f"calendar_policy_id={calendar_policy_id!r}. The two must match — "
            "either pass the manifest's policy id explicitly or rebuild the "
            "provider under the intended policy."
        )

    policy.assert_run_mode_allowed(run_mode)

    # PR 8c Blocker 1: read calendar end from disk, not via D.calendar().
    # qlib_dir defaults to the manifest's recorded path when caller didn't
    # supply one explicitly.
    if qlib_dir is None:
        qlib_dir = manifest.provider.path
    try:
        live_calendar_end = _read_provider_calendar_end(qlib_dir)
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise RuntimeError(
            f"Formal provider/calendar validation could not read the "
            f"calendar from {qlib_dir}: {exc}. The validator must not "
            "silently skip the mismatch check on formal runs."
        ) from exc

    if policy.frozen:
        if policy.calendar_end_date != live_calendar_end:
            raise RuntimeError(
                f"Frozen calendar policy {calendar_policy_id!r} declares "
                f"calendar_end_date={policy.calendar_end_date} but live Qlib "
                f"calendar ends at {live_calendar_end}. Either rebuild the "
                "provider or load a non-frozen policy."
            )
        if manifest.provider.calendar_end_date != policy.calendar_end_date:
            raise RuntimeError(
                f"Manifest calendar_end_date={manifest.provider.calendar_end_date} "
                f"does not match frozen policy {calendar_policy_id!r} "
                f"calendar_end_date={policy.calendar_end_date}."
            )
        # Both ends agree; namespacing still must be enforced.
        validate_provider_manifest_against_qlib(
            manifest, live_calendar_end, allow_calendar_mismatch=False,
        )
    else:
        validate_provider_manifest_against_qlib(
            manifest, live_calendar_end, allow_calendar_mismatch=False,
        )


class EventDrivenBacktester:
    """High-level API for running event-driven backtests.

    Wraps all component creation and wiring into a single entry point.
    Compatible with the result_analysis module.

    Args:
        data_dir: Root data directory (default: auto-detect from config).
        config_path: Path to config.yaml (optional).
    """

    def __init__(self, data_dir: str = None, config_path: str = None):
        if data_dir is None:
            # Try to auto-detect
            if config_path and os.path.exists(config_path):
                import yaml
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                data_dir = config.get('data_dir', 'data')
            else:
                data_dir = 'data'
        self.data_dir = data_dir

    def run(self, strategy: Strategy,
            start_time: str, end_time: str,
            benchmark: str = None,
            account: float = 100_000,
            exchange_config: CostConfig = None,
            slippage: SlippageModel = None,
            volume_limit: float | None = None,
            preload_fields: list[str] = None,
            time_split: dict | None = None,
            holdout_context: Any | None = None,
            preload_strict: bool = False,
            preload_required: bool = False,
            instrumentation_path: str | None = None,
            fill_mode: str | None = None,
            calendar_policy_id: str | None = None,
            require_provider_manifest: bool = False,
            run_mode: str | None = None,
            execution_profile: str | None = None,
            override_reason: str | None = None,
            hold_on_limit_up: bool = False) -> BacktestResult:
        """Run a backtest with the given strategy.

        Args:
            strategy: Strategy instance to run.
            start_time: Start date ('YYYY-MM-DD').
            end_time: End date ('YYYY-MM-DD').
            benchmark: Benchmark index code (e.g., '000852.SH').
            account: Initial cash in ¥.
            exchange_config: Custom cost configuration.
            slippage: Slippage model to use.
            volume_limit: Max fraction of daily volume per order.
            preload_strict: When True, re-raise on preload failure instead of
                silently degrading to per-day ``D.features`` queries. Formal
                validation handlers must pass ``True``. Plan
                ``snappy-buzzing-meerkat`` v5 Phase 2.a.
            instrumentation_path: When set, write a harness-instrumentation
                JSON report to this path after the run completes. Required by
                the v5 verification gate; captures preload_status / cache-hit
                / fallback / per-day timing / cache-event design_hashes.
            fill_mode: ``'open_close'`` (default) fills before_market_open
                orders at OPEN and on_bar orders at CLOSE — closest to live
                execution.  ``'jq_daily_avg'`` fills BOTH phases at the day's
                average price ``(open + close) / 2`` — matches JoinQuant's
                daily-backtest fill model (API doc line 1252). Use the latter
                when local CAGR must predict JoinQuant daily-backtest CAGR.
            calendar_policy_id: Identifier of the calendar policy this run was
                explicitly authorized under (see config/calendar_policies/).
                Recorded into result.config via ArtifactProvenance. Formal runs
                must pass an explicit value; sandbox runs may leave None.
            require_provider_manifest: When True, raise if the local Qlib
                provider has no data/qlib_data/metadata/provider_build.json.
                Formal validation handlers should pass True; sandbox/historical
                investigation scripts may leave the default False so the
                wrapper still tolerates a pre-PR1 environment.
            preload_required: PR 2 of the 2026-05-26 freeze plan. When True,
                always preload (even if ``preload_fields`` is None) AND have
                the engine assert that the cache covers ENGINE_REQUIRED_FIELDS
                with zero direct fallbacks before the day loop. Auto-set to
                True when ``run_mode`` is in FORMAL_RUN_MODES.
            run_mode: Optional execution-mode tag (e.g., 'formal', 'oos_test',
                'joinquant_replication', 'sandbox'). When set to any value in
                FORMAL_RUN_MODES the wrapper auto-enables preload and strict.
                PR 3 will expand this into a full ExecutionProfile contract.

        Returns:
            BacktestResult with all outputs.  ``result.config['artifact_provenance']``
            carries provider_build_id, calendar_policy_id, and (post PR 3)
            execution_profile_*; missing fields make the artifact legacy.
        """
        # PR 3 of 2026-05-26 freeze plan + PR 8 fixup: resolve the execution
        # profile up front so the rest of the wrapper works with concrete
        # fill_mode / cost_config / slippage / volume_limit values. PR 8
        # critical fix: compute is_formal ONCE here, considering BOTH
        # run_mode AND profile.allowed_for_formal — previously the wrapper
        # computed it twice and the second computation overwrote the
        # profile-aware version, so a caller passing
        # `execution_profile='joinquant_daily_sim', run_mode=None` got
        # JoinQuant fill semantics without strict preload enforcement.
        profile_obj: ExecutionProfile | None = None
        override_diff_record: dict[str, Any] = {}
        explicit_fill_mode = fill_mode
        explicit_slippage_obj = slippage
        explicit_cost_config_obj = exchange_config
        explicit_volume_limit = volume_limit

        if execution_profile is not None:
            profile_obj = get_profile(execution_profile)
            if profile_obj.backend != "event_driven":
                raise ExecutionProfileError(
                    f"execution_profile={execution_profile!r} has backend={profile_obj.backend!r} "
                    "but EventDrivenBacktester only accepts event_driven profiles. "
                    "Use VectorizedBacktester for screening profiles."
                )
            # Compute the diff WITHOUT yet using the explicit values to override.
            override_diff_record = dict(detect_override_diff(
                profile=profile_obj,
                explicit_fill_mode=explicit_fill_mode,
                explicit_cost_config_factory=None,  # caller passes objects, not factory names
                explicit_slippage_preset=None,
                explicit_volume_limit=explicit_volume_limit,
            ))
            # PR 8 fix #6: replayable object-form override records.
            # Previously we stored opaque '<caller-supplied CostConfig instance>'
            # strings. Now we serialize the full class + params so the override
            # is reconstructable from the artifact alone.
            if explicit_cost_config_obj is not None:
                override_diff_record["cost_config_object"] = {
                    "from": {
                        "factory": profile_obj.cost_config_factory,
                    },
                    "to": _serialize_cost_config(explicit_cost_config_obj),
                }
            if explicit_slippage_obj is not None:
                override_diff_record["slippage_object"] = {
                    "from": {"preset": profile_obj.slippage_preset},
                    "to": _serialize_slippage(explicit_slippage_obj),
                }

            # Apply profile defaults where caller did not supply explicit values.
            if explicit_fill_mode is None:
                fill_mode = profile_obj.fill_mode
            if explicit_volume_limit is None:
                volume_limit = profile_obj.volume_limit
            if explicit_cost_config_obj is None:
                exchange_config = resolve_cost_config(profile_obj.cost_config_factory)
            if explicit_slippage_obj is None:
                slippage = resolve_slippage_preset(profile_obj.slippage_preset)
        else:
            # No profile supplied. Backwards-compatible: apply legacy defaults
            # if the caller didn't set them. These keep PR 2 behavior intact
            # for sandbox / historical_investigation runs.
            if fill_mode is None:
                fill_mode = "open_close"
            if volume_limit is None:
                volume_limit = 0.25

        # GPT R1 P1: hold_on_limit_up (果仁 不卖条件 涨停不卖) is a NON-profiled execution rule that changes
        # SELL behavior. Track it as an explicit override so it is provenance-stamped (manual_override /
        # override_diff below) and caught by the formal override-reason gate — never silently enabled.
        if hold_on_limit_up:
            override_diff_record["hold_on_limit_up"] = True

        # PR 8 fix #1: SINGLE is_formal computation considering BOTH run_mode
        # and profile.allowed_for_formal. Used uniformly below for preload
        # condition, strict preload, require_preloaded, and provider-manifest
        # requirement.
        mode_is_formal = run_mode in FORMAL_RUN_MODES if run_mode else False
        profile_is_formal = bool(profile_obj and profile_obj.allowed_for_formal)
        is_formal = mode_is_formal or profile_is_formal

        # GPT R1 P1: a formal run must JUSTIFY hold_on_limit_up explicitly. This dedicated guard fires for
        # BOTH profile-formal AND run_mode-formal (the generic override gate below only fires when a profile
        # is present, so it would miss a run_mode-formal run with no profile).
        if is_formal and hold_on_limit_up and not override_reason:
            raise OverrideRequiresReasonError(
                "Formal run enabled hold_on_limit_up=True (果仁 涨停不卖 — a non-profiled execution rule that "
                "changes sell behavior) without override_reason. Pass override_reason='...' to document the "
                "deliberate deviation, or disable it for formal runs."
            )

        # Formal runs reject overrides unless override_reason is supplied.
        if profile_obj is not None and is_formal and override_diff_record and not override_reason:
            raise OverrideRequiresReasonError(
                f"Formal execution_profile={execution_profile!r} received "
                f"overrides {sorted(override_diff_record)} without an "
                "override_reason. Pass override_reason='...' to document "
                "why the formal contract is being deliberately overridden."
            )

        if time_split:
            stage = str(time_split.get("stage", "") or "")
            allowed_start = str(time_split.get("oos_start" if stage == "oos_test" else "is_start", "") or "")
            allowed_end = str(time_split.get("oos_end" if stage == "oos_test" else "is_end", "") or "")
            if allowed_start and pd.Timestamp(start_time) < pd.Timestamp(allowed_start):
                raise ValueError(f"TimeSplit violation: start_time {start_time} is before allowed window {allowed_start}")
            if allowed_end and pd.Timestamp(end_time) > pd.Timestamp(allowed_end):
                raise ValueError(f"TimeSplit violation: end_time {end_time} is after allowed window {allowed_end}")
            if stage == "oos_test":
                if holdout_context is None:
                    raise ValueError(
                        "Engine backstop: time_split.stage='oos_test' requires a holdout_context. "
                        "Sandbox mode cannot touch the holdout window."
                    )
                from src.research_orchestrator.holdout_seal import (
                    HoldoutSealStore,
                    resolve_configured_global_holdout_root,
                )

                # PR3 R6 Blocker 1: the backstop verifies the claim against the ONE
                # canonical sealed world — never a caller-chosen store.
                store = HoldoutSealStore(resolve_configured_global_holdout_root())
                # PR P1.4: check by the seal_key the claim was made under
                # (effective_seal_key falls back to design_hash for back-compat).
                events = store.list_events(seal_key=holdout_context.effective_seal_key)
                matching = events[
                    (events["run_dir"] == holdout_context.run_dir)
                    & (events["step_id"] == holdout_context.step_id)
                ]
                if matching.empty:
                    raise ValueError(
                        f"Engine backstop: OOS run on seal_key={holdout_context.effective_seal_key} "
                        f"(design_hash={holdout_context.design_hash}) but no seal claim found for "
                        f"run_dir={holdout_context.run_dir}, step_id={holdout_context.step_id}. "
                        f"Did you call SealedBacktestRunner?"
                    )

        # PR 2 corrected preload condition + PR 8 fix #1: is_formal already
        # computed above considering BOTH run_mode and profile.allowed_for_formal.
        # Formal profiles (joinquant_daily_sim, joinquant_open_close_replica)
        # now correctly auto-enable preload + strict + require_preloaded even
        # when the caller leaves run_mode=None.
        should_preload = (
            preload_required
            or preload_fields is not None
            or is_formal
        )
        effective_strict = preload_strict or is_formal
        effective_require_preloaded = preload_required or is_formal
        # PR 8 fix #3: formal runs require a current provider manifest. Sandbox
        # runs may leave the default False so legacy environments still work.
        effective_require_provider_manifest = require_provider_manifest or is_formal

        # PR 8b Blocker 1: governance preconditions MUST fire BEFORE any
        # feeder creation or preload — pre-PR-8b, the check ran after
        # feeder.preload_features() so a formal run without a policy still
        # touched Qlib and burned cache work before failing.
        if effective_require_provider_manifest and not calendar_policy_id:
            raise RuntimeError(
                "Formal run requires calendar_policy_id but received None. "
                "Pass a committed policy id from config/calendar_policies/ "
                "explicitly (for a live-provider run, the manifest-recorded "
                "provider_build.json calendar_policy_id). The policy is "
                "what authorizes a formal run to operate against the current "
                "calendar window; without it the manifest validator cannot "
                "run and the artifact cannot be formally attested."
            )

        # PR 8b: load + validate the provider manifest BEFORE feeder/preload
        # so a stale calendar or wrong policy id fails immediately, not
        # after feature data has been loaded into memory. Sandbox runs
        # tolerate missing manifests (warn + legacy provenance).
        provider_build_id: str | None = None
        manifest = None
        try:
            manifest = load_provider_manifest(os.path.join(self.data_dir, 'qlib_data'))
            provider_build_id = manifest.provider_build_id
            if effective_require_provider_manifest:
                _validate_provider_at_runtime(
                    manifest=manifest,
                    calendar_policy_id=calendar_policy_id,
                    run_mode=run_mode or (
                        profile_obj.deployment_target if profile_obj else "sandbox"
                    ),
                    # PR 8c Blocker 1: pass the qlib_dir explicitly so the
                    # validator can read calendars/day.txt directly without
                    # depending on qlib.init() having run.
                    qlib_dir=os.path.join(self.data_dir, 'qlib_data'),
                )
        except ProviderManifestError as exc:
            if effective_require_provider_manifest:
                raise
            logger.warning(
                "Provider manifest unavailable (%s). Result will be marked legacy_artifact=True.",
                exc,
            )

        # Create components.
        # Part E (plan snappy-buzzing-meerkat v5): derive feeder stage from
        # time_split.stage so cache-manifest rows carry the correct stage
        # label. Without this, OOS runs would mislabel rows as is_only.
        feeder_stage = "is_only"
        if time_split:
            ts_stage = str(time_split.get("stage", "") or "")
            if ts_stage:
                feeder_stage = ts_stage
        feeder = QlibDataFeeder(self.data_dir, stage=feeder_stage)

        if should_preload:
            # Expand start_time to include the previous trading day for Day 1 warmup
            try:
                # We need one day prior to start_time
                prev_date = feeder.get_prev_trading_day(pd.Timestamp(start_time))
                preload_start = prev_date.strftime('%Y-%m-%d') if prev_date else start_time
            except Exception as e:
                logger.warning(f"Failed to pad preload start date: {e}")
                preload_start = start_time

            requested_fields = list(preload_fields or [])
            all_preload_fields = list(
                dict.fromkeys([*requested_fields, *ENGINE_REQUIRED_FIELDS])
            )
            # We fetch 'all' domain to ensure we have every stock for the backtest
            feeder.preload_features(
                'all', all_preload_fields, preload_start, end_time,
                strict=effective_strict,
            )

        st_path = os.path.join(
            self.data_dir, 'qlib_data', 'instruments', 'st_stocks.txt'
        )
        if not os.path.exists(st_path):
            st_path = None

        suspension_ranges_path = os.path.join(
            self.data_dir, 'market', 'suspension', 'suspension_ranges.parquet'
        )
        if not os.path.exists(suspension_ranges_path):
            logger.warning(
                "Authoritative suspension ranges not found at %s; Exchange will fall back "
                "to vol==0 suspension detection.",
                suspension_ranges_path,
            )
            suspension_ranges_path = None

        exchange = Exchange(
            cost_config=exchange_config,
            st_data_path=st_path,
            feeder=feeder,
            volume_limit=volume_limit,
            slippage_model=slippage,
            suspension_ranges_path=suspension_ranges_path,
        )

        dividends_dir = os.path.join(self.data_dir, 'corporate', 'dividends')
        corp_handler = None
        if os.path.isdir(dividends_dir):
            corp_handler = CorporateActionHandler(dividends_dir)

        engine = BacktestEngine(
            feeder=feeder,
            exchange=exchange,
            strategy=strategy,
            initial_cash=account,
            corp_action_handler=corp_handler,
            fill_mode=fill_mode,
            require_preloaded=effective_require_preloaded,
        )
        # 果仁 不卖条件 "调仓日交易时涨停" (hold limit-up winners): opt-in fill-step rule. Default OFF
        # → zero impact on existing/formal runs; does NOT touch the §3.3 can_buy/can_sell limit GATE.
        # NON-FORMAL research feature (果仁 parity); GPT §10 review required before any formal/load-bearing use.
        engine._hold_on_limit_up = bool(hold_on_limit_up)

        # PR 8b: provider manifest + calendar validation moved above (before
        # feeder + preload). provider_build_id is already populated.
        import time as _time
        _run_t0 = _time.perf_counter()
        try:
            result = engine.run(start_time, end_time, benchmark_code=benchmark)
        finally:
            _run_wall = _time.perf_counter() - _run_t0
            if instrumentation_path:
                try:
                    self._write_instrumentation_report(
                        instrumentation_path,
                        feeder=feeder,
                        engine=engine,
                        feeder_stage=feeder_stage,
                        wall_seconds=_run_wall,
                        start_time=start_time,
                        end_time=end_time,
                        preload_strict=preload_strict,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Failed to write instrumentation report to %s: %s",
                        instrumentation_path, exc,
                    )

        # Stamp provenance onto result.config — PR 1 (provider/calendar) +
        # PR 3 (execution_profile + override block).
        provenance_kwargs: dict[str, Any] = {
            "provider_build_id": provider_build_id,
            "calendar_policy_id": calendar_policy_id,
        }
        if profile_obj is not None:
            provenance_kwargs.update(profile_obj.to_provenance_dict())
        # GPT R2 P2: stamp overrides REGARDLESS of profile, so a no-profile run (run_mode-formal or
        # non-formal) that enabled an override (e.g. hold_on_limit_up) records it in provenance. Previously
        # this was inside the profile branch, leaving run_mode-formal/no-profile with manual_override=False
        # despite the override being active (execution_profile_id is Optional, so this is schema-safe).
        if override_diff_record:
            provenance_kwargs["manual_override"] = True
            provenance_kwargs["override_reason"] = override_reason
            provenance_kwargs["override_diff"] = dict(override_diff_record)

        provenance = ArtifactProvenance(**provenance_kwargs)
        provenance = ArtifactProvenance.from_dict(provenance.to_dict())
        config = getattr(result, "config", None)
        if isinstance(config, dict):
            attach_provenance(config, provenance)
        else:
            logger.debug(
                "Skipping provenance attach: result has no dict config (type=%s)",
                type(result).__name__,
            )
        return result

    @staticmethod
    def _write_instrumentation_report(
        path: str,
        *,
        feeder: QlibDataFeeder,
        engine: BacktestEngine,
        feeder_stage: str,
        wall_seconds: float,
        start_time: str,
        end_time: str,
        preload_strict: bool,
    ) -> None:
        """Write the harness-instrumentation JSON expected by the v5 verification gate."""
        import json
        from pathlib import Path
        from src.research_orchestrator.cache_manifest import CacheManifestStore

        per_day = list(getattr(engine, "_day_wall_seconds", []))
        if per_day:
            sorted_per_day = sorted(per_day)
            n = len(sorted_per_day)

            def _pct(p):
                if n == 0:
                    return None
                idx = min(n - 1, int(round(p * (n - 1))))
                return float(sorted_per_day[idx])

            timing = {
                "p50": _pct(0.50),
                "p95": _pct(0.95),
                "max": float(max(per_day)),
                "min": float(min(per_day)),
                "mean": float(sum(per_day) / n),
                "n_days": n,
            }
        else:
            timing = {"p50": None, "p95": None, "max": None, "min": None, "mean": None, "n_days": 0}

        # Read the live cache manifest to surface which design_hashes our
        # preload + per-day fetches recorded — required by the gate to
        # confirm Part D propagation worked end-to-end.
        try:
            manifest = CacheManifestStore()
            recent = manifest.list_events()
            design_hashes = sorted(
                {str(h) for h in recent["design_hash"].tolist() if str(h)}
            )
            stages_by_window = sorted(
                {str(s) for s in recent["stage"].tolist() if str(s)}
            )
        except Exception:  # noqa: BLE001
            design_hashes = []
            stages_by_window = []

        report = {
            "tool": "EventDrivenBacktester._write_instrumentation_report",
            "plan": "snappy-buzzing-meerkat v5",
            "window": [start_time, end_time],
            "feeder_stage": feeder_stage,
            "preload_strict": preload_strict,
            "preload_status": getattr(feeder, "_preload_status", "not_attempted"),
            "preload_wall_seconds": round(
                float(getattr(feeder, "_preload_wall_seconds", 0.0)), 4,
            ),
            "cache_hit_count": int(getattr(feeder, "_cache_hit_count", 0)),
            "direct_fallback_count": int(getattr(feeder, "_direct_fallback_count", 0)),
            "per_day_timing_seconds": timing,
            "total_wall_seconds": round(float(wall_seconds), 4),
            "cache_events_design_hashes_seen": design_hashes,
            "cache_events_stages_seen": stages_by_window,
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        logger.info("Wrote instrumentation report to %s", path)
