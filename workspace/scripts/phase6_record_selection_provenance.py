"""Phase 6 governance follow-up (GPT PR-#35 cross-review): record the FULL selection funnel.

The live testing-ledger `batch_effective_trials=72` is accurate for the CONSUMED run but
incomplete for the full selection process (147 base → 114 field-eligible → 85 IS-candidates
→ 72 OOS-stable promoted). This writes:
  1. a committed provenance artifact (workspace/research/factor_expansion/) labelling the 72
     an `oos_informed_backfill` with the full funnel + explicit caveats; and
  2. a live testing-ledger event recording the full selection surface for downstream
     multiple-testing accounting.

The 72 must NEVER be described later as a fresh OOS-free selection.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

OUT = PROJECT_ROOT / "workspace" / "outputs"
DATA = PROJECT_ROOT / "data"
ARTIFACT = PROJECT_ROOT / "workspace" / "research" / "factor_expansion" / "phase6_selection_provenance.json"
RUN_DIR = OUT / "phase6_factor_lifecycle_live_prod72"
LABEL = "oos_informed_backfill"


def main() -> int:
    dry = json.loads((OUT / "phase6_dry_run_result.json").read_text(encoding="utf-8"))
    promoted = json.loads((OUT / "phase6_oos_stable_72.json").read_text(encoding="utf-8"))
    csv = pd.read_csv(
        PROJECT_ROOT / "workspace" / "research" / "factor_expansion" / "catalog_revalidation"
        / "catalog_revalidation_status.csv"
    ).set_index("factor")

    candidates_85 = list(dry["candidates"])
    field_excluded_33 = list(dry["field_excluded_factors"])
    excluded_13 = sorted(set(candidates_85) - set(promoted))
    collapsers = [{
        "factor": f,
        "is_rank_icir": round(float(csv.loc[f, "is_rank_icir"]), 4),
        "oos_rank_icir": round(float(csv.loc[f, "oos_rank_icir"]), 4),
        "full_window_status": str(csv.loc[f, "status"]),
    } for f in excluded_13]

    provenance = {
        "label": LABEL,
        "run_dir": str(RUN_DIR),
        "run_id": RUN_DIR.name,
        "hypothesis_id": "factor_lifecycle_phase6",
        "branch": "factor-lifecycle-p6",
        "pr": 35,
        "is_window": {"is_start": "2014-01-01", "is_end": "2020-12-31"},
        "horizon": 20,
        "selection_funnel": {
            "base_catalog_factors": int(dry["base_factor_count"]),          # 147
            "field_eligible_tested": int(dry["field_eligible_tested"]),     # 114
            "field_ineligible_excluded": int(dry["field_excluded"]),        # 33
            "is_candidates": len(candidates_85),                            # 85
            "is_candidates_excluded_as_oos_collapsers": len(excluded_13),   # 13
            "promoted_to_candidate": len(promoted),                         # 72
        },
        "promoted_72": sorted(promoted),
        "oos_collapsers_excluded_13": collapsers,
        "field_ineligible_33": field_excluded_33,
        "caveats": [
            "These 72 are an OOS-INFORMED conservative backfill, NOT a fresh OOS-free selection "
            "of 72. The exclusion of the 13 OOS-collapsers used the PRE-EXISTING full-window "
            "(2014-2026) catalog_revalidation_status.csv.",
            "The IS-only validator was NOT contaminated: OOS data did not enter labels / folds / "
            "metrics / set_status; the 72 lifecycle evidence rows are IS-only (oos_rank_icir=NA).",
            "candidate != approved. candidate is an ADDITIVE tier; it can never auto-become "
            "approved (separate P1.1 OOS/promotion gate).",
            "The 2021-2026 window is ALREADY BURNED for these 72 (observed in the pre-Phase-2 "
            "catalog revalidation). A future candidate->approved promotion for these factors MUST "
            "use a genuinely-sealed window, NOT 2021-2026.",
            "The live testing_ledger batch_effective_trials=72 reflects only the CONSUMED run; "
            "this artifact + the phase6_selection_funnel ledger event record the FULL selection "
            "surface (147 base -> 114 tested -> 85 IS-candidates -> 72 promoted) for downstream "
            "multiple-testing accounting.",
        ],
        "gpt_cross_review": "PR #35 = GO; this artifact + ledger event resolve the one governance follow-up.",
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote provenance artifact -> {ARTIFACT}")
    print("funnel:", json.dumps(provenance["selection_funnel"]))

    # ---- live testing-ledger event recording the FULL selection surface ----
    from src.alpha_research.testing_ledger import TestingLedgerStore
    from src.research_orchestrator import ResearchRequest

    req = json.loads((OUT / "phase6_request_live_prod72.json").read_text(encoding="utf-8-sig"))
    try:
        design_hash = ResearchRequest.from_dict(req).hypothesis.design_hash()
    except Exception as exc:  # design_hash is best-effort association
        design_hash = ""
        print("WARN: could not reconstruct design_hash:", exc)

    ledger = TestingLedgerStore(DATA / "testing_ledger")
    fn = provenance["selection_funnel"]
    note = (
        f"oos_informed_backfill full selection funnel: {fn['base_catalog_factors']} base -> "
        f"{fn['field_eligible_tested']} field-eligible (IS-tested) -> {fn['is_candidates']} "
        f"IS-candidates -> {fn['promoted_to_candidate']} promoted "
        f"({fn['is_candidates_excluded_as_oos_collapsers']} OOS-collapsers excluded via the "
        f"pre-existing full-window CSV; {fn['field_ineligible_excluded']} field-ineligible). "
        f"NOT a fresh OOS-free selection; 2021-2026 burned for these 72. "
        f"Artifact: {ARTIFACT.relative_to(PROJECT_ROOT)}"
    )
    ev = ledger.record_event(
        hypothesis_id="factor_lifecycle_phase6", design_hash=design_hash, prose_hash="",
        structural_family="", profile_id="factor_lifecycle", run_id=RUN_DIR.name,
        run_dir=str(RUN_DIR), test_name="factor_lifecycle:phase6_selection_funnel",
        stage="is_only", statistic_name="full_selection_base_pool",
        statistic_value=float(fn["base_catalog_factors"]), n_obs=fn["base_catalog_factors"],
        notes=note, event_kind="measurement",
    )
    print("recorded ledger event id:", ev.get("event_id"))
    print("label:", LABEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
