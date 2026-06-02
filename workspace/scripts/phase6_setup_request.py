"""Phase 6 helper: set up a temp registry copy + write a factor_lifecycle request JSON.

Usage:
  phase6_setup_request.py --mode temp  --factors rev_max_return_20d,risk_vol_20d,liq_turnover_20d
  phase6_setup_request.py --mode live  --factors-file <json list>

`--mode temp` copies ALL registry dirs to a temp root (live untouched) and points the
request there. `--mode live` points at data/ (the real registries). It NEVER writes the
registry itself — only the request JSON + (temp) a registry copy. Read-only w.r.t. live.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATA = PROJECT_ROOT / "data"
OUT = PROJECT_ROOT / "workspace" / "outputs"
REGISTRY_SUBDIRS = [
    "factor_registry", "candidate_registry", "signal_registry", "model_registry",
    "strategy_registry", "hypothesis_registry", "testing_ledger", "holdout_seals",
]
TIME_SPLIT = {"is_start": "2014-01-01", "is_end": "2020-12-31",
              "oos_start": "2021-01-01", "oos_end": "2022-01-01"}


def _hypothesis(factor_ids: list[str]) -> dict:
    return {
        "hypothesis_id": "factor_lifecycle_phase6",
        "thesis_statement": (
            "The named A-share base catalog factors carry IS-only (2014-2020) predictive "
            "power sufficient for a draft->candidate promotion via the IS-only walk-forward gate."
        ),
        "mechanism": (
            "Each factor's cross-sectional rank IC over the IS window is sign-consistent "
            "across calendar years (a-priori factors; the IS-only gate is structurally "
            "blind to OOS and does NOT attest deployability)."
        ),
        "source": {"source_type": "internal_research", "identifier": "factor_lifecycle_phase6",
                   "title": "Factor-lifecycle Phase 6 catalog gate", "authors": ["Claude"],
                   "url": "", "publication_date": "2026-06-01", "publisher": "internal"},
        "factor_refs": [{"object_type": "factor", "object_name": f} for f in factor_ids],
        "factor_yaml_hashes": [],
        "universe": "csi_all",
        "benchmark": "000905.SH",
        "time_split": {**TIME_SPLIT, "walk_forward_config": {
            "train_years": 3, "validation_years": 1, "test_years": 1, "step_years": 1}},
        "rebalance_frequency": "20d",
        "neutralization": [],
        "expected_sign": 1,
        "expected_effect": {"statistic": "rank_icir", "point_estimate": 0.20,
                            "ci_low": 0.10, "ci_high": 0.75, "horizon_days": 20},
        "expected_decay_horizon_days": 20,
        # IS-only gate: ONLY min_rank_icir is meaningful. Leaving the sharpe/drawdown/
        # turnover/monotonicity fields None means evaluate_success_criteria generates NO
        # rule for them (gate_report.py:123), so the automated verdict reflects the actual
        # IS-only gate (accepted on rank_icir) instead of being "quarantined" by null rules.
        "success_criteria": {
            "min_rank_icir": 0.10,
            "effect_size_must_be_in_ci": False, "custom_rules": [],
        },
        "pre_registered_concerns": {
            "most_likely_failure_mode": (
                "An IS-stable factor collapses out-of-sample (the IS-only gate cannot see "
                "this); rank_icir is the keyed metric."),
            "weakest_assumption": (
                "IS sign-consistency over 2014-2020 generalizes; falsified by the SEPARATE "
                "OOS/promotion gate (not run here)."),
            "what_would_falsify_this": (
                "rank_icir below the IS heldout floor (0.10) for a given factor -> stays draft."),
            "priors_on_cost_sensitivity": (
                "No cost model in an IS-only cross-sectional IC gate; cost-adjusted viability "
                "is a later-phase recompute."),
        },
        "pre_registered_at": "2026-06-01", "registered_by": "claude_phase6",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["temp", "live"], required=True)
    ap.add_argument("--factors", default="")
    ap.add_argument("--factors-file", default="")
    ap.add_argument("--tag", default="smoke")
    args = ap.parse_args()

    if args.factors_file:
        factors = list(json.loads(Path(args.factors_file).read_text(encoding="utf-8")))
    else:
        factors = [f.strip() for f in args.factors.split(",") if f.strip()]
    if not factors:
        raise SystemExit("no factors given (--factors a,b,c or --factors-file path)")

    if args.mode == "temp":
        registry_root = OUT / "phase6_temp_registry"
        if registry_root.exists():
            shutil.rmtree(registry_root)
        registry_root.mkdir(parents=True)
        for sub in REGISTRY_SUBDIRS:
            src = DATA / sub
            if src.exists():
                shutil.copytree(src, registry_root / sub)
            else:
                (registry_root / sub).mkdir(parents=True, exist_ok=True)
        print(f"[temp] copied {len(REGISTRY_SUBDIRS)} registry dirs -> {registry_root}")
    else:
        registry_root = DATA

    run_dir = OUT / f"phase6_factor_lifecycle_{args.mode}_{args.tag}"
    request = {
        "profile_id": "factor_lifecycle",
        "mode": "formal",
        "consumes": [{"object_type": "factor", "object_name": f} for f in factors],
        "produces": [],
        "requested_capabilities": [],
        "inputs": {
            "output_dir": str(run_dir),
            "time_split": TIME_SPLIT,
            "horizon": 20,
            "factor_origin": "a_priori",
            "qlib_dir": str(DATA / "qlib_data"),
        },
        "run_context": {"registry_root": str(registry_root), "resume_policy": "resume"},
        "hypothesis": _hypothesis(factors),
    }
    req_path = OUT / f"phase6_request_{args.mode}_{args.tag}.json"
    req_path.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"factors={len(factors)}  run_dir={run_dir}")
    print(f"wrote request -> {req_path}")
    print(f"registry_root={registry_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
