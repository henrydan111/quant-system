"""v1.4 PR3 — the book-level sealed evaluation: the ``book_seal_key`` claim path, the
pre-declared-bar verdict, and the in-context component diagnostics.

Design (normative): ``workspace/research/factor_eval_methodology/
FACTOR_EVAL_V1.4_AMENDMENT_book_level_promotion.md`` §2 A2/A6/A8 (+ round-2 N2/N3),
REWORKED per the GPT §10 implementation review R1 (2026-07-12, 5 Blockers folded):

* **One request, one persisted result (R1 B1).** Every evaluation is identified by a
  ``request_hash``; the run is a state machine persisted in
  :class:`~.book_seal_stores.BookSealArtifactStore`
  (``claimed → verdict_persisted → complete | diagnostics_failed``). The FIRST persisted
  book verdict is immutable. Resume is AUTOMATIC and fail-closed: same
  ``request_hash`` + ``run_dir`` + ``step_id`` + provider ids, refuses ``complete``,
  re-runs the backtest ONLY when no verdict was ever persisted (state ``claimed``), and
  otherwise finishes ONLY the unfinished diagnostics. There is no caller-facing
  ``allow_same_run`` and no path that re-executes a completed evaluation.
* **Spend accounting is atomic (R1 B5).** ``OosWindowLedgerStore.reserve_book_spend``
  (one lock: recognize-resume → count → enforce budget → append spend-on-attempt row)
  runs BEFORE the holdout claim; a crash between the two over-counts (conservative),
  never under-counts. The hard-threshold override is a consume-once
  ``OverrideAuthorizationStore`` record (kind ``a6_multiplicity``) with a human
  sign-off + adjusted-statistics commitment — never a boolean.
* **Live mode is REFUSED until the governed S6 runner exists (R1 B4 interim, per the
  reviewer's own replacement).** The promotion-driving number must come from an
  attested event-driven total-return 1× engine bound to a formal execution profile —
  not a caller-supplied callable. ``mode="dryrun"`` (the §5 burned-window pilot shape)
  is the only executable mode; its stores MUST be run-local (enforced, R1 Minor 1) and
  it refuses virgin windows outright.
* **Diagnostics are verified, complete, and durable (R1 B4/M2).** The diagnostics leg
  verifies the claimed seal EVENT exists in the supplied ``HoldoutSealStore`` (a
  fabricated in-process context without a real claim is refused), requires EXACT
  component coverage of the frozen set with finite mandatory metrics, appends durable
  rows to :class:`~.book_seal_stores.StrategyComponentDiagnosticStore`, and mints no
  status. A diagnostics failure persists ``diagnostics_failed`` and RAISES
  :class:`BookSealDiagnosticsError`; resume finishes only the diagnostics.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from src.alpha_research.factor_eval_skill._hashing import payload_hash
from src.alpha_research.factor_eval_skill.book_seal_stores import (
    BookSealArtifactStore,
    OverrideAuthorizationStore,
    StrategyComponentDiagnosticStore,
)
from src.alpha_research.factor_eval_skill.identity import BookSealIdentity, DeploymentFrozenPlan
from src.alpha_research.factor_eval_skill.multiplicity import (
    is_virgin_window,
    oos_window_multiplicity,
    virgin_window_multiplicity,
)
from src.alpha_research.factor_eval_skill.sealed_oos import (
    evaluate_sealed_oos_bar,
    sides_from_frozen_set,
)
from src.alpha_research.factor_eval_skill.stores import OosWindowLedgerStore

ARTIFACT_SCHEMA_VERSION = 2
VALID_MODES = ("dryrun", "live")
# Metrics whose repo-wide convention is NEGATIVE (goal_metrics / result_analysis: a 40%
# drawdown is mdd=-0.40). A `<name>_max` bar bound on one of these is a MAGNITUDE cap:
# pass iff metric >= bound (i.e. no DEEPER than the bound). Enforced with an explicit
# sign assertion so a positive-mdd caller fails loudly instead of silently inverting.
NEGATIVE_CONVENTION_METRICS = frozenset({"mdd", "max_drawdown"})
# Mandatory finite metrics every component-diagnostic row must carry (R1 B4: empty /
# all-NaN diagnostics must never read as healthy).
MANDATORY_DIAGNOSTIC_METRICS = ("oos_rank_icir", "oos_ls_sharpe")
VIRGIN_WARN, VIRGIN_HARD = 3, 5


class BookSealError(RuntimeError):
    """Fail-closed error for the book sealed-evaluation path."""


class BookSealDiagnosticsError(BookSealError):
    """The component-diagnostics leg failed AFTER the seal was spent: the state is
    persisted as ``diagnostics_failed``; resume finishes ONLY the diagnostics."""


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ────────────────────────────────────────────────────────── pre-declared bar ──


@dataclass(frozen=True)
class BookVerdict:
    """The book-level verdict vs the pre-declared bar. ``bar_passed`` is the
    promotion-driving boolean; ``criteria`` records every per-key comparison."""

    metrics: Mapping[str, Any]
    bar: Mapping[str, Any]
    bar_passed: bool
    criteria: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "metrics": {str(k): v for k, v in self.metrics.items()},
            "bar": {str(k): v for k, v in self.bar.items()},
            "bar_passed": bool(self.bar_passed),
            "criteria": [dict(c) for c in self.criteria],
        }


def evaluate_pre_declared_bar(
    metrics: Mapping[str, Any], bar: Mapping[str, Any]
) -> BookVerdict:
    """Evaluate net book metrics against the plan's PRE-DECLARED bar. FAIL-CLOSED:

    * bar keys must end in ``_min`` (metric >= value) or ``_max`` (metric <= value);
      anything else raises (no silent skip);
    * a bar key whose metric is MISSING or NON-FINITE (NaN or ±inf — R1 Major 1)
      raises — it never passes;
    * drawdown-convention metrics (:data:`NEGATIVE_CONVENTION_METRICS`) under ``_max``
      are a magnitude cap (``metric >= value``) and BOTH sides must be <= 0, else
      raises ``ambiguous drawdown sign`` (the silent sign-flip trap);
    * an empty bar raises — a sealed book without a bar is not evaluable.
    """
    if not bar:
        raise BookSealError("pre_declared_bar is empty — a sealed book requires a declared bar")
    criteria: list[dict[str, Any]] = []
    all_ok = True
    for key in sorted(str(k) for k in bar):
        value = bar[key]
        if key.endswith("_min"):
            metric_name, direction = key[: -len("_min")], "min"
        elif key.endswith("_max"):
            metric_name, direction = key[: -len("_max")], "max"
        else:
            raise BookSealError(
                f"pre_declared_bar key {key!r} must end in '_min' or '_max' (explicit comparator)"
            )
        if metric_name not in metrics:
            raise BookSealError(
                f"book metrics missing {metric_name!r} required by bar key {key!r} — fail-closed"
            )
        try:
            metric_val = float(metrics[metric_name])
            bound = float(value)
        except (TypeError, ValueError) as exc:
            raise BookSealError(f"non-numeric bar/metric for {key!r}: {exc}") from exc
        if not math.isfinite(metric_val) or not math.isfinite(bound):
            raise BookSealError(
                f"non-finite bar/metric for {key!r}: bound={bound}, metric={metric_val} — "
                "fail-closed, never passes"
            )
        if direction == "max" and metric_name in NEGATIVE_CONVENTION_METRICS:
            if bound > 0 or metric_val > 0:
                raise BookSealError(
                    f"ambiguous drawdown sign for {key!r}: this repo's convention is "
                    f"NEGATIVE drawdowns (goal_metrics mdd=-0.40 for a 40% drawdown); got "
                    f"bound={bound}, metric={metric_val}"
                )
            ok = metric_val >= bound  # magnitude cap: no deeper than the bound
        elif direction == "min":
            ok = metric_val >= bound
        else:
            ok = metric_val <= bound
        criteria.append(
            {"key": key, "metric": metric_name, "direction": direction,
             "bound": bound, "value": metric_val, "passed": bool(ok)}
        )
        all_ok = all_ok and ok
    return BookVerdict(metrics=dict(metrics), bar=dict(bar), bar_passed=bool(all_ok),
                       criteria=tuple(criteria))


# ─────────────────────────────────── component diagnostics (inside the book seal) ──


def run_component_diagnostics_in_book_context(
    *,
    book_seal_key: str,
    request_hash: str,
    artifact_store,
    seal_store,
    oos_start: str,
    oos_end: str,
    qlib_dir: str,
    horizon: int = 20,
    n_quantiles: int = 10,
    component_weights: Mapping[str, float] | None = None,
    compute_metrics_fn: Callable[..., tuple[dict, str]] | None = None,
    trade_cal=None,
) -> dict[str, Any]:
    """A2(b)/N3 — per-component gross OOS diagnostics computed INSIDE the book's
    already-claimed seal. The ONLY sanctioned component-diagnostics path.

    R2 Blocker 3: the leg is bound to the CANONICAL CLAIM, not to caller arguments —
    the component set (factors, sides, expressions) is loaded from the manifest SEALED
    at claim time (``BookSealArtifactStore.load_component_manifest``); there is no
    ``frozen_set``/``factor_exprs`` parameter to substitute foreign factors into a real
    book's seal. Refuses (fail-closed) unless ALL of:

    * the ACTIVE ``ResearchAccessContext`` is a claimed OOS context with
      ``effective_seal_key == book_seal_key``, ``request_hash == request_hash``,
      covering ``[oos_start, oos_end]``;
    * the canonical claim exists for (key, request) and its ``run_dir`` / ``step_id`` /
      provider / calendar / window ALL equal the context's;
    * a REAL holdout seal event exists for the key whose ``event_id`` matches the
      claim's, with the same ``request_hash`` / run / step.

    NEVER claims a seal, NEVER installs a (nested) context. Completeness (R1 B4):
    every manifest member must yield a FINITE-metric row with exact coverage. Emits NO
    promotion evidence and mints NO status (rows carry
    ``run_type='book_component_diagnostic'``, ``spent_in_book_context=True``,
    ``fresh_oos_eligible=False``, ``promotion_eligible=False``)."""
    import pandas as pd

    from src.research_orchestrator.research_access_context import get_research_access_context

    key = str(book_seal_key).strip()
    req = str(request_hash).strip()
    if not key or not req:
        raise BookSealError("book_seal_key + request_hash are required (blank refused)")
    ctx = get_research_access_context()
    if ctx is None:
        raise BookSealError(
            "component diagnostics require an ACTIVE claimed book ResearchAccessContext — "
            "there is none. A bare run outside run_book_sealed_evaluation is not a "
            "sanctioned path (v1.4 A2(b)/N3)."
        )
    if not getattr(ctx, "holdout_seal_claimed", False):
        raise BookSealError(
            "component diagnostics require holdout_seal_claimed=True on the active context "
            "(a no-seal OOS context is exactly the reuse path v1.4 N3 closes)."
        )
    if str(ctx.effective_seal_key) != key:
        raise BookSealError(
            f"active context seal_key {ctx.effective_seal_key!r} != book_seal_key {key!r} — "
            "the diagnostics leg may only run inside ITS OWN book's claimed seal."
        )
    if str(getattr(ctx, "request_hash", "")) != req:
        raise BookSealError(
            f"active context request_hash {getattr(ctx, 'request_hash', '')!r} != {req!r} — "
            "a context borrowed from a different evaluation cannot authorize diagnostics."
        )
    if str(getattr(ctx, "stage", "")) != "oos_test":
        raise BookSealError(f"active context stage {ctx.stage!r} != 'oos_test'")
    if pd.Timestamp(ctx.allowed_start) > pd.Timestamp(oos_start) or pd.Timestamp(
        ctx.allowed_end
    ) < pd.Timestamp(oos_end):
        raise BookSealError(
            f"diagnostics window [{oos_start}, {oos_end}] is not covered by the active book "
            f"context window [{ctx.allowed_start}, {ctx.allowed_end}]"
        )
    # R2 B3: bind to the CANONICAL CLAIM — run/step/provider/calendar/window all matched.
    if artifact_store is None or seal_store is None:
        raise BookSealError(
            "component diagnostics require the artifact_store + holdout seal_store (fail-closed)"
        )
    claim = artifact_store.current(key)
    if claim is None or str(claim.get("request_hash")) != req:
        raise BookSealError(
            f"no canonical claim for book_seal_key {key!r} under request {req!r}"
        )
    ctx_run = str(Path(str(ctx.run_id)).resolve())
    for field, ctx_value in (
        ("run_dir", ctx_run),
        ("step_id", str(ctx.step_id)),
        ("provider_build_id", str(ctx.provider_build_id)),
        ("calendar_policy_id", str(ctx.calendar_policy_id)),
        ("oos_window_id", f"{oos_start}..{oos_end}"),
    ):
        recorded = str(claim.get(field, ""))
        compare = str(Path(recorded).resolve()) if field == "run_dir" and recorded else recorded
        if compare != ctx_value:
            raise BookSealError(
                f"canonical claim {field} {recorded!r} != active context/evaluation "
                f"{ctx_value!r} — foreign-context reuse refused"
            )
    events = seal_store.list_events(seal_key=key)
    if events.empty:
        raise BookSealError(
            f"no holdout seal event exists for book_seal_key {key!r} — a fabricated context "
            "without a real claim is not a sanctioned path"
        )
    event = events.iloc[0].to_dict()
    if str(event.get("event_id", "")) != str(claim.get("seal_event_id", "")):
        raise BookSealError(
            f"holdout seal event {event.get('event_id')!r} != the claim's recorded "
            f"{claim.get('seal_event_id')!r}"
        )
    for field, expect in (
        ("request_hash", req),
        ("run_dir", ctx_run),
        ("step_id", str(ctx.step_id)),
    ):
        if str(event.get(field, "")) != expect:
            raise BookSealError(
                f"holdout seal event {field} {event.get(field)!r} != {expect!r} — "
                "foreign-context reuse refused"
            )

    # the SEALED manifest is the only source of the observable component set (R2 B2/B3)
    manifest = artifact_store.load_component_manifest(book_seal_key=key, request_hash=req)
    components = manifest.get("components")
    if not isinstance(components, Mapping) or not components:
        raise BookSealError("sealed component manifest is empty/malformed")
    sides = {str(fid): str(spec.get("side", "")) for fid, spec in components.items()}
    bad_sides = {f: s for f, s in sides.items() if s not in ("long", "short")}
    if bad_sides:
        raise BookSealError(f"sealed manifest has non-held-side directions {bad_sides}")
    factor_exprs = {str(fid): str(spec.get("expr", "")) for fid, spec in components.items()}
    if any(not e.strip() for e in factor_exprs.values()):
        raise BookSealError("sealed manifest has blank factor expressions")
    book_plan_hash = str(claim.get("book_plan_hash", ""))

    if compute_metrics_fn is None:
        from src.research_orchestrator.promotion_evidence import _compute_oos_per_factor_metrics
        compute_metrics_fn = _compute_oos_per_factor_metrics

    per_factor, max_label_realization = compute_metrics_fn(
        factor_exprs=dict(factor_exprs), oos_start=oos_start, oos_end=oos_end,
        qlib_dir=qlib_dir, horizon=horizon, n_quantiles=n_quantiles, trade_cal=trade_cal,
    )
    # R1 B4 completeness: exact coverage + finite mandatory metrics, else fail-closed.
    missing = sorted(set(sides) - set(per_factor))
    if missing:
        raise BookSealError(
            f"component diagnostics incomplete: no metrics for frozen-set members {missing}"
        )
    for fid in sides:
        for metric in MANDATORY_DIAGNOSTIC_METRICS:
            value = per_factor[fid].get(metric)
            try:
                finite = value is not None and math.isfinite(float(value))
            except (TypeError, ValueError):
                finite = False
            if not finite:
                raise BookSealError(
                    f"component diagnostics for {fid!r} have non-finite {metric}={value!r} — "
                    "an empty/NaN diagnostics leg must never read as healthy"
                )
    reference = evaluate_sealed_oos_bar(sides, per_factor)
    weights = {str(k): float(v) for k, v in (component_weights or {}).items()}
    oos_window_id = f"{oos_start}..{oos_end}"
    rows: list[dict[str, Any]] = []
    for entry in reference.results:
        fid = str(entry["factor"])
        rows.append(
            {
                "run_type": "book_component_diagnostic",
                "book_plan_hash": str(book_plan_hash),
                "book_seal_key": key,
                "component_factor_id": fid,
                "component_side": entry["side"],
                "component_weight": weights.get(fid),
                "oos_window_id": oos_window_id,
                "oos_rank_icir": entry["oos_rank_icir"],
                "oos_ls_sharpe": entry["oos_ls_sharpe"],
                "aligned_rank_icir": entry["aligned_rank_icir"],
                "aligned_ls_sharpe": entry["aligned_ls_sharpe"],
                # the retired factor-level bar — a diagnostic REFERENCE line, never a gate
                "reference_pass": bool(entry["pass"]),
                "spent_in_book_context": True,
                "fresh_oos_eligible": False,
                "promotion_eligible": False,
            }
        )
    if len(rows) != len(sides):
        raise BookSealError(
            f"component diagnostics produced {len(rows)} rows for {len(sides)} frozen-set "
            "members — coverage must be exact"
        )
    return {
        "rows": rows,
        "n_components": len(rows),
        "n_reference_pass": int(reference.n_pass),
        "max_label_realization_date": max_label_realization,
        "note": (
            "gross factor-level OOS diagnostics inside the claimed book seal (attribution: "
            "'signal decayed' vs 'execution ate it'); reference_pass is the retired "
            "factor-level bar as a reference line, NOT a gate; no status minted."
        ),
    }


# ─────────────────────────────────────────────── the book sealed evaluation ──


def _request_hash(
    *,
    identity: BookSealIdentity,
    mode: str,
    provider_build_id: str,
    calendar_policy_id: str,
    hypothesis_id: str,
    profile_id: str,
    factor_exprs: Mapping[str, str],
    horizon: int,
    n_quantiles: int,
    component_weights: Mapping[str, float] | None,
) -> str:
    """The ONE-evaluation identity (R1 B1): everything that determines what the sealed
    evaluation computes. run_dir/step_id are deliberately NOT here — they are the
    resume-binding fields, checked separately; a changed ANY-of-these can never resume
    a prior spend."""
    return payload_hash(
        {
            "book_seal_key": identity.book_seal_key,
            "mode": str(mode),
            "provider_build_id": str(provider_build_id),
            "calendar_policy_id": str(calendar_policy_id),
            "hypothesis_id": str(hypothesis_id),
            "profile_id": str(profile_id),
            "factor_exprs": {str(k): str(v) for k, v in sorted(factor_exprs.items())},
            "horizon": int(horizon),
            "n_quantiles": int(n_quantiles),
            "component_weights": {
                str(k): float(v) for k, v in sorted((component_weights or {}).items())
            },
        }
    )


def _require_run_local(path: str | Path, run_dir: str | Path, label: str) -> None:
    """R1 Minor 1: dryrun stores MUST live under the run directory — a misconfigured
    dry run must be structurally unable to write the global stores."""
    resolved = Path(path).resolve()
    root = Path(run_dir).resolve()
    if not resolved.is_relative_to(root):
        raise BookSealError(
            f"dryrun {label} ({resolved}) must be run-local (under {root}) — a dry run may "
            "never touch the global seal/ledger stores"
        )


def run_book_sealed_evaluation(
    *,
    plan: DeploymentFrozenPlan,
    selected_set_hash: str,
    execution_envelope_hash: str,
    eval_protocol_hash: str,
    oos_start: str,
    oos_end: str,
    book_backtest_fn: Callable[[], Mapping[str, Any]],
    frozen_set,
    factor_exprs: Mapping[str, str],
    qlib_dir: str,
    seal_store_dir: str | Path,
    ledger_root: str | Path,
    run_dir: str,
    step_id: str,
    hypothesis_id: str,
    provider_build_id: str,
    calendar_policy_id: str,
    mode: str = "dryrun",
    structural_family: str = "",
    profile_id: str = "book_sealed_evaluation",
    multiplicity_ack: bool = False,
    multiplicity_override_id: str = "",
    component_weights: Mapping[str, float] | None = None,
    horizon: int = 20,
    n_quantiles: int = 10,
    compute_metrics_fn: Callable[..., tuple[dict, str]] | None = None,
    trade_cal=None,
    seal_store=None,
    artifact_store: BookSealArtifactStore | None = None,
    diagnostic_store: StrategyComponentDiagnosticStore | None = None,
    override_store: OverrideAuthorizationStore | None = None,
) -> dict[str, Any]:
    """v1.4 A2 (post-R1-REWORK) — spend the ONE book seal and produce the full A2
    artifact, as a persisted state machine.

    Fresh path (no prior state for this ``book_seal_key``), each step fail-closed
    BEFORE the next:

    1. derive ``BookSealIdentity`` → ``book_seal_key`` + the evaluation
       ``request_hash``;
    2. mode/window policy: ``live`` is REFUSED until the governed S6 runner exists
       (R1 B4 interim — the caller-supplied callable cannot attest event-driven
       total-return 1×); ``dryrun`` refuses virgin windows and requires RUN-LOCAL
       stores (R1 m1);
    3. ATOMIC spend reservation (``reserve_book_spend`` — R1 B5): recognize-resume,
       count, enforce the virgin budget (warn band needs ``multiplicity_ack``; the
       hard threshold needs a consume-once ``a6_multiplicity`` authorization, never a
       boolean), append the spend-on-attempt row — all under one lock, BEFORE the
       claim (a crash between over-counts, never under-counts);
    4. CLAIM the holdout seal (``seal_key=book_seal_key``, request-hash-bound);
    5. persist ``claimed`` in the artifact store, then INSIDE the claimed
       ``ResearchAccessContext``: run the book backtest ONCE and IMMEDIATELY persist
       the immutable verdict (``verdict_persisted``); then the component diagnostics
       (verified against the real seal event, exact coverage, finite metrics), whose
       rows are durably appended to the diagnostic store; ``complete`` persists the
       canonical artifact (content-addressed by ``artifact_hash``).

    Resume path (prior state exists): the request must hash-match, ``run_dir`` /
    ``step_id`` / provider ids must match, ``complete`` REFUSES (a completed
    evaluation is never re-run — R1 B1), ``claimed`` re-runs the backtest (no verdict
    was ever persisted — this is the first completion, not a re-run), and
    ``verdict_persisted`` / ``diagnostics_failed`` reuse the PERSISTED verdict and
    finish ONLY the diagnostics. ``book_backtest_fn`` is never called once a verdict
    exists.

    A diagnostics failure persists ``diagnostics_failed`` and raises
    :class:`BookSealDiagnosticsError` (R1 B1 exact replacement) — the seal is spent,
    the verdict is preserved, and promotion stays blocked until a resume completes the
    diagnostics.
    """
    if mode not in VALID_MODES:
        raise BookSealError(f"mode must be one of {VALID_MODES}, got {mode!r}")
    if mode == "live":
        raise BookSealError(
            "live book seals are REFUSED until the governed S6 book runner exists (GPT PR3 "
            "R1 Blocker 4): the promotion-driving number must come from an attested "
            "event-driven total-return 1x engine bound to a formal execution profile — a "
            "caller-supplied callable cannot attest that. Run mode='dryrun' for the "
            "burned-window pilot; the S6 runner PR lifts this."
        )
    if not str(oos_start).strip() or not str(oos_end).strip():
        raise BookSealError("oos_start and oos_end are required")
    if not str(provider_build_id).strip() or not str(calendar_policy_id).strip():
        raise BookSealError(
            "provider_build_id and calendar_policy_id are required (the spend is "
            "generation-bound; blank ids would break crash-resume binding)"
        )
    # R2 Blocker 2: the seal must bind the ACTUAL observed book — the frozen set must be
    # the real typed object, must hash-match the plan, and the expressions must cover the
    # selected members EXACTLY (no foreign factor can ride a book's seal, no member can
    # be silently dropped). The canonical component manifest is sealed into the claim and
    # is the diagnostics leg's only component source.
    from src.research_orchestrator.frozen_selection_set import FrozenSelectionSet

    if not isinstance(frozen_set, FrozenSelectionSet):
        raise BookSealError(
            f"frozen_set must be a FrozenSelectionSet (got {type(frozen_set).__name__}) — "
            "the seal binds the actual observed book, not a look-alike"
        )
    if str(frozen_set.frozen_set_hash) != str(plan.frozen_set_hash):
        raise BookSealError(
            f"plan.frozen_set_hash {plan.frozen_set_hash!r} != frozen_set.frozen_set_hash "
            f"{frozen_set.frozen_set_hash!r} — the plan and the observed set must be the same book"
        )
    sides_check = sides_from_frozen_set(frozen_set)   # raises on non-held-side directions
    selected_ids = set(sides_check)
    if not selected_ids:
        raise BookSealError("frozen_set has no selected members")
    if set(map(str, factor_exprs)) != selected_ids:
        raise BookSealError(
            f"factor_exprs must cover the frozen set EXACTLY: exprs={sorted(map(str, factor_exprs))} "
            f"vs selected={sorted(selected_ids)}"
        )
    component_manifest = {
        "components": {
            sf.factor_id: {
                "version": int(sf.version),
                "definition_hash": str(sf.definition_hash),
                "side": str(sf.expected_direction),
                "expr": str(factor_exprs[sf.factor_id]),
            }
            for sf in frozen_set.selected
        }
    }

    identity = BookSealIdentity.from_plan(
        plan,
        selected_set_hash=selected_set_hash,
        execution_envelope_hash=execution_envelope_hash,
        eval_protocol_hash=eval_protocol_hash,
        oos_window_id=f"{oos_start}..{oos_end}",
    )
    book_seal_key = identity.book_seal_key
    oos_window_id = identity.oos_window_id
    virgin = is_virgin_window(oos_end)
    request_hash = _request_hash(
        identity=identity, mode=mode, provider_build_id=provider_build_id,
        calendar_policy_id=calendar_policy_id, hypothesis_id=hypothesis_id,
        profile_id=profile_id, factor_exprs=factor_exprs, horizon=horizon,
        n_quantiles=n_quantiles, component_weights=component_weights,
    )

    if mode == "dryrun":
        if virgin:
            raise BookSealError(
                "dryrun REFUSED on a virgin (post-2026-02-27) window: the §5 pilot runs on "
                "already-burned windows ONLY — a dry-run that observes virgin data still "
                "contaminates it."
            )
        _require_run_local(seal_store_dir, run_dir, "seal_store_dir")
        _require_run_local(ledger_root, run_dir, "ledger_root")

    ledger = OosWindowLedgerStore(ledger_root)
    if artifact_store is None:
        artifact_store = BookSealArtifactStore(ledger_root)
    if diagnostic_store is None:
        diagnostic_store = StrategyComponentDiagnosticStore(ledger_root)
    if seal_store is None:
        from src.research_orchestrator.holdout_seal import HoldoutSealStore
        seal_store = HoldoutSealStore(seal_store_dir)

    # ── fresh vs resume: derived from the persisted state, never a caller flag (R1 B1) ──
    state_row = artifact_store.current(book_seal_key)
    resuming = state_row is not None
    if resuming:
        if str(state_row.get("request_hash")) != request_hash:
            raise BookSealError(
                f"resume refused: book_seal_key {book_seal_key} was opened under request_hash "
                f"{state_row.get('request_hash')!r} but this call hashes to {request_hash!r} — "
                "a changed evaluation request can never continue a prior spend"
            )
        state = str(state_row.get("state"))
        if state == "complete":
            raise BookSealError(
                f"book_seal_key {book_seal_key} is COMPLETE — a completed sealed evaluation is "
                "never re-run (one seal, one persisted result). Load the canonical artifact "
                "from the BookSealArtifactStore instead."
            )
        for field, current in (
            ("run_dir", str(Path(str(run_dir)).resolve())),
            ("step_id", str(step_id)),
            ("provider_build_id", str(provider_build_id)),
            ("calendar_policy_id", str(calendar_policy_id)),
            ("mode", str(mode)),
        ):
            recorded = str(state_row.get(field, ""))
            compare = str(Path(recorded).resolve()) if field == "run_dir" and recorded else recorded
            if compare != current:
                raise BookSealError(
                    f"resume refused: {field} mismatch (recorded {recorded!r}, resume {current!r})"
                )

    # ── atomic spend reservation, then the claim (fresh path only for the claim row) ──
    # The a6 authorization is consumed ONLY on a fresh spend attempt — a resume's
    # reservation already exists (resumed=True short-circuits the budget check), and
    # re-consuming a single-use authorization would wrongly refuse the recovery.
    if override_store is None:
        override_store = OverrideAuthorizationStore(seal_store_dir)
    if multiplicity_override_id and not resuming:
        # consume-once (fresh spends only — a resume's reservation already exists);
        # the reservation below RE-READS the consumed record from the store
        # (require_consumed, request-bound) — caller input is never the authorization.
        override_store.consume_authorization(
            kind="a6_multiplicity", override_id=multiplicity_override_id,
            oos_window_id=oos_window_id, scope_key=book_seal_key,
            consumed_by_request_hash=request_hash,
        )
    reservation = ledger.reserve_book_spend(
        oos_window_id=oos_window_id, book_seal_key=book_seal_key,
        frozen_set_hash=str(plan.frozen_set_hash), book_plan_hash=plan.plan_hash,
        request_hash=request_hash, structural_family=str(structural_family),
        factor_ids=sorted(str(k) for k in factor_exprs), seal_mode=mode,
        virgin=virgin, warn_threshold=VIRGIN_WARN, hard_threshold=VIRGIN_HARD,
        multiplicity_ack=multiplicity_ack, override_store=override_store,
        multiplicity_override_id=str(multiplicity_override_id),
    )

    if not resuming:
        claim_kwargs = dict(
            design_hash=plan.plan_hash,
            hypothesis_id=str(hypothesis_id),
            structural_family=str(structural_family),
            profile_id=str(profile_id),
            run_dir=str(run_dir),
            step_id=str(step_id),
            stage="oos_test",
            seal_key=book_seal_key,
            provider_build_id=str(provider_build_id),
            calendar_policy_id=str(calendar_policy_id),
            request_hash=request_hash,
        )
        try:
            seal_event = seal_store.claim_holdout_access(allow_same_run=False, **claim_kwargs)
        except ValueError:
            # crash-recovery gap: a prior attempt claimed the seal but died before the
            # artifact-store row was opened. Recovery is legitimate ONLY if the existing
            # event matches this run/step/provider/request (allow_same_run enforces it);
            # a foreign or changed-request claim re-raises fail-closed.
            seal_event = seal_store.claim_holdout_access(allow_same_run=True, **claim_kwargs)
        state_row = artifact_store.open_claim(
            book_seal_key=book_seal_key, request_hash=request_hash,
            run_dir=str(Path(str(run_dir)).resolve()), step_id=str(step_id), mode=mode,
            oos_window_id=oos_window_id, provider_build_id=str(provider_build_id),
            calendar_policy_id=str(calendar_policy_id),
            seal_event_id=str(seal_event.get("event_id", "")),
            book_plan_hash=plan.plan_hash,
            component_manifest=component_manifest,
        )
    else:
        # the claim already happened; recover the recorded event (same-run, request-bound)
        seal_event = seal_store.claim_holdout_access(
            design_hash=plan.plan_hash, hypothesis_id=str(hypothesis_id),
            structural_family=str(structural_family), profile_id=str(profile_id),
            run_dir=str(run_dir), step_id=str(step_id), stage="oos_test",
            allow_same_run=True, seal_key=book_seal_key,
            provider_build_id=str(provider_build_id),
            calendar_policy_id=str(calendar_policy_id), request_hash=request_hash,
        )

    import pandas as pd

    from src.research_orchestrator.research_access_context import (
        ResearchAccessContext,
        research_access_context,
    )

    book_ctx = ResearchAccessContext(
        run_id=str(Path(str(run_dir)).resolve()), step_id=str(step_id), stage="oos_test",
        design_hash=plan.plan_hash,
        allowed_start=pd.Timestamp(oos_start), allowed_end=pd.Timestamp(oos_end),
        provider_build_id=str(provider_build_id), calendar_policy_id=str(calendar_policy_id),
        holdout_seal_claimed=True, seal_key=book_seal_key, request_hash=request_hash,
    )

    def _validated_verdict(book_metrics) -> dict[str, Any]:
        if not isinstance(book_metrics, Mapping) or not book_metrics:
            raise BookSealError(
                f"book_backtest_fn must return a non-empty metrics mapping, got "
                f"{type(book_metrics)!r}"
            )
        return evaluate_pre_declared_bar(book_metrics, plan.pre_declared_bar).to_dict()

    with research_access_context(book_ctx):
        # R2 Blocker 1: read-state → evaluate → persist is ATOMIC under the store's
        # per-key lock — a concurrent same-key resume serializes and receives the
        # persisted verdict; the backtest can never execute twice for one request.
        verdict_dict = artifact_store.run_or_load_verdict(
            book_seal_key=book_seal_key, request_hash=request_hash,
            evaluator=book_backtest_fn, make_verdict=_validated_verdict,
        )

        try:
            diagnostics = run_component_diagnostics_in_book_context(
                book_seal_key=book_seal_key, request_hash=request_hash,
                artifact_store=artifact_store, seal_store=seal_store,
                oos_start=oos_start, oos_end=oos_end, qlib_dir=qlib_dir,
                horizon=horizon, n_quantiles=n_quantiles,
                component_weights=component_weights,
                compute_metrics_fn=compute_metrics_fn, trade_cal=trade_cal,
            )
        except Exception as exc:  # noqa: BLE001 — persist the failed state, then raise (R1 B1)
            artifact_store.mark_diagnostics_failed(
                book_seal_key=book_seal_key, request_hash=request_hash,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise BookSealDiagnosticsError(
                f"component diagnostics failed for {book_seal_key} — the seal is SPENT, the "
                f"book verdict is persisted, and promotion is blocked; resume (same request, "
                f"run_dir, step_id) finishes ONLY the diagnostics. Cause: {exc}"
            ) from exc

    diagnostic_row_ids = diagnostic_store.append_rows(
        [{**row, "request_hash": request_hash} for row in diagnostics["rows"]]
    )
    diagnostics["diagnostic_record_ids"] = diagnostic_row_ids

    if virgin:
        governing_report = virgin_window_multiplicity(ledger, oos_window_id, pending_self=False)
    else:
        governing_report = oos_window_multiplicity(ledger, oos_window_id, pending_self=False)

    artifact: dict[str, Any] = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_type": "book_sealed_evaluation",
        "mode": mode,
        "created_at": _now(),
        "book_seal_key": book_seal_key,
        "request_hash": request_hash,
        "book_seal_identity": identity._payload(),
        "plan": plan._payload(),
        "oos_window_id": oos_window_id,
        "virgin_window": bool(virgin),
        "provider_build_id": str(provider_build_id),
        "calendar_policy_id": str(calendar_policy_id),
        "run_dir": str(Path(str(run_dir)).resolve()),
        "step_id": str(step_id),
        "seal_event": {k: str(v) for k, v in dict(seal_event).items()},
        "spend_reservation_record_id": str(reservation.get("record_id", "")),
        "book_verdict": verdict_dict,
        "component_diagnostics": diagnostics,
        "component_diagnostics_ok": True,
        "component_diagnostics_error": "",
        "multiplicity": governing_report.to_dict(),
        # promotion eligibility is a NECESSARY precondition the strategy-registry gate
        # re-verifies from the CANONICAL stored artifact; never sufficient by itself.
        "promotion_eligible": bool(mode == "live" and verdict_dict.get("bar_passed") is True),
    }
    completed = artifact_store.complete(
        book_seal_key=book_seal_key, request_hash=request_hash, artifact=artifact,
    )
    artifact["artifact_hash"] = str(completed.get("artifact_hash", ""))
    return artifact
