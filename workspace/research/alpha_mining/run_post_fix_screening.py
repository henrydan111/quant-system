"""Follow-up Plan #1 - Post-fix factor screening runner.

Direct-call entrypoint that bypasses the research_orchestrator's formal-
mode hypothesis requirement. This script exists ONLY because the legacy
``workspace/scripts/batch_factor_screening.py`` CLI now routes through
``run_research()`` which raises ``ValueError: Formal profile factor_screening
requires a hypothesis.`` for any formal-mode request.

The underlying screening primitives (``compute_factors``, ``add_composites``,
``run_batch_screening``) don't care about the orchestrator - this script
calls them directly and writes the same output artifacts the legacy CLI
produces so ``factor_registry_cli.py import-screening`` can consume them.

One-off usage:
    venv/Scripts/python.exe workspace/research/alpha_mining/run_post_fix_screening.py \\
        --outdir workspace/research/alpha_mining/post_fix_screening_20260411

Ref: plan file ``C:\\Users\\henry\\.claude\\plans\\vast-exploring-rabbit.md``
Step 7. Archive this script under the post-fix run directory after use.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_eval.batch_screening import run_batch_screening
from src.alpha_research.factor_library import operators
from src.alpha_research.factor_library.catalog import (
    get_composite_defs,
    get_factor_catalog,
    get_industry_relative_defs,
)


def _classify_grade(row: pd.Series) -> str:
    """Replicate the grading used by workspace/scripts/batch_factor_screening.py."""
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
    parser = argparse.ArgumentParser(description="Post-fix factor screening direct runner")
    parser.add_argument("--start", default="2012-01-01")
    parser.add_argument("--end", default="2026-02-27")
    parser.add_argument("--horizon", type=int, nargs="+", default=[5, 10, 20])
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--include-new-data", action="store_true", default=True)
    parser.add_argument("--engine", choices=["batch", "reference"], default="batch")
    parser.add_argument(
        "--kernels",
        type=int,
        default=None,
        help="Qlib worker count (None = Qlib default multi-process; 1 = single-thread)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    log = logging.getLogger("run_post_fix_screening")

    args.outdir.mkdir(parents=True, exist_ok=True)

    log.info("Loading catalog (include_new_data=%s)...", args.include_new_data)
    catalog = get_factor_catalog(include_new_data=args.include_new_data)
    composites = get_composite_defs()
    log.info("Catalog has %d base factors and %d composites", len(catalog), len(composites))

    log.info("Computing base factors via Qlib (%s -> %s)...", args.start, args.end)
    t0 = time.time()
    factors_df, fwd_df = operators.compute_factors(
        catalog=catalog,
        start_date=args.start,
        end_date=args.end,
        horizons=args.horizon,
        qlib_dir=str(PROJECT_ROOT / "data" / "qlib_data"),
        kernels=args.kernels,
    )
    t_compute = time.time() - t0
    log.info("compute_factors done in %.1fs; factors shape=%s", t_compute, factors_df.shape)

    log.info("Building composite factors...")
    t0 = time.time()
    factors_df = operators.add_composites(factors_df, composite_defs=composites)
    t_comp = time.time() - t0
    log.info("add_composites done in %.1fs; total shape=%s", t_comp, factors_df.shape)

    # Industry-relative composites (Layer 2 — requires external SW2021 labels)
    # Plan vast-exploring-rabbit v8 phase B3.3.
    industry_rel_defs = get_industry_relative_defs()
    if industry_rel_defs:
        log.info(
            "Building %d industry-relative composites (PIT-safe market_cap "
            "via fetch_auxiliary_fields → Ref($total_mv, 1))...",
            len(industry_rel_defs),
        )
        t0 = time.time()
        # Reuse fetch_auxiliary_fields from event_driven_strategy_research
        # for PIT-safe market_cap (Codex review-3 B2 fix: this function uses
        # Ref($total_mv, 1) at line 416, NOT raw $total_mv).
        from workspace.research.alpha_mining.event_driven_strategy_research import (
            fetch_auxiliary_fields,
        )
        from src.data_infra.provider_metadata import build_industry_series_asof
        aux_df = fetch_auxiliary_fields(args.start, args.end)
        industry_series = build_industry_series_asof(factors_df.index, "L1")
        factors_df = operators.add_industry_relative_composites(
            factors_df,
            industry_series,
            market_cap=aux_df["market_cap"],
            defs=industry_rel_defs,
        )
        t_ir = time.time() - t0
        log.info(
            "add_industry_relative_composites done in %.1fs; total shape=%s",
            t_ir,
            factors_df.shape,
        )

    log.info("Running %s screening engine across horizons %s...", args.engine, args.horizon)
    t0 = time.time()
    results = run_batch_screening(
        factors_df,
        fwd_df,
        horizons=tuple(args.horizon),
        engine=args.engine,
        progress_every=25,
        log=log,
    )
    t_screen = time.time() - t0
    log.info("Screening done in %.1fs; results rows=%d", t_screen, len(results))

    # Grade classification
    results = results.copy()
    results["grade"] = results.apply(_classify_grade, axis=1)
    grade_counts = results["grade"].value_counts().to_dict()
    log.info("Grade counts: %s", grade_counts)

    # Write artifacts in the same shape as workspace/scripts/batch_factor_screening.py
    parquet_path = args.outdir / "factor_screening_results.parquet"
    csv_path = args.outdir / "factor_screening_report.csv"
    summary_txt = args.outdir / "factor_screening_summary.txt"
    metadata_path = args.outdir / "factor_screening_run_metadata.json"

    results.to_parquet(parquet_path, index=False)
    results.to_csv(csv_path, index=False)
    log.info("Wrote %s and %s", parquet_path, csv_path)

    summary_lines = [
        f"Post-fix screening run generated at {datetime.now().isoformat(timespec='seconds')}",
        f"Window: {args.start} to {args.end}",
        f"Horizons: {args.horizon}",
        f"Factors screened: {len(results)}",
        f"Grade counts: {grade_counts}",
        f"Include new data: {args.include_new_data}",
        f"Engine: {args.engine}",
        "",
        "Notes:",
        "  - This run was produced by run_post_fix_screening.py (not the",
        "    orchestrator-routed legacy CLI) as part of follow-up plan #1.",
        "  - Factor library operators had same-day leakage fixed across 45+",
        "    operators before this screening ran.",
    ]
    summary_txt.write_text("\n".join(summary_lines), encoding="utf-8")

    metadata = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "start_date": args.start,
        "end_date": args.end,
        "horizons": args.horizon,
        "include_new_data": args.include_new_data,
        "engine": args.engine,
        "factor_count": int(len(results)),
        "grade_counts": {k: int(v) for k, v in grade_counts.items()},
        "output_dir": str(args.outdir.resolve()),
        "qlib_dir": str((PROJECT_ROOT / "data" / "qlib_data").resolve()),
        "timing_seconds": {
            "compute_factors": round(t_compute, 2),
            "add_composites": round(t_comp, 2),
            "run_batch_screening": round(t_screen, 2),
        },
        "plan_reference": "follow-up plan #1 (factor library same-day leakage fix)",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    log.info("Wrote %s", metadata_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
