"""P1b — production driver (verify pass): wire the unified-eval helpers into an end-to-end per-factor
record on the 7 representative factors, with the methodology FROZEN + HASHED.

Computes (all IS-only, zero OOS spend, reusing the tested unified_eval helpers):
  Tier 1: heldout RankICIR + sign-consistency (run_is_walk_forward); mean RankIC + IC hit-rate +
          HAC t (overlap-adjusted); monotonicity shape (NON-circular orientation = early-window sign);
          one-way turnover; coverage + tier; leak-safe decay vector.
  Tier 2: residual IC vs the approved-STABLE reference set (excl. provisionals, leave-one-out) AND vs
          the frozen style_controls_v1.
Each record is stamped with the EvalMethodology.methodology_hash.

DEFERRED to P1b-data (need extra plumbing): neutralized IC (mcap+industry), long-leg-excess vs both
benchmarks (index fwd returns). Read-only; no registry writes; panel cached to parquet.
"""
from __future__ import annotations

import json
import logging
import sys
import time
import traceback
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
np.seterr(all="ignore")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.factor_library import operators as op
from src.alpha_research.factor_library.catalog import get_factor_catalog
from src.alpha_research.factor_eval import ic_analysis as ica
from src.alpha_research.factor_eval import quantile_analysis as qa
from src.alpha_research.factor_eval.unified_eval import (
    EvalMethodology,
    STYLE_CONTROLS_V1,
    classify_quantile_shape,
    hac_mean_tstat,
    leak_safe_decay_ic_vector,
    one_way_turnover,
    residual_ic_vs_controls,
    resolve_orientation,
)
from src.alpha_research.factor_lifecycle.walk_forward_validation import (
    build_is_windowed_panel,
    run_is_walk_forward,
)
from src.alpha_research.walk_forward import TimeSplit

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("unified_eval_driver")

TIME_SPLIT = TimeSplit("2014-01-01", "2020-12-31", "2021-01-01", "2022-01-01")
HORIZON = 20
QLIB_DIR = PROJECT_ROOT / "data" / "qlib_data"
OUTDIR = PROJECT_ROOT / "workspace" / "outputs"
PANEL_CACHE = OUTDIR / "unified_eval_driver_panel.parquet"
OUT = OUTDIR / "unified_eval_driver.json"
ADJ_COL = "__adj_close__"
LABEL_COL = "__label__"

PICKS = {
    "earn_eps_diffusion_60": "approved", "liq_zero_ret_days_10d": "approved",
    "qual_piotroski_fscore_9pt": "approved", "liq_vol_cv_20d": "candidate",
    "qual_gross_profitability": "candidate", "rev_up_down_ratio_20d": "candidate",
    "qual_q_gross_margin": "draft",
}
APPROVED_8 = ["earn_eps_diffusion_60", "earn_eps_diffusion_120", "grow_n_income_attr_p_yoy_accel_q",
              "grow_operate_profit_yoy_accel_q", "grow_total_revenue_yoy_accel_q",
              "liq_zero_ret_days_10d", "qual_piotroski_fscore_9pt", "rev_turnover_spike_5d"]
PROVISIONAL = ["earn_eps_diffusion_60", "earn_eps_diffusion_120"]
REFERENCE_STABLE = [a for a in APPROVED_8 if a not in PROVISIONAL]


def _to_dt_inst(s):
    return (s.swaplevel(0, 1) if s.index.names[0] != "datetime" else s).sort_index()


def _build_or_load_panel(needed):
    if PANEL_CACHE.exists():
        log.info("Loading cached driver panel %s ...", PANEL_CACHE)
        return pd.read_parquet(PANEL_CACHE)
    full = get_factor_catalog(include_new_data=True)
    catalog = {n: full[n] for n in needed}
    catalog[ADJ_COL] = op.ADJ_CLOSE
    t0 = time.time()
    log.info("Computing %d factors + adj_close over [%s, %s] ...", len(needed),
             TIME_SPLIT.is_start, TIME_SPLIT.is_end)
    panel, _ = op.compute_factors(catalog=catalog, start_date=TIME_SPLIT.is_start,
                                  end_date=TIME_SPLIT.is_end, horizons=None,
                                  qlib_dir=str(QLIB_DIR), kernels=1, stage="is_only")
    log.info("Computed in %.0fs: shape=%s", time.time() - t0, panel.shape)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(PANEL_CACHE)
    return panel


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    needed = sorted(set(PICKS) | set(APPROVED_8) | set(STYLE_CONTROLS_V1))
    raw = _build_or_load_panel(needed)

    adj_close = raw[ADJ_COL]
    factor_panel = raw[[c for c in raw.columns if c != ADJ_COL]]
    windowed = build_is_windowed_panel(factor_panel, adj_close, is_end=TIME_SPLIT.is_end, horizon=HORIZON)
    del factor_panel

    method = EvalMethodology(
        is_start=TIME_SPLIT.is_start, is_end=TIME_SPLIT.is_end,
        reference_set_stable=tuple(REFERENCE_STABLE), reference_set_current=tuple(APPROVED_8),
        provisional_factors=tuple(PROVISIONAL),
    )
    log.info("methodology_hash=%s", method.methodology_hash)

    # heldout ICIR + sign for ALL factors in one pass
    wf = run_is_walk_forward(panel=windowed, time_split=TIME_SPLIT, horizon=HORIZON, factor_origin="a_priori")
    wf_rows = {r["factor"]: dict(r) for r in wf.rows}
    label = _to_dt_inst(windowed.label)
    del windowed  # free the ~380MB windowed subset before the per-factor loop

    # fac = column VIEWS into raw (instrument, datetime order) — NO 25× dti copies (the prior OOM).
    # Helpers normalize index order on demand; per-factor copies are transient and freed each iter.
    fac = {n: raw[n] for n in needed}
    all_dates = sorted(label.index.get_level_values("datetime").unique())
    orient_train = set(all_dates[: int(len(all_dates) * 0.6)])  # early-window orientation (non-circular)

    report = []
    for fid, status in PICKS.items():
      try:
        f_dt = _to_dt_inst(fac[fid])  # (datetime, instrument) for the IC/quantile helpers
        ic = ica.compute_ic_series(f_dt, label, min_obs=30)
        summ = ica.compute_ic_summary(ic)
        rank_ic = ic["RankIC"].dropna()
        hac = hac_mean_tstat(rank_ic, lags=method.hac_lags)

        # NON-circular orientation → shape
        orient = resolve_orientation(rank_ic.rename(None), train_dates=orient_train, min_train_t=1.0)
        of = f_dt * orient["sign"]
        try:
            qdf = qa.compute_quantile_returns(of, label, n_quantiles=method.n_quantiles, min_obs=50)
            qs = qa.compute_quantile_summary(qdf)
            mono = classify_quantile_shape(qs["annualized_return"].tolist())
        except Exception as e:  # noqa: BLE001
            mono = {"mono_shape": None, "mono_reason": f"error:{e}"}

        turn = one_way_turnover(fac[fid], rebalance_days=method.rebalance_days, top_q=method.top_q)
        cov = float(fac[fid].notna().mean())
        cov_tier = "full" if cov >= 0.90 else ("broad" if cov >= 0.50 else "sub")
        # decay needs the RAW (instrument, datetime) factor + full adj_close (build_is_windowed_panel)
        decay = leak_safe_decay_ic_vector(fac[fid], adj_close, is_end=TIME_SPLIT.is_end,
                                          horizons=method.decay_horizons)

        # Tier 2: residual vs approved-STABLE (leave-one-out) + vs style_controls_v1
        base_stable = [b for b in REFERENCE_STABLE if b != fid]
        resid_appr = residual_ic_vs_controls(fid, fac, label, control_names=base_stable,
                                             winsor=method.winsor_limits, hac_lags=method.hac_lags)
        ctrls = [c for c in STYLE_CONTROLS_V1 if c != fid]
        resid_style = residual_ic_vs_controls(fid, fac, label, control_names=ctrls,
                                              winsor=method.winsor_limits, hac_lags=method.hac_lags)

        report.append({
            "factor": fid, "registry_status": status, "methodology_hash": method.methodology_hash,
            "tier1": {
                "heldout_rank_icir": wf_rows.get(fid, {}).get("heldout_rank_icir"),
                "sign_consistency": wf_rows.get(fid, {}).get("sign_consistency"),
                "mean_rank_ic": summ.get("mean_rank_ic"), "ic_hit_rate": summ.get("ic_hit_rate"),
                "mean_rank_ic_hac_t": hac.get("hac_t"), "hac_small_sample": hac.get("small_sample_warning"),
                "mono_shape": mono.get("mono_shape"), "mono_reason": mono.get("mono_reason"),
                "direction_source": orient["direction_source"], "orientation_valid": orient["orientation_valid"],
                "turnover_ann": turn.get("turnover_ann"), "tie_rate": turn.get("tie_rate"),
                "coverage": cov, "coverage_tier": cov_tier,
                "decay_vector": {h: v["rank_icir"] for h, v in decay["vector"].items()},
                "decay_half_life_vs_shortest": decay["half_life_vs_shortest"],
            },
            "tier2": {
                "resid_ic_vs_approved_stable": resid_appr.get("residual_mean_rank_ic"),
                "resid_icir_vs_approved_stable": resid_appr.get("residual_rank_icir"),
                "resid_coverage_vs_approved_stable": resid_appr.get("residual_coverage"),
                "resid_ic_vs_style_controls_v1": resid_style.get("residual_mean_rank_ic"),
                "resid_hac_t_vs_style_controls_v1": resid_style.get("residual_hac_t"),
                "resid_coverage_vs_style_controls_v1": resid_style.get("residual_coverage"),
            },
        })
        log.info("done %s", fid)
      except Exception as exc:  # noqa: BLE001 — log + continue so one bad factor doesn't abort the run
        log.error("FAILED %s: %s", fid, exc)
        traceback.print_exc()
        report.append({"factor": fid, "registry_status": status,
                       "error": f"{type(exc).__name__}: {exc}"})

    payload = {
        "methodology": {
            "hash": method.methodology_hash, "is_window": [TIME_SPLIT.is_start, TIME_SPLIT.is_end],
            "reference_set_stable": REFERENCE_STABLE, "provisional_excluded": PROVISIONAL,
            "style_controls_v1": list(STYLE_CONTROLS_V1), "hac_lags": method.hac_lags,
            "benchmark_policy": method.benchmark_policy, "mt_t_bar": method.mt_t_bar,
        },
        "deferred_to_p1b_data": ["neutralized_rank_icir (mcap+industry)",
                                 "long_leg_excess_ir_proxy_is vs CSI300/CSI500 (index fwd returns)"],
        "factors": report,
    }
    OUT.write_text(json.dumps(payload, indent=2, default=lambda x: None), encoding="utf-8")
    log.info("=== UNIFIED EVAL DRIVER (methodology_hash=%s) ===", method.methodology_hash)
    log.info("%-28s %-9s %8s %8s %7s %6s %-14s %10s %10s", "factor", "status", "heldICIR", "HAC-t",
             "turn", "cov", "mono_shape", "rsd_appr", "rsd_style")
    for r in report:
        t1, t2 = r["tier1"], r["tier2"]
        def p(x, n=3):
            return f"{x:.{n}f}" if isinstance(x, (int, float)) else "NA"
        log.info("%-28s %-9s %8s %8s %7s %6s %-14s %10s %10s", r["factor"], r["registry_status"],
                 p(t1["heldout_rank_icir"]), p(t1["mean_rank_ic_hac_t"], 2), p(t1["turnover_ann"], 1),
                 p(t1["coverage"], 2), str(t1["mono_shape"]),
                 p(t2["resid_ic_vs_approved_stable"]), p(t2["resid_ic_vs_style_controls_v1"]))
    log.info("wrote %s", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
