# ──────────────────────────────────────────────────────────────────────
# PR 7 of 2026-05-26 freeze plan — SCRIPT_STATUS header block.
# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: joinquant_attribution_only
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   Walk-forward re-validation of the 147 base catalog factors (Layer-1 of the
#   "171-factor" library) with a proper IS(2014-2020) / OOS(2021-2026) split +
#   per-year fold-stability, assigning a status by a PREDEFINED mechanical rule.
#   Read-only w.r.t. registry/catalog; writes a status-assignment CSV + metadata.
#
#   PHASE 4 (factor_lifecycle): the walk-forward + IS/OOS + status logic now lives
#   in the TESTED module ``src.alpha_research.factor_lifecycle`` — this file is a
#   THIN WRAPPER over ``run_historical_catalog_revalidation`` (mode-2 HISTORICAL
#   revalidation, ``historical_investigation``). It is NOT a candidate-promotion
#   entry point; the formal ``draft -> candidate`` gate is ``run_is_walk_forward``
#   (IS-only, ``is_end``-bounded) in the same package, never this script.
#
#   HONESTY / CONTAMINATION NOTE: the 147 factor DEFINITIONS are a-priori and were
#   never promoted using OOS (all `draft`); this IS/OOS split is a legitimate first
#   clean split-test but NOT pristine never-computed OOS. After this run, 2021-2026
#   is spent. The PREDEFINED STATUS RULE is frozen in
#   ``factor_lifecycle.status_rules.assign_historical_status`` (oos-based; parity).
#   ``approved`` is NEVER assigned here (requires the strategy-level promotion gate).
# ──────────────────────────────────────────────────────────────────────
"""Walk-forward re-validation of the base catalog factors (thin wrapper, Phase 4)."""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_lifecycle import report
from src.alpha_research.factor_lifecycle.revalidation import (
    END, HORIZON, IS_END, OOS_START, START, run_historical_catalog_revalidation,
)

OUTDIR = PROJECT_ROOT / "workspace" / "research" / "factor_expansion" / "catalog_revalidation"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("revalidate_catalog")


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    log.info("Re-validating base catalog factors %s -> %s (historical IS/OOS, mode 2).", START, END)
    df = run_historical_catalog_revalidation()
    report.write_catalog_csv(df, OUTDIR / "catalog_revalidation_status.csv")
    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "window": {"start": START, "is_end": IS_END, "oos_start": OOS_START, "end": END},
        "horizon": HORIZON, "n_factors": int(len(df)),
        "status_counts": dict(Counter(df["status"])),
        "field_ineligible_count": int((~df["field_eligible"].astype(bool)).sum()),
        "method": "walk-forward per-year fold-stability + IS/OOS split (historical_investigation); "
                  "logic ported to src/alpha_research/factor_lifecycle/.",
        "approved_note": "approved NOT assigned here -- requires strategy-level promotion gate.",
    }
    (OUTDIR / "catalog_revalidation_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log.info("status counts: %s | field-ineligible: %s", meta["status_counts"], meta["field_ineligible_count"])
    log.info("wrote %s", OUTDIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
