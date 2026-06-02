# ──────────────────────────────────────────────────────────────────────
# Phase 7 (composite/industry-rel) DRY-RUN — pre-flight before any live write to
# data/factor_registry/. Computes the IS-only walk-forward verdicts for the 16 OOS-stable
# Layer-2 factors (12 composites + 4 industry-relative, per derived_revalidation_status.csv
# status==candidate) via the FIXED Layer-2 builder, and reports the WRITE PLAN. NOTHING is
# written to data/factor_registry/. Read-only w.r.t. live data; Qlib compute only.
# ──────────────────────────────────────────────────────────────────────
"""Phase 7 composite/industry-rel dry-run: Layer-2 IS-only verdicts + write-plan counts (no live write)."""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_library.catalog import get_composite_defs, get_industry_relative_defs
from src.alpha_research.factor_lifecycle.walk_forward_validation import (
    load_is_windowed_panel_with_layer2,
    run_is_walk_forward,
)
from src.alpha_research.walk_forward import TimeSplit
from src.research_orchestrator.factor_lifecycle_steps import per_factor_field_eligible

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("phase7_dry_run")

TIME_SPLIT = TimeSplit("2014-01-01", "2020-12-31", "2021-01-01", "2022-01-01")
HORIZON = 20
FACTOR_ORIGIN = "a_priori"
OUTDIR = PROJECT_ROOT / "workspace" / "outputs"
QLIB_DIR = PROJECT_ROOT / "data" / "qlib_data"
DERIVED_CSV = (PROJECT_ROOT / "workspace" / "research" / "factor_expansion"
               / "catalog_revalidation" / "derived_revalidation_status.csv")


def _icir_key(d):
    v = d.get("heldout_rank_icir")
    return abs(v) if v == v else -1.0  # NaN-safe


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    csv = pd.read_csv(DERIVED_CSV)
    oos_stable = sorted(csv[csv["status"] == "candidate"]["factor"])
    comp_all = {str(d["name"]): d for d in get_composite_defs()}
    ind_all = {str(d["name"]): d for d in get_industry_relative_defs()}
    comp_names = [n for n in oos_stable if n in comp_all]
    ind_names = [n for n in oos_stable if n in ind_all]
    unknown = [n for n in oos_stable if n not in comp_all and n not in ind_all]
    log.info("OOS-stable input: %d (=%d composites + %d industry-rel); unknown=%s",
             len(oos_stable), len(comp_names), len(ind_names), unknown)

    elig = per_factor_field_eligible(comp_names + ind_names, stage="formal_validation")
    excluded = sorted(n for n, ok in elig.items() if not ok)
    comp_elig = [n for n in comp_names if elig.get(n)]
    ind_elig = [n for n in ind_names if elig.get(n)]
    log.info("field-eligible: %d composites + %d industry-rel; field-excluded=%s",
             len(comp_elig), len(ind_elig), excluded)

    t0 = time.time()
    log.info("Building Layer-2 IS-only panel for %d factors over [%s, %s] (horizon=%d) ...",
             len(comp_elig) + len(ind_elig), TIME_SPLIT.is_start, TIME_SPLIT.is_end, HORIZON)
    panel = load_is_windowed_panel_with_layer2(
        gated_base=[],
        gated_composite_defs=[comp_all[n] for n in comp_elig],
        gated_industry_defs=[ind_all[n] for n in ind_elig],
        time_split=TIME_SPLIT, horizon=HORIZON, qlib_dir=str(QLIB_DIR),
    )
    log.info("Layer-2 panel built in %.0fs: shape=%s, max_factor_date=%s, max_label_realization=%s",
             time.time() - t0, panel.factor_panel.shape,
             panel.max_factor_date.date(), panel.max_label_realization_date.date())

    log.info("Running IS-only walk-forward (factor_origin=%s) ...", FACTOR_ORIGIN)
    result = run_is_walk_forward(panel=panel, time_split=TIME_SPLIT, horizon=HORIZON, factor_origin=FACTOR_ORIGIN)
    rows = [dict(r) for r in result.rows]
    candidates = sorted(r["factor"] for r in rows if r.get("status") == "candidate")
    drafts = sorted(r["factor"] for r in rows if r.get("status") == "draft")

    write_plan = {
        "window": {"is_start": TIME_SPLIT.is_start, "is_end": TIME_SPLIT.is_end},
        "horizon": HORIZON, "factor_origin": FACTOR_ORIGIN, "evidence_kind": result.evidence_kind,
        "oos_stable_input": len(comp_names) + len(ind_names),
        "input_composites": len(comp_names), "input_industry_rel": len(ind_names),
        "field_eligible_tested": len(comp_elig) + len(ind_elig),
        "field_excluded": len(excluded), "field_excluded_factors": excluded,
        "candidate_verdicts": len(candidates), "draft_verdicts": len(drafts),
        "effective_eval_end": str(result.effective_eval_end.date()),
        "candidates": candidates, "drafts": drafts,
        "verdict_detail": sorted(
            [{"factor": r["factor"], "heldout_rank_icir": r.get("heldout_rank_icir"),
              "sign_consistency": r.get("sign_consistency"),
              "expected_direction": r.get("expected_direction"), "status": r.get("status")}
             for r in rows], key=_icir_key, reverse=True),
        "live_registry_written": False,
        "note": "DRY-RUN ONLY — review before any live write. The 16 are the OOS-stable subset of "
                "the 24 (derived_revalidation_status.csv status==candidate); promotion would be "
                "oos_informed_backfill (candidate!=approved; 2021-2026 burned for these).",
    }
    out = OUTDIR / "phase7_dry_run_result.json"
    out.write_text(json.dumps(write_plan, indent=2), encoding="utf-8")
    log.info("=== PHASE 7 DRY-RUN WRITE PLAN (no live write) ===")
    log.info("tested=%d  CANDIDATE=%d  draft=%d  field-excluded=%d",
             len(comp_elig) + len(ind_elig), len(candidates), len(drafts), len(excluded))
    log.info("candidates: %s", candidates)
    log.info("drafts: %s", drafts)
    log.info("wrote %s", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
