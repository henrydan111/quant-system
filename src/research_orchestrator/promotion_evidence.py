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
# R11 Blocker: ONE constant — the executable axes ARE the screening horizons; a
# declared horizon outside this set was runtime-EQUAL but never computed (NaN metrics
# on a consumed seal).
from src.alpha_research.factor_eval_skill.sealed_oos import EXECUTABLE_HORIZONS

SCREENING_HORIZONS = EXECUTABLE_HORIZONS

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


def resolve_frozen_catalog_expressions(
    frozen_set,
    *,
    catalog: Mapping[str, str] | None = None,
    definition_hashes: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """PR3 R4 Blocker 3 — the ONLY expression source for a sealed factor-level
    reproduction: the CURRENT code catalog, definition-hash-verified against the frozen
    set. A caller can never inject expressions (an unselected factor, a swapped
    expression, or a drifted definition all refuse):

    * every ``SelectedFactor`` must exist in the catalog;
    * the current catalog ``definition_hash`` must EQUAL the frozen
      ``SelectedFactor.definition_hash`` (the P1.3 definition-binding parity primitive);
    * exactly the selected ids are returned — nothing more.

    ``catalog`` / ``definition_hashes`` are injectable for tests; live defaults are
    ``get_factor_catalog(include_new_data=True)`` and
    ``FactorRegistryStore.current_catalog_definition_hashes()`` (recomputed from code,
    read-only)."""
    if catalog is None:
        from src.alpha_research.factor_library.catalog import get_factor_catalog

        catalog = get_factor_catalog(include_new_data=True)
    if definition_hashes is None:
        from src.alpha_research.factor_registry.store import FactorRegistryStore

        registry_root = _PROJECT_ROOT / "data" / "factor_registry"
        definition_hashes = FactorRegistryStore(registry_root).current_catalog_definition_hashes()
    exprs: dict[str, str] = {}
    for sf in frozen_set.selected:
        fid = str(sf.factor_id)
        if fid not in catalog:
            raise PromotionEvidenceError(
                f"frozen factor {fid!r} is not in the current catalog — cannot reproduce"
            )
        current_hash = str(definition_hashes.get(fid, ""))
        if not current_hash or current_hash != str(sf.definition_hash):
            raise PromotionEvidenceError(
                f"definition drift for {fid!r}: frozen definition_hash "
                f"{sf.definition_hash!r} != current catalog {current_hash!r} — the sealed "
                "recipe is not reproducible against the live catalog (definition-binding gate)"
            )
        exprs[fid] = str(catalog[fid])
    if not exprs:
        raise PromotionEvidenceError("frozen_set has no selected members")
    return exprs


def reproduce_sealed_oos(
    *,
    frozen_set,
    oos_start: str,
    oos_end: str | None = None,
    qlib_dir: str | Path,
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
    trade_cal=None,
    fresh_window_override_id: str = "",
    multiplicity_ack: bool = False,
    a6_multiplicity_override_id: str = "",
    registration_bar: Mapping[str, Any] | None = None,
    registration_bar_hash: str = "",
    eval_protocol=None,
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
    # R11 Blocker: runtime-EQUAL is not runtime-EXECUTABLE — validate the axes
    # INDEPENDENTLY here (exact-type callers can construct EvalProtocolSpec directly,
    # bypassing the sanctioned constructor), BEFORE any claim or governance action.
    from src.alpha_research.factor_eval_skill.sealed_oos import (
        validate_executable_protocol_axes,
    )

    try:
        horizon, n_quantiles = validate_executable_protocol_axes(
            horizon=horizon,
            n_quantiles=n_quantiles,
        )
    except ValueError as exc:
        raise PromotionEvidenceError(str(exc)) from exc

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
    # R4 Blocker 1: every sealed store derives from the ONE CONFIGURED global holdout
    # root — there is no caller-suppliable seal_root, so a caller cannot fork a parallel
    # sealed world (seal events + authorizations + budget ledger + completion records
    # all live together under the configured root). LATE import: the single monkeypatch
    # target for tests is holdout_seal.resolve_configured_global_holdout_root.
    from src.research_orchestrator.holdout_seal import (
        resolve_configured_global_holdout_root,
    )

    root = resolve_configured_global_holdout_root()
    # R4 Blocker 3: expressions are resolved from the CURRENT catalog, definition-hash-
    # verified against the frozen set — never accepted from the caller.
    factor_exprs = resolve_frozen_catalog_expressions(frozen_set)
    # R3 Blocker 3: the ONE-recipe identity of this reproduction. Everything that
    # determines what the sealed evaluation computes is hash material; the seal claim,
    # the A5 reservation, the authorization consumption, the completion record, and the
    # access context are all bound to it — a changed recipe (different expressions/
    # horizon/quantiles/window/provider generation) can never resume a prior spend.
    from src.alpha_research.factor_eval_skill._hashing import payload_hash as _phash

    # R8 Blocker 3: the bar snapshot is threaded down from the ONE declaration point
    # (cmd_seal reads the global exactly once, binds its hash into EvalProtocolSpec, and
    # passes the SAME snapshot here) — this function NEVER re-reads the module global,
    # and it VERIFIES the snapshot re-hashes to the declared identity, so the judgment
    # actually executed is provably the judgment that was declared.
    if not isinstance(registration_bar, Mapping) or not registration_bar:
        raise PromotionEvidenceError(
            "reproduce_sealed_oos requires the DECLARED registration_bar snapshot "
            "(threaded from the seal declaration; the global is never re-read here — R8 B3)"
        )
    if not str(registration_bar_hash).strip():
        raise PromotionEvidenceError(
            "reproduce_sealed_oos requires the declared registration_bar_hash (R8 B3)"
        )
    _bar = dict(registration_bar)
    _bar_hash = _phash(_bar)
    if _bar_hash != str(registration_bar_hash):
        raise PromotionEvidenceError(
            "registration bar/protocol mismatch: the supplied bar snapshot does not "
            "re-hash to the DECLARED registration_bar_hash — the executed judgment must "
            "be the declared judgment (R8 B3)"
        )
    # R9 Blocker 2: a self-consistent (dict, hash) pair is NOT enough — the declared bar
    # must BE the EXECUTABLE canonical bar (literals + a live evaluator-source hash), so
    # a forged "aligned_rank_icir > 100" rule with its own matching hash can never be
    # persisted as the declared judgment while the real evaluator runs something else.
    # Enforced BEFORE any seal claim or OOS read; a sealed spend under an old bar is a
    # DIFFERENT recipe that refuses here (versioned-evaluator recovery is future work —
    # unknown bars fail closed, never "accept the old dict, run the current evaluator").
    from src.alpha_research.factor_eval_skill.sealed_oos import (
        canonical_registration_bar_snapshot,
    )

    if claim_seal:
        canonical_bar = canonical_registration_bar_snapshot()
        if _bar != canonical_bar or _bar_hash != _phash(canonical_bar):
            raise PromotionEvidenceError(
                "declared registration bar is not the executable canonical bar — only "
                "canonical_registration_bar_snapshot() may govern a sealed spend (R9 B2)"
            )
    # R9 Blocker 2 + R10 Blocker 1: the FULL EvalProtocolSpec travels (never a bare hash
    # string, never a duck-typed look-alike) and it must BE the recipe the runner will
    # actually execute — every identity field is verified against the runtime, not
    # merely hashed. A protocol declaring anything the runtime does not do refuses
    # BEFORE any claim.
    from src.alpha_research.factor_eval_skill.identity import (
        EvalProtocolSpec,
        normalize_enum,
    )
    from src.alpha_research.factor_eval_skill.sealed_oos import EXECUTABLE_PROTOCOL_FIELDS

    if type(eval_protocol) is not EvalProtocolSpec:
        raise PromotionEvidenceError(
            "reproduce_sealed_oos requires the full EvalProtocolSpec (eval_protocol=...) "
            f"— got {type(eval_protocol).__name__!r}; a bare hash string or a shaped "
            "look-alike object is not verifiable identity (R9 B2 / R10 B1)"
        )
    _runtime = {
        "horizon": int(horizon),
        "n_quantiles": int(n_quantiles),
        "oos_window": f"{oos_start}..{oos_end}",
    }
    if (int(eval_protocol.horizon) != _runtime["horizon"]
            or int(eval_protocol.n_quantiles) != _runtime["n_quantiles"]
            or str(eval_protocol.oos_window) != _runtime["oos_window"]):
        raise PromotionEvidenceError(
            f"protocol/runtime mismatch: the declared protocol "
            f"(horizon={eval_protocol.horizon}, n_quantiles={eval_protocol.n_quantiles}, "
            f"oos_window={eval_protocol.oos_window!r}) is not the recipe this runner "
            f"will execute ({_runtime}) — declarations are executed, never merely hashed "
            "(R10 B1)"
        )
    for field, executable_value in EXECUTABLE_PROTOCOL_FIELDS.items():
        declared_value = normalize_enum(str(getattr(eval_protocol, field)))
        if declared_value != normalize_enum(str(executable_value)):
            raise PromotionEvidenceError(
                f"protocol/runtime mismatch: declared {field}={declared_value!r} but the "
                f"sealed registration runtime executes only {executable_value!r} — "
                "unsupported declarations refuse, they are never merely hashed (R10 B1)"
            )
    if str(eval_protocol.registration_bar_hash) != _bar_hash:
        raise PromotionEvidenceError(
            "protocol/bar mismatch: eval_protocol.registration_bar_hash does not equal "
            "the declared bar hash (R9 B2)"
        )
    _fs_obs = getattr(frozen_set, "eval_protocol_hash", None)
    if str(eval_protocol.observation_protocol_hash) != str(_fs_obs):
        raise PromotionEvidenceError(
            "frozen-set observation protocol mismatch: the frozen set was not built "
            "from this protocol's observation identity (R9 B2)"
        )
    eval_protocol_hash = str(eval_protocol.protocol_hash)
    _eval_protocol_payload = eval_protocol._payload()
    a5_request_hash = _phash(
        {
            "kind": "a5_sealed_oos_reproduction",
            "frozen_set_hash": str(seal_hash),
            "factor_exprs": {str(k): str(v) for k, v in sorted(factor_exprs.items())},
            "oos_window": f"{oos_start}..{oos_end}",
            "provider_build_id": str(prov.get("provider_build_id", "")),
            "calendar_policy_id": str(prov.get("calendar_policy_id", "")),
            "horizon": int(horizon),
            "n_quantiles": int(n_quantiles),
            "hypothesis_id": str(hypothesis_id),
            # R6 Blocker 3: the registration bar is part of the sealed recipe identity —
            # a changed bar is a DIFFERENT request, never a reinterpretation.
            "registration_bar_hash": _bar_hash,
            # R8 Blocker 3: the FULL declared protocol identity travels in the request
            # hash and the completion record too.
            "eval_protocol_hash": str(eval_protocol_hash),
        }
    )
    import pandas as pd

    from src.research_orchestrator.research_access_context import (
        ResearchAccessContext,
        research_access_context,
    )

    def _compute_result_block() -> dict:
        # Guard #3 hardening: install the OOS ResearchAccessContext so the
        # qlib_windowed_features reads INSIDE compute_factors are validated against
        # [oos_start, oos_end] + the claimed seal at the data layer (the formal
        # chokepoint). compute_factors requests exactly [oos_start, oos_end] (lookback is
        # internal to the Qlib expr engine -> NaN warmup, no sub-oos_start read), so the
        # read sits within the window. holdout_seal_claimed mirrors claim_seal.
        oos_ctx = ResearchAccessContext(
            run_id=str(run_dir), step_id=step_id, stage="oos_test", design_hash=design_hash,
            allowed_start=pd.Timestamp(oos_start), allowed_end=pd.Timestamp(oos_end),
            provider_build_id=prov.get("provider_build_id", ""),
            calendar_policy_id=prov.get("calendar_policy_id", ""),
            holdout_seal_claimed=bool(claim_seal), seal_key=seal_hash,
            request_hash=a5_request_hash,
        )
        with research_access_context(oos_ctx):
            per_factor, max_label_realization = _compute_oos_per_factor_metrics(
                factor_exprs=factor_exprs, oos_start=oos_start, oos_end=oos_end, qlib_dir=qlib_dir,
                horizon=horizon, n_quantiles=n_quantiles, compute_factors_fn=compute_factors_fn,
                trade_cal=trade_cal,
            )
        # R6 Blocker 3: the registration-bar VERDICT is computed HERE — inside the same
        # locked span that persists the completion record — against the CANONICAL bar
        # whose full semantics travel with the record (bar_json + bar_hash + verdict).
        # Reading a `complete` record later returns THIS verdict; no future code version
        # ever re-judges observed OOS data. A frozen set that cannot yield held sides
        # (legacy stub) records bar_verdict=None — quarantined by the bar consumers.
        from src.alpha_research.factor_eval_skill.sealed_oos import (
            evaluate_sealed_oos_bar,
            sides_from_frozen_set,
        )

        try:
            sides = sides_from_frozen_set(frozen_set)
        except (AttributeError, ValueError):
            sides = None   # legacy stub without held sides — verdict quarantined on read
        bar_verdict = None
        if sides is not None:
            _v = evaluate_sealed_oos_bar(
                sides, per_factor, ls_floor=float(_bar["ls_sharpe_floor"])
            )
            bar_verdict = {"results": list(_v.results), "n_pass": int(_v.n_pass),
                           "n_total": int(_v.n_total)}
        return {
            "registration_bar": dict(_bar),
            "registration_bar_hash": _bar_hash,
            "eval_protocol_hash": str(eval_protocol_hash),
            # R10 B1: the CANONICAL protocol payload is persisted verbatim with its hash.
            "eval_protocol_payload": dict(_eval_protocol_payload),
            "bar_verdict": bar_verdict,
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

    # claim_seal=False (dryrun/no-seal) touches no governance state — compute directly.
    if not claim_seal:
        return _compute_result_block()

    from src.alpha_research.factor_eval_skill.book_seal_stores import A5ReproductionStore
    from src.alpha_research.factor_eval_skill.multiplicity import is_virgin_window
    from src.research_orchestrator.holdout_seal import HoldoutSealStore

    a5_store = A5ReproductionStore(root)
    # R5 Blocker 3: hold a per-seal-key mutex across read-state -> consume/reserve/claim
    # -> compute -> complete, so two runs can NEVER both enter the OOS computation for one
    # seal. A concurrent run blocks here, then (when it acquires) sees the `complete`
    # record and returns the persisted result — never a second observation.
    with a5_store.execution_lock(str(seal_hash)):
        # R4 Blocker 2: the completion state machine is consulted FIRST — a COMPLETED
        # reproduction returns its PERSISTED result and is NEVER recomputed. A still-
        # `claimed` state resumes only for the SAME run (crash recovery); a foreign run or
        # a changed recipe refuses inside open_or_resume.
        prior = a5_store.current(str(seal_hash))
        if prior is not None and str(prior.get("request_hash")) == a5_request_hash \
                and str(prior.get("state")) == "complete":
            return a5_store.load_result(prior)
        is_fresh_open = prior is None

        # v1.4 A5 (PR3 REWORK, R1 Blocker 3): the fresh-window authorization is enforced
        # HERE (the LOWEST shared claim point). It must PRE-EXIST in the
        # OverrideAuthorizationStore (window+scope bound) and is consumed once (idempotent
        # by request on a same-request retry). Only a FRESH open runs consume/reserve/claim.
        if is_fresh_open and is_virgin_window(str(oos_end)):
            from src.alpha_research.factor_eval_skill.book_seal_stores import (
                OverrideAuthorizationStore,
            )

            override_store = OverrideAuthorizationStore(root)
            override_store.consume_authorization(
                kind="a5_fresh_window",
                override_id=str(fresh_window_override_id),
                oos_window_id=f"{oos_start}..{oos_end}",
                scope_key=str(seal_hash),
                consumed_by_request_hash=a5_request_hash,
            )
            # R2 B4 + R3 B2: the A5 spend enters the A6 budget denominator HERE, in the
            # CANONICAL ledger under the configured root; the warn/hard bands are enforced
            # INSIDE the reservation (the a6 authorization is consumed there, request-bound).
            from src.alpha_research.factor_eval_skill.stores import OosWindowLedgerStore

            OosWindowLedgerStore(root).reserve_a5_study_spend(
                oos_window_id=f"{oos_start}..{oos_end}",
                frozen_set_hash=str(seal_hash),
                override_id=str(fresh_window_override_id),
                request_hash=a5_request_hash,
                factor_ids=sorted(str(k) for k in factor_exprs),
                multiplicity_ack=multiplicity_ack,
                override_store=override_store,
                a6_multiplicity_override_id=str(a6_multiplicity_override_id),
            )
        if is_fresh_open:
            # R5 Blocker 1: the seal store is NOT caller-injectable — it derives from the
            # ONE configured global root, same as every other sealed store here.
            seal_store = HoldoutSealStore(root)
            seal_store.claim_holdout_access(
                design_hash=design_hash, hypothesis_id=hypothesis_id, structural_family=structural_family,
                profile_id=profile_id, run_dir=str(run_dir), step_id=step_id, stage="oos_test",
                allow_same_run=allow_same_run, seal_key=seal_hash,
                provider_build_id=str(prov.get("provider_build_id", "")),
                calendar_policy_id=str(prov.get("calendar_policy_id", "")),
                request_hash=a5_request_hash,
            )
        # open (fresh) or same-run resume (crash-while-claimed) the reproduction record —
        # bound to run_dir/step_id; a foreign concurrent run, a changed recipe, or a
        # QUARANTINED execution_started state refuses HERE.
        a5_store.open_or_resume(
            seal_key=str(seal_hash), request_hash=a5_request_hash,
            run_dir=str(run_dir), step_id=step_id, allow_same_run=allow_same_run,
        )
        # R7 Blocker 1: mark execution_started BEFORE any OOS read — a crash between the
        # computation and the persisted result leaves a PERMANENTLY QUARANTINED record
        # (resume refuses); only a crash while still `claimed` (no OOS touched) resumes.
        a5_store.mark_execution_started(
            seal_key=str(seal_hash), request_hash=a5_request_hash
        )
        result_block = _compute_result_block()
        a5_store.complete(
            seal_key=str(seal_hash), request_hash=a5_request_hash, result=result_block
        )
        return result_block


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
