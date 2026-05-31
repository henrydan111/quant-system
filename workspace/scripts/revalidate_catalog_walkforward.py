# ──────────────────────────────────────────────────────────────────────
# PR 7 of 2026-05-26 freeze plan — SCRIPT_STATUS header block.
# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: joinquant_attribution_only
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   Walk-forward re-validation of the 147 base catalog factors (the existing
#   "171-factor" library, Layer-1 portion). The catalog was previously graded
#   ONLY on a full-sample 2012-2026 IC pass with no holdout (all 171 are status
#   `draft`). This re-validates each factor with a proper IS(2014-2020) /
#   OOS(2021-2026) split AND per-year fold-stability, then assigns a status by
#   a PREDEFINED mechanical rule (below). Read-only w.r.t. registry/catalog;
#   writes a status-assignment CSV + per-year IC table.
#
#   HONESTY / CONTAMINATION NOTE: the 147 factor DEFINITIONS are a-priori
#   (literature/economic-hypothesis expressions with conventional windows), NOT
#   searched against the 2021-2026 window, and NONE has ever been promoted using
#   OOS (all `draft`). So splitting into IS/OOS here is a LEGITIMATE first clean
#   split-test (no selection used the OOS). It is NOT a pristine never-computed
#   OOS (the old full-sample grade folded 2021-2026 in). Per-year fold-stability
#   is the primary, multiple-testing-robust status driver; the IS/OOS split is a
#   secondary cross-check. After this run, 2021-2026 should be treated as spent.
#
#   PREDEFINED STATUS RULE (frozen here, before results):
#     field_eligible := expression references ONLY `approved` fields (formal_validation stage)
#     sign_consistency := fraction of calendar-year folds whose annual mean RankIC
#                         has the same sign as the full-period mean RankIC
#     candidate  := field_eligible AND sign(IS ICIR)==sign(OOS ICIR)!=0 AND
#                   |OOS rank_icir_20| >= 0.10 AND sign_consistency >= 0.70
#     deprecated := (sign(IS)!=sign(OOS) with |IS rank_icir_20|>=0.20)  OR
#                   |OOS rank_icir_20| < 0.03   (demonstrably failed the holdout)
#     draft      := everything else (incl. ALL field-ineligible factors, capped)
#     approved   := NEVER assigned here — requires the strategy-level promotion
#                   gate (EventDriven tradability + independent PIT reproduction).
# ──────────────────────────────────────────────────────────────────────
"""Walk-forward re-validation of the base catalog factors."""

from __future__ import annotations

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

from src.alpha_research.factor_library import operators
from src.alpha_research.factor_library.catalog import get_factor_catalog
from src.alpha_research.factor_eval.ic_analysis import (
    compute_ic_series, compute_ic_summary, compute_ic_by_year,
)
from src.data_infra.field_registry import load_field_registry, extract_qlib_fields

OUTDIR = PROJECT_ROOT / "workspace" / "research" / "factor_expansion" / "catalog_revalidation"
START, END = "2014-01-01", "2026-02-27"
IS_END = "2020-12-31"
OOS_START = "2021-01-01"
HORIZON = 20

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("revalidate_catalog")


def field_eligible(expr: str, registry) -> bool:
    for tok in extract_qlib_fields(expr):
        if not registry.resolve_field(tok, "formal_validation").allowed:
            return False
    return True


def assign_status(field_ok, is_icir, oos_icir, sign_consistency) -> tuple[str, str]:
    if not field_ok:
        return "draft", "field-ineligible (quarantine/pending/unknown field) — capped at draft"
    if pd.isna(oos_icir) or pd.isna(is_icir):
        return "draft", "insufficient IS or OOS data"
    if abs(oos_icir) < 0.03:
        return "deprecated", f"collapsed OOS (|OOS ICIR|={abs(oos_icir):.3f} < 0.03)"
    if is_icir * oos_icir < 0 and abs(is_icir) >= 0.20:
        return "deprecated", f"IS/OOS sign FLIP (IS={is_icir:+.3f}, OOS={oos_icir:+.3f})"
    if (is_icir * oos_icir > 0) and abs(oos_icir) >= 0.10 and sign_consistency >= 0.70:
        return "candidate", (f"walk-forward stable (OOS ICIR={oos_icir:+.3f}, "
                             f"sign-consistency={sign_consistency:.2f})")
    return "draft", (f"marginal (OOS ICIR={oos_icir:+.3f}, "
                     f"sign-consistency={sign_consistency:.2f})")


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    catalog = dict(get_factor_catalog(include_new_data=True))   # 147 base
    registry = load_field_registry(PROJECT_ROOT / "config" / "field_registry" / "field_status.yaml")
    log.info("Re-validating %d base catalog factors, %s -> %s (walk-forward + IS/OOS).",
             len(catalog), START, END)

    t0 = time.time()
    factors_df, fwd_df = operators.compute_factors(
        catalog=catalog, start_date=START, end_date=END, horizons=[HORIZON],
        qlib_dir=str(PROJECT_ROOT / "data" / "qlib_data"), kernels=1, stage="is_only",
    )
    log.info("compute_factors done in %.0fs; shape=%s", time.time() - t0, factors_df.shape)
    fwd_col = f"fwd_ret_{HORIZON}d"
    fwd = fwd_df[fwd_col] if fwd_col in fwd_df.columns else fwd_df.iloc[:, 0]

    rows = []
    t0 = time.time()
    for i, name in enumerate(catalog, 1):
        expr = catalog[name]
        fld_ok = field_eligible(expr, registry)
        ic = compute_ic_series(factors_df[name], fwd)
        if ic.empty:
            rows.append({"factor": name, "field_eligible": fld_ok, "full_rank_icir": np.nan,
                         "is_rank_icir": np.nan, "oos_rank_icir": np.nan,
                         "sign_consistency": np.nan, "n_years": 0,
                         "status": "draft", "reason": "no IC (degenerate/all-NaN)"})
            continue
        full = compute_ic_summary(ic)["rank_icir"]
        ic_is = ic[ic.index <= pd.Timestamp(IS_END)]
        ic_oos = ic[ic.index >= pd.Timestamp(OOS_START)]
        is_icir = compute_ic_summary(ic_is)["rank_icir"] if len(ic_is) else np.nan
        oos_icir = compute_ic_summary(ic_oos)["rank_icir"] if len(ic_oos) else np.nan
        yearly = compute_ic_by_year(ic)
        if len(yearly) and not pd.isna(full) and full != 0:
            same = (np.sign(yearly["mean_rank_ic"]) == np.sign(full)).sum()
            sign_consistency = same / len(yearly)
        else:
            sign_consistency = np.nan
        status, reason = assign_status(fld_ok, is_icir, oos_icir, sign_consistency)
        rows.append({"factor": name, "field_eligible": fld_ok,
                     "full_rank_icir": round(float(full), 4) if pd.notna(full) else None,
                     "is_rank_icir": round(float(is_icir), 4) if pd.notna(is_icir) else None,
                     "oos_rank_icir": round(float(oos_icir), 4) if pd.notna(oos_icir) else None,
                     "sign_consistency": round(float(sign_consistency), 3) if pd.notna(sign_consistency) else None,
                     "n_years": int(len(yearly)), "status": status, "reason": reason})
        if i % 25 == 0:
            log.info("  scored %d/%d", i, len(catalog))
    log.info("IC + status done in %.0fs", time.time() - t0)

    df = pd.DataFrame(rows).sort_values(
        ["status", "oos_rank_icir"], key=lambda s: s.abs() if s.name == "oos_rank_icir" else s,
        ascending=[True, False])
    df.to_csv(OUTDIR / "catalog_revalidation_status.csv", index=False)
    from collections import Counter
    meta = {"generated_at": datetime.now().isoformat(timespec="seconds"),
            "window": {"start": START, "is_end": IS_END, "oos_start": OOS_START, "end": END},
            "horizon": HORIZON, "n_factors": len(catalog),
            "status_counts": dict(Counter(r["status"] for r in rows)),
            "field_ineligible_count": int(sum(1 for r in rows if not r["field_eligible"])),
            "method": "walk-forward per-year fold-stability + IS/OOS split; a-priori factors, "
                      "unpromoted; 2021-2026 = first clean split (not pristine OOS).",
            "approved_note": "approved NOT assigned here — requires strategy-level promotion gate."}
    (OUTDIR / "catalog_revalidation_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log.info("status counts: %s", meta["status_counts"])
    log.info("field-ineligible (capped draft): %d", meta["field_ineligible_count"])
    log.info("wrote %s", OUTDIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
