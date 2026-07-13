"""v1.4 PR3 — the book-level sealed evaluation: the ``book_seal_key`` claim path, the
pre-declared-bar verdict, and the in-context component diagnostics.

Design (normative): ``workspace/research/factor_eval_methodology/
FACTOR_EVAL_V1.4_AMENDMENT_book_level_promotion.md`` §2 A2/A6/A8 (+ round-2 N2/N3).
This module lands the amendment's named PR3 residuals:

* :func:`run_book_sealed_evaluation` — ONE holdout seal per book, claimed with
  ``seal_key = BookSealIdentity.book_seal_key`` (NO fallback to ``design_hash`` /
  ``frozen_set_hash``), spend-on-attempt, virgin-window A6 budget enforced BEFORE the
  claim, the book event-driven total-return verdict evaluated against the plan's
  PRE-DECLARED bar, and the component-diagnostics leg embedded INSIDE the same claimed
  ``ResearchAccessContext``. Produces the full A2 artifact.
* :func:`run_component_diagnostics_in_book_context` — the ONLY sanctioned component-
  diagnostics path (round-2 N3): REFUSES without an active claimed book context, never
  claims a second seal, never installs a nested context, mints no status
  (``spent_in_book_context=True``, ``fresh_oos_eligible=False``,
  ``promotion_eligible=False``).
* :func:`evaluate_pre_declared_bar` — fail-closed bar logic (missing metric / unknown
  key / ambiguous drawdown sign REFUSE, never pass).

Mode contract: ``mode="dryrun"`` is the §5 burned-window pilot shape — it runs the full
path against CALLER-SUPPLIED (run-local, temporary) seal/ledger stores and marks the
artifact ``promotion_eligible=False``; it REFUSES virgin windows outright (a dry-run
that observed virgin data would still contaminate it). ``mode="live"`` is the one-shot
spend against the GLOBAL stores. The caller supplies the store roots explicitly; a
dry-run pointed at the global stores would waste a burned-window seal row (auditable,
recoverable) but can never touch a virgin window.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from src.alpha_research.factor_eval_skill.identity import BookSealIdentity, DeploymentFrozenPlan
from src.alpha_research.factor_eval_skill.multiplicity import (
    ACTION_ACKNOWLEDGE,
    ACTION_REFUSE,
    ACTION_REQUIRE,
    is_virgin_window,
    oos_window_multiplicity,
    virgin_window_multiplicity,
)
from src.alpha_research.factor_eval_skill.sealed_oos import (
    evaluate_sealed_oos_bar,
    sides_from_frozen_set,
)
from src.alpha_research.factor_eval_skill.stores import OosWindowLedgerStore

ARTIFACT_SCHEMA_VERSION = 1
VALID_MODES = ("dryrun", "live")
# Metrics whose repo-wide convention is NEGATIVE (goal_metrics / result_analysis: a 40%
# drawdown is mdd=-0.40). A `<name>_max` bar bound on one of these is a MAGNITUDE cap:
# pass iff metric >= bound (i.e. no DEEPER than the bound). Enforced with an explicit
# sign assertion so a positive-mdd caller fails loudly instead of silently inverting.
NEGATIVE_CONVENTION_METRICS = frozenset({"mdd", "max_drawdown"})


class BookSealError(RuntimeError):
    """Fail-closed error for the book sealed-evaluation path."""


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
    * a bar key whose metric is MISSING or non-finite raises — it never passes;
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
        if math.isnan(metric_val) or math.isnan(bound):
            raise BookSealError(f"NaN bar/metric for {key!r} — fail-closed, never passes")
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
    book_plan_hash: str,
    frozen_set,
    factor_exprs: Mapping[str, str],
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

    Refuses (fail-closed) unless the ACTIVE ``ResearchAccessContext`` is a claimed
    OOS context whose ``effective_seal_key == book_seal_key`` and whose window covers
    ``[oos_start, oos_end]``. NEVER claims a seal, NEVER installs a (nested) context —
    the metric computation (:func:`promotion_evidence._compute_oos_per_factor_metrics`,
    the screening's exact path) runs under the caller's active context, so its
    ``qlib_windowed_features`` reads are validated against the book seal at the data
    layer. Emits NO promotion evidence and mints NO status: every row carries
    ``run_type='book_component_diagnostic'``, ``spent_in_book_context=True``,
    ``fresh_oos_eligible=False``, ``promotion_eligible=False`` (round-1 m3). The old
    factor-level bar survives only as ``reference_pass`` — a diagnostic line, never a
    gate."""
    import pandas as pd

    from src.research_orchestrator.research_access_context import get_research_access_context

    key = str(book_seal_key).strip()
    if not key:
        raise BookSealError("book_seal_key is required (blank keys are refused)")
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
    if str(getattr(ctx, "stage", "")) != "oos_test":
        raise BookSealError(f"active context stage {ctx.stage!r} != 'oos_test'")
    if pd.Timestamp(ctx.allowed_start) > pd.Timestamp(oos_start) or pd.Timestamp(
        ctx.allowed_end
    ) < pd.Timestamp(oos_end):
        raise BookSealError(
            f"diagnostics window [{oos_start}, {oos_end}] is not covered by the active book "
            f"context window [{ctx.allowed_start}, {ctx.allowed_end}]"
        )

    if compute_metrics_fn is None:
        from src.research_orchestrator.promotion_evidence import _compute_oos_per_factor_metrics
        compute_metrics_fn = _compute_oos_per_factor_metrics

    sides = sides_from_frozen_set(frozen_set)
    per_factor, max_label_realization = compute_metrics_fn(
        factor_exprs=dict(factor_exprs), oos_start=oos_start, oos_end=oos_end,
        qlib_dir=qlib_dir, horizon=horizon, n_quantiles=n_quantiles, trade_cal=trade_cal,
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


def _enforce_multiplicity(report, *, ack: bool, override: bool) -> None:
    """Mirror of orchestration's enforcement: the action is ENFORCED before OOS access."""
    if report.action == ACTION_ACKNOWLEDGE and not (ack or override):
        raise BookSealError(
            f"OOS-window multiplicity requires reviewer acknowledgement "
            f"(n_spent={report.n_spent}): pass multiplicity_ack=True. {report.note}"
        )
    if report.action == ACTION_REQUIRE and not override:
        raise BookSealError(
            f"OOS-window multiplicity requires adjusted stats or an explicit override "
            f"(n_spent={report.n_spent}): pass multiplicity_override=True. {report.note}"
        )
    if report.action == ACTION_REFUSE:
        raise BookSealError(
            f"virgin-window book budget HARD STOP (n_spent={report.n_spent}): a user-signed "
            f"multiplicity override must be recorded BEFORE the spend (A6). {report.note}"
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
    allow_same_run: bool = False,
    multiplicity_ack: bool = False,
    multiplicity_override: bool = False,
    component_weights: Mapping[str, float] | None = None,
    horizon: int = 20,
    n_quantiles: int = 10,
    compute_metrics_fn: Callable[..., tuple[dict, str]] | None = None,
    trade_cal=None,
    seal_store=None,
) -> dict[str, Any]:
    """v1.4 A2 — spend the ONE book seal and produce the full A2 artifact.

    Order (each step fail-closed BEFORE the next):

    1. derive ``BookSealIdentity`` → ``book_seal_key`` (every spend-differentiating
       field is key material; no design_hash/frozen_set_hash fallback);
    2. mode/window policy: ``dryrun`` REFUSES virgin windows (§5 pilot = burned windows
       only); ``live`` on a virgin window enforces the A6 budget (warn 3 / hard 5);
    3. CLAIM the holdout seal keyed by ``book_seal_key`` — SPEND-ON-ATTEMPT: any
       post-claim failure consumes the slot; recovery is same ``run_dir`` + ``step_id``
       via ``allow_same_run`` only (provider/calendar-id bound);
    4. record the D6 ledger book spend (after the claim, so a pre-claim failure never
       overcounts);
    5. install the claimed ``ResearchAccessContext`` (``seal_key=book_seal_key``) and,
       INSIDE it: (a) the book verdict — ``book_backtest_fn()`` net metrics vs the
       plan's PRE-DECLARED bar; (b) the component diagnostics
       (:func:`run_component_diagnostics_in_book_context`, same context, no second
       claim). A diagnostics failure is RECORDED (the seal is already spent; the book
       verdict must survive) and blocks promotion eligibility;
    6. assemble the A2 artifact: identity + verdict + diagnostics + multiplicity +
       provenance. ``promotion_eligible`` is True only for a LIVE run whose bar PASSED
       with healthy diagnostics — the strategy-registry gate re-verifies all of it.

    ``book_backtest_fn`` is the execution seam: a zero-arg callable returning the net
    event-driven TOTAL-RETURN 1× metrics on the declared target universe (the S6
    harness closes over the engine config; this module owns sealing, not execution).
    """
    if mode not in VALID_MODES:
        raise BookSealError(f"mode must be one of {VALID_MODES}, got {mode!r}")
    if not str(oos_start).strip() or not str(oos_end).strip():
        raise BookSealError("oos_start and oos_end are required")
    if not str(provider_build_id).strip() or not str(calendar_policy_id).strip():
        raise BookSealError(
            "provider_build_id and calendar_policy_id are required (the spend is "
            "generation-bound; blank ids would break crash-resume binding)"
        )

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

    if mode == "dryrun" and virgin:
        raise BookSealError(
            "dryrun REFUSED on a virgin (post-2026-02-27) window: the §5 pilot runs on "
            "already-burned windows ONLY — a dry-run that observes virgin data still "
            "contaminates it."
        )

    ledger = OosWindowLedgerStore(ledger_root)
    if virgin:
        report = virgin_window_multiplicity(
            ledger, oos_window_id, override_recorded=multiplicity_override, pending_self=True
        )
    else:
        report = oos_window_multiplicity(ledger, oos_window_id, pending_self=True)
    _enforce_multiplicity(report, ack=multiplicity_ack, override=multiplicity_override)

    if seal_store is None:
        from src.research_orchestrator.holdout_seal import HoldoutSealStore
        seal_store = HoldoutSealStore(seal_store_dir)
    # THE claim — seal_key is the derived book key, explicitly; design_hash carries the
    # plan hash for audit only (the store keys by seal_key when supplied; there is no
    # fallback path here because seal_key is always passed).
    seal_event = seal_store.claim_holdout_access(
        design_hash=plan.plan_hash,
        hypothesis_id=str(hypothesis_id),
        structural_family=str(structural_family),
        profile_id=str(profile_id),
        run_dir=str(run_dir),
        step_id=str(step_id),
        stage="oos_test",
        allow_same_run=allow_same_run,
        seal_key=book_seal_key,
        provider_build_id=str(provider_build_id),
        calendar_policy_id=str(calendar_policy_id),
    )
    ledger.record_book_spend(
        oos_window_id=oos_window_id, book_seal_key=book_seal_key,
        frozen_set_hash=str(plan.frozen_set_hash), seal_mode=mode,
    )

    import pandas as pd

    from src.research_orchestrator.research_access_context import (
        ResearchAccessContext,
        research_access_context,
    )

    book_ctx = ResearchAccessContext(
        run_id=str(run_dir), step_id=str(step_id), stage="oos_test",
        design_hash=plan.plan_hash,
        allowed_start=pd.Timestamp(oos_start), allowed_end=pd.Timestamp(oos_end),
        provider_build_id=str(provider_build_id), calendar_policy_id=str(calendar_policy_id),
        holdout_seal_claimed=True, seal_key=book_seal_key,
    )
    diagnostics: dict[str, Any] | None = None
    diagnostics_error = ""
    with research_access_context(book_ctx):
        book_metrics = book_backtest_fn()
        if not isinstance(book_metrics, Mapping) or not book_metrics:
            raise BookSealError(
                f"book_backtest_fn must return a non-empty metrics mapping, got {type(book_metrics)!r}"
            )
        verdict = evaluate_pre_declared_bar(book_metrics, plan.pre_declared_bar)
        try:
            diagnostics = run_component_diagnostics_in_book_context(
                book_seal_key=book_seal_key, book_plan_hash=plan.plan_hash,
                frozen_set=frozen_set, factor_exprs=factor_exprs,
                oos_start=oos_start, oos_end=oos_end, qlib_dir=qlib_dir,
                horizon=horizon, n_quantiles=n_quantiles,
                component_weights=component_weights,
                compute_metrics_fn=compute_metrics_fn, trade_cal=trade_cal,
            )
        except Exception as exc:  # noqa: BLE001 — the seal is SPENT; preserve the book verdict
            diagnostics_error = f"{type(exc).__name__}: {exc}"

    if virgin:
        final_report = virgin_window_multiplicity(
            ledger, oos_window_id, override_recorded=multiplicity_override, pending_self=False
        )
    else:
        final_report = oos_window_multiplicity(ledger, oos_window_id, pending_self=False)

    component_diagnostics_ok = diagnostics is not None and not diagnostics_error
    artifact: dict[str, Any] = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_type": "book_sealed_evaluation",
        "mode": mode,
        "created_at": _now(),
        "book_seal_key": book_seal_key,
        "book_seal_identity": identity._payload(),
        "plan": plan._payload(),
        "oos_window_id": oos_window_id,
        "virgin_window": bool(virgin),
        "provider_build_id": str(provider_build_id),
        "calendar_policy_id": str(calendar_policy_id),
        "seal_event": dict(seal_event),
        "book_verdict": verdict.to_dict(),
        "component_diagnostics": diagnostics,
        "component_diagnostics_ok": bool(component_diagnostics_ok),
        "component_diagnostics_error": diagnostics_error,
        "multiplicity": final_report.to_dict(),
        # promotion eligibility is a NECESSARY precondition the strategy-registry gate
        # re-verifies (mode/live + bar + diagnostics + seal-event existence + key recompute);
        # it is never sufficient by itself.
        "promotion_eligible": bool(mode == "live" and verdict.bar_passed and component_diagnostics_ok),
    }
    return artifact
