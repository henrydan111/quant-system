# ──────────────────────────────────────────────────────────────────────
# PR 7 of 2026-05-26 freeze plan — SCRIPT_STATUS header block.
# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: joinquant_attribution_only
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   IS-only factor screening of the 21 formal-eligible factor-expansion
#   candidates (GPT 5.5 Pro Round-4 GO set). Loads the candidate expressions
#   from factor_candidates_merged.csv (formal_eligible == "yes"), computes them
#   via the sanctioned compute_factors() -> qlib_windowed_features path
#   (stage="is_only"), and runs the validated batch-screening engine
#   (IC/RankIC/ICIR/quantile/monotonicity/decay/turnover). IS window only
#   (2014-01-01 .. 2020-12-31) — the 2021+ OOS is left SEALED per the project's
#   research-integrity standard. Read-only: writes screening artifacts under
#   workspace/research/factor_expansion/screening_is/ and nothing else; no
#   registry/catalog writes, no Tushare, no field promotions.
# ──────────────────────────────────────────────────────────────────────
"""Screen the 21 formal-eligible factor-expansion candidates (IS only).

Usage:
    venv/Scripts/python.exe workspace/scripts/screen_factor_expansion_21.py
"""

from __future__ import annotations

import csv
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_eval.batch_screening import run_batch_screening
from src.alpha_research.factor_library import operators

import os
MERGED_CSV = PROJECT_ROOT / "workspace/research/factor_expansion/factor_candidates_merged.csv"
# OUTDIR overridable via env so successive runs (21-factor pre-Wave1, 47-factor
# post-Wave1) can be preserved side by side for comparison.
OUTDIR = PROJECT_ROOT / "workspace/research/factor_expansion" / os.environ.get(
    "SCREEN_OUTDIR", "screening_is"
)
IS_START = "2014-01-01"
IS_END = "2020-12-31"
HORIZONS = [5, 10, 20]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("screen_factor_expansion_21")


def load_formal_eligible_catalog() -> dict[str, str]:
    """Return {name: qlib_expression} for the formal_eligible == yes rows."""
    catalog = {}
    for r in csv.DictReader(open(MERGED_CSV, encoding="utf-8")):
        if r["formal_eligible"].strip().lower() == "yes":
            catalog[r["name"]] = r["qlib_expression"]
    return catalog


def _classify_grade(row: pd.Series) -> str:
    """Same grade rule as workspace/research/alpha_mining/run_post_fix_screening.py."""
    rankic_icir_5 = float(row.get("rank_icir_5d", float("nan")))
    monotonic = bool(row.get("monotonic", False))
    abs_icir = abs(rankic_icir_5) if pd.notna(rankic_icir_5) else 0.0
    if abs_icir >= 0.6 and monotonic:
        return "A"
    if abs_icir >= 0.3:
        return "B"
    if abs_icir >= 0.1:
        return "C"
    return "D"


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    catalog = load_formal_eligible_catalog()
    log.info("Loaded %d formal-eligible candidates from %s", len(catalog), MERGED_CSV.name)
    for name in catalog:
        log.info("  %s", name)

    log.info("Computing factors via Qlib (IS %s -> %s, stage=is_only)...", IS_START, IS_END)
    t0 = time.time()
    factors_df, fwd_df = operators.compute_factors(
        catalog=catalog,
        start_date=IS_START,
        end_date=IS_END,
        horizons=HORIZONS,
        qlib_dir=str(PROJECT_ROOT / "data" / "qlib_data"),
        kernels=1,
        stage="is_only",
    )
    t_compute = time.time() - t0
    log.info("compute_factors done in %.1fs; factors shape=%s", t_compute, factors_df.shape)

    log.info("Running batch screening across horizons %s...", HORIZONS)
    t0 = time.time()
    results = run_batch_screening(
        factors_df, fwd_df, horizons=tuple(HORIZONS), engine="batch",
        progress_every=5, log=log,
    )
    t_screen = time.time() - t0
    log.info("Screening done in %.1fs; results rows=%d", t_screen, len(results))

    results = results.copy()
    results["grade"] = results.apply(_classify_grade, axis=1)
    grade_counts = results["grade"].value_counts().to_dict()
    log.info("Grade counts: %s", grade_counts)

    results.to_parquet(OUTDIR / "screening_is_results.parquet", index=False)
    results.to_csv(OUTDIR / "screening_is_report.csv", index=True)

    metadata = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "window": {"is_start": IS_START, "is_end": IS_END, "oos_status": "SEALED (2021+ untouched)"},
        "horizons": HORIZONS,
        "factor_count": int(len(results)),
        "grade_counts": {k: int(v) for k, v in grade_counts.items()},
        "source": "factor_candidates_merged.csv (formal_eligible == yes)",
        "qlib_dir": str((PROJECT_ROOT / "data" / "qlib_data").resolve()),
        "stage": "is_only",
        "timing_seconds": {"compute_factors": round(t_compute, 2),
                           "run_batch_screening": round(t_screen, 2)},
    }
    (OUTDIR / "screening_is_run_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    log.info("Wrote artifacts under %s", OUTDIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
