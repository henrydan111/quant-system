# ──────────────────────────────────────────────────────────────────────
# PR 7 of 2026-05-26 freeze plan — SCRIPT_STATUS header block.
# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: joinquant_attribution_only
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: C
# notes: |
#   Closes out the catalog re-validation: the 20 Layer-2 composites
#   (get_composite_defs) + 4 industry-relative (get_industry_relative_defs)
#   that the 147-base walk-forward run did NOT cover (they need Layer-2
#   post-processing + SW2021 labels). Same predeclared walk-forward status rule
#   as revalidate_catalog_walkforward.py. ALSO introduces a LONG-ONLY top-bucket
#   metric (top-decile-minus-universe, sign-aligned) so long-only viability is
#   measured directly rather than inferred from IC / long-short Sharpe — the
#   distinction that matters in a no-shorting A-share book. Read-only.
# ──────────────────────────────────────────────────────────────────────
"""Re-validate the 24 derived catalog factors + long-only top-bucket metric."""

from __future__ import annotations

import json, logging, sys, time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_library import operators
from src.alpha_research.factor_library.catalog import (
    get_factor_catalog, get_composite_defs, get_industry_relative_defs,
)
from src.alpha_research.factor_eval.ic_analysis import (
    compute_ic_series, compute_ic_summary, compute_ic_by_year,
)
from src.alpha_research.factor_eval.quantile_analysis import compute_quantile_returns

OUTDIR = PROJECT_ROOT / "workspace" / "research" / "factor_expansion" / "catalog_revalidation"
START, END, IS_END, OOS_START = "2014-01-01", "2026-02-27", "2020-12-31", "2021-01-01"
HORIZON, NQ = 20, 10
ANN = 252.0 / HORIZON   # annualization for horizon-day overlapping forward returns

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("revalidate_derived")


def long_only_topbucket(factor: pd.Series, fwd: pd.Series, ic_sign: float) -> dict:
    """Top-decile-minus-universe excess return, sign-aligned so the 'good'
    decile is selected in the IC's predictive direction. Answers: does the LONG
    leg earn the premium (a no-shorting A-share book can only hold the long leg)?
    """
    if ic_sign == 0 or pd.isna(ic_sign):
        return {"lo_excess_ann": np.nan, "lo_sharpe": np.nan, "lo_hit": np.nan}
    qdf = compute_quantile_returns(factor, fwd, n_quantiles=NQ, min_obs=50)
    if qdf.empty:
        return {"lo_excess_ann": np.nan, "lo_sharpe": np.nan, "lo_hit": np.nan}
    # universe per-date = count-weighted mean across deciles (~equal-weight universe)
    uni = (qdf.assign(w=qdf["mean_return"] * qdf["count"])
              .groupby("date").apply(lambda g: g["w"].sum() / g["count"].sum()))
    good_q = int(qdf["quantile"].max()) if ic_sign > 0 else int(qdf["quantile"].min())
    good = qdf[qdf["quantile"] == good_q].set_index("date")["mean_return"]
    excess = (good - uni).dropna()
    if len(excess) < 50:
        return {"lo_excess_ann": np.nan, "lo_sharpe": np.nan, "lo_hit": np.nan}
    mu, sd = excess.mean(), excess.std()
    return {
        "lo_excess_ann": round(float(mu * ANN), 4),
        "lo_sharpe": round(float(mu / sd * np.sqrt(ANN)), 3) if sd > 0 else np.nan,
        "lo_hit": round(float((excess > 0).mean()), 3),
    }


def assign_status(field_ok, is_icir, oos_icir, sign_consistency):
    if not field_ok:
        return "draft", "field-ineligible — capped at draft"
    if pd.isna(oos_icir) or pd.isna(is_icir):
        return "draft", "insufficient IS or OOS data"
    if abs(oos_icir) < 0.03:
        return "deprecated", f"collapsed OOS (|OOS ICIR|={abs(oos_icir):.3f}<0.03)"
    if is_icir * oos_icir < 0 and abs(is_icir) >= 0.20:
        return "deprecated", f"IS/OOS sign FLIP (IS={is_icir:+.3f}, OOS={oos_icir:+.3f})"
    if (is_icir * oos_icir > 0) and abs(oos_icir) >= 0.10 and sign_consistency >= 0.70:
        return "candidate", f"walk-forward stable (OOS ICIR={oos_icir:+.3f}, consist={sign_consistency:.2f})"
    return "draft", f"marginal (OOS ICIR={oos_icir:+.3f}, consist={sign_consistency:.2f})"


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    full_catalog = get_factor_catalog(include_new_data=True)
    comp_defs = get_composite_defs()
    ind_defs = get_industry_relative_defs()

    # union of base components needed by composites + industry-rel bases
    needed = set()
    for c in comp_defs:
        needed.update(c["components"])
    for d in ind_defs:
        needed.add(d["base"])
    sub_catalog = {n: full_catalog[n] for n in needed if n in full_catalog}
    log.info("Computing %d base components for %d composites + %d industry-rel, %s->%s",
             len(sub_catalog), len(comp_defs), len(ind_defs), START, END)

    t0 = time.time()
    base_df, fwd_df = operators.compute_factors(
        catalog=sub_catalog, start_date=START, end_date=END, horizons=[HORIZON],
        qlib_dir=str(PROJECT_ROOT / "data" / "qlib_data"), kernels=1, stage="is_only")
    # market_cap for size_industry_neutralize industry-rel
    mcap_df, _ = operators.compute_factors(
        catalog={"market_cap": "Ref($total_mv, 1)"}, start_date=START, end_date=END,
        horizons=[HORIZON], qlib_dir=str(PROJECT_ROOT / "data" / "qlib_data"),
        kernels=1, stage="is_only")
    log.info("base compute done in %.0fs; base shape=%s", time.time() - t0, base_df.shape)
    fwd = fwd_df[f"fwd_ret_{HORIZON}d"] if f"fwd_ret_{HORIZON}d" in fwd_df.columns else fwd_df.iloc[:, 0]

    # Layer-2: 20 composites
    comp_df = operators.add_composites(base_df.copy(), composite_defs=comp_defs)
    comp_names = [c["name"] for c in comp_defs]
    # Layer-2: 4 industry-relative
    from src.data_infra.provider_metadata import build_industry_series_asof
    industry_series = build_industry_series_asof(base_df.index, "L1")
    ind_df = operators.add_industry_relative_composites(
        base_df.copy(), industry_series, market_cap=mcap_df["market_cap"], defs=ind_defs)
    ind_names = [d["name"] for d in ind_defs]

    derived = {}
    for n in comp_names:
        if n in comp_df.columns:
            derived[n] = comp_df[n]
    for n in ind_names:
        if n in ind_df.columns:
            derived[n] = ind_df[n]
    log.info("built %d derived factors (%d composite + %d industry-rel)",
             len(derived), len(comp_names), len(ind_names))

    rows = []
    for i, (name, series) in enumerate(derived.items(), 1):
        ic = compute_ic_series(series, fwd)
        if ic.empty:
            rows.append({"factor": name, "kind": "composite" if name in comp_names else "industry_rel",
                         "full_rank_icir": None, "is_rank_icir": None, "oos_rank_icir": None,
                         "sign_consistency": None, "status": "draft", "reason": "no IC",
                         "lo_excess_ann": None, "lo_sharpe": None, "lo_hit": None})
            continue
        full = compute_ic_summary(ic)["rank_icir"]
        is_icir = compute_ic_summary(ic[ic.index <= pd.Timestamp(IS_END)])["rank_icir"]
        oos_icir = compute_ic_summary(ic[ic.index >= pd.Timestamp(OOS_START)])["rank_icir"]
        yearly = compute_ic_by_year(ic)
        sign_consistency = ((np.sign(yearly["mean_rank_ic"]) == np.sign(full)).sum() / len(yearly)
                            if len(yearly) and full != 0 else np.nan)
        status, reason = assign_status(True, is_icir, oos_icir, sign_consistency)  # derived inherit approved base fields
        lo = long_only_topbucket(series, fwd, np.sign(full))
        rows.append({"factor": name, "kind": "composite" if name in comp_names else "industry_rel",
                     "full_rank_icir": round(float(full), 4), "is_rank_icir": round(float(is_icir), 4),
                     "oos_rank_icir": round(float(oos_icir), 4),
                     "sign_consistency": round(float(sign_consistency), 3) if pd.notna(sign_consistency) else None,
                     "status": status, "reason": reason, **lo})
        log.info("  %-26s status=%-10s OOS_ICIR=%s lo_sharpe=%s", name, status,
                 rows[-1]["oos_rank_icir"], rows[-1]["lo_sharpe"])

    df = pd.DataFrame(rows)
    df.to_csv(OUTDIR / "derived_revalidation_status.csv", index=False)
    from collections import Counter
    meta = {"generated_at": datetime.now().isoformat(timespec="seconds"),
            "n_derived": len(derived), "status_counts": dict(Counter(r["status"] for r in rows)),
            "window": {"start": START, "is_end": IS_END, "oos_start": OOS_START, "end": END},
            "horizon": HORIZON, "long_only_metric": "top-decile minus count-weighted universe, sign-aligned, ann + sharpe + hit"}
    (OUTDIR / "derived_revalidation_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log.info("status counts: %s", meta["status_counts"])
    log.info("wrote %s", OUTDIR / "derived_revalidation_status.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
