# ──────────────────────────────────────────────────────────────────────
# Single-shot sealed-OOS validation for EWaveSelectedSet_v2 (the 6-core).
# script_status: formal_candidate
# formal_research_allowed: true
# deployment_target: factor_registry_validation
# requires_provider_manifest: true
# pr2_audit_class: A
# notes: |
#   The 6 family-aware marginal representatives (IS-only selection on 2010-2020,
#   EWaveSelectedSet_v2) -> ONE FrozenSelectionSet -> ONE sealed OOS (2021-01-01..
#   2026-02-27), the mandate's "select -> one sealed OOS -> deployment gate". NOT
#   69 individual OOS. Selection class: a_priori IS-only (the 2021+ window is
#   UNBURNED by our own statistics). Direction-aware bar (5 inverse + 1 positive).
#
#   --mode show   (default): build the FrozenSelectionSet, print the frozen_set_hash
#       + the full pre-registered recipe + definition binding. NO OOS touched, NO seal.
#   --mode dryrun: TEMP seal + compute the OOS metrics (REVEALS the OOS numbers; only
#       run once the recipe is final — seeing the preview IS observing the OOS).
#   --mode live:   REAL one-shot seal claim (the irreversible spend) + record the
#       per-factor OOS verdict to provenance. Promotion to 'approved' is a SEPARATE
#       downstream decision (reuses the saved reproduction; no re-spend). Pre-flights
#       BEFORE the seal claim: clean committed tree + unsafe_pit_dates lint == passed.
# ──────────────────────────────────────────────────────────────────────
"""Validate EWaveSelectedSet_v2 (6-core) via a single-shot sealed OOS."""
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

# EWaveSelectedSet_v2 6-core: (factor_id, IS expected_direction). 5 inverse + 1 positive.
SIX_CORE = [
    ("corr_ret_turnd_20d", "inverse"),
    ("liq_vstd_20d", "inverse"),
    ("vol_w_downshadow_std_60d", "inverse"),
    ("corr_price_turn_post_20d", "inverse"),
    ("flow_act_buy_shift_dist_xl_20d", "inverse"),
    ("liq_shortcut_avg_20d", "positive"),
]
DIR_MAP = {"inverse": "short", "positive": "long"}  # FrozenSelectionSet side convention

QLIB_DIR = ROOT / "data" / "qlib_data"
SEAL_ROOT = ROOT / "data" / "holdout_seals"
PROV_PATH = ROOT / "workspace" / "research" / "cicc_replication" / "e_wave_v2_sealed_oos.json"
COHORT = "cicc_price_volume_handbook_v1"
OOS_START, OOS_END = "2021-01-01", "2026-02-27"
IS_WINDOW = "2010-01-01..2020-12-31"
HORIZON, N_QUANTILES = 20, 10  # decile (post-2026-06-11 unified 10-group standard)

SELECTION_RULE = (
    "EWaveSelectedSet_v2 (2026-06-20): family-aware marginal-contribution selection over the 68 "
    "CICC price-volume E-wave candidates (cohort cicc_price_volume_handbook_v1), IS-only 2010-2020 "
    "univ_all. quality=|heldout_rank_icir|; redundancy=month-end Spearman exposure correlation to "
    "the already-selected set + the pre-existing rev_up_down_ratio_20d reference; greedy "
    "marginal=|icir|*(1-maxcorr), family caps (corr/flow/liq<=2, vol<=1, mmt<=1), 6-core = the "
    "picks above the natural marginal break (>=0.27). style_resid_ic annotation-only, NOT a gate. "
    "Selected on IS-only statistics; 2021+ UNBURNED."
)


# The direction-aware bar is the extracted library function (factor_eval_skill.sealed_oos);
# locked by tests/alpha_research/test_factor_eval_skill_d3.py::test_sealed_oos_bar_reproduces_ewave_6of6_regression.
from src.alpha_research.factor_eval_skill.sealed_oos import direction_aligned_pass as _dir_aligned_pass  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["show", "dryrun", "live"], default="show")
    args = ap.parse_args()

    from src.alpha_research.factor_library.catalog import get_factor_catalog
    from src.alpha_research.factor_registry.store import FactorRegistryStore
    from src.research_orchestrator import promotion_evidence as pe
    from src.research_orchestrator.frozen_selection_set import FrozenSelectionSet, SelectedFactor

    cat = get_factor_catalog(include_new_data=True)
    store = FactorRegistryStore(ROOT / "data" / "factor_registry")
    cat_hashes = store.current_catalog_definition_hashes()
    master = store.factor_master[store.factor_master["is_current"].fillna(False)]

    fids = [f for f, _ in SIX_CORE]
    exprs = {f: cat[f] for f in fids if f in cat}
    missing_expr = [f for f in fids if f not in exprs]
    if missing_expr:
        print("ABORT: missing catalog expression for", missing_expr); return 2
    hashes = {f: cat_hashes.get(f, "") for f in fids}
    if not all(hashes.values()):
        print("ABORT: missing catalog definition hash for", [f for f in fids if not hashes[f]]); return 2

    def _ver(f):
        r = master[master["factor_id"] == f]
        return int(r.iloc[0]["version"]) if len(r) else 1

    selected = tuple(
        SelectedFactor(factor_id=f, version=_ver(f), definition_hash=hashes[f],
                       expected_direction=DIR_MAP[d])
        for f, d in SIX_CORE
    )

    # candidate pool = the 68 cohort candidates the selection saw (for candidate_pool_hash)
    pool = sorted(master[(master["status"] == "candidate") &
                         (master["replication_cohort_id"] == COHORT)]["factor_id"])
    ph = lambda obj: hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()
    eval_protocol = {"screen_horizons": [5, 10, 20], "oos_horizon": HORIZON, "n_quantiles": N_QUANTILES,
                     "is_window": IS_WINDOW, "oos_window": f"{OOS_START}..{OOS_END}",
                     "metric": "rank_icir_sign_aligned_ls_sharpe", "label": "forward_return",
                     "stage_is": "is_only", "stage_oos": "oos_test"}
    fs = FrozenSelectionSet(
        selected=selected,
        candidate_pool_hash=ph(pool),
        selection_rule_hash=hashlib.sha256(SELECTION_RULE.encode()).hexdigest(),
        eval_protocol_hash=ph(eval_protocol),
        metric="rank_icir", portfolio_side="long_short",
        universe="ashare_full_provider(univ_all_basis)",
        time_split_window=f"{OOS_START}..{OOS_END}", rebalance="20d", neutralization="none")

    binding = pe.assert_definition_binding(hashes, hashes)
    print("=" * 78)
    print("EWaveSelectedSet_v2 — 6-core FrozenSelectionSet")
    print("=" * 78)
    print(f"frozen_set_hash : {fs.frozen_set_hash}")
    print(f"pool_size       : {len(pool)} cohort candidates")
    print(f"definition_bind : bound={binding['bound']} (mismatched={binding['mismatched']})")
    print(f"OOS window      : {OOS_START}..{OOS_END}   horizon={HORIZON}d  n_quantiles={N_QUANTILES} (decile)")
    print(f"metric          : rank_icir@{HORIZON}d (sign-aligned) + ls_sharpe@5d (direction-aligned) > 1.0")
    print(f"portfolio_side  : long_short   neutralization: none   universe: full provider (univ_all basis)")
    print("the 6 (held side):")
    for f, d in SIX_CORE:
        print(f"   {f:34} IS_dir={d:8} -> held {DIR_MAP[d]:5} (v{_ver(f)}, def {hashes[f][:10]})")
    print("=" * 78)

    if args.mode == "show":
        print("MODE=show: recipe + hash only. NO OOS touched, NO seal. "
              "Sign off on this recipe before --mode dryrun/live (running either OBSERVES the OOS).")
        return 0

    if args.mode == "live":
        gs = pe.capture_git_state()
        if gs["dirty_tree"] or not gs["git_sha"]:
            print("[live] ABORT: working tree not clean — commit/stash first (gate needs dirty_tree=False)."); return 2
        lint = pe.run_unsafe_pit_dates_lint()
        if lint != "passed":
            print(f"[live] ABORT: unsafe_pit_dates lint = {lint!r} (must pass BEFORE the seal claim)."); return 2
        seal_root = SEAL_ROOT
        run_dir = str(ROOT / "workspace" / "outputs" / "e_wave_v2_sealed_oos_live")
        Path(run_dir).mkdir(parents=True, exist_ok=True)
        print(f"[live] clean tree at {gs['git_sha'][:12]}, lint passed; claiming the OOS seal (ONE-SHOT SPEND).")
    else:
        tmp = tempfile.mkdtemp(prefix="e_wave_v2_oos_dry_", dir=str(ROOT / "workspace" / "outputs"))
        seal_root = Path(tmp) / "seals"; seal_root.mkdir(parents=True, exist_ok=True); run_dir = tmp
        print("[dryrun] temp seal_root (no real spend) — but the OOS numbers below ARE the real OOS.")

    reproduction = pe.reproduce_sealed_oos(
        frozen_set=fs, factor_exprs=exprs, oos_start=OOS_START, oos_end=OOS_END,
        qlib_dir=str(QLIB_DIR), seal_root=str(seal_root), run_dir=run_dir,
        design_hash=fs.frozen_set_hash, hypothesis_id="e_wave_v2_sealed_oos",
        horizon=HORIZON, n_quantiles=N_QUANTILES, claim_seal=True)
    ir = reproduction["independent_reproduction"]
    print(f"\nreproduction source={ir['source']} provider_build={ir['provider_build_id']} "
          f"calendar={ir['calendar_policy_id']} oos={ir['oos_window']}")
    print(f"\n{'factor':34} {'side':5} {'oos_rank_icir':>13} {'oos_ls_sharpe':>13} {'aligned_ls':>11}  bar")
    results = []
    for f, d in SIX_CORE:
        side = DIR_MAP[d]
        m = ir["per_factor"].get(f, {})
        ri = m.get("oos_rank_icir", float("nan")); ls = m.get("oos_ls_sharpe", float("nan"))
        ok, da_ri, da_ls = _dir_aligned_pass(side, ri, ls)
        results.append({"factor": f, "side": side, "oos_rank_icir": ri, "oos_ls_sharpe": ls,
                        "aligned_rank_icir": da_ri, "aligned_ls_sharpe": da_ls, "pass": ok})
        print(f"{f:34} {side:5} {ri:13.4f} {ls:13.4f} {da_ls:11.4f}  {'PASS' if ok else 'fail'}")
    n_pass = sum(1 for r in results if r["pass"])
    print(f"\n-> {n_pass}/6 clear the bar (sign-aligned rank_icir>0 AND aligned ls_sharpe>1.0)")

    if args.mode == "live":
        PROV_PATH.write_text(json.dumps({
            "set_id": "EWaveSelectedSet_v2", "frozen_set_hash": fs.frozen_set_hash,
            "evidence_class": "single_shot_sealed_oos", "selection_class": "a_priori_is_only",
            "oos_window": f"{OOS_START}..{OOS_END}", "horizon": HORIZON, "n_quantiles": N_QUANTILES,
            "provider_build_id": ir["provider_build_id"], "calendar_policy_id": ir["calendar_policy_id"],
            "git_sha": pe.capture_git_state()["git_sha"], "bar": "sign_aligned_rank_icir>0 AND aligned_ls_sharpe>1.0",
            "results": results, "n_pass": n_pass,
            "promotion": "DEFERRED — separate downstream decision; reuse this reproduction (seal already spent).",
            "reproduction": ir,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[live] OOS spent + recorded -> {PROV_PATH}")
        print("[live] promotion to 'approved' is a SEPARATE decision (not auto-applied).")
    else:
        print("\n[dryrun] machinery validated; the OOS numbers above are real. "
              "Recipe is now observed — proceed to --mode live for the formal one-shot spend (SAME recipe).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
