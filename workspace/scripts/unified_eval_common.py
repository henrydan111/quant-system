# ──────────────────────────────────────────────────────────────────────
# script_status: research_tooling
# formal_research_allowed: false
# deployment_target: unified_eval_evidence_only
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   Shared construction of the FROZEN EvalMethodology for the unified-eval drivers
#   (unified_eval_driver.py + unified_eval_driver_data.py). Single source of truth so both
#   drivers stamp the IDENTICAL methodology_hash. Fills the provenance fields GPT R3
#   required and the F-audit found empty: code_commit (git HEAD) + per-factor
#   definition hashes (FactorRegistryStore.current_catalog_definition_hashes — the same
#   algorithm as the P1.3 definition-binding gate). Reference sets are read LIVE from the
#   registry (approved minus the hardcoded provisional list), so a revoked provisional
#   approval changes the hash and forces a recompute. Read-only w.r.t. all registries.
# ──────────────────────────────────────────────────────────────────────
"""Shared frozen-methodology builder for the unified-eval drivers."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_eval.unified_eval import STYLE_CONTROLS_V1, EvalMethodology

# The 2 report_rc eps_diffusion approvals are PROVISIONAL (canary overridden; revoke if the
# 2026-06-15 canary fails — CLAUDE.md §3.5). Provisionality is a governance fact recorded in the
# approval YAML, not a registry column, so it is pinned here.
PROVISIONAL_FACTORS = ("earn_eps_diffusion_120", "earn_eps_diffusion_60")


def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT,
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:  # noqa: BLE001 — provenance best-effort; empty means "unknown", never crashes
        return ""


def approved_reference_sets() -> tuple[list, list]:
    """(stable, current) approved factor ids, read LIVE from the registry."""
    m = pd.read_parquet(PROJECT_ROOT / "data" / "factor_registry" / "factor_master.parquet")
    cur = m[m["is_current"] == True]  # noqa: E712
    current = sorted(cur.loc[cur["status"] == "approved", "factor_id"])
    stable = [f for f in current if f not in PROVISIONAL_FACTORS]
    return stable, current


def build_frozen_methodology(*, is_start: str, is_end: str,
                             universe_id: str = "univ_all") -> EvalMethodology:
    """The ONE construction all drivers must use (identical hash by construction).

    F2: ``universe_id`` scopes the evaluation domain (one methodology hash per
    domain); the default keeps every pre-F2 caller bit-identical.
    """
    stable, current = approved_reference_sets()
    from src.alpha_research.factor_registry.store import FactorRegistryStore
    def_hashes = FactorRegistryStore(PROJECT_ROOT / "data" / "factor_registry") \
        .current_catalog_definition_hashes()
    ref_members = sorted(set(current) | set(PROVISIONAL_FACTORS))
    return EvalMethodology(
        is_start=is_start, is_end=is_end, universe_id=universe_id,
        reference_set_stable=tuple(stable), reference_set_current=tuple(current),
        provisional_factors=tuple(p for p in PROVISIONAL_FACTORS if p in current),
        code_commit=_git_head(),
        reference_set_definition_hashes=tuple((f, def_hashes.get(f, "")) for f in ref_members),
        style_control_definition_hashes=tuple((f, def_hashes.get(f, "")) for f in STYLE_CONTROLS_V1),
    )
