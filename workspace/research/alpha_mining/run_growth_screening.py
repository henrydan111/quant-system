"""Phase 1 quick-kill screening for the growth-stock hypothesis-driven plan.

Scope: 14 growth factors + 3 growth-leaning composites + 3 new alpha
endpoint factors = 20 factors. Sandbox mode (no hypothesis required).

Window: 2014-01-01 to 2026-02-27. Skips the early 2012-13 period where
some Phase 3 endpoints (cyq_perf starts ~2018) and `top_inst` /
`block_trade` coverage are sparse, but is still long enough for
14-year walk-forward stability checks at 5/10/20d horizons.

Output:
    workspace/research/alpha_mining/growth_strategy_screening_<ts>/
        factor_screening_results.parquet
        factor_screening_report.csv
        factor_screening_summary.txt
        factor_screening_run_metadata.json

Plan ref: C:\\Users\\henry\\.claude\\plans\\jolly-seeking-lollipop.md (Phase 1).
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
from src.alpha_research.factor_library.catalog import get_composite_defs, get_factor_catalog


# Factors in scope for the growth-stock plan Phase 1.
GROWTH_FACTORS = [
    "grow_revenue_yoy", "grow_netprofit_yoy", "grow_opprofit_yoy",
    "grow_opprofit_qoq", "grow_eps_yoy", "grow_roe_yoy",
    "grow_rev_acceleration", "grow_profit_acceleration", "grow_consistency",
    "grow_gross_margin_chg", "grow_roe_improvement",
    "grow_rev_trend", "grow_profit_trend", "grow_peg",
]
ALPHA_FACTORS = [
    "alpha_inst_net_buy_20d", "alpha_insider_net_buy_60d", "alpha_block_discount_20d",
]
GROWTH_COMPOSITES = ["comp_garp", "comp_growth_value", "comp_qual_grow"]


def _classify_grade(row: pd.Series) -> str:
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
    parser = argparse.ArgumentParser(description="Growth-strategy Phase 1 quick-kill screening")
    parser.add_argument("--start", default="2014-01-01")
    parser.add_argument("--end", default="2026-02-27")
    parser.add_argument("--horizon", type=int, nargs="+", default=[5, 10, 20])
    parser.add_argument("--outdir", type=Path, default=None,
                        help="Output dir (default: growth_strategy_screening_<ts>/)")
    parser.add_argument("--kernels", type=int, default=None)
    args = parser.parse_args()

    if args.outdir is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.outdir = Path(__file__).parent / f"growth_strategy_screening_{ts}"
    args.outdir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    log = logging.getLogger("run_growth_screening")

    log.info("Loading full catalog (include_new_data=True for alpha factors)...")
    full_catalog = get_factor_catalog(include_new_data=True)
    full_composites = get_composite_defs()

    # Filter to scope
    catalog = {name: full_catalog[name] for name in (GROWTH_FACTORS + ALPHA_FACTORS) if name in full_catalog}
    missing_base = sorted(set(GROWTH_FACTORS + ALPHA_FACTORS) - catalog.keys())
    if missing_base:
        log.error("Missing base factors in catalog: %s", missing_base)
        return 2

    composites = [c for c in full_composites if c["name"] in GROWTH_COMPOSITES]
    missing_comp = sorted(set(GROWTH_COMPOSITES) - {c["name"] for c in composites})
    if missing_comp:
        log.error("Missing composites: %s", missing_comp)
        return 2

    log.info("Scope: %d base factors + %d composites = %d total", len(catalog), len(composites), len(catalog) + len(composites))
    log.info("  base: %s", sorted(catalog.keys()))
    log.info("  composites: %s", [c["name"] for c in composites])

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

    log.info("Running batch screening across horizons %s...", args.horizon)
    t0 = time.time()
    results = run_batch_screening(
        factors_df,
        fwd_df,
        horizons=tuple(args.horizon),
        engine="batch",
        progress_every=5,
        log=log,
    )
    t_screen = time.time() - t0
    log.info("Screening done in %.1fs; results rows=%d", t_screen, len(results))

    results = results.copy()
    results["grade"] = results.apply(_classify_grade, axis=1)
    grade_counts = results["grade"].value_counts().to_dict()
    log.info("Grade counts: %s", grade_counts)

    parquet_path = args.outdir / "factor_screening_results.parquet"
    csv_path = args.outdir / "factor_screening_report.csv"
    summary_txt = args.outdir / "factor_screening_summary.txt"
    metadata_path = args.outdir / "factor_screening_run_metadata.json"

    results.to_parquet(parquet_path, index=False)
    results.to_csv(csv_path, index=False)

    summary_lines = [
        "Growth-Strategy Phase 1 Quick-Kill Screening",
        "=" * 60,
        f"Generated: {datetime.now().isoformat()}",
        f"Window: {args.start} to {args.end}",
        f"Horizons: {args.horizon}",
        f"Base factors: {len(catalog)}, Composites: {len(composites)}",
        f"Grade counts: {grade_counts}",
        "",
        "Factor-grade table (sorted by |rank_icir_5d| desc):",
        "-" * 60,
    ]
    if "rank_icir_5d" in results.columns and "factor" in results.columns:
        sorted_r = results.assign(_abs=results["rank_icir_5d"].abs()).sort_values("_abs", ascending=False)
        for _, row in sorted_r.iterrows():
            summary_lines.append(
                f"  {row.get('factor','?'):<35s} grade={row.get('grade','?')}  "
                f"rank_icir_5d={row.get('rank_icir_5d', float('nan')):>+7.4f}  "
                f"monotonic={row.get('monotonic','?')}"
            )
    summary_txt.write_text("\n".join(summary_lines), encoding="utf-8")

    metadata_path.write_text(json.dumps({
        "generated_at": datetime.now().isoformat(),
        "window": {"start": args.start, "end": args.end},
        "horizons": args.horizon,
        "scope": {
            "growth_factors": GROWTH_FACTORS,
            "alpha_factors": ALPHA_FACTORS,
            "growth_composites": GROWTH_COMPOSITES,
        },
        "timings_sec": {"compute_factors": t_compute, "add_composites": t_comp, "run_batch_screening": t_screen},
        "grade_counts": grade_counts,
        "results_count": int(len(results)),
        "factors_df_shape": list(factors_df.shape),
    }, indent=2), encoding="utf-8")

    log.info("Wrote artifacts to %s", args.outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
