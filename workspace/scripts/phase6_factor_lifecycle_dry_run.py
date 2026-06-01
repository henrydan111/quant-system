# ──────────────────────────────────────────────────────────────────────
# Phase 6 (factor_lifecycle) DRY-RUN — GPT-mandated pre-flight before any live
# write to data/factor_registry/. Computes the IS-only walk-forward verdicts for
# the field-ELIGIBLE base factors and reports the WRITE PLAN (counts). It writes
# ONLY to workspace/outputs/ (never data/factor_registry/), so the live registry
# is untouched. Read-only w.r.t. live data; Qlib compute only.
#
# The 114-factor IS panel is expensive (~29 min); it is cached to parquet so a
# downstream failure does not force a recompute. Delete the cache to force a fresh
# compute.
# ──────────────────────────────────────────────────────────────────────
"""Phase 6 factor_lifecycle dry-run: walk-forward verdicts + write-plan counts (no live write)."""

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

from src.alpha_research.factor_library.catalog import get_factor_catalog
from src.alpha_research.factor_lifecycle.walk_forward_validation import (
    IsWindowedPanel,
    load_is_windowed_panel,
    load_open_trading_days,
    run_is_walk_forward,
)
from src.alpha_research.walk_forward import TimeSplit
from src.research_orchestrator.factor_lifecycle_steps import per_factor_field_eligible

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("phase6_dry_run")

# Same window/horizon as the catalog revalidation (IS bounded to is_end=2020-12-31).
TIME_SPLIT = TimeSplit("2014-01-01", "2020-12-31", "2021-01-01", "2022-01-01")
HORIZON = 20
FACTOR_ORIGIN = "a_priori"  # the 147 catalog factors are a-priori definitions
OUTDIR = PROJECT_ROOT / "workspace" / "outputs"
QLIB_DIR = PROJECT_ROOT / "data" / "qlib_data"
PANEL_CACHE = OUTDIR / "phase6_panel_cache.parquet"
LABEL_COL = "__label__"


def _build_or_load_panel(eligible_catalog: dict) -> IsWindowedPanel:
    """Build the IS-only windowed panel (expensive) or load it from the parquet cache."""
    if PANEL_CACHE.exists():
        log.info("Loading cached IS panel from %s ...", PANEL_CACHE)
        combined = pd.read_parquet(PANEL_CACHE)
        label = combined.pop(LABEL_COL)
        panel = IsWindowedPanel(
            factor_panel=combined, label=label, is_end=TIME_SPLIT.is_end,
            horizon=HORIZON, open_days=load_open_trading_days(None),
        )
        log.info("Cached panel loaded: shape=%s", panel.factor_panel.shape)
        return panel

    t0 = time.time()
    log.info("Building IS-only windowed panel for %d eligible factors over [%s, %s] (horizon=%d) ...",
             len(eligible_catalog), TIME_SPLIT.is_start, TIME_SPLIT.is_end, HORIZON)
    panel = load_is_windowed_panel(eligible_catalog, TIME_SPLIT, horizon=HORIZON, qlib_dir=str(QLIB_DIR))
    log.info("Panel built in %.0fs: factor_panel shape=%s, max_factor_date=%s, max_label_realization=%s",
             time.time() - t0, panel.factor_panel.shape,
             panel.max_factor_date.date(), panel.max_label_realization_date.date())
    combined = panel.factor_panel.copy()
    combined[LABEL_COL] = panel.label
    combined.to_parquet(PANEL_CACHE)
    log.info("Cached IS panel -> %s", PANEL_CACHE)
    return panel


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    full = get_factor_catalog(include_new_data=True)  # 147 base
    elig = per_factor_field_eligible(list(full), stage="formal_validation")
    eligible = sorted(n for n, ok in elig.items() if ok)
    excluded = sorted(n for n, ok in elig.items() if not ok)
    eligible_catalog = {n: full[n] for n in eligible}
    log.info("Phase 6 dry-run: %d base factors -> %d field-eligible (tested), %d field-excluded.",
             len(full), len(eligible), len(excluded))

    panel = _build_or_load_panel(eligible_catalog)

    log.info("Running IS-only walk-forward (factor_origin=%s) ...", FACTOR_ORIGIN)
    result = run_is_walk_forward(panel=panel, time_split=TIME_SPLIT, horizon=HORIZON, factor_origin=FACTOR_ORIGIN)
    rows = [dict(r) for r in result.rows]
    candidates = sorted(r["factor"] for r in rows if r.get("status") == "candidate")
    drafts = sorted(r["factor"] for r in rows if r.get("status") == "draft")

    # surface the strongest candidates by |heldout rank ICIR| for the review
    ranked = sorted(
        ({"factor": r["factor"], "heldout_rank_icir": r.get("heldout_rank_icir"),
          "sign_consistency": r.get("sign_consistency"), "n_blocks": r.get("n_heldout_blocks"),
          "status": r.get("status"), "reason": r.get("reason")} for r in rows),
        key=lambda d: (abs(d["heldout_rank_icir"]) if d["heldout_rank_icir"] == d["heldout_rank_icir"] else -1.0),
        reverse=True,
    )

    write_plan = {
        "window": {"is_start": TIME_SPLIT.is_start, "is_end": TIME_SPLIT.is_end},
        "horizon": HORIZON,
        "factor_origin": FACTOR_ORIGIN,
        "evidence_kind": result.evidence_kind,
        "base_factor_count": len(full),
        "field_eligible_tested": len(eligible),
        "field_excluded": len(excluded),
        "composites_industry_rel_deferred": 24,
        "candidate_verdicts": len(candidates),
        "draft_verdicts": len(drafts),
        "effective_eval_end": str(result.effective_eval_end.date()),
        "candidates": candidates,
        "field_excluded_factors": excluded,
        "top_by_abs_icir": ranked[:25],
        "live_registry_written": False,  # DRY-RUN: nothing written to data/factor_registry/
        "note": "DRY-RUN ONLY — review counts before any live write. The candidate->approved "
                "OOS path and the 6 sealed-OOS winners are SEPARATE and not in this run.",
    }
    out_path = OUTDIR / "phase6_dry_run_result.json"
    out_path.write_text(json.dumps(write_plan, indent=2), encoding="utf-8")

    log.info("=== PHASE 6 DRY-RUN WRITE PLAN (no live write) ===")
    log.info("tested(field-eligible)=%d  field-excluded=%d  CANDIDATE=%d  draft=%d",
             len(eligible), len(excluded), len(candidates), len(drafts))
    log.info("candidates: %s", candidates)
    log.info("wrote %s", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
