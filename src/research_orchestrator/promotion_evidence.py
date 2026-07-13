"""Promotion-evidence reproduction harness — the PRODUCER for the promotion gate's artifact.

The promotion gate (`release_gate.evaluate_promotion_artifact`) consumes a `promotion_evidence`
artifact in which a set of PIT-correctness checks + an independent OOS reproduction + a clean git
state are all attested. Nothing produced it (only test fixtures). This module produces it, with the
6 hard guards from the GPT cross-review (see promotion_evidence_harness_design.md §7a):

  1. real holdout-seal claim (HoldoutSealStore.claim_holdout_access), not a self-attested flag;
  2. the seal key = FrozenSelectionSet.frozen_set_hash over the FULL frozen selection set;
  3. leak-free OOS labels via the Phase-4 belt (build_is_windowed_panel(is_end=OOS_END));
  4. exact-field live-provider parity;
  5. skip-as-fail (a check that did not actually run against a present provider -> "failed");
  6. explicit definition binding (catalog hash == frozen-artifact hash).

KEY PRINCIPLE: the leak-free reproduction numbers GOVERN approval — a factor below the bar under
the capped Phase-4 label is a correct rejection, so the harness may attest FEWER than were frozen.

The component gatherers are split from `build_promotion_evidence` (the pure assembler) so the unit
tests can drive the assembler + self-verify + fail-closed logic with injected component results,
while the live gatherers (lint/parity/OOS) run at dry-run/temp/live time.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Mapping

from src.research_orchestrator.release_gate import evaluate_promotion_artifact

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
# The src/data_infra package (pit_backend / pit_alignment_core, reached via collect_pit_canaries)
# uses the src-on-path `from data_infra.X` import convention; ensure src/ is importable so the
# canary chain loads regardless of whether the caller put the project ROOT or src/ on sys.path.
_SRC = str(_PROJECT_ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
# UNFREEZE_PLAN.md Phase 2.2a (GPT R2-M7): no executable hardcoded window
# constant — the spent-OOS boundary resolves lazily from the live manifest's
# declared policy (legacy frozen fallback = that policy's calendar end =
# 2026-02-27, bit-identical pre-thaw). Callers may still pass an explicit
# oos_end; the calendar_end guard cross-checks it against the boundary.
def _default_oos_end() -> str:
    from src.data_infra.pit_research_loader import live_spent_oos_end

    return live_spent_oos_end().strftime("%Y-%m-%d")
PASSED = "passed"
FAILED = "failed"
# The screening's horizon set, mirroring workspace/scripts/run_sealed_oos.py::HORIZONS.
# run_batch_screening produces ls_sharpe at the PRIMARY (first) horizon (5d) — that is
# the exact metric the Round-6 registration bar (LS Sharpe > 1.0) was defined against —
# while rank_icir is read per-horizon (rank_icir_20d). Reproducing with this set + the
# engine="batch" path matches the screening report bit-for-bit (verified: grow_total_
# revenue 3.4441 vs 3.444, rev_turnover 2.6818 vs 2.682).
SCREENING_HORIZONS = (5, 10, 20)

# The 6 PIT canary keys (mirrors pit_canaries.CANARY_KEYS; duplicated here to avoid importing the
# heavy pit chain at module load — validated equal by test).
CANARY_KEYS = (
    "synthetic_lookahead_canary",
    "restatement_canary",
    "q0_canary_multiperiod",
    "q0_canary_stateful_restatement",
    "q0_canary_missing_field",
    "availability_assertion",
)


class PromotionEvidenceError(RuntimeError):
    """The assembled promotion_evidence artifact is not gate-eligible (fail-closed)."""


# ── cheap / fully-testable components ─────────────────────────────────────────────────────────

def collect_pit_canaries() -> dict[str, str]:
    """Run the 6 PIT canaries -> {canary_key: 'passed'|'failed'} (lazy import of the heavy chain)."""
    from src.data_infra.pit_canaries import run_pit_canaries

    return run_pit_canaries()


def capture_git_state(project_root: str | Path | None = None) -> dict:
    """``{dirty_tree, git_sha}``. Fail-closed: any error / non-empty status -> dirty_tree=True."""
    root = str(project_root or _PROJECT_ROOT)
    try:
        status = subprocess.run(["git", "-C", root, "status", "--porcelain"],
                                capture_output=True, text=True, timeout=60)
        sha = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=60)
        if status.returncode != 0 or sha.returncode != 0:
            return {"dirty_tree": True, "git_sha": ""}
        return {"dirty_tree": bool(status.stdout.strip()), "git_sha": sha.stdout.strip()}
    except Exception:
        return {"dirty_tree": True, "git_sha": ""}


def _run_script_passed(rel_path: str, *, project_root: str | Path | None = None, timeout: int = 1200) -> str:
    """Invoke a check script; exit 0 -> 'passed'; non-zero / error / skip -> 'failed' (skip-as-fail)."""
    root = Path(project_root or _PROJECT_ROOT)
    script = root / rel_path
    if not script.exists():
        return FAILED
    try:
        r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                           cwd=str(root), timeout=timeout)
        return PASSED if r.returncode == 0 else FAILED
    except Exception:
        return FAILED


def run_unsafe_pit_dates_lint(*, project_root: str | Path | None = None) -> str:
    return _run_script_passed("scripts/lint_no_unsafe_pit_dates.py", project_root=project_root, timeout=600)


def run_statement_parity(*, project_root: str | Path | None = None) -> str:
    """Exact-field statement provider parity. NOTE: the dry-run MUST confirm the script covers the
    promoted factors' exact `_sq_q*`/`_q4` fields (extend it if not) — coverage is asserted there."""
    return _run_script_passed("workspace/scripts/verify_statement_provider_parity.py", project_root=project_root)


def assert_definition_binding(catalog_hashes: Mapping[str, str], frozen_hashes: Mapping[str, str]) -> dict:
    """Every frozen factor's catalog `definition_hash` MUST equal the frozen-artifact hash.
    Returns ``{bound, mismatched}``; a mismatch/absence means the catalog drifted from the
    definition the OOS validated -> approval must fail or the OOS be re-run (GPT guard #6)."""
    mismatched = sorted(
        f for f, h in frozen_hashes.items()
        if not catalog_hashes.get(f) or catalog_hashes.get(f) != h
    )
    return {"bound": not mismatched, "mismatched": mismatched}


# ── the assembler + self-verify (the orchestration heart) ─────────────────────────────────────

def _load_provider_provenance(qlib_dir: str | Path) -> dict:
    """Live provider provenance: ``{provider_build_id, calendar_policy_id, calendar_end}``.
    `calendar_end` is read from ``calendars/day.txt`` (the daily-QA pattern), not assumed."""
    from src.data_infra.provider_manifest import load_provider_manifest

    qdir = Path(qlib_dir)
    manifest = load_provider_manifest(qdir)
    day_txt = qdir / "calendars" / "day.txt"
    lines = [ln.strip() for ln in day_txt.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        raise PromotionEvidenceError(f"empty calendar at {day_txt}")
    return {
        "provider_build_id": manifest.provider_build_id,
        "calendar_policy_id": manifest.calendar_policy_id,
        "calendar_end": lines[-1],
    }


def _compute_oos_per_factor_metrics(
    *,
    factor_exprs: Mapping[str, str],
    oos_start: str,
    oos_end: str,
    qlib_dir: str | Path,
    horizon: int,
    n_quantiles: int,
    compute_factors_fn=None,
    trade_cal=None,
) -> tuple[dict[str, dict], str]:
    """The screening's EXACT per-factor OOS metric path (``compute_factors(stage="oos_test")`` →
    the ``build_is_windowed_panel`` label-realization belt → ``run_batch_screening``), extracted
    verbatim from :func:`reproduce_sealed_oos` (v1.4 PR3, amendment §2 A2(b)/N3).

    CONTEXT-AGNOSTIC BY DESIGN: this function NEVER installs a ``ResearchAccessContext`` — it
    runs under whatever context the CALLER has active. Exactly two sanctioned callers:

    * :func:`reproduce_sealed_oos` — installs its own OOS context (claimed or not) and calls
      this inside it (the legacy factor-level path, behavior unchanged);
    * ``run_component_diagnostics_in_book_context`` (factor_eval_skill.book_seal) — REUSES the
      book's already-claimed context (``holdout_seal_claimed=True, seal_key=book_seal_key``)
      and must never nest a second context (round-2 N3).

    Returns ``(per_factor, max_label_realization_date)`` where ``per_factor`` is
    ``{factor_id: {"oos_rank_icir", "oos_ls_sharpe", "ls_sharpe_horizon"}}``."""
    from src.alpha_research.factor_lifecycle.walk_forward_validation import build_is_windowed_panel

    if compute_factors_fn is None:
        from src.alpha_research.factor_library import operators
        compute_factors_fn = operators.compute_factors
        adj_expr = getattr(operators, "ADJ_CLOSE", "$close * $adj_factor")
    else:
        adj_expr = "$close * $adj_factor"

    import pandas as pd
    from src.alpha_research.factor_eval.batch_screening import run_batch_screening

    qdir = str(qlib_dir)
    factors_df, fwd_df = compute_factors_fn(catalog=dict(factor_exprs), start_date=oos_start, end_date=oos_end,
                                            horizons=list(SCREENING_HORIZONS), qlib_dir=qdir, kernels=1,
                                            stage="oos_test")
    factors_df = factors_df[[c for c in factor_exprs if c in factors_df.columns]]
    apanel, _ = compute_factors_fn(catalog={"adj_close": adj_expr}, start_date=oos_start, end_date=oos_end,
                                   horizons=None, qlib_dir=qdir, kernels=1, stage="oos_test")
    # The explicit label-realization leak-guard (raises IsEndLeakageError if the longest-horizon
    # label would realize past oos_end); its panel is NOT the scoring metric.
    panel = build_is_windowed_panel(factors_df, apanel["adj_close"], is_end=oos_end,
                                    horizon=max(SCREENING_HORIZONS), trade_cal=trade_cal)
    screen = run_batch_screening(factors_df, fwd_df, horizons=tuple(SCREENING_HORIZONS),
                                 engine="batch", progress_every=0, n_quantiles=n_quantiles)
    per_factor: dict[str, dict] = {}
    for name in factor_exprs:
        if name not in screen.index:
            continue
        row = screen.loc[name]
        ricir, ls = row.get(f"rank_icir_{horizon}d"), row.get("ls_sharpe")
        per_factor[str(name)] = {
            "oos_rank_icir": float(ricir) if ricir is not None and not pd.isna(ricir) else float("nan"),
            "oos_ls_sharpe": float(ls) if ls is not None and not pd.isna(ls) else float("nan"),
            "ls_sharpe_horizon": int(SCREENING_HORIZONS[0]),
        }
    return per_factor, str(getattr(panel, "max_label_realization_date", ""))


def reproduce_sealed_oos(
    *,
    frozen_set,
    factor_exprs: Mapping[str, str],
    oos_start: str,
    oos_end: str | None = None,
    qlib_dir: str | Path,
    seal_root: str | Path,
    run_dir: str,
    design_hash: str,
    hypothesis_id: str = "sealed_oos_winners",
    structural_family: str = "",
    profile_id: str = "promotion_evidence",
    step_id: str = "reproduce_sealed_oos",
    horizon: int = 20,
    n_quantiles: int = 10,
    claim_seal: bool = True,
    allow_same_run: bool = False,
    provider_provenance: Mapping | None = None,
    compute_factors_fn=None,
    seal_store=None,
    trade_cal=None,
    fresh_window_override_id: str = "",
    ledger_root: str | Path | None = None,
) -> dict:
    """GUARDS #1-3: claim the holdout seal (keyed by the FULL frozen set), assert the provider
    calendar end == OOS_END, then reproduce the OOS by re-running the SCREENING'S EXACT path —
    ``run_batch_screening(engine="batch", horizons=SCREENING_HORIZONS)`` over factors recomputed
    through ``compute_factors(stage="oos_test")`` (→ source ``qlib_windowed_features``). This
    matches the Round-6 registration bit-for-bit (it is the same code + same horizons), so the
    bar (LS Sharpe > 1.0, defined against ``ls_sharpe`` = the primary-horizon long-short Sharpe)
    is applied on the exact scale. Leak-freedom is guaranteed by the calendar_end == OOS_END
    assertion (Ref(-h) is NaN past the data boundary for every horizon); the Phase-4 belt
    (``build_is_windowed_panel``) is retained as a redundant explicit leak-guard. Returns the
    ``independent_reproduction`` block with `source='qlib_windowed_features'`, provenance, and
    per-factor `oos_rank_icir` (read at `horizon`) + `oos_ls_sharpe` (primary horizon). The
    metrics GOVERN approval. Injectable deps for tests; live by default."""
    oos_end = oos_end or _default_oos_end()
    prov = dict(provider_provenance) if provider_provenance is not None else _load_provider_provenance(qlib_dir)
    calendar_end = str(prov.get("calendar_end"))
    if calendar_end != str(oos_end):
        # UNFREEZE_PLAN.md D3 item 5: after the calendar thaw the provider end
        # may legitimately exceed OOS_END — but ONLY when oos_end is exactly the
        # policy-recorded spent-OOS boundary (the explicit window binding). Any
        # other mismatch stays fail-closed; we NEVER default to the live end.
        # Label leak-freedom then rests on the retained Phase-4 belt
        # (build_is_windowed_panel(is_end=oos_end) raises IsEndLeakageError on
        # any label realizing past oos_end) + the D3 door clamps.
        if calendar_end < str(oos_end):
            raise PromotionEvidenceError(
                f"provider calendar end {calendar_end!r} is SHORTER than OOS_END "
                f"{oos_end!r}; refusing the reproduction (labels cannot realize)."
            )
        # calendar_end > oos_end: allowed under EXACTLY two bindings (D3.5 /
        # GPT R4-M1 contract) — never inferred from the live end:
        #   1. spent-OOS replay: oos_end IS the policy-recorded spent boundary;
        #   2. sealed fresh-window evaluation: an ACTIVE ResearchAccessContext
        #      with a CLAIMED holdout seal whose window covers [oos_start,
        #      oos_end] and whose provider/policy binding matches the live
        #      provenance this reproduction runs against.
        spent_boundary = None
        try:
            from src.data_infra.provider_context import live_spent_oos_end

            spent_boundary = live_spent_oos_end().strftime("%Y-%m-%d")
        except Exception:
            spent_boundary = None  # unresolvable → only the seal branch can allow
        spent_replay_ok = spent_boundary is not None and str(oos_end) == spent_boundary

        sealed_ok = False
        if not spent_replay_ok:
            from src.research_orchestrator.research_access_context import (
                get_research_access_context,
            )

            ctx = get_research_access_context()
            if ctx is not None and getattr(ctx, "holdout_seal_claimed", False):
                import pandas as _pd

                sealed_ok = (
                    _pd.Timestamp(ctx.allowed_start) <= _pd.Timestamp(oos_start)
                    and _pd.Timestamp(ctx.allowed_end) >= _pd.Timestamp(oos_end)
                    and str(ctx.provider_build_id) == str(prov.get("provider_build_id"))
                    and str(ctx.calendar_policy_id) == str(prov.get("calendar_policy_id"))
                )

        if not (spent_replay_ok or sealed_ok):
            raise PromotionEvidenceError(
                f"provider calendar end {calendar_end!r} > OOS_END {oos_end!r}, and the "
                f"window is neither the policy-recorded spent-OOS boundary "
                f"({spent_boundary!r}) nor covered by an ACTIVE claimed holdout seal "
                "bound to this provider/policy; refusing the reproduction (an unbound "
                "calendar advance would change the OOS labels)."
            )

    seal_hash = frozen_set.frozen_set_hash
    if claim_seal:
        # v1.4 A5 (PR3 REWORK, R1 Blocker 3): this is the LOWEST shared claim point of the
        # factor-level (frozen-set-keyed) path — enforce the fresh-window authorization
        # HERE, not only in the wrappers, so a direct import cannot bypass it. The
        # authorization must PRE-EXIST in the OverrideAuthorizationStore (recorded with an
        # explicit human sign-off + burn statement, window+scope bound) and is consumed
        # exactly once; an invented non-empty string refuses.
        from src.alpha_research.factor_eval_skill.multiplicity import is_virgin_window

        if is_virgin_window(str(oos_end)):
            from src.alpha_research.factor_eval_skill.book_seal_stores import (
                OverrideAuthorizationStore,
            )

            OverrideAuthorizationStore(seal_root).consume_authorization(
                kind="a5_fresh_window",
                override_id=str(fresh_window_override_id),
                oos_window_id=f"{oos_start}..{oos_end}",
                scope_key=str(seal_hash),
            )
            # R2 Blocker 4: the A5 spend enters the A6 budget denominator HERE — the
            # lowest shared claim point — atomically BEFORE the claim, so a direct
            # import can never consume an authorization + claim a virgin seal without
            # the spend being ledgered. Fail-closed: no ledger_root, no virgin claim.
            if not ledger_root:
                raise PromotionEvidenceError(
                    "a virgin-window A5 claim requires ledger_root (the A6 "
                    "OosWindowLedgerStore root) so the spend is reserved BEFORE the "
                    "claim — refusing an unledgered virgin observation"
                )
            from src.alpha_research.factor_eval_skill.stores import OosWindowLedgerStore

            OosWindowLedgerStore(ledger_root).reserve_a5_study_spend(
                oos_window_id=f"{oos_start}..{oos_end}",
                frozen_set_hash=str(seal_hash),
                override_id=str(fresh_window_override_id),
                factor_ids=sorted(str(k) for k in factor_exprs),
            )
        if seal_store is None:
            from src.research_orchestrator.holdout_seal import HoldoutSealStore
            seal_store = HoldoutSealStore(seal_root)
        seal_store.claim_holdout_access(
            design_hash=design_hash, hypothesis_id=hypothesis_id, structural_family=structural_family,
            profile_id=profile_id, run_dir=str(run_dir), step_id=step_id, stage="oos_test",
            allow_same_run=allow_same_run, seal_key=seal_hash,
            # R1 B3: the factor-level claim is provider-generation-bound too.
            provider_build_id=str(prov.get("provider_build_id", "")),
            calendar_policy_id=str(prov.get("calendar_policy_id", "")),
        )

    import pandas as pd

    # Guard #3 hardening (GPT post-impl review #3): install the OOS ResearchAccessContext so the
    # qlib_windowed_features reads INSIDE compute_factors are validated against [oos_start, oos_end]
    # + the claimed seal at the data layer (the formal chokepoint), instead of relying solely on
    # the calendar_end == OOS_END boundary above. compute_factors requests exactly [oos_start,
    # oos_end] (lookback is internal to the Qlib expr engine -> NaN warmup, no sub-oos_start read),
    # so the read sits within the window. holdout_seal_claimed mirrors claim_seal: a real OOS read
    # without a seal claim is correctly refused (HoldoutSealViolation) rather than silently allowed.
    from src.research_orchestrator.research_access_context import (
        ResearchAccessContext,
        research_access_context,
    )
    oos_ctx = ResearchAccessContext(
        run_id=str(run_dir), step_id=step_id, stage="oos_test", design_hash=design_hash,
        allowed_start=pd.Timestamp(oos_start), allowed_end=pd.Timestamp(oos_end),
        provider_build_id=prov.get("provider_build_id", ""),
        calendar_policy_id=prov.get("calendar_policy_id", ""),
        holdout_seal_claimed=bool(claim_seal), seal_key=seal_hash,
    )
    # Reproduce the screening's EXACT inputs AND metric path (extracted, v1.4 PR3:
    # _compute_oos_per_factor_metrics — the shared context-agnostic body). ls_sharpe is
    # run_batch_screening's primary-horizon (5d) long-short Sharpe — the metric the
    # registration bar was defined against; rank_icir is read at `horizon` (20d). The
    # n_quantiles default is the 2026-06-11 decile standard; pass n_quantiles=5 to
    # reproduce pre-unification evidence bit-for-bit.
    with research_access_context(oos_ctx):
        per_factor, max_label_realization = _compute_oos_per_factor_metrics(
            factor_exprs=factor_exprs, oos_start=oos_start, oos_end=oos_end, qlib_dir=qlib_dir,
            horizon=horizon, n_quantiles=n_quantiles, compute_factors_fn=compute_factors_fn,
            trade_cal=trade_cal,
        )
    return {
        "independent_reproduction": {
            "source": "qlib_windowed_features",
            "provider_build_id": prov.get("provider_build_id", ""),
            "calendar_policy_id": prov.get("calendar_policy_id", ""),
            "frozen_set_hash": seal_hash,
            "oos_window": f"{oos_start}..{oos_end}",
            "horizon": horizon,
            "rank_icir_horizon": horizon,
            "ls_sharpe_horizon": int(SCREENING_HORIZONS[0]),
            "metric_note": (
                f"Approval bar reproduced exactly as the Round-6 screening defined it: "
                f"rank_icir at {horizon}d + run_batch_screening's primary-horizon ls_sharpe "
                f"from horizons={tuple(SCREENING_HORIZONS)} (i.e. {SCREENING_HORIZONS[0]}d "
                f"long-short Sharpe). This is the registration metric, not a horizon-consistent "
                f"tradability metric; strategy-level deployment validation is a separate gate."
            ),
            "max_label_realization_date": max_label_realization,
            "per_factor": per_factor,
        }
    }


def build_promotion_evidence(
    *,
    canaries: Mapping[str, str],
    unsafe_pit_dates_lint: str,
    live_provider_parity: str,
    reproduction: Mapping,
    git_state: Mapping,
    promotion_status: str = "approved",
) -> dict:
    """Assemble the gate artifact from component results. Fail-closed: a missing canary key
    defaults to 'failed'; a missing dirty_tree defaults to True. Does NOT self-verify (callers
    use :func:`assert_self_consistent` / :func:`produce_promotion_evidence`)."""
    artifact: dict = {
        "independent_reproduction": dict(reproduction.get("independent_reproduction", reproduction)),
        "unsafe_pit_dates_lint": str(unsafe_pit_dates_lint),
        "live_provider_parity": str(live_provider_parity),
        "dirty_tree": bool(git_state.get("dirty_tree", True)),
        "promotion_status": str(promotion_status),
    }
    for key in CANARY_KEYS:
        artifact[key] = str(canaries.get(key, FAILED))
    git_sha = str(git_state.get("git_sha", "") or "")
    if git_sha:
        artifact["git_sha"] = git_sha
    return artifact


def assert_self_consistent(artifact: Mapping, *, current_git_sha: str | None) -> None:
    """Self-verify the artifact through the SAME gate that will consume it; raise if not eligible.
    So the harness can only ever EMIT a gate-passing artifact (fail-closed self-check)."""
    result = evaluate_promotion_artifact(dict(artifact), current_git_sha=current_git_sha)
    if not result.eligible:
        raise PromotionEvidenceError(
            f"promotion_evidence is NOT gate-eligible (refusing to emit): {list(result.reasons)}"
        )


def produce_promotion_evidence(
    *,
    reproduction: Mapping,
    definition_binding: Mapping,
    project_root: str | Path | None = None,
    canaries: Mapping[str, str] | None = None,
    lint: str | None = None,
    parity: str | None = None,
    git_state: Mapping | None = None,
    promotion_status: str = "approved",
) -> dict:
    """Gather every component (live unless injected), assemble, and SELF-VERIFY. Raises
    PromotionEvidenceError unless the result passes the promotion gate. ``definition_binding``
    (from :func:`assert_definition_binding`) must be bound or this refuses up front (guard #6)."""
    if not definition_binding.get("bound", False):
        raise PromotionEvidenceError(
            f"definition binding failed (catalog drifted from frozen artifact): "
            f"{definition_binding.get('mismatched')}"
        )
    canaries = collect_pit_canaries() if canaries is None else canaries
    lint = run_unsafe_pit_dates_lint(project_root=project_root) if lint is None else lint
    parity = run_statement_parity(project_root=project_root) if parity is None else parity
    git_state = capture_git_state(project_root=project_root) if git_state is None else git_state

    artifact = build_promotion_evidence(
        canaries=canaries, unsafe_pit_dates_lint=lint, live_provider_parity=parity,
        reproduction=reproduction, git_state=git_state, promotion_status=promotion_status,
    )
    assert_self_consistent(artifact, current_git_sha=str(git_state.get("git_sha") or "") or None)
    return artifact
