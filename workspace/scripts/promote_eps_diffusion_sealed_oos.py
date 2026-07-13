# ══════════════════════════════════════════════════════════════════════
# HISTORICAL DRIVER (pre-PR3-R4) — DO NOT RE-RUN AS-IS.
# This one-off targeted the PRE-R4 reproduce_sealed_oos signature (caller
# `factor_exprs=` + `seal_root=`). PR3 R4 (2026-07-13) REMOVED both: expressions
# now resolve from the current catalog (definition-hash-verified) and the sealed
# stores derive from the ONE configured global holdout root. This spend is already
# recorded (see the provenance JSON under workspace/research/); the record here is
# preserved for audit, not for re-execution (a sealed OOS window is single-shot).
# ══════════════════════════════════════════════════════════════════════
# ──────────────────────────────────────────────────────────────────────
# Sealed-OOS promotion driver for the report_rc eps_diffusion candidates
# (earn_eps_diffusion_60 / earn_eps_diffusion_120). FrozenSelectionSet of the
# TWO, single fresh seal (their OOS is unburned — selected purely on IS).
# script_status: formal_candidate
# formal_research_allowed: true
# deployment_target: factor_registry_promotion
# requires_provider_manifest: true
# pr2_audit_class: A
# notes: |
#   ⚠⚠ CANARY OVERRIDE ⚠⚠ — the report_rc field approval records a HARD pre-OOS
#   gate: the 2026-06-15 breadth-restatement canary MUST pass before this spend.
#   It has NOT passed (today < 2026-06-15). This driver runs the single-shot OOS
#   ANYWAY, per EXPLICIT user override ("override the canary gate"), with the risk
#   in view: if the breadth primitives are later shown contaminated, this verdict
#   is meaningless AND the only unburned OOS in the registry is permanently spent.
#   The override + risk acceptance is stamped into the provenance + set_status
#   reason for the audit trail.
#
#   --mode dryrun (default): TEMP seal, injected-clean git, NO writes — validates
#     the machinery + previews OOS metrics.
#   --mode live: REAL seal claim (the override spend) + set_status('approved') for
#     factors clearing oos_rank_icir>0 AND oos_ls_sharpe>1.0. Pre-flights: clean
#     committed tree + unsafe_pit_dates lint == passed (checked BEFORE the seal
#     claim so a failing gate can't waste the spend).
# ──────────────────────────────────────────────────────────────────────
"""Promote the 2 eps_diffusion candidates via single-shot sealed OOS (canary OVERRIDDEN)."""
from __future__ import annotations

import argparse, hashlib, json, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

FACTOR_IDS = ["earn_eps_diffusion_60", "earn_eps_diffusion_120"]
QLIB_DIR = ROOT / "data" / "qlib_data"
SEAL_ROOT = ROOT / "data" / "holdout_seals"
PROV_PATH = ROOT / "workspace" / "research" / "idea_sourcing" / "eps_diffusion_sealed_oos_promotion.json"
OOS_START, OOS_END = "2021-01-01", "2026-02-27"
IS_WINDOW = "2014-01-01..2020-12-31"
HORIZON, N_QUANTILES = 20, 5
CANARY_OVERRIDE_REASON = ("EXPLICIT user override 2026-06-09: spend the single-shot OOS BEFORE the "
                          "2026-06-15 breadth-restatement canary, risk (meaningless-if-contaminated "
                          "verdict + permanent loss of the unburned OOS) acknowledged.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dryrun", "live"], default="dryrun")
    args = ap.parse_args()
    from src.alpha_research.factor_library.catalog import get_factor_catalog
    from src.alpha_research.factor_registry.store import FactorRegistryStore
    from src.research_orchestrator import promotion_evidence as pe
    from src.research_orchestrator.frozen_selection_set import FrozenSelectionSet, SelectedFactor

    cat = get_factor_catalog(include_new_data=True)
    store = FactorRegistryStore(ROOT / "data" / "factor_registry")
    cat_hashes = store.current_catalog_definition_hashes()
    exprs = {fid: cat[fid] for fid in FACTOR_IDS}
    hashes = {fid: cat_hashes.get(fid, "") for fid in FACTOR_IDS}
    if not all(hashes.values()):
        print("ABORT: missing catalog definition hash for", [f for f in FACTOR_IDS if not hashes[f]]); return 2

    selected = tuple(SelectedFactor(factor_id=f, version=1, definition_hash=hashes[f],
                                    expected_direction="long") for f in FACTOR_IDS)
    rule = ("report_rc eps_diffusion (analyst EPS-revision breadth) -> size-neutralized IS screen -> "
            "marginal PARTIAL but orthogonal-residual SURVIVES (retains ~100% vs ROE/growth) -> IS "
            "factor_lifecycle gate PASSED (heldout RankICIR 0.42/0.34). Selected on IS only.")
    ph = lambda obj: hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()
    eval_protocol = {"screen_horizons": [5,10,20], "oos_horizon": HORIZON, "n_quantiles": N_QUANTILES,
                     "is_window": IS_WINDOW, "oos_window": f"{OOS_START}..{OOS_END}",
                     "metric": "rank_icir_sign_aligned_ls_sharpe", "label": "forward_return",
                     "stage_is": "is_only", "stage_oos": "oos_test"}
    fs = FrozenSelectionSet(selected=selected,
        candidate_pool_hash=ph(["earn_eps_diffusion_20","earn_eps_diffusion_60","earn_eps_diffusion_120",
                                "eps_up_ratio","eps_rev_intensity"]),
        selection_rule_hash=hashlib.sha256(rule.encode()).hexdigest(), eval_protocol_hash=ph(eval_protocol),
        metric="rank_icir", portfolio_side="long_short", universe="report_rc_covered_ashare",
        time_split_window=f"{OOS_START}..{OOS_END}", rebalance="20d", neutralization="size")
    print(f"FrozenSelectionSet({{{','.join(FACTOR_IDS)}}})  frozen_set_hash={fs.frozen_set_hash}")
    binding = pe.assert_definition_binding(hashes, hashes)
    print(f"definition_binding: bound={binding['bound']}")
    print("\n*** CANARY OVERRIDE *** spending the single-shot OOS BEFORE the 2026-06-15 breadth canary (user override).\n")

    if args.mode == "live":
        seal_root = SEAL_ROOT; run_dir = str(ROOT / "workspace" / "outputs" / "eps_diffusion_sealed_oos_live")
        Path(run_dir).mkdir(parents=True, exist_ok=True)
        gs = pe.capture_git_state()
        if gs["dirty_tree"] or not gs["git_sha"]:
            print("[live] ABORT: working tree not clean — commit/stash first (gate needs dirty_tree=False)."); return 2
        lint = pe.run_unsafe_pit_dates_lint()
        if lint != "passed":
            print(f"[live] ABORT: unsafe_pit_dates lint = {lint!r} (must be 'passed' BEFORE the seal claim "
                  "so a failing gate can't waste the one-shot OOS)."); return 2
        print(f"[live] clean tree at {gs['git_sha'][:12]}, lint passed; claiming the OOS seal (override spend).")
    else:
        tmp = tempfile.mkdtemp(prefix="eps_diff_dry_", dir=str(ROOT / "workspace" / "outputs"))
        seal_root = Path(tmp) / "seals"; seal_root.mkdir(parents=True, exist_ok=True); run_dir = tmp
        print(f"[dryrun] temp seal_root (no real spend, no writes)")

    reproduction = pe.reproduce_sealed_oos(frozen_set=fs, factor_exprs=exprs, oos_start=OOS_START,
        oos_end=OOS_END, qlib_dir=str(QLIB_DIR), seal_root=str(seal_root), run_dir=str(run_dir),
        design_hash=fs.frozen_set_hash, hypothesis_id="eps_diffusion_sealed_oos",
        horizon=HORIZON, n_quantiles=N_QUANTILES, claim_seal=True)
    ir = reproduction["independent_reproduction"]
    print(f"\nreproduction source={ir['source']} provider_build={ir['provider_build_id']} "
          f"calendar={ir['calendar_policy_id']} oos={ir['oos_window']} max_label={ir['max_label_realization_date']}")
    print(f"\n{'factor':28s} {'oos_rank_icir':>14s} {'oos_ls_sharpe':>14s}  bar(LS>1.0,sign+)")
    bar = []
    for f in FACTOR_IDS:
        m = ir["per_factor"].get(f, {}); ri = m.get("oos_rank_icir", float("nan")); ls = m.get("oos_ls_sharpe", float("nan"))
        ok = (ri is not None and ri > 0) and (ls is not None and ls > 1.0)
        bar.append((f, ok, ri, ls)); print(f"{f:28s} {ri:14.4f} {ls:14.4f}  {'PASS' if ok else 'FAIL'}")

    git_state = ({"dirty_tree": False, "git_sha": pe.capture_git_state()["git_sha"] or "DRYRUN_HEAD"}
                 if args.mode == "dryrun" else None)
    try:
        artifact = pe.produce_promotion_evidence(reproduction=reproduction, definition_binding=binding,
                                                 git_state=git_state, promotion_status="approved")
        print("\npromotion_evidence: SELF-VERIFY PASSED")
    except pe.PromotionEvidenceError as e:
        print(f"\npromotion_evidence: SELF-VERIFY FAILED -> {e}"); return 1

    if args.mode == "dryrun":
        print(f"\n[dryrun] machinery validated; OOS preview above. NO writes. Run --mode live for the override spend.")
        return 0

    git_sha = artifact["git_sha"]; live = FactorRegistryStore(ROOT / "data" / "factor_registry")
    promoted, skipped = [], []
    for f, ok, ri, ls in bar:
        if not ok:
            skipped.append({"factor_id": f, "oos_rank_icir": ri, "oos_ls_sharpe": ls})
            print(f"[live] SKIP {f} (bar not cleared: rank_icir={ri:.4f}, ls_sharpe={ls:.4f}) -> stays candidate, OOS spent."); continue
        live.set_status(factor_id=f, status="approved",
            reason=(f"report_rc eps_diffusion sealed-OOS winner (CANARY-OVERRIDDEN). FrozenSelectionSet "
                    f"{fs.frozen_set_hash[:12]}, OOS {OOS_START}..{OOS_END}: rank_icir={ri:.4f}, LS Sharpe={ls:.4f} "
                    f">1.0 sign-stable. {CANARY_OVERRIDE_REASON}"),
            promotion_evidence=artifact, current_git_sha=git_sha, source_run_id=f"eps_diff_oos_{fs.frozen_set_hash[:12]}")
        live.set_expected_direction(factor_id=f, expected_direction="positive")
        promoted.append({"factor_id": f, "oos_rank_icir": ri, "oos_ls_sharpe": ls}); print(f"[live] APPROVED {f}")
    live.save()
    PROV_PATH.write_text(json.dumps({"promoted_at_oos_end": OOS_END, "factors": FACTOR_IDS,
        "frozen_set_hash": fs.frozen_set_hash, "git_sha": git_sha, "provider_build_id": ir["provider_build_id"],
        "calendar_policy_id": ir["calendar_policy_id"], "evidence_class": "single_shot_sealed_oos_CANARY_OVERRIDDEN",
        "canary_overridden": True, "canary_override_reason": CANARY_OVERRIDE_REASON,
        "outstanding_canary": "report_rc_breadth_restatement_canary (2026-06-15) — NOT passed at approval time",
        "promoted": promoted, "skipped": skipped, "promotion_evidence": artifact}, indent=2), encoding="utf-8")
    print(f"\n[live] provenance -> {PROV_PATH}\n[live] DONE: {len(promoted)} approved {[p['factor_id'] for p in promoted]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
