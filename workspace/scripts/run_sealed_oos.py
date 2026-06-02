# ──────────────────────────────────────────────────────────────────────
# PR 7 of 2026-05-26 freeze plan — SCRIPT_STATUS header block.
# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: joinquant_attribution_only
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   SEALED OOS runner for the factor-expansion frozen top set. Runs the
#   factor_eval battery (IC/RankIC/ICIR/quantile/monotonicity/LS Sharpe/decay)
#   on the OOS window via the sanctioned compute_factors() -> qlib_windowed_features
#   path with stage="oos_test". This is the ONE-SHOT sealed-OOS evaluation:
#   it reads the frozen top-set factor NAMES from a committed JSON (so it cannot
#   see anything but the frozen set), runs ONCE, and writes evidence. NO tuning,
#   NO re-selection. OOS window matches the prior long_only_50cagr protocol
#   (IS 2014-2020, sealed OOS 2021-01-01 -> provider end).
# ──────────────────────────────────────────────────────────────────────
"""One-shot sealed-OOS evaluation of the frozen factor-expansion top set."""

from __future__ import annotations

import csv
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_eval.batch_screening import run_batch_screening
from src.alpha_research.factor_library import operators

EXP = PROJECT_ROOT / "workspace" / "research" / "factor_expansion"
MERGED_CSV = EXP / "factor_candidates_merged.csv"
FROZEN_JSON = EXP / "oos_frozen_topset.json"   # written by the freeze step
OUTDIR = EXP / "screening_oos"
OOS_START = "2021-01-01"
OOS_END = "2026-02-27"   # provider calendar end (frozen 2026-02-27)
HORIZONS = [5, 10, 20]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("run_sealed_oos")


def load_frozen_catalog() -> dict[str, str]:
    """Return {name: expression} for ONLY the frozen top-set factors.

    The factor names come from the committed freeze JSON; the expressions come
    from the merged CSV. The runner can therefore only ever touch the frozen
    set — it cannot screen the full universe against OOS.
    """
    frozen = json.loads(FROZEN_JSON.read_text(encoding="utf-8"))
    names = list(frozen["frozen_topset"])
    expr_by_name = {
        r["name"]: r["qlib_expression"]
        for r in csv.DictReader(open(MERGED_CSV, encoding="utf-8"))
    }
    catalog = {}
    missing = []
    for n in names:
        if n in expr_by_name:
            catalog[n] = expr_by_name[n]
        else:
            missing.append(n)
    if missing:
        raise SystemExit(f"FATAL: frozen factor(s) not in merged CSV: {missing}")
    return catalog


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
    OUTDIR.mkdir(parents=True, exist_ok=True)
    if (OUTDIR / "screening_oos_report.csv").exists():
        raise SystemExit(
            "REFUSING TO RE-RUN: screening_oos_report.csv already exists. The sealed "
            "OOS is one-shot. Delete the dir manually ONLY for a verified mechanical "
            "re-run of the SAME frozen set (log the reason)."
        )
    catalog = load_frozen_catalog()
    log.info("SEALED OOS — frozen top set of %d factors:", len(catalog))
    for n in catalog:
        log.info("  %s", n)
    log.info("OOS window %s -> %s (stage=oos_test). ONE SHOT.", OOS_START, OOS_END)

    t0 = time.time()
    factors_df, fwd_df = operators.compute_factors(
        catalog=catalog, start_date=OOS_START, end_date=OOS_END,
        horizons=HORIZONS, qlib_dir=str(PROJECT_ROOT / "data" / "qlib_data"),
        kernels=1, stage="oos_test",
    )
    t_compute = time.time() - t0
    log.info("compute_factors(oos_test) done in %.1fs; shape=%s", t_compute, factors_df.shape)

    # null / inf diagnostics BEFORE screening (evidence requirement)
    diag = {}
    for c in factors_df.columns:
        s = factors_df[c]
        n = len(s)
        n_inf = int(np.isinf(s.to_numpy(dtype="float64", na_value=np.nan)).sum())
        diag[c] = {"null_pct": round(100 * s.isna().mean(), 2), "n_inf": n_inf}

    t0 = time.time()
    results = run_batch_screening(
        factors_df, fwd_df, horizons=tuple(HORIZONS), engine="batch",
        progress_every=5, log=log,
    )
    t_screen = time.time() - t0
    results = results.copy()
    results["grade"] = results.apply(_classify_grade, axis=1)
    results["oos_null_pct"] = [diag.get(n, {}).get("null_pct") for n in results.index]
    results["oos_n_inf"] = [diag.get(n, {}).get("n_inf") for n in results.index]

    results.to_parquet(OUTDIR / "screening_oos_results.parquet", index=True)
    results.to_csv(OUTDIR / "screening_oos_report.csv", index=True)
    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "window": {"oos_start": OOS_START, "oos_end": OOS_END, "stage": "oos_test"},
        "horizons": HORIZONS,
        "frozen_topset_count": len(catalog),
        "frozen_topset": list(catalog.keys()),
        "grade_counts": {k: int(v) for k, v in results["grade"].value_counts().items()},
        "timing_seconds": {"compute_factors": round(t_compute, 2),
                           "run_batch_screening": round(t_screen, 2)},
        "one_shot": True,
        "note": "Sealed OOS run once on the predeclared frozen top set. No tuning, no re-selection.",
    }
    (OUTDIR / "screening_oos_run_metadata.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    log.info("Grade counts: %s", meta["grade_counts"])
    log.info("Wrote OOS artifacts under %s", OUTDIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
