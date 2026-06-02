"""Phase 7 governance: record the full 24 -> 16 -> 15 selection funnel + oos_informed_backfill label.

Mirrors phase6_record_selection_provenance for the composite/industry-relative promotion. Writes
a committed provenance artifact + a live testing-ledger event recording the FULL selection surface
(24 composites/industry-rel considered -> 16 OOS-stable consumed -> 15 IS-candidate promoted; the
1 IS-draft comp_momentum_quality; the 8 OOS-marginal/collapsed excluded). The 15 must NEVER be
described later as a fresh OOS-free selection.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

OUT = PROJECT_ROOT / "workspace" / "outputs"
DATA = PROJECT_ROOT / "data"
ARTIFACT = PROJECT_ROOT / "workspace" / "research" / "factor_expansion" / "phase7_selection_provenance.json"
RUN_DIR = OUT / "phase6_factor_lifecycle_live_p7prod16"
DERIVED_CSV = (PROJECT_ROOT / "workspace" / "research" / "factor_expansion"
               / "catalog_revalidation" / "derived_revalidation_status.csv")
LABEL = "oos_informed_backfill"


def main() -> int:
    csv = pd.read_csv(DERIVED_CSV).set_index("factor")
    all24 = sorted(csv.index)
    oos16 = sorted(csv[csv["status"] == "candidate"].index)
    excluded8 = [{"factor": f, "full_window_status": str(csv.loc[f, "status"]),
                  "is_rank_icir": round(float(csv.loc[f, "is_rank_icir"]), 4),
                  "oos_rank_icir": round(float(csv.loc[f, "oos_rank_icir"]), 4)}
                 for f in all24 if f not in oos16]

    dry = json.loads((OUT / "phase7_dry_run_result.json").read_text(encoding="utf-8"))
    promoted15 = list(dry["candidates"])
    is_draft = list(dry["drafts"])  # consumed-but-not-promoted (IS-marginal)
    detail = {d["factor"]: d for d in dry["verdict_detail"]}

    provenance = {
        "label": LABEL,
        "run_dir": str(RUN_DIR), "run_id": RUN_DIR.name,
        "hypothesis_id": "factor_lifecycle_phase6", "branch": "factor-lifecycle-p7", "pr": 36,
        "is_window": {"is_start": "2014-01-01", "is_end": "2020-12-31"}, "horizon": 20,
        "selection_funnel": {
            "composite_industry_rel_total": len(all24),                 # 24
            "oos_stable_consumed": len(oos16),                          # 16
            "field_eligible": dry["field_eligible_tested"],             # 16
            "is_candidate_promoted": len(promoted15),                   # 15
            "is_draft_not_promoted": len(is_draft),                     # 1 (comp_momentum_quality)
            "oos_marginal_or_collapsed_excluded": len(excluded8),       # 8
        },
        "promoted_15": [{"factor": f, "expected_direction": detail.get(f, {}).get("expected_direction"),
                         "is_heldout_rank_icir": detail.get(f, {}).get("heldout_rank_icir")}
                        for f in promoted15],
        "is_draft_not_promoted": [{"factor": f, "is_heldout_rank_icir": detail.get(f, {}).get("heldout_rank_icir"),
                                   "sign_consistency": detail.get(f, {}).get("sign_consistency"),
                                   "reason": "IS sign-consistency < 0.70 on 2014-2020 (full-window OOS-stable but IS-marginal)"}
                                  for f in is_draft],
        "oos_marginal_or_collapsed_excluded_8": excluded8,
        "caveats": [
            "These 15 are an OOS-INFORMED conservative backfill, NOT a fresh OOS-free selection. "
            "The selection of the 16 consumed used the PRE-EXISTING full-window (2014-2026) "
            "derived_revalidation_status.csv.",
            "The IS-only validator was NOT contaminated: OOS data did not enter labels / folds / "
            "metrics / set_status; the 15 lifecycle evidence rows are IS-only (oos_rank_icir=NA).",
            "candidate != approved. candidate is an ADDITIVE tier; it can never auto-become approved "
            "(separate P1.1 OOS/promotion gate).",
            "2021-2026 is ALREADY BURNED for these 15 (observed in the pre-existing revalidation). A "
            "future candidate->approved promotion MUST use a genuinely-sealed window.",
            "comp_momentum_quality was consumed (OOS-stable) but the IS-only gate left it DRAFT "
            "(sign-consistency 0.571 < 0.70 on 2014-2020) — the gate filtering, not OOS data.",
            "expected_direction persisted to factor_master (3 inverse predictors: mom_idio_20d, "
            "mom_industry_rel_20d, comp_52w_position) — not implied long-only-positive.",
        ],
        "live_registry_after": {"candidate": 87, "draft": 84, "note": "72 base (Phase 6) + 15 Layer-2 (Phase 7)"},
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", ARTIFACT)
    print("funnel:", json.dumps(provenance["selection_funnel"]))

    # live testing-ledger event for the full selection surface
    from src.alpha_research.testing_ledger import TestingLedgerStore
    from src.research_orchestrator import ResearchRequest
    req = json.loads((OUT / "phase6_request_live_p7prod16.json").read_text(encoding="utf-8-sig"))
    try:
        design_hash = ResearchRequest.from_dict(req).hypothesis.design_hash()
    except Exception as exc:
        design_hash = ""
        print("WARN design_hash:", exc)
    fn = provenance["selection_funnel"]
    note = (f"oos_informed_backfill Layer-2 funnel: {fn['composite_industry_rel_total']} "
            f"composites/industry-rel -> {fn['oos_stable_consumed']} OOS-stable consumed -> "
            f"{fn['is_candidate_promoted']} promoted (1 IS-draft comp_momentum_quality; "
            f"{fn['oos_marginal_or_collapsed_excluded']} OOS-excluded). NOT a fresh OOS-free "
            f"selection; 2021-2026 burned. Artifact: {ARTIFACT.relative_to(PROJECT_ROOT)}")
    ledger = TestingLedgerStore(DATA / "testing_ledger")
    ev = ledger.record_event(
        hypothesis_id="factor_lifecycle_phase6", design_hash=design_hash, prose_hash="",
        structural_family="", profile_id="factor_lifecycle", run_id=RUN_DIR.name,
        run_dir=str(RUN_DIR), test_name="factor_lifecycle:phase7_selection_funnel", stage="is_only",
        statistic_name="layer2_selection_pool", statistic_value=float(fn["composite_industry_rel_total"]),
        n_obs=fn["composite_industry_rel_total"], notes=note, event_kind="measurement",
    )
    print("recorded ledger event:", ev.get("event_id"), "label:", LABEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
