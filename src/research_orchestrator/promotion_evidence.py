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
OOS_END = "2026-02-27"
PASSED = "passed"
FAILED = "failed"

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
