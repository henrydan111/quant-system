# ──────────────────────────────────────────────────────────────────────
# Phase 1 — Tier-1 new-data factor IS-2014-2020 discovery screen.
# script_status: historical_investigation
# formal_research_allowed: false
# deployment_target: research
# requires_provider_manifest: false
# requires_preload_strict: false
# pr2_audit_class: B
# notes: |
#   Runs the FROZEN PRE_REGISTRATION_tier1.md spec (committed 486860e BEFORE this
#   ran). IS-2014-2020 ONLY, enforced structurally: a ResearchAccessContext with
#   allowed_end=2020-12-31 around compute_factors (so qlib_windowed_features
#   blocks any 2021+ read), AND forward returns end at the 2020-12-31 data
#   boundary (NaN for the last h days -> no 2021 bar). Computes RankIC / RankICIR
#   / quintile monotonicity / decay per the pre-set bar. No 2021-26 performance.
# ──────────────────────────────────────────────────────────────────────
"""Tier-1 new-data factor IS discovery screen (frozen pre-registration)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from src.alpha_research.factor_library.operators import compute_factors
from src.alpha_research.factor_lifecycle import metrics as lf_metrics
from src.alpha_research.factor_eval.quantile_analysis import compute_quantile_returns
from src.research_orchestrator.research_access_context import research_access_context, ResearchAccessContext

OUT = ROOT / "workspace" / "outputs" / "factor_expansion_newdata"
OUT.mkdir(parents=True, exist_ok=True)
QLIB = str(ROOT / "data" / "qlib_data")
COMPUTE_START, IS_END = "2013-01-01", "2020-12-31"
HORIZONS = [5, 10, 20]
PRIMARY_H = 20

# FROZEN Tier-1 set (PRE_REGISTRATION_tier1.md §3). Sign = economic prior.
FACTORS = {
    "flow_mainforce_imbalance_5d":  "Mean((Ref($buy_lg_amount,1)+Ref($buy_elg_amount,1)-Ref($sell_lg_amount,1)-Ref($sell_elg_amount,1))/(Ref($amount,1)+1),5)",
    "flow_mainforce_imbalance_20d": "Mean((Ref($buy_lg_amount,1)+Ref($buy_elg_amount,1)-Ref($sell_lg_amount,1)-Ref($sell_elg_amount,1))/(Ref($amount,1)+1),20)",
    "flow_retail_pressure_5d":      "0 - Mean((Ref($buy_sm_amount,1)-Ref($sell_sm_amount,1))/(Ref($amount,1)+1),5)",
    "flow_elg_concentration_5d":    "Mean((Ref($buy_elg_amount,1)-Ref($sell_elg_amount,1))/(Ref($buy_elg_amount,1)+Ref($sell_elg_amount,1)+1),5)",
    "lev_margin_bal_growth_20d":    "Delta(Ref($rzrqye,1),20)/(Ref($rzrqye,1)+1)",
    "lev_short_interest_ratio":     "Ref($rqye,1)/(Ref($rzrqye,1)+1)",
    "lev_margin_buy_intensity_5d":  "Mean(Ref($rzmre,1),5)/(Ref($amount,1)+1)",
    "lev_margin_to_mktcap":         "Ref($rzye,1)/(Ref($total_mv,1)+1)",
}
# pre-set survivor bar (PRE_REGISTRATION_tier1.md §4)
BAR_RANKICIR, BAR_MEAN_RANKIC = 0.30, 0.015


def _fwd_col(fwd: pd.DataFrame, h: int):
    for c in fwd.columns:
        if str(h) in str(c):
            return c
    return None


def _monotone_quintiles(factor: pd.Series, fwd: pd.Series, sign: float) -> bool:
    try:
        q = compute_quantile_returns(factor, fwd, n_quantiles=5)
        if q is None or q.empty or "mean_return" not in q.columns:
            return False
        m = q.groupby("quantile")["mean_return"].mean()  # column is mean_return, not return
        lo, hi = m.loc[m.index.min()], m.loc[m.index.max()]
        return (hi - lo) * sign > 0  # pre-reg: top-vs-bottom quintile spread consistent with RankIC sign
    except Exception:
        return False


def main() -> int:
    ctx = ResearchAccessContext(
        run_id="tier1_newdata_is_screen", step_id="phase1_is_screen", stage="sandbox_screening",
        design_hash="tier1_newdata_prereg_486860e",
        allowed_start=pd.Timestamp(COMPUTE_START), allowed_end=pd.Timestamp(IS_END),
        provider_build_id="prod_full_20260421_namespace_v1",
        calendar_policy_id="frozen_20260227_system_build", holdout_seal_claimed=False,
    )
    print(f"[screen] computing {len(FACTORS)} Tier-1 factors over IS {COMPUTE_START}..{IS_END} "
          f"(window-enforced, no 2021+ read)...", flush=True)
    with research_access_context(ctx):
        factors, fwd = compute_factors(catalog=dict(FACTORS), start_date=COMPUTE_START, end_date=IS_END,
                                       horizons=HORIZONS, qlib_dir=QLIB, kernels=1, stage="sandbox_screening")
    print(f"[screen] factors {factors.shape}; fwd cols {list(fwd.columns)}; "
          f"dates {factors.index.get_level_values(0).min().date()}..{factors.index.get_level_values(0).max().date()}", flush=True)

    results = {}
    for name in FACTORS:
        per_h = {}
        for h in HORIZONS:
            fc = _fwd_col(fwd, h)
            ic_df = lf_metrics.factor_ic(factors[name], fwd[fc])
            ricir = lf_metrics.rank_icir(ic_df)
            mric = float(ic_df["RankIC"].dropna().mean()) if "RankIC" in getattr(ic_df, "columns", []) else float("nan")
            per_h[h] = {"rank_icir": round(ricir, 4) if ricir == ricir else None,
                        "mean_rankic": round(mric, 5) if mric == mric else None}
        ricir20 = per_h[PRIMARY_H]["rank_icir"]
        mric20 = per_h[PRIMARY_H]["mean_rankic"]
        signs = [np.sign(per_h[h]["mean_rankic"]) for h in HORIZONS if per_h[h]["mean_rankic"] is not None]
        decay_consistent = len(signs) == len(HORIZONS) and len(set(signs)) == 1
        mono = _monotone_quintiles(factors[name], fwd[_fwd_col(fwd, PRIMARY_H)], np.sign(mric20) if mric20 else 1.0)
        survivor = bool(ricir20 is not None and abs(ricir20) >= BAR_RANKICIR
                        and mric20 is not None and abs(mric20) >= BAR_MEAN_RANKIC
                        and mono and decay_consistent)
        results[name] = {"per_horizon": per_h, "rank_icir_20d": ricir20, "mean_rankic_20d": mric20,
                         "quintile_monotone": mono, "decay_sign_consistent": decay_consistent, "survivor": survivor}

    survivors = [n for n, r in results.items() if r["survivor"]]
    out = {"pre_registration": "PRE_REGISTRATION_tier1.md (frozen 486860e)", "is_window": [COMPUTE_START, IS_END],
           "effective_trials": len(FACTORS), "bar": {"rank_icir": BAR_RANKICIR, "mean_rankic": BAR_MEAN_RANKIC},
           "results": results, "survivors": survivors}
    (OUT / "phase1_is_screen.json").write_text(json.dumps(out, indent=2, default=str))

    print(f"\n{'factor':32s} {'RankICIR_20d':>12s} {'meanRankIC':>11s} {'mono':>5s} {'decay':>6s} {'SURV':>5s}", flush=True)
    for n, r in sorted(results.items(), key=lambda kv: -abs(kv[1]["rank_icir_20d"] or 0)):
        print(f"  {n:30s} {str(r['rank_icir_20d']):>12s} {str(r['mean_rankic_20d']):>11s} "
              f"{str(r['quintile_monotone']):>5s} {str(r['decay_sign_consistent']):>6s} {str(r['survivor']):>5s}", flush=True)
    print(f"\n[screen] survivors ({len(survivors)}/{len(FACTORS)}): {survivors}", flush=True)
    print(f"[screen] saved {OUT / 'phase1_is_screen.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
