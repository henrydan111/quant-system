# ──────────────────────────────────────────────────────────────────────
# C2 onboarding driver for the 6 Round-6 sealed-OOS winners.
# script_status: formal_candidate
# formal_research_allowed: true
# deployment_target: factor_registry_promotion
# execution_profile: n/a (factor-level promotion, not a strategy backtest)
# requires_provider_manifest: true
# requires_preload_strict: false
# pr2_audit_class: A
# notes: |
#   Builds the FrozenSelectionSet over the 13-factor frozen top set, runs the
#   promotion-evidence harness (reproduce_sealed_oos + definition-binding +
#   canaries + lint + parity + self-verify), and — in --mode live only — promotes
#   the winners that clear the leak-free bar to factor-registry status `approved`.
#
#   --mode dryrun (default): TEMP seal_root, injected-clean git_state, NO registry
#     writes. Validates that the 6 reproduce + pass the leak-free bar and that the
#     promotion_evidence artifact self-verifies through the gate.
#   --mode live: REAL HoldoutSeal claim (the one sanctioned OOS spend, keyed by the
#     frozen-13 hash), REAL git_state (clean committed tree required), and
#     set_status('approved', ...) for each winner that clears the bar. Behind
#     explicit user approval per CLAUDE.md §13.
# ──────────────────────────────────────────────────────────────────────
"""Onboard the 6 sealed-OOS winners (C2). See module header for modes."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

FE = ROOT / "workspace" / "research" / "factor_expansion"
FROZEN_TOPSET_JSON = FE / "oos_frozen_topset.json"
SELECTION_RULE_MD = FE / "oos_topset_selection_rule.md"
CANDIDATES_CSV = FE / "factor_candidates_merged.csv"
QLIB_DIR = ROOT / "data" / "qlib_data"
SEAL_ROOT = ROOT / "data" / "holdout_seals"

OOS_START = "2021-01-01"
OOS_END = "2026-02-27"
IS_WINDOW = "2014-01-01..2020-12-31"
HORIZON = 20
N_QUANTILES = 5

# The 6 winners (REGISTER per oos_results_and_registration.md) + their documented
# sealed-OOS IS/OOS signs (all IS RankICIR positive -> held LONG).
WINNERS = [
    "liq_zero_ret_days_10d",
    "rev_turnover_spike_5d",
    "grow_total_revenue_yoy_accel_q",
    "grow_n_income_attr_p_yoy_accel_q",
    "grow_operate_profit_yoy_accel_q",
    "qual_piotroski_fscore_9pt",
]


def _base_def_hash(factor_id: str, expression: str) -> str:
    """Mirror FactorRegistryStore._build_catalog_snapshots base-factor hash."""
    return hashlib.sha256(f"base|{factor_id}|{expression}".encode("utf-8")).hexdigest()


def _load_csv_exprs() -> dict[str, str]:
    df = pd.read_csv(CANDIDATES_CSV)
    return dict(zip(df["name"], df["qlib_expression"]))


def _formal_eligible_pool(df_path: Path = CANDIDATES_CSV) -> list[str]:
    df = pd.read_csv(df_path)
    pool = df.loc[df["formal_eligible"].astype(str).str.lower() == "yes", "name"]
    return sorted(pool.tolist())


def build_frozen_selection_set():
    """FrozenSelectionSet over the 13-factor frozen top set. expected_direction is
    the PRE-OOS (IS-frozen) direction — all 13 had positive IS RankICIR -> 'long'.
    Pool/rule/protocol hashes are derived from the committed pre-OOS artifacts."""
    from src.research_orchestrator.frozen_selection_set import (
        FrozenSelectionSet,
        SelectedFactor,
    )

    frozen = json.loads(FROZEN_TOPSET_JSON.read_text(encoding="utf-8"))
    topset = frozen["frozen_topset"]
    assert len(topset) == 13, f"expected 13 frozen factors, got {len(topset)}"
    exprs = _load_csv_exprs()

    selected = tuple(
        SelectedFactor(
            factor_id=name,
            version=1,
            definition_hash=_base_def_hash(name, exprs[name]),
            expected_direction="long",  # IS-frozen: all 13 had positive IS RankICIR
        )
        for name in topset
    )
    pool = _formal_eligible_pool()
    candidate_pool_hash = hashlib.sha256(
        json.dumps(pool, sort_keys=True).encode("utf-8")
    ).hexdigest()
    selection_rule_hash = hashlib.sha256(
        SELECTION_RULE_MD.read_bytes()
    ).hexdigest()
    eval_protocol = {
        "screen_horizons": [5, 10, 20],
        "oos_horizon": HORIZON,
        "n_quantiles": N_QUANTILES,
        "is_window": IS_WINDOW,
        "oos_window": f"{OOS_START}..{OOS_END}",
        "metric": "rank_icir_sign_aligned_ls_sharpe",
        "label": "forward_return",
        "stage_is": "is_only",
        "stage_oos": "oos_test",
    }
    eval_protocol_hash = hashlib.sha256(
        json.dumps(eval_protocol, sort_keys=True).encode("utf-8")
    ).hexdigest()

    return FrozenSelectionSet(
        selected=selected,
        candidate_pool_hash=candidate_pool_hash,
        selection_rule_hash=selection_rule_hash,
        eval_protocol_hash=eval_protocol_hash,
        metric="rank_icir",
        portfolio_side="long_short",
        universe="formal_eligible_ashare_screen50",
        time_split_window=f"{OOS_START}..{OOS_END}",
        rebalance="20d",
        neutralization="none",
    )


def winner_frozen_hashes() -> dict[str, str]:
    """Independent definition hashes for the 6 winners, computed from the FROZEN
    artifact (factor_candidates_merged.csv) — the definition the OOS validated."""
    exprs = _load_csv_exprs()
    return {name: _base_def_hash(name, exprs[name]) for name in WINNERS}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dryrun", "live"], default="dryrun")
    args = ap.parse_args()

    from src.alpha_research.factor_registry.store import FactorRegistryStore
    from src.research_orchestrator import promotion_evidence as pe

    fs = build_frozen_selection_set()
    print(f"FrozenSelectionSet: 13 factors, frozen_set_hash={fs.frozen_set_hash}")

    # ── definition binding (guard #6): catalog hashes == frozen-artifact hashes ──
    store = FactorRegistryStore(ROOT / "data" / "factor_registry")
    catalog_hashes_all = store.current_catalog_definition_hashes()
    catalog_hashes = {n: catalog_hashes_all.get(n, "") for n in WINNERS}
    frozen_hashes = winner_frozen_hashes()
    binding = pe.assert_definition_binding(catalog_hashes, frozen_hashes)
    print(f"definition_binding: bound={binding['bound']} mismatched={binding['mismatched']}")

    # ── reproduce sealed OOS (leak-free Phase-4 belt) ──
    winner_exprs = {n: _load_csv_exprs()[n] for n in WINNERS}
    if args.mode == "dryrun":
        tmp = tempfile.mkdtemp(prefix="sealed_oos_dryrun_", dir=str(ROOT / "workspace" / "outputs"))
        seal_root = Path(tmp) / "seals"
        seal_root.mkdir(parents=True, exist_ok=True)
        run_dir = tmp
        print(f"[dryrun] temp seal_root={seal_root}")
    else:
        seal_root = SEAL_ROOT
        run_dir = str(ROOT / "workspace" / "outputs" / "sealed_oos_winners_live")
        Path(run_dir).mkdir(parents=True, exist_ok=True)
        # Fail fast on a dirty tree BEFORE claiming the (one-shot) OOS seal: the gate
        # requires dirty_tree=False, so a dirty tree would waste the seal claim on a
        # run that can never self-verify.
        gs = pe.capture_git_state()
        if gs["dirty_tree"] or not gs["git_sha"]:
            print("[live] ABORT: working tree is not clean (git status --porcelain non-empty) "
                  "or git_sha unavailable. A clean committed tree is required before claiming "
                  "the OOS seal. Commit / stash / gitignore the untracked or modified files first.")
            return 2
        print(f"[live] clean tree at {gs['git_sha']}; proceeding to claim the OOS seal.")

    reproduction = pe.reproduce_sealed_oos(
        frozen_set=fs,
        factor_exprs=winner_exprs,
        oos_start=OOS_START,
        oos_end=OOS_END,
        qlib_dir=str(QLIB_DIR),
        seal_root=str(seal_root),
        run_dir=str(run_dir),
        design_hash=fs.frozen_set_hash,
        hypothesis_id="sealed_oos_winners",
        horizon=HORIZON,
        n_quantiles=N_QUANTILES,
        claim_seal=True,
    )
    ir = reproduction["independent_reproduction"]
    print(f"\nreproduction source={ir['source']} provider_build={ir['provider_build_id']} "
          f"calendar_policy={ir['calendar_policy_id']}")
    print(f"oos_window={ir['oos_window']} horizon={ir['horizon']} "
          f"max_label_realization={ir['max_label_realization_date']}")
    print(f"\n{'factor':38s} {'oos_rank_icir':>14s} {'oos_ls_sharpe':>14s}  bar(LS>1.0,sign+)")
    bar_pass = []
    for name in WINNERS:
        m = ir["per_factor"].get(name, {})
        ricir = m.get("oos_rank_icir", float("nan"))
        ls = m.get("oos_ls_sharpe", float("nan"))
        ok = (ricir is not None and ricir > 0) and (ls is not None and ls > 1.0)
        bar_pass.append((name, ok, ricir, ls))
        print(f"{name:38s} {ricir:14.4f} {ls:14.4f}  {'PASS' if ok else 'FAIL'}")
    passed = [n for n, ok, *_ in bar_pass if ok]
    print(f"\nleak-free bar: {len(passed)}/6 pass -> {passed}")

    # ── assemble + self-verify the artifact ──
    git_state = (
        {"dirty_tree": False, "git_sha": pe.capture_git_state()["git_sha"] or "DRYRUN_HEAD"}
        if args.mode == "dryrun"
        else None  # live: capture real git state (clean tree required)
    )
    try:
        artifact = pe.produce_promotion_evidence(
            reproduction=reproduction,
            definition_binding=binding,
            git_state=git_state,
            promotion_status="approved",
        )
        print("\npromotion_evidence: SELF-VERIFY PASSED (gate-eligible)")
        print(json.dumps({k: artifact[k] for k in artifact if k != "independent_reproduction"},
                         indent=2))
    except pe.PromotionEvidenceError as e:
        print(f"\npromotion_evidence: SELF-VERIFY FAILED -> {e}")
        return 1

    if args.mode == "dryrun":
        print("\n[dryrun] NO registry writes. Live promotion is --mode live behind explicit approval.")
        return 0

    # ── LIVE promotion (3e): Step B sync->draft, then Step C2 approve the passers ──
    from src.alpha_research.factor_library import sync_catalog_to_registry

    git_sha = artifact["git_sha"]
    reg_dir = ROOT / "data" / "factor_registry"
    sync_res = sync_catalog_to_registry(registry_dir=str(reg_dir), record_run=True)
    print(f"\n[live] sync_catalog_to_registry: synced={sync_res.get('synced')} "
          f"new_drafts={len(sync_res.get('new_drafts', []))} parity_ok={sync_res.get('parity_ok')}")

    live_store = FactorRegistryStore(reg_dir)
    promoted, skipped = [], []
    for name, ok, ricir, ls in bar_pass:
        if not ok:
            skipped.append({"factor_id": name, "oos_rank_icir": ricir, "oos_ls_sharpe": ls})
            print(f"[live] SKIP {name} (leak-free bar not cleared: rank_icir={ricir:.4f}, ls_sharpe={ls:.4f})")
            continue
        live_store.set_status(
            factor_id=name, status="approved",
            reason=(f"Round-6 sealed-OOS winner. Leak-free reproduction (FrozenSelectionSet "
                    f"{fs.frozen_set_hash[:12]}, OOS {OOS_START}..{OOS_END}, Phase-4 capped "
                    f"label): rank_icir={ricir:.4f}, LS Sharpe={ls:.4f} (>1.0, sign-stable IS->OOS)."),
            promotion_evidence=artifact, current_git_sha=git_sha,
            source_run_id=f"sealed_oos_{fs.frozen_set_hash[:12]}",
        )
        live_store.set_expected_direction(factor_id=name, expected_direction="positive")
        promoted.append({"factor_id": name, "oos_rank_icir": ricir, "oos_ls_sharpe": ls})
        print(f"[live] APPROVED {name}")
    live_store.save()

    prov_path = FE / "sealed_oos_winners_promotion.json"
    prov_path.write_text(json.dumps({
        "promoted_at_oos_end": OOS_END,
        "frozen_set_hash": fs.frozen_set_hash,
        "git_sha": git_sha,
        "provider_build_id": ir["provider_build_id"],
        "calendar_policy_id": ir["calendar_policy_id"],
        "evidence_class": "single_shot_sealed_oos_leak_free_reproduction",
        "note": ("These 6 are NOT oos_informed_backfill: the 13-factor top set was frozen "
                 "PRE-OOS (oos_frozen_topset.json) and the OOS window was run once. This is the "
                 "leak-free Phase-4-belt reproduction of that already-spent window; its numbers "
                 "GOVERN approval. 2021-2026 remains spent for this frozen set."),
        "promoted": promoted,
        "skipped": skipped,
        "promotion_evidence": {k: artifact[k] for k in artifact if k != "independent_reproduction"},
    }, indent=2), encoding="utf-8")
    print(f"[live] provenance -> {prov_path}")

    try:
        from src.alpha_research.testing_ledger import TestingLedgerStore
        led = TestingLedgerStore(ROOT / "data" / "testing_ledger")
        led.record_event(
            hypothesis_id="sealed_oos_winners", design_hash=fs.frozen_set_hash, prose_hash="",
            structural_family="sealed_oos_winners", profile_id="promotion_evidence",
            run_id=f"sealed_oos_{fs.frozen_set_hash[:12]}", run_dir=str(run_dir),
            test_name="sealed_oos_winners_promotion", stage="registry_publish",
            statistic_name="n_promoted", statistic_value=float(len(promoted)),
        )
        print(f"[live] testing-ledger event recorded")
    except Exception as e:  # ledger is provenance, not a gate — warn, do not fail the promotion
        print(f"[live] WARN: testing-ledger event failed: {e}")

    print(f"\n[live] DONE: {len(promoted)} approved -> {[p['factor_id'] for p in promoted]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
