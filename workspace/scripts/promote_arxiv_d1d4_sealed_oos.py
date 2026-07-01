# ──────────────────────────────────────────────────────────────────────
# Sealed-OOS promotion driver for the arXiv D1-D4 idea-sourced candidates
# (alpha_chip_cgo_smooth_20d, earn_sue_ni_mcap, earn_sue_ni_assets,
#  north_hold_change_20d_cov, north_hold_change_60d_cov).
# FrozenSelectionSet of the FIVE, single fresh seal.
# script_status: formal_candidate
# formal_research_allowed: true
# deployment_target: factor_registry_promotion
# requires_provider_manifest: true
# pr2_audit_class: A
# notes: |
#   Selection class: a_priori IS-only (sandbox screens + marginal gate + IS
#   factor_lifecycle, ALL <= 2020-12-31) -> the 2021-2026 OOS is UNBURNED by
#   our own statistics. Residual caveat (stamped into provenance): the source
#   papers are literature-informed (e.g. arXiv:2505.20608 sampled A-shares
#   1995-2024). No canary dependency: none of the 5 reads report_rc.
#
#   --mode dryrun (default): TEMP seal, injected-clean git, NO writes —
#     validates the machinery + previews OOS metrics.
#   --mode live: REAL seal claim (the one-shot spend) + set_status('approved')
#     for factors clearing oos_rank_icir>0 AND oos_ls_sharpe>1.0 (the same bar
#     as the GP / eps_diffusion precedents). Pre-flights BEFORE the seal claim:
#     clean committed tree + unsafe_pit_dates lint == passed.
# ──────────────────────────────────────────────────────────────────────
"""Promote the 5 arXiv D1-D4 candidates via single-shot sealed OOS."""
from __future__ import annotations

import argparse, hashlib, json, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

FACTOR_IDS = [
    "alpha_chip_cgo_smooth_20d",
    "earn_sue_ni_mcap",
    "earn_sue_ni_assets",
    "north_hold_change_20d_cov",
    "north_hold_change_60d_cov",
]
QLIB_DIR = ROOT / "data" / "qlib_data"
SEAL_ROOT = ROOT / "data" / "holdout_seals"
PROV_PATH = ROOT / "workspace" / "research" / "idea_sourcing" / "arxiv_d1d4_sealed_oos_promotion.json"
OOS_START, OOS_END = "2021-01-01", "2026-02-27"
IS_WINDOW = "2014-01-01..2020-12-31"
HORIZON, N_QUANTILES = 20, 5

# The full screened candidate pool (19 factors incl. masked variants) — the
# selection these 5 were drawn from. See knowledge/D1_D4_SCREEN_RESULTS.md.
CANDIDATE_POOL = [
    "behav_cgo", "behav_cgo_smooth_20", "behav_winner_rate", "behav_cost_disp",
    "flow_lg_net_5", "flow_lg_net_20", "flow_sm_net_5", "flow_sm_net_20",
    "sue_ni_mcap", "sue_ni_assets", "sue_rev_mcap", "ni_yoy_growth",
    "north_level", "north_chg_20", "north_chg_60", "north_accel_20",
    "north_level_cov", "north_chg_20_cov", "north_chg_60_cov",
]
SELECTION_RULE = (
    "arXiv knowledge-framework D1-D4 exploration (2026-06-10): 671-paper themed corpus -> 4 "
    "Tier-1 frontier directions -> 19-factor sandbox screen (raw + size-neut RankIC/ICIR, IS "
    "<= 2020-12-31) -> marginal-contribution gate vs the 31-factor book (overlap-window "
    "increment) -> winner + borderline added as catalog drafts -> ALL 5 passed the IS-only "
    "factor_lifecycle gate (heldout RankICIR 0.34-0.60, sign-consistency 0.86-1.00). Selected "
    "on IS-only statistics; literature-informed caveat (source papers sampled through 2024)."
)


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
    ph = lambda obj: hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()
    eval_protocol = {"screen_horizons": [5, 10, 20], "oos_horizon": HORIZON, "n_quantiles": N_QUANTILES,
                     "is_window": IS_WINDOW, "oos_window": f"{OOS_START}..{OOS_END}",
                     "metric": "rank_icir_sign_aligned_ls_sharpe", "label": "forward_return",
                     "stage_is": "is_only", "stage_oos": "oos_test"}
    fs = FrozenSelectionSet(selected=selected,
        candidate_pool_hash=ph(CANDIDATE_POOL),
        selection_rule_hash=hashlib.sha256(SELECTION_RULE.encode()).hexdigest(),
        eval_protocol_hash=ph(eval_protocol),
        metric="rank_icir", portfolio_side="long_short",
        universe="ashare_all_mixed_coverage(cyq2018plus,connect_held,statements)",
        time_split_window=f"{OOS_START}..{OOS_END}", rebalance="20d", neutralization="size")
    print(f"FrozenSelectionSet({{{','.join(FACTOR_IDS)}}})  frozen_set_hash={fs.frozen_set_hash}")
    binding = pe.assert_definition_binding(hashes, hashes)
    print(f"definition_binding: bound={binding['bound']}")

    if args.mode == "live":
        seal_root = SEAL_ROOT
        run_dir = str(ROOT / "workspace" / "outputs" / "arxiv_d1d4_sealed_oos_live")
        Path(run_dir).mkdir(parents=True, exist_ok=True)
        gs = pe.capture_git_state()
        if gs["dirty_tree"] or not gs["git_sha"]:
            print("[live] ABORT: working tree not clean — commit/stash first (gate needs dirty_tree=False)."); return 2
        lint = pe.run_unsafe_pit_dates_lint()
        if lint != "passed":
            print(f"[live] ABORT: unsafe_pit_dates lint = {lint!r} (must be 'passed' BEFORE the seal claim "
                  "so a failing gate can't waste the one-shot OOS)."); return 2
        print(f"[live] clean tree at {gs['git_sha'][:12]}, lint passed; claiming the OOS seal (one-shot spend).")
    else:
        tmp = tempfile.mkdtemp(prefix="arxiv_d1d4_dry_", dir=str(ROOT / "workspace" / "outputs"))
        seal_root = Path(tmp) / "seals"; seal_root.mkdir(parents=True, exist_ok=True); run_dir = tmp
        print("[dryrun] temp seal_root (no real spend, no writes)")

    reproduction = pe.reproduce_sealed_oos(frozen_set=fs, factor_exprs=exprs, oos_start=OOS_START,
        oos_end=OOS_END, qlib_dir=str(QLIB_DIR), seal_root=str(seal_root), run_dir=str(run_dir),
        design_hash=fs.frozen_set_hash, hypothesis_id="arxiv_d1d4_sealed_oos",
        horizon=HORIZON, n_quantiles=N_QUANTILES, claim_seal=True)
    ir = reproduction["independent_reproduction"]
    print(f"\nreproduction source={ir['source']} provider_build={ir['provider_build_id']} "
          f"calendar={ir['calendar_policy_id']} oos={ir['oos_window']} max_label={ir['max_label_realization_date']}")
    print(f"\n{'factor':28s} {'oos_rank_icir':>14s} {'oos_ls_sharpe':>14s}  bar(LS>1.0,sign+)")
    bar = []
    for f in FACTOR_IDS:
        m = ir["per_factor"].get(f, {})
        ri = m.get("oos_rank_icir", float("nan")); ls = m.get("oos_ls_sharpe", float("nan"))
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
        print("\n[dryrun] machinery validated; OOS preview above. NO writes. Run --mode live for the one-shot spend.")
        return 0

    git_sha = artifact["git_sha"]; live = FactorRegistryStore(ROOT / "data" / "factor_registry")
    promoted, skipped = [], []
    for f, ok, ri, ls in bar:
        if not ok:
            skipped.append({"factor_id": f, "oos_rank_icir": ri, "oos_ls_sharpe": ls})
            print(f"[live] SKIP {f} (bar not cleared: rank_icir={ri:.4f}, ls_sharpe={ls:.4f}) -> stays candidate, OOS spent."); continue
        live.set_status(factor_id=f, status="approved",
            reason=(f"arXiv D1-D4 sealed-OOS winner. FrozenSelectionSet {fs.frozen_set_hash[:12]}, "
                    f"OOS {OOS_START}..{OOS_END}: rank_icir={ri:.4f}, LS Sharpe={ls:.4f} >1.0 sign-stable. "
                    f"a_priori IS-only selection (2021-2026 unburned by own stats; literature-informed "
                    f"caveat recorded in arxiv_d1d4_selection_provenance.json)."),
            promotion_evidence=artifact, current_git_sha=git_sha,
            source_run_id=f"arxiv_d1d4_oos_{fs.frozen_set_hash[:12]}")
        live.set_expected_direction(factor_id=f, expected_direction="positive")
        promoted.append({"factor_id": f, "oos_rank_icir": ri, "oos_ls_sharpe": ls}); print(f"[live] APPROVED {f}")
    live.save()
    PROV_PATH.write_text(json.dumps({"promoted_at_oos_end": OOS_END, "factors": FACTOR_IDS,
        "frozen_set_hash": fs.frozen_set_hash, "git_sha": git_sha, "provider_build_id": ir["provider_build_id"],
        "calendar_policy_id": ir["calendar_policy_id"], "evidence_class": "single_shot_sealed_oos",
        "selection_class": "a_priori_is_only", "literature_informed_caveat": True,
        "promoted": promoted, "skipped": skipped, "promotion_evidence": artifact}, indent=2), encoding="utf-8")
    print(f"\n[live] provenance -> {PROV_PATH}\n[live] DONE: {len(promoted)} approved {[p['factor_id'] for p in promoted]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
