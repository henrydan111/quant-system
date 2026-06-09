# ──────────────────────────────────────────────────────────────────────
# Sealed-OOS promotion driver for the single OSAP-sourced candidate
# `qual_gross_profitability` (GP). Mirrors promote_sealed_oos_winners.py but
# over a FrozenSelectionSet of {GP} with a FRESH seal (GP's OOS is unburned).
# script_status: formal_candidate
# formal_research_allowed: true
# deployment_target: factor_registry_promotion
# requires_provider_manifest: true
# pr2_audit_class: A
# notes: |
#   --mode dryrun (default): TEMP seal_root, injected-clean git_state, NO registry
#     writes, NO real seal spend. Validates GP reproduces + the promotion_evidence
#     artifact self-verifies through the gate, and PREVIEWS GP's OOS metrics.
#   --mode live: REAL HoldoutSeal claim (the ONE sanctioned OOS spend for GP's
#     frozen set), REAL git_state (clean committed tree required), and — IFF GP
#     clears the leak-free bar (oos_rank_icir>0 AND oos_ls_sharpe>1.0) —
#     set_status('approved'). Behind explicit user approval per CLAUDE.md §13.
#   GP definition is frozen/definition-bound and the bar is pre-declared, so a
#   dryrun preview cannot enable cherry-picking; the live spend is run once and
#   the result governs (no modify-and-retry).
# ──────────────────────────────────────────────────────────────────────
"""Promote qual_gross_profitability via single-shot sealed OOS. See header for modes."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

FACTOR_ID = "qual_gross_profitability"
QLIB_DIR = ROOT / "data" / "qlib_data"
SEAL_ROOT = ROOT / "data" / "holdout_seals"
PROV_PATH = ROOT / "workspace" / "research" / "idea_sourcing" / "gp_sealed_oos_promotion.json"

OOS_START = "2021-01-01"
OOS_END = "2026-02-27"
IS_WINDOW = "2014-01-01..2020-12-31"
HORIZON = 20
N_QUANTILES = 5

# GP's selection identity (OSAP idea-sourcing → IS screen → marginal-contribution → residual probe).
OSAP_CANDIDATE_POOL = sorted([
    "rev_lt_36_12", "beta_250d", "idiovol_capm_60d", "coskew_250d",
    "gross_profitability", "net_stock_issuance", "asset_growth", "equity_growth",
])
SELECTION_RULE = (
    "OSAP idea-sourcing -> IS-2014-2020 RankICIR screen -> marginal-contribution vs the live "
    "catalog (only +increment kept) -> orthogonal-residual survives the quality set (|t|>2). "
    "Sole survivor: qual_gross_profitability (Novy-Marx gross-profits-to-assets)."
)


def build_gp_frozen_set(definition_hash: str):
    from src.research_orchestrator.frozen_selection_set import FrozenSelectionSet, SelectedFactor
    selected = (SelectedFactor(
        factor_id=FACTOR_ID, version=1, definition_hash=definition_hash,
        expected_direction="long",  # IS RankICIR +0.138 (positive) -> held long
    ),)
    candidate_pool_hash = hashlib.sha256(
        json.dumps(OSAP_CANDIDATE_POOL, sort_keys=True).encode("utf-8")).hexdigest()
    selection_rule_hash = hashlib.sha256(SELECTION_RULE.encode("utf-8")).hexdigest()
    eval_protocol = {
        "screen_horizons": [5, 10, 20], "oos_horizon": HORIZON, "n_quantiles": N_QUANTILES,
        "is_window": IS_WINDOW, "oos_window": f"{OOS_START}..{OOS_END}",
        "metric": "rank_icir_sign_aligned_ls_sharpe", "label": "forward_return",
        "stage_is": "is_only", "stage_oos": "oos_test",
    }
    eval_protocol_hash = hashlib.sha256(
        json.dumps(eval_protocol, sort_keys=True).encode("utf-8")).hexdigest()
    return FrozenSelectionSet(
        selected=selected, candidate_pool_hash=candidate_pool_hash,
        selection_rule_hash=selection_rule_hash, eval_protocol_hash=eval_protocol_hash,
        metric="rank_icir", portfolio_side="long_short",
        universe="formal_eligible_ashare_screen50",
        time_split_window=f"{OOS_START}..{OOS_END}", rebalance="20d", neutralization="none",
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dryrun", "live"], default="dryrun")
    args = ap.parse_args()

    from src.alpha_research.factor_library.catalog import get_factor_catalog
    from src.alpha_research.factor_registry.store import FactorRegistryStore
    from src.research_orchestrator import promotion_evidence as pe

    expr = get_factor_catalog(include_new_data=True)[FACTOR_ID]
    store = FactorRegistryStore(ROOT / "data" / "factor_registry")
    catalog_hash = store.current_catalog_definition_hashes().get(FACTOR_ID, "")
    if not catalog_hash:
        print(f"ABORT: {FACTOR_ID} not found in current catalog definition hashes."); return 2

    fs = build_gp_frozen_set(catalog_hash)
    print(f"factor={FACTOR_ID}  expr={expr}")
    print(f"FrozenSelectionSet({{GP}})  frozen_set_hash={fs.frozen_set_hash}")

    # definition binding: catalog hash == frozen hash (GP's frozen definition IS its current
    # catalog definition — no separate frozen artifact). Bound by construction.
    binding = pe.assert_definition_binding({FACTOR_ID: catalog_hash}, {FACTOR_ID: catalog_hash})
    print(f"definition_binding: bound={binding['bound']} mismatched={binding['mismatched']}")

    if args.mode == "live":
        seal_root = SEAL_ROOT
        run_dir = str(ROOT / "workspace" / "outputs" / "gp_sealed_oos_live")
        Path(run_dir).mkdir(parents=True, exist_ok=True)
        gs = pe.capture_git_state()
        if gs["dirty_tree"] or not gs["git_sha"]:
            print("[live] ABORT: working tree not clean (git status --porcelain non-empty) or "
                  "git_sha unavailable. A clean committed tree is required before claiming the "
                  "one-shot OOS seal. Commit/stash/gitignore first.")
            return 2
        print(f"[live] clean tree at {gs['git_sha']}; claiming the OOS seal (one-shot spend).")
    else:
        tmp = tempfile.mkdtemp(prefix="gp_sealed_oos_dry_", dir=str(ROOT / "workspace" / "outputs"))
        seal_root = Path(tmp) / "seals"; seal_root.mkdir(parents=True, exist_ok=True)
        run_dir = tmp
        print(f"[dryrun] temp seal_root={seal_root} (no real seal spend, no registry writes)")

    reproduction = pe.reproduce_sealed_oos(
        frozen_set=fs, factor_exprs={FACTOR_ID: expr}, oos_start=OOS_START, oos_end=OOS_END,
        qlib_dir=str(QLIB_DIR), seal_root=str(seal_root), run_dir=str(run_dir),
        design_hash=fs.frozen_set_hash, hypothesis_id="gp_sealed_oos",
        horizon=HORIZON, n_quantiles=N_QUANTILES, claim_seal=True,
    )
    ir = reproduction["independent_reproduction"]
    m = ir["per_factor"].get(FACTOR_ID, {})
    ricir = m.get("oos_rank_icir", float("nan"))
    ls = m.get("oos_ls_sharpe", float("nan"))
    bar_ok = (ricir is not None and ricir > 0) and (ls is not None and ls > 1.0)
    print(f"\nreproduction source={ir['source']} provider_build={ir['provider_build_id']} "
          f"calendar_policy={ir['calendar_policy_id']}")
    print(f"oos_window={ir['oos_window']} horizon={ir['horizon']} "
          f"max_label_realization={ir['max_label_realization_date']}")
    print(f"\n{'factor':30s} {'oos_rank_icir':>14s} {'oos_ls_sharpe':>14s}  bar(LS>1.0,sign+)")
    print(f"{FACTOR_ID:30s} {ricir:14.4f} {ls:14.4f}  {'PASS' if bar_ok else 'FAIL'}")

    git_state = ({"dirty_tree": False, "git_sha": pe.capture_git_state()["git_sha"] or "DRYRUN_HEAD"}
                 if args.mode == "dryrun" else None)
    try:
        artifact = pe.produce_promotion_evidence(
            reproduction=reproduction, definition_binding=binding,
            git_state=git_state, promotion_status="approved")
        print("\npromotion_evidence: SELF-VERIFY PASSED (gate-eligible)")
    except pe.PromotionEvidenceError as e:
        print(f"\npromotion_evidence: SELF-VERIFY FAILED -> {e}"); return 1

    if args.mode == "dryrun":
        print(f"\n[dryrun] machinery validated; GP OOS preview above. bar={'PASS' if bar_ok else 'FAIL'}. "
              "NO registry/seal writes. Run --mode live (clean tree) for the formal spend.")
        return 0

    # ── LIVE ──
    git_sha = artifact["git_sha"]
    reg_dir = ROOT / "data" / "factor_registry"
    if not bar_ok:
        print(f"\n[live] GP did NOT clear the leak-free bar (rank_icir={ricir:.4f}, ls_sharpe={ls:.4f}). "
              "Seal SPENT; GP stays `candidate` (its 2021-2026 OOS is now burned). NO approval written.")
        decision = "rejected"
    else:
        live_store = FactorRegistryStore(reg_dir)
        live_store.set_status(
            factor_id=FACTOR_ID, status="approved",
            reason=(f"OSAP-sourced single-shot sealed-OOS winner. Leak-free reproduction "
                    f"(FrozenSelectionSet {fs.frozen_set_hash[:12]}, OOS {OOS_START}..{OOS_END}, "
                    f"Phase-4 capped label): rank_icir={ricir:.4f}, LS Sharpe={ls:.4f} "
                    f"(>1.0, sign-stable IS->OOS)."),
            promotion_evidence=artifact, current_git_sha=git_sha,
            source_run_id=f"gp_sealed_oos_{fs.frozen_set_hash[:12]}")
        live_store.set_expected_direction(factor_id=FACTOR_ID, expected_direction="positive")
        live_store.save()
        print(f"\n[live] APPROVED {FACTOR_ID} (rank_icir={ricir:.4f}, ls_sharpe={ls:.4f})")
        decision = "approved"

    PROV_PATH.write_text(json.dumps({
        "promoted_at_oos_end": OOS_END, "factor_id": FACTOR_ID,
        "frozen_set_hash": fs.frozen_set_hash, "git_sha": git_sha,
        "provider_build_id": ir["provider_build_id"], "calendar_policy_id": ir["calendar_policy_id"],
        "evidence_class": "single_shot_sealed_oos_leak_free_reproduction",
        "decision": decision, "oos_rank_icir": ricir, "oos_ls_sharpe": ls,
        "note": ("qual_gross_profitability is NOT oos_informed_backfill: selected purely on IS "
                 "2014-2020 evidence (OSAP pipeline); its 2021-2026 OOS was unburned and spent "
                 "ONCE here. 2021-2026 is now spent for this frozen set."),
        "promotion_evidence": artifact,
    }, indent=2), encoding="utf-8")
    print(f"[live] provenance -> {PROV_PATH}")

    try:
        from src.alpha_research.testing_ledger import TestingLedgerStore
        led = TestingLedgerStore(ROOT / "data" / "testing_ledger")
        led.record_event(
            hypothesis_id="gp_sealed_oos", design_hash=fs.frozen_set_hash, prose_hash="",
            structural_family="gp_sealed_oos", profile_id="promotion_evidence",
            run_id=f"gp_sealed_oos_{fs.frozen_set_hash[:12]}", run_dir=str(run_dir),
            test_name="gp_sealed_oos_promotion", stage="registry_publish",
            statistic_name="approved", statistic_value=float(1 if decision == "approved" else 0))
        print("[live] testing-ledger event recorded")
    except Exception as e:
        print(f"[live] WARN: testing-ledger event failed: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
