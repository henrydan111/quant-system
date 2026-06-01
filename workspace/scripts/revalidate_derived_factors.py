# ──────────────────────────────────────────────────────────────────────
# PR 7 of 2026-05-26 freeze plan — SCRIPT_STATUS header block.
# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: joinquant_attribution_only
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   Closes out the catalog re-validation: the 20 Layer-2 composites + 4 industry-
#   relative factors that the 147-base run did not cover (Layer-2 post-processing +
#   SW2021 labels). Same predeclared walk-forward rule + a GROSS LONG-ONLY top-bucket
#   metric (top-decile-minus-universe, sign-aligned) so long-only viability is
#   measured directly. Read-only.
#
#   PHASE 4 (factor_lifecycle): the logic now lives in the TESTED module
#   ``src.alpha_research.factor_lifecycle`` — this is a THIN WRAPPER over
#   ``run_historical_derived_revalidation`` (mode-2 HISTORICAL, ``historical_investigation``).
#   NOT a candidate-promotion entry point.
# ──────────────────────────────────────────────────────────────────────
"""Re-validate the 24 derived catalog factors + long-only metric (thin wrapper, Phase 4)."""

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
    END, HORIZON, IS_END, OOS_START, START, run_historical_derived_revalidation,
)

OUTDIR = PROJECT_ROOT / "workspace" / "research" / "factor_expansion" / "catalog_revalidation"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("revalidate_derived")


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    log.info("Re-validating 24 derived factors %s -> %s (historical IS/OOS + long-only, mode 2).", START, END)
    df = run_historical_derived_revalidation()
    report.write_derived_csv(df, OUTDIR / "derived_revalidation_status.csv")
    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "n_derived": int(len(df)),
        "status_counts": dict(Counter(df["status"])),
        "window": {"start": START, "is_end": IS_END, "oos_start": OOS_START, "end": END},
        "horizon": HORIZON,
        "long_only_metric": "top-decile minus count-weighted universe, sign-aligned, ann + sharpe + hit (GROSS)",
        "method": "historical_investigation; logic ported to src/alpha_research/factor_lifecycle/.",
    }
    (OUTDIR / "derived_revalidation_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log.info("status counts: %s", meta["status_counts"])
    log.info("wrote %s", OUTDIR / "derived_revalidation_status.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
